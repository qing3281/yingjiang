# -*- coding: utf-8 -*-
"""
远端 ComfyUI 启动器（本文件放在纯 ASCII 路径 C:\\yjai_run.py，用系统 Python 跑）
    C:\\Users\\Seele\\AppData\\Local\\Programs\\Python\\Python312\\python.exe  C:\\yjai_run.py

为什么要有这个文件：
    cmd.exe 读 .cmd 是按【OEM 代码页】解码的。SYSTEM / 非交互环境下代码页是 437，
    而启动脚本里含中文路径 "E:\\影匠AI"，于是路径被解成乱码 → cmd 报 9009（找不到程序）。
    Python 读源码固定按 UTF-8，中文字面量不会坏 —— 这就是绕过代码页坑的办法。
"""
import os
import subprocess
import sys
import time

根 = "E:\\影匠AI"
程序 = os.path.join(根, "ComfyUI")
PY = os.path.join(程序, ".venv", "Scripts", "python.exe")
MAIN = os.path.join(程序, "main.py")
YAML = os.path.join(程序, "extra_model_paths.yaml")
日志目录 = os.path.join(根, "logs")
LOG = os.path.join(日志目录, "comfy.log")
ERR = os.path.join(日志目录, "comfy.err")
PID文件 = os.path.join(日志目录, "comfy.pid")

端口 = sys.argv[1] if len(sys.argv) > 1 else "8188"

os.makedirs(日志目录, exist_ok=True)


def 已在跑():
    """端口已经在监听就不重复拉起。"""
    import socket
    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect(("127.0.0.1", int(端口)))
        return True
    except OSError:
        return False
    finally:
        s.close()


if 已在跑():
    print("已经在跑了，端口 %s" % 端口)
    sys.exit(0)

for f in (PY, MAIN, YAML):
    if not os.path.exists(f):
        print("缺文件: %s" % f)
        sys.exit(2)

o = open(LOG, "wb")
e = open(ERR, "wb")
p = subprocess.Popen(
    [PY, "-X", "utf8", MAIN,
     "--port", 端口,
     "--listen", "0.0.0.0",
     "--extra-model-paths-config", YAML],
    stdout=o, stderr=e, cwd=程序,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008,  # DETACHED_PROCESS
)
with open(PID文件, "w", encoding="utf-8") as f:
    f.write(str(p.pid))
print("已拉起 ComfyUI PID=%d 端口=%s" % (p.pid, 端口))
print("日志: %s" % LOG)
