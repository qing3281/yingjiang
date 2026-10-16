# -*- coding: utf-8 -*-
"""全局查：网盘里每个大文件（>1 GiB）住在哪些路径、几个 inode、nlink 多少。

这是决定「还能再硬链省多少」的唯一可靠判据 —— 只看两个目录会漏掉第三个副本。
"""
import os
import sys

根 = sys.argv[1] if len(sys.argv) > 1 else r"D:\DSHworkspace\素材\网盘"
下限 = 1 << 30

按名 = {}
for dp, dn, fn in os.walk(根):
    for f in fn:
        p = os.path.join(dp, f)
        try:
            s = os.stat(p)
        except OSError:
            continue
        if s.st_size >= 下限:
            按名.setdefault(f, []).append((p, s))

print(f"{根} 下 >1 GiB 的文件共 {sum(len(v) for v in 按名.values())} 个，{len(按名)} 种名字\n")

可省 = 0
重复的名字 = []
for n, v in sorted(按名.items(), key=lambda kv: -kv[1][0][1].st_size):
    if len(v) < 2:
        continue
    块 = {}
    for p, s in v:
        块.setdefault((s.st_dev, s.st_ino), []).append(p)
    if len(块) == 1:
        continue          # 已经全是同一块
    重复的名字.append((n, v, 块))
    独立 = len(块)
    省 = v[0][1].st_size * (独立 - 1) / 2**30
    可省 += 省

for n, v, 块 in 重复的名字:
    print(f"■ {n}   {v[0][1].st_size / 2**30:.2f} GiB × {len(v)} 份，{len(块)} 块独立数据")
    for k, ps in 块.items():
        print(f"    ino={k[1]}  nlink={os.stat(ps[0]).st_nlink}  ({len(ps)} 个路径)")
        for p in ps:
            print(f"        {os.path.relpath(p, 根)}")

print(f"\n★ 还能再硬链省下：{可省:.2f} GiB")
