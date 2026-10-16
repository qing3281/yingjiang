# -*- coding: utf-8 -*-
"""找「删了能真的省空间」的东西。

关键道理：**硬链的两个路径共用同一份数据。删掉其中一条，磁盘一个字节都不省。**
所以「哪份能删」不能看它占多大，要看**它是不是这份数据的最后一条路径**。

本脚本只读。输出：
  一、网盘\下载 里的大件（>=80 MB），标出它有没有硬链孪生、孪生在哪
  二、按「去掉这些就能省多少」排序的候选清单
"""
import os, sys, collections

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
ROOT = r"D:\DSHworkspace"
网盘 = os.path.join(ROOT, "网盘")
阈值 = 80 * 1024 * 1024

def GB(n):
    return n / 2**30

# 1) 建 inode -> [路径...] 索引（只扫工作区，跨目录才能看出孪生）
print("扫描中……（工作区全扫，可能要一分钟）", flush=True)
ino2paths = collections.defaultdict(list)
size_of = {}
for dp, dns, fns in os.walk(ROOT):
    dns[:] = [d for d in dns if not d.startswith('$')]
    for fn in fns:
        p = os.path.join(dp, fn)
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_nlink > 1:
            ino2paths[(st.st_dev, st.st_ino)].append(p)
            size_of[(st.st_dev, st.st_ino)] = st.st_size

print(f"工作区里有硬链孪生的文件：{len(ino2paths)} 组\n", flush=True)

# 2) 网盘\下载 里的大件
下载 = os.path.join(网盘, "下载")
大件 = []
for dp, dns, fns in os.walk(下载):
    for fn in fns:
        p = os.path.join(dp, fn)
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_size >= 阈值:
            大件.append((st.st_size, p, (st.st_dev, st.st_ino), st.st_nlink))
大件.sort(reverse=True)

print("=" * 100)
print(f"一、网盘\\下载 里 >= 80 MB 的 {len(大件)} 个文件（共 {GB(sum(s for s,_,_,_ in 大件)):.1f} GiB）")
print("=" * 100)
省不到 = 0.0
省得到 = 0.0
for sz, p, k, nl in 大件:
    孪 = [q for q in ino2paths.get(k, []) if os.path.normcase(q) != os.path.normcase(p)]
    if 孪:
        省不到 += sz
        print(f"  {GB(sz):>7.2f} GiB  [删了不省]  {p}")
        for q in 孪[:2]:
            print(f"                       孪生→ {q}")
    else:
        省得到 += sz
        print(f"  {GB(sz):>7.2f} GiB  [删了能省]  {p}")

print()
print("=" * 100)
print("二、结论")
print("=" * 100)
print(f"  删了**不省空间**（别处还有孪生）: {GB(省不到):>7.2f} GiB")
print(f"  删了**能真省**                 : {GB(省得到):>7.2f} GiB")
print()
print("  注意：硬链孪生删掉一条不省空间；要省空间必须**两份都删**，或者两份本来就是同一份。")
print("  所以上面标 [删了不省] 的那些，删它只是「少一个入口」，磁盘不会变大。")
