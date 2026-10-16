# -*- coding: utf-8 -*-
"""★ 非常仔细地研究分析 —— 把官方立绘的**局部放大**出来看。

用户 m32773 的原话：「你就不能多搜点合适的立绘，然后**非常仔细的研究分析这个形象的样子**，
然后文字描述吗，**200字不行就800字**」
   —— 我前面一直跳过"看细节"这一步，拿一句短提示词就去出图，所以永远对不上。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

参 = r"D:\DSHworkspace\影匠\作品\楚子航\_参考\卡门wiki立绘"
出 = r"D:\DSHworkspace\记忆\归档\归档\截图"

# (文件, 名字, [(左上x, 左上y, 右下x, 右下y, 标签), ...])
单 = [
    ("02_楚子航角色图鉴立绘.png.png", "楚子航", [
        (30, 20, 376, 260, "1 头 / 头发 / 眼睛"),
        (0, 180, 376, 560, "2 上身：风衣领 / 扣子 / 内衬 / 领带"),
        (120, 560, 376, 800, "3 手：手套 / 学号 / 刀柄"),
    ]),
    ("03_夏弥角色图鉴立绘.png.png", "夏弥", [
        (40, 20, 376, 300, "1 头 / 发带 / 脸"),
        (20, 250, 376, 560, "2 上身：水手领 / 蝴蝶结 / 背心裙"),
    ]),
    ("01_耶梦加得角色图鉴立绘.png.png", "耶梦加得", [
        (40, 20, 376, 260, "1 头：角 / 耳 / 眼 / 鳞"),
        (80, 230, 376, 620, "2 身：鳞片斑块 / 衣服"),
        (100, 620, 376, 1000, "3 腿：鳞片 / 鞋"),
    ]),
    ("00_楚子航&夏弥角色图鉴立绘.png.png", "UR双人", [
        (60, 180, 376, 620, "1 楚子航上半身：黑鳞裂片 / 金裂缝"),
        (30, 100, 300, 350, "2 夏弥（背景）：水手服"),
        (0, 620, 376, 1112, "3 下半身 / 腰带 / 背景地铁"),
    ]),
]

try:
    字 = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
except Exception:
    字 = ImageFont.load_default()

for f, 名, 区 in 单:
    p = os.path.join(参, f)
    if not os.path.isfile(p):
        print("  ✗ 缺", p)
        continue
    im = Image.open(p).convert("RGB")
    for i, (a, b, c, d, 标) in enumerate(区):
        a, b = max(0, a), max(0, b)
        c, d = min(im.size[0], c), min(im.size[1], d)
        if c <= a or d <= b:
            continue
        裁 = im.crop((a, b, c, d))
        k = min(3.0, 1400 / max(裁.size))
        裁 = 裁.resize((int(裁.size[0] * k), int(裁.size[1] * k)), Image.LANCZOS)
        q = os.path.join(出, "_细看_%s_%d.png" % (名, i))
        裁.save(q)
        print("  ✓ %-8s %-40s %s  x%.1f" % (名, 标, 裁.size, k))
