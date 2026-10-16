# -*- coding: utf-8 -*-
"""在远端跑：列 ComfyUI 的 output 目录 + loras + 队列（一次看全）。

用法（本机侧）：python _远端看一眼.py
"""
import os
import time

出 = r"E:\影匠AI\ComfyUI-Shared\output"
loras = r"E:\影匠AI\ComfyUI-Shared\models\loras"

print("=== 远端 output 目录 ===")
if os.path.isdir(出):
    文件 = []
    for dp, dn, fn in os.walk(出):
        for f in fn:
            文件.append(os.path.join(dp, f))
    文件.sort(key=lambda p: os.path.getmtime(p))
    print("  共 %d 个文件" % len(文件))
    for p in 文件[-12:]:
        print("    %-52s %7.2f MB  %s" % (
            os.path.relpath(p, 出),
            os.path.getsize(p) / 1e6,
            time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p)))))
else:
    print("  (没有这个目录)")

print("\n=== 远端 loras ===")
if os.path.isdir(loras):
    for f in sorted(os.listdir(loras)):
        p = os.path.join(loras, f)
        print("    %-66s %6.2f GB" % (f, os.path.getsize(p) / 1e9 if os.path.isfile(p) else 0))
else:
    print("  (没有这个目录)")
