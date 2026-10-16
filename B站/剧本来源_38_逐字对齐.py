# -*- coding: utf-8 -*-
"""
探针 38 —— 逐字对齐：找出「解出来明显不通」的具体码位

做法：把原文和解码结果按位置对齐，凡解码字在上下文中不通的地方，
直接打印「码位 + 原/解」。人眼扫一遍即可定案。
"""
import html as _html
import json
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
import fanqie_font

j = json.load(open(r"D:\DSHworkspace\B站\情报\_font_probe\font_corrections_merged.json", encoding="utf-8"))
fanqie_font.PUA2CHAR.update({int(k, 0): v for k, v in j.items() if str(k).startswith("0x") or str(k).isdigit()})

from curl_cffi import requests as creq
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526"]:
    t = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25).text
    raws.append(_html.unescape(re.sub(r"<[^>]+>", "", "".join(re.findall(r"<p>(.*?)</p>", t, re.S)))))
raw = "\n".join(raws)
dec = fanqie_font.decrypt(raw)

# 归一化：把 fanqie_font 里残留的字符串键也转成整数键
norm = {}
for k, v in list(fanqie_font.PUA2CHAR.items()):
    try:
        norm[int(k, 0)] = v
    except (ValueError, TypeError):
        pass
fanqie_font.PUA2CHAR.clear()
fanqie_font.PUA2CHAR.update(norm)

# 收集每个码位出现处的上下文（用解码后文本做上下文，便于判断）
cnt = Counter(c for c in raw if "\ue000" <= c <= "\uf8ff")
print(f"语料 {len(raw)} 字，不同 PUA 码位 {len(cnt)} 个\n")

# 高频疑似冲突：解码后同一个汉字由多个码位产生
rev = {}
for cp, ch in fanqie_font.PUA2CHAR.items():
    rev.setdefault(ch, []).append(cp)
dup = {ch: cps for ch, cps in rev.items() if len(cps) > 1}
print("== 一个汉字对应多个码位（必须逐一核实，通常其中一个是错的）==")
for ch, cps in sorted(dup.items()):
    parts = []
    for cp in cps:
        n = cnt.get(chr(cp), 0)
        parts.append(f"U+{cp:04X}({n}次)")
    print(f"   「{ch}」 ← {', '.join(parts)}")

print("\n== 每个码位的 2 条上下文（便于快速核对解出来的字是否通顺）==")
for c, n in cnt.most_common():
    cp = ord(c)
    hits = []
    for m in list(re.finditer(re.escape(c), raw))[:2]:
        a = dec[max(0, m.start() - 6):m.start()].replace("\n", "/")
        b = dec[m.end():m.end() + 6].replace("\n", "/")
        hits.append(f"{a}【{fanqie_font.PUA2CHAR.get(cp, '?')}】{b}")
    print(f"  U+{cp:04X} {fanqie_font.PUA2CHAR.get(cp, '?')} x{n:3d}  " + " ‖ ".join(hits))
