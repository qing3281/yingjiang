# -*- coding: utf-8 -*-
"""_盘点3.py —— 只读。两件：
  ① 从**核心文档**出发做传递闭包，算出根目录里到底哪些 `_*.py` 是「活工具」
     （核心文档 = AGENTS.md / 交接.md / 接续.md / 要求台账.md / 计划.md / 记忆\\** / 影匠\\知识\\** /
       桌面 lnk；然后顺着「活脚本里又提到谁」继续扩两轮）
  ② 看清真正的定妆照在哪（`影匠\\assets\\角色\\` 是 `角色库.定妆照路径()` 真读的目录）
"""
import os
import re
import sys
import time
from collections import deque

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"


def 人(n):
    for u in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return "%.1f%s" % (n, u)
        n /= 1024.0
    return "%.1fP" % n


def 读(p):
    try:
        if os.path.getsize(p) > 6 * 1024 * 1024:
            return ""
        return open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


# ── 核心文档 ──
核心 = []
for f in ("AGENTS.md", "交接.md", "接续.md", "要求台账.md", "计划.md",
          "_待你点头.md", "_等Agent.md", "欠账总表.html", "README.md"):
    p = os.path.join(根, f)
    if os.path.isfile(p):
        核心.append(p)
for 子 in ("记忆", os.path.join("影匠", "知识")):
    for 底, 目们, 文们 in os.walk(os.path.join(根, 子)):
        目们[:] = [d for d in 目们 if d not in ("__pycache__",)]
        for f in 文们:
            if os.path.splitext(f)[1].lower() in (".md", ".json", ".txt"):
                核心.append(os.path.join(底, f))

核心文 = {p: 读(p) for p in 核心}
核心文 = {p: t for p, t in 核心文.items() if t}
print("核心文档 %d 份（%s）" % (len(核心文), 人(sum(len(t.encode('utf-8')) for t in 核心文.values()))))

# ── 传递闭包 ──
名到路 = {}
for f in os.listdir(根):
    if f.startswith("_") and f.endswith(".py"):
        名到路[f] = os.path.join(根, f)

活 = set()
队列 = deque()
for p, t in 核心文.items():
    for m in re.finditer(r"(_[^\s`\"'<>()\[\]，。、：；（）]+?\.py)", t):
        f = os.path.basename(m.group(1))
        if f in 名到路 and f not in 活:
            活.add(f)
            队列.append(f)

轮 = 0
while 队列 and 轮 < 3:
    批 = list(队列)
    队列.clear()
    轮 += 1
    for f in 批:
        t = 读(名到路[f])
        for m in re.finditer(r"(_[^\s`\"'<>()\[\]，。、：；（）]+?\.py)", t):
            g = os.path.basename(m.group(1))
            if g in 名到路 and g not in 活:
                活.add(g)
                队列.append(g)

print("传递 %d 轮后：活工具 %d 个，其余 %d 个" % (轮, len(活), len(名到路) - len(活)))

print("")
print("── 活工具（按目录里的字节）──")
活行 = sorted(活, key=lambda f: -os.path.getsize(名到路[f]))
for f in 活行:
    print("   %-34s %7s  %s" % (f, 人(os.path.getsize(名到路[f])),
                                time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(名到路[f])))))

print("")
print("── 一次性脚本（不在活集合里）按 mtime 分月 ──")
月 = {}
for f in 名到路:
    if f in 活:
        continue
    k = time.strftime("%m-%d", time.localtime(os.path.getmtime(名到路[f])))
    月.setdefault(k, []).append(f)
for k in sorted(月):
    print("   %s  %3d 个" % (k, len(月[k])))

# ── 定妆照真身 ──
print("")
print("── 定妆照真身（`角色库.定妆照路径()` = 影匠\\assets\\角色\\<名>.png）──")
for 路 in (os.path.join(根, "影匠", "assets", "角色"),
           os.path.join(根, "影匠", "assets")):
    if not os.path.isdir(路):
        print("   ✗ %s 不在" % 路)
        continue
    print("   %s" % 路)
    for f in sorted(os.listdir(路))[:24]:
        q = os.path.join(路, f)
        print("       %9s  %s  %s" % (人(os.path.getsize(q)) if os.path.isfile(q) else "目录",
                                      time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(q))), f))

with open(os.path.join(根, "_活工具.txt"), "w", encoding="utf-8") as fp:
    fp.write("\n".join(活行))
print("")
print("✓ 活工具清单写到 _活工具.txt（%d 行）" % len(活行))
