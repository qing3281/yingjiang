# -*- coding: utf-8 -*-
"""探针 81 —— 诊断 list_chapters 的排序问题：目录页链接的文档顺序到底是什么样"""
import sys

sys.path.insert(0, r"D:\DSHworkspace\B站")
sys.stdout.reconfigure(encoding="utf-8")
from fanqie_reader import list_chapters

title, chs = list_chapters("7069948840148732967")
print(f"《{title}》 共 {len(chs)} 章（文档顺序）\n")
for i, (cid, nm) in enumerate(chs[:15]):
    print(f"  [{i:>3}] {cid}  {nm[:46]}")
print("  ...")
for i, (cid, nm) in enumerate(chs[-6:], start=len(chs) - 6):
    print(f"  [{i:>3}] {cid}  {nm[:46]}")
