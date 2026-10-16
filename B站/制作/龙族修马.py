# -*- coding: utf-8 -*-
"""重出 05b 八足马首帧 —— 第一版失败（四条腿 / 尺寸正常 / 甲胄变装饰皮具）

失败根因：
  ① 「马」的先验太强，而「八条腿」被埋在句子中段 → 模型按普通马生成
  ② 「大到装不进画面」是抽象描述，模型没有尺度参照 → 画成正常尺寸
  ③ 「chased metal armour」被理解成装饰性压花皮具 → 出来是鞍具而非战甲

修正策略：
  ① 把异常点提到第一句，并用「数腿」的写法强制（EIGHT legs，前四后四）
  ② 给具体尺度锚：护栏只到它膝盖、轿车像玩具、头在画面之外
  ③ 甲胄改用「像军舰装甲一样用螺栓铆在动物身上」，并显式排除鞍具/装饰压花
"""
import os
import sys

根 = r"D:\DSHworkspace\B站\成片\龙族\试验"
出 = os.path.join(根, "05c_八足马.png")

正 = (
    "A horse with EIGHT legs, not four. Count them: four legs at the front of its "
    "body and four legs at the back, planted at different angles like the "
    "hydraulic outriggers that stabilise a heavy crane. "
    "It is impossibly large. The concrete guardrail of the elevated expressway "
    "reaches only to its knees. The black luxury sedan on the road beside it "
    "looks like a toy pushed up against its hoof. Its back is higher than the "
    "streetlamps, and the top of its head is cut off by the upper edge of the "
    "frame. "
    "Its coat is a pale, almost grey-white colour, soaked flat and dark by the "
    "rain so that the heavy musculature shows through the wet hair. "
    "It is armoured the way a warship is armoured: thick plates of oxidised black "
    "iron and bronze bolted and riveted directly onto the animal over heavy dark "
    "leather straps, the plates scratched, dented, gouged and eaten with rust, "
    "rainwater running down between them. There is no saddle, no decorative "
    "tooling and no ornamental filigree anywhere on the harness. "
    "Its hooves are dark gold, and they have driven deep into the asphalt, "
    "tearing open one wound after another in the road surface and kicking broken "
    "chips of stone up into the air, where they hang suspended in the rain. "
    "A corroded metal faceplate covers its head. Fine crackling sparks of "
    "electricity spray out from the nostril openings of that faceplate and light "
    "the underside of its jaw. Its eyes are dark red with vertical slit pupils. "
    "It throws its head back and screams. "
    "Heavy rain falls through a cold blue-black night. Fog drifts across the wet "
    "road. "
    "Photoreal live-action cinema, ARRI ALEXA 65 with anamorphic lenses, "
    "cinematic wide shot from a very low angle on the road surface looking up. "
    "Absolutely not anime, not animation, not illustration, not CG, not a game "
    "render, not a concept painting, not a plastic or toy look."
)

负 = (
    "anime, animation, cartoon, cel shading, illustration, painting, drawing, "
    "CG render, game render, concept art, plastic, toy, figurine, "
    "four legs, normal-sized horse, saddle, ornate tooling, gold filigree, "
    "decorative armour, gleaming polished armour, "
    "text, watermark, logo, signature, caption, subtitle, "
    "daylight, sunny, blue sky, dry road, "
    "extra heads, deformed anatomy, fused legs"
)


def 主() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import 出图_纯文本 as 图

    if os.path.isfile(出) and "--重" not in sys.argv:
        print(f"↷ 已有 {出}（加 --重 覆盖）")
        return 0
    from PIL import Image
    import shutil

    print(f"出首帧 05c_八足马   正向 {len(正)} 字符 / 负向 {len(负)} 字符")
    路 = 图.跑(正, 种子=5511, 宽=1344, 高=768, 负面=负, 静默=False)
    if not 路:
        print("⛔ 出图失败")
        return 1
    shutil.copy2(路, 出)
    print(f"✅ {路} → {出}")
    return 0


if __name__ == "__main__":
    raise SystemExit(主())
