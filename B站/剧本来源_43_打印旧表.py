# -*- coding: utf-8 -*-
"""
探针 43 —— 把「旧映射表」按码位顺序打印出来，便于与字形图逐格比对

旧表 = 情报/_font_probe/pua_map_old.json（在此之前已被验证能解出通顺中文）
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

OLD = json.load(open(r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json", encoding="utf-8"))["map"]
OLD = {int(k, 0): v for k, v in OLD.items()}
GAPS = {0xE3F6, 0xE3FE, 0xE3FF, 0xE419, 0xE45B, 0xE4B6, 0xE4D4, 0xE4D8}
codes = [c for c in range(0xE3E8, 0xE55C) if c not in GAPS | {0xE51A, 0xE51F}]

print(f"码位 {len(codes)} 个\n")
COLS = 12
for i in range(0, len(codes), COLS):
    row = codes[i:i + COLS]
    top = "  ".join(f"{c:04X}" for c in row)
    mid = "    ".join(OLD.get(c, "?") for c in row)
    print(top)
    print(mid)
    print()
