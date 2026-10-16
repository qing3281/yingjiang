# -*- coding: utf-8 -*-
"""
探针 66 —— 决定性对拍：公开 charset.json 子表0 与自建映射表逐位比较

子表0 索引 1 对应 U+E3E9（锚点『在 主 特 家 军 然 表 场』定位），
所以 codepoint = U+E3E8 + index。
"""
import base64
import json
import sys
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "probe", "Accept": "application/vnd.github+json"}
d = json.loads(u.urlopen(u.Request(
    "https://api.github.com/repos/ying-ck/fanqienovel-downloader/contents/src/charset.json",
    headers=UA), timeout=25).read())
pub = json.loads(base64.b64decode(d["content"]).decode("utf-8", "replace"))[0]

from fontTools.ttLib import TTFont
f = TTFont(r"D:\DSHworkspace\B站\情报\_font_probe\fq_subset.ttf")
cmap = f.getBestCmap()
fontcps = set(c for c in cmap if 0xE000 <= c <= 0xF8FF)

MINE = {int(k, 0): v for k, v in json.load(open(
    r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json",
    encoding="utf-8"))["map"].items()}

EXTRA = {0xE3F6: "?", 0xE3FE: "?", 0xE3FF: "?", 0xE419: "?", 0xE45B: "?",
         0xE4B6: "?", 0xE4D4: "?", 0xE4D8: "?", 0xE51A: "?", 0xE51F: "?"}

same = diff = unknown = 0
bad = []
notin = []
for i, p in enumerate(pub):
    cp = 0xE3E8 + i
    if cp not in fontcps:
        notin.append((i, cp, p))
        continue
    m = MINE.get(cp)
    if p == "?":
        unknown += 1
        continue
    if p == m:
        same += 1
    else:
        diff += 1
        bad.append((i, cp, m, p))

print(f"公开子表0 共 {len(pub)} 项")
print(f"  落在本字体 cmap 内的：{len(pub) - len(notin)}")
print(f"  一致 {same} / 不一致 {diff} / 公开表标『?』{unknown}")
print(f"  超出本字体范围的 {len(notin)} 项：")
for i, cp, p in notin:
    print(f"     索引{i:3d} U+{cp:04X}  公开={p!r}")
if bad:
    print(f"\n不一致明细（{len(bad)} 条）：")
    for i, cp, m, p in bad[:50]:
        print(f"   U+{cp:04X}  自建={m!r:6s} 公开={p!r}")
else:
    print("\n✔ 逐位完全一致、零冲突")
print(f"\n自建表条目 {len(MINE)}，字体 cmap PUA {len(fontcps)}")
