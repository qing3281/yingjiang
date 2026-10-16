# -*- coding: utf-8 -*-
"""守着两条线，74 格一齐就自动总装《觉醒》。

用法：
    python _守总装_觉醒.py            # 一直等，齐了就装
    python _守总装_觉醒.py --最长 7200  # 最多守 2 小时

为什么要守着：两条线各跑各的（本机 1–40、远端 41–74），谁先跑完都不算齐。
人守着会漏（第 74 格到的那一刻可能正好是半夜），所以让脚本守。

★ 一句实话：这个脚本第一版会「以为齐了」——它只数文件个数（==74），
  但只要有一格两条线都出了（重跑过就会出现），个数到 74 时其实还缺一格。
  **判据必须是「74 个格号全在」，不是「文件有 74 个」。**
"""
import argparse
import os
import re
import subprocess
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
段 = os.path.join(根, "作品", "觉醒", "段")
py = sys.executable

模 = re.compile(r"^格(\d+)_(本机|远端)\.mp4$")


def 齐了():
    """返回（齐没齐, 有哪几格, 缺哪几格）。判据是格号，不是文件个数。"""
    有 = set()
    for 名 in os.listdir(段):
        m = 模.match(名)
        if m:
            有.add(int(m.group(1)))
    缺 = sorted(set(range(1, 75)) - 有)
    return (not 缺), sorted(有), 缺


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--最长", type=int, default=6 * 3600, help="最多守多少秒")
    ap.add_argument("--间隔", type=int, default=60, help="多少秒看一次")
    ap.add_argument("--到", default="字幕", help="总装跑到哪一步")
    参 = ap.parse_args()

    起 = time.time()
    上 = ""
    while time.time() - 起 < 参.最长:
        好, 有, 缺 = 齐了()
        行 = f"{time.strftime('%H:%M:%S')}  {len(有)}/74" + (f"  缺 {缺[:8]}" if 缺 else "  ✓ 齐")
        if 行 != 上:
            print(行, flush=True)
            上 = 行
        if 好:
            print(f"\n{'=' * 50}\n  {time.strftime('%H:%M:%S')}  74 格齐了，开始总装\n{'=' * 50}\n", flush=True)
            r = subprocess.run([py, "-X", "utf8", "-W", "ignore",
                                os.path.join(根, "_成片_觉醒.py"), "--到", 参.到],
                               cwd=根)
            print(f"\n  {time.strftime('%H:%M:%S')}  总装退出码 {r.returncode}", flush=True)
            return r.returncode
        time.sleep(参.间隔)

    print(f"  {time.strftime('%H:%M:%S')}  守到 {参.最长} 秒还没齐，退出", flush=True)
    return 2


if __name__ == "__main__":
    sys.exit(主())
