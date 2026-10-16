# -*- coding: utf-8 -*-
"""从**成片**里切底部条，看观众到底会看到哪些「模型自己画进去的字」。

## 为什么不能只看段文件

段文件是原始素材；成片里：
1. 格与格之间有 **0.5 秒转场**，时间轴不是简单的「格n × 4.4583」；
2. 我自己的硬字幕也压在底部同一条上。

**观众看到的才算数。** 所以要按成片的时间轴切。

## 时间轴（与 `_拼长片.py` 的 xfade 一致）

    格n 在成片里的起点 = 头卡 4.0 + (n−1) × (4.4583 − 0.5) = 4.0 + (n−1) × 3.9583

## 判据

人眼看拼图。**每格切两个时刻**（1.2s / 3.0s）——
只要有一个时刻有字，这一格就算「带字」。
"""
import argparse
import os
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")

头秒 = 4.0
每格秒 = 107 / 24.0     # 4.45833
转场吃 = 0.5
步长 = 每格秒 - 转场吃   # 3.95833


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("片", help="成片路径")
    ap.add_argument("--格起", type=int, default=1)
    ap.add_argument("--格止", type=int, default=74)
    ap.add_argument("--带", type=float, default=0.24)
    ap.add_argument("--列", type=int, default=2)
    ap.add_argument("--宽", type=int, default=620)
    参 = ap.parse_args()

    临 = os.path.join(根, "作品", "觉醒", "_成片条_临时")
    os.makedirs(临, exist_ok=True)

    from PIL import Image, ImageDraw

    条s = []
    for n in range(参.格起, 参.格止 + 1):
        起 = 头秒 + (n - 1) * 步长
        for j, 偏 in enumerate((1.2, 3.0)):
            t = 起 + 偏
            o = os.path.join(临, f"{n:02d}_{j}.png")
            subprocess.run(
                [FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", 参.片,
                 "-vf", f"crop=iw:ih*{参.带:.2f}:0:ih*(1-{参.带:.2f})",
                 "-frames:v", "1", o], capture_output=True)
            if os.path.isfile(o):
                条s.append((n, j, o))
        if n % 20 == 0:
            print(f"    切到 格{n}")

    if not 条s:
        print("  ✗ 一条都没切出来")
        return 1

    图s = [Image.open(o).convert("RGB") for _, _, o in 条s]
    每宽 = 参.宽
    每高 = int(图s[0].height * 每宽 / 图s[0].width)
    图s = [im.resize((每宽, 每高), Image.LANCZOS) for im in 图s]

    列 = 参.列
    行 = (len(图s) + 列 - 1) // 列
    标 = 20
    版 = Image.new("RGB", (每宽 * 列, (每高 + 标) * 行), (8, 8, 8))
    笔 = ImageDraw.Draw(版)
    for i, im in enumerate(图s):
        行i, 列i = divmod(i, 列)
        x, y = 列i * 每宽, 行i * (每高 + 标)
        版.paste(im, (x, y))
        笔.text((x + 5, y + 每高 + 2), "格%d·%ss" % (条s[i][0], (1.2, 3.0)[条s[i][1]]),
                fill=(255, 220, 80))

    出 = os.path.join(根, "作品", "觉醒", "_成片底部条.png")
    版.save(出)
    import shutil
    shutil.rmtree(临, ignore_errors=True)
    print(f"\n  ✓ {出}")
    print(f"     {版.width}×{版.height}　{列} 列 × {行} 行（每格两条：1.2s / 3.0s）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
