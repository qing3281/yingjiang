# -*- coding: utf-8 -*-
"""从 `_会话_LMtio\\A_用户.md` 里按关键词取一段**连续原文**。

## 为什么要专门取「连续原文」

`_待你点头.md` 的「他哪句话让我做这个」那一栏，`_候你点头.py --查` 是拿
**逐字（去空白标点后）子串**去比的。我原来贴的是**省略过的引**：

    「**加到5分钟**，……更加详细的描写……**台词可以不动」     ← 中间有 ……

省略过的引**永远搜不到** —— 于是闸把它判成「我编的，不是他说的」，
而它其实是真话。**这正是「假判据」的一种：冤枉真话，比漏判更危险。**

所以贴之前先跑这个脚本，把**连续的一段**原样取出来。
"""
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")

路 = r"D:\DSHworkspace\_会话_LMtio\A_用户.md"
要看的 = [
    "加到5分钟",
    "中间还有很多很诡异的情况",
    "台词可以不动",
]

for 词 in 要看的:
    print("═" * 70)
    print("  关键词：%s" % 词)
    n = 0
    for i, 线 in enumerate(io.open(路, encoding="utf-8", errors="replace"), 1):
        j = 线.find(词)
        if j < 0:
            continue
        n += 1
        a = max(0, j - 6)
        print("  行 %d（这一行共 %d 字）：" % (i, len(线)))
        print("    " + 线[a:a + 150].replace("\n", " "))
        if n >= 3:
            break
    if not n:
        print("  ✗ 一条都没搜到")
