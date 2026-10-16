# -*- coding: utf-8 -*-
"""把一批格图拼成一张九宫格联系表（带格号标签），用来看景别有没有变化。

用法：
    python _联系表.py 雪线              # 45 格 → 5 行 9 列
    python _联系表.py 雪线 --列 6
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

根 = os.path.dirname(os.path.abspath(__file__))


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--列", type=int, default=9)
    ap.add_argument("--宽", type=int, default=440, help="每格缩略图宽")
    参 = ap.parse_args()

    目录 = os.path.join(根, "作品", 参.戏)
    格 = []
    i = 1
    while True:
        p = os.path.join(目录, f"01_格{i}.png")
        if not os.path.exists(p):
            break
        格.append((i, p))
        i += 1
    if not 格:
        print("✗ 一张图都没有")
        return 1

    列 = 参.列
    行 = (len(格) + 列 - 1) // 列
    im0 = Image.open(格[0][1])
    格宽 = 参.宽
    格高 = int(格宽 * im0.height / im0.width)
    标 = 26
    画布 = Image.new("RGB", (列 * 格宽, 行 * (格高 + 标)), (18, 18, 20))
    画 = ImageDraw.Draw(画布)

    for k, (号, p) in enumerate(格):
        r, c = divmod(k, 列)
        im = Image.open(p).convert("RGB").resize((格宽, 格高), Image.LANCZOS)
        画布.paste(im, (c * 格宽, r * (格高 + 标) + 标))
        画.text((c * 格宽 + 6, r * (格高 + 标) + 5), f"{号:02d}", fill=(230, 230, 230))

    出 = os.path.join(目录, f"_联系表_{len(格)}格.png")
    画布.save(出)
    print(f"✓ {出}  {画布.width}×{画布.height}  {os.path.getsize(出)/1024/1024:.2f} MB  "
          f"{len(格)} 格")
    return 0


if __name__ == "__main__":
    sys.exit(主())
