# -*- coding: utf-8 -*-
"""_盘点2.py —— 只读。看三样：
  ① 影匠\\ 的内部结构（哪些是代码、哪些是产物、哪些是参考素材）
  ② 角色卡 / 定妆照到底哪一套是「现在正在用的」（出片脚本真读的是哪个路径）
  ③ 根目录那 724 个 `_*.py` 里，哪些是**还在用的工具**（被 AGENTS.md / 桌面 lnk / 开工脚本引用），
     哪些是一次性调试脚本
"""
import os
import re
import sys
import time
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"


def 人(n):
    for u in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return "%.1f%s" % (n, u)
        n /= 1024.0
    return "%.1fP" % n


def 大(p):
    if os.path.isfile(p):
        try:
            return os.path.getsize(p)
        except OSError:
            return 0
    s = 0
    for 底, 目, 文 in os.walk(p):
        for f in 文:
            try:
                s += os.path.getsize(os.path.join(底, f))
            except OSError:
                pass
    return s


print("═══ ① 影匠\\ 下各目录 ═══")
影 = os.path.join(根, "影匠")
行 = []
for n in sorted(os.listdir(影)):
    p = os.path.join(影, n)
    行.append((大(p), os.path.isdir(p), n))
for s, d, n in sorted(行, reverse=True):
    print("  %-9s %-4s %s" % (人(s), "目录" if d else "文件", n))

print("")
print("═══ ② 角色卡 / 定妆照 ═══")
for 路 in (os.path.join(影, "角色卡"), os.path.join(影, "作品", "楚子航", "_定妆照"),
           os.path.join(影, "作品", "楚子航", "_定妆卡_楚子航"),
           os.path.join(影, "作品", "楚子航", "_定妆卡_夏弥"),
           os.path.join(影, "作品", "楚子航", "_定妆卡_耶梦加得")):
    if not os.path.isdir(路):
        print("  ✗ %s 不在" % 路)
        continue
    print("  %s（%s）" % (路, 人(大(路))))
    for f in sorted(os.listdir(路))[:14]:
        q = os.path.join(路, f)
        print("      %9s  %s  %s" % (人(大(q)) if os.path.isfile(q) else "目录",
                                     time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(q))), f))

print("")
print("═══ ②b 出片脚本到底读哪个路径当角色参考 ═══")
for f in ("导演.py", "引擎.py", "角色.py", "角色库.py"):
    p = os.path.join(影, f)
    if not os.path.isfile(p):
        continue
    s = open(p, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r'^.*(定妆|角色卡|锚点|参考图).*$', s, re.M):
        L = m.group(0).strip()
        if "=" in L or "join" in L or "def " in L:
            print("  %-10s %s" % (f, L[:130]))

print("")
print("═══ ③ 根目录 `_*.py` 是被引用还是孤儿 ═══")
脚本 = [f for f in os.listdir(根) if f.startswith("_") and f.endswith(".py")]
全 = {}
for f in os.listdir(根):
    p = os.path.join(根, f)
    if os.path.isfile(p) and os.path.splitext(f)[1].lower() in (".md", ".py", ".ps1", ".cmd", ".txt", ".lnk"):
        try:
            if os.path.getsize(p) < 4 * 1024 * 1024:
                全[f] = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            pass

引用 = defaultdict(set)
for f in 脚本:
    for 主, 文 in 全.items():
        if 主 == f:
            continue
        if f in 文:
            引用[f].add(主)

活 = sorted([f for f in 脚本 if f in 引用], key=lambda x: (-len(引用[x]), x))
孤 = sorted([f for f in 脚本 if f not in 引用])
print("  共 %d 个脚本；被别处提到过 %d 个，没人提到 %d 个" % (len(脚本), len(活), len(孤)))
print("")
print("  ── 被提到最多的 25 个（多半是在用的工具）──")
for f in 活[:25]:
    print("     %-34s 被 %2d 处引用" % (f, len(引用[f])))
print("")
print("  ── 没人提到的（多半是一次性调试脚本）前 30 个 ──")
for f in 孤[:30]:
    p = os.path.join(根, f)
    print("     %-40s %7s  %s" % (f, 人(os.path.getsize(p)),
                                  time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))))
print("  …（一共 %d 个）" % len(孤))
