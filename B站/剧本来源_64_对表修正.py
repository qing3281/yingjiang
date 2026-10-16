# -*- coding: utf-8 -*-
"""
探针 64 —— charset.json 里其实有两个列表：正排列 + 逆排列。用它和自建表对拍。
（探针 63 的 bug：charset.json 是 list[list[str]]，我只取了外层。）
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
print(f"外层 list，{len(pub)} 个子项，各自长度：" +
      ", ".join(str(len(x)) for x in pub))

from fontTools.ttLib import TTFont

f = TTFont(r"D:\DSHworkspace\B站\情报\_font_probe\fq_subset.ttf")
cps = sorted(c for c in f.getBestCmap() if 0xE000 <= c <= 0xF8FF)
print(f"字体 PUA 码位 {len(cps)} 个：U+{cps[0]:04X} ~ U+{cps[-1]:04X}")

MINE = {int(k, 0): v
        for k, v in json.load(open(
            r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json",
            encoding="utf-8"))["map"].items()}

for li, table in enumerate(pub):
    if len(table) != len(cps):
        print(f"\n[子表 {li}] 长度 {len(table)} ≠ 字体 {len(cps)}，跳过")
        continue
    same = diff = 0
    bad = []
    for i, p in enumerate(table):
        m = MINE.get(cps[i])
        if p == m:
            same += 1
        else:
            diff += 1
            bad.append((i, cps[i], m, p))
    print(f"\n[子表 {li}] 对齐 {len(table)} 项：一致 {same}，不一致 {diff}")
    if bad:
        print("   前 30 条不一致：")
        for i, cp, m, p in bad[:30]:
            print(f"     索引{i:3d} U+{cp:04X}  自建={m!r:6s} 公开={p!r}")
