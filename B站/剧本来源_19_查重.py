# -*- coding: utf-8 -*-
"""探针 19 —— 反向映射查重：找出 PUA2CHAR 里映射到同一汉字的码位（即转录冲突）。"""
import io
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR

full = r"D:\DSHworkspace\B站\情报\_font_probe\上下文核对表.txt"
have = set()
for line in io.open(full, encoding="utf-8"):
    m = re.match(r"U\+([0-9A-F]{4})", line)
    if m:
        have.add(int(m.group(1), 16))

print("映射表码位总数:", len(PUA2CHAR))
print("语料中出现过的:", len(have))
print("0 出现的码位:", len([c for c in PUA2CHAR if c not in have]))
print()

rev = defaultdict(list)
for cp, ch in PUA2CHAR.items():
    rev[ch].append(cp)

dups = {ch: cps for ch, cps in rev.items() if len(cps) > 1}
print(f"== 反向重复（{len(dups)} 组）—— 每组里必有转录错误 ==")
for ch, cps in sorted(dups.items(), key=lambda kv: kv[1][0]):
    print(f"  {ch}: " + "  ".join(f"U+{c:04X}" for c in sorted(cps)))

print()
print("== 重点字在映射表里的归位 ==")
for ch in "我战年无目不友下关结老2图恩按早黑音0":
    if ch in rev:
        print(f"  {ch} -> " + ", ".join(f"U+{c:04X}" for c in sorted(rev[ch])))
    else:
        print(f"  {ch} -> (未映射) ★")

print()
print("== 语料里 0 出现的码位（无法用语料校验，保留原转录）==")
print("  " + " ".join(f"{PUA2CHAR[c]}:U+{c:04X}" for c in sorted(c for c in PUA2CHAR if c not in have)))
