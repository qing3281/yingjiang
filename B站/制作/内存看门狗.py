# -*- coding: utf-8 -*-
"""显存/内存看门狗：让 ComfyUI 别把机器吃干。

背景：MiniMax-H3 的文本编码器 14.96 GB + 主模型 15.24 GB，本机显存只有 15.9 GB，
      必然有一个要待在系统内存里。再叠加 attention 中间量溢出，内存会被吃满，
      用户就没法用机器了。

做法：每 N 秒看一次空闲内存，低于「保底线」就调 ComfyUI 的 /api/free 让它把
      模型和缓存吐出来。同时在超过「紧急线」时把情况写进日志。

用法：
    python 内存看门狗.py                     # 保底 3 GB，紧急 1.5 GB
    python 内存看门狗.py --保底 3 --紧急 1.5
    python 内存看门狗.py --只报数             # 不真的释放，只看
"""
import argparse, ctypes, json, os, sys, time, urllib.request, datetime

COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
日志 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "内存看门狗.log")


class 内存状态(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def 空闲GB():
    st = 内存状态()
    st.dwLength = ctypes.sizeof(内存状态)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullAvailPhys / (1024 ** 3), st.dwMemoryLoad


def 释放(unload=True, free=True):
    try:
        r = urllib.request.Request(
            COMFY + "/api/free",
            data=json.dumps({"unload_models": unload, "free_memory": free}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status == 200
    except Exception as e:
        return f"失败 {e}"


def 记(文):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    行 = f"[{ts}] {文}"
    print(行, flush=True)
    try:
        with open(日志, "a", encoding="utf-8") as f:
            f.write(行 + "\n")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--保底", type=float, default=3.0, help="空闲内存低于这个数（GB）就释放")
    ap.add_argument("--紧急", type=float, default=1.5, help="低于这个数（GB）记为紧急")
    ap.add_argument("--间隔", type=float, default=4.0, help="检查间隔秒")
    ap.add_argument("--只报数", action="store_true")
    a = ap.parse_args()

    记(f"看门狗启动：保底 {a.保底} GB / 紧急 {a.紧急} GB / 每 {a.间隔} 秒")
    上次释放 = 0.0
    最低 = 999.0
    try:
        while True:
            闲, 占用率 = 空闲GB()
            最低 = min(最低, 闲)
            if 闲 < a.紧急:
                记(f"🔴 紧急！只剩 {闲:.2f} GB（占用 {占用率}%）")
            elif 闲 < a.保底:
                now = time.time()
                if now - 上次释放 > 10:          # 别太频繁地打断 ComfyUI
                    结果 = "已通知 ComfyUI 释放"
                    if not a.只报数:
                        结果 = 释放()
                    记(f"🟡 空闲 {闲:.2f} GB < 保底 {a.保底} GB → {结果}")
                    上次释放 = now
                    time.sleep(1.5)
                    新, _ = 空闲GB()
                    记(f"    释放后空闲 {新:.2f} GB（回收 {新-闲:+.2f} GB）")
            time.sleep(a.间隔)
    except KeyboardInterrupt:
        记(f"看门狗退出。本次最低空闲 {最低:.2f} GB")


if __name__ == "__main__":
    main()
