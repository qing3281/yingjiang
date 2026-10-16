# -*- coding: utf-8 -*-
"""看一眼：--出动态 实际会发给 MiniMax 的提示词长什么样。
   改提示词结构之后，先跑这个，别浪费 GPU。"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("d", r"D:\DSHworkspace\B站\制作\做不烧心.py")
d = importlib.util.module_from_spec(spec)
sys.modules["d"] = d
spec.loader.exec_module(d)

想要 = [int(x) for x in sys.argv[1:]] or list(range(1, 31))
镜表 = d.读剧本(d.剧本)

for 镜 in 镜表:
    if 镜["号"] not in 想要:
        continue
    台词 = d.提台词(镜.get("台词", "") or "")
    主体 = d.造主体(镜)
    动作 = d.造动态提示词(镜)
    段 = []
    if 动作:
        段.append(动作.strip() + ".")
    if 主体:
        段.append(f"On screen: {主体.strip()}.")
    else:
        段.append("The street is completely empty, no people at all.")
    if 台词:
        段.append(f'She speaks Chinese: "{台词}"')
        段.append("No other dialogue, no narration, no voice-over, no music.")
    else:
        段.append("No dialogue, no narration, no music, ambient sound only.")
    最终 = " ".join(段)
    print(f"=== 镜 {镜['号']:02d} {镜.get('标题','')} ===")
    print(f"  台词 : {台词!r}")
    print(f"  主体 : {主体}")
    print(f"  最终 : {最终}")
    print()
