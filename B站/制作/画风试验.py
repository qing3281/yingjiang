# -*- coding: utf-8 -*-
"""背景画风 A/B/C 试片 —— 用户 m03304 给了两条路，都试一遍给他挑。

用户原话：
> 「我说的不要融入背景是不要融入背景的画风，或者你可以给背景换一个贴合人物动漫形象的画风，
>   或者你可以试着转下仿3d的」

所以做三版同样的画面，只是画风不同：
  A 动画背景美术   —— 角色赛璐璐 + 背景也动画化（吉卜力/新海诚那种手绘背景），两边同为 2D
  B 仿 3D          —— 角色和背景都做成赛璐璐渲染的 3D 动画质感（原神/《我推的孩子》3D 那种）
  C 拼贴合成       —— 角色单独白底出，抠图后贴到背景上，画风彻底不互相污染

三张都用同一个分镜：Q 版鲸鱼娘站在黄昏的中国老街中间。
"""
from __future__ import annotations

import os

from PIL import Image

from 出镜_Qwen参考 import 跑, 参考根

出根 = r"D:\DSHworkspace\B站\成片\不烧心\画风试验"
参考_DS = os.path.join(参考根, r"净版\DS_Q版_立绘.png")

景 = "黄昏的中国老街道，青石板路，两侧木质门面铺子，红灯笼，远处有雾"

风格词 = {
    "A_动画": (
        "整张图是日本电视动画的一帧。角色和背景都用同一种手绘动画画风："
        "角色是赛璐璐上色（粗黑描边 + 平涂色块 + 两段式阴影），"
        "背景是日本动画背景美术（手绘水彩/水粉质感，柔和的笔触，不写实，不摄影感，"
        "像吉卜力或新海诚动画里的街道背景）。"
        "整张图是平的 2D，没有任何 3D 渲染感，没有照片质感。"
    ),
    "B_仿3D": (
        "整张图是日本 3D 动画（卡通渲染 / cel-shaded 3D）的一帧，"
        "像《原神》或《我推的孩子》里那种 3D 动画质感："
        "角色和背景都是 3D 模型渲染出来的，表面是干净的平涂色块 + 明确的卡通描边，"
        "有柔和的全局光照和轻微的环境光遮蔽，材质是哑光的卡通材质，不写实。"
        "注意：是「卡通渲染的三维动画」，不是真人电影，不是写实渲染。"
    ),
}


def 出(风格名: str, 词: str, 种子: int) -> str | None:
    os.makedirs(出根, exist_ok=True)
    print(f"\n=== 风格 {风格名} ===")
    r = 跑([参考_DS], 词, 种子=种子, 宽=1536, 高=864, 高质量=True)
    if not r:
        return None
    im = Image.open(r).convert("RGB")
    p = os.path.join(出根, f"{风格名}.png")
    im.save(p)
    print(f"✓ {p}")
    return p


def main() -> int:
    if not os.path.isfile(参考_DS):
        print("❌ 缺参考图", 参考_DS)
        return 1

    底 = f"{景}。画一个 Q 版二头身的小女孩站在街中间，双手叉腰得意地笑，中景。"

    for i, (名, 风) in enumerate(风格词.items()):
        出(名, f"{底}\n\n【画风要求，最重要，必须严格遵守】{风}"
               f"\n\n人物设计完全照参考图1：深蓝到浅蓝的渐变长发、白色蕾丝女仆头饰、"
               f"头两侧的蓝色鲸鳍耳、深蓝女仆裙配白色围裙、身后一条鲸尾。"
               f"人物要圆滚滚胖乎乎的 Q 版比例。画面里只有她一个人。",
           种子=7001 + i * 7)

    # 拼一张对比图
    fs = [os.path.join(出根, f"{n}.png") for n in 风格词]
    fs = [f for f in fs if os.path.isfile(f)]
    if fs:
        W = 1280
        ims = [Image.open(f).convert("RGB") for f in fs]
        ims = [i.resize((W, int(W * i.height / i.width)), Image.LANCZOS) for i in ims]
        sh = Image.new("RGB", (W, sum(i.height for i in ims) + 16 * (len(ims) - 1)),
                       (16, 16, 20))
        y = 0
        for i in ims:
            sh.paste(i, (0, y))
            y += i.height + 16
        o = r"D:\DSHworkspace\_画风对比ABC.png"
        sh.save(o)
        print(f"\n✅ 对比图 → {o}  {sh.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
