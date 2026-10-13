# -*- coding: utf-8 -*-
"""给自测戏造几张假 PNG（自测用，跑完就删）。"""

import os
import sys

from PIL import Image, ImageDraw

这里 = os.path.dirname(os.path.abspath(__file__))
目录 = os.path.join(这里, "作品", "_剧组自测")
os.makedirs(目录, exist_ok=True)

要 = ["01_格1.png", "01_格2.png", "01_格3.png",
      "03_锚1格1.png", "03_锚1格2.png", "03_锚1格3.png", "03_锚1格4.png",
      "03_锚2格1.png"]          # 锚2 的 2/3/4 故意不造，测「缺源图」告警

for i, 名 in enumerate(要):
    图 = Image.new("RGB", (240, 135), (20 + i * 8, 40 + i * 6, 90 + i * 5))
    d = ImageDraw.Draw(图)
    d.rectangle([10, 10, 229, 124], outline=(210, 230, 255))
    d.line([0, 0, 239, 134], fill=(150, 190, 255))
    d.line([0, 134, 239, 0], fill=(150, 190, 255))
    图.save(os.path.join(目录, 名))
    print("造图", 名)

print("好了，共", len(要), "张 →", 目录)
sys.exit(0)
