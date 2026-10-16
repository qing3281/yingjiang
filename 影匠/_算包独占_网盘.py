# -*- coding: utf-8 -*-
"""算清四个整合包各占多少**独有**空间（按 inode 去重）。

用途：用户问「那些副本干嘛的，没用就删」。
结论要能回答：删掉某个包，**真正**能释放多少字节（而不是它的名义大小）。
一个文件只要在别处还有一个硬链（nlink>1 且同 inode 在别的包/别处出现过），
删它就不释放空间。
"""
import os
import sys
from collections import defaultdict

根 = r"D:\DSHworkspace\素材\网盘"
扫 = [os.path.join(根, "下载"), os.path.join(根, "HF")]

# inode -> [(路径, 大小)]
inode = defaultdict(list)
全部 = []
for 顶 in 扫:
    if not os.path.isdir(顶):
        continue
    for 目录, _, 文件们 in os.walk(顶):
        for f in 文件们:
            p = os.path.join(目录, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            inode[(st.st_dev, st.st_ino)].append((p, st.st_size))
            全部.append((p, st.st_size, st.st_dev, st.st_ino))

print(f"扫到 {len(全部)} 个文件（含硬链），去重后 {len(inode)} 份数据\n")


def 顶层(p):
    r = os.path.relpath(p, 根)
    段 = r.split(os.sep)
    return os.sep.join(段[:2]) if len(段) > 1 else 段[0]


# 每个顶层目录：名义大小 / 独有大小
名义 = defaultdict(int)
独有 = defaultdict(int)
份数 = defaultdict(int)
for (dev, ino), 们 in inode.items():
    大小 = 们[0][1]
    位 = sorted({顶层(p) for p, _ in 们})
    for b in 位:
        名义[b] += 大小
        份数[b] += 1
    if len(位) == 1:
        独有[位[0]] += 大小

print(f"{'目录':<52}{'名义':>12}{'独有':>12}{'占比':>8}")
print("-" * 86)
for b in sorted(名义, key=lambda x: -名义[x]):
    n, u = 名义[b], 独有[b]
    print(f"{b:<52}{n/2**30:>10.2f}G{u/2**30:>10.2f}G{u/max(n,1)*100:>7.1f}%")
print("-" * 86)
print(f"{'合计':<52}{sum(名义.values())/2**30:>10.2f}G"
      f"{sum(独有.values())/2**30:>10.2f}G")

# 跨目录重复的总量
跨 = 0
for (dev, ino), 们 in inode.items():
    if len({顶层(p) for p, _ in 们}) > 1:
        跨 += 们[0][1] * (len(们) - 1)
print(f"\n跨目录重复、已经靠硬链省掉的：{跨/2**30:.2f} GiB")

# 还能再省多少（同 inode 多份且都还在）
再省 = sum(们[0][1] * (len(们) - 1) for 们 in inode.values() if len(们) > 1)
print(f"同 inode 仍有多份的：{再省/2**30:.2f} GiB（= 0 说明已经一处不重复）")
多份 = [(dev, ino, 们) for (dev, ino), 们 in inode.items() if len(们) > 1]
if 多份:
    for dev, ino, 们 in 多份[:10]:
        print(f"  ×{len(们)}  {们[0][1]/2**30:.2f}G  {os.path.basename(们[0][0])}")
