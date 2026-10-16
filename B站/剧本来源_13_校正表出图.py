# -*- coding: utf-8 -*-
"""
探针 13 —— 校正表出图：把「我怀疑读错的」码位连同它在该书里的真实上下文一起渲染。
这样一眼就能看出到底应该是哪个字（字形 + 语境 双重证据）。
"""
import html as _html
import os
import re
import sys
import time
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR

FONT_DIR = r"D:\DSHworkspace\B站\情报\_font_probe"
TTF = os.path.join(FONT_DIR, "fq_subset.ttf")

# ---- 1) 抓语料 ----
BOOK = "7069948840148732967"
s = creq.Session(impersonate="chrome131")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
page = s.get(f"https://fanqienovel.com/page/{BOOK}", headers=H, timeout=25).text
cids, seen = [], set()
for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
    if m.group(1) not in seen:
        seen.add(m.group(1))
        cids.append(m.group(1))

texts = []
# 该书的免费章节是第 1~10 章（第 11 章起 isChapterLock=True），抓全免费章做语料
for cid in cids[1:11]:
    t = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25).text
    paras = re.findall(r"<p>(.*?)</p>", t, re.S)
    body = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
    texts.append(body)
    print(f"  {cid}  {len(body)} 字")
    time.sleep(0.8)
full = "\n".join(texts)
print("语料", len(full), "字")

ctx = defaultdict(list)
for m in re.finditer(r".{5}([\ue000-\uf8ff]).{5}", full):
    ctx[ord(m.group(1))].append(m.group(0))

# ---- 2) 渲染校正表 ----
tt = TTFont(TTF)
pua_all = [cp for cp in sorted(tt.getBestCmap()) if 0xE000 <= cp <= 0xF8FF]
font_big = ImageFont.truetype(TTF, 54)
font_ctx = ImageFont.truetype(r"C:\Windows\Fonts\simsun.ttc", 20)
font_lbl = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 12)

ORDER = [cp for cp in pua_all if len(ctx.get(cp, [])) >= 3]
print("出现 >=3 次的码位:", len(ORDER))

ROWH = 108
W = 1180
PER = 30                      # 每张 30 行，避免图片过高影响识别
for si in range(0, len(ORDER), PER):
    chunk = ORDER[si:si + PER]
    img = Image.new("RGB", (W, ROWH * len(chunk) + 10), "white")
    dr = ImageDraw.Draw(img)
    for i, cp in enumerate(chunk):
        y = i * ROWH + 5
        dr.line([(0, y - 2), (W, y - 2)], fill=(220, 220, 220))
        dr.text((8, y + 18), chr(cp), font=font_big, fill="black")
        dr.text((8, y + 78), f"U+{cp:04X}", font=font_lbl, fill=(180, 0, 0))
        old = PUA2CHAR.get(cp, "·")
        dr.text((78, y + 78), f"旧猜={old}", font=font_ctx, fill=(0, 110, 0))
        for j, smp in enumerate(ctx[cp][:4]):
            dr.text((150, y + 6 + j * 25), smp.replace(chr(cp), f"[{old}]"),
                    font=font_ctx, fill=(30, 30, 30))
    p = os.path.join(FONT_DIR, f"校正表_{si//PER + 1}.png")
    img.save(p)
    print("->", p, img.size, f"U+{chunk[0]:04X}~U+{chunk[-1]:04X}")
