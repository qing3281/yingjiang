# -*- coding: utf-8 -*-
import json
import os
import subprocess
import urllib.request

print("=== 进程 ===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -like '*main.py*' } | "
                    "ForEach-Object { \"$($_.ProcessId)\" }"],
                   capture_output=True, timeout=60)
print("  main.py 进程：%s" % (r.stdout or b"").decode("gbk", "replace").strip())

print("\n=== 端口 ===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-NetTCPConnection -State Listen -EA SilentlyContinue | "
                    "Where-Object { $_.LocalPort -eq 8188 } | "
                    "ForEach-Object { \"$($_.LocalAddress):$($_.LocalPort)\" }"],
                   capture_output=True, timeout=60)
print("  监听 8188：%s" % ((r.stdout or b"").decode("gbk", "replace").strip() or "★ 没有"))

print("\n=== 本机回环 ===")
try:
    d = json.load(urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=10))
    print("  在线 %s" % d["system"]["comfyui_version"])
except Exception as e:
    print("  ✗ %s" % e)

print("\n=== 启动日志尾 ===")
p = r"C:\Users\Seele\_comfyui_re.log"
if os.path.exists(p) and os.path.getsize(p):
    print(open(p, "rb").read().decode("utf-8", "replace")[-2000:])
p2 = r"C:\Users\Seele\_comfyui_r.log"
if os.path.exists(p2):
    t = open(p2, "rb").read().decode("utf-8", "replace")
    print("  输出日志 %d 字节" % len(t))
    失败 = [l for l in t.splitlines() if "IMPORT FAILED" in l or "Cannot import" in l]
    print("  导入失败 %d 条" % len(失败))
    for l in 失败[:15]:
        print("    " + l[:180])
