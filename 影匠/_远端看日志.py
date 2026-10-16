# -*- coding: utf-8 -*-
import os
import urllib.request

p = r"C:\Users\Seele\_comfyui_r.log"
if not os.path.exists(p):
    print("  日志不存在 %s" % p)
else:
    t = open(p, "rb").read().decode("utf-8", "replace")
    print("  大小 %d 字节" % len(t))
    print("\n=== 尾部 3500 字 ===\n")
    print(t[-3500:])

print("\n=== 有没有 import 失败的节点 ===")
if os.path.exists(p):
    t = open(p, "rb").read().decode("utf-8", "replace")
    行 = [l for l in t.splitlines()
          if ("IMPORT FAILED" in l or "Traceback" in l or "Error" in l or "错误" in l)]
    for l in 行[-40:]:
        print("  " + l[:200])
    if not 行:
        print("  （没有）")

print("\n=== 端点在不在 ===")
try:
    d = urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=10).read()
    print("  在线 %d 字节" % len(d))
except Exception as e:
    print("  不在：%s" % e)
