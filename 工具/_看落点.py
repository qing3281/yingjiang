# -*- coding: utf-8 -*-
"""把「该走到的地方」和「真走出来的地方」并排拼成两条，用眼睛看。

上一行 = 关键帧（01_格N / 中N_1 / 中N_2 / 中N_3 / 末_格N）—— 他让我生成的那 96 张就在这里面
下一行 = 真出来的 4 段的末帧（段1末 / 段2末 / 段3末 / 段4末）
两行的差，就是「中间帧到底当没当上刻度」。
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
子镜目 = os.path.join(目, "子镜")
出 = r"D:\DSHworkspace\_看落点.jpg"
格格 = [int(x) for x in (sys.argv[1:] or ["13", "22", "3"])]
宽 = 420


def 图(p):
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        return None
    h = max(1, int(im.shape[0] * 宽 / im.shape[1]))
    return cv2.resize(im, (宽, h))


def 末帧(p):
    cap = cv2.VideoCapture(p)
    末 = None
    while True:
        好, f = cap.read()
        if not 好:
            break
        末 = f
    cap.release()
    if 末 is None:
        return None
    h = max(1, int(末.shape[0] * 宽 / 末.shape[1]))
    return cv2.resize(末, (宽, h))


def 贴(画, x, y, im, 字):
    if im is None:
        return
    h, w = im.shape[:2]
    画[y:y + h, x:x + w] = im
    cv2.putText(画, 字, (x + 6, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(画, 字, (x + 6, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA)


块 = []
for g in 格格:
    上 = [图(os.path.join(目, "01_格%d.png" % g))]
    for k in (1, 2, 3):
        上.append(图(os.path.join(目, "02_中%d_%d.png" % (g, k))))
    上.append(图(os.path.join(目, "末帧", "末_格%d.png" % g)))
    上字 = ["01_格%d" % g, "中%d_1" % g, "中%d_2" % g, "中%d_3" % g, "末_格%d" % g]

    下 = [图(os.path.join(目, "01_格%d.png" % g))]
    下字 = ["起点"]
    for 段 in (1, 2, 3, 4):
        p = os.path.join(子镜目, "格%d_%d.mp4" % (g, 段))
        q = os.path.join(子镜目, "_链首", "格%d_%d.png" % (g, 段))
        if 段 >= 2 and os.path.isfile(q):
            下.append(图(q))
        else:
            下.append(图(os.path.join(目, "01_格%d.png" % g)))
        下字.append("段%d末" % 段)

    hh = 上[0].shape[0] if 上 and 上[0] is not None else 220
    ww = 宽 * 5
    条 = np.full((hh * 2 + 28, ww, 3), 245, np.uint8)
    cv2.putText(条, ("格 %d  —— 上排 = 该走到的地方（关键帧）　下排 = 真走出来的地方（每段末帧）" % g),
                (6, hh * 2 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
    for i in range(5):
        if i < len(上):
            贴(条, i * 宽, 0, 上[i], 上字[i])
        if i < len(下):
            贴(条, i * 宽, hh, 下[i], 下字[i])
    块.append(条)
    块.append(np.full((10, ww, 3), 255, np.uint8))

大 = np.vstack(块)
cv2.imencode(".jpg", 大)[1].tofile(出)     # ★ 中文路径必须走 imencode
print("拼好了 %s  %dx%d  %d 字节" % (出, 大.shape[1], 大.shape[0], os.path.getsize(出)))
