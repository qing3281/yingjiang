# -*- coding: utf-8 -*-
"""远端：杀掉旧 ComfyUI 进程，用原来的命令行重启（脱离父进程）。"""
import json
import os
import subprocess
import sys
import time
import urllib.request

基础 = r"E:\影匠AI\ComfyUI"

# 1) 找现在在跑的 ComfyUI 进程及其命令行
ps = r"""
$p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object { $_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*ComfyUI*' }
$p | ForEach-Object { "$($_.ProcessId)|$($_.CommandLine)" }
"""
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, timeout=120)
文本 = (r.stdout or b"").decode("gbk", "replace").strip()

行 = [l for l in 文本.splitlines() if "|" in l]
print("    找到 %d 个 ComfyUI 进程" % len(行))
命令行 = None
for l in 行:
    pid, _, cmd = l.partition("|")
    print("      PID %s" % pid.strip())
    print("        %s" % cmd.strip()[:220])
    if "main.py" in cmd:
        命令行 = cmd.strip()

if not 命令行:
    # 没找到就用默认的
    py = os.path.join(基础, ".venv", "Scripts", "python.exe")
    命令行 = '"%s" main.py --listen 0.0.0.0 --port 8188' % py
    print("    （没找到，用默认命令行）")

# 2) 杀掉
for l in 行:
    pid = l.split("|")[0].strip()
    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    print("    杀掉 PID %s" % pid)
time.sleep(4)

# 3) 重启（脱离）
DETACHED = 0x00000008 | 0x00000200
日志 = open(r"C:\Users\Seele\_comfyui_r.log", "wb")
p = subprocess.Popen(命令行, cwd=基础, stdout=日志, stderr=subprocess.STDOUT,
                     creationflags=DETACHED, shell=True)
print("    新进程 PID %d" % p.pid)

# 4) 等它起来
好了 = False
for i in range(60):
    time.sleep(5)
    try:
        d = json.load(urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=10))
        好了 = True
        print("    ComfyUI 起来了（等了 %d 秒）" % ((i + 1) * 5))
        break
    except Exception:
        pass

if not 好了:
    print("    ★ 90 秒还没起来，看日志：C:\\Users\\Seele\\_comfyui_r.log")
    sys.exit(1)
