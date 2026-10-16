# -*- coding: utf-8 -*-
"""重启本机 ComfyUI（让新装的自定义节点生效），并等它起来。"""
import json
import os
import subprocess
import time
import urllib.request

py = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
程序 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
日志 = r"D:\Comfy-Desktop\ComfyUI-Shared\comfy.log"
错误 = r"D:\Comfy-Desktop\ComfyUI-Shared\comfy.err"

# 用 PowerShell 找进程：这台机器**没有 wmic**（踩过，FileNotFoundError WinError 2）
死 = []
out = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
     "Where-Object { $_.CommandLine -match 'main\\.py' -and $_.CommandLine -match '8188' } | "
     "ForEach-Object { $_.ProcessId }"],
    capture_output=True, text=True, encoding="utf-8", errors="replace")
for 行 in (out.stdout or "").splitlines():
    if 行.strip().isdigit():
        死.append(int(行.strip()))
print("要停的 PID:", 死)
for p in set(死):
    subprocess.run(["taskkill", "/F", "/PID", str(p)], capture_output=True)
time.sleep(3)

os.makedirs(os.path.dirname(日志), exist_ok=True)
fo = open(日志, "w", encoding="utf-8", errors="replace")
fe = open(错误, "w", encoding="utf-8", errors="replace")
子 = subprocess.Popen(
    [py, "-X", "utf8", os.path.join(程序, "main.py"),
     "--port", "8188",
     "--extra-model-paths-config", os.path.join(程序, "extra_model_paths.yaml"),
     "--output-directory", r"D:\Comfy-Desktop\ComfyUI-Shared\output",
     "--input-directory", r"D:\Comfy-Desktop\ComfyUI-Shared\input"],
    cwd=程序, stdout=fo, stderr=fe,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008)
print("新 PID", 子.pid, "日志", 日志)

for i in range(120):
    time.sleep(5)
    try:
        d = json.load(urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=5))
        print(f"★ {5 * (i + 1)} 秒起来了")
        print("  ComfyUI", d.get("system", {}).get("comfyui_version"))
        for x in d.get("devices", []):
            print("  ", x.get("name"), "空闲", round(x.get("vram_free", 0) / 2**30, 1), "GB")
        break
    except Exception:
        if i % 6 == 5:
            尾 = open(错误, encoding="utf-8", errors="replace").read()[-600:]
            print(f"  {5 * (i + 1)}s 还没起　err尾: {尾.strip()[-200:]}")
else:
    print("✗ 5 分钟没起来")
    print(open(错误, encoding="utf-8", errors="replace").read()[-3000:])

time.sleep(2)
try:
    ks = json.load(urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=90))
    print(f"\n节点总数 {len(ks)}")
    for 键 in ("MiniMaxH3DualClockSamplerT8", "MiniMaxH3AVDecodeT8", "MiniMaxH3MotionQualityAuditT8Advanced",
              "MiniMaxH3AudioConditioningT8", "MiniMaxH3StudioTimelineT8Advanced", "VHS_VideoCombine",
              "MiniMaxH3MultiKeyframeAdvanced"):
        print(f"  {键:42s}", "✓ 有" if 键 in ks else "✗ 没有")
except Exception as e:
    print("查节点失败", e)
