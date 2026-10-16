# -*- coding: utf-8 -*-
"""探针 22 —— 从站点首页/分类页取真实书号，供盲测使用。"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

s = creq.Session(impersonate="chrome131")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}

ids = Counter()
for url in ["https://fanqienovel.com/", "https://fanqienovel.com/library"]:
    try:
        r = s.get(url, headers=H, timeout=25)
        print(url, "->", r.status_code, len(r.text))
        for m in re.finditer(r'/(?:page|reader)/(\d{15,25})', r.text):
            ids[m.group(1)] += 1
        # 顺带看看页面里出现的书名
        for m in list(re.finditer(r'book_name["\']?\s*[:=]\s*["\']([^"\']{2,30})', r.text))[:12]:
            print("   书名:", m.group(1))
    except Exception as e:
        print(url, "失败", type(e).__name__, e)

print("\n候选书号（出现次数）：")
for k, v in ids.most_common(30):
    print(f"   {k}  x{v}")
