# -*- coding: utf-8 -*-
r"""把 `02-九宫格.md` 里指定几格的 `动作` / `提示词` / `景别` / `光色` 打出来。

为什么需要它：改「起手式」的时候要看**动作和提示词摆在一起**才看得出
「提示词是不是把动作写完的样子画下来了」。分开看是看不出来的。

用法：python _看格.py 11 22 29 32 34 44 54 56 57 58 62 68
      python _看格.py --全            （74 格全打）
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

戏 = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isdigit() else "觉醒"
号们 = [int(x) for x in sys.argv[1:] if x.isdigit()]
路 = rf"D:\DSHworkspace\影匠\作品\{戏}\02-九宫格.md"
原文 = open(路, encoding="utf-8").read()


def 找块(全文, 号):
    m = re.search(rf"\n## 格{号}(?=[^\d])(.*?)(?=\n## |\Z)", 全文, re.S)
    return m.group(1) if m else None


def 要(块, 键):
    m = re.search(rf"[-*]?\s*\**{键}\**\s*[:：]\s*(.+)", 块)
    return m.group(1).strip() if m else ""


def 公共子串长(a, b):
    """最长公共子串长度 —— 词法探针。会漏（换了词但语义还是「已完成」的写法抓不到）。"""
    最好 = 0
    for i in range(len(a)):
        for j in range(i + 最好 + 1, len(a) + 1):
            if a[i:j] in b:
                最好 = j - i
            else:
                break
    return 最好


if "--全" in sys.argv or not 号们:
    号们 = sorted(int(m) for m in re.findall(r"\n## 格(\d+)", 原文))

for 号 in 号们:
    块 = 找块(原文, 号)
    if not 块:
        print(f"  ✗ 格{号} 找不到")
        continue
    动 = 要(块, "动作")
    词 = 要(块, "提示词")
    公 = 公共子串长(动, 词)
    标 = "★ 词法命中" if 公 >= 6 else "  "
    print(f"\n{'=' * 78}\n格{号}  {标}  最长公共子串 {公} 字"
          f"　景别 {要(块, '景别')}　光色 {要(块, '光色')}")
    print(f"  动作：{动}")
    print(f"  提示词：{词}")
