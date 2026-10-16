# -*- coding: utf-8 -*-
"""打印 02-九宫格.md 的紧凑摘要（写『动作：』字段时看用）。"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

路 = sys.argv[1] if len(sys.argv) > 1 else r"作品\雪线\02-九宫格.md"
t = open(路, encoding="utf-8").read()
块 = re.split(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$", t, flags=re.M)


def 取(b, k):
    m = re.search(rf"^-\s*{k}\s*[:：]\s*(.*)$", b, flags=re.M)
    return m.group(1).strip() if m else ""


for i in range(1, len(块), 3):
    b = 块[i + 2] if i + 2 < len(块) else ""
    print(f"[{块[i]}] {块[i+1]}  <{取(b,'景别')}> / {取(b,'机位')} / 重点:{取(b,'重点')}")
    print("   词: " + 取(b, "提示词"))
