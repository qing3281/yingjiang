# -*- coding: utf-8 -*-
"""从网上的表情包封面里把 Q 版鲸鱼娘裁出来，得到干净的参考图。"""
import os

from PIL import Image

根 = r"D:\DSHworkspace\B站\情报\AI娘参考图\新Q版"
出 = r"D:\DSHworkspace\B站\情报\AI娘参考图\新Q版\裁切"
os.makedirs(出, exist_ok=True)

# (源文件, 左, 上, 右, 下) —— 按像素框住角色本体，尽量避开文字
表 = [
    ("101_蓝色大肥鱼动图200张.jpg", 1290, 40, 1990, 1010),
    ("100_大肥鱼表情包1700张合集.jpg", 0, 40, 430, 800),
    ("104_免费Live2d模型大肥鱼.jpg", 0, 330, 760, 1140),
    ("109_我觉得Deepseek好可爱.jpg", 400, 130, 1560, 1080),
    ("105_梗知识蓝色大肥鱼.jpg", 480, 380, 1130, 1010),
    ("102_新一批蓝色大肥鱼表情包.jpg", 0, 0, 1440, 1080),
]

for n, l, t, r, b in 表:
    p = os.path.join(根, n)
    if not os.path.isfile(p):
        print("✗ 缺", n)
        continue
    im = Image.open(p).convert("RGB")
    r = min(r, im.width)
    b = min(b, im.height)
    c = im.crop((l, t, r, b))
    # 放大到最长边 1600，让参考图尽量清晰
    s = 1600 / max(c.size)
    if s > 1:
        c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
    o = os.path.join(出, n.replace(".jpg", "_裁.png").replace(".png", "_裁.png"))
    c.save(o)
    print(f"✓ {os.path.basename(o)}  {c.size}")
