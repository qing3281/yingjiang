# -*- coding: utf-8 -*-
"""眼睛试色对照 —— 四张，只放大眼睛那一条。"""
import cv2, numpy as np, os, sys

sys.stdout.reconfigure(encoding="utf-8")
d = r"D:\DSHworkspace\影匠\作品\楚子航\_定妆卡_楚子航_爆血\_眼睛试色"
件 = [
    ("A", "熔金(改之前)", "A_旧熔金.png"),
    ("B", "浅茶褐+淡琥珀", "B_浅茶褐.png"),
    ("C", "浅褐+极淡金", "C_极淡金.png"),
    ("D", "灰蓝底+薄琥珀", "D_灰蓝琥珀.png"),
]

块 = []
for 代, 说, f in 件:
    p = os.path.join(d, f)
    if not os.path.exists(p):
        print("  ★ 缺 %s" % f); continue
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    H, W = im.shape[:2]
    # 眼睛那一横条
    眼 = im[int(H * 0.055):int(H * 0.135), int(W * 0.33):int(W * 0.67)]
    眼 = cv2.resize(眼, (620, 400), interpolation=cv2.INTER_LANCZOS4)
    头 = im[0:int(H * 0.22), int(W * 0.28):int(W * 0.72)]
    头 = cv2.resize(头, (620, 360), interpolation=cv2.INTER_LANCZOS4)
    条 = np.vstack([头, 眼])
    cv2.rectangle(条, (0, 0), (620, 40), (0, 0, 0), -1)
    代号 = ("%s  " % 代).encode("ascii").decode()
    cv2.putText(条, 代号, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    块.append(条)

a = np.hstack(块)
出 = os.path.join(d, "_四版眼睛对照.jpg")
cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(出)
print("  ✓ %s  %dx%d  %d B" % (出, a.shape[1], a.shape[0], os.path.getsize(出)))
print()
print("  顺序：A 熔金（改之前）｜B 浅茶褐+淡琥珀｜C 浅褐+极淡金｜D 灰蓝底+薄琥珀")
