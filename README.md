# 黄龄新浪博客 · 离线存档备用仓库

「黄龄（huanglingisabelle）新浪博客」全站离线存档的**发布 + 重建备用**镜像仓库。

## 原始博客地址（新浪博客）

- **博客主页**：`https://blog.sina.cn/dpool/blog/huanglingisabelle`
- **移动端主页**：`https://blog.sina.com.cn/dpool/blog/u/1281047653`

## 目录结构

```
yellowzero-blog-archive/
├── index.html        # 站点入口（列表页）
├── page/             # 分页（324 篇正文页，发布产物）
├── images/           # 本地化图片（1306 张）
├── articles/         # 文章页面（324 篇，发布产物）
├── _manifest.json    # 构建清单（build_html.py 的唯一依赖，必须入库）
├── scripts/          # 供重建的脚本（BASE 已锚定到跳一级的项目根）
│   ├── build_html.py
│   ├── crawl_articles.py
│   ├── download_images.py
│   └── enum_all.py
└── docs/             # 运维与交接文档
    ├── 离线文档_部署方案_主备.md
    ├── 新浪博客离线存档_HANDOFF.md
    └── 离线存档缺失内容清单.md
```


## 附注

`_manifest.json` 是 `scripts/build_html.py` 重建时读取的唯一数据依赖，请勿删除或忽略该文件。