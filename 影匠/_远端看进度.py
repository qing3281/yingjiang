# -*- coding: utf-8 -*-
"""在远端跑：报 H3 下载进度（含 .incomplete 临时文件）。"""
import os
import sys

根 = r"E:\影匠AI\ComfyUI-Shared\models"
print("=== 远端下载状态 ===")

总已下 = 0.0
for dp, dn, fn in os.walk(根):
    for f in fn:
        if ("minimax_h3" in f or "qwen3vl_32b" in f) and f.endswith(".safetensors"):
            p = os.path.join(dp, f)
            try:
                g = os.path.getsize(p) / 1e9
            except OSError:
                continue
            总已下 += g
            print("  %-58s %7.2f GB" % (f, g))

print("\n=== 未完成的临时文件 ===")
缓存 = os.path.expanduser(r"~\.cache\huggingface\hub")
n = 0
for dp, dn, fn in os.walk(缓存):
    for f in fn:
        if "incomplete" in f:
            p = os.path.join(dp, f)
            try:
                g = os.path.getsize(p) / 1e9
            except OSError:
                continue
            n += 1
            总已下 += g
            print("  %-58s %7.2f GB" % (f[:58], g))
if not n:
    print("  （没有）")

print("\n  合计已落盘 %.2f GB / 目标 58 GB" % 总已下)

print("\n=== 下载进程 ===")
找 = False
for pid in os.listdir("/proc") if os.path.isdir("/proc") else []:
    pass
import subprocess
尝试 = [
    ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
]
for c in 尝试:
    try:
        o = subprocess.run(c, capture_output=True, text=True, timeout=30).stdout
        print("  " + o.strip()[:400])
        找 = True
    except Exception as e:
        print("  %s" % e)

print("\n=== 日志尾部 ===")
日志 = r"C:\Users\Seele\_dl_h3.log"
if os.path.exists(日志):
    t = open(日志, encoding="utf-8", errors="replace").read()
    print("  文件 %d 字节" % len(t))
    print("  " + (t[-1500:].strip().replace("\n", "\n  ") or "（空）"))
else:
    print("  日志文件不存在：%s" % 日志)
