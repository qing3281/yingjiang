# -*- coding: utf-8 -*-
"""拼一张「眼睛颜色」对照图：改之前 vs 改之后 3 个种子。
左边整张缩略，右边把脸放大 —— 用户要看的是颜色，不是构图。
"""
import cv2, numpy as np, os, sys

sys.stdout.reconfigure(encoding="utf-8")
d = r"D:\DSHworkspace\影匠\作品\楚子航\_定妆卡_楚子航_爆血"
件 = [
    ("旧 熔金色", os.path.join(d, "_旧眼睛_对照.png")),
    ("新 淡 种子808", os.path.join(d, "楚子航_爆血.png")),
    ("新 淡 种20261016", os.path.join(d, "楚子航_爆血_种20261016.png")),
    ("新 淡 种777", os.path.join(d, "楚子航_爆血_种777.png")),
]

块 = []
for 名, p in 件:
    if not os.path.exists(p):
        print("  ★ 缺：%s" % p); continue
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    H, W = im.shape[:2]
    # 整张缩略
    缩 = cv2.resize(im, (300, 400))
    # 脸放大：头在图的上方 1/5，水平居中
    脸 = im[int(H * 0.03):int(H * 0.20), int(W * 0.22):int(W * 0.78)]
    脸 = cv2.resize(脸, (300, 260), interpolation=cv2.INTER_LANCZOS4)
    条 = np.vstack([缩, 脸])
    cv2.rectangle(条, (0, 0), (300, 34), (0, 0, 0), -1)
    # 标签用英文，避开 OpenCV 画不了中文的问题
    cv2.putText(条, 名.split(" ")[0].encode("ascii", "ignore").decode() or "new", (8, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    块.append(条)

a = np.hstack(块)
出 = os.path.join(d, "_眼睛颜色对照.jpg")
cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, 94])[1].tofile(出)
print("  ✓ %s  %dx%d  %d B" % (出, a.shape[1], a.shape[0], os.path.getsize(出)))
