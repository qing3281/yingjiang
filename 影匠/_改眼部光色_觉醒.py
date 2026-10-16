# -*- coding: utf-8 -*-
"""光色字段里「眼窝是两块黑」这类写法会把眼部阴影画成一整块死黑。

改法：把「压成两块黑 / 眼窝是两块黑」换成「眼窝陷进阴影里 / 眼窝没进阴影」——
说的是**光**，不是**色块**。模型对「两块黑」是照着色块画的。
"""
import io
import os

根 = os.path.dirname(os.path.abspath(__file__))
分镜 = os.path.join(根, "作品", "觉醒", "02-九宫格.md")

对表 = [
    ("把眼窝的深处压成两块黑", "让眼窝整个陷进阴影里"),
    ("眼窝是两块黑", "眼窝没进阴影里，而不是涂黑"),
    ("眼窝里的两块黑比之前更深", "眼窝里的阴影比之前更深"),
    ("眼窝是两团黑", "眼窝没进阴影里"),
]

t = io.open(分镜, encoding="utf-8").read()
前 = len(t)
计 = {}
for a, b in 对表:
    n = t.count(a)
    if n:
        t = t.replace(a, b)
        计[a] = n
io.open(分镜, "w", encoding="utf-8").write(t)

for k, v in 计.items():
    print(f"  {k}  ×{v}")
print(f"  共 {sum(计.values())} 处  ({前} → {len(t)} 字节)")

# 复验
t2 = io.open(分镜, encoding="utf-8").read()
剩 = sum(t2.count(a) for a, _ in 对表)
print(f"\n复验：旧写法还剩 {剩} 处（应为 0）")
