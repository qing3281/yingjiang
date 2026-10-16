# -*- coding: utf-8 -*-
"""《龙族 · 雨落狂流》后 30 秒 —— 8 条动态提示词（重做版）

与旧版的区别（两条，都是实测出来的）：

  ① **运镜一律 large amplitude at fast speed。**
     旧版为了防止《光明顶》那种场景漂移，每条都写成 small amplitude at slow speed，
     等于告诉模型「什么都别动」。同一张首帧的对照实测：
         温和加锚 3.18 ｜ 猛运镜加锚 12.56 ｜ 猛运镜去锚 11.17
     所以猛运镜，而场景锚**保留**（它不抑制运动，却防漂移）。

  ② **每条都写「从哪到哪」的位移。** 「他在打」不会动，「他从左边冲到右边」才会动。

骨架用 H3 官方三字段：integrated_multimodal_description / overall_soundscape /
non_diegetic_music。正文字符数 2400~3600，在上限 7000 之内。
"""

# 全片共用的场景锚（防漂移；实测不影响运动量）
_锚 = (
    "The location is fixed and identical in every frame: a rain-soaked elevated "
    "expressway at night. Wet black asphalt with white painted lane markings, "
    "standing water reflecting the lights. A concrete central divider running "
    "along the left, metal guardrails on both sides, tall street lamps receding "
    "into fog and casting cold white cones. Dense fog, heavy driving rain, "
    "distant dark forested hills, snowless. A black luxury sedan stopped in the "
    "middle of the road. There is no interior room, no daylight, no dry ground, "
    "no snow, no mountains, no desert, no forest clearing, no red lanterns, "
    "no wooden shopfronts, no bamboo."
)

# 共用的画风与质感要求
_质感 = (
    "Shot as live-action cinema, not animation and not CG. Photographed on an ARRI "
    "ALEXA 65 with anamorphic lenses at T1.8, shallow depth of field, 35mm film "
    "grain, soft anamorphic horizontal flares. Skin shows visible pores, fine "
    "vellus hair, and the wet sheen and flushed colour of rain-soaked faces; "
    "subsurface scattering glows faintly red through ears and nostrils. Fabric "
    "shows its weave, darkens and grows heavy where soaked, clings and wrinkles. "
    "Hair is individually visible, clumped and dripping where wet. Rain obeys "
    "physics: out-of-focus drops become round bokeh in front of the lens, drops "
    "burst into mist on contact, water runs down fabric fibres and hair, and "
    "puddles ripple under each impact."
)

_音 = (
    "overall_soundscape: Heavy rain on asphalt and metal, water sheeting off the "
    "car body, wind gusting across the open roadway, distant thunder rolling. "
    "Footsteps splash through standing water. There is no dialogue, no narration, "
    "no voice-over, no singing. Every character stays silent throughout and their "
    "lips remain closed."
)

_乐 = "non_diegetic_music: N/A"


def 取动态词(号: int) -> str:
    return 词表.get(号, "")


词表: dict[int, str] = {

    # ── 1 神抬起枪 ────────────────────────────────────────────────
    1: (
        "The camera begins low, pressed almost against the wet roof of the black "
        "sedan, then tilts up with large amplitude at fast speed, sweeping from the "
        "car roof all the way up to the head of the god, and keeps going until his "
        "head is nearly cut off by the top edge of the frame. "

        "On screen: a colossal armoured figure standing on the roof of the black "
        "sedan. He is more than three times the height of a man: the car roof reaches "
        "only his belt, the street lamps come up only to his shoulders, and the heads "
        "of the people below would not reach his knee. His head is a single seamless "
        "cast shell of dark gold metal with no facial features at all - no eye sockets, "
        "no nose, no mouth - broken only by one narrow vertical slit in the centre of "
        "the forehead, and inside that slit burns a single golden eye like a heated "
        "lamp, throwing two shafts of gold light through the rain. Six curved horns "
        "sweep backwards from the shell. His armour is oxidized near-black gold, "
        "matte, cast rather than riveted, scaled in overlapping plates with faint gold "
        "light in the seams; there is no blood, no red, no rust and no damage anywhere "
        "on it. A heavy dark blue cloak, soaked through, whips sideways in the wind "
        "and falls out of frame. He holds Gungnir, a spear whose shaft is twisted "
        "branch and whose head is a thin inward-curving arc like the tail of a meteor. "

        "He raises the spear from his side and levels the point down towards the "
        "sedan; the movement is slow and continuous, and the rain hissing off the "
        "blade turns to steam. On both sides of the car, a crowd of identical "
        "black-robed figures steps forward in unison, one single pace, and the "
        "standing water explodes outward from under their bare feet in a ring. "
        "Behind them, out of focus, the hooves of an enormous pale horse come down on "
        "the asphalt; the surface cracks open and slabs of it lift and tumble. "

        + _锚 + " " + _质感 + " " + _音 + " " + _乐
    ),

    # ── 2 黑影压上 ────────────────────────────────────────────────
    2: (
        "The camera stays very low, almost at the surface of the water, and trucks "
        "left with large amplitude at fast speed straight through the legs of the "
        "advancing crowd, moving at exactly the pace of their walk. "

        "On screen: a long rank of identical black-robed figures walking forward "
        "through ankle-deep water. Their robes are ankle-length, matte black, soaked "
        "and heavy, dragging through the water and clinging to their legs. They are "
        "completely bald - no long hair, no fringe, no topknot, no hood, no hat - and "
        "their faces are real human faces, bloodless pale, with every feature clearly "
        "visible and no mask, no bandage, no veil and no hood covering them. Their "
        "expressions are entirely blank, like people asleep with their eyes open. "
        "Their irises are a dull flat gold, unfocused, like small lamps set in the "
        "eye sockets. They differ in apparent age and sex, yet their bearing is "
        "identical, as if one body had been copied many times. "

        "They advance one rank at a time, and each footfall punches a shallow crater "
        "into the standing water that spreads outward and overlaps the next. The "
        "camera skims across the surface between their legs; their reflections and "
        "the reflections of the street lamps smear and break apart in the ripples. "
        "From the right edge of frame, the forelegs of an enormous pale horse with "
        "riveted dark iron plate bolted directly onto its hide enter the shot; its "
        "dark gold hooves strike the asphalt and send a shockwave through the water "
        "that throws spray across the lens. "

        + _锚 + " " + _质感 + " " + _音 + " " + _乐
    ),

    # ── 3 推开儿子 ────────────────────────────────────────────────
    3: (
        "The camera pans right with large amplitude at fast speed, tracking the "
        "boy's stumble across the frame, and comes to rest on the instant he turns "
        "his head. Handheld, with visible weight and a little roll. "

        "On screen: a Chinese man of about forty, lean and hard, high cheekbones, "
        "dark stubble, cropped hair soaked flat to his skull, in a long black "
        "raincoat heavy with water, a narrow slightly curved longsword with a matte "
        "unreflective blade in his right hand. Beside him a Chinese boy of about "
        "fifteen, pale, wet black hair stuck to his forehead, in a dark navy school "
        "shirt, soaked through. Both at true adult human proportions, head-to-body "
        "about one to seven and a half. Behind them a black luxury sedan with one "
        "door hanging open and its headlights cutting two white cones through the "
        "downpour. "

        "The man grabs the boy by the shoulder and shoves him hard towards the car; "
        "the boy staggers two full steps sideways through the water, throws one hand "
        "out and catches the edge of the open door, and turns his head back. In the "
        "same continuous movement the man pivots away from the car to face the god, "
        "and his soaked coat hem swings out behind him in a wide arc, throwing a "
        "sheet of water off the fabric. Rain strikes the car roof and bursts into "
        "fine mist, and the open door rocks slightly on its hinge. "

        "The man's jaw is set and his eyes are quiet; the boy's eyes are wide and "
        "his mouth is open. "

        + _锚 + " " + _质感 + " " + _音 + " " + _乐
    ),

    # ── 4 父亲冲向神 ──────────────────────────────────────────────
    4: (
        "The camera trucks left with large amplitude at fast speed, holding pace "
        "with the running man so that he stays in the same part of the frame while "
        "the street lamps in the background streak into long horizontal smears of "
        "motion blur. Low angle. "

        "On screen: the man in the long black raincoat, soaked and heavy, the long "
        "narrow sword in his right hand, sprinting. Ahead of him and growing larger, "
        "the colossal armoured god: seamless dark gold head with no face, one narrow "
        "vertical slit in the forehead holding a single burning golden eye, six horns "
        "sweeping back, oxidized near-black gold scale armour, dark blue cloak, the "
        "twisted-branch spear Gungnir held across his body. Between them, black-robed "
        "figures with pale blank faces and dull gold eyes. "

        "The man drops his centre of gravity and drives forward, passing between two "
        "of the black-robed figures; every stride punches a continuous string of "
        "water craters out from under his shoes, and the spray hangs in the air "
        "behind him. He swings the sword up and across, and the wet blade draws a "
        "long silver arc through the rain, water flying off it in a line. In the "
        "depth of the frame the point of Gungnir begins to press downward, and the "
        "rain around it bends away. "

        "His teeth are clenched and his eyes are locked forward. "

        + _锚 + " " + _质感 + " " + _音 + " " + _乐
    ),

    # ── 5 星雨 ────────────────────────────────────────────────────
    5: (
        "The camera arcs around the lone figure with large amplitude at fast speed, "
        "half-circling him so that the highway sweeps past behind and the lamps smear "
        "into long bands, and shakes strongly on every impact. "

        "On screen: the man in the long black raincoat alone in the middle of the wet "
        "highway, the narrow longsword held across his body. The god who is striking "
        "at him is far too large to fit into the frame and is never visible - only his "
        "weapon's light enters the picture. "

        "Gungnir strikes from somewhere outside the top of the frame. In an instant it "
        "thrusts countless times, and each thrust leaves a thin dark gold arc of light "
        "hanging in the air, so that within a second a dense net of curved golden lines "
        "has been woven all around the man, slashing down from above like a rain of "
        "falling stars. The man folds sideways, drops under one arc, rolls through the "
        "water and comes up with the longsword braced across his body; the arcs meet "
        "the blade and bursts of orange sparks scatter and die in the rain. The "
        "pressure of the exchange pushes the downpour outward, opening a clear dry "
        "circle on the asphalt around his feet, its rim boiling with spray. "

        "His face is rigid and his eyes never leave a point just outside the top of "
        "the frame. "

        + _锚 + " " + _质感 + " " + _音 + " " + _乐
    ),

    # ── 6 跃斩与坠落 ──────────────────────────────────────────────
    6: (
        "The camera tilts up with large amplitude at fast speed to follow the leap "
        "all the way to its apex, then drops suddenly and shakes violently as the "
        "body comes down. "

        "On screen: the man in the black raincoat, the longsword gripped in both "
        "hands above his head, and the colossal armoured god towering over the scene "
        "- seamless dark gold head with no face, one narrow vertical slit in the "
        "forehead holding a single burning golden eye, six horns swept back, "
        "oxidized near-black gold scale armour, dark blue cloak, Gungnir. Below "
        "them, black-robed figures with pale blank faces and dull gold eyes, and "
        "the black sedan on the wet road. "

        "The man plants one foot on the shoulder of a black-robed figure and launches "
        "himself straight up, coat streaming behind him, water shedding off the "
        "fabric in a trail. At the top of the arc he brings the sword down in a single "
        "committed cut; the edge bites into the god's shoulder plate and a line of "
        "dark gold sparks sprays out and falls. Gungnir sweeps across in answer, and "
        "the man is thrown clear off his feet and out through the air; blood leaves "
        "his back in a long unbroken line that hangs in the rain, and he falls "
        "towards the asphalt. "

        "In the air his mouth is open and his eyes are wide. "

        + _锚 + " " + _质感 + " " + _音 + " " + _乐
    ),

    # ── 7 拍下启动键 ──────────────────────────────────────────────
    7: (
        "The camera pushes in with large amplitude at fast speed from outside the "
        "windscreen, through the streaming glass, all the way in to the boy's face. "

        "On screen: the interior of the black luxury sedan, seen through a "
        "windscreen completely covered in running rain. The dashboard lights up in "
        "cold blue. The seats are dark leather, beaded with water. A Chinese boy of "
        "about fifteen, pale, wet black hair flat on his forehead, in a dark navy "
        "school shirt soaked through, at true human proportions. "

        "He throws himself into the driver's seat, water flicking off his sleeves, "
        "and brings one hand down flat on the centre console; the engine catches and "
        "the whole car shudders, the needles on the dashboard sweeping up. With his "
        "other hand he grabs the wheel. He twists his head to look back through the "
        "rear window, and rain runs down the inside of the glass in fast threads. "
        "The wipers throw themselves across the windscreen and for a moment the view "
        "outside is clear: the god standing in the road, one golden eye burning in "
        "the dark. "

        "His face is covered in water, his lips tremble, and his eyes change from "
        "fear into something decided. "

        + _锚 + " " + _质感 + " " + _音 + " " + _乐
    ),

    # ── 8 倒冲出雨幕 ──────────────────────────────────────────────
    8: (
        "The camera whips left with large amplitude at fast speed, staying with the "
        "reversing car so that the background tears into long horizontal bands of "
        "motion blur. Low angle, close to the road surface. "

        "On screen: the black luxury sedan reversing violently out of the scene, "
        "red tail lights dragging two long wet streaks across the flooded asphalt. "
        "The rain is so heavy it reads as a hanging sheet, like a membrane stretched "
        "across the road, and the car's body punches through it and tears it open. "
        "Water explodes off the tyres in white sheets and the tyres briefly lose "
        "grip and spin, throwing up smoke. Far back in the depth of the frame, "
        "reduced and half-dissolved in the fog, the colossal armoured god stands "
        "motionless on the road; of his whole body only the single burning golden "
        "eye in the vertical slit of his faceless head stays readable, a hard point "
        "of light that does not move as everything else blurs away. "

        + _锚 + " " + _质感 + " " + _音 + " " + _乐
    ),
}
