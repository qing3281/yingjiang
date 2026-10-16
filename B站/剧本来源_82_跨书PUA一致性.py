# -*- coding: utf-8 -*-
"""探针 82 —— 决定性：不同书的 PUA 码位集合是否一致？表能不能跨书通用？"""
import sys

sys.path.insert(0, r"D:\DSHworkspace\B站")
sys.stdout.reconfigure(encoding="utf-8")
from fanqie_font import PUA2CHAR
from fanqie_reader import read_chapter

BOOKS = [
    ("部族荣光（玄幻）", "7069952706521236001"),
    ("娇养玫瑰（现言）", "7137980122702807592"),
    ("皇后重生要谋反（古言）", "7151085120553120292"),
]

sets = {}
for label, cid in BOOKS:
    try:
        d = read_chapter(cid)
    except Exception as e:
        print(f"{label}: 抓取失败 {type(e).__name__}: {e}")
        continue
    codes = set(d["pua_codes"])
    missing = sorted(c for c in codes if c not in PUA2CHAR)
    sets[label] = codes
    print(f"{label}")
    print(f"   正文字数 {len(d['text'])}  PUA 字符 {d['pua_total']}  不同码位 {len(codes)}")
    print(f"   未映射码位 {len(missing)} 个"
          + (f"  例: {[hex(c) for c in missing[:6]]}" if missing else "  ✅ 全部可解"))
    print(f"   码位范围 {hex(min(codes))}~{hex(max(codes))}" if codes else "")

print()
labels = list(sets)
if len(labels) >= 2:
    base = sets[labels[0]]
    for other in labels[1:]:
        inter = base & sets[other]
        print(f"共有码位 {len(inter)} / {len(base)}({labels[0]}) / {len(sets[other])}({other})")
        print(f"   只在《{labels[0]}》出现: {len(base - sets[other])}")
        print(f"   只在《{other}》出现: {len(sets[other] - base)}")
