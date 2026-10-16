# -*- coding: utf-8 -*-
"""
剧本来源探针 01 —— 番茄小说网页端加载方式侦察
目的：判断 fanqienovel.com 是 SSR 还是 XHR，以及有没有可直接调的公开接口。

只抓首页 + 1 个详情页 + 1 个阅读页，不下载正文。
"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as rq

UA_IMP = "chrome"
S = rq.Session(impersonate=UA_IMP)
S.headers.update({
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})


def get(url, **kw):
    try:
        r = S.get(url, timeout=30, **kw)
        print(f"[HTTP {r.status_code}] {url}  len={len(r.text)}  ct={r.headers.get('content-type')}")
        return r
    except Exception as e:
        print(f"[FAIL] {url}  {type(e).__name__}: {e}")
        return None


def analyze_html(label, h):
    print(f"\n===== {label} =====")
    print("  len =", len(h))
    srcs = sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', h)))
    print("  script srcs (%d):" % len(srcs))
    for s in srcs:
        print("     ", s)
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.{0,240})", h, re.S)
    print("  inline scripts:", len(inline))
    for s in inline[:6]:
        print("      inline>", s[:180].replace("\n", " "))
    for kw in ["__INITIAL_STATE__", "__NEXT_DATA__", "window.__", "__NUXT__", "_ROUTER_DATA", "SSR_DATA", "__SSR"]:
        n = h.count(kw)
        if n:
            print(f"  found '{kw}' x{n}")
    print("  book_id occurrences:", h.count("book_id"), "| bookId:", h.count("bookId"),
          "| /page/ links:", len(re.findall(r'href="(/page/[^"]+)"', h)))
    print("  /reader/ links:", len(re.findall(r'href="(/reader/[^"]+)"', h)))
    for m in sorted(set(re.findall(r'href="(/page/[^"]+)"', h)))[:6]:
        print("     page link:", m)
    hosts = sorted(set(re.findall(r"https?://([a-z0-9.\-]*(?:snssdk|fanqie|bytedance|zijieapi|byteoversea)[a-z0-9.\-]*)", h)))
    print("  byte-ish hosts referenced:", hosts[:20])
    paths = sorted(set(re.findall(r'"(/api/[a-zA-Z0-9_/\-]{3,60})"', h)))
    print("  /api/ paths in HTML:", paths[:20])
    return srcs


# ---------- 1. 首页 ----------
r = get("https://fanqienovel.com/")
if r:
    analyze_html("首页 /", r.text)
    # 首页是否直接含书名（=SSR）？
    titles = re.findall(r'<a[^>]+href="/page/\d+"[^>]*>(.*?)</a>', r.text, re.S)
    print("  首页 /page/ 锚文本数:", len(titles))
    for t in titles[:8]:
        print("     ", re.sub(r"<[^>]+>", "", t).strip()[:60])

# ---------- 2. 找一本具体书 ----------
# 从首页里抠一个 book_id
book_id = None
if r:
    m = re.search(r'/page/(\d+)', r.text)
    if m:
        book_id = m.group(1)
print("\n>>> picked book_id =", book_id)

if book_id:
    r2 = get(f"https://fanqienovel.com/page/{book_id}")
    if r2:
        analyze_html(f"详情页 /page/{book_id}", r2.text)
        # 找目录里的章节 item_id
        ids = re.findall(r'/reader/(\d+)', r2.text)
        print("  详情页里的章节 item_id 数:", len(ids))
        print("  sample item_ids:", ids[:10])
        # 书名
        t = re.search(r"<title>(.*?)</title>", r2.text, re.S)
        print("  <title> =", (t.group(1).strip() if t else None))
        if ids:
            r3 = get(f"https://fanqienovel.com/reader/{ids[0]}")
            if r3:
                analyze_html(f"阅读页 /reader/{ids[0]}", r3.text)
                # 正文是否在 HTML 里？
                body = re.sub(r"<script.*?</script>", "", r3.text, flags=re.S)
                body = re.sub(r"<[^>]+>", "", body)
                body = re.sub(r"\s+", "", body)
                print("  去标签后可见文本长度:", len(body))
                print("  前 300 字:", body[:300])
