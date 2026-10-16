# -*- coding: utf-8 -*-
"""_盘点4.py —— 重算「活工具」。比 `_盘点3.py` 宽：**把 `影匠\\**\\*.py` 与
`B站\\制作\\*.py` 也当根**（生产代码引用了谁，谁就是活的）。

为什么上一次算漏了：`_盘点3.py` 只从 AGENTS.md / 交接.md / 记忆\\** / 影匠\\知识\\** 出发，
而 `_配音楚子航.py`、`_寄片.py`、`_出官方片.py`、`_验超分片.py` 这些是我今天新写的、
还没被写进那几份文档 —— 于是它们被算成「一次性脚本」，差点被搬走。
**教训：判「谁还在用」时，根集合必须包含代码本身，不能只包含文档。**
"""
import os
import re
import sys
from collections import deque

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"


def 读(p):
    try:
        if os.path.getsize(p) > 6 * 1024 * 1024:
            return ""
        return open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


名到路 = {}
for f in os.listdir(根):
    if f.endswith(".py") and os.path.isfile(os.path.join(根, f)):
        名到路[f] = os.path.join(根, f)
print("根目录 .py 共 %d 个（含 `check_*`）" % len(名到路))

根文 = []
for f in ("AGENTS.md", "交接.md", "接续.md", "要求台账.md", "计划.md", "待办.md",
          "_待你点头.md", "_等Agent.md", "欠账总表.html", "README.md"):
    p = os.path.join(根, f)
    if os.path.isfile(p):
        根文.append(p)
for 子 in ("记忆", os.path.join("影匠", "知识")):
    for 底, 目们, 文们 in os.walk(os.path.join(根, 子)):
        目们[:] = [d for d in 目们 if d != "__pycache__"]
        for f in 文们:
            if os.path.splitext(f)[1].lower() in (".md", ".json", ".txt"):
                根文.append(os.path.join(底, f))
# ★ 生产代码本身也是根
for 子 in ("影匠", os.path.join("B站", "制作")):
    for 底, 目们, 文们 in os.walk(os.path.join(根, 子)):
        目们[:] = [d for d in 目们 if d not in ("__pycache__", "venv", "site-packages")]
        for f in 文们:
            if f.endswith((".py", ".json", ".md", ".ps1", ".cmd")):
                根文.append(os.path.join(底, f))
根文 = [p for p in 根文 if os.path.isfile(p)]
print("根文档/代码 %d 份" % len(根文))

活 = set()
队 = deque()
for p in 根文:
    for m in re.finditer(r"([A-Za-z_0-9\u4e00-\u9fff]+\.py)", 读(p)):
        f = m.group(1)
        if f in 名到路 and f not in 活:
            活.add(f)
            队.append(f)

轮 = 0
while 队 and 轮 < 4:
    批 = list(队)
    队.clear()
    轮 += 1
    for f in 批:
        for m in re.finditer(r"([A-Za-z_0-9\u4e00-\u9fff]+\.py)", 读(名到路[f])):
            g = m.group(1)
            if g in 名到路 and g not in 活:
                活.add(g)
                队.append(g)

print("传递 %d 轮：活 %d 个，一次性 %d 个" % (轮, len(活), len(名到路) - len(活)))

活行 = sorted(活)
with open(os.path.join(根, "_活工具.txt"), "w", encoding="utf-8") as fp:
    fp.write("\n".join(活行) + "\n")
print("✓ 写 _活工具.txt（%d 行）" % len(活行))

print("")
print("── 一次性（前 60）──")
孤 = sorted([f for f in 名到路 if f not in 活])
for f in 孤[:60]:
    print("   %-44s %7.1f KB" % (f, os.path.getsize(名到路[f]) / 1024))
print("   … 共 %d 个" % len(孤))
