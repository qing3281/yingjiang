# -*- coding: utf-8 -*-
"""起本机 ComfyUI（脱离控制台，DSH 会话断了也不死）。

为什么不用 .cmd：cmd.exe 按 OEM 代码页（非交互环境是 437）解码 .cmd，
中文路径会被解成乱码 —— 远端就是这么栽在 exit=9009 上的。
Python 的 argv 是 Unicode，绕开整个问题。

用法：
    python _起本机.py            # 起，已在跑就什么都不做
    python _起本机.py --重启      # 先杀再起
"""
import argparse
import os
import socket
import subprocess
import sys
import time

程序 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
PY = os.path.join(程序, ".venv", "Scripts", "python.exe")
MAIN = os.path.join(程序, "main.py")
YAML = os.path.join(程序, "extra_model_paths.yaml")
共享 = r"D:\Comfy-Desktop\ComfyUI-Shared"
日志目录 = os.path.join(程序, "logs")
端口 = 8188


def 在跑(口=端口, 秒=1.0):
    s = socket.socket()
    s.settimeout(秒)
    try:
        s.connect(("127.0.0.1", 口))
        return True
    except Exception:
        return False
    finally:
        s.close()


def 杀旧的():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
         "Where-Object { $_.CommandLine -like '*ComfyUI-Installs*main.py*' } | "
         "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }"],
        capture_output=True, text=True, errors="replace")
    for 行 in (r.stdout or "").splitlines():
        行 = 行.strip()
        if 行.isdigit():
            print(f"  杀掉 PID {行}")
    time.sleep(2)


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--重启", action="store_true")
    参 = ap.parse_args()

    if 参.重启:
        杀旧的()
    if 在跑():
        print(f"✓ {端口} 已经在跑，不动")
        return 0

    os.makedirs(日志目录, exist_ok=True)
    出 = open(os.path.join(日志目录, "comfy.log"), "w", encoding="utf-8", errors="replace")
    错 = open(os.path.join(日志目录, "comfy.err"), "w", encoding="utf-8", errors="replace")

    命令 = [PY, "-X", "utf8", MAIN,
            "--port", str(端口),
            "--extra-model-paths-config", YAML,
            "--output-directory", os.path.join(共享, "output"),
            "--input-directory", os.path.join(共享, "input")]
    标记 = 0x00000008 | 0x00000200      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen(命令, stdout=出, stderr=错, cwd=程序, creationflags=标记)
    print(f"  已拉起 PID {p.pid}，等它起来…")

    for i in range(120):
        time.sleep(1)
        if 在跑():
            print(f"✓ {端口} 起来了（{i+1} 秒）")
            return 0
    print(f"✗ 120 秒没起来，看 {日志目录}\\comfy.err")
    return 1


if __name__ == "__main__":
    sys.exit(主())
