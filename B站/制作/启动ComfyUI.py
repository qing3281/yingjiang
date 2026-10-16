# -*- coding: utf-8 -*-
"""启动本机 ComfyUI（Desktop 版内核），等它就绪，然后常驻。

用法：
    python 启动ComfyUI.py            # 起服务并等就绪，然后一直挂着
    python 启动ComfyUI.py --只等     # 不启动，只等服务就绪

设计要点：
  * 用 .venv 里的 python 直接跑 main.py，不依赖 Desktop 那个 Electron 壳
  * 模型路径走 extra_model_paths.yaml，跟 Desktop 版一致
  * 启动后轮询 /system_stats，就绪了才返回，避免上层脚本抢跑
  * 本进程常驻并把子进程输出转存到日志，Ctrl+C 时连带关掉子进程
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

根 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
PY = os.path.join(根, ".venv", "Scripts", "python.exe")
模型表 = r"D:\DSHworkspace\B站\制作\extra_model_paths.yaml"
输出目录 = r"D:\Comfy-Desktop\ComfyUI-Shared\output"
输入目录 = r"D:\Comfy-Desktop\ComfyUI-Shared\input"
日志 = r"D:\DSHworkspace\B站\制作\ComfyUI启动.log"
地址 = "http://127.0.0.1:8188"


def 活着(超时=3):
    try:
        urllib.request.urlopen(地址 + "/system_stats", timeout=超时).read()
        return True
    except Exception:
        return False


def 等就绪(最多秒=600):
    t0 = time.time()
    while time.time() - t0 < 最多秒:
        if 活着():
            print(f"   ✅ ComfyUI 就绪（等了 {time.time()-t0:.0f} 秒）")
            return True
        time.sleep(3)
        if int(time.time() - t0) % 30 < 3:
            print(f"   [{time.time()-t0:5.0f}s] 还在起…", flush=True)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--只等", action="store_true")
    ap.add_argument("--端口", type=int, default=8188)
    a = ap.parse_args()

    if 活着():
        print(f"✅ ComfyUI 已经在跑（{地址}），不用重启")
        return 0
    if a.只等:
        print("⏳ 只等模式：等服务就绪…")
        return 0 if 等就绪() else 1

    for p in (PY, os.path.join(根, "main.py"), 模型表):
        if not os.path.isfile(p):
            print(f"❌ 找不到 {p}")
            return 1

    命令 = [
        PY, "main.py",
        "--port", str(a.端口),
        "--listen", "127.0.0.1",
        "--extra-model-paths-config", 模型表,
        "--output-directory", 输出目录,
        "--input-directory", 输入目录,
    ]
    print("启动：")
    print("  cwd " + 根)
    print("  " + " ".join(命令))
    句柄 = open(日志, "a", encoding="utf-8", errors="replace")
    句柄.write(f"\n\n{'='*70}\n[启动ComfyUI] {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}\n")
    句柄.flush()

    进程 = subprocess.Popen(命令, cwd=根, stdout=句柄, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    print(f"   pid {进程.pid} → 日志 {日志}")

    try:
        if not 等就绪():
            print("❌ 等了 10 分钟还没就绪，看日志：", 日志)
            return 1
        print(f"\n✅ ComfyUI 跑在 {地址}（pid {进程.pid}）")
        print("   （本进程常驻看门；Ctrl+C 结束）")
        while 进程.poll() is None:
            time.sleep(5)
        print(f"⚠ ComfyUI 退出了，返回码 {进程.returncode}")
        return 进程.returncode or 0
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，关掉 ComfyUI…")
        进程.terminate()
        try:
            进程.wait(timeout=20)
        except subprocess.TimeoutExpired:
            进程.kill()
        return 0
    finally:
        句柄.close()


if __name__ == "__main__":
    sys.exit(main())
