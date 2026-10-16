# -*- coding: utf-8 -*-
import os
import subprocess
import time

print("=== netstat 看 8188 ===")
r = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=90)
t = (r.stdout or b"").decode("gbk", "replace")
行 = [l.strip() for l in t.splitlines() if "8188" in l]
for l in 行:
    print("  " + l)
if not 行:
    print("  ★ 没有任何 8188 的监听/连接")

print("\n=== 所有 python 进程 ===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Select-Object ProcessId,CreationDate,CommandLine | Format-List"],
                   capture_output=True, timeout=90)
print((r.stdout or b"").decode("gbk", "replace")[:2500])

print("\n=== 本机回环 127.0.0.1:8188 ===")
import urllib.request
try:
    d = urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=10).read()
    print("  ✓ %d 字节" % len(d))
except Exception as e:
    print("  ✗ %s" % e)

print("\n=== 本机打自己的 Tailscale IP 100.127.224.106:8188 ===")
try:
    d = urllib.request.urlopen("http://100.127.224.106:8188/system_stats", timeout=10).read()
    print("  ✓ %d 字节" % len(d))
except Exception as e:
    print("  ✗ %s" % e)

print("\n=== 日志最后 20 行（去色）===")
import re
p = r"C:\Users\Seele\_comfyui_r.log"
if os.path.exists(p):
    x = re.sub(r"\x1b\[[0-9;]*m", "", open(p, "rb").read().decode("utf-8", "replace"))
    尾 = [l for l in x.splitlines() if l.strip()][-20:]
    for l in 尾:
        print("  " + l[:190])
else:
    print("  没有 %s" % p)
p = r"C:\Users\Seele\_comfyui_re.log"
if os.path.exists(p):
    x = re.sub(r"\x1b\[[0-9;]*m", "", open(p, "rb").read().decode("utf-8", "replace"))
    尾 = [l for l in x.splitlines() if l.strip()][-12:]
    print("  --- stderr 尾 ---")
    for l in 尾:
        print("  " + l[:190])
