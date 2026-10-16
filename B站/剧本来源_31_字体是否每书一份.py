# -*- coding: utf-8 -*-
"""
探针 31 —— 字体是否「每本书一份」？（决定解码方案是通用还是按书重建）

方法：从两本不同书的页面里抽出 @font-face 里的 woff2/font 文件 URL，
下载后比较 md5；再对每份字体各自数 cmap 条目、比对码位集合。
如果 url 带书籍相关的 hash 且 md5 不同，就是「每书一份」。
"""
import hashlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

s = creq.Session(impersonate="chrome131")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}

BOOKS = ["7137359676424850443", "6823667291557727235", "7674861059122924569"]


def get(u, tries=3):
    for i in range(tries):
        try:
            r = s.get(u, headers=H, timeout=25)
            if r.status_code == 200 and len(r.text) > 2000:
                return r
        except Exception:
            pass
        import time as _t; _t.sleep(1.2 * (i + 1))
    raise RuntimeError(u)


for BK in BOOKS:
    r = get(f"https://fanqienovel.com/reader/{BK}")
    html = r.text
    # 抽 @font-face / css 里的字体地址
    urls = set(re.findall(r'url\(["\']?(https?://[^)"\']+\.(?:woff2?|ttf|otf)[^)"\']*)', html))
    urls |= set(re.findall(r'["\'](https?://[^"\']+\.woff2?[^"\']*)', html))
    urls |= set(re.findall(r'<link[^>]+href="([^"]+\.css[^"]*)"', html))
    print(f"=== book {BK}  len={len(html)}")
    print("    发现的字体/CSS 链接:", list(urls)[:6] or "（无，可能字体地址在外部 CSS 里）")

    # 找形如 https://p*.byteimg.com/.../*.woff2 的一切字符串
    cand = set(re.findall(r'https?://[^\s"\'<>()]+\.woff2?', html))
    for c in list(cand)[:4]:
        try:
            fr = s.get(c, headers=H, timeout=25)
            print(f"    {c[:90]}  -> {fr.status_code} {len(fr.content)}B md5={hashlib.md5(fr.content).hexdigest()[:12]}")
        except Exception as e:
            print("    下载失败", type(e).__name__)
    if not cand:
        print("    HTML 里没有直接出现 woff2 链接")

    # 找关键 CSS 文件
    for css in list(urls)[:3]:
        try:
            cr = s.get(css, headers=H, timeout=25)
            w2 = re.findall(r'url\(["\']?([^)"\']+\.woff2?[^)"\']*)', cr.text)
            print(f"    CSS {css[:70]} -> {cr.status_code}, 内含字体 {len(w2)} 个: {w2[:3]}")
        except Exception:
            pass
    print()
    import time as _t; _t.sleep(0.5)
