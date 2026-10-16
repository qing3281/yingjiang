# -*- coding: utf-8 -*-
"""
探针 46 —— 重新生成权威字形表（用「对账图」那套已验证可靠的渲染配方）

关键差异（旧版错在标签错位）：
  - 用 fontTools cmap -> glyph 名，再用 glyf 轮廓自己在**同一张图**上重画？不做。
  - 直接用 PIL truetype(TTF, size) 画 chr(cp)，标签写 cp。
    （这正是 对账_最高频码位.png 用的配方，已由人工核对确认真实对齐：
      E4F3=的 E436=了 E4DE=一 E4C2=人 E444=着 E47D=上 E52A=不 E531=下
      E3E9=在 E508=小 E4FF=开 E44C=色 E510=口 E41E=是 E4FA=来 E489=身
      E480=有 E547=她 E528=眼 E409=男 E488=声 E54C=子 E521=我 E44D=里）
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
print(f"cmap 码位 {len(codes)}：U+{codes[0]:04X} ~ U+{codes[-1]:04X}")

COLS = 12
PER = 96
GLYPH_PX = 116
CW, CH = 172, 186

glyph_font = ImageFont.truetype(TTF, GLYPH_PX)
lab = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 27)

for pi in range(0, len(codes), PER):
    page = codes[pi:pi + PER]
    rows = (len(page) + COLS - 1) // COLS
    img = Image.new("RGB", (COLS * CW, rows * CH), "white")
    d = ImageDraw.Draw(img)
    for i, cp in enumerate(page):
        r, c = divmod(i, COLS)
        x0, y0 = c * CW, r * CH
        d.rectangle([x0, y0, x0 + CW - 2, y0 + CH - 2], outline=(215, 215, 215))
        ch = chr(cp)
        bb = d.textbbox((0, 0), ch, font=glyph_font)
        d.text((x0 + (CW - (bb[2] - bb[0])) / 2 - bb[0], y0 + 14 - bb[1]),
               ch, font=glyph_font, fill=(0, 0, 0))
        t = f"{cp:04X}"
        lb = d.textbbox((0, 0), t, font=lab)
        d.text((x0 + (CW - (lb[2] - lb[0])) / 2, y0 + CH - 46), t, font=lab, fill=(195, 0, 0))
    p = os.path.join(OUT, f"字表B_{pi // PER + 1}.png")
    img.save(p)
    print(f"  {p}  {img.size}  {len(page)} 格")
print("完成")
