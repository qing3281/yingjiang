# -*- coding: utf-8 -*-
"""把 B 站封面里的角色本体裁出来，去掉封面上的大字。

用户 m03141 的意见：「你的这些图上面怎么全是什么可爱动图分享」——
之前直接把带标题大字的封面当参考图喂给模型，模型会把大字也学进去。
这里手工框出每个封面里角色的位置，裁成只有角色的干净参考图。

裁完会输出一张 `_参考图裁切校验.png`，必须亲眼看一遍确认没有字。
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

封面根 = r"D:\DSHworkspace\B站\情报\AI娘参考图"
出根 = r"D:\DSHworkspace\B站\情报\AI娘参考图\净版"
os.makedirs(出根, exist_ok=True)

# (源相对路径, 左, 上, 右, 下, 说明)
# 坐标按**像素**给；用 -1 表示「一直到边」
表 = [
    # DeepSeek Q 版：封面右边那个 Q 版，左边全是大字
    (r"新Q版\101_蓝色大肥鱼动图200张.jpg", 1660, 70, 2380, 1240, "DS_Q版_立绘"),
    (r"新Q版\100_大肥鱼表情包1700张合集.jpg", 20, 60, 700, 1180, "DS_Q版_围裙"),
    (r"新Q版\104_免费Live2d模型大肥鱼.jpg", 470, 300, 1250, 1146, "DS_Q版_拿笔"),
    # 配角
    (r"配角\202_Claude娘人是猫_BV1jn4y1Z7hu.jpg", 1560, 60, 2500, 1300, "Claude_立绘"),
    (r"配角\203_ClaudePV_Astra_BV1MFpG63E26.jpg", 900, 60, 1672, 900, "Claude_半身"),
    (r"配角\211_豆包被调成啥样了_BV1SJXNBbERC.jpg", 600, 60, 1180, 981, "豆包_3D人偶"),
    (r"配角\221_Kimi娘鼠标指针17形态_BV1nWeu67ERy.jpg", 950, 60, 1620, 1080, "Kimi_抱月亮"),
    (r"配角\222_Kimi自己画娘化形象_BV1DBaB6kET5.jpg", 1150, 240, 1990, 1300, "Kimi_立绘"),
    (r"配角\231_GLM小狐娘_zcode.jpg", 700, 60, 1900, 1680, "GLM_小狐娘Q版"),
    (r"配角\230_GLM智谱小狐娘_手指舞.jpg", 220, 20, 704, 396, "GLM_狐娘半身"),
    (r"配角\241_美丽的千问娘.jpg", 1100, 60, 2560, 1440, "千问_立绘"),
]


def main() -> int:
    出 = []
    for 源, l, t, r, b, 说明 in 表:
        p = os.path.join(封面根, 源)
        if not os.path.isfile(p):
            print(f"✗ 缺 {源}")
            continue
        im = Image.open(p).convert("RGB")
        r2 = im.width if r < 0 else min(r, im.width)
        b2 = im.height if b < 0 else min(b, im.height)
        c = im.crop((l, t, r2, b2))
        # 放大到最长边 1400，参考图要够清晰
        s = 1400 / max(c.size)
        if s > 1:
            c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
        o = os.path.join(出根, 说明 + ".png")
        c.save(o)
        print(f"✓ {说明}  {c.size}  ← {os.path.basename(源)}")
        出.append((说明, o))

    # 校验图
    小 = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 22)
    CW, CH = 420, 560
    cols = min(5, len(出))
    rows = (len(出) + cols - 1) // cols
    sh = Image.new("RGB", (CW * cols, 40 + rows * (CH + 30)), (220, 220, 224))
    d = ImageDraw.Draw(sh)
    for i, (名, p) in enumerate(出):
        im = Image.open(p).convert("RGB")
        im.thumbnail((CW - 14, CH - 6), Image.LANCZOS)
        x = (i % cols) * CW + (CW - im.width) // 2
        y = 40 + (i // cols) * (CH + 30)
        sh.paste(im, (x, y))
        d.text(((i % cols) * CW + 6, y + im.height + 4), 名, font=小, fill=(20, 20, 24))
    o = r"D:\DSHworkspace\_参考图裁切校验.png"
    sh.save(o)
    print(f"\n✅ 校验图 {o}  {sh.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
