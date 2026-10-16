# -*- coding: utf-8 -*-
"""盘账 —— 准确地量「到底占了多少」，并识别硬链重复计数。

为什么要这个：只用 Get-ChildItem 的 Length 求和，**硬链会被每条路径各算一次**。
同一个 inode 被 os.link 到 2 个地方，磁盘上只占 1 份，但求和会算成 2 份。
判据：st_nlink > 1 的文件，只在「第一次遇到它的 (dev, ino)」时计入。

只读，不动任何文件。
"""
import os, sys, collections

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
ROOT = r"D:\DSHworkspace"

def 量(目录):
    """返回 (逻辑字节, 去重字节, 文件数, 硬链文件数)"""
    逻辑 = 去重 = 文件数 = 硬链数 = 0
    见过 = set()
    for dp, dns, fns in os.walk(目录):
        dns[:] = [d for d in dns if not d.startswith('$')]
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            文件数 += 1
            逻辑 += st.st_size
            if st.st_nlink > 1:
                硬链数 += 1
                k = (st.st_dev, st.st_ino)
                if k in 见过:
                    continue           # 这份数据已经在别处算过了
                见过.add(k)
            去重 += st.st_size
    return 逻辑, 去重, 文件数, 硬链数

def GB(n):
    return n / 2**30

def 报(名, 目录, 缩进=""):
    if not os.path.isdir(目录):
        print(f"{缩进}{名:<28} —— 不存在")
        return None
    l, d, c, h = 量(目录)
    差 = GB(l - d)
    尾巴 = f"  硬链 {h} 个，重复计 {差:.2f} GiB" if h else ""
    print(f"{缩进}{名:<28} {GB(l):>9.2f} GiB  去重后 {GB(d):>9.2f} GiB  {c:>7,} 文件{尾巴}")
    return d

print("=" * 96)
print("一、D:\\DSHworkspace 下各层（GiB，第二列才是真实占用）")
print("=" * 96)
总逻辑 = 总去重 = 0
for 名 in sorted(os.listdir(ROOT)):
    p = os.path.join(ROOT, 名)
    if not os.path.isdir(p) or 名.startswith('.'):
        continue
    r = 报(名, p)
    if r is None:
        continue
    # 总账单独再量一次（因为跨目录的硬链要合并去重）
print()

print("=" * 96)
print("二、网盘 内部拆解")
print("=" * 96)
WD = os.path.join(ROOT, "网盘")
if os.path.isdir(WD):
    for 名 in sorted(os.listdir(WD)):
        p = os.path.join(WD, 名)
        if os.path.isdir(p):
            报(名, p, "  ")
        else:
            print(f"  [文件] {名}")
print()

print("=" * 96)
print("三、整机（C / D 两盘）")
print("=" * 96)
import shutil
for 盘 in ("C:\\", "D:\\"):
    try:
        t, u, f = shutil.disk_usage(盘)
        print(f"  {盘}  总 {GB(t):>7.1f} GiB   已用 {GB(u):>7.1f} GiB   可用 {GB(f):>7.1f} GiB")
    except OSError as e:
        print(f"  {盘}  取不到: {e}")
