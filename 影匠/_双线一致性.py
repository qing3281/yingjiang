# -*- coding: utf-8 -*-
"""双线一致性 —— 真跑一遍验证 L1/L2/L3。

做法：把 引擎.派工 包一层，把【本机发出去的那张图】截下来，
     跑完后从对端 /history 读回【它实际执行的图】，两个指纹对比。
"""
import os
import sys
import time

这里 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 这里)

import 双线  # noqa: E402
import 引擎  # noqa: E402

# ── 钩住派工，把发出去的图存下来 ──
原派工 = 引擎.派工
抓到 = {}


def 钩子(工作流, 报=None, 等=True, 上限秒=1800):
    抓到["图"] = 工作流
    抓到["指纹"] = 双线.图指纹(工作流)
    果 = 原派工(工作流, 报=报, 等=等, 上限秒=上限秒)
    抓到["号"] = 果.get("提示号", "")
    return 果


引擎.派工 = 钩子

print("=" * 70)
print("两端状态")
print("=" * 70)
for 名 in ("本机", "远端"):
    print(f"  {名:<4} {引擎.换端点(名)}")
    print(f"       {引擎.在线()}")

print()
print("=" * 70)
print("L1 模型一致")
print("=" * 70)
r1 = 双线.比模型(["wan22_i2v"])

print()
print("=" * 70)
print("派工到远端（视频线）")
print("=" * 70)
引擎.换端点("远端")
print("  端点:", 引擎.在线().get("端点"), 引擎.在线().get("显卡"))

首帧 = os.path.join(这里, "作品", "试镜", "01_格7.png")
if not os.path.exists(首帧):
    首帧 = os.path.join(这里, "作品", "换脸_格7.png")
print("  首帧:", 首帧, os.path.exists(首帧))

词 = "银发剑客立于雪原，黑发黑衣白饰，侧身回望，剑垂于侧，风吹发丝微动，电影写实，冷蓝色调，雪花缓落"
t = time.time()
果 = 引擎.图生视频(
    首帧, 词, 种子=20261014, 帧数=49, 帧率=16, 宽=832, 高=480,
    前缀="双线验", 存到=os.path.join(这里, "作品", "试镜", "_双线一致性.mp4"),
    报=lambda s: print("   ", s),
)
花 = time.time() - t
print(f"  远端出片用时 {花:.1f} 秒 -> {果['路']}")

print()
print("=" * 70)
print("L2 工作流一致（对端执行的图 == 本机发的图？）")
print("=" * 70)
r2 = 双线.验回执(果.get("提示号") or 抓到.get("号", ""), 抓到["图"])

print()
print("=" * 70)
print("L3 成片一致（画幅/帧数/帧率是不是本机要求的）")
print("=" * 70)
r3 = 双线.验片(果["路"], 宽=832, 高=480, 帧率=16, 帧数=49)

print()
print("=" * 70)
print("汇总")
print("=" * 70)
print(f"  L1 模型一致   {'✓ 通过' if r1['通过'] else '✗ 没过'}")
print(f"  L2 工作流一致 {'✓ 通过' if r2.get('通过') else ('⚠ 没验成' if r2.get('通过') is None else '✗ 没过')}")
print(f"  L3 成片一致   {'✓ 通过' if r3.get('通过') else ('⚠ 没验成' if r3.get('通过') is None else '✗ 没过')}")
