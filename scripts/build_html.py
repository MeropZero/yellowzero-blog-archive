# -*- coding: utf-8 -*-
"""生成可离线浏览的HTML存档：索引首页 + 每篇独立页面（图片本地化）"""
import re, html, json, os, glob, struct

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(BASE, "articles")
PAGE_DIR = os.path.join(BASE, "page")
os.makedirs(PAGE_DIR, exist_ok=True)

manifest = json.load(open(os.path.join(BASE, '_manifest.json'), encoding='utf-8'))

# 每篇正文内容已经在 articles/<blogid>.html 里，是干净的 HTML 片段（含 <h1> 标题、时间、正文）
# 我们不再从 save 的整个 html 提取，而是直接用保存的正文片段，但去掉其自带标题，统一用索引构建页面

def build_article_page(it):
    """为单篇文章生成独立页面，图片引用本地 images/"""
    bid = it['blogid']
    title = it['title']
    time_ = it['time']
    # 读取正文片段
    fpath = os.path.join(ART_DIR, bid + '.html')
    if not os.path.exists(fpath):
        return None
    raw = open(fpath, encoding='utf-8', errors='ignore').read()
    # 移除片段自带的 <meta>、<h1>、时间 div（用统一模板重建）
    raw = re.sub(r'<meta[^>]*>', '', raw)
    raw = re.sub(r'<h1[^>]*>.*?</h1>', '', raw, flags=re.S)
    raw = re.sub(r'<div class="post-time">.*?</div>', '', raw, flags=re.S)
    # 只保留到正文结束注释为止，去掉其后的分享/评论等残留组件（含外部JS）
    raw = raw.split('<!-- 正文结束 -->')[0]
    body = raw.strip()
    # 删除所有 <script> 及其内容（外部脚本离线无意义）
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.S)
    # 删除所有协议相对 / 绝对外链脚本的引用标签
    body = re.sub(r'<script[^>]*>', '', body)
    # 处理图片：把占位 src 删掉，保留本地 src（src="images/xxx"）
    # 新浪懒加载：<img src="//simg...sg_trans.gif" src="images/xxx.jpg" ...>
    # 需要删除第一个占位 src 属性，让第二个本地 src 生效
    body = re.sub(r'\s+src="//simg\.sinajs\.cn[^"]*"', '', body)
    # 兜底：任何指向 simg.sinajs.cn 占位图的 src 都清掉
    body = re.sub(r'\s+src="[^"]*sg_trans\.gif[^"]*"', '', body)
    # 清掉遗留的 src="//x" 协议相对引用（外部资源）
    body = re.sub(r'\s+(?:src|href)="//[^"]*"', '', body)
    # ---- 剥离新浪编辑器残留的"死链锚点"，防止文字/图片被错误包裹成超链接 ----
    # 原始博文里混有大量 <A HREF="file://Towing-share/...">（2007年本地共享路径，离线无效）
    # 和 <A HREF="http://album.sina.com.cn/pic...">（相册原图链接，图已本地化，无需再跳）。
    # 这些锚点若只删闭合 </A> 而保留开标签，会导致开标签之后的所有文字被"未闭合锚点"误包成
    # 指向死链图片的超链接（用户反馈的现象）。正确做法是整对删除死链锚点，仅保留内层 img。
    # ⭐ 重要：本步必须在"清理 sinaimg.cn 外链 href"【之前】执行——早期文章的
    #    <img src="//simg...sg_trans.gif"> 是懒加载占位，真实图片 id 藏在死链
    #    <A href="...&url=<sN.sinaimg.cn/<size>/<imgid>>"> 的 url= 里。只有 href 还存在时才能
    #    提取到 imgid 并映射到 manifest 本地文件。若先清 href，这些锚点不再匹配 HREF= 模式，
    #    内层 img 就会失去唯一可用的图 id，最终渲染成"无法离线显示"占位块（用户报告的 dwoa 等
    #    2008/2009 页图片误判为失效的根因）。注入路径用 relative 形式 "images/<local>"，
    #    由后面统一的 "images/" -> "../images/" 前缀步骤补全。
    # 建立 imgid -> local 映射（manifest images: local -> url，url 含 real id）
    _bid_imgid2local = {}
    for _loc, _uv in (it.get('images', {}).items() if isinstance(it.get('images'), dict) else []):
        _m = re.search(r'/s\d+\.sinaimg\.cn/(?:orignal|bmiddle|middle)/([0-9a-z]+)', _uv)
        if _m:
            _bid_imgid2local.setdefault(_m.group(1), _loc)
    def _strip_dead_anchors(body):
        # 死链锚点 <A href="..."> 的开标签（协带 photo.blog / album / file / control 死链）
        OUTER = re.compile(r'<A\s+HREF="([^"]*(?:file://[^"]*|album\.sina\.com\.cn[^"]*|'
                           r'photo\.blog\.sina\.com\.cn[^"]*|control\.blog\.sina\.com\.cn[^"]*))"[^>]*>(.*?)</A>',
                           re.I | re.S)
        def _kill(m):
            href = m.group(1)          # 锚点整个 href
            inner = m.group(2)          # <a> 内部内容
            imgs = re.findall(r'<img[^>]*>', inner, flags=re.I)
            if not imgs:
                return ''
            # 从 href 提取真实图 id（url=<sN.sinaimg.cn/<size>/<imgid>>）
            _url_id = None
            _um = re.search(r'url=(?:https?://)?s\d+\.sinaimg\.cn/(?:orignal|bmiddle|middle)/([0-9a-z]+)', href)
            if _um:
                _url_id = _um.group(1)
            # 直链相册锚点 <a href="http://album.sina.com.cn/pic/<id>"> 内层 img 也无 src，
            # 但 id 直接写在 href 路径里（非 showpic url= 形式）。提取该 id 用于注入本地图。
            if not _url_id:
                _am = re.search(r'album\.sina\.com\.cn/pic(?:_\d+)?/([A-Za-z0-9]+)', href)
                if _am:
                    _url_id = _am.group(1)
                    # 直链相册 id：优先按 manifest sinaimg 映射（identifier 相同），否则按 album_<id>.jpg 命名
                    _source = 'album_direct'
                else:
                    _source = None
            else:
                _source = 'showpic'
            # 给每个内层 img 注入本地 src：若当前无 src、或 src 仅是懒加载占位(sg_trans)，
            # 都优先替换成映射到的本地文件（若本地文件存在且 map 命中）。
            _out = []
            for tg in imgs:
                _has_real_src = bool(re.search(r'(?i)\bsrc\s*=\s*"((?!//?simg\.sinajs\.cn|//?[^"]*sg_trans\.gif)[^"]*)"', tg))
                if _url_id and not _has_real_src:
                    _loc = _bid_imgid2local.get(_url_id)
                    # 直链相册锚点：若 manifest 无该 id，则回退到专辑本地命名 album_<id>.jpg
                    if not _loc and _source == 'album_direct':
                        _cand = 'album_' + _url_id + '.jpg'
                        if os.path.isfile(os.path.join(BASE, 'images', _cand)):
                            _loc = _cand
                    if _loc and os.path.isfile(os.path.join(BASE, 'images', _loc)) \
                       and os.path.getsize(os.path.join(BASE, 'images', _loc)) > 0:
                        if re.search(r'(?i)\bsrc\s*=\s*"', tg):
                            # 已有占位 src → 直接整体替换该 src 值
                            tg = re.sub(r'(?i)\bsrc\s*=\s*"[^"]*"', 'src="images/{0}"'.format(_loc), tg, count=1)
                        else:
                            # 无 src → 在收尾处注入
                            tg = re.sub(r'(?i)(<img[^>]*?)(\s*/?>)$',
                                        lambda mm: '{0} src="images/{1}"{2}'.format(mm.group(1), _loc, mm.group(2)),
                                        tg, count=1)
                _out.append(tg)
            return ''.join(_out)
        body = OUTER.sub(_kill, body)
        return body

    body = _strip_dead_anchors(body)
    # 清掉指向新浪图床原图链接的 href（本地已有图，外链离线无效）。
    # 注意：死链锚点的 href 已在 _strip_dead_anchors 里整体消费（锚点删除、仅留内层 img），
    # 到这里剩下的都是不在死链锚点内的孤立 sinaimg.cn href，可直接清掉。
    body = re.sub(r'\s+href="[^"]*sinaimg\.cn[^"]*"', '', body)
    # 残留在正文里、且未形成死链的孤立 <a TARGET="_blank"> 开标签（无 `<a href>`），删掉开标签。
    # 死链(file:// 与 album)的开标签 + 闭合 </A> 已被 _strip_dead_anchors 成对删除；
    # 剩余 </A> 均属作者真实外链(如 smgmusic/tudou/baidu 等)，必须保留其闭合，此处不再全局删 </A>。
    body = re.sub(r'<a\s+TARGET="_blank">', '', body, flags=re.I)

    # 文章页位于 page/ 子目录，图片/索引相对路径需加 ../ 前缀
    # 统一把正文里 src="images/xxx" 加 ../ 前缀
    # （archive 恢复件与 _strip_dead_anchors 注入的本地图都写 "images/<local>"，在此统一补 ../）
    body = re.sub(r'(?i)(\ssrc=")images/', r'\1../images/', body)

    # ---- 清理正文末尾游离的新浪容器闭合残迹（archive 恢复件特有）----
    # 从 archive.org 快照恢复的 fragment 尾部常残留新浪外层容器闭合 ` </div>` 与
    # 空注释 `<!--   -->`（原页面 <div class="articalContent"> 的收尾 + 模板分隔注释）。
    # 这些不属于正文内容，且会与本文模板的 `</div>` 叠加产生多余闭合（body 内 close>open）。
    # 仅剥离"末尾独立的 `</div>` + 可选空注释"，不触碰 `</p>/</dl>/</dd>` 等正文自身闭合。
    body = re.sub(r'\s*<\s*/\s*div\s*>\s*(<!--[^>]*-->\s*)*$', '', body, flags=re.I)

    # ---- 本地缺失图（原图已随新浪旧相册域名退役而彻底丢失）→ 替换为占位块，避免离线破图图标 ----
    def _dead_local(mo):
        tag = mo.group(0)
        src_m = re.search(r'(?i)src="\.\./images/([^"]+)"', tag)
        if src_m:
            loc = src_m.group(1)
            # 存在且非空则保留原图；否则替换成占位提示块
            full = os.path.join(BASE, 'images', loc)
            if os.path.isfile(full) and os.path.getsize(full) > 0:
                return tag
        return ('<div class="dead-pic" style="display:block;margin:12px auto;'
                'max-width:480px;padding:18px 14px;border:1px dashed #bbb;'
                'background:#fafafa;color:#888;font-size:13px;text-align:center;">'
                '此图已被新浪删除，无法离线显示</div>')
    body = re.sub(r'<img[^>]*src="\.\./images/[^"]*"[^>]*>', _dead_local, body, flags=re.I)
    # ---- 回填 emoji 表情：新浪原文用 <img TYPE="face" src="占位"/> 表示表情，
    # 清洗后 src 为空导致无图。真实表情 gif 已在 images/ 里，按文档顺序回填 src。----
    # 收集该文 manifest 里确认为小尺寸(≤32x32)的 emoji gif，按序号 `_k` 排序（crawl 时按文档序命名）
    def _is_small_gif(p):
        try:
            with open(p, 'rb') as f:
                d = f.read(16)
            if d[:6] not in (b'GIF87a', b'GIF89a'):
                return False
            w, h = struct.unpack('<HH', d[6:10])
            return w <= 32 and h <= 32
        except Exception:
            return False
    emoji_local = [
        local for local, _ in sorted(it.get('images', {}).items())
        if local.endswith('.gif')
        and os.path.exists(os.path.join(BASE, 'images', local))
        and _is_small_gif(os.path.join(BASE, 'images', local))
    ]
    if emoji_local:
        # 按顺序把 emoji gif 回填到前 N 个 <img TYPE="face"> 的 src（N=min(face数, emoji数)）
        # 若 face 数量超过已下载的 emoji 数（新浪懒加载对重复表情只留一份 gif），
        # 剩余的 face 复用最后一个已赋值 emoji——同一篇文章的重复表情内容完全相同。
        _last_emoji = None
        def _fill_faces(mo):
            nonlocal emoji_local, _last_emoji
            tag = mo.group(0)
            if emoji_local:
                local = emoji_local.pop(0)
                _last_emoji = local
            elif _last_emoji:
                local = _last_emoji
            else:
                return tag
            src_attr = ' src="../images/' + local + '"'
            # 已有 src（占位）则替换；否则在结束括号前补 src
            if re.search(r'\bsrc\s*=', tag, re.I):
                tag = re.sub(r'(?i)\bsrc\s*=\s*"[^"]*"', lambda m: src_attr, tag, count=1)
            else:
                if tag.endswith('/>'):
                    tag = tag[:-2] + src_attr + '/>'
                elif tag.endswith('>'):
                    tag = tag[:-1] + src_attr + '>'
            # 强制内联显示表情（占位 src 本来就是空图，避免残留行高）
            if re.search(r'\bstyle\s*=', tag, re.I):
                tag = re.sub(r'(?i)(\bstyle\s*=\s*")', r'\1display:inline;margin:0 2px;vertical-align:middle;', tag, count=1)
            return tag
        body = re.sub(r'<img[^>]*TYPE="face"[^>]*>', _fill_faces, body, flags=re.I)

    # ---- 回填经典 face 表情（2007 年文章）：<img src="http://blog.sina.com.cn/images/face/NNN.gif">
    # 这类 emoji 有真实 URL，但已被本地化为 images/face_NNN.gif；
    # 把任意 host 的 face/NNN.gif 重写为本地 ../images/face_NNN.gif，并强制内联显示避免拆除空白行。----
    FACE_MAP = {c: f'../images/face_{c}.gif' for c in
                ['001','002','003','005','013','027','030','038','039','040']}
    if FACE_MAP:
        def _loc_face(mo):
            tag = mo.group(0)
            code_m = re.search(r'face/(\d+)\.gif', tag, re.I)
            if code_m and code_m.group(1) in FACE_MAP:
                local = FACE_MAP[code_m.group(1)]
                # 替换 src 值
                tag = re.sub(r'(?i)\bsrc\s*=\s*"[^"]*face/\d+\.gif[^"]*"',
                             lambda m: f'src="{local}"', tag, count=1)
                # 强制内联：加 style（若已有 style 则追加 display/margin/vertical-align）
                if re.search(r'\bstyle\s*=', tag, re.I):
                    tag = re.sub(r'(?i)(\bstyle\s*=\s*")', r'\1display:inline;margin:0 2px;vertical-align:middle;', tag, count=1)
                else:
                    if tag.endswith('/>'):
                        tag = tag[:-2] + ' style="display:inline;margin:0 2px;vertical-align:middle;"/>'
                    elif tag.endswith('>'):
                        tag = tag[:-1] + ' style="display:inline;margin:0 2px;vertical-align:middle;">'
                return tag
            return tag
        body = re.sub(r'<img[^>]*face/\d+\.gif[^>]*>', _loc_face, body, flags=re.I)

    # ---- 本地化新浪相册图（2007-2008 年文章）：<img src="http://album.sina.com.cn/pic[_3]/<id>">
    # 这些图通过直连 album 短链已下载为 images/album_<id>.jpg，
    # 把正文里的 album 外链重写为本地相对链接（保留 alt/title），并内联显示避免空白行。----
    def _loc_album(mo):
        tag = mo.group(0)
        id_m = re.search(r'album\.sina\.com\.cn/[a-z0-9_]+/([A-Za-z0-9]+)', tag, re.I)
        if id_m:
            local = '../images/album_' + id_m.group(1) + '.jpg'
            if os.path.exists(os.path.join(BASE, 'images', 'album_' + id_m.group(1) + '.jpg')):
                # 替换 src 值为本地相对链接
                tag = re.sub(r'(?i)\bsrc\s*=\s*"[^"]*album\.sina\.com\.cn[^"]*"',
                             lambda m: f'src="{local}"', tag, count=1)
                # 加内联样式，避免块级化产生空白行（如需整图居中，可去掉此内联样式）
                if re.search(r'\bstyle\s*=', tag, re.I):
                    tag = re.sub(r'(?i)(\bstyle\s*=\s*")', r'\1display:block;margin:12px auto;', tag, count=1)
                else:
                    if tag.endswith('/>'):
                        tag = tag[:-2] + ' style="display:block;margin:12px auto;"/>'
                    elif tag.endswith('>'):
                        tag = tag[:-1] + ' style="display:block;margin:12px auto;">'
            else:
                # 本地无该图（原图已被新浪删除，返回 default_*.gif 占位）。
                # 用带样式的占位提示块整体替代外链，避免离线破图（灰色叉图标）。
                return ('<div class="dead-pic" style="display:block;margin:12px auto;'
                        'max-width:480px;padding:18px 14px;border:1px dashed #bbb;'
                        'background:#fafafa;color:#888;font-size:13px;text-align:center;">'
                        '此图已被新浪删除，无法离线显示</div>')
        return tag
    body = re.sub(r'<img[^>]*album\.sina\.com\.cn/(?:pic|pic_3)/[A-Za-z0-9]+[^>]*>', _loc_album, body, flags=re.I)

    # ---- 本地化 bj.static.photo 图（2008 年文章，如「吉隆坡之行」系列）----
    # <img src="http://bj.static.photo.sina.com.cn/bmiddle/<id>"> 是旧新浪相册直接外链。
    # 图已按 bj_<id>.jpg 下载到 images/（经 s8.sinaimg.cn/orignal|<id> 链恢复，历史上 301 跳转）。
    # 命中本地文件（真实图）→ 重写为本地相对链接；本地缺失（原图被新浪删除）→ 替换为占位块。
    def _loc_bjphoto(mo):
        tag = mo.group(0)
        id_m = re.search(r'bj\.static\.photo\.sina\.com\.cn/(?:bmiddle|middle)/([0-9a-z]+)', tag, re.I)
        if id_m:
            fid = id_m.group(1)
            local = '../images/bj_' + fid + '.jpg'
            full = os.path.join(BASE, 'images', 'bj_' + fid + '.jpg')
            if os.path.isfile(full) and os.path.getsize(full) > 0:
                tag = re.sub(r'(?i)\bsrc\s*=\s*"[^"]*bj\.static\.photo[^"]*"',
                             lambda m: f'src="{local}"', tag, count=1)
                if re.search(r'\bstyle\s*=', tag, re.I):
                    tag = re.sub(r'(?i)(\bstyle\s*=\s*")', r'\1display:block;margin:12px auto;', tag, count=1)
                else:
                    if tag.endswith('/>'):
                        tag = tag[:-2] + ' style="display:block;margin:12px auto;"/>'
                    elif tag.endswith('>'):
                        tag = tag[:-1] + ' style="display:block;margin:12px auto;">'
            else:
                return ('<div class="dead-pic" style="display:block;margin:12px auto;'
                        'max-width:480px;padding:18px 14px;border:1px dashed #bbb;'
                        'background:#fafafa;color:#888;font-size:13px;text-align:center;">'
                        '此图已被新浪删除，无法离线显示</div>')
        return tag
    body = re.sub(r'<img[^>]*bj\.static\.photo\.sina\.com\.cn[^>]*>', _loc_bjphoto, body, flags=re.I)

    # ---- 清单内但正文未引用的本地图，按文档序回填到仍无 src 的正文图 ----
    # 部分文章（花絮花絮 bwu8 等）的懒加载图并未包在死链锚点里，真实图 id 无处可寻；
    # 但下载时 manifest 已按文档顺序存为 `_k.jpg`，正文仍无 src 的图按先后顺序对应
    # 这些未引用文件。仅处理"已有 src 之外、仍完全无 src"的正文图（排除 TYPE=face、
    # SG_icon 小控件），避免误覆盖。
    _refd = set(re.findall(r'(?i)\bsrc\s*=\s*"[^"]*[/\\]([^/"\\]+\.(?:jpg|jpeg|png|gif))"', body))
    _unused = []
    if isinstance(it.get('images'), dict):
        for _loc, _ in it['images'].items():
            if _loc not in _refd and os.path.isfile(os.path.join(BASE, 'images', _loc)) \
               and os.path.getsize(os.path.join(BASE, 'images', _loc)) > 0:
                # 跳过小尺寸 emoji gif（已由 TYPE=face 回填处理，不给裸图）
                if _loc.lower().endswith('.gif') and _is_small_gif(os.path.join(BASE, 'images', _loc)):
                    continue
                _unused.append(_loc)
        def _nk(st):
            m = re.search(r'_(\d+)\.', st)
            return int(m.group(1)) if m else 999999
        _unused.sort(key=_nk)
    if _unused:
        _ui = 0
        def _fill_naked(mo):
            nonlocal _ui
            tag = mo.group(0)
            # 已有真实 src（本地图/专辑/表情）则跳过；占位 src 已在更早步骤被剥离
            if re.search(r'(?i)\bsrc\s*=\s*["\']', tag):
                return tag
            if re.search(r'(?i)TYPE\s*=\s*["\']face["\']', tag):
                return tag
            if re.search(r'(?i)\bclass\s*=\s*["\'][^"\']*SG_icon', tag):
                return tag
            if _ui >= len(_unused):
                return tag
            local = _unused[_ui]
            _ui += 1
            # 在结束括号前补 src
            src_attr = ' src="../images/' + local + '"'
            if tag.endswith('/>'):
                tag = tag[:-2] + src_attr + '/>'
            elif tag.endswith('>'):
                tag = tag[:-1] + src_attr + '>'
            return tag
        body = re.sub(r'<img[^>]*>', _fill_naked, body, flags=re.I)

    # ---- 无 src 的孤立 <img>（懒加载占位图且真实图 id 无处可寻、archive 恢复件残留）→ 占位块 ----
    # 早期文章 <img src="//simg...sg_trans.gif"> 是懒加载占位，若正文里既无第二个本地/原图 src、
    # 也不在死链 <A href="...url=..."> 的 url= 里（无法把 imgid 映射到本地文件），清洗后会是
    # 一个无 src 的 <img>，离线渲染成破图图标。此块放在所有注入/回填(本地图/url=映射/emoji face/
    # 经典 face/相册 album)之后统一兜底：这时已无 src 的 img 均为无法本地化的死图 → 换成占位块。
    def _empty_img(mo):
        tag = mo.group(0)
        if re.search(r'(?i)\bsrc\s*=\s*["\']', tag):
            return tag  # 已有 src（本地或占位回填成功），保留
        alt_m = re.search(r'(?i)\balt\s*=\s*["\']([^"\']*)["\']', tag)
        alt_txt = alt_m.group(1).strip() if alt_m else ''
        hint = f'（{alt_txt}）' if alt_txt else ''
        return ('<div class="dead-pic dead-empty" style="display:block;margin:12px auto;'
                'max-width:480px;padding:18px 14px;border:1px dashed #bbb;'
                'background:#fafafa;color:#888;font-size:13px;text-align:center;">'
                '此图无法离线显示（原图链接已失效，未留存本地副本）' + hint + '</div>')
    body = re.sub(r'<img[^>]*>', _empty_img, body, flags=re.I)

    # 文章页 HTML
    # 找上一篇/下一篇（在 manifest 里按时间排序后计算）
    page_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · 黄龄新浪博客离线存档</title>
<style>
  body {{ font-family: "PingFang SC","Microsoft YaHei",Arial,sans-serif; max-width: 780px; margin: 0 auto; padding: 24px 18px 60px; color: #222; line-height: 1.85; background: #fafafa; }}
  .nav {{ font-size: 13px; color: #888; margin-bottom: 20px; }}
  .nav a {{ color: #069; text-decoration: none; }}
  h1 {{ font-size: 24px; margin: 8px 0 6px; color: #111; }}
  .post-time {{ color: #999; font-size: 13px; margin-bottom: 26px; border-bottom: 1px solid #e6e6e6; padding-bottom: 12px; }}
  .article-body {{ font-size: 16px; }}
  .article-body img {{ max-width: 100%; height: auto; display: block; margin: 12px auto; border-radius: 4px; }}
  .article-body img[TYPE="face"] {{ display: inline; max-width: none; margin: 0 2px; vertical-align: middle; border-radius: 0; }}
  .article-body a {{ color: #069; }}
  .article-body p {{ margin: 12px 0; }}
  .pager {{ margin-top: 40px; border-top: 1px solid #e6e6e6; padding-top: 16px; font-size: 14px; display: flex; justify-content: space-between; }}
  .pager a {{ color: #069; text-decoration: none; }}
  .back {{ display:inline-block; margin-top: 28px; font-size: 14px; color:#069; text-decoration:none; }}
  .pager span.dull {{ color:#bbb; }}
</style>
</head>
<body>
<div class="nav"><a href="../index.html#a-{bid}">← 返回索引</a> ｜ 黄龄新浪博客离线存档</div>
<h1>{title}</h1>
<div class="post-time">{time}</div>
<div class="article-body">
{body}
</div>
<div class="pager">
  <span>{prev}</span>
  <span>{next}</span>
</div>
<a class="back" href="../index.html#a-{bid}">← 返回全部文章索引</a>
</body>
</html>
"""
    return page_template.format(bid=bid, title=html.escape(title), time=html.escape(time_), body=body, prev='', next='')

def build_index(manifest):
    """生成索引首页，按时间倒序（最新在前）。
    功能：
      - 精确记忆返回：点击列表项前把 scrollY 存进 sessionStorage，从文章页返回时 scrollTo 回原位
      - 兜底锚点：返回链接带 #a-<blogid>，即使 JS 失效也能跳到对应文章（回到附近）
      - 按年份跳转：页首年份导航条 + 每个年份段开头一个分隔标题（id=y-<year>）
      - 正序/倒序切换：顶部小按钮，JS 动态重排；可关闭
    """
    items = sorted(manifest, key=lambda x: x['time'], reverse=True)
    total = len(items)

    # 计算每个年份在倒序列表中的位置（用于年份分隔标题 + 导航条计数）
    years_sorted = []  # 倒序年份列表
    seen = set()
    for it in items:
        y = it['time'][:4]
        if y not in seen:
            seen.add(y)
            years_sorted.append(y)
    years_count = {}
    for it in items:
        y = it['time'][:4]
        years_count[y] = years_count.get(y, 0) + 1

    # 生成主体 rows：在每个年份段开头插入分隔标题（倒序布局，最新在前）
    rows = []
    emitted = set()
    for it in items:
        y = it['time'][:4]
        if y not in emitted:
            emitted.add(y)
            rows.append(f'<div class="ysec" id="y-{y}">{y}年 · {years_count[y]}篇</div>')
        title = html.escape(it['title'])
        time_ = html.escape(it['time'])
        summ = html.escape(it.get('summary',''))[:80]
        bid = it['blogid']
        rows.append(
            f'<div class="item" id="a-{bid}" data-date="{time_}">'
            f'<a href="page/{bid}.html" class="t" data-bid="{bid}">{title}</a>'
            f'<div class="meta">{time_}</div>'
            f'<div class="sum">{summ}</div></div>'
        )
    rows_html = '\n'.join(rows)

    # 年份导航条：倒序排列（与页面一致）
    year_nav = '　'.join(
        f'<a href="#y-{y}">{y}年</a>' for y in years_sorted
    )
    # 年份统计条（保留原计数展示）
    year_badges = ' · '.join(f'{y}年 {c}篇' for y, c in years_count.items())

    # 底部脚本：年份跳转、精确记忆返回、锚点兜底（正序/倒序切换由用户后续按效果决定，暂不启用）
    script = """
<script>
(function(){
  var KEY='hl_index_pos';
  // 年份跳转导航条：平滑滚动到对应年份分隔标题（倒序布局下即该年最新一篇）
  var jump = document.querySelectorAll('.jump a');
  for (var i=0;i<jump.length;i++){
    (function(link){
      link.addEventListener('click', function(e){
        e.preventDefault();
        var el = document.getElementById(link.getAttribute('href').slice(1));
        if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
      });
    })(jump[i]);
  }
  // 精确记忆返回：点击文章链接前记录当前滚动位置
  document.addEventListener('click', function(e){
    var a = e.target.closest ? e.target.closest('a[data-bid]') : null;
    if(a){
      try{ sessionStorage.setItem(KEY, String(window.scrollY)); }catch(_){}
    }
  }, true);
  // 返回本页时恢复位置：精确滚动位置（sessionStorage）优先，锚点仅作无记录时的兜底
  // （否则带 #a-xxx 的返回链接会 scrollIntoView 把对应文章顶到屏幕最上，丢失原本的阅读位置）
  function afterLoad(){
    var p = sessionStorage.getItem(KEY);
    if(p!=null){
      window.scrollTo(0, Number(p));
      // 立刻清除 #a-xxx hash，阻止浏览器在原位恢复后再原生跳到锚点（一次跳两次错位到该文顶部）
      try{ history.replaceState(null, '', location.pathname); }catch(_){}
      try{ sessionStorage.removeItem(KEY); }catch(_){}
      return;
    }
    if(location.hash && location.hash.indexOf('#a-')===0){
      var el = document.querySelector(location.hash);
      if(el){ el.scrollIntoView(); }
    }
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', afterLoad); }
  else { afterLoad(); }
})();
</script>
"""
    index_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>黄龄新浪博客 · 离线存档（{total}篇）</title>
<style>
  body {{ font-family: "PingFang SC","Microsoft YaHei",Arial,sans-serif; max-width: 820px; margin: 0 auto; padding: 26px 18px 80px; color: #222; background: #fafafa; }}
  h1 {{ font-size: 26px; margin: 6px 0 4px; }}
  .sub {{ color: #999; font-size: 14px; margin-bottom: 8px; }}
  .years {{ color: #888; font-size: 13px; margin-bottom: 22px; border-bottom:1px solid #e6e6e6; padding-bottom:12px;}}
  .jump {{ margin-bottom: 16px; font-size: 13px; background:#fff; border:1px solid #eee; border-radius:8px; padding:8px 10px; }}
  .jump a {{ color:#069; text-decoration:none; margin-right:2px; }}
  .jump a:hover {{ text-decoration:underline; }}
  .jump a.toend {{ color:#069; font-weight:600; }}
  .item {{ padding: 12px 6px; border-bottom: 1px solid #eee; }}
  .item a.t {{ font-size: 16px; color: #069; text-decoration: none; font-weight: 500; }}
  .item a.t:hover {{ text-decoration: underline; }}
  .item .meta {{ font-size: 12px; color: #aaa; margin-top: 3px; }}
  .item .sum {{ font-size: 13px; color: #777; margin-top: 3px; line-height:1.5; }}
  .count {{ color:#888; font-size:12px; }}
  .ysec {{ margin: 22px 0 6px; padding: 6px 10px; background:#f0f0f0; border-left:4px solid #ddd; color:#666; font-size:14px; font-weight:500; }}
  .ysec:first-of-type {{ margin-top:0; }}
</style>
</head>
<body>
<h1>黄龄新浪博客 · 离线存档</h1>
<div class="sub">博主：黄龄 ｜ 原站：blog.sina.cn/dpool/blog/huanglingisabelle ｜ 共 {total} 篇</div>
<div class="years">{year_badges}</div>
<div class="jump">按年份跳转：{year_nav}　|　<a href="#y-end" class="toend">跳到底部 ↓</a></div>
{rows}
<div class="count" id="y-end">共 {total} 篇文章 · 按发布时间倒序</div>
{script}
</body>
</html>
"""
    return index_template.format(total=total, year_badges=year_badges,
                                 year_nav=year_nav, rows=rows_html, script=script)

def main():
    # 生成索引首页
    index_html = build_index(manifest)
    with open(os.path.join(BASE,'index.html'),'w',encoding='utf-8') as f:
        f.write(index_html)
    print("已生成 index.html：", len(manifest), "篇")
    # 生成每篇文章页
    done = 0; skip = []
    for it in manifest:
        page = build_article_page(it)
        if page is None:
            skip.append(it['blogid'])
            continue
        with open(os.path.join(PAGE_DIR, it['blogid']+'.html'),'w',encoding='utf-8') as f:
            f.write(page)
        done += 1
    print(f"已生成单篇页面: {done} 篇，跳过缺失正文: {len(skip)}")
    if skip: print("缺失:", skip)

if __name__ == '__main__':
    main()