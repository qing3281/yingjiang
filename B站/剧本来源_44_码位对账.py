# -*- coding: utf-8 -*-
"""
探针 44 —— 决定性检验：字体字形表的码位标注是否与密文码位真正对齐？

前情：字形图把 U+E3E8 渲染成拉丁字母 D，但用「U+E3E8=在」的映射表
      却能解出通顺中文。二者必有一错。本探针直接对账。

做法：
  1. 抓一章密文，统计每个 PUA 码位出现次数（按次数降序）
  2. 用字体文件把「出现次数最高的若干码位」渲染出来，看图
  3. 同时把「映射表里出现次数最高的若干码位对应的字」列出来
  4. 若渲染出的字形与映射表声称的字不一致 → 说明码位标注/渲染有系统性偏移
"""
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
import certifi

# 规避 curl_cffi 在非 ASCII 路径下加载 CA 失败（既有约定）
_CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(_CAB):
    import shutil
    shutil.copy(certifi.where(), _CAB)
os.environ["CURL_CA_BUNDLE"] = _CAB

sys.path.insert(0, r"D:\DSHworkspace\B站")
import fanqie_novel as F

from curl_cffi import requests as creq
s = creq.Session(impersonate="chrome124")
s.verify = _CAB
H = {"Accept-Language": "zh-CN,zh;q=0.9"}

raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25, verify=_CAB)
    raws.append(F.clean_chapter_text(r.text))
raw = "\n".join(raws)
print(f"密文语料 {len(raw)} 字，标题长度分布 ok")

cnt = Counter(c for c in raw if "\ue000" <= c <= "\uf8ff")
print(f"不同 PUA 码位 {len(cnt)} 个\n")

top = [ord(c) for c, _ in cnt.most_common(60)]
print("== 出现次数最高的 24 个码位：字形渲染 vs 映射表 ==")
print(f"{'码位':8s} {'次数':>5s}  {'映射表':6s} {'字体里该码位的字形':s}")

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

TTF = r"D:\DSHworkspace\B站\情报\_font_probe\fq_subset.ttf"
f = TTFont(TTF)
cmap = f.getBestCmap()
PUA_FONT = ImageFont.truetype(TTF, 64)

cells = []
for cp in top[:24]:
    n = cnt[chr(cp)]
    mapped = F.PUA2CHAR.get(cp, "?")
    in_cmap = cp in cmap
    cells.append((cp, n, mapped, in_cmap))
    print(f"U+{cp:04X}  {n:5d}  {mapped:6s}  {'在 cmap 内' if in_cmap else '★不在 cmap 内★'}")

# 渲染这 24 个码位的字形图，供肉眼对账
COLS, CW, CH = 6, 200, 150
rows = (len(cells) + COLS - 1) // COLS
img = Image.new("RGB", (COLS * CW, rows * CH), "white")
d = ImageDraw.Draw(img)
lab = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 22)
for i, (cp, n, mapped, _) in enumerate(cells):
    r, c = divmod(i, COLS)
    x0, y0 = c * CW, r * CH
    d.rectangle([x0, y0, x0 + CW - 2, y0 + CH - 2], outline=(200, 200, 200))
    d.text((x0 + 62, y0 + 16), chr(cp), font=PUA_FONT, fill=(0, 0, 0))
    d.text((x0 + 8, y0 + 96), f"{cp:04X} x{n}", font=lab, fill=(190, 0, 0))
    d.text((x0 + 8, y0 + 120), f"表={mapped}", font=lab, fill=(0, 110, 0))
out = r"D:\DSHworkspace\B站\情报\_font_probe\对账_最高频码位.png"
img.save(out)
print(f"\n对账图已存: {out}")
