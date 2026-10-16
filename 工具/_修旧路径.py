# -*- coding: utf-8 -*-
"""把两个入口文档里残留的「记忆\\归档\\归档\\」旧嵌套路径改回「记忆\\归档\\」。

背景：`_搬家.py` 把 `_归档` 整个挪进 `记忆\` 时多套了一层（`记忆\归档\归档\`），
`_修归档嵌套.py` 已经把**磁盘上**的平掉了（27 个子项），但 `交接.md` / `目录说明.md`
里**写下来的字符串**还是旧的，`_收尾.py` 一验就报「不在磁盘」。

只改这三处字面替换（长的写在前面）：
  记忆\\归档\\归档\\  →  记忆\\归档\\
同时把 `_归档\\清理清单\\` 这种与「记忆\\归档」拼起来会错的也算进来。
"""
import io
import os
import shutil
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
目标 = [
    os.path.join(根, "交接.md"),
    os.path.join(根, "目录说明.md"),
    os.path.join(根, "AGENTS.md"),
]

替换 = [
    (r"记忆\归档\归档\清理清单", r"记忆\归档\清理清单"),
    (r"记忆\归档\归档\交接历史", r"记忆\归档\交接历史"),
    (r"记忆\归档\归档\_归档总表", r"记忆\归档\_归档总表"),
    (r"记忆\归档\归档\搬家前", r"记忆\归档\搬家前"),
    (r"记忆\归档\归档", r"记忆\归档"),
    ("记忆/归档/归档", "记忆/归档"),
]

戳 = datetime.now().strftime("%Y%m%d-%H%M%S")
总 = 0
for p in 目标:
    if not os.path.isfile(p):
        print(f"· 跳过（不在）{p}")
        continue
    with io.open(p, "r", encoding="utf-8") as f:
        文 = f.read()
    新 = 文
    n = 0
    for a, b in 替换:
        if a in 新:
            k = 新.count(a)
            新 = 新.replace(a, b)
            n += k
    if n == 0:
        print(f"· {os.path.basename(p)}　无需改")
        continue
    shutil.copy2(p, p + ".bak-" + 戳)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(新)
    print(f"✓ {os.path.basename(p)}　改了 {n} 处　{len(文)} → {len(新)} 字节")
    总 += n
print(f"\n合计改 {总} 处")
