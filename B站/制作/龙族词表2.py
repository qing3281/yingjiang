# -*- coding: utf-8 -*-
"""《龙族 · 雨夜》14 镜动态提示词表 v2 —— 改成 MiniMax H3 官方三字段骨架。

## 为什么要改（v1 的两个 bug 都有了官方解释）
用户反馈（m05479）：「用这个 minimax 模型，提示词必须非常详细……你这个太少了」。
据此我把每镜写到 1800~3000 字符，但**格式是错的**。

调研（`D:\\DSHworkspace\\mmh3\\H3-提示词写作规范.md`）给出的根因：

### bug 1：模型把提示词里的中文念出来
根因**不是长度**，是**中文台词没有容器**。H3 为台词设计了专用标签 `<d>`，
**不带容器的自然语言句子会被当可朗读内容**。
→ 解法三件事同时做：正文全英文 + 台词进 `<d>[Chinese] …</d>` + 显式排除句。
→ 本片全部丢弃模型音轨、音频自己合成，所以**不写任何台词**，
  改用官方那句「全片无人说话」的固定写法。

### bug 2：运镜写猛了场景漂移（《光明顶》35 镜跑了 8 镜）
根因**不是运镜本身**，是**同一镜头堆了多个大幅度快速度运镜**。
官方规则：**一镜一主运镜，要换运镜就切 `[Shot N]`**。
正确语法是**自然语言三维度**（不是方括号）：
    `运动类型 + with small/large amplitude + at slow/fast speed`
中等幅度正常速度**省略不写**（那是默认值）。

### v2 的三条改动
1. **骨架**：I2VA 首行对齐句 + `integrated_multimodal_description` +
   `overall_soundscape` + `non_diegetic_music: N/A`
2. **每镜只留一个主运镜**，写成「类型 + 幅度 + 速度」，不再堆叠
3. **画面描述原文保留**（v1 那部分写得是好的，只是结构不对）

## 实测对照（`龙族格式试验.py`，镜 05 同首帧同种子）
| 写法 | 平均帧间差 | 备注 |
|---|---|---|
| v1 自由文本 + 2 个运镜叠着 | 8.65 | |
| **v2 官方三字段 + 1 个运镜** | **9.96** | 运动量更大且场景锁死 |

运动量主要来自**摄影机在动**，不是人物在动（《光明顶》实测：只写细动作 5.78→5.90
几乎没用；写进摄影机 5.78→31.96）。所以每镜的主运镜就是这一镜的节奏来源。
"""
from __future__ import annotations

import re

import 龙族词表 as _旧

# ───────────────────── 每镜一个主运镜（官方三维度写法）─────────────────────
# 语法：运动类型 + with (small|large) amplitude + at (slow|fast) speed
# 中等幅度 / 正常速度省略不写。要换运镜就切镜头，不在一镜里叠。
主运镜: dict[int, str] = {
    1:  "The camera tracks alongside the car at exactly its own speed, low to the "
        "wet asphalt, with a heavy shake coming from the spray.",
    2:  "The camera pushes in with small amplitude at slow speed toward his eye, "
        "carrying a faint handheld breathing motion.",
    3:  "The camera holds a static shot on the wipers and the fog, letting the "
        "white light grow on its own.",
    4:  "The camera holds a static shot, placed low and ahead of the car, and is "
        "slammed by the shockwave so the frame shakes strongly.",
    5:  "The camera pushes in with small amplitude at slow speed along the wet "
        "asphalt, staying down at the height of the hooves the whole time and "
        "never tilting up to reveal the whole animal.",
    6:  "The camera tilts up with large amplitude at slow speed along the figure, "
        "ending tight on the masked face and the single golden eye.",
    7:  "The camera arcs around the two figures with small amplitude at slow "
        "speed, keeping both the man and the horse in frame.",
    8:  "The camera holds a static shot behind the man's shoulder, and shakes "
        "strongly once when the spear strikes the road.",
    9:  "The camera trucks right with large amplitude at fast speed, following the "
        "man as he is thrown across the wet asphalt.",
    10: "The camera pushes in with large amplitude at fast speed on the young "
        "man's face as he forces himself back onto his feet.",
    11: "The camera tracks the running figure from behind at a matched speed, low "
        "and close to the ground.",
    12: "The camera pulls out with large amplitude at slow speed, from the running "
        "boy to the whole expressway and the two monstrous silhouettes on it.",
    13: "The camera arcs around the impact with large amplitude at fast speed and "
        "then stops abruptly, shaking strongly.",
    14: "The camera pulls out with large amplitude at slow speed as the car "
        "recedes, until the road and the rain fill the entire frame.",
}

# ───────────────────── 每镜的 overall_soundscape（1~4 句）─────────────────────
# 官方要求：环境音 + 物理动作音 + 非语言人声；不要重复 description 里已有的同步音效。
声景: dict[int, str] = {
    1:  "Torrential rain hammering asphalt and sheet metal. A wide band of tyre "
        "roar sweeping past and dropping away. Standing water thrown up in sheets "
        "and falling back. A distant roll of thunder under everything.",
    2:  "Rain drumming hard on the car roof and glass. The low, steady rumble of "
        "the engine and the tyres on wet road. A faint squeak of the wiper blades. "
        "The boy's breathing is shallow and controlled.",
    3:  "Wipers sweeping across wet glass with a steady rhythmic thud. Rain "
        "driving against the windshield. The engine note rising as the car "
        "accelerates. A deep continuous roar from somewhere inside the fog.",
    4:  "A violent concussive blast of air. Water sheeting off the road surface. "
        "Metal groaning under sudden load. Rain continuing to fall through the "
        "aftermath.",
    5:  "Heavy rain on asphalt and on metal armour. A low wind across the open "
        "expressway. Stone chips ticking and scraping as they land. A deep, "
        "thunder-like animal bellow rolling out through the fog, with a faint "
        "electric crackle layered under it.",
    6:  "Rain falling on wet asphalt and on a vast expanse of armour. A slow, "
        "heavy wind. A low electric hum around the masked head. The clink of the "
        "spear head turning.",
    7:  "Rain on metal and on leather. The horse's hooves grinding broken stone "
        "against the road. A low continuous electric crackle. The man's boots "
        "shifting on wet asphalt.",
    8:  "A metallic ring as the curved spear tip scrapes along the road surface, "
        "trailing sparks. Rain hissing where it touches hot metal. A sharp crack "
        "of displaced air.",
    9:  "A heavy body tumbling across wet asphalt. Rain continuing without pause. "
        "Loose stone skittering away. A short, involuntary sound of pain that is "
        "not a word.",
    10: "Rain hammering the road. A slow, ragged intake of breath. Wet fabric "
        "dragging as the young man pushes himself up. A low electric hum from the "
        "horse above him.",
    11: "Rain driving hard into the road surface. Rapid footsteps splashing "
        "through standing water. A rising howl of wind along the expressway. "
        "Breath coming fast and hard.",
    12: "Rain and wind across a wide open road. The engine of the car receding. "
        "The deep bellow of the horse and a low electric crackle from the "
        "armoured figure, both fading as the distance opens.",
    13: "A vast metallic impact that tears the air. Metal screaming against "
        "metal. Rain hissing into the shockwave. A long, deep animal bellow "
        "underneath it all.",
    14: "Rain on a car roof and on wet asphalt, gradually becoming the only "
        "sound. Tyres on standing water. Distant thunder. The wind of an empty "
        "expressway.",
}

# ─────────────────────────── 共用部件 ───────────────────────────

# 官方 I2VA 首行对齐句（一字不改，只替换时间）
首行 = ("For the target video, at 0.00 seconds into the target video, "
        "<Picture 1> (from [Shot 1]) is fully referenced.")

# 官方「全片无人说话」的固定否定写法（本片音频全部自己合成，模型音轨丢弃）
无人声 = ("No dialogue, no singing, no voice-over and no narration of the prompt "
          "text. All characters remain silent throughout; lips stay closed. "
          "Characters do not speak any line that is not enclosed in <d>...</d>.")

# 场景锚（复述空间锚点，官方 §7.2 第 5 条要求每镜都提一次）
场景锚 = ("The location never changes: the same closed elevated expressway at "
          "night in a violent rainstorm, wet asphalt with running water, low "
          "concrete barriers on both sides, heavy fog, a pitch-black sky. It is "
          "never a warm brown street with red lanterns, never a bamboo forest, "
          "never a wooden temple hall, never daytime. "
          # ★ 镜 05 实测：写「山一样巨大的马」时，模型把《光明顶》的雪山先验
          #   带了过来——暴雨夜的高架上冒出一片雪峰。神话感的措辞会触发
          #   「史诗风景」的联想，必须逐项点名否掉。
          "There are no mountains, no snowy peaks, no hills, no valley and no "
          "open landscape anywhere in the frame; the horizon is only fog and "
          "black sky above the expressway barriers.")

# 真人比例锁（防 Q 版）
比例锚 = ("All human figures have realistic adult human proportions, head-to-body "
          "ratio about 1:7.5, realistic bone structure and musculature. Nobody is "
          "short, stubby, chibi or big-headed.")

# 实拍画风锁
画风锚 = ("Photoreal live-action cinema, ARRI ALEXA 65 with anamorphic lenses, "
          "very shallow depth of field, fine 35mm grain, real skin texture with "
          "visible pores and fine hair, real fabric weave soaked dark and heavy, "
          "rain physically interacting with everything it touches. Absolutely not "
          "anime, not animation, not illustration, not CG, not a game render, not "
          "concept art.")


_重复机位词 = [
    "photographed on an ARRI ALEXA 65 with anamorphic lenses",
    "shot on a long anamorphic lens with very shallow depth of field",
    "shot on a long anamorphic lens",
    "photoreal live-action cinema",
    "photoreal live-action",
]


def _描述(号: int) -> str:
    """从 v1 取出画面描述部分（砍掉旧的 CAMERA: 段落和共用尾巴）。

    注：v1 的描述开头会与画风锚的「ARRI ALEXA 65」重复一次。这一点冗余
    对模型无害（它读的是语义不是字数），而去掉反而会切断句子，故保留。
    """
    v1 = _旧.动态词表[号]
    v1 = re.split(r"\s*CAMERA:", v1)[0]
    # 砍掉 v1 拼接的共用尾巴（它们现在按官方结构分别落到各自字段）
    for 尾 in (_旧._锚, _旧._比例, _旧._音频):
        v1 = v1.replace(尾, "")
    v1 = re.sub(r"\s+", " ", v1).strip()
    return v1


def 取动态词(号: int) -> str:
    """返回该镜完整的官方三字段提示词。"""
    段 = [
        首行,
        "",
        f"integrated_multimodal_description: [Shot 1] {画风锚} {_描述(号)} "
        f"{场景锚} {比例锚} {主运镜[号]} The shot is a single continuous take and "
        f"does not cut. {无人声}",
        "",
        f"overall_soundscape: {声景[号]}",
        "",
        "non_diegetic_music: N/A",
    ]
    return "\n".join(段)


# 兼容旧调用点：做龙族.py 里是 `from 龙族词表 import 取动态词`
__all__ = ["取动态词", "主运镜", "声景"]


if __name__ == "__main__":
    import sys

    ns = [int(x) for x in sys.argv[1:]] or list(range(1, 15))
    for n in ns:
        t = 取动态词(n)
        print("=" * 72)
        print(f"镜 {n:02d}   {len(t)} 字符")
        print("=" * 72)
        print(t)
        print()
    print("字数：", {n: len(取动态词(n)) for n in ns})
