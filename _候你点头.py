# -*- coding: utf-8 -*-
r"""`_待你点头.md` —— 攒着等你拍板的事，一件事一行。

─ 为什么要这个东西 ───────────────────────────────────────────
用户把同一句话说了 **四次**：

    10-13 00:54  「正式生成前必须把内容给我审核」
    10-13 01:02  「先审核再生成」
    10-13 18:47  「必要时先给他看」
    台账 #13/#14  两条一直挂着 🟡「没形成固定动作」

**说了四遍还是没成为动作，说明缺的不是记性，是位置。**
所以我给它一个固定的位置：

  · 桌面「验收」那一页上有一块 `待你点头`
  · `_开工.py` 每次开工报「**欠你 N 个点头**」
  · `_候你点头.py` 负责增删查

**判据**（`_找复发.py` 已把这病收进词表）：
**凡是「要花钱 / 花机器时间 / 改已有产物」而用户没点过头的 —— 必须先出现在这个表里。**
自己觉得「这事很小不用问」就是又犯了。

用法：
    python _候你点头.py                     # 列出来
    python _候你点头.py --加 "标题" "要花多少" "为什么要你点头"
    python _候你点头.py --点头 3             # 标成已点头
    python _候你点头.py --撤 3               # 撤回（不做了）
"""
import argparse
import io
import os
import re
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

根 = os.path.dirname(os.path.abspath(__file__))
路 = os.path.join(根, "_待你点头.md")

头 = """# 待你点头

> 用户说过的：「**正式生成前必须把内容给我审核**」（10-13 00:54）、「**先审核再生成**」（01:02）、
> 「必要的时候**先给他看**」（18:47）。说了四遍。
>
> **这张表就是那个动作。** 凡是「要花机器时间 / 花 token / 改已有产物」而你没点过头的，
> 都应该先出现在这里 —— **不许我自己觉得「这事太小不用问」。**
>
> 状态：⬜ 等你点头　✅ 你已点头　✖ 撤了

| # | 要做什么 | 要花多少 | 为什么得你点头 | 从什么时候开始等 | 状态 |
|---|---|---|---|---|---|
"""


def 读():
    if not os.path.exists(路):
        return []
    行 = []
    for 线 in io.open(路, encoding="utf-8").read().splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|(.+)\|\s*$", 线)
        if not m:
            continue
        格 = [x.strip() for x in m.group(2).split("|")]
        if len(格) < 5:
            continue
        行.append({"号": int(m.group(1)), "事": 格[0], "花": 格[1],
                   "为什么": 格[2], "等": 格[3], "状": 格[4]})
    return 行


def 写(行):
    with io.open(路, "w", encoding="utf-8", newline="\n") as f:
        f.write(头)
        for r in 行:
            f.write(f"| {r['号']} | {r['事']} | {r['花']} | {r['为什么']} | {r['等']} | {r['状']} |\n")


参 = argparse.ArgumentParser()
参.add_argument("--加", nargs=3, metavar=("标题", "花多少", "为什么要点头"))
参.add_argument("--点头", type=int)
参.add_argument("--撤", type=int)
参.add_argument("--清已办", action="store_true")
参 = 参.parse_args()

行 = 读()

if 参.加:
    事, 花, 为 = 参.加
    号 = max([r["号"] for r in 行], default=0) + 1
    行.append({"号": 号, "事": 事, "花": 花, "为什么": 为,
               "等": datetime.now().strftime("%m-%d %H:%M"), "状": "⬜ 等你点头"})
    写(行)
    print(f"  ✓ 加了第 {号} 条：{事}")

elif 参.点头 or 参.撤:
    号 = 参.点头 or 参.撤
    找 = [r for r in 行 if r["号"] == 号]
    if not 找:
        print(f"  ✗ 没有第 {号} 条")
        sys.exit(1)
    找[0]["状"] = "✅ 你已点头" if 参.点头 else "✖ 撤了"
    写(行)
    print(f"  ✓ 第 {号} 条 → {找[0]['状']}")

elif 参.清已办:
    前 = len(行)
    行 = [r for r in 行 if r["状"].startswith("⬜")]
    写(行)
    print(f"  ✓ 清掉 {前 - len(行)} 条办过的，剩 {len(行)} 条")

等 = [r for r in 行 if r["状"].startswith("⬜")]
print(f"  待你点头 {len(等)} 条　（表在 {路}）")
for r in 等:
    print(f"    [{r['号']}] {r['事']}")
    print(f"         要花：{r['花']}")
    print(f"         为什么：{r['为什么']}　（从 {r['等']} 起等）")
