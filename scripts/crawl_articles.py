# -*- coding: utf-8 -*-
"""抓取黄龄博客全部文章正文到本地存档"""
import re, html, json, os, time, urllib.request, ssl, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR = os.path.join(BASE, "articles")
IMG_DIR = os.path.join(BASE, "images")
os.makedirs(ART_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Referer': 'http://blog.sina.com.cn/',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}

def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            return urllib.request.urlopen(req, timeout=30, context=ctx).read()
        except Exception as e:
            if i == retries-1:
                return None
            time.sleep(2)
    return None

def fetch_text(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            raw = resp.read()
            ctype = resp.headers.get('Content-Type','')
            if 'charset=gb' in ctype.lower():
                return raw.decode('gbk','ignore')
            return raw.decode('utf-8','ignore')
        except Exception as e:
            if i == retries-1:
                return ''
            time.sleep(2)
    return ''

def extract_body(html_content):
    """提取正文容器内的HTML+真实图片URL"""
    m = re.search(r'class="articalContent([^"]*)"[^>]*>(.*)$', html_content, re.S)
    if not m:
        return '', []
    body = m.group(2)
    # 截断到正文结束（找SG_Comment区）
    cm = re.search(r'<div class="SG_Comment"', body)
    if cm: body = body[:cm.start()]
    # 真实图片：取 real_src 中新浪图床，或 src 中非占位图
    imgs = []
    # 1. real_src
    for rs in re.findall(r'real_src\s*=\s*["\']([^"\']+)', body):
        rs = html.unescape(rs).strip()
        if 'sinaimg' in rs and rs not in imgs:
            imgs.append(rs)
    # 2. src 中新浪图床（无real_src时）
    for s in re.findall(r'<img[^>]*?\ssrc\s*=\s*["\']([^"\']+)["\']', body, re.I):
        s = html.unescape(s).strip()
        if 'sinaimg' in s and 'sg_trans' not in s and s not in imgs:
            imgs.append(s)
    # 把 real_src 属性替换为 src（让离线HTML直接显示）
    body = re.sub(r'real_src\s*=\s*["\']([^"\']+)["\']',
                  lambda mo: 'src="%s"' % html.unescape(mo.group(1)), body)
    return body, imgs

def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return name.strip()[:60]

def main():
    idx = json.load(open(os.path.join(BASE,'_index.json'), encoding='utf-8'))
    print("总数:", len(idx))
    done = 0; fail = 0
    manifest = []
    for it in idx:
        bid = it['blogid']
        art_path = os.path.join(ART_DIR, bid + '.html')
        if os.path.exists(art_path) and os.path.getsize(art_path) > 1000:
            done += 1
            continue
        html_content = fetch_text(it['url'])
        if not html_content or '<div' not in html_content:
            fail += 1
            print(f"[FAIL] {bid} {it['title']}")
            continue
        body, imgs = extract_body(html_content)
        if not body.strip():
            fail += 1
            print(f"[EMPTY] {bid} {it['title']}")
            continue
        # 记录图片清单（供后续下载）
        img_map = {}  # 本地文件名 -> 远程url
        for k, u in enumerate(imgs):
            ext = '.jpg'
            m5 = re.search(r'\.(jpg|jpeg|png|gif|bmp)(?:/|$|&|\?)', u.lower())
            if m5: ext = '.'+m5.group(1)
            local = f"{bid}_{k}{ext}"
            img_map[local] = u
        manifest.append({
            'blogid': bid, 'title': it['title'], 'time': it['time'],
            'url': it['url'], 'summary': it['summary'],
            'images': img_map
        })
        # 保存正文HTML（图片链接先本地化文件名，若已下载则替换）
        final_body = body
        for local, u in img_map.items():
            final_body = final_body.replace('src="%s"' % u.replace('&','&amp;'), '')
            final_body = final_body.replace(u, 'images/'+local)
        with open(art_path,'w',encoding='utf-8') as f:
            f.write(f'<meta charset="utf-8">\n<h1>{html.escape(it["title"])}</h1>\n<div class="post-time">{it["time"]}</div>\n'+final_body)
        done += 1
        if done % 20 == 0:
            print(f"进度: {done}/{len(idx)} 失败:{fail}", flush=True)
        time.sleep(0.3)
    json.dump(manifest, open(os.path.join(BASE,'_manifest.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n完成: 成功{done} 失败{fail} 图片待下载:{sum(len(m['images']) for m in manifest)}")

if __name__ == '__main__':
    main()