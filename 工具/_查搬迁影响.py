# -*- coding: utf-8 -*-
"""_查搬迁影响.py —— 动目录之前，先数清楚「谁引用了它」。只读。

为什么要先数：`网盘\\` 362 GB 这种**同卷改名是秒级**的，
但脚本里写死的 `D:\\DSHworkspace\\网盘\\...` 会当场断掉。**先数，再动。**
"""
import collections
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"

计划 = [
    ("网盘", "素材\\网盘"),
    ("本地AI", "素材\\本地AI"),
    ("downloads", "素材\\下载"),
    ("_字体", "素材\\字体"),
    ("远程", "素材\\远程"),
    ("远程装机包", "素材\\远程装机包"),
    ("_运行时", "工具\\_运行时"),
    ("片场", "素材\\片场"),
    ("会话存档", "记忆\\会话存档"),
    ("研究", "记忆\\研究"),
    ("_归档", "记忆\\归档"),
    ("仓库", "记忆\\仓库"),
    ("_GitHub", "记忆\\_GitHub"),
    ("_出连片", "（空，删）"),
    ("_对比", "（空，删）"),
]

扫的 = []
for 模式 in ("*.py", "*.cmd", "*.ps1", "*.json", "*.md", "*.txt", "*.html", "*.bat"):
    扫的 += glob.glob(os.path.join(根, 模式))
for 子 in ("影匠", "B站", "工具"):
    扫的 += glob.glob(os.path.join(根, 子, "**", "*.py"), recursive=True)
    扫的 += glob.glob(os.path.join(根, 子, "**", "*.json"), recursive=True)
    扫的 += glob.glob(os.path.join(根, 子, "**", "*.md"), recursive=True)
扫的 = sorted(set(p for p in 扫的 if os.path.isfile(p)))

print("扫 %d 个文件（脚本 + 文档 + 配置）\n" % len(扫的))

文 = {}
for p in 扫的:
    try:
        文[p] = open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        pass

总影响 = 0
for 旧, 新 in 计划:
    形 = ["D:\\DSHworkspace\\" + 旧, "D:/DSHworkspace/" + 旧,
          "DSHworkspace\\" + 旧, "DSHworkspace/" + 旧]
    hit = collections.Counter()
    for p, t in 文.items():
        n = sum(t.count(f) for f in 形)
        if n:
            hit[os.path.relpath(p, 根)] = n
    总 = sum(hit.values())
    总影响 += 总
    print("%-12s → %-20s 被 %2d 个文件引用 %3d 处" % (旧, 新, len(hit), 总))
    for k, v in list(hit.most_common(6)):
        print("        %-56s %d 处" % (k, v))
    if len(hit) > 6:
        print("        … 还有 %d 个文件" % (len(hit) - 6))
    print("")

print("★ 合计要改 %d 处" % 总影响)
