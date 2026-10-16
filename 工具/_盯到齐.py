# -*- coding: utf-8 -*-
"""
_盯到齐.py —— 盯着《楚子航》的 32 段视频，齐了就自动接片 + 烧硬字幕 + 重生成验收页。

★ 为什么要有它：出片要跑到 04:30 左右，我不该在它旁边干等（等 = 空转 = 烧他的钱）。
  交给一个后台进程盯着，齐了自己收尾；我这边去干别的。

用法：
    python _盯到齐.py            # 盯到 32 段齐，然后自动收尾
    python _盯到齐.py --就跑一次  # 不盯，现在有什么接什么（调试用）
"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
戏 = os.path.join(根, "影匠", "作品", "楚子航")
段目 = os.path.join(戏, "段")
出目 = os.path.join(戏, "片")
Python = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"


def 齐了几格():
    有 = set()
    if os.path.isdir(段目):
        for f in os.listdir(段目):
            if f.startswith("格") and f.endswith(".mp4"):
                try:
                    n = int(f[1:].split("_")[0])
                except Exception:
                    continue
                有.add(n)
    return 有


def 说(s):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), s), flush=True)


def 收尾(齐):
    os.makedirs(出目, exist_ok=True)
    说("32 段齐了 —— 开始接片 + 烧硬字幕")
    p = subprocess.run(
        [Python, "-X", "utf8", os.path.join(戏, "_接片楚子航.py"), "--烧"],
        cwd=戏, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for 行 in (p.stdout or "").splitlines():
        if any(k in 行 for k in ("✓", "✗", "⚠", "▶", "片", "秒", "MB", "B")):
            说("  " + 行.strip())
    if p.returncode != 0:
        说("★ 接片退出码 %s　stderr：%s" % (p.returncode, (p.stderr or "")[-500:]))
    成 = os.path.join(出目, "楚子航_成片_字幕.mp4")
    if os.path.exists(成):
        说("✓ 成片：%s  %.1f MB" % (成, os.path.getsize(成) / 1048576))
    else:
        说("★ 没出成片 —— 去 %s 看" % 出目)
    # 验收页跟着更新（不然他双击桌面「验收」看到的还是旧的）
    v = subprocess.run([Python, "-X", "utf8", os.path.join(根, "_生成验收.py")],
                       cwd=根, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for 行 in (v.stdout or "").splitlines():
        说("  " + 行.strip())
    return 成


def 主():
    就一次 = "--就跑一次" in sys.argv
    if 就一次:
        收尾(齐了几格())
        return
    上次 = -1
    轮 = 0
    while True:
        齐 = 齐了几格()
        n = len(齐)
        if n != 上次:
            说("段 %d / 32　缺：%s" % (n, " ".join(str(x) for x in sorted(set(range(1, 33)) - 齐))))
            上次 = n
        if n >= 32:
            收尾(齐)
            说("收工")
            return
        # 20 分钟一格都没涨 = 卡死了，别傻等
        轮 += 1
        if 轮 % 40 == 0:
            说("（盯着，还没齐）")
        time.sleep(30)


if __name__ == "__main__":
    主()
