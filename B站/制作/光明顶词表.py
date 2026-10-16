# -*- coding: utf-8 -*-
"""《光明顶》35 镜动态提示词表 —— **全英文**。

两条铁律（都从《不烧心》的坑里换来的）：

  ① **全英文**。中文会被 MiniMax 语音模型当成台词念出来。
  ② **必须写显式摄影机运动**。实测：只把动作写细没用（5.78→5.90），
     把摄影机写进去才有量级跳变（→31.96，5.5 倍）。
     每一条都要有 whip / crane / dolly / orbit / push in / shake 这类词。

另外每条都要带：衣料与发丝二次运动、环境反应（尘雪火）、结尾定住。
战斗片全程丢弃模型音轨，所以提示词写长不亏——不会被念出来。
"""

动态词表: dict[int, str] = {

1: (
    "An empty stone plaza dawns in deep blue before sunrise. "
    "The camera starts very low near the wet flagstones and cranes slowly upward, "
    "rising past broken stone railings and guttering bronze braziers whose embers glow orange, "
    "then keeps climbing until the vast Ming Cult hall and the far snow peaks swing into frame. "
    "Thin smoke drifts sideways across the lens and shreds apart in the wind. "
    "Scattered weapons, torn banners and dropped swords lie on the ground, "
    "and loose snow skitters low across the stones in fast streaks. "
    "The camera slows to a halt at the top of the crane and holds, everything settling into stillness. "
    "Cold cyan and warm ember orange, volumetric haze, cinematic wide shot."
),

2: (
    "Hundreds of martial artists in six different robe colours stand massed in square formations "
    "filling the plaza, weapons angled up like a steel forest. "
    "The camera flies forward low and fast over the front rank, skimming just above the blades, "
    "then banks and rises over the crowd, revealing rank after rank stretching to the horizon. "
    "The foremost disciples' faces tighten as the camera sweeps past them. "
    "Robe hems, sash ends and loose hair snap and stream in the mountain wind. "
    "Dust lifts in a long rolling wave from under their boots and trails behind the camera. "
    "The camera crests the formation and decelerates, holding on the frozen army. "
    "Overcast grey light, cold steel tones, epic scale."
),

3: (
    "Wounded Ming Cult people lie broken across the stone steps - Yang Xiao on one knee clutching a "
    "shattered sword with blood soaking through his white robe, Wei Yixiao flat on his side, "
    "the Five Wanderers slumped in a row against the railing. "
    "The camera drifts sideways in a slow lateral dolly past each of them in turn, "
    "then dips down and tilts up into a low angle that makes them loom and the sky behind them burn. "
    "Blood drips from a blade tip and taps the stone. "
    "Torn cloth flutters weakly in the wind. "
    "One man's chest rises and falls hard; another's fingers twitch against the flagstone. "
    "Ash and fine snow drift through the frame between the camera and the bodies. "
    "The camera settles into the low angle and stops, holding on the ruin. "
    "Desaturated grey with dull red accents, sombre, heavy."
),

4: (
    "The old nun in grey stands over the fallen, raising her ancient sword two-handed above her head. "
    "The camera starts tight on her thin lips and hard eyes, then whips down and around to a low angle "
    "behind her shoulder as the blade comes up, then pushes in hard as the sword reaches full height. "
    "The blade clears its scabbard and a cold blue-white gleam runs along the steel edge. "
    "Her grey robe snaps taut and the hem lashes outward; the prayer beads swing hard against her chest. "
    "Grit and snow blast away from her feet in a ring. "
    "The camera shakes once on the moment the blade locks overhead, then holds absolutely still. "
    "Cold blue-white key light against dark grey, terrifying stillness."
),

5: (
    "Extreme close-up of cracked plaza flagstones. "
    "The camera is pressed right down against the stone, then shakes violently as the cracks widen - "
    "the stones heave, split and burst upward toward the lens while the camera recoils back and up. "
    "A column of dirt, gravel and shattered rock erupts into the air in slow motion, "
    "each chunk tumbling and spinning as it flies. "
    "A huge dust cloud boils outward and rolls across the lens, blotting out the frame for an instant. "
    "Small pebbles rain back down and bounce off the stones. "
    "The camera pushes back in through the settling dust and holds on the new hole. "
    "Backlit by pale sun, dust motes blazing, violent."
),

6: (
    "A young man in a torn white robe erupts straight up out of the broken ground in an explosion of "
    "rubble, landing in a deep crouch, then rises to full height and straightens slowly. "
    "The camera starts buried in the dust cloud at ground level, then cranks up and back into a low "
    "hero angle as he ascends, and finally cranes upward past him to the sky. "
    "Dirt and stone spray outward in an arc and clatter down around him. "
    "His robe billows and cracks like a flag; his loose hair and white headband stream straight back. "
    "A faint golden shimmer crawls over his forearms and fades. "
    "The camera finishes its crane and holds him against the clouds. "
    "Golden rim light against cold blue, dust glittering, heroic."
),

7: (
    "Hundreds of heads turn at once toward the newcomer. "
    "The camera whips fast to the right across the packed ranks, catching face after face snapping "
    "around, then brakes hard and pushes in on the old nun as her eyes narrow. "
    "Weapons swing up off shoulders in a ragged wave and clash against each other. "
    "Robe sleeves and hair whip sideways with the turn. "
    "Dust puffs up from stamping boots along the entire line and drifts across the frame. "
    "The camera stops dead on her face and holds. "
    "Cold grey daylight, tension, sharp."
),

8: (
    "The young man in white plants his feet, folds his hands into a cupped salute and bows his head "
    "slightly toward the gathered sects. "
    "The camera arcs around him in a slow quarter-circle from his front to his side, "
    "then eases down to a calm medium close-up and stops. "
    "His sleeves fall back along his forearms as his hands come together. "
    "The frayed hem of his robe settles around his boots. "
    "A thin curl of dust lifts from under his feet and drifts away sideways. "
    "His expression stays calm and open. "
    "Soft overcast light, still air, respectful."
),

9: (
    "A stout grey-bearded fighter in brown robes drops into a fighting stance, fists cocked, "
    "and drives forward off his back foot. "
    "The camera pulls back fast ahead of him as he charges, keeping him dead centre, "
    "then drops into a low tracking angle so his boots pound toward the lens. "
    "He throws a heavy straight punch and the camera shakes on the impact frame. "
    "His robe flares out behind him and his beard whips back. "
    "Dust bursts up from each footfall in hard little puffs that hang in the air behind him. "
    "The camera stops retreating and holds as his fist fills the frame. "
    "Warm brown and grey tones, aggressive forward energy."
),

10: (
    "The young man raises one open palm to meet the incoming punch, and a brilliant golden aura "
    "detonates around his whole body. "
    "The camera slams into a low angle looking up past his palm, shakes hard on the instant of contact, "
    "then pushes in fast through the blast of light onto his face. "
    "Ripples of golden energy spiral up his arm and burst outward in rings. "
    "His robe and hair are blown straight back by his own power; his sleeves snap and crack. "
    "A shockwave flattens the dust on the ground into a spreading ring and whips up a spray of grit. "
    "The camera steadies out of the shake and locks onto his eyes. "
    "Blinding gold against cold blue, lens flare across the frame, immense power."
),

11: (
    "The stout fighter is blasted backwards off his feet, arms flailing. "
    "The camera tracks him hard as he flies, whipping sideways to keep him framed, "
    "then cranes up as he arcs through the air. "
    "His body tumbles once, robe flapping wildly and beard streaming. "
    "He ploughs into a stone railing and shatters it into flying blocks. "
    "Dust and stone chips spray across the lens. "
    "The camera decelerates and drops with him into a low angle as he sprawls on the flagstones. "
    "Fragments clatter and roll to a stop around him. "
    "Warm dust haze, impact, kinetic."
),

12: (
    "A pale, thin-faced man in dark robes flicks his wrist sideways and a cloud of fine white powder "
    "hisses off his fingertips toward the young man's face. "
    "The camera snaps in tight on his fingers, then whips sideways with the powder cloud, "
    "following it through the air, and slams to a stop on the young man's eyes. "
    "The powder sparkles and spreads in a curling stream. "
    "The thrower's wide sleeve snaps and the prayer beads at his throat swing hard. "
    "The powder catches the light as a glittering haze. "
    "The young man turns his head aside and the cloud shreds past his cheek. "
    "Cold light, sickly green cast, treacherous."
),

13: (
    "The young man sweeps both arms outward and a slow spiral of pale light coils into being around "
    "his body, warping the air. "
    "The camera orbits him fast in a tightening circle, then rises into a high angle looking down "
    "as the spiral turns beneath him, then drops back down to eye level in one continuous move. "
    "The light bends the falling dust and snow into a ring that rotates around him. "
    "The powder cloud is caught in the spiral and whirled back the way it came. "
    "The camera shakes once as the spiral snaps taut, then holds. "
    "Pale violet and white light, reality bending at the edges."
),

14: (
    "The thrown powder reverses, whirling back into the thrower's own face. "
    "The camera follows it in a fast whip pan back across the plaza and lands hard on him. "
    "He staggers, clawing at his own throat with both hands, eyes bulging. "
    "His dark robes twist around him as he spins; the prayer beads snap and scatter. "
    "A burst of dust and gravel kicks up around his stumbling boots. "
    "The camera pushes in as he goes down to one knee, then holds. "
    "Harsh cold light, cruel irony, tight."
),

15: (
    "Two swordsmen flank the young man and attack together - one high, one low - "
    "their blades leaving bright arcs of light across the frame. "
    "The camera cranes up and back into a high wide angle, revealing the two of them circling him "
    "in perfect symmetry, then banks sideways to show the crossing blade trails. "
    "Blue-white sword energy sweeps out in long curved ribbons through the air. "
    "Blue and white robes stream outward with the spin; hair whips across faces. "
    "Dust lifts in a wide ring around all three of them, turning slowly. "
    "The camera settles and holds on the frozen triangle. "
    "Cold blue-white glow, geometric, elegant."
),

16: (
    "The young man walks straight forward into the crossing swords, weaving between the blades with "
    "tiny unhurried steps, and the steel passes so close it parts his hair. "
    "The camera tracks beside him at shoulder height as he walks, then tilts down to his feet "
    "and back up to his face without ever stopping. "
    "Blade trails slice the air right in front of the lens in bright streaks. "
    "His torn robe whips and snaps as the swords pass; strands of his hair fall away. "
    "Dust rises in a thin line from his footsteps. "
    "The camera keeps pace and holds on his calm expression. "
    "Shafts of pale light, deadly grace, unhurried."
),

17: (
    "The young man plants one palm on the ground and sweeps a wide circle with his leg, "
    "sending out a flat shockwave that blasts both swordsmen off their feet. "
    "The camera drops to floor level as he plants his palm, then whips in a fast 180-degree arc "
    "around him with the sweep, and finally cranks up into a high angle as they fly. "
    "A ring of dust and stone chips expands outward across the whole plaza. "
    "Both men's robes balloon and stream as they leave the ground. "
    "The camera shakes hard on the sweep and then holds. "
    "Warm golden light against cold grey, wide and violent."
),

18: (
    "A stocky old monk in yellow lunges in low with both hands hooked into rigid claws, "
    "fingers spread, and drives a claw strike at the young man's throat. "
    "The camera pushes in fast on the claw then whips around to a side angle as the strike passes, "
    "then settles into a tight two-shot. "
    "His sleeves are bound tight and his thick forearms bunch with each move; "
    "the yellow robe hem snaps with every lunge. "
    "A sharp crack of displaced air puffs dust off the flagstones beneath them. "
    "The camera holds steady on the two locked figures. "
    "Warm gold and dusty yellow, sharp and heavy."
),

19: (
    "The young man mirrors the old monk exactly - the same hooked claws, the same low lunge - "
    "and the two sets of clawed hands meet and lock in the centre of the frame. "
    "The camera whips between the two faces in fast alternating cuts of movement, "
    "then snaps wide to a symmetric two-shot, then pushes in on the locked hands. "
    "Two sets of sleeves crack outward at the same instant. "
    "A ring of dust blows out flat from between their feet. "
    "The camera shakes once on the lock and freezes. "
    "Warm gold light, mirrored motion, perfectly matched."
),

20: (
    "The old monk's eyes go wide and his hands slowly drop to his sides. "
    "The camera pushes in very slowly on his face from a low angle, then holds. "
    "His white eyebrows tremble; a bead of sweat runs down his temple. "
    "His yellow robe settles and the hem stops swinging. "
    "A single puff of dust drifts up past the lens between the camera and his face. "
    "Nothing else in the frame moves. "
    "Warm gold rim light, absolute stillness, disbelief."
),

21: (
    "A tall thin taoist in blue-grey steps forward, sweeps both hands up and outward in a slow "
    "circle, and a soft grey-white sphere of light turns into being between his palms. "
    "The camera circles him slowly at chest height, then cranes up and over to look down into "
    "the turning sphere, then drifts back down to his face. "
    "His long sleeves and three-strand beard drift sideways as if in water. "
    "Loose dust on the flagstones lifts and orbits slowly around his feet. "
    "The camera comes to rest and holds on the sphere. "
    "Soft grey-white light, rippling air, calm and vast."
),

22: (
    "The young man answers with the same circling motion and the two spheres of light face each other "
    "across twenty paces, turning in opposite directions. "
    "The camera rises into a high wide angle showing both men and the space between them, "
    "then dollies slowly forward down the middle of that gap. "
    "Both sets of robes and beards stream sideways, drawn toward the centre. "
    "Dust all across the plaza lifts and spirals inward. "
    "The camera shakes gently and holds between the two spheres. "
    "Grey-white light, mirror symmetry, immense quiet pressure."
),

23: (
    "Both spheres are driven together and detonate in a dome of white light that swallows the plaza. "
    "The camera whips back fast and shakes violently as the blast front races toward it, "
    "then cranes up over the expanding dome. "
    "A flat disc of dust and stone blasts outward in every direction, flipping flagstones end over end. "
    "Both men's robes are torn straight back and their hair blows flat. "
    "The dome rolls outward, picks up snow and debris, and keeps growing. "
    "The camera steadies and holds on the settling cloud. "
    "Blinding white core, grey shockwave ring, overwhelming."
),

24: (
    "The old nun tears the ancient sword from its scabbard and levels it at the young man; "
    "cold blue-white light floods out along the blade. "
    "The camera starts tight on her hand on the hilt, then cranks up into a steep upward angle as the "
    "blade clears, then pulls back fast to reveal the young man small at the far end of the point. "
    "Her grey robe is blown back by the sword's own light and the hem cracks like a whip. "
    "Frost crystals form on the flagstones in a spreading line under the blade. "
    "The camera stops and holds on the levelled sword. "
    "Cold blue-white light, dread, absolute."
),

25: (
    "The old nun cuts the air in fast precise arcs and crescent-shaped blades of light fly off the "
    "sword toward the young man, one after another. "
    "The camera whips sideways to follow the first crescent, then pans rapidly back and forth "
    "between the two of them as more fly, then pushes in behind the young man's shoulder. "
    "Each crescent leaves a lingering trail of frost in the air. "
    "Her robes snap with every cut; her sleeves stream. "
    "Frost spreads across the stones and small ice shards skitter along the ground. "
    "The camera holds on the young man as the light fills the frame. "
    "Cold blue-white, slicing, relentless."
),

26: (
    "The young man braces, throws both palms forward and lets out everything he has; "
    "a vast golden aura roars up around him and the air itself bends. "
    "The camera drops to a low angle at his feet, then pushes in fast through the golden light "
    "straight onto his face while shaking hard. "
    "Rings of gold energy blast off his shoulders and stream upward. "
    "His robe and hair are ripped straight back by the force. "
    "The flagstones under his boots crack and dust explodes outward in a ring. "
    "The camera keeps pushing in and holds on his straining eyes. "
    "Blinding gold, wind, maximum effort."
),

27: (
    "Palm and sword meet in the centre of the plaza and the impact tears the world apart; "
    "a vertical column of light erupts between them and the ground splits open. "
    "The camera whips around from behind the young man to behind the nun in one fast orbit, "
    "then slams to a stop and shakes violently, then cranks up the column of light to the sky. "
    "Golden and blue-white energies grind against each other in a screaming spiral. "
    "Both figures' robes are shredded straight back and their hair whips wild. "
    "The entire plaza floor shatters and lifts in a storm of stone and dust. "
    "The camera steadies, holds on the two locked figures inside the light. "
    "Colossal, blinding, the whole frame burning."
),

28: (
    "The old nun lowers the sword and lets the point drop to the stones. "
    "The camera pushes in slowly on her face from a level angle, then eases back a step and stops. "
    "Her thin lips press together and her eyes stay on the young man. "
    "The last of the blue-white light drains off the blade and dies. "
    "Frost on the stones turns to water and steams very faintly. "
    "Her grey robe settles and stops moving. "
    "Dust drifts slowly down through the frame and settles. "
    "Cold grey light, exhaustion, a truce."
),

29: (
    "A gaunt grey-robed old monk steps out from behind a broken pillar, hands folded, "
    "a thin, cold smile on his scarred face. "
    "The camera arcs slowly around the pillar with him, revealing him a piece at a time, "
    "then eases in on his eyes and holds. "
    "His wide sleeves hang perfectly still, unnaturally calm. "
    "A faint line of pale dust hangs in the air behind him. "
    "The prayer beads at his neck click once against each other. "
    "Nothing else in the frame moves at all. "
    "Flat cold light, quiet menace."
),

30: (
    "The gaunt monk's arm flashes out from his wide sleeve and a spray of thin dark needles "
    "hisses toward the young man's back. "
    "The camera whips sideways with the needles, tracking them through the air, "
    "then slams to a stop behind the young man's shoulder. "
    "His hanging sleeve snaps outward and the prayer beads swing. "
    "The needles glitter as they cut a thin line of disturbed dust. "
    "The young man begins to turn. "
    "The camera shakes once and holds. "
    "Cold grey, sudden, treacherous."
),

31: (
    "The young man spins, both hands sweeping in a wide circle, and the needle spray stops dead in "
    "the air, turns as one and points back the way it came. "
    "The camera orbits him fast through a half-circle, then rises slightly and holds as the needles "
    "hang frozen. "
    "The needles turn in perfect unison without a sound. "
    "His robe and hair settle slowly as he stops turning. "
    "Every dust mote in the frame hangs motionless. "
    "The camera holds absolutely still. "
    "Pale gold light, frozen moment, turning of the tables."
),

32: (
    "The needles fly home and the gaunt monk is hurled backwards off his feet by his own force, "
    "his wide sleeves blown inside out. "
    "The camera tracks him hard as he tumbles, whipping sideways to stay with him, "
    "then cranes down with him as he hits the flagstones and slides. "
    "His robe wraps and drags; the prayer beads burst and scatter across the stone. "
    "A long plume of dust and gravel rides up behind his slide and hangs in the air. "
    "The camera slows and holds as he comes to rest. "
    "Cold grey dust, ironic, final."
),

33: (
    "The whole plaza goes silent; hundreds of fighters stand frozen, weapons lowered, "
    "snow falling steadily through the frame. "
    "The camera starts tight on a single dropped sword and cranes up and back very slowly, "
    "revealing more and more of the silent crowd, until the whole plaza is in frame. "
    "Snow streaks down past the lens in long soft trails. "
    "Torn banners and robe hems hang motionless in the still air. "
    "A single column of smoke rises straight up in the distance. "
    "The camera finishes its crane and stops completely. "
    "Desaturated cold blue, snowfall, absolute quiet."
),

34: (
    "The wounded Ming Cult people push themselves up onto their knees, then bow their heads "
    "and press their foreheads toward the young man in white. "
    "The camera starts low among them, then rises steadily and pulls back to reveal rank after rank "
    "of kneeling figures, then keeps rising into a high angle. "
    "Bloodied hands press flat against the stones. "
    "Torn robes drag and spread on the flagstones as they kneel. "
    "Dust puffs up lightly around each kneeling body and drifts away. "
    "The camera comes to rest high above and holds. "
    "Warm gold light breaking through cold grey, solemn, wide."
),

35: (
    "The young man in the torn white robe stands alone in the middle of the ruined plaza, "
    "hands at his sides, looking out; snow falls around him and the wind lifts his hem. "
    "The camera pushes in slowly and steadily on him from a wide shot, "
    "passing between the kneeling figures, and does not stop until the frame is tight on his face. "
    "His ruined robe ripples and snaps gently; loose strands of hair across his cheek move. "
    "Snow drifts past the lens and settles on his shoulders. "
    "The camera settles into the close-up and holds, everything going still. "
    "Cold blue with a warm rim light, the calm after, heroic."
),

}

# ─────────────────────────── 取用 ───────────────────────────

def 取动态词(号: int) -> str:
    """取某一镜的英文动态提示词。取不到返回空串（调用方会报错并跳过）。

    表里存的是一条完整字符串（不是《不烧心》那种 (动作, 表情) 二元组），
    因为这一版把「动作 + 摄影机 + 环境反应 + 结尾定住」四段揉成了一句——
    模型是按整段语义生成运动的，分段传反而会丢运镜。
    """
    return 动态词表.get(号, "").strip()


def 全表自检() -> list[str]:
    """跑之前先自检：每一条都得是纯 ASCII、够长、且带运镜词。

    返回问题列表，空列表 = 全过。`做光明顶.py --查词表` 会调它。
    """
    import re

    运镜词 = ("camera", "whip", "crane", "dolly", "orbit", "push in", "pull back",
              "tracking", "tilt", "pan", "zoom", "low angle", "high angle", "shake")
    问题 = []
    for 号 in range(1, 36):
        词 = 取动态词(号)
        if not 词:
            问题.append(f"镜 {号:02d}：词表里没有")
            continue
        坏 = [c for c in 词 if ord(c) > 127 and not (0x2018 <= ord(c) <= 0x201F
                                                    or ord(c) in (0x2013, 0x2014, 0x2026))]
        if 坏:
            问题.append(f"镜 {号:02d}：有非 ASCII 字符 {'、'.join(dict.fromkeys(坏))[:12]}")
        if len(词) < 300:
            问题.append(f"镜 {号:02d}：只有 {len(词)} 字符，太短（会没动作）")
        if not any(w in 词.lower() for w in 运镜词):
            问题.append(f"镜 {号:02d}：没有摄影机运动词（运动量会掉到 1/5）")
    return 问题

