# -*- coding: utf-8 -*-
"""_boot_8794.py —— 起 8794 依据台（如果还没起）。

为什么单独写这么一个小文件：
    原来我把 `python -X utf8 _依据台.py` 直接写进了 `restart-dsh.cmd`，
    **那 5 个中文字节违反了 AGENTS.md 第 0.05 条**（`.cmd` / `.bat 里一个非 ASCII
    字节都不许有` —— cmd.exe 按 OEM 代码页解析它，中文会把命令行拆成两半）。
    这条病已经犯过 6 次，2026-10-16 00:53 又犯了第 7 次。

    所以命令行里只留 ASCII：`restart-dsh.cmd` 调 `_boot_8794.py`，
    中文路径全部藏在这个 .py 文件里面（.py 走 UTF-8，没事）。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
WS = r"D:\DSHworkspace"
目标 = os.path.join(WS, "_依据台.py")
口 = 8794


def 起着吗():
    import socket

    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect(("127.0.0.1", 口))
        return True
    except Exception:
        return False
    finally:
        s.close()


def 主():
    if 起着吗():
        print("  · 8794 已经在跑，不动它")
        return 0
    if not os.path.exists(目标):
        print("  ★ 找不到 %s" % 目标)
        return 1
    subprocess.Popen(
        [PY, "-X", "utf8", 目标],
        cwd=WS,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    print("  ✓ 已拉起 8794")
    return 0


if __name__ == "__main__":
    sys.exit(主())
