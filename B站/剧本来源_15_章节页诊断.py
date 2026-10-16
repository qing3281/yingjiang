# -*- coding: utf-8 -*-
"""探针 15：章节页为何解析出 0 字？逐字诊断"""
import html as _html
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

BOOK = "7069948840148732967"
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
s = creq.Session(impersonate="chrome131")

page = s.get(f"https://fanqienovel.com/page/{BOOK}", headers=H, timeout=25).text
cids, seen = [], set()
for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
    if m.group(1) not in seen:
        seen.add(m.group(1))
        cids.append(m.group(1))
print("目录拿到", len(cids), "章")

for cid in cids[:3]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25)
    t = r.text
    paras = re.findall(r"<p>(.*?)</p>", t, re.S)
    print(f"\n[{cid}] HTTP={r.status_code} 长度={len(t)}  <p> 数量={len(paras)}")
    print("  title:", (re.search(r"<title>(.*?)</title>", t, re.S) or [None, "?"])[1][:60]
          if re.search(r"<title>(.*?)</title>", t, re.S) else "?")
    print("  含 'muye' :", t.count("muye"), " 含 'verify':", t.lower().count("verify"))
    print("  前 400 字:", repr(t[:400]))
    if paras:
        joined = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
        print("  段落拼接长度:", len(joined), " 前 60:", joined[:60])
    time.sleep(1.5)
