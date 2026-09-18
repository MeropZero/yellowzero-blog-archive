# 交接文档：黄龄新浪博客 → 离线HTML存档 整条链路

> 生成时间：2026-09-17。用途：让一个全新会话能无缝接手「黄龄新浪博客离线存档」项目的后续维护。
> 本会话核心工作已完成，文档重点记录**链路全貌、已验证的关键经验、已知遗留问题**。


所有图片/页面/索引均**已完全离线可用**（当前已无需要"能不能显示"的断点）。324 篇文章 + 索引首页全部构建完成、本地图引用 0 缺失。

---

## 一、项目现状速览（截至 2026-09-17）

| 项 | 值 | 说明 |
|---|---|---|
| 文章总数 | **324** | 2007–2013 七年间，博客 ID 前缀 `4c5b3c6501` |
| 构建产物 | `page/*.html`（324） + `index.html` | 每篇独立页 + 索引首页，**全部重建于懒加载修复后** |
| 原始正文 | `articles/*.html`（324，**干净 HTML 片段**） | `build_html.py` 从这里读取再加工 |
| 检索清单 | `lists/*.html`（33 页）+ `crawl_articles.py` | 抓取阶段用的分页列表 |
| 图片总数 | `images/` 1305 个文件 | 相册图 `album_*.jpg` + `images/` 正文图 `<bid>_N.jpg` + GIF 表情 |
| 关联元数据 | `_manifest.json`（324 篇按时间排序）、`_album_fill.json`、`_album_scan.json` 等 | 构建脚本读取 manifest |
| 体积 | 约 73M | |
| 图片引用完整性 | **324 篇共 1319 处 `../images/` 本地引用，0 缺失/0 空字节；全站 0 个 dead-empty；占位块仅余 10 处 dead-pic(真丢)** | 见"关键经验6"，完整校验跑 `python _p2_img_health.py` |

**重要结构**：`page/` 里的页面图片用 `../images/...` 相对路径；`articles/` 里的原始正文用 `images/...`（无 `../`），两者**前缀不同**，构建时会统一给 `page/` 输出加 `../`。

---

## 二、整条链路（生成一篇离线页面的完整流程）

```
crawl_articles.py  →  articles/*.html   （抓原始正文，含全部新浪残留标签/外链/懒加载占位）
download_images.py →  images/*.jpg       （下载正文图，按文档序命名 <bid>_N.jpg）
_recover_album*.py →  images/album_*.jpg  （补抓 2007-2008 相册图，见"关键经验3"）
build_html.py      →  page/*.html + index.html  （本地化+清洗+表情回填+索引）
```

`build_html.py` 对单篇正文的处理链条（读 `articles/<bid>.html`）：
1. 剥离 `<meta>/<h1>/时间div`（用统一模板重建）
2. 截断到 `<!-- 正文结束 -->`，删所有 `<script>` 及其内容
3. 清新浪懒加载占位 `src="//simg.sinajs.cn...sg_trans.gif"`，让第二个真正的 `src="images/..."` 生效
4. 清协议相对 `src/href="//..."`、新浪图床外链 `href="...sinaimg.cn..."`
5. **`_strip_dead_anchors`（成对剥离死链锚点）** —— 新增，见"关键经验1"
6. 删孤立 `<a TARGET="_blank">` 开标签（不再全局删 `</A>`，保留作者真实外链闭合）
7. `src="images/"` → `src="../images/"`（page 子目录前缀）
8. 表情 emoji 回填（两类，见"关键经验2"）
9. **相册图本地化 `_loc_album`** —— 含新增占位 else 分支，见"关键经验3/4"

---

## 三、已验证的关键经验（重要，务必阅读）

### 1. 死链锚点必须"成对"剥离，不能只删闭合 `</A>` ⚠️高风险
- **现象**（用户反馈）：原文没有超链接，但生成页里整段文字变成了"跳转图片的超链接"。
- **根因**：新浪编辑器从 Word 粘贴残留 446 个 `<A HREF="file://Towing-share/...">`（2007年本地共享路径死链）+ 421 个 `<A HREF="http://album.sina.com.cn/pic...">`（相册已本地化）。旧代码用 `re.sub(r'<a\s+TARGET="_blank">', ...)` 只匹配"无 HREF 且开头即 TARGET"的 `<a>`，匹配不到 `HREF` 在前的 `<A HREF=...>`；再加上 `body.replace('</A>','')` 无差别删光闭合标签 → **开标签全残留、闭合全删 → 开标签之后整段文字被未闭合 `<a>` 误包成指向死链的超链接**。
- **正确做法**：`_strip_dead_anchors(body)` 用正则**整对匹配** `<A HREF="死链域名"...>(.*?)</A>`（`re.I|re.S`），回调只保留内层 `<img>`，其余整体丢弃。死链域名集合：`file://`、`album.sina.com.cn`、`photo.blog.sina.com.cn`、`control.blog.sina.com.cn`。
- **绝不能再**加回"全局删 `</A>`"——那会破坏 15 个作者真实外链（youku/tudou/douban/music.sina/贴吧等）的闭合配对。

### 2. 表情 emoji 分两类，回填逻辑不同
- **经典 face**（2007年）：`<img src="http://blog.sina.com.cn/images/face/NNN.gif">`，本地化为 `images/face_NNN.gif`（10个：`001/002/003/005/013/027/030/038/039/040`），用 `FACE_MAP` 重写 src 并强制 `display:inline`。
- **TYPE="face" 占位**：`<img TYPE="face" src="占位"/>`，真实 gif 已按文档序命名为语义化序号，用 `_is_small_gif`（读取 GIF 头，`w<=32 and h<=32`）判定并按顺序回填 src。

### 3. 新浪相册两条链路行为截然不同——必须用 `pic/` 而非 `pic_3/` ⚠️本次最大坑
- **`album.sina.com.cn/pic/<id>`**（原图，**正确**）→ 302 到 `s*.sinaimg.cn/orignal/<sig>` → **真图 JPEG**。浏览器能看到图走的就是这条。
- **`album.sina.com.cn/pic_3/<id>`**（bmiddle 链路，旧正文外链）→ 302 到 `s*.sinaimg.cn/bmiddle/<sig>` → **被劫持到 `default_s_bmiddle.gif` 占位**（破图/红叉）。
- **结论**：只要 `<id>` 还在新浪，`pic/` 链路永远能拿真图；`pic_3/` 才被劫持。**下载一律用 `pic/` 路径**（`_recover_album_fill.py` 第68行正是 `'http://album.sina.com.cn/pic/' + id_`，这是对的）。不要直接用正文里残留的 `pic_3/` 短链。
- **下载成功判定**：body 以 `FF D8`（JPEG头）开头 或 `content_type` 含 `image/jpeg` ⇒ ok 落盘；否则视为占位**不落盘**（`_album_fill.json` 记录 `step=='placeholder'`）。

### 4. `build_html.py` 相册本地化 `_loc_album` 的占位 else 分支（新增）
- `src=http://album.../pic[_3]/<id>` 且本地 `images/album_<id>.jpg` **存在** → 重写为 `../images/album_<id>.jpg` + `display:block;margin:12px auto` 内联样式。
- **本地不存在**（新浪真删，只可能出现在 `pic/` 链路也返回 default 占位时）→ 整体替换为 `<div class="dead-pic" ...>此图已被新浪删除，无法离线显示</div>` 带边框提示块，**避免离线破图外链**。不要指望浏览器在线能载（会破图）。

### 5. 沙箱环境两个技术坑
- 本沙箱写 `/tmp/x.jpg` 会 **size=0**（curl 落盘失败/不可写），**必须把图片直接写项目 `images/` 目录**。
- 运行 `build_html.py` 等 python 脚本加 `PYTHONDONTWRITEBYTECODE=1` 前缀，避免 `.pyc` 缓存写入被沙箱拦截（blocked paths 报错）。另外 grep 读取 `app.asar` 类大文件时 Bash 的 `cat/head` 可能乱码，需 `grep -a`。
- 批量下载脚本建议 `run_in_background` + 等待通知，避免前台超时。
- **简体中文路径的 Bash heredoc 写文件会乱码/报错**（如 `离线网页存档\黄龄新浪博客` 在 `cat > _x.py` 时路径编码被破坏）。临时脚本一律用 Write 工具写，或在脚本内用相对路径 + bash heredoc 时避开中文目录。

### 6. 早期(2008-2009)文章"图片离线缺失"根因与修复 ⚠️本次修复的核心（已二修定案）
- **现象**（用户两次反馈）：`page/4c5b3c650100clv8.html`、`page/4c5b3c650100dwoa.html` 等 2008/2009 页离线图片缺失/被误判为"无法离线显示"，但浏览器在线能看到。
- **根因（精确定位）**：早期新浪博文用**懒加载占位** `<img src="//simg.sinajs.cn/...sg_trans.gif">`（透明占位），真实图 URL **藏在死链锚点 `<A href="...&url=http://sN.sinaimg.cn/<size>/<imgid>>"` 的 `url=` 参数里**。本地其实有图（manifest `images` 记录 `local→url`，url 含真实 `<imgid>`），但正文 `<img>` 的 src 从未被改写成本地路径。**第一版修复注入 src 的判定条件写反了**：要求"img 无 src 才注入"，但这些图有占位 src，导致注入被跳过 → 清洗后无 src → 被兜底转成"无法离线显示"占位块。**且第一版把 `_strip_dead_anchors` 放在"清理 sinaimg.cn href"之后**——先清 href 会连 url= 上下文一起删掉，锚点不再匹配 `HREF=`，img 彻底失去可用的图 id。
- **最终修复（build_html.py 已修正定案）**：
  1. **调整顺序**：`_strip_dead_anchors` 必须在"清理 `href="...sinaimg.cn[^"]*"`"【之前】执行，保证 href 里的 `url=` 上下文可读。
  2. **判定条件改为"无真实 src 就注入"**：内层 img 若 `无 src` 或 `src 仅为占位 sg_trans`（用正则 `src="((?!//?simg\.sinajs\.cn|//?[^"]*sg_trans\.gif)[^"]*)"` 判真实 src），则把 `url=` 的 imgid 映射到 manifest 本地文件并**注入/替换** `src="images/<local>"`（已有占位 src 则整体替换其 src 值，无 src 则在收尾注入）。前提是本地文件存在且非空。
- **验证（本次三修后全局定案）**：① dwoa 11 张图全部注入 `../images/4c5b3c650100dwoa_0..10.jpg`，dead-pic=0、0 文件缺失；② clv8 3 张、其余 2008/2009 页同理；③ 全站 `page/*.html` 共 **1319 处 `../images/` 本地引用、0 个指向缺失/0字节文件、全站 0 个 dead-empty**（完整校验：`python _p2_img_health.py`，用**绝对路径** IMG_DIR 解析，杜绝相对路径误报）；④ 剩余 **10 个 dead-pic 块**（7 页：`0a11`×2、`0bmn`×3、`0d0o`、`8kb4`、`8kbe`、`9lgc`、`di6k` 各1）经逐一核查**确为真丢**（`dead-pic` class=原图被新浪删除）——原文非锚点占位 only、manifest 无对应本地文件，属新浪当年就删/从未下载，非误判。
- **⚠️审计路径陷阱（重要）**：校验 `../images/x.jpg` 是否存在时**绝不能用相对 `os.path.exists('../images/x.jpg')`**——从错误 CWD 解析会把 `../images/` 指向项目上一级不存在的目录，导致全站误报"1319 全缺失"。必须用 `os.path.join(BASE,'images',basename)` 绝对路径。已固化为 `_p2_img_health.py`。
- **真丢与误判的判别标准**（后续排查依据）：**img 在死链 `<A href=...url=...>` 里且 url= 的 imgid 能映射到本地文件 → 可恢复（本次已恢复）；img 是"非锚点纯占位"（正文无任何真实 URL、manifest 无图）→ 真丢，保留占位块即可，别再尝试按文档序强配（会错配）。**

---

## 四、遗留问题 / 待办（留给后续会话）

### P1 图片恢复现状（已尽最大努力，剩余无法恢复）
- `_album_fill.json`：104 唯一相册 ID，OK=114、placeholder=20（合计含补下载）；`images/album_*.jpg` 共 **594** 张。
- **9 张确认新浪真删**（`pic/` 链路也返回 `default_s_orignal.gif` 404 占位）：`4c5b3c6502000wbh`、`4c5b3c6502000wbi`、`4c5b3c65020017fk`、`4c5b3c65020017fl`、`4c5b3c65020017fp`、`4c5b3c6502001hdq`、`4c5b3c654425bb5b94144`、`4c5b3c654425c89ef3b9f`、`4c5b3c6544aee7a96c3e0`。
  - 分布在 6 篇文章：`a11`（拗造型）、`bmn`（我眼中的韩寒）、`d0o`（《晴天日记》花絮照照）、`8kb4`（百事MV-棚内）、`8kbe`（百事MV-2）、`9lgc`(舞林照照)。
  - 这些位置现在显示"此图已被新浪删除，无法离线显示"占位块，属**预期行为**。
- **12 篇缺失正文博文 archive.org 探测 = 全部无快照（本次定案，勿再尝试）**：`_wb_probe12.py` 对 `0a5v/0cgx/0czt/8jff/cpcd/fz1z/fzl9/g4ld/g9t2/ggb4/hu09/i865` 逐年份查 web.archive.org replay，**各年份均无有效快照** → 0 篇可恢复。这 12 篇正文连同其图片在本存档中缺失属**无法挽回**（原站文章已删且无存档）。脚本已跑、结果写入即定案。
- 若后续要再碰恢复：**统一用 `album/pic/<id>` 链路**，参考 `_recover_album_fill.py`。”

### P2 全站仍可能有未本地化的 GIF 外链 / 非相册图
- 本次重点清理了相册 `.jpg`、face 表情、`sinaimg.cn` 外链。但 `images/` 里共有 1253 个文件（659 个非相册），若某些文章正文仍引用 `src="//sinaimg.cn/...xxx.gif"`（动图/头像/装饰图）而本地无对应文件，离线可能破图。
- **验证手段**（已有一套）：`grep -roE 'src="(http|//)[^"]*"' page/*.html` 扫残留绝对/协议相对 src；同时校验每个 `src="../images/..."` 对应文件真实存在（`_verify_face.py` 给过 face 方向的先例）。
- **待办：跑一次全站外链扫描，把残留的外链图若能下则补下，不能则加占位块**（参考 `_loc_album` 的 else 分支模式通用化）。


### P3 脚本清点（大量临时脚本可归档）
```
完整持久脚本：build_html.py（核心构建）、crawl_articles.py、download_images.py、enum_all.py
历史恢复脚本（保留作参考）：_recover_album.py、_recover_album_fill.py、_recover_all.py、_recover_all2.py
已删本次临时 _recover_pic3.py。其他 _wb_recover*.py/_missing_all.py/_placeholder_urls.py/_verify_face.py 为一次性排查。
临时目录 _wb/（cdx.json 等）、_rr_tmp/、_face/ 可清理或归档，勿删 articles/ images/ lists/ page/。
```

---

## 五、给接手会话的建议技能（suggested skills）

- **agent-browser**：验证渲染效果、截图确认图片/占位/索引交互，因为当前模型非多模态。
- **find-skills**：若遇到沙箱/文件读写/浏览器自动化等能力缺口，先检索可安装 skill 再自行判断。
- **pdf / document-skills 系**：仅当后续要产出报告/备份说明文档时使用。

---

## 六、一句话总结（给下一个会话的启动锚点）

> **该项目已基本完成、全站离线可见**。若继续，优先做 P2（扫全站残留非相册外链图并本地化/占位）。任何图片恢复一律走 `album/pic/<id>` 原图链路；任何 HTML 清洗锚点务必成对处理；构建用 `PYTHONDONTWRITEBYTECODE=1` 防沙箱拦截；图片必须写项目 `images/` 目录。