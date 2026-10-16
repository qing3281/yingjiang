# -*- coding: utf-8 -*-
"""运镜强度试验 —— 用户报「根本没什么动作，就是在看几张图片」。

全片帧间差实测 7.30（《光明顶》12.38，试验丙组 31.96），确实在「静态」档。
本脚本用同一张首帧、同一个种子，只改提示词里的**运镜写法与场景锚**，找出到底是什么在压运动量。

三组：
  甲  现行：温和运镜（small amplitude / slow speed）+ 场景锚
  乙  猛运镜（large amplitude / fast speed，多个）+ 场景锚
  丙  猛运镜 + **去掉场景锚**

跑法：python 龙族运镜试验.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

首帧 = r"D:\DSHworkspace\B站\成片\龙族\首帧\09_首帧.png"
出根 = r"D:\DSHworkspace\B站\成片\龙族\运镜试验"

场景锚 = (
    "The location never changes and stays exactly the same in every frame: "
    "a rain-soaked elevated highway at night, wet black asphalt with painted lane markings, "
    "a concrete central divider on the left, metal guardrails on both sides, "
    "tall street lamps receding into the distance casting cold cones of light, "
    "dense fog, heavy rain, distant forested hills, a black sedan stopped in the middle of the road. "
    "There is no other location, no interior room, no daylight, no dry ground."
)

# 主体与音效要求三组共用，保证只变运镜这一个变量
主体 = (
    "On screen: a colossal armoured figure standing on the roof of the black sedan, "
    "surrounded by a crowd of identical black-robed figures with dead white faces, "
    "and a teenage boy visible inside the car."
)

音频 = "No dialogue, no narration, no voice-over, no music. Only rain, wind, thunder and footsteps."

甲 = (
    "The camera pushes in with small amplitude at slow speed toward the armoured figure. "
    "The armoured figure stands motionless on the roof of the car while rain runs down its armour. "
    "The black-robed figures walk slowly forward through the standing water, their robes dragging. "
    "Rain falls steadily and fog drifts across the road."
)

乙 = (
    "The camera whips around the armoured figure with large amplitude at fast speed, "
    "then drops to a low angle and shakes strongly as the black-robed figures close in, "
    "then pushes in hard with large amplitude at fast speed onto the face of the boy inside the car. "
    "The armoured figure turns its head slowly and raises the spear overhead. "
    "The black-robed figures surge forward all at once, robes snapping, water exploding under their feet. "
    "The boy throws himself across the seat. Rain lashes the lens and fog boils across the road."
)


def 跑(名: str, 动作: str, 用锚: bool):
    from MiniMax动态 import 出动态

    出 = os.path.join(出根, f"Y_{名}.mp4")
    if os.path.isfile(出) and os.path.getsize(出) > 10240:
        print(f"  ↷ {名} 已有")
        return 出
    段 = [动作.strip() + "."]
    if 用锚:
        段.append(场景锚)
    段.append(主体)
    段.append(音频)
    提示词 = " ".join(段)
    中文 = __import__("re").findall(r"[\u4e00-\u9fff]+", __import__("re").sub(r'"[^"]*"', "", 提示词))
    if 中文:
        print(f"    ⛔ 引号外还有中文：{中文[:5]}")
        return None
    print(f"\n── {名} ── {len(提示词)} 字符  场景锚={'有' if 用锚 else '无'}")
    出动态(首帧, 提示词, "", 出, 种子=7711, 主体="")
    return 出


def main():
    os.makedirs(出根, exist_ok=True)
    from PIL import Image  # noqa: F401  仅确认依赖在
    清单 = [("甲_现行温和加锚", 甲, True),
            ("乙_猛运镜加锚", 乙, True),
            ("丙_猛运镜去锚", 乙, False)]
    for 名, 动作, 用锚 in 清单:
        跑(名, 动作, 用锚)
    print("\n全部完成 →", 出根)


if __name__ == "__main__":
    main()
