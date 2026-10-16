# -*- coding: utf-8 -*-
"""盯到 74 格齐了，自动往下走：配音 → 接片 → 头尾 → 混音 → 字幕 → 报规格。

为什么要它：两条线（本机 1-40、远端 41-74）预计 20:0x 才出齐，
人在旁边守着没意义，不如让机器等。齐了立刻开跑，一分钟不浪费。

用法：
    python _盯到齐就跑.py                 # 只盯，不动手
    python _盯到齐就跑.py --真跑          # 齐了就往下走
    python _盯到齐就跑.py --真跑 --到 字幕  # 走到指定步骤就停
"""
import argparse
import os
import subprocess
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
戏 = "觉醒"
段 = os.path.join(根, "作品", 戏, "段")
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
只数 = 74


def 齐了几个():
    有 = set()
    for f in os.listdir(段):
        if not f.endswith(".mp4"):
            continue
        if not f.startswith("格"):
            continue
        头 = f[1:].split("_")[0]
        if 头.isdigit():
            有.add(int(头))
    return 有


def 缺哪些(有):
    return [i for i in range(1, 只数 + 1) if i not in 有]


def 跑(命令, 名):
    print(f"\n{'=' * 62}\n▶ {名}\n   {' '.join(命令)}\n{'=' * 62}")
    t0 = time.time()
    r = subprocess.run(命令, cwd=根)
    print(f"   [{名}] 退出码 {r.returncode}　用时 {time.time() - t0:.0f} 秒")
    return r.returncode


def main():
    参 = argparse.ArgumentParser()
    参.add_argument("--真跑", action="store_true")
    参.add_argument("--到", default="", help="走到这个步骤就停")
    参.add_argument("--每轮", type=int, default=120, help="多久看一次（秒）")
    a = 参.parse_args()

    print(f"=== {time.strftime('%H:%M:%S')} 盯 {戏} 的 {只数} 格 ===")
    while True:
        有 = 齐了几个()
        缺 = 缺哪些(有)
        print(f"  {time.strftime('%H:%M:%S')}  已有 {len(有)}/{只数}　缺 {len(缺)}"
              + (f"　最早缺 {缺[:8]}" if 缺 else "　★ 齐了"))
        if not 缺:
            break
        time.sleep(a.每轮)

    if not a.真跑:
        print("\n（没给 --真跑，只看不动手）")
        return 0

    步骤 = [
        ("配音", [PY, "-X", "utf8", "-u", "_配台词_觉醒.py", "--头", "4.0"]),
        ("总装", [PY, "-X", "utf8", "-u", "_成片_觉醒.py", 戏, "--到", "字幕"]),
    ]
    for 名, 命令 in 步骤:
        if 跑(命令, 名) != 0:
            print(f"\n✗ {名} 失败，停在这里")
            return 1
        if a.到 and a.到 == 名:
            print(f"\n（--到 {a.到}，停）")
            return 0

    print(f"\n★ {time.strftime('%H:%M:%S')} 全流程走完")
    return 0


if __name__ == "__main__":
    sys.exit(main())
