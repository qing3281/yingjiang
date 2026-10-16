# -*- coding: utf-8 -*-
"""临时核对：监工台有没有把定妆照挂上去。"""
import json
import re
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

h = urllib.request.urlopen("http://127.0.0.1:8791/", timeout=40).read().decode("utf-8", "replace")
print("  页面 %.1f KB" % (len(h) / 1024))
print("  <img> 共 %d 个" % h.count("<img"))

m = re.search(r"人物形象[^<]*</h2>(.*?)</div>\s*<h2", h, re.S)
块 = m.group(1) if m else ""
print("  人物形象那一块 %d 字符　含 <img> %d 个" % (len(块), 块.count("<img")))
if 块:
    节 = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", 块))
    print("  文字节选：" + 节[:220])

print("  ── 定妆照能不能取到")
for 角 in ("陈老根", "阿棠", "周执", "内门执事"):
    路 = urllib.parse.quote("作品/觉醒/_定妆照/%s.png" % 角)
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8791/f?p=" + 路, timeout=25)
        b = r.read()
        print("    %-6s HTTP %s  %-11s %.0f KB" % (角, r.status, r.headers.get("Content-Type"), len(b) / 1024))
    except Exception as e:
        print("    %-6s ✗ %s" % (角, e))
