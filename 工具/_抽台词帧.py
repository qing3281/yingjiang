# -*- coding: utf-8 -*-
"""从**真成片**里，按 `_台词表` 每句台词的中间时刻抽一帧，拼成一张总览。

为什么要有这个：`_验成片.py` 的判据③只能证明「没有 Subtitle 流」——
它证不了「字幕真的画上画面了」。机器判不了的那一格，得留一张人眼能看的图。
"""
import os
import sys
import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠\作品\楚子航")
from _台词表 import 台词表, 一格秒          # noqa: E402

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
成片 = os.path.join(目, "片", "楚子航_成片_字幕.mp4")
出 = os.path.join(目, "片", "_台词帧总览.png")

cap = cv2.VideoCapture(成片)
if not cap.isOpened():
    print("★ 打不开成片：%s" % 成片)
    sys.exit(1)

条 = []
for 号 in range(1, 33):
    词 = 台词表.get(号)
    if not 词 or not 词[1]:
        continue
    起 = (号 - 1) * 一格秒 + 0.35
    中 = 起 + min(1.4, max(0.6, len(词) * 0.19 * 0.6))
    cap.set(cv2.CAP_PROP_POS_MSEC, 中 * 1000.0)
    ok, im = cap.read()
    if not ok:
        print("  ★ 格%-2d t=%.2f 抽帧失败" % (号, 中))
        continue
    条.append((号, 中, im))
    print("  格%-2d  t=%6.2f s  词=%s" % (号, 中, 词))
cap.release()

if not 条:
    print("★ 一句台词帧都没抽到")
    sys.exit(2)

# 缩到宽 560 再拼 3 列
W = 560
小 = []
for 号, 中, im in 条:
    h, w = im.shape[:2]
    nh = int(round(h * W / float(w)))
    s = cv2.resize(im, (W, nh), interpolation=cv2.INTER_AREA)
    cv2.rectangle(s, (0, 0), (95, 24), (0, 0, 0), -1)
    cv2.putText(s, "Z%d %.0fs" % (号, 中), (5, 17),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    小.append(s)

列 = 3
行 = (len(小) + 列 - 1) // 列
格高 = max(x.shape[0] for x in 小)
板 = np.zeros((行 * 格高, 列 * W, 3), np.uint8)
for i, s in enumerate(小):
    r, c = divmod(i, 列)
    板[r * 格高:r * 格高 + s.shape[0], c * W:c * W + W] = s

# ★ OpenCV 的 imwrite 在 Windows 上写不了中文路径（会**静默**返回 False），
#   所以一律 imencode 成字节再用 Python 自己写。这个坑已经踩过一次了。
ok, buf = cv2.imencode(".png", 板)
if not ok:
    print("★ imencode 失败")
    sys.exit(3)
with open(出, "wb") as f:
    f.write(buf.tobytes())
print("  %s　%d B" % (出, os.path.getsize(出)))
