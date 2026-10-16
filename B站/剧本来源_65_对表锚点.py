# -*- coding: utf-8 -*-
"""探针 65 —— 看 charset.json 两个子表的原始首尾，判断长度差异来源"""
import base64
import json
import sys
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "probe", "Accept": "application/vnd.github+json"}
d = json.loads(u.urlopen(u.Request(
    "https://api.github.com/repos/ying-ck/fanqienovel-downloader/contents/src/charset.json",
    headers=UA), timeout=25).read())
pub = json.loads(base64.b64decode(d["content"]).decode("utf-8", "replace"))

from fontTools.ttLib import TTFont
f = TTFont(r"D:\DSHworkspace\B站\情报\_font_probe\fq_subset.ttf")
cps = sorted(c for c in f.getBestCmap() if 0xE000 <= c <= 0xF8FF)

MINE = {int(k, 0): v for k, v in json.load(open(
    r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json",
    encoding="utf-8"))["map"].items()}

for li, t in enumerate(pub):
    print(f"\n[子表 {li}] len={len(t)}")
    print("  前 20:", t[:20])
    print("  后 20:", t[-20:])
    print("  '?' 个数:", t.count("?"), " 空串个数:", sum(1 for x in t if x == ""))

# 子表1 前 20 项几乎就是我的表前 20 项（顺序不同）—— 说明它是「码位->字」但
# 起点/长度不同。用共同序列「在,主,特,家,军,然」做锚点找对齐偏移。
anchor = ["在", "主", "特", "家", "军", "然", "表", "场"]
for li, t in enumerate(pub):
    for i in range(len(t) - len(anchor)):
        if t[i:i + len(anchor)] == anchor:
            print(f"\n[子表 {li}] 锚点『{' '.join(anchor)}』出现在索引 {i}")
            print(f"   对应字体码位 U+{cps[i]:04X}" if i < len(cps) else "   超出字体范围")
            break
    else:
        print(f"\n[子表 {li}] 未找到锚点")
