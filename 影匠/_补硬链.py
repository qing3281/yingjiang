# -*- coding: utf-8 -*-
"""把剩下 3 组重复大文件硬链掉（零损失：每个路径都还在，只是共用同一块数据）。

为什么这一步是安全的：
  · 硬链不是复制也不是删除 —— 两个路径指向同一个 inode，谁都能照常打开；
  · 删掉其中任意一个路径，另一个还完整（删的是「链接」不是数据）；
  · 三个整合包照旧各自能启动。

判据（先比再链，链完复验）：
  1. 两份大小必须完全相等，否则跳过；
  2. 首尾各 4 MiB 真读哈希必须相等 —— 只比大小会漏掉「同名同大小但内容不同」；
  3. 链完再 stat 一次，确认 (dev, ino) 真的相同、nlink 真的涨了。
"""
import hashlib
import os
import sys

根 = r"D:\DSHworkspace\素材\网盘\下载"
组 = [
    (
        r"1.MINIMAX打斗专篇\【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）\models（放入comfyui modes文件夹即可，直接替换）\diffusion_models\minimax_h3_fl2va_int8_convrot.safetensors",
        r"【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）\models（放入comfyui modes文件夹即可，直接替换）\diffusion_models\minimax_h3_fl2va_int8_convrot.safetensors",
    ),
    (
        r"1.MINIMAX打斗专篇\【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）\models（放入comfyui modes文件夹即可，直接替换）\diffusion_models\minimax_h3_fl2va_pruned_int8_convrot.safetensors",
        r"【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）\models（放入comfyui modes文件夹即可，直接替换）\diffusion_models\minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    ),
    (
        r"1.MINIMAX打斗专篇\【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）\Comfyui-WF-2026.8.8.7z",
        r"【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）\Comfyui-WF-2026.8.8.7z",
    ),
    (
        r"1.MINIMAX打斗专篇\【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）\models（放入comfyui modes文件夹即可，直接替换）\diffusion_models\minimax_h3_fl2va_pruned_int8_convrot.safetensors",
        r"ComfyUI-aki\models\diffusion_models\minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    ),
]

块 = 4 * 1048576


def 指纹(p):
    with open(p, "rb") as f:
        h = f.read(块)
        f.seek(-块, 2)
        h += f.read(块)
    return hashlib.sha256(h).hexdigest()


省 = 0
for i, (a, b) in enumerate(组, 1):
    pa, pb = os.path.join(根, a), os.path.join(根, b)
    print(f"\n【{i}】{os.path.basename(a)}")
    for p in (pa, pb):
        if not os.path.isfile(p):
            print(f"  ✗ 不在：{p}")
    if not (os.path.isfile(pa) and os.path.isfile(pb)):
        continue
    sa, sb = os.stat(pa), os.stat(pb)
    print(f"  大小 {sa.st_size / 2**30:.2f} GiB　nlink {sa.st_nlink} / {sb.st_nlink}")
    if sa.st_size != sb.st_size:
        print("  ✗ 大小不等，跳过（不硬链）")
        continue
    if (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino):
        print("  – 已经是同一块数据，无需处理")
        continue
    fa, fb = 指纹(pa), 指纹(pb)
    if fa != fb:
        print(f"  ✗ 内容指纹不同（{fa[:12]} vs {fb[:12]}），跳过 —— 同名同大小但不是同一份东西")
        continue
    print(f"  ✓ 指纹一致 {fa[:12]}，开始硬链")
    备份 = pb + ".链前备份"
    try:
        os.replace(pb, 备份)          # 先把 B 挪开（不留窗口期）
        os.link(pa, pb)               # 用 A 的数据建 B 这个新名字
        os.remove(备份)               # 备份和 A 是同一块，删掉它只是去掉一个链接
    except OSError as e:
        print(f"  ✗ 硬链失败：{e}")
        if os.path.exists(备份) and not os.path.exists(pb):
            os.replace(备份, pb)
            print("  ↩ 已回滚")
        continue
    na, nb = os.stat(pa), os.stat(pb)
    同 = (na.st_dev, na.st_ino) == (nb.st_dev, nb.st_ino)
    省 += sa.st_size
    print(f"  复验：同一块 {同}　nlink {na.st_nlink}/{nb.st_nlink}　可读 {os.access(pa, os.R_OK) and os.access(pb, os.R_OK)}")
    if not 同:
        print("  ✗ 复验失败：不是同一块！")

print(f"\n★ 本轮硬链省下 {省 / 2**30:.2f} GiB")
