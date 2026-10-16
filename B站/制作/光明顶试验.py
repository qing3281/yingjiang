# -*- coding: utf-8 -*-
"""《光明顶》画风 + 动作幅度 对照试验。

要回答两个问题：

  ① 画风「写实玄幻动漫」能不能出得来？（对比 Q 版卡渲）
  ② 提示词写长、写满动作，**帧间运动量**到底涨不涨？

做法：同一张首帧 + 同一个种子，只换提示词，跑三条：
    甲 = 《不烧心》那种短静态提示词（对照组）
    乙 = 写满过程的动作提示词
    丙 = 乙 + 显式摄影机运动 + 多节拍
然后逐帧算灰度帧间差（越小越静），看运动量差多少。

用法：python 光明顶试验.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

测试根 = r"D:\DSHworkspace\B站\成片\光明顶\测试"

# ─────────────────────────── 画风锁：写实玄幻动漫 ───────────────────────────

画风锁 = (
    "【画风 · 必须严格照做】中国写实玄幻动画电影质感，真人比例与真实人体结构，"
    "写实五官、写实肌肉与骨骼，皮肤有次表面散射和毛孔级细节，"
    "仙侠水墨气质与电影级硬光影结合，强烈的高对比打光，"
    "体积光穿过空气中的尘埃与烟气，"
    "衣袂、袍角、发丝有真实的布料解算与毛发质感，"
    "内力表现为发光的金色气流与掌风，剑气是有体积感的银白光束，"
    "画面带电影级运动模糊与镜头光晕，"
    "冷青与暖金双色调对撞，宽银幕电影构图，8K 超精细。\n"
    "**绝对不要**：Q 版、卡通大头身、日式赛璐璐平涂、塑料感、玩具感、"
    "低幼向、写实照片、真人剧照。"
)

负面 = (
    "Q版, 卡通, 大头身, 日式平涂, 赛璐璐, 低幼, 玩具, 塑料感, "
    "文字, 字幕, 水印, 签名, 边框, logo, 分格, 拼图, 三视图, 设定表, "
    "多个同一角色, 真人照片, 畸形, 多手多脚, 手指错乱, "
    "血腥, 恐怖, 阴暗, 低饱和"
)

# ────────────────────────────── 张无忌定妆描述 ──────────────────────────────

张无忌 = (
    "张无忌：二十出头的年轻男子，清瘦挺拔，"
    "浓眉大眼、双目黑白分明、眼神温和而坚定，鼻梁挺直，下颌线清晰，"
    "皮肤是健康的浅麦色，一头浓密黑发用一根素白布带松松束在脑后，"
    "几缕碎发垂在额前，"
    "身穿月白色粗布长袍，袍身宽大、袖口挽起，腰间系一条青灰色布带，"
    "袍角与袖口有轻微的磨损与尘土，脚下是黑色布靴。"
    "整体气质：朴实、沉静、不张扬，但周身有一层极淡的金色微光在流动"
    "（九阳神功的内力外溢）。"
    "不要华丽锦衣，不要冠冕，不要武器。"
)

# ─────────────────────────────── 三条对照提示词 ───────────────────────────────

短静态 = (
    "the young man in white raises his right hand slowly"
)

写满过程 = (
    "the young man in white plants his left foot hard into the cracked stone floor, "
    "his body twisting at the waist as his right palm sweeps up and forward in a wide arc, "
    "the loose sleeves of his robe snapping taut and then billowing outward behind him, "
    "his long black hair whipping across his face, "
    "a ring of dust and gravel bursting off the ground under his feet and expanding outward, "
    "golden light flaring from his palm and streaking across the frame, "
    "his robe hem tearing through the air, the fabric rippling in waves from his shoulder to the hem"
)

写满加运镜 = (
    "the young man in white lunges forward across the courtyard, "
    "his left foot slamming into the cracked stone floor and shattering it, "
    "his body twisting hard at the waist as his right palm sweeps up and forward in a wide arc, "
    "the loose sleeves of his robe snapping taut and then billowing violently behind him, "
    "his long black hair whipping across his face, "
    "a ring of dust and gravel bursting off the ground and blowing outward in a shockwave, "
    "golden light flaring from his palm and streaking across the whole frame, "
    "then he pivots and drives his other palm down toward the ground, "
    "a second shockwave blasting outward from the impact point, "
    "the camera whips around to follow him, dropping into a low angle and shaking hard on the impact, "
    "then pushes in fast on his face as he straightens up, breathing hard"
)


def 出首帧() -> str:
    import 出图_纯文本 as 图

    路 = os.path.join(测试根, "T_首帧.png")
    if os.path.isfile(路):
        print(f"  ↷ 首帧已有 {路}")
        return 路
    正 = (
        f"【任务】画出中国写实玄幻动画电影《光明顶》的一个镜头的一帧。\n\n"
        f"【镜头】中景，略低角度\n"
        f"【场景】昆仑山光明顶，明教总坛前的青石广场，"
        f"四周是断裂的石栏与燃烧的火盆，远处是连绵雪山与翻滚的云海，"
        f"空气里飘着烟尘与碎雪\n"
        f"【这一镜在发生什么】张无忌正一掌击出，身体处在扭转发力的瞬间，"
        f"脚下青石碎裂，金色的内力气流从他掌心炸开，衣袂向后翻飞\n"
        f"【表情】眉头紧锁，眼神凌厉，咬牙\n"
        f"【角色】{张无忌}\n\n"
        f"【画面要求】横向 16:9 构图，像电影动画的一帧，不是设定图不是三视图不是分格。"
        f"画面里只有这一个人，不要多画。"
        f"**画面上绝对不要出现任何文字、字幕、水印、签名、边框。**\n\n"
        f"{画风锁}"
    )
    r = 图.跑(正, 种子=8801, 宽=1344, 高=768, 负面=负面)
    if not r:
        return ""
    from PIL import Image

    Image.open(r).convert("RGB").save(路)
    print(f"  ✓ 首帧 {路}")
    return 路


def 跑一条(名: str, 提示词: str, 首帧: str, 种子: int) -> str:
    from MiniMax动态 import 出动态

    出 = os.path.join(测试根, f"T_{名}.mp4")
    if os.path.isfile(出) and os.path.getsize(出) > 10240:
        print(f"  ↷ {名} 已有")
        return 出
    print(f"\n── {名} ── 提示词 {len(提示词)} 字符")
    # ★ 战斗片全程丢弃模型音轨，所以提示词可以写满，不用为「不被念」而压短
    出动态(首帧, 提示词, "", 出, 种子=种子,
           主体="the young man in white (Zhang Wuji)")
    return 出


def 运动量(路: str) -> tuple[float, float, float]:
    """返回 (平均帧间差, P90, 最大)。灰度 224×126，越大越动。"""
    import av
    import numpy as np

    c = av.open(路)
    s = c.streams.video[0]
    前 = None
    ds = []
    for i, f in enumerate(c.decode(s)):
        if i % 2:
            continue
        g = np.asarray(f.to_image().convert("L").resize((224, 126)), dtype=np.float32)
        if 前 is not None:
            ds.append(float(np.abs(g - 前).mean()))
        前 = g
    c.close()
    a = np.array(ds)
    return float(a.mean()), float(np.percentile(a, 90)), float(a.max())


def main() -> int:
    os.makedirs(测试根, exist_ok=True)

    print("=" * 74)
    print("《光明顶》试验：画风 + 动作幅度")
    print("=" * 74)

    print("\n【1/2】出写实玄幻画风的首帧…")
    首帧 = 出首帧()
    if not 首帧:
        print("❌ 首帧失败")
        return 1

    print("\n【2/2】同一首帧、同一种子，只换提示词，跑三条…")
    结果 = {}
    for 名, 词 in (("甲_短静态", 短静态), ("乙_写满过程", 写满过程),
                   ("丙_写满加运镜", 写满加运镜)):
        路 = 跑一条(名, 词, 首帧, 种子=8801)
        if 路 and os.path.isfile(路):
            结果[名] = 运动量(路)

    print("\n" + "=" * 74)
    print(f"{'组':<16}{'平均帧间差':>12}{'P90':>10}{'峰值':>10}")
    print("-" * 74)
    for 名, (a, b, c) in 结果.items():
        print(f"{名:<16}{a:>12.2f}{b:>10.2f}{c:>10.2f}")
    print("-" * 74)
    print("参考：《不烧心》30 镜平均 5.49 / 255，P90 约 10")
    print("      < 1.0 几乎静止 | 1~3 小幅局部动 | 3~8 明显动作 | > 8 剧烈运动")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
