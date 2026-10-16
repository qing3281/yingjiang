# -*- coding: utf-8 -*-
"""网盘四个整合包：每个包里的东西，本机别处有没有？没有的才是「留着有用」。

用户问：「那些副本干嘛的，没用就删」。
所以要回答两件事：
  1. 这些副本各自是什么（谁是谁的副本、谁是超集）
  2. 每一份数据在本机有没有第二个来源 —— 有，删了不丢东西；没有，删了就真没了
"""
import os
import sys

下载 = r"D:\DSHworkspace\素材\网盘\下载"
已装根 = [
    r"D:\Comfy-Desktop\ComfyUI-Shared\models",
    r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models",
]
取出 = r"D:\DSHworkspace\影匠\_网盘整理\取出"

包 = {
    "3.九月整合包（minimax+qwen2.1+自由姿势)": os.path.join(下载, "3.九月整合包（minimax+qwen2.1+自由姿势)"),
    "【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）": os.path.join(下载, "【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）"),
    "1.MINIMAX打斗专篇": os.path.join(下载, "1.MINIMAX打斗专篇"),
    "ComfyUI-aki": os.path.join(下载, "ComfyUI-aki"),
    "6.MINIMAX打戏V2版+配套整合包": os.path.join(下载, "6.MINIMAX打戏V2版+配套整合包"),
}

# 1) 本机已装的大模型（按名字 -> 总大小）
已装 = {}
for r in 已装根:
    if not os.path.isdir(r):
        continue
    for dp, dn, fn in os.walk(r):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                s = os.stat(p).st_size
            except OSError:
                continue
            if s >= 1 << 30:
                已装.setdefault(f, []).append((p, s))

print(f"本机已装 >1 GiB 模型：{len(已装)} 种\n")

# 2) 取出目录里已落地的文件（按名字）
落了 = set()
for dp, dn, fn in os.walk(取出):
    for f in fn:
        落了.add(f)
print(f"已取出到 _网盘整理\\取出 的文件名：{len(落了)} 种\n")

# 3) 逐包分析
print("=" * 100)
总数 = {}
for 名, 根 in 包.items():
    if not os.path.isdir(根):
        print(f"\n■ {名}　—— 目录不在")
        continue
    文件 = []
    for dp, dn, fn in os.walk(根):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                s = os.stat(p).st_size
            except OSError:
                continue
            文件.append((f, s, p))
    if not 文件:
        print(f"\n■ {名}　—— 空目录")
        continue
    总 = sum(x[1] for x in 文件)
    大 = [x for x in 文件 if x[1] >= 1 << 30]
    在别处 = [x for x in 大 if x[0] in 已装]
    只在这 = [x for x in 大 if x[0] not in 已装]
    总数[名] = (len(文件), 总, 大, 在别处, 只在这)
    print(f"\n■ {名}")
    print(f"   {len(文件)} 文件 / {总 / 2**30:.2f} GiB　其中 >1 GiB 的 {len(大)} 个")
    print(f"   ├ 本机已装同名同大小：{len(在别处)} 个 / {sum(x[1] for x in 在别处) / 2**30:.2f} GiB")
    for f, s, p in 在别处[:8]:
        print(f"   │   {s / 2**30:8.2f} GiB  {f}")
    if len(在别处) > 8:
        print(f"   │   …另有 {len(在别处) - 8} 个")
    print(f"   └ 只在这个包里有：{len(只在这)} 个 / {sum(x[1] for x in 只在这) / 2**30:.2f} GiB")
    for f, s, p in 只在这:
        print(f"       {s / 2**30:8.2f} GiB  {f}")

# 4) 嵌套关系
print("\n" + "=" * 100)
print("嵌套关系（谁是另一个的超集）：")
for 名, 根 in 包.items():
    if not os.path.isdir(根):
        continue
    for dp, dn, fn in os.walk(根):
        if dp == 根:
            continue
        内层 = os.path.basename(dp)
        for 别的名, 别的根 in 包.items():
            if 别的名 != 名 and 内层 == 别的名:
                n = sum(len(f) for _, _, f in os.walk(dp))
                sz = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(dp) for f in fs)
                print(f"  {名}\n    └ 里面套了一份【{别的名}】　{n} 文件 / {sz / 2**30:.2f} GiB")

# 5) 物理占用（硬链后）
print("\n" + "=" * 100)
print("硬链之后的真实物理占用：")
for 名, 根 in 包.items():
    if not os.path.isdir(根):
        continue
    seen = {}
    for dp, dn, fn in os.walk(根):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                s = os.stat(p)
                seen.setdefault((s.st_dev, s.st_ino), s.st_size)
            except OSError:
                pass
    print(f"  {名}：{len(seen)} 块独立数据 / {sum(seen.values()) / 2**30:.2f} GiB")
