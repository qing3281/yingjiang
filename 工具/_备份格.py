# -*- coding: utf-8 -*-
r"""把一部戏里指定几格的**首帧**和**已有的段**复制到备份目录。

★ 为什么要专门写一个，而不是 `shutil.copy2(源, 目录)`：
  上一批我就是这么写的 —— `copy2` 的目标**不带文件名**时，它会把文件复制成
  **一个叫那个目录名的文件**。七个段互相覆盖，最后只剩一个、还丢了扩展名。
  → **目标路径必须 `os.path.join(备, 文件名)`**；复制完还要**数一遍个数对不对**。

★ 还有一条：`首帧` 的真实文件名是 `01_格5.png`（**不补零**），写 `01_格05.png` 会找不到。

用法：python _备份格.py 觉醒 _起手式2前 8 9 22 29 42 44 56 58
"""
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

戏 = sys.argv[1] if len(sys.argv) > 1 else "觉醒"
标 = sys.argv[2] if len(sys.argv) > 2 else "备份"
号们 = [int(x) for x in sys.argv[3:]]

根 = rf"D:\DSHworkspace\影匠\作品\{戏}"
备 = os.path.join(根, f"_{标}_{time.strftime('%Y%m%d-%H%M%S')}")
os.makedirs(os.path.join(备, "段"), exist_ok=True)

要的数 = 0
抄的数 = 0

for 号 in 号们:
    首 = os.path.join(根, f"01_格{号}.png")
    if os.path.isfile(首):
        要的数 += 1
        目 = os.path.join(备, os.path.basename(首))
        shutil.copy2(首, 目)
        抄的数 += 1
        print(f"  · 首帧 {os.path.basename(首)} → {os.path.getsize(目):,} B")

for 号 in 号们:
    夹 = os.path.join(根, "段")
    if not os.path.isdir(夹):
        continue
    同 = sorted(c for c in os.listdir(夹)
                if c.startswith(f"格{号}_") and c.lower().endswith(".mp4"))
    for c in 同:
        要的数 += 1
        目 = os.path.join(备, "段", c)          # ★ 必须带文件名
        shutil.copy2(os.path.join(夹, c), 目)
        抄的数 += 1
        print(f"  · 段   {c} → {os.path.getsize(目):,} B")

print(f"\n  备份目录 {备}")
print(f"  要抄 {要的数} 个，抄了 {抄的数} 个 —— " + ("✓ 数目对上了" if 要的数 == 抄的数 else "✗ 数目对不上！"))
sys.exit(0 if 要的数 == 抄的数 else 1)
