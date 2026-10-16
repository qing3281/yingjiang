# -*- coding: utf-8 -*-
"""
剧本来源探针 09 —— 把 362 个 PUA 字形渲染成 3 张清晰图片（供视觉转录）

因为 woff2 的 cmap 只说明「码位 → 无意义 gid」，没有任何字符级元数据，
纯算法反查需要精确匹配版本的 SourceHanSansSC 字体。
但字形本身就是标准思源黑体汉字，所以「渲染成图 + 视觉识别」是 100% 可靠的路线。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = r"D:\DSHworkspace\B站\情报\_font_probe"
TTF = os.path.join(FONT_DIR, "fq_subset.ttf")
tt = TTFont(TTF)
pua = [cp for cp in sorted(tt.getBestCmap()) if 0xE000 <= cp <= 0xF8FF]
print("PUA 总数:", len(pua))

COLS, CELL, PAD = 10, 104, 26
PER_SHEET = 130
font_big = ImageFont.truetype(TTF, 78)
try:
    font_lbl = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 12)
except Exception:
    font_lbl = None

for si in range(0, len(pua), PER_SHEET):
    chunk = pua[si : si + PER_SHEET]
    rows = (len(chunk) + COLS - 1) // COLS
    W = COLS * CELL
    H = rows * (CELL + PAD)
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    for i, cp in enumerate(chunk):
        cx = (i % COLS) * CELL
        cy = (i // COLS) * (CELL + PAD)
        dr.rectangle([cx + 1, cy + 1, cx + CELL - 2, cy + CELL + PAD - 2], outline=(225, 225, 225))
        try:
            dr.text((cx + 10, cy + 4), chr(cp), font=font_big, fill="black")
        except Exception as e:
            print("  render fail", hex(cp), e)
        dr.text((cx + 8, cy + CELL + 4), f"E{cp:04X}".replace("E", "", 1).rjust(4, "0"), font=font_lbl, fill=(190, 0, 0))
    p = os.path.join(FONT_DIR, f"字形表_{si//PER_SHEET + 1}.png")
    img.save(p)
    print(f"  -> {p}  {img.size}  含 {len(chunk)} 字 (U+{chunk[0]:04X} ~ U+{chunk[-1]:04X})")
