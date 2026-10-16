# -*- coding: utf-8 -*-
"""把七个角色的「最终参考形象图」拼成一页，交用户审核。

用户 m03271：「我要所有人物的最终的参考形象图（豆包有前后两个版本，我把一个参考的发给你了的）」

所以这一页只做一件事：把每个角色的**网上原图**（不经过我重画）摆出来，
标清楚每个角色的造型要点，让用户点头说"就用这个"。
"""
from __future__ import annotations

import base64
import io
import os

from PIL import Image, ImageDraw, ImageFont

参考根 = r"D:\DSHworkspace\B站\情报\AI娘参考图"
出根 = r"D:\DSHworkspace\B站\成片\不烧心"
出图 = os.path.join(出根, "角色最终参考形象.png")
出页 = os.path.join(出根, "角色最终参考形象.html")

字大 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 44)
字中 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 30)
字小 = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 24)

# 每个角色：(名字, 一句话定位, [参考图相对路径...], 造型要点)
角色表 = [
    (
        "DeepSeek 鲸鱼娘",
        "主角之一 · Q 版 · 卖白饭的黑心同行",
        [r"净版\DS_Q版_立绘.png", r"净版\DS_Q版_围裙.png", r"净版\DS_Q版_拿笔.png"],
        [
            "二头身 Q 版，圆滚滚，大脑袋大眼睛",
            "深蓝 → 浅蓝渐变的超长蓬松头发",
            "头两侧一对蓝色鲸鳍耳（像耳朵一样外撇）",
            "白色蕾丝女仆头饰 + 蓝色蝴蝶结 + 卷曲呆毛",
            "深蓝女仆短裙 + 白色蕾丝围裙（围裙上有蓝色小鲸鱼）",
            "身后一条鲸尾；白袜子 + 深蓝玛丽珍鞋",
        ],
    ),
    (
        "GPT 龙娘",
        "另一主角 · 正常比例 · 老实本分的贵价老板",
        [
            r"GPT龙娘_角色立绘_转.png",
            r"GPT娘_标准设定图.webp",
            r"GPT龙娘_三视图.webp",
        ],
        [
            "正常少女比例，高挑清冷",
            "银白超长发，发梢薄荷绿渐变",
            "一对向后弯曲的白色龙角 + 尖长精灵耳",
            "大型白色蝙蝠式带骨节龙翼",
            "粗白鳞片龙尾，末端鳍状",
            "白玫瑰发饰，花心是 OpenAI 结环标志",
            "白色多层礼服 + 黑腰带 + 黑领结 + 黑短靴",
            "怀中抱一本印着 OpenAI 标志的黑皮书",
        ],
    ),
    (
        "Claude 娘",
        "金句担当 · 唯一不慌的客人",
        [r"净版\Claude_立绘.png", r"净版\Claude_半身.png"],
        [
            "橙红／橘棕色长卷发，蓬松",
            "头上戴一朵大花发饰",
            "琥珀色眼睛，温和安静的笑",
            "白衬衫 + 深色束腰马甲 + 白色荷叶围裙",
            "手里常拿书或空饭盒",
        ],
    ),
    (
        "豆包娘 · 前",
        "官方人设 · 吃便宜 token 之前",
        [r"净版\豆包_3D人偶.png"],
        [
            "官方给定的 3D 人偶质感（豆包 App 里那个）",
            "深棕色齐耳短发，厚刘海",
            "圆脸大眼，表情木讷",
            "深色上衣，身材正常",
        ],
    ),
    (
        "豆包娘 · 后",
        "官方人设 · 吃了白饭之后（用户指定）",
        [r"净版\豆包_后_吃了白饭很胖很唐.png"],
        [
            "同一个人，吃了白饭之后变成很胖很唐的样子",
            "脸圆到变形，双下巴",
            "嘴角挂着一条长长的口水",
            "眼睛发直、瞳孔失焦",
            "围着一条大红色围巾",
        ],
    ),
    (
        "Kimi 娘",
        "跟风买便宜 token 的客人",
        [r"净版\Kimi_抱月亮.png", r"净版\Kimi_立绘.png"],
        [
            "银白偏浅紫超长卷发",
            "一对白色猫耳",
            "蓝紫色大眼睛，安静乖巧",
            "黑白女仆装 + 大量荷叶边蝴蝶结",
            "怀里抱一个黄色月亮抱枕",
        ],
    ),
    (
        "GLM 娘（智谱小狐娘）",
        "精打细算的客人",
        [r"净版\GLM_小狐娘Q版.png", r"净版\GLM_狐娘半身.png"],
        [
            "黑长直发，一对黑色狐耳",
            "眼睛半睁，慵懒",
            "黑白女仆裙 + 蕾丝眼罩推在额头上",
            "身上挂着小铃铛、骰子、「Z」字挂饰",
            "手里常拿一块写字的板子",
        ],
    ),
    (
        "千问娘",
        "来凑热闹的客人",
        [r"净版\千问_立绘.png"],
        [
            "浅蓝紫长直发，编辫子",
            "蓝紫色眼睛，温柔",
            "白色中式盘扣上衣 + 蓝紫马甲",
            "长耳坠",
        ],
    ),
]


def 读(路: str) -> Image.Image | None:
    p = 路 if os.path.isabs(路) else os.path.join(参考根, 路)
    if not os.path.isfile(p):
        print(f"  ✗ 缺 {路}")
        return None
    return Image.open(p).convert("RGB")


def 拼大图():
    """每个角色一行：左边摆参考图，右边列造型要点。行高按实际内容算，绝不重叠。"""
    W = 1840
    左边宽 = 700
    边距 = 30
    行距 = 24
    头高 = 118
    行高表 = []
    for 名, 定位, 图们, 要点 in 角色表:
        图们2 = [p for p in 图们 if 读(p)][:2]
        if 图们2:
            宽 = (左边宽 - 20) // len(图们2)
            ims = [读(p) for p in 图们2]
            hs = []
            for im in ims:
                im.thumbnail((宽 - 10, 620), Image.LANCZOS)
                hs.append(im.height)
            图高 = max(hs) + 34
        else:
            图高 = 60
        文高 = 44 + len(要点) * 34 + 16
        行高表.append(max(图高, 文高, 200))

    H = 头高 + sum(行高表) + 行距 * len(角色表) + 边距
    sh = Image.new("RGB", (W, H), (16, 16, 20))
    d = ImageDraw.Draw(sh)

    d.text((边距, 26), "《不烧心》全部角色的最终参考形象", font=字大, fill=(120, 220, 255))
    d.text((边距, 78), "全部取自互联网原图，未经重画 —— 请确认「就用这个」", font=字小,
           fill=(150, 155, 165))

    y = 头高
    for i, ((名, 定位, 图们, 要点), 行高) in enumerate(zip(角色表, 行高表)):
        d.rectangle([边距 - 10, y - 8, W - 边距 + 10, y + 行高 + 8], fill=(22, 22, 28))

        # 左：参考图
        图们2 = [p for p in 图们 if 读(p)][:2]
        if 图们2:
            宽 = (左边宽 - 20) // len(图们2)
            x = 边距
            for p in 图们2:
                im = 读(p)
                im.thumbnail((宽 - 10, 620), Image.LANCZOS)
                sh.paste(im, (x + (宽 - 10 - im.width) // 2, y + 22))
                d.rectangle([x, y + 20, x + 宽 - 8, y + 24 + im.height],
                            outline=(58, 60, 68))
                x += 宽

        # 右：名字 + 定位 + 要点
        tx = 边距 + 左边宽 + 40
        d.text((tx, y + 18), 名, font=字中, fill=(255, 205, 90))
        d.text((tx, y + 58), 定位, font=字小, fill=(140, 145, 155))
        ty = y + 96
        for k in 要点:
            d.text((tx, ty), "·  " + k, font=字小, fill=(216, 219, 226))
            ty += 34

        y += 行高 + 行距

    sh.save(出图)
    print(f"✅ 大图 → {出图}  {sh.size}")


def 拼网页():
    """单文件 HTML，图片 base64 内联，双击就能看。"""

    def 内联(路: str) -> str | None:
        p = 路 if os.path.isabs(路) else os.path.join(参考根, 路)
        if not os.path.isfile(p):
            return None
        im = Image.open(p).convert("RGB")
        im.thumbnail((1100, 1100), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, "JPEG", quality=88)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

    块 = []
    for 名, 定位, 图们, 要点 in 角色表:
        图html = ""
        for p in 图们:
            s = 内联(p)
            if s:
                图html += f'<figure><img src="{s}" alt="{os.path.basename(p)}">' \
                          f'<figcaption>{os.path.basename(p)}</figcaption></figure>'
        点html = "".join(f"<li>{k}</li>" for k in 要点)
        块.append(
            f'<section><h2>{名}<span class="tag">{定位}</span></h2>'
            f'<div class="pics">{图html}</div><ul>{点html}</ul></section>'
        )

    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>《不烧心》角色最终参考形象</title><style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:#0e0e12;color:#e8e8ee;
 font:16px/1.7 "Microsoft YaHei",-apple-system,system-ui,sans-serif}}
header{{padding:40px 48px 24px;border-bottom:1px solid #26262e;position:sticky;top:0;
 background:#0e0e12ee;backdrop-filter:blur(12px);z-index:9}}
h1{{margin:0 0 8px;font-size:30px;letter-spacing:.5px}}
header p{{margin:0;color:#8c8c9a}}
main{{padding:28px 48px 80px;display:grid;gap:28px}}
section{{background:#15151b;border:1px solid #26262e;border-radius:14px;padding:22px 24px}}
h2{{margin:0 0 16px;font-size:23px;color:#ffcd5a;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}}
.tag{{font-size:13px;font-weight:400;color:#8c8c9a;background:#1d1d25;
 border:1px solid #2c2c36;border-radius:99px;padding:3px 12px}}
.pics{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px}}
figure{{margin:0;text-align:center}}
figure img{{max-height:440px;max-width:100%;border-radius:10px;border:1px solid #2c2c36;
 display:block;background:#fff}}
figcaption{{font-size:12px;color:#6f6f7d;margin-top:6px}}
ul{{margin:0;padding-left:20px;columns:2;column-gap:36px}}
li{{margin:4px 0;color:#d6d6de;break-inside:avoid}}
@media(max-width:860px){{ul{{columns:1}}main{{padding:18px}}header{{padding:24px 18px}}}}
</style></head><body>
<header><h1>《不烧心》角色最终参考形象</h1>
<p>全部取互联网原图，我一个字都没重画。请逐条确认 —— 尤其是两个主角和豆包的前后两版。</p></header>
<main>{''.join(块)}</main></body></html>"""

    with open(出页, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 网页 → {出页}  {os.path.getsize(出页)/1048576:.1f} MB")


if __name__ == "__main__":
    拼大图()
    拼网页()
