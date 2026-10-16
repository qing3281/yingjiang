# -*- coding: utf-8 -*-
"""列出「删了真能省」的文件明细，供用户逐项核对。

规矩（用户 m13285：「这个删除之前要给我核对一下」）：
  本脚本**只读**，一个字节都不删。它的产物是一份清单，不是一次操作。
"""
import os
import subprocess
from collections import defaultdict

根 = r"D:\DSHworkspace\素材\网盘"
扫 = [os.path.join(根, "下载"), os.path.join(根, "HF"),
      r"D:\Comfy-Desktop\ComfyUI-Shared\models"]
门槛 = 100 * 1024 * 1024       # 只看 >100 MB

inode = defaultdict(list)
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
            if st.st_size >= 门槛:
                inode[(st.st_dev, st.st_ino)].append((p, st.st_size))


def 包名(p):
    r = os.path.relpath(p, 根)
    段 = r.split(os.sep)
    if 段[0] == "下载":
        return 段[1] if len(段) > 1 else "下载"
    if 段[0] == "HF":
        return "HF"
    return "（本机 ComfyUI）"


# 每个包：独有文件（inode 只出现在这个包）
独有 = defaultdict(list)
for (dev, ino), 们 in inode.items():
    包们 = sorted({包名(p) for p, _ in 们})
    if len(包们) == 1:
        独有[包们[0]].append(们[0])

print(f"扫描 {len(inode)} 份 >100MB 的数据\n")
for b in sorted(独有, key=lambda x: -sum(s for _, s in 独有[x])):
    行 = sorted(独有[b], key=lambda x: -x[1])
    合 = sum(s for _, s in 行)
    print(f"▌ {b}　独有 {合/2**30:.2f} GiB / {len(行)} 个文件")
    for p, s in 行[:14]:
        短 = p.replace(根 + os.sep, "").replace(
            r"D:\Comfy-Desktop\ComfyUI-Shared\models" + os.sep, "models\\")
        print(f"     {s/2**30:>7.2f}G  {短}")
    if len(行) > 14:
        剩 = sum(s for _, s in 行[14:])
        print(f"     … 另 {len(行)-14} 个小的，合 {剩/2**30:.2f} GiB")
    print()
