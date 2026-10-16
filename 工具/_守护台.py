# -*- coding: utf-8 -*-
"""三个台的常驻看门狗 —— 开机自己起、死了自己活、一个窗口都不弹。

用户 2026-10-16 01:55 原话（m37793）：
  「我刚刚重启了，但是发现记忆和依据这两个窗口现在就没有东西了。你能不能让我每一次开的时候？
    他就这些东西他就能够存在，能够使用。并且不要在后台给我弹一些命令行，什么弹窗这些。
    太多了，看着很烦。我如果不小心给关了，那么你这记器台是不是就用不了了？」

所以这个脚本干三件事：
  ① 每 10 秒探一次三个台的端口，谁不在就把它拉起来 —— 用户关掉窗口也不影响，台是后台服务
  ② 拉起子进程时带 CREATE_NO_WINDOW + DETACHED_PROCESS —— **一个黑窗口都不许弹**
  ③ 它自己由「计划任务·登录时」用 pythonw.exe 启动 —— 开机就有，全程无窗口

怎么单独跑（不装计划任务时）：
    pythonw.exe _守护台.py            # 无窗口常驻（正常用法）
    python.exe  _守护台.py --前台      # 带控制台看日志（调试用）
    python.exe  _守护台.py --一遍      # 只探一遍就退（自检用）
    python.exe  _守护台.py --状态      # 打印三台现在在不在

判据（不用听我说，自己跑）：
    python _守护台.py --状态
    它打「✓ 在听」就是真的在；打「✗ 没人听」就是没在。
★ 为什么第 27 行要包 try：
    pythonw.exe 底下 **`sys.stdout` 是 None**（没有控制台）。直接 `.reconfigure()`
    会抛 `AttributeError: 'NoneType' object has no attribute 'reconfigure'`，
    进程当场死掉、连日志都来不及写一行 —— 这就是它第一次没起来的原因。
"""
import os
import sys
import time
import socket
import subprocess
import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

工作区 = r"D:\DSHworkspace"
Python = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
PythonW = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\pythonw.exe"
日志 = os.path.join(工作区, "_守护台.log")
锁文件 = os.path.join(工作区, "_守护台.pid")

# ★ 三个台。要加新台就往这里加一行。
台们 = [
    {"名": "影匠控制台", "口": 8791, "脚本": os.path.join(工作区, "影匠", "_控台.py"),
     "参数": ["--口", "8791", "--不开"], "工作目录": os.path.join(工作区, "影匠")},
    {"名": "记忆台", "口": 8792, "脚本": os.path.join(工作区, "_记忆台.py"),
     "参数": [], "工作目录": 工作区},
    {"名": "依据台", "口": 8794, "脚本": os.path.join(工作区, "_依据台.py"),
     "参数": [], "工作目录": 工作区},
]

# 无窗口标志：CREATE_NO_WINDOW 不建控制台；DETACHED_PROCESS 彻底脱离父进程
无窗口 = 0x08000000 | 0x00000008


def 写日志(话):
    行 = "[%s] %s\n" % (datetime.datetime.now().strftime("%m-%d %H:%M:%S"), 话)
    try:
        # 超过 2 MB 就先截一半，别让它无限长
        if os.path.exists(日志) and os.path.getsize(日志) > 2 * 1024 * 1024:
            with open(日志, "r", encoding="utf-8", errors="replace") as f:
                旧 = f.readlines()
            with open(日志, "w", encoding="utf-8") as f:
                f.writelines(旧[-500:])
        with open(日志, "a", encoding="utf-8") as f:
            f.write(行)
    except Exception:
        pass
    if 前台:
        sys.stdout.write(行)
        sys.stdout.flush()


def 在听吗(口):
    """判据：能连上 = 在听。不用 HTTP（有的台要鉴权、有的慢）。"""
    s = socket.socket()
    s.settimeout(1.2)
    try:
        s.connect(("127.0.0.1", int(口)))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def 拉起来(台):
    参 = [Python, 台["脚本"]] + list(台["参数"])
    try:
        p = subprocess.Popen(
            参,
            cwd=台["工作目录"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=无窗口,
            close_fds=True,
        )
        写日志("拉起 %s（口 %d）→ pid %d" % (台["名"], 台["口"], p.pid))
        return True
    except Exception as e:
        写日志("★ 拉不起来 %s：%r" % (台["名"], e))
        return False


def 单实例():
    """已经有一个守护在跑就不开第二个。判据：pid 文件里的进程还活着。"""
    try:
        if os.path.exists(锁文件):
            with open(锁文件, "r", encoding="utf-8") as f:
                旧 = int((f.read() or "0").strip() or 0)
            if 旧 and 旧 != os.getpid():
                # tasklist 查这个 pid 在不在
                r = subprocess.run(["tasklist", "/FI", "PID eq %d" % 旧, "/NH"],
                                   capture_output=True, text=True, creationflags=无窗口)
                if str(旧) in (r.stdout or ""):
                    return 旧
    except Exception:
        pass
    return 0


def 主循环(间隔=10):
    写日志("守护起来了（pid %d），盯 %d 个台" % (os.getpid(), len(台们)))
    缺席 = {}          # 名 → 连续失败次数，用于拉长重试间隔，别把 CPU 烧了
    while True:
        for 台 in 台们:
            if 在听吗(台["口"]):
                缺席.pop(台["名"], None)
                continue
            n = 缺席.get(台["名"], 0)
            if n % 3 == 0:                       # 头三次每轮都试，之后每 3 轮试一次
                写日志("%s（口 %d）不在，拉起来" % (台["名"], 台["口"]))
                拉起来(台)
            缺席[台["名"]] = n + 1
        time.sleep(间隔)


前台 = False
if __name__ == "__main__":
    args = sys.argv[1:]
    前台 = "--前台" in args

    if "--状态" in args:
        for 台 in 台们:
            好 = 在听吗(台["口"])
            print("  %s 口 %-5d %s" % (台["名"], 台["口"], "✓ 在听" if 好 else "✗ 没人听"))
        sys.exit(0)

    if "--一遍" in args:
        for 台 in 台们:
            if not 在听吗(台["口"]):
                写日志("（--一遍）%s 不在，拉起来" % 台["名"])
                拉起来(台)
                time.sleep(2)
        for 台 in 台们:
            print("  %s 口 %-5d %s" % (台["名"], 台["口"], "✓ 在听" if 在听吗(台["口"]) else "✗ 还是没人听"))
        sys.exit(0)

    别的 = 单实例()
    if 别的:
        print("已经有一个守护在跑了（pid %d），这个不重复起" % 别的)
        sys.exit(0)
    try:
        with open(锁文件, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    主循环()
