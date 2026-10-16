# -*- coding: utf-8 -*-
"""_盘点.py —— 只读。把 D:\\DSHworkspace 摊开：顶层有什么、各占多大、根目录那堆
`_*` 临时文件都是什么时候的什么东西、有哪些明确是垃圾（pycache/part/0 字节）。

出这张表是为了**删之前先看见**：上一次「数少了」的虚惊就是没先看代码。
"""
import os
import sys
import time
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
垃圾名 = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def 大小(p):
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


def 人(n):
    for u in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return "%.1f%s" % (n, u)
        n /= 1024.0
    return "%.1fP" % n


顶层 = []
for 名 in sorted(os.listdir(根)):
    p = os.path.join(根, 名)
    顶层.append((大小(p), os.path.isdir(p), 名, os.path.getmtime(p)))

顶层.sort(reverse=True)
总 = sum(t[0] for t in 顶层)
print("D:\\DSHworkspace 顶层 %d 项，合计 %s" % (len(顶层), 人(总)))
print("")
print("  %-10s %-4s %-46s %s" % ("大小", "类型", "名字", "mtime"))
for s, d, n, m in 顶层:
    print("  %-10s %-4s %-46s %s" % (人(s), "目录" if d else "文件", n[:46],
                                     time.strftime("%m-%d %H:%M", time.localtime(m))))

# 根目录里 `_*` 的文件按扩展名分类
print("")
print("── 根目录 `_*` 文件按后缀 ──")
类 = defaultdict(lambda: [0, 0])
for 名 in os.listdir(根):
    p = os.path.join(根, 名)
    if not os.path.isfile(p) or not 名.startswith("_"):
        continue
    e = os.path.splitext(名)[1].lower() or "(无后缀)"
    类[e][0] += 1
    类[e][1] += os.path.getsize(p)
for e, (c, s) in sorted(类.items(), key=lambda x: -x[1][0]):
    print("  %-8s %4d 个　%s" % (e, c, 人(s)))
print("  合计 %d 个" % sum(c for c, _ in 类.values()))

# 真垃圾
print("")
print("── 明确是垃圾的 ──")
罐 = defaultdict(lambda: [0, 0])
例子 = defaultdict(list)
for 底, 目们, 文们 in os.walk(根):
    for d in list(目们):
        if d in 垃圾名:
            罐["__pycache__ 等缓存目录"][0] += 1
            罐["__pycache__ 等缓存目录"][1] += 大小(os.path.join(底, d))
            if len(例子["__pycache__ 等缓存目录"]) < 4:
                例子["__pycache__ 等缓存目录"].append(os.path.join(底, d))
    for f in 文们:
        p = os.path.join(底, f)
        e = os.path.splitext(f)[1].lower()
        try:
            z = os.path.getsize(p)
        except OSError:
            continue
        if e in (".part", ".pyc", ".tmp", ".crdownload"):
            罐["断点/编译临时 (.part/.pyc/.tmp)"][0] += 1
            罐["断点/编译临时 (.part/.pyc/.tmp)"][1] += z
            if len(例子["断点/编译临时 (.part/.pyc/.tmp)"]) < 4:
                例子["断点/编译临时 (.part/.pyc/.tmp)"].append(p)
        elif z == 0:
            罐["0 字节文件"][0] += 1
            罐["0 字节文件"][1] += 0
            if len(例子["0 字节文件"]) < 6:
                例子["0 字节文件"].append(p)
for k, (c, s) in sorted(罐.items(), key=lambda x: -x[1][1]):
    print("  %-32s %4d 个　%s" % (k, c, 人(s)))
    for x in 例子[k]:
        print("        %s" % x)

# 定妆照
print("")
print("── 定妆照相关 ──")
for 底, 目们, 文们 in os.walk(根):
    if "定妆" in 底 or any("定妆" in f for f in 文们):
        n = len(文们)
        if n:
            print("  %-70s %3d 个　%s" % (底[:70], n, 人(大小(底))))
