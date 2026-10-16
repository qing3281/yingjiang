# -*- coding: utf-8 -*-
import io, os
根 = os.path.dirname(os.path.abspath(__file__))
替 = [
    ("眼窝深陷，眼下有两道浅浅的青灰色眼袋（不是黑眼圈、不是淤青、不是伤）",
     "眼窝略深，眼下是两道跟皮肤同色的浅纹，那一片皮肤的颜色和脸上别处一样"),
    ("眼窝深陷，眼下只有两道浅浅的青灰色眼袋（年纪大了皮松出来的袋，不是黑眼圈、不是淤青、不是伤）",
     "眼窝略深，眼下是两道跟皮肤同色的浅纹，那一片皮肤的颜色和脸上别处一样"),
]
for 名 in ("02-九宫格.md", "00-故事.md"):
    路 = os.path.join(根, "作品", "觉醒", 名)
    t = io.open(路, encoding="utf-8").read()
    n = 0
    for a, b in 替:
        c = t.count(a)
        if c: t = t.replace(a, b); n += c
    if n: io.open(路, "w", encoding="utf-8").write(t)
    print(f"  {名}：改 {n} 处")
print("\n复验：")
for 名 in ("02-九宫格.md", "00-故事.md"):
    t = io.open(os.path.join(根, "作品", "觉醒", 名), encoding="utf-8").read()
    坏 = [w for w in ("不是黑眼圈", "不是淤青", "不是伤", "青灰色眼袋", "陷进阴影里") if w in t]
    print(f"  {名}：{'✓ 干净' if not 坏 else '✗ 还剩 ' + str(坏)}")
