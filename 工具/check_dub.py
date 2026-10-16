# -*- coding: utf-8 -*-
"""试配一句，把「配 32 句」这条路先跑通一遍。

为什么要单独试一句：`_守成片2.py` 是一整条无人值守的链 ——
等 128 段 → 配音 → 接片 → 验片 → 发信。要是配音那步跑不通，它会卡在第一站，
我早上看到的就只是一个停在 ① 的日志。**一句的成本是几秒，整条链卡住的成本是一晚上。**

判据（不是我嘴上说的「成功」）：
  1. 产出文件的头 4 个字节是 `RIFF`（真 WAV；配音.py 里记着 SaveAudio 只存 FLAC，
     必须按魔数认，见 配音.py 的 转真WAV）
  2. 秒数 > 0
  3. 音色来源是「角色映射表」而不是「模糊匹配」—— 降级是**不报错**的，只能这样看
"""
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
sys.path.insert(0, r"D:\DSHworkspace\影匠\作品\楚子航")

import 配音
from _台词表 import 台词表

出 = r"D:\DSHworkspace\_试配音"
os.makedirs(出, exist_ok=True)

# 挑一句真台词，用 角色 走映射表（不是用 音色 直接点名 —— 要验的正是映射这条路）
号 = 2
说话人, 词, 来源 = 台词表[号]
输入 = [{"序号": 号, "台词": 词, "角色": 说话人}]
print("试配：格%d %s「%s」（原文来源：%s）" % (号, 说话人, 词, 来源))

果 = 配音.批量(输入, 输出目录=出, 保留显存=False, 写字幕=False, 要真WAV=True,
                报=lambda s: print("   " + str(s)))

坏 = 0
for 条 in 果.get("配音", []):
    p = 条.get("路")
    print("  路 = %s" % p)
    print("  秒 = %s　音色 = %s　角色 = %s　来源 = %s"
          % (条.get("秒"), 条.get("音色"), 条.get("角色"), 条.get("音色来源")))
    if 条.get("错"):
        print("  ✗ 错 = %s" % 条["错"]); 坏 += 1
    if not p or not os.path.isfile(p):
        print("  ✗ 文件不在"); 坏 += 1; continue
    头 = open(p, "rb").read(4)
    print("  头 4 字节 = %r　大小 = %d B" % (头, os.path.getsize(p)))
    if 头 != b"RIFF":
        print("  ✗ 不是真 WAV（SaveAudio 会存 FLAC，必须转）"); 坏 += 1
    if not 条.get("秒") or 条["秒"] <= 0:
        print("  ✗ 秒数不对"); 坏 += 1
    源 = str(条.get("音色来源") or "")
    if "映射" not in 源 and "角色" not in 源:
        print("  ✗ 音色来源是「%s」—— 说明角色没命中映射表、降级成模糊匹配了（不报错的坑）" % 源)
        坏 += 1

print("角色解析 =", json.dumps(果.get("角色解析"), ensure_ascii=False))
print("总时长 =", 果.get("总时长"), "秒")
print("=" * 60)
print("结论：%s" % ("✓ 试配这条路通了" if 坏 == 0 else "✗ %d 条没过" % 坏))
sys.exit(1 if 坏 else 0)
