# -*- coding: utf-8 -*-
"""下载所有文章的图片到本地 images/ 目录"""
import re, html, json, os, time, urllib.request, ssl

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(BASE, "images")
os.makedirs(IMG_DIR, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Referer': 'http://blog.sina.com.cn/',
}

def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 500:
        return 'skip'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        data = urllib.request.urlopen(req, timeout=30, context=ctx).read()
        if len(data) < 100:
            return 'too-small'
        with open(path, 'wb') as f:
            f.write(data)
        return 'ok'
    except Exception as e:
        return 'err:'+str(e)[:40]

def main():
    manifest = json.load(open(os.path.join(BASE,'_manifest.json'), encoding='utf-8'))
    total = sum(len(m['images']) for m in manifest)
    done = 0; ok = 0; fail = []
    print(f"共需下载 {total} 张图片")
    for m in manifest:
        bid = m['blogid']
        for local, url in m['images'].items():
            path = os.path.join(IMG_DIR, local)
            r = download(url, path)
            if r == 'ok': ok += 1
            elif r not in ('skip',): fail.append((url, r))
            done += 1
            if done % 100 == 0:
                print(f"进度 {done}/{total} 成功{ok}", flush=True)
            time.sleep(0.2)
    # 生成图片清单（待后续HTML引用）
    print(f"\n完成: 成功{ok}/{total} 失败{len(fail)}")
    if fail:
        json.dump(fail, open(os.path.join(BASE,'_img_fail.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()