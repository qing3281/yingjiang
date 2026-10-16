# -*- coding: utf-8 -*-
"""验 `_出子镜.py` 新加的 `--第4段I2VA` 到底改了什么 —— 不提交任何任务，只看表。

判据（不是我说了算）：
  1. 不加这个开关时，第 4 小段的末路 = `末帧\\末_格N.png`，128 段里 0 段是 I2VA
  2. 加上之后，**每一个第 4 小段的末路都变成空字符串**（= I2VA），其余 96 段一个字不变
  3. 段数还是 128（不能把格32 的第 4 段弄丢或弄重）
"""
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location(
    "chuzijing", r"D:\DSHworkspace\影匠\_出子镜.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
表 = M.子镜表(目)
print("不加开关：段数 %d" % len(表))
甲 = len(表)
乙 = len([x for x in 表 if x[3] == ""])
print("  末路为空（I2VA）的段数：%d　（应该只有格32 的第 4 段 = 1）" % 乙)

表2 = [(号, 段, 首路, ("" if 段 == 4 else 末路)) for (号, 段, 首路, 末路) in 表]
print("加开关：段数 %d" % len(表2))
丙 = len([x for x in 表2 if x[3] == ""])
print("  末路为空（I2VA）的段数：%d　（应该是 32）" % 丙)

夫 = [(a[0], a[1]) for a in 表] != [(a[0], a[1]) for a in 表2]
print("  段清单变了没有：%s　（必须是 False）" % 夫)
没变 = [i for i in range(len(表))
        if 表[i][0] != 表2[i][0] or 表[i][1] != 表2[i][1] or 表[i][2] != 表2[i][2]]
print("  除了末路以外任何一项被改动的段：%d 个　（必须是 0）" % len(没变))
仅4 = [i for i in range(len(表)) if 表[i][3] != 表2[i][3] and 表[i][1] != 4]
print("  动到了「不是第 4 小段」的段：%d 个　（必须是 0）" % len(仅4))

好 = (甲 == 128 and 乙 == 1 and len(表2) == 128 and 丙 == 32
      and not 夫 and not 没变 and not 仅4)
print()
print("★ %s" % ("四条判据全过" if 好 else "★ 有判据没过 —— 不许拿这个去出片"))
sys.exit(0 if 好 else 1)
