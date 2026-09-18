# -*- coding: utf-8 -*-
import json, re, urllib.request, ssl, sys, time
sys.stdout.reconfigure(encoding='utf-8')

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HDR = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0','Referer':'http://m.blog.sina.com.cn/'}

def parse_lsmod(htm):
    """从含 lsMod 的 HTML 中提取所有 (blogid, title, time)"""
    out = []
    # 每个 lsMod div 块：以 <div ...class="lsMod"...blogid="..."> 开头
    # 用 finditer 找所有 lsMod 块的开始，并往后抓本块内容（直到下一块或其闭合）
    for m in re.finditer(r'<div[^>]*class="lsMod"[^>]*blogid="([0-9a-z]+)"[^>]*>(.*?)(?=<div[^>]*class="lsMod"|$)', htm, re.S):
        bid, blk = m.group(1), m.group(2)
        tm = re.search(r'artTit[^>]*>\s*(?:<a[^>]*>)?(.*?)(?:</a>)?\s*</', blk, re.S)
        title = re.sub(r'<[^>]+>','', tm.group(1)).strip() if tm else ''
        t = re.search(r'artTime[^>]*>([^<]+)<', blk)
        ts = t.group(1).strip() if t else ''
        out.append((bid, title, ts))
    return out

all_items = []
seen = set()
for page in range(1, 40):
    url = f'http://m.blog.sina.com.cn/u/1281047653?appblog=1&vt=4&page={page}'
    try:
        d = urllib.request.urlopen(urllib.request.Request(url,headers=HDR),timeout=30,context=ctx).read().decode('utf-8','ignore')
    except Exception as e:
        print('page',page,'err',e); break
    if page == 1:
        htm = d
        page_num_info = re.findall(r'pageNum[^0-9]*(\d+)', d)
    else:
        try:
            j = json.loads(d)
            htm = j['data']['data']
            # 从JSON里提取pageNum/total
            page_num_info = re.findall(r'pageNum[^0-9]*(\d+)', str(j.get('data','')))
        except Exception as e:
            print('page',page,'parseerr',e, d[:120]); break
    items = parse_lsmod(htm)
    new = [it for it in items if it[0] not in seen]
    for it in new: seen.add(it[0]); all_items.append(it)
    print(f'page{page}: 本页{len(items)} 新{len(new)} 累计{len(all_items)}', flush=True)
    if page == 1 and page_num_info:
        print('  pageNum标记:', page_num_info[:3])
    if len(items) < 10 and page != 1:
        print('  不足10篇，可能到底了', flush=True)
    time.sleep(0.3)

print('\n=== 总计唯一篇数:', len(all_items), '===')
json.dump([{'blogid':b,'title':t,'time':ts} for b,t,ts in all_items],
          open('_all_titles_dump.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)