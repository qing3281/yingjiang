# -*- coding: utf-8 -*-
"""量一组视频的运动量，并拼出抽帧对照图。

用法：
    python 量运动.py <视频目录或单个mp4> [-o 输出.png] [--匹配 关键词] 
"""
import argparse
import os
import glob
import sys

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

F = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 26)


def 量(路: str):
    """返回 (帧列表, 逐帧帧间差数组)"""
    c = av.open(路)
    s = c.streams.video[0]
    帧, 差, 前 = [], [], None
    for f in c.decode(s):
        a = np.asarray(f.to_image().convert("L"), dtype=np.float32)
        if 前 is not None:
            差.append(float(np.abs(a - 前).mean()))
        前 = a
        帧.append(f.to_image())
    c.close()
    return 帧, np.array(差)


def 条(路: str, 标签: str, 宽: int = 430) -> Image.Image:
    帧, 差 = 量(路)
    n = len(帧)
    时刻 = [0.2, n / 24 * 0.32, n / 24 * 0.60, n / 24 * 0.84, max(0.1, n / 24 - 0.2)]
    idx = [min(n - 1, int(t * 24)) for t in 时刻]
    ims = [帧[i].resize((宽, int(宽 * 768 / 1344)), Image.LANCZOS) for i in idx]
    r = Image.new("RGB", (宽 * len(ims), ims[0].height), (0, 0, 0))
    for i, im in enumerate(ims):
        r.paste(im, (i * 宽, 0))
    d = ImageDraw.Draw(r)
    d.rectangle([0, 0, 500, 34], fill=(0, 0, 0))
    d.text((8, 2), f"{标签}  μ{差.mean():.2f}  P90 {np.percentile(差, 90):.1f}  峰 {差.max():.1f}",
           font=F, fill=(140, 255, 170))
    return r, float(差.mean()), float(np.percentile(差, 90)), float(差.max())


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument("目标")
    a.add_argument("-o", "--出图", default="")
    a.add_argument("--匹配", default="")
    a = a.parse_args()

    路 = []
    if os.path.isfile(a.目标):
        路 = [a.目标]
    else:
        for p in sorted(glob.glob(os.path.join(a.目标, "*.mp4"))):
            if a.匹配 and a.匹配 not in os.path.basename(p):
                continue
            路.append(p)
    if not 路:
        print("没找到 mp4")
        return 1

    行 = []
    表 = []
    for p in 路:
        标 = os.path.splitext(os.path.basename(p))[0]
        r, μ, p90, 峰 = 条(p, 标)
        行.append(r)
        表.append((标, μ, p90, 峰))
        print(f"  {标:<28} μ{μ:6.2f}  P90 {p90:6.2f}  峰 {峰:6.2f}")

    if 表:
        全 = np.array([t[1] for t in 表])
        print(f"\n  {'平均':<28} μ{全.mean():6.2f}   （{len(表)} 条）")

    if a.出图:
        sh = Image.new("RGB", (max(r.width for r in 行), sum(r.height for r in 行) + 8 * (len(行) - 1)), (10, 11, 15))
        y = 0
        for r in 行:
            sh.paste(r, (0, y))
            y += r.height + 8
        sh.save(a.出图)
        print(f"\n✓ {a.出图}  {sh.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
