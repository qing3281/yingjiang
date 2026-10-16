# -*- coding: utf-8 -*-
"""《龙族 · 雨夜》14 镜动态提示词表（全英文，给 MiniMax H3 fl2va）。

## 为什么这么长
用户原话（m05479）：「用这个 minimax 模型，提示词必须非常详细，一小段视频要 9000 字，
你这个提示词简直太少了，效果很差」。

官方文档核实：H3 提示词上限 **7000 字符**（不是 9000），4–15 秒整数时长。
上一部《光明顶》平均只有 580 字符 —— 确实太短了。

## 这一版怎么写（和上一部的区别）
1. **长度**：每镜 1800~3000 字符，是上一部的 3~5 倍
2. **结构分五段**：镜头规格 → 主体精确外观 → 动作节拍（逐拍）→ 环境物理 →
   光照与氛围。上一部只有「动作 + 运镜」两项
3. **运动量靠摄影机**（《光明顶》实测：只把动作写细，帧间差 5.78→5.90 几乎没用；
   把摄影机写进去才 5.78→31.96）。所以每镜都必须有显式运镜
4. **场景锚**：每一镜都重申「封闭高架路 + 暴雨夜 + 浓雾」，
   并且**逐项否定**最容易漂移成的那几类场景（暖褐街市 / 绿色竹林 / 木构殿堂 / 白天）
   —— 《光明顶》就是栽在这里，35 镜里 8 镜跑景
5. **人物比例**：每镜都重申真实成年人类比例、头身比 1:7.5，否定矮小/大头/儿童体型

## 两条铁律（上一部用血换来的）
- **提示词里引号外的中文会被念出来**。这里全英文，一个中文字符都没有。
- **提示词整体都会被当成「要念的内容」**。所以不写任何台词，并且每镜结尾都
  明确写「没有任何人声」——因为这一部的音频我全部丢弃、自己合成。
"""
from __future__ import annotations

# ─────────────────────────── 每镜共用的尾巴 ───────────────────────────

_比例 = (
    "All human figures have realistic adult human proportions, head-to-body ratio "
    "about 1:7.5, realistic bone structure and musculature, normal-sized heads. "
    "Nobody is short, stubby, chibi, child-proportioned or big-headed."
)

_音频 = (
    "There is absolutely no dialogue, no narration, no voice-over and no music in "
    "this clip. Only natural ambient sound."
)

_锚 = (
    "The location never changes: this is always the same closed elevated expressway "
    "at night in a violent rainstorm, wet asphalt with running water, low concrete "
    "barriers on both sides, heavy fog, a pitch-black sky. It is never a warm brown "
    "Chinese street with red lanterns, never a green bamboo forest, never a wooden "
    "temple hall with red pillars, never daytime, never a sunny interior."
)

# ─────────────────────────────── 14 镜 ───────────────────────────────

动态词表: dict[int, str] = {

    1: (
        "Cinematic wide establishing shot, photographed on an ARRI ALEXA 65 with "
        "anamorphic lenses. A closed elevated expressway at night in a violent "
        "rainstorm. A single pure-black luxury sedan races along the empty road at "
        "extreme speed, its headlights cutting two cone-shaped white beams through "
        "the downpour. The car hits standing water and throws a curtain of white "
        "spray taller than a man up behind it, and that spray is lit from inside by "
        "the tail lights and glows. Rain falls in sheets; individual raindrops close "
        "to the lens are out of focus and read as a field of round bokeh orbs. Water "
        "on the asphalt mirrors the headlights and the occasional lamp post and the "
        "mirror image ripples apart wherever a drop lands. Far away a lightning bolt "
        "flashes inside the low black clouds and for a fraction of a second outlines "
        "the cloud mass in cold white. The only light sources in the whole frame are "
        "the headlights, the distant street lamps and that lightning; everything "
        "else is buried in darkness. "
        "CAMERA: an extremely low camera, almost touching the wet asphalt, tracking "
        "alongside the car at exactly the same speed so the car stays the same size "
        "in frame while the road surface streams toward the viewer; the lens keeps "
        "getting hit by flying water so droplets smear across the image and slide "
        "off. The camera shakes hard from the spray and from the slipstream. " + _锚 + " " + _比例 + " " + _音频
    ),

    2: (
        "Cinematic medium close-up inside a moving luxury car at night, shot on a "
        "long anamorphic lens with very shallow depth of field. A fifteen-year-old "
        "Chinese boy sits in the front passenger seat. He has a pale, bloodless face, "
        "thin lips, a sharply defined jaw, and short straight black hair that has been "
        "soaked by rain and now clings flat to his forehead and the sides of his neck, "
        "with droplets running off the tips. He wears a dark navy school shirt, the "
        "fabric darkened and heavy where rain has soaked his shoulders and chest, "
        "creasing and sticking to him, buttoned all the way up to the collar. His "
        "eyes are locked on the windshield, unblinking. He swallows once, his throat "
        "moving, and his fingers tighten unconsciously around the seat belt strap. "
        "His expression is blank and hollow in the way of a boy who has spent years "
        "suppressing everything, but underneath it his jaw is clenched and there is a "
        "thin sheen of cold sweat on his forehead. Outside the side window is nothing "
        "but black rain. The dashboard throws cold white light onto the right side of "
        "his face while a warm orange glow from a distant light source catches the "
        "left side. Rain hammers the window glass and runs down it in wavering "
        "streaks, and those streaks cross his reflection. "
        "CAMERA: inside the car, starting behind his shoulder and slowly pushing in "
        "toward his profile, with a subtle handheld breathing motion, the focus "
        "staying locked on his eye. " + _比例 + " " + _音频
    ),

    3: (
        "Cinematic extreme wide shot looking forward through a car windshield at "
        "night in a rainstorm. The windshield glass fills the upper half of the "
        "frame and is smeared with water; two wipers sweep across it fast, each pass "
        "wiping the glass clear for a moment before the rain covers it again. Beyond "
        "the glass, a straight elevated expressway runs into thick fog. Deep inside "
        "that fog, an enormous, solemn white light is rising and expanding. It is not "
        "a lamp post and not a building; it is shapeless and vast and it keeps "
        "growing as the car approaches, and each time the wipers sweep across it the "
        "white light is briefly sliced in two and then joins back together. The car's "
        "own headlight beams push into the fog and are swallowed by it a few metres "
        "out. The dashboard glows faintly at the bottom of the frame and the rear-view "
        "mirror hangs at the top. Rain streams down the outside of the glass and "
        "distorts everything behind it. "
        "CAMERA: fixed inside the car, shaking violently with the road surface, "
        "creeping slowly forward as though the viewer is leaning toward the glass. "
        + _锚 + " " + _音频
    ),

    4: (
        "Cinematic wide shot from outside the car, camera very low and off to the "
        "front quarter. A pure-black luxury sedan at full speed on a wet elevated "
        "expressway at night charges straight into an enormous wall of blinding white "
        "light that fills the fog ahead. In the instant the car's nose pierces the "
        "fog wall, the fog is cut open from the middle and rolls back to both sides in "
        "two heavy curling waves. Then the white light explodes outward and the whole "
        "image blows out to near-white, holding there for a beat, with only a "
        "silhouette of the car visible inside the glare. Water is thrown off the road "
        "surface in a wide sheet. The car's shape distorts in the shockwave. "
        "CAMERA: locked off, extremely low, positioned ahead of the car so the car "
        "rushes directly at and past the lens; the camera is slammed by the shockwave "
        "and shakes violently, then the blown-out white slowly resolves back into fog "
        "and rain. " + _锚 + " " + _比例 + " " + _音频
    ),

    5: (
        # ★ 2026-10-13 重写：原来写的是「大远景强仰拍，露出整匹马」。
        #   实测模型对「披甲的马」的先验牢不可破——四次不同种子都出了四条腿、
        #   棕色毛、带马鞍、背景还自动长出雪山。文字否定改不动它。
        #   改成【只拍腿】之后，模型不需要理解「八条腿的马」这种它没见过的生物，
        #   只需要画「很多条裹着甲片的马腿」——这反而更贴原文的
        #   「八条腿像起重机用来稳定车身的支架一样撑在地面上」，也更有压迫感。
        "Cinematic extreme wide shot from an extremely low camera placed right down "
        "at the level of the wet asphalt, looking straight ahead and slightly up, "
        "never tilting up far enough to show the whole animal. The fog on the "
        "elevated expressway splits apart and a mass of armoured legs steps into "
        "the frame. Each leg is sheathed in riveted plates of oxidised black iron "
        "and bronze, scratched, dented and streaked with rust, with rainwater "
        "running down between the plates. There are legs in front, legs behind and "
        "legs on both sides, one group after another, far more of them than any "
        "ordinary animal has, planted at different angles like the hydraulic "
        "outriggers that stabilise a heavy crane. Their dark gold hooves have "
        "driven deep into the asphalt, tearing open one wound after another in the "
        "road surface and kicking broken chips of stone up into the air where they "
        "hang suspended. The enormous body rises up and out of the top of the "
        "frame and disappears into the churning rain and fog; only a corner of its "
        "jaw and one riveted metal faceplate are visible at the very top, and from "
        "the nostril openings of that faceplate fine crackling sparks of "
        "electricity spray out, lighting the underside of the metal. There is no "
        "saddle, no decorative engraving and no gold ornament on the armour; the "
        "only gold in the frame is on the hooves. Rain and fog fill the rest of "
        "the frame, and the horizon is closed off by fog and black night with no "
        "mountains, no snowy peaks and no landscape visible at all. "
        "CAMERA: the camera pushes in with small amplitude at slow speed along the "
        "wet asphalt, staying down at the height of the hooves the whole time and "
        "never rising to reveal the whole animal. " + _锚 + " " + _比例 + " " + _音频
    ),

    6: (
        "Cinematic extreme wide shot, steep low angle looking up at a god. On the "
        "elevated expressway at night in the rain, a figure stands in the fog and the "
        "vast white light: he is so tall that he occupies the upper two thirds of the "
        "frame, while at the very bottom of the frame there is only the roof of a "
        "black sedan. He wears heavy armour forged from oxidised black bronze and "
        "iron, its plates layered over one another, covered in scratches, dents and "
        "dark red rust in the seams, with rainwater running down between the plates "
        "and cutting dark wet streaks across the metal. The armour does not gleam at "
        "all; it is only wet, heavy and cold. He wears an iron mask that covers the "
        "upper half of his face, and that mask is itself corroded black iron. Below "
        "the mask, the single eye that is exposed is pure gold, like a great lamp, "
        "and it throws two shafts of golden light out through the rain. That eye is "
        "the only golden thing anywhere in the frame. In his right hand, held low, is "
        "a curved spear: the shaft is dark wood, the head is matte iron, and the curve "
        "of the weapon traces the arc of a shooting star across the sky. Behind him a "
        "heavy dark blue cloak, soaked through with rain, whips sideways in the gale "
        "and blurs at the edges. The rain around him is unnaturally heavy and forms a "
        "slowly circulating ring of white mist. The clouds press low and flash with "
        "internal lightning. The single golden eye narrows very slightly, and the "
        "spear tip rises and turns to aim off-frame toward the car. "
        "CAMERA: steeply low angle beneath the figure, slowly tilting upward and "
        "pushing in, ending tight on the masked face and the golden eye. " + _锚 + " " + _比例 + " " + _音频
    ),

    7: (
        "Cinematic wide shot, camera almost on the ground directly in front of a car. "
        "On the elevated expressway at night, the rain behaves impossibly: all of the "
        "water in the air around the god is drawn inward and gathers into a "
        "translucent wall of falling water more than a man's height, hanging in the "
        "air. The black luxury sedan hits that wall at maximum speed. The front of the "
        "car crumples instantly, the body is shoved violently backwards by a force far "
        "larger than the impact should produce, and the tyres break traction on the "
        "flooded asphalt, spinning and smoking. At the instant of impact the water wall "
        "ruptures and bursts into a cloud of atomised spray that fills the entire "
        "frame. Fragments of the headlight housing and the grille spin away. "
        "CAMERA: locked off, lying almost on the road surface, the car rushing "
        "straight at the lens and being thrown back; the lens is completely smeared "
        "over by the exploding water and the image goes soft and white. "
        + _锚 + " " + _比例 + " " + _音频
    ),

    8: (
        "Cinematic medium close-up inside a car cabin at the moment of a crash, shot "
        "on a wide lens. The airbag detonates in front of the passenger seat and white "
        "gas fills the cabin in a fraction of a second. A fifteen-year-old Chinese boy "
        "in a soaked navy school shirt is thrown forward by the deceleration and then "
        "slammed back into the seat by the seat belt; his head snaps back into the "
        "headrest, his hair flying, his whole body jerking. He grabs at the inflating "
        "airbag with both hands and his fingers sink into it. Loose objects in the "
        "cabin are thrown forward through the white gas. Rain streams down the side "
        "window and the world outside is a smeared blur of dark blue and white "
        "headlight glare. "
        "CAMERA: fixed inside the cabin, jolted violently by the impact, the focus "
        "briefly lost in the white gas and then snapping back onto his face. "
        + _比例 + " " + _音频
    ),

    9: (
        "Cinematic wide shot on a long lens, slowly tracking forward. On the elevated "
        "expressway at night, a black sedan sits crumpled and steaming in the "
        "foreground, and beyond it the god stands in the fog mounted on his enormous "
        "horse. Out of the fog behind him, and out of the fog on both sides, figures "
        "walk forward in silence. They are all identical: the same long black coat, "
        "the same bloodless white face, the same empty eyes glowing with a faint "
        "golden light. There are dozens of them and then more than can be counted, "
        "walking with an even, unhurried, ceremonial step, like a congregation "
        "processing into a mass, closing in from every direction until the car is "
        "completely surrounded. Near the edges of the frame a few of them are moving "
        "fast enough that their bodies smear into distorted streaks, like long snakes "
        "rearing up off the ground. None of them speaks. None of their faces shows any "
        "expression at all. "
        "CAMERA: a long lens compressing the depth, slowly tracking forward from "
        "behind the car, looking between the car's body panels toward the god while "
        "the dark figures keep sliding into frame from both edges and filling the "
        "space around the car. " + _锚 + " " + _比例 + " " + _音频
    ),

    10: (
        "Cinematic medium shot, slightly low angle, strongly backlit. Night on the "
        "elevated expressway in heavy rain. Two figures stand side by side in the "
        "blazing white light of a car's two headlights, both rendered as sharp "
        "silhouettes, with the headlight glare burning a hard rim light along the "
        "edges of their bodies. On the left is a Chinese man in his forties, tall and "
        "straight with broad shoulders, wearing a dark jacket soaked through with "
        "rain, holding a straight single-edged blade about a metre long low in his "
        "right hand, the steel catching a cold glint. On the right is a "
        "fifteen-year-old boy, half a head shorter, in a soaked school shirt, and the "
        "man's left arm is around his shoulders, pulling him half a step closer. Rain "
        "runs off both their chins. The rain between the camera and the figures is "
        "picked out by the headlights into thousands of bright silver threads "
        "slanting across the frame. The ground is flooded and mirrors the headlights, "
        "and the falling rain stipples that reflection with dense rings. The man turns "
        "his head slightly and leans down to speak close to his son's ear. "
        "CAMERA: a slightly low fixed medium shot with a subtle handheld breathing "
        "motion, pushing in very slowly on the two of them. " + _锚 + " " + _比例 + " " + _音频
    ),

    11: (
        "Cinematic medium close-up, handheld, shot from behind and to the side of a "
        "man. Night on the elevated expressway in torrential rain, everything lit by "
        "blazing white headlights through a curtain of falling water. The man hurls a "
        "black hard-shell suitcase away from himself into the depth of the frame; the "
        "case tumbles end over end through the rain, catching the light as it spins. "
        "In the same motion he twists and slams his open palm flat against the back of "
        "the boy beside him, shoving him hard toward the car, and the boy is thrown "
        "forward off his feet into a stumbling run. The man's mouth is wide open as he "
        "roars, his face contorted by the effort, the tendons in his neck standing "
        "out, his eyes bloodshot and wide, an expression of somebody who has "
        "completely given up on surviving. Water sprays off his clothing as he turns. "
        "CAMERA: handheld and shaking hard, whipping far into the depth of the frame "
        "to follow the thrown suitcase, then whipping back to land on the man's face "
        "as he roars. " + _锚 + " " + _比例 + " " + _音频
    ),

    12: (
        "Cinematic wide shot, slow motion, orbiting camera. Night on the flooded "
        "elevated expressway, lit by car headlights through heavy rain. A transparent "
        "curtain of force unfolds outward from the man and spreads across the whole "
        "area, and everywhere it touches, time itself slows down. Individual raindrops "
        "stop in mid-air and hang there like thousands of tiny glass beads, each one "
        "holding a point of light. The dark figures all slow to a crawl and their "
        "bodies drag long smeared afterimages behind them. Only the man is unaffected. "
        "He spins on the spot, steps forward, turns at the waist, and his blade draws "
        "one long dazzling silver arc through the suspended black raindrops, the edge "
        "of the arc flaring white. Thick black blood wells slowly out of the figures he "
        "cuts and hangs motionless in the air rather than falling, drifting in the "
        "suspended water like ink released in a glass. His face is completely calm, "
        "his eyes fixed and terribly focused. "
        "CAMERA: a slow-motion orbital track that swings in a wide half-circle around "
        "the man at a fraction of normal speed, the suspended raindrops sliding across "
        "the foreground between the lens and him. " + _锚 + " " + _比例 + " " + _音频
    ),

    13: (
        "Cinematic extreme wide shot, steeply low angle, dramatic action. Night on "
        "the elevated expressway in a violent rainstorm. The man drives his foot down "
        "onto a dark figure, launches himself high into the air, and brings the long "
        "blade up over his head for a two-handed downward strike aimed at the god's "
        "skull. The god's arm moves: the curved spear is drawn and thrust, not once "
        "but dozens of times in the space of a breath. Every thrust trails a thin "
        "afterglow of dark gold light, and those arcs of light curve around the man "
        "and stab in toward his throat, his heart, his spine, his legs, converging "
        "like a dense shower of shooting stars. The man twists in the air inside that "
        "shower, whipping the blade around him in a fast circle, deflecting, "
        "contorting, teeth bared, eyes wide. Where the arcs of light graze him, his "
        "clothing tears open and dark blood sprays out into the rain. "
        "CAMERA: steeply low angle wide, tilting up fast to follow his leap, then "
        "shaking violently and pushing in slightly at the instant the star-shower of "
        "spear-light bursts outward and fills the frame. " + _锚 + " " + _比例 + " " + _音频
    ),

    14: (
        "Cinematic wide action shot, violent motion, camera behind and to the side of "
        "a car. Night on the flooded elevated expressway. The crumpled black luxury "
        "sedan reverses hard, roaring out of the ring of dark figures, its tyres "
        "spinning and smoking on the standing water, the rear of the car smashing "
        "backwards through the translucent wall of rain. That wall shatters like glass "
        "and bursts apart into a spray of bright fragments. Free of it, the car swings "
        "around and accelerates away, plunging into the dense blackness ahead, and its "
        "two red tail lights drag long smeared streaks of light through the falling "
        "rain. Behind it, the vast white light and the massed dark figures recede into "
        "the fog. Water thrown up by the tyres hangs in the air behind the car. "
        "CAMERA: tracking behind and to the side of the car, shaking and rotating "
        "violently with the manoeuvre, then falling behind and holding as the car "
        "shrinks into the darkness with only its tail lights still visible. "
        + _锚 + " " + _比例 + " " + _音频
    ),
}


def 取动态词(号: int) -> str:
    """取某一镜的全英文动态提示词。"""
    if 号 not in 动态词表:
        raise KeyError(f"动态词表里没有第 {号} 镜")
    return 动态词表[号]


# ─────────────────────────────── 自检 ───────────────────────────────

def 自检() -> int:
    """检查：①全 ASCII ②长度够 ③都带摄影机词 ④都不含台词。"""
    import re

    摄影机词 = ("CAMERA", "camera", "lens", "tracking", "tilting", "push", "orbit",
              "whip", "dolly", "crane", "shakes", "shaking")
    坏 = 0
    最长 = 0
    for 号 in sorted(动态词表):
        词 = 动态词表[号]
        非ASCII = sorted({c for c in 词 if ord(c) > 127})
        if 非ASCII:
            print(f"  ✗ 镜 {号:>2}  含非 ASCII 字符：{非ASCII}")
            坏 += 1
        if 号 not in (2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14) and "The location never changes" not in 词 and 号 not in (1,):
            pass
        if not any(w in 词 for w in 摄影机词):
            print(f"  ✗ 镜 {号:>2}  没有摄影机描述")
            坏 += 1
        if len(词) < 1200:
            print(f"  ⚠ 镜 {号:>2}  只有 {len(词)} 字符，偏短")
        最长 = max(最长, len(词))
    print(f"\n  {len(动态词表)} 镜  最短 {min(len(v) for v in 动态词表.values())} 字符  "
          f"最长 {最长} 字符  平均 {sum(len(v) for v in 动态词表.values())//len(动态词表)} 字符")
    print(f"  官方上限 7000 字符 —— {'✅ 全部在上限内' if 最长 < 7000 else '✗ 有超限'}")
    print(f"  纯 ASCII：{'✅' if 坏 == 0 else f'✗ {坏} 处问题'}")
    return 0 if 坏 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(自检())
