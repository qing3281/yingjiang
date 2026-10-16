# -*- coding: utf-8 -*-
"""
探针 42 —— 生成「最终权威字形表」：大字号 + 码位标签，12 列网格

目的：一次性把 362 个码位的字形看准，替换掉此前所有目视转录的误差。
每格画：上面大号字形（130px），下面红字码位标签（如 E3E8）。
输出 4 张图，每张约 8 行 x 12 列。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

TTF = r"D:\DSHworkspace\B站\情报\_font_probe\fq_subset.ttf"
OUT = r"D:\DSHworkspace\B站\情报\_font_probe"

f = TTFont(TTF)
cmap = f.getBestCmap()
codes = sorted(c for c in cmap if 0xE000 <= c <= 0xF8FF)
print(f"码位 {len(codes)} 个：U+{codes[0]:04X} ~ U+{codes[-1]:04X}")

COLS, ROWS_PER = 12, 8
PER_IMAGE = COLS * ROWS_PER
GLYPH_PX = 132
CELL_W, CELL_H = 150, 196

label_font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 30)
glyph_font = ImageFont.truetype(TTF, GLYPH_PX)


def draw_page(codes_page, idx):
    rows = (len(codes_page) + COLS - 1) // COLS
    W, H = COLS * CELL_W, rows * CELL_H
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    for i, cp in enumerate(codes_page):
        r, c = divmod(i, COLS)
        x0, y0 = c * CELL_W, r * CELL_H
        d.rectangle([x0, y0, x0 + CELL_W - 2, y0 + CELL_H - 2], outline=(210, 210, 210))
        ch = chr(cp)
        bb = d.textbbox((0, 0), ch, font=glyph_font)
        gw, gh = bb[2] - bb[0], bb[3] - bb[1]
        d.text((x0 + (CELL_W - gw) / 2 - bb[0], y0 + 20 - bb[1]), ch,
               font=glyph_font, fill=(0, 0, 0))
        lab = f"{cp:04X}"
        lb = d.textbbox((0, 0), lab, font=label_font)
        d.text((x0 + (CELL_W - (lb[2] - lb[0])) / 2, y0 + CELL_H - 52),
               lab, font=label_font, fill=(200, 0, 0))
    p = os.path.join(OUT, f"权威字形表_{idx}.png")
    img.save(p)
    print(f"  {p}  {img.size}  {len(codes_page)} 字")
    return p


n = 0
for i in range(0, len(codes), PER_IMAGE):
    n += 1
    draw_page(codes[i:i + PER_IMAGE], n)
print(f"\n共 {n} 张，每张 {COLS} 列 x {ROWS_PER} 行")
