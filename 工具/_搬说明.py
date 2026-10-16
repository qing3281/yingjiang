# -*- coding: utf-8 -*-
"""把三份提示词文件里的「我自己写的说明」搬出去，让它们 0 告警。

原因：`剧组.py` 的解析器对**认不出的行**一律记告警（`这一行不是标题 / 字段 / 续写，没人认领`）。
它的 `告警` 只打印、不当闸门，所以不卡流程 —— 但 22+20+16 条噪声会把**真的解析错误淹没掉**。
我那些 `>` 开头的解释文字对管线没用，搬去 `_提示词说明.md` 就行。

判据：搬完三份文件解析出来 **告警 0 条**，而且 32 格 / 8 锚点 / 8 锚点 一个不少。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
落 = r"D:\DSHworkspace\影匠\作品\楚子航"
说明 = ["# 提示词说明（给人看的，不进管线）\n",
        "> 这三段是从 `02-九宫格.md` / `03-四宫格.md` / `04-动态提示词.md` 里搬出来的 ——",
        "> 解析器认不出 `>` 开头的行，会记成告警，把真正的解析错误淹掉。\n"]

for f in ("02-九宫格.md", "03-四宫格.md", "04-动态提示词.md"):
    p = os.path.join(落, f)
    行 = open(p, encoding="utf-8").read().splitlines()
    留, 搬 = [], []
    for s in 行:
        if s.lstrip().startswith(">"):
            搬.append(s)
        else:
            留.append(s)
    # 收掉因为搬走而产生的连续空行
    干 = []
    for s in 留:
        if not s.strip() and (not 干 or not 干[-1].strip()):
            continue
        干.append(s)
    open(p, "w", encoding="utf-8").write("\n".join(干).rstrip() + "\n")
    说明.append("\n## 来自 %s 的说明\n" % f)
    说明.extend(搬)
    print("  %-18s 搬走 %2d 行，剩 %d 行" % (f, len(搬), len(干)))

open(os.path.join(落, "_提示词说明.md"), "w", encoding="utf-8").write("\n".join(说明) + "\n")
print("  →", os.path.join(落, "_提示词说明.md"))
