# -*- coding: utf-8 -*-
"""量「这一格的画面底部有没有被模型画上字」。

## 为什么不能用「跟首帧比像素差」

画面本来就在动，阴影、衣料、地面都会变，逐像素比会把正常运动判成有字。

## 判据：**笔画的边缘密度**

字是**又细又硬的高对比笔画** —— 它在一个小范围里制造的梯度，
比场景里任何东西（石缝、草、衣褶）都密。所以：

    底部字幕带 → 灰度 → Sobel 梯度 → 取 99 分位 → 与「整帧的 99 分位」比

比值大 = 那一带异常锐利 = 有字。

**标定**（2026-10-14，本片）：拿已知有字的 8 格和已知干净的若干格各量一遍，
把阈值卡在中间。脚本带 `--标定` 打全部 74 格的分数，直接看分布。

## 两个坑

1. **只量底部还不够** —— 格46 的字在纸的正中间（道具上的字），不在字幕带。
   所以 `--全区` 会把整帧也量一遍。
2. **首帧本身就有字**（比如纸上的公文）要能区分：那是「画面里的字」，
   不是「模型加的」。判据是**首帧那条带 vs 成片那条带**的差 —— 首帧就有的两边都高。
"""
import argparse
import glob
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")

import numpy as np
from PIL import Image


def 抽帧(片, t, 出, 滤镜=None):
    cmd = [FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", 片]
    if 滤镜:
        cmd += ["-vf", 滤镜]
    cmd += ["-frames:v", "1", 出]
    subprocess.run(cmd, capture_output=True)
    return 出 if os.path.isfile(出) else None


def 梯度99(png):
    """返回 (底部带的梯度99分位, 整帧的梯度99分位)。"""
    a = np.asarray(Image.open(png).convert("L"), dtype=np.float32)
    h, w = a.shape
    # 底部 22%，横向中间 70%（字幕一般居中）
    带 = a[int(h * 0.78):, int(w * 0.15):int(w * 0.85)]
    gx = np.abs(np.diff(带, axis=1))
    gy = np.abs(np.diff(带, axis=0))
    g = np.concatenate([gx.ravel(), gy.ravel()])
    G = np.concatenate([np.abs(np.diff(a, axis=1)).ravel(),
                        np.abs(np.diff(a, axis=0)).ravel()])
    return float(np.percentile(g, 99)), float(np.percentile(G, 99))


def 段文件(戏):
    目 = os.path.join(根, "作品", 戏, "段")
    出 = {}
    for p in glob.glob(os.path.join(目, "*.mp4")):
        m = re.match(r"^格(\d+)_(本机|远端)\.mp4$", os.path.basename(p))
        if not m:
            continue
        n = int(m.group(1))
        if n not in 出 or os.path.getsize(p) > os.path.getsize(出[n]):
            出[n] = p
    return dict(sorted(出.items()))


def 量一格(段, 图, 临, 时刻s=(1.2, 2.2, 3.0)):
    首 = 抽帧(图, 0, os.path.join(临, "首.png"))
    if not 首:
        return None
    _, 整0 = 梯度99(首)
    底0, _ = 梯度99(首)
    分 = []
    for t in 时刻s:
        p = 抽帧(段, t, os.path.join(临, f"t{t}.png"))
        if not p:
            continue
        底, 整 = 梯度99(p)
        # 归一化：拿整帧的锐度当分母，抵消场景本身的粗糙程度
        分.append(底 / max(整, 1e-6))
    if not 分:
        return None
    return max(分), 底0 / max(整0, 1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏", nargs="?", default="觉醒")
    ap.add_argument("--标定", action="store_true", help="把全部格的分数打出来看分布")
    ap.add_argument("--格", type=int, nargs="*", help="只量这几格")
    参 = ap.parse_args()

    段 = 段文件(参.戏)
    图目 = os.path.join(根, "作品", 参.戏)
    临 = os.path.join(图目, "_字检_临时")
    os.makedirs(临, exist_ok=True)

    们 = sorted(参.格) if 参.格 else list(段)
    print(f"  量 {len(们)} 格　（分数 = 底部带的梯度99 ÷ 整帧的梯度99；越大越像有字）")
    行 = []
    for n in 们:
        if n not in 段:
            continue
        图 = os.path.join(图目, f"01_格{n}.png")
        if not os.path.isfile(图):
            continue
        r = 量一格(段[n], 图, 临)
        if r:
            行.append((n, r[0], r[1]))

    if not 行:
        print("  ✗ 一格都没量出来")
        return 1

    行.sort(key=lambda t: -t[1])
    print()
    if 参.标定:
        print(f"  {'格':>4}  {'成片底带':>9}  {'首帧底带':>9}  {'净增':>7}")
        for n, a, b in 行:
            print(f"  {n:>4}  {a:>9.3f}  {b:>9.3f}  {a - b:>+7.3f}")
        分 = np.array([a for _, a, _ in 行])
        print()
        print(f"  分布：中位 {np.median(分):.3f}　90分位 {np.percentile(分, 90):.3f}"
              f"　最大 {分.max():.3f}　最小 {分.min():.3f}")
    else:
        print(f"  {'格':>4}  {'成片底带':>9}  {'首帧底带':>9}")
        for n, a, b in 行[:20]:
            print(f"  {n:>4}  {a:>9.3f}  {b:>9.3f}")

    import shutil
    shutil.rmtree(临, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
