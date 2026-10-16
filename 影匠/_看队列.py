# -*- coding: utf-8 -*-
"""看两台 ComfyUI 的队列和进度 —— 出片期间隔几分钟看一眼，别瞎等。"""
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
目 = r"D:\DSHworkspace\影匠\作品\楚子航\段"
台 = (("本机", "http://127.0.0.1:8188"), ("远端", "http://100.127.224.106:8188"))

for 名, 址 in 台:
    try:
        q = json.loads(urllib.request.urlopen(址 + "/queue", timeout=12).read())
        运 = len(q.get("queue_running", []))
        排 = len(q.get("queue_pending", []))
        头 = ""
        if q.get("queue_running"):
            头 = str(q["queue_running"][0][2].get("client_id", ""))[:8]
        print("  %-4s %-28s 运行中 %d　排队 %d" % (名, 址, 运, 排))
    except Exception as e:
        print("  %-4s %-28s ✗ %s" % (名, 址, e))
    try:
        h = json.loads(urllib.request.urlopen(址 + "/history?max_items=6", timeout=12).read())
        for k, v in list(h.items())[-3:]:
            状 = v.get("status", {})
            st = 状.get("status_str", "?")
            t = 状.get("messages", [])
            print("        %s  %s  %s" % (k[:8], st, str(t[-1])[:70] if t else ""))
    except Exception as e:
        print("        history ✗ %s" % e)

print()
s = sorted(os.listdir(目)) if os.path.isdir(目) else []
print("  段目录：%d 个" % len(s))
for f in s:
    print("    %-18s %6.2f MB" % (f, os.path.getsize(os.path.join(目, f)) / 1048576))
