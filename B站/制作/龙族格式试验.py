# -*- coding: utf-8 -*-
"""龙族 · 提示词格式 A/B 试验

目的：验证「官方三字段骨架 + 单一运镜」是否比现行写法（多运镜自由文本）
      ① 运动量不下降  ② 场景不漂移

甲 = 现行写法（龙族词表.py 里镜 05 的原文，一条里叠了 tilt up + pull back）
乙 = 官方三字段骨架（I2VA 首行对齐句 + integrated_multimodal_description
                     + overall_soundscape + non_diegetic_music），只写一个主运镜

用法：
    python 龙族格式试验.py             # 只出提示词，不跑 GPU
    python 龙族格式试验.py --跑        # 真跑两条
    python 龙族格式试验.py --量        # 量已生成的两条的运动量
"""
import os
import sys

根 = r"D:\DSHworkspace\B站\成片\龙族\试验"
首帧 = os.path.join(根, "05b_八足马.png")
种子 = 8801

# ─────────────────────────── 甲：现行写法 ───────────────────────────
甲 = (
    "Cinematic extreme wide shot, dramatic low angle looking steeply upward. The "
    "fog on the elevated expressway splits apart and reveals a horse so enormous "
    "that it is not fully contained by the frame: only its body, its neck and its "
    "legs are visible. Its coat is a pale, almost grey-white colour, soaked flat "
    "by the rain so that the heavy musculature shows through the wet hair. It "
    "wears a heavy harness of chased metal armour, and that armour is oxidised "
    "black iron and bronze covered in scratches, dents and rust, strapped to the "
    "animal with dark leather, with rainwater running down between the plates. It "
    "has eight legs, planted at different angles like the hydraulic outriggers "
    "that stabilise a heavy crane, and its dark gold hooves have driven deep into "
    "the asphalt, tearing open one wound after another in the road surface and "
    "kicking broken chips of stone up into the air where they hang suspended. A "
    "metal faceplate covers its head, and from the nostril openings of that "
    "faceplate fine crackling sparks of electricity spray out, lighting the "
    "underside of its jaw. Its eyes are dark red with vertical slit pupils. It "
    "throws its head back and screams, and the scream is so deep it reads as "
    "thunder rather than a horse. Rain and fog fill the rest of the frame. "
    "CAMERA: an extremely low camera looking almost straight up from beneath the "
    "horse; it starts on the hooves and the torn asphalt, tilts slowly upward "
    "along the legs and body, and then pulls back slightly to reveal how "
    "impossibly large the animal is. "
    "Keep the photoreal live-action look. "
    "No dialogue, no narration, no music, ambient sound only."
)

# ───────────────────── 乙：官方三字段骨架（I2VA） ─────────────────────
乙 = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced.\n"
    "\n"
    "integrated_multimodal_description: [Shot 1] Photoreal live-action night "
    "exterior on an elevated expressway in heavy rain, anamorphic widescreen. "
    "A colossal horse stands in the fog, so large that the frame cannot contain "
    "it: only its body, its neck and its eight legs are inside the picture. Its "
    "coat is pale grey-white and soaked flat by the rain, so the heavy "
    "musculature reads through the wet hair. It wears a harness of chased metal "
    "armour - oxidised black iron and bronze, scratched, dented and rusted - "
    "strapped on with dark leather, rainwater running between the plates. Eight "
    "legs plant at different angles like the hydraulic outriggers of a heavy "
    "crane. Its dark gold hooves have driven deep into the asphalt, tearing open "
    "wound after wound in the road and kicking broken stone chips into the air, "
    "where they hang suspended in the rain. A metal faceplate covers its head, "
    "and from the nostril openings of that faceplate fine crackling sparks of "
    "electricity spray out and light the underside of its jaw. Its eyes are dark "
    "red with vertical slit pupils. It throws its head back and screams, a sound "
    "so deep it reads as thunder rather than as a horse. Torn asphalt, falling "
    "rain, drifting fog and the wet dark road fill the rest of the frame. The "
    "colour palette is cold blue-black with the only warm notes coming from the "
    "gold hooves and the electric sparks. The camera tilts up with large "
    "amplitude at slow speed, starting on the torn asphalt and the hooves and "
    "rising along the legs to the full height of the animal. The shot stays on "
    "the same horse in the same place and does not cut. "
    "No narration of the prompt text. No text overlay. Characters do not speak "
    "any line that is not enclosed in <d>...</d>.\n"
    "\n"
    "overall_soundscape: Heavy rain falling on asphalt and on metal armour. A low "
    "continuous wind across the open expressway. Stone chips ticking and scraping "
    "as they land on wet road. A deep, thunder-like animal bellow rolling out "
    "through the fog, with a faint electric crackle layered under it.\n"
    "\n"
    "non_diegetic_music: N/A"
)


def 出提示词() -> None:
    for 名, 文 in (("甲 现行写法", 甲), ("乙 官方三字段", 乙)):
        print("=" * 70)
        print(f"{名}   {len(文)} 字符")
        print("=" * 70)
        print(文)
        print()


def 跑() -> None:
    from MiniMax动态 import 出动态
    import shutil

    if not os.path.isfile(首帧):
        print(f"⛔ 找不到首帧 {首帧}")
        return
    for 名, 文 in (("甲", 甲), ("乙", 乙)):
        出 = os.path.join(根, f"F_{名}_八足马.mp4")
        if os.path.isfile(出) and os.path.getsize(出) > 102400:
            print(f"  ↷ {名} 已有")
            continue
        print(f"\n── {名} ── 提示词 {len(文)} 字符")
        出动态(首帧, 文, "", 出, 种子=种子,
               主体="a colossal eight-legged armoured horse")


def 量() -> None:
    import av
    import numpy as np

    print(f"{'组':<6}{'平均帧间差':>12}{'P90':>10}{'峰值':>10}")
    for 名 in ("甲", "乙"):
        路 = os.path.join(根, f"F_{名}_八足马.mp4")
        if not os.path.isfile(路):
            print(f"{名:<6}  ✗ 没有 {路}")
            continue
        c = av.open(路)
        s = c.streams.video[0]
        上 = None
        差 = []
        for f in c.decode(s):
            a = np.asarray(f.to_image().convert("L"), dtype=np.float32)
            if 上 is not None:
                差.append(float(np.abs(a - 上).mean()))
            上 = a
        c.close()
        d = np.asarray(差, dtype=np.float32)
        print(f"{名:<6}{d.mean():>12.2f}{np.percentile(d,90):>10.2f}{d.max():>10.2f}")
    print("\n（对照：光明顶甲 5.78 / 乙 5.90 / 丙 31.96）")


if __name__ == "__main__":
    if "--跑" in sys.argv:
        跑()
    elif "--量" in sys.argv:
        量()
    else:
        出提示词()
