# -*- coding: utf-8 -*-
"""写法试验：同首帧、同种子，只换提示词写法，比运动量与画面。

三组：
  甲  官方三字段（英文）—— 现在生产用的写法
  乙  Work-Fisher 中文逐秒时间轴 —— 用户发来的那套
  丙  英文三字段骨架 + 中文逐秒动作轴嵌进 detailed_description —— 折中

用法：
    python 写法试验.py            跑全部
    python 写法试验.py --只 乙     只跑一组
    python 写法试验.py --测        只打印三组提示词长度，不跑
"""
import os
import sys
import argparse

import MiniMax动态 as 动

根 = r"D:\DSHworkspace\B站\成片\龙族_写法试验"
首帧 = r"D:\DSHworkspace\B站\成片\龙族_后30秒\首帧\05_首帧.png"
种子 = 5150

# ─────────────────────── 甲：官方三字段（英文） ───────────────────────
甲 = (
    "integrated_multimodal_description: "
    "Photorealistic live-action cinema, anamorphic widescreen, 35mm film grain, heavy rain at night "
    "on an elevated urban expressway. A single man in a long black leather coat stands alone in the "
    "centre of the flooded road, gripping a long straight sword in both hands. The camera moves with "
    "large amplitude at fast speed, arcing sideways around him from his left to behind his back while "
    "the frame shakes hard on every impact. Golden comet-like arcs of light slice down from outside "
    "the top of the frame one after another, none of them attached to anything visible, and every arc "
    "that meets his blade bursts into a spray of orange sparks that hiss out in the standing water. "
    "The rain is driven sideways by the shockwaves; a dry circle of bare asphalt opens around his feet "
    "while the rain hammers down everywhere else. His wet hair whips across his face, his coat snaps "
    "and trails behind him, and water sprays off the hem in sheets. No other person and no creature is "
    "visible anywhere in the frame at any moment. "
    "overall_soundscape: Sheeting rain on asphalt, the roar of wind, a deep metallic ring each time a "
    "golden arc meets the blade, water splashing under running feet, distant rolling thunder. "
    "non_diegetic_music: N/A"
)

# ───────────────── 乙：Work-Fisher 中文逐秒时间轴（原样） ─────────────────
乙 = (
    "【镜头规格】真人实拍电影级，16:9 院线宽画幅，8K，60fps，35mm 胶片颗粒，冷灰蓝电影底色，"
    "暴雨夜，高架快速路面，物理级流体动力学特效与 3D 体积粒子渲染，全程动态模糊随火力升级渐进加重。\n"
    "【人物设定】一名穿黑色长风衣的成年男性，湿透的头发贴在额前，双手横握一把长直刀，"
    "表情绷紧，全程高速移动无站桩，脚下积水被踩得水花四溅。\n"
    "【场景】暴雨夜的封闭高架快速路，路面积水反着冷光，路灯一盏接一盏向远处退去，"
    "看不到任何其他人物或生物，画面里只有他一个人。\n"
    "【核心特效定义】暗金色弧光：半透明的高温能量弧线，像彗星的尾巴，"
    "从画面外斜切进来，表面翻涌流动，边缘迸溅橘色火星粒子，带真实的高光与光线衰减；"
    "火星落到积水上立刻滋地熄灭；弧光与刀身接触的瞬间，空间轻微扭曲并炸开一圈空气冲击波。\n"
    "【分镜时间轴脚本】\n"
    "0-2s｜他压低重心横刀格挡，第一道暗金弧光从右上斜劈下来，刀弧相撞炸出成片橘色火星，"
    "火星如雨点砸进积水，他顺势向左侧滑出两米。\n"
    "2-3.5s｜第二、第三道弧光接连从不同角度切下，他连续两次转身格挡，"
    "风衣下摆被气浪掀起，水花沿着他的脚步甩成扇面。\n"
    "3.5-5.2s｜火力升级，弧光变成密集连击，他不再后退，改为迎着火网向前突进，"
    "边冲边挥刀，每一次格挡都让脚下的干燥圆圈扩大一圈。\n"
    "【运镜规则】\n"
    "0-2s｜镜头贴地低机位，大幅快速从他的左侧绕到背后，保持超广角畸变，动态模糊中度。\n"
    "2-3.5s｜镜头继续高速横移，穿插毫秒级快切，每次撞击镜头强烈震动一下，动态模糊加重。\n"
    "3.5-5.2s｜镜头升到半空俯拍，跟着他向前突进的轨迹快速推进，动态模糊重度。\n"
    "【负面提示词】站桩定点输出；无躲避动作；静止；动作僵硬卡顿；挥刀频率低；"
    "角色之外出现第二个人；出现怪兽；出现神；剑气为纯色能量波、无火星粒子；"
    "人物畸形、五官崩坏、手指扭曲、穿模；镜头固定呆滞；色彩过饱和；卡通感、动漫感"
)

# ─────────── 丙：英文三字段骨架 + 中文逐秒动作轴（折中） ───────────
丙 = (
    "integrated_multimodal_description: "
    "Photorealistic live-action cinema, anamorphic widescreen, 35mm film grain, heavy rain at night on "
    "an elevated urban expressway. A single man in a long black leather coat grips a long straight sword. "
    "The camera moves with large amplitude at fast speed, arcing sideways around him and then rising to a "
    "high angle, shaking hard on every impact. "
    "GOLDEN ARCS: semi-transparent high-temperature energy arcs like comet tails, slicing in from outside "
    "the frame, surfaces churning, edges spitting orange spark particles, physically accurate light falloff; "
    "sparks die hissing in the standing water; each blade contact warps space and blows out a ring of air. "
    "BEAT 0-2s: he drops his weight and blocks; the first arc slices down from upper right; the impact "
    "bursts into a sheet of orange sparks that rain into the puddles; he slides two metres to his left. "
    "BEAT 2-3.5s: two more arcs cut in from different angles; he turns and blocks twice; his coat hem is "
    "lifted by the blast and water fans out along his steps. "
    "BEAT 3.5-5.2s: the fire intensifies into a dense barrage; he stops retreating and charges forward "
    "into the net of light, swinging as he runs; the dry circle at his feet widens with every block. "
    "No other person and no creature is visible anywhere in the frame at any moment. "
    "overall_soundscape: Sheeting rain on asphalt, the roar of wind, a deep metallic ring each time an arc "
    "meets the blade, water splashing under running feet, distant rolling thunder. "
    "non_diegetic_music: N/A"
)

表 = {"甲": 甲, "乙": 乙, "丙": 丙}


def 跑(名: str) -> str | None:
    出 = os.path.join(根, f"W_{名}.mp4")
    if os.path.isfile(出) and os.path.getsize(出) > 10240:
        print(f"  ↷ {名} 已有")
        return 出
    print(f"\n── {名}  {len(表[名])} 字符 ──")
    return 动.出动态(首帧, 表[名], "", 出, 种子=种子, 放行中文=True)


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--只", default="")
    a.add_argument("--测", action="store_true")
    a = a.parse_args()

    print(f"首帧 {首帧}")
    print(f"种子 {种子}")
    for 名, 文 in 表.items():
        print(f"  {名}：{len(文)} 字符")

    if a.测:
        return 0

    要 = list(a.只) if a.只 else list(表)
    os.makedirs(根, exist_ok=True)
    for 名 in 要:
        if 名 not in 表:
            print(f"  ✗ 没有「{名}」这组")
            continue
        跑(名)
    print(f"\n全部结束 → {根}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
