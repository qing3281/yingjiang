# -*- coding: utf-8 -*-
"""看清「打斗专篇」和「WF 纯净版整合包」到底是不是同一份东西 —— 决定能不能删。"""
import hashlib
import os

下载 = r"D:\DSHworkspace\素材\网盘\下载"
A = os.path.join(下载, "1.MINIMAX打斗专篇")
B = os.path.join(下载, "【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）")


def 列(根):
    out = []
    for dp, dn, fn in os.walk(根):
        for f in fn:
            p = os.path.join(dp, f)
            out.append((os.path.relpath(p, 根).replace("\\", "/"), os.path.getsize(p), p))
    return sorted(out)


def 印(名, 根):
    a = 列(根)
    print(f"\n=== {名} ===   {len(a)} 文件 / {sum(x[1] for x in a) / 2**30:.2f} GiB")
    for rel, sz, p in a:
        print(f"  {sz / 2**30:9.2f} GiB  {rel}")
    return a


甲 = 印("1.MINIMAX打斗专篇", A)
乙 = 印("【Work-Fisher】纯净版整合包", B)

# 按文件名（basename）配对，比大小 + 抽样哈希
print("\n=== 配对比较（按文件名） ===")
by甲 = {}
for rel, sz, p in 甲:
    by甲.setdefault(os.path.basename(rel), []).append((rel, sz, p))
by乙 = {}
for rel, sz, p in 乙:
    by乙.setdefault(os.path.basename(rel), []).append((rel, sz, p))

共同 = sorted(set(by甲) & set(by乙))
只在甲 = sorted(set(by甲) - set(by乙))
只在乙 = sorted(set(by乙) - set(by甲))

print(f"  同名文件 {len(共同)} 个　只在打斗专篇有 {len(只在甲)} 个　只在 WF 有 {len(只在乙)} 个")

相同 = 不同 = 0
for n in 共同:
    a = by甲[n][0]
    b = by乙[n][0]
    if a[1] != b[1]:
        print(f"  ✗ 大小不同：{n}  {a[1]} vs {b[1]}")
        不同 += 1
        continue
    with open(a[2], "rb") as f:
        ha = hashlib.sha256(f.read(2 * 1048576)).hexdigest()[:16]
    with open(b[2], "rb") as f:
        hb = hashlib.sha256(f.read(2 * 1048576)).hexdigest()[:16]
    if ha == hb:
        相同 += 1
    else:
        print(f"  ✗ 内容不同：{n}  {ha} vs {hb}")
        不同 += 1

print(f"  → 抽样哈希一致 {相同}　不一致 {不同}")
if 只在甲:
    print("\n  只在「打斗专篇」里的：")
    for n in 只在甲:
        for rel, sz, p in by甲[n]:
            print(f"    {sz / 2**30:8.2f} GiB  {rel}")
if 只在乙:
    print("\n  只在「WF 纯净版」里的：")
    for n in 只在乙:
        for rel, sz, p in by乙[n]:
            print(f"    {sz / 2**30:8.2f} GiB  {rel}")

# ★ 决定性判据：两个目录下所有文件加起来，有几块真正独立的数据
print("\n=== ★ 真正占了多少物理空间（按 (dev,ino) 去重） ===")
for 名, 根 in (("打斗专篇", A), ("WF 纯净版", B)):
    seen = {}
    for dp, dn, fn in os.walk(根):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                s = os.stat(p)
                seen.setdefault((s.st_dev, s.st_ino), s.st_size)
            except OSError:
                pass
    逻辑 = sum(sz for _, sz, _ in 列(根))
    物理 = sum(seen.values())
    print(f"  {名}：逻辑 {逻辑 / 2**30:.2f} GiB　物理 {物理 / 2**30:.2f} GiB　独立数据块 {len(seen)} 个")
