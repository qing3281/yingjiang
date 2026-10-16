# -*- coding: utf-8 -*-
"""在远端跑：列 loras 目录。"""
import os

p = r"E:\影匠AI\ComfyUI-Shared\models\loras"
print("  %s 存在=%s" % (p, os.path.isdir(p)))
if os.path.isdir(p):
    for f in sorted(os.listdir(p)):
        q = os.path.join(p, f)
        g = os.path.getsize(q) / 1e9 if os.path.isfile(q) else 0.0
        print("    %-70s %6.2f GB" % (f, g))
else:
    print("    (目录不存在)")
