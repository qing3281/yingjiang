# -*- coding: utf-8 -*-
"""
探针 63 —— 用公开的 charset.json（ying-ck/fanqienovel-downloader，★2384）
逐索引对齐自建映射表，自动定位到底哪个位置开始错位，并用它修表。

charset.json = list[str]，第 i 项对应字体 cmap 里第 i 个 PUA 码位（按升序）。
「?」表示原作者也没认出来的字。
"""
import base64
import json
import sys
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "probe", "Accept": "application/vnd.github+json"}


def raw(repo, path):
    d = json.loads(u.urlopen(u.Request(
        f"https://api.github.com/repos/{repo}/contents/{path}", headers=UA),
        timeout=25).read())
    return base64.b64decode(d["content"]).decode("utf-8", "replace")


pub = json.loads(raw("ying-ck/fanqienovel-downloader", "src/charset.json"))
print(f"公开表：{len(pub)} 项")

# 字体 cmap 里 PUA 码位的升序列表（用之前落盘的字体文件）
from fontTools.ttLib import TTFont

f = TTFont(r"D:\DSHworkspace\B站\情报\_font_probe\fq_subset.ttf")
cps = sorted(c for c in f.getBestCmap()
             if 0xE000 <= c <= 0xF8FF)
print(f"字体 PUA 码位：{len(cps)} 个（U+{cps[0]:04X} ~ U+{cps[-1]:04X}）")

MINE = {int(k, 0): v
        for k, v in json.load(open(
            r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json",
            encoding="utf-8"))["map"].items()}

if len(pub) != len(cps):
    print(f"⚠ 长度不等：公开 {len(pub)} vs 字体 {len(cps)}")

n = min(len(pub), len(cps))
same = diff = unknown = 0
first_bad = None
bad_list = []
for i in range(n):
    p, m = pub[i], MINE.get(cps[i])
    if p == "?":
        unknown += 1
        continue
    if p == m:
        same += 1
    else:
        diff += 1
        if first_bad is None:
            first_bad = i
        bad_list.append((i, cps[i], m, p))

print(f"\n对齐结果（共 {n} 项）：一致 {same}，不一致 {diff}，公开表未识别 {unknown}")
if first_bad is not None:
    print(f"首个不一致出现在索引 {first_bad} (U+{cps[first_bad]:04X})："
          f"自建={MINE.get(cps[first_bad])} 公开={pub[first_bad]}")
    print("不一致明细（最多 40 条）：")
    for i, cp, m, p in bad_list[:40]:
        print(f"   索引{i:3d} U+{cp:04X}  自建={m!r:6s} 公开={p!r}")
