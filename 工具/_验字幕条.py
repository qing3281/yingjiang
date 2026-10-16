# -*- coding: utf-8 -*-
"""从**真成片**里，在指定的几句台词时刻各取一帧，裁下缘 30% 竖着叠起来。

给谁看：给人眼看。`_验成片.py` 判据③只能证明「没有 Subtitle 流」，
证不了「字幕真的画上了画面」。这一张就是那个证据。
"""
import os
import sys
import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
成片 = os.path.join(目, "片", "楚子航_成片_字幕.mp4")
出 = os.path.join(目, "片", "_字幕条_真成片.png")

取 = [(2, 5.41), (5, 18.78), (13, 54.45), (19, 81.20), (24, 103.49), (30, 130.24)]

cap = cv2.VideoCapture(成片)
if not cap.isOpened():
    print("★ 打不开成片")
    sys.exit(1)

条 = []
for 号, t in 取:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
    ok, im = cap.read()
    if not ok:
        print("  ★ 格%d t=%.2f 抽帧失败" % (号, t))
        continue
    h = im.shape[0]
    底 = im[int(h * 0.70):, :].copy()
    cv2.rectangle(底, (0, 0), (108, 26), (0, 0, 0), -1)
    cv2.putText(底, "Z%d %.1fs" % (号, t), (6, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
    条.append(底)
cap.release()

if not 条:
    print("★ 一帧都没抽到")
    sys.exit(2)

板 = np.vstack(条)
ok, buf = cv2.imencode(".png", 板)      # ★ 中文路径不能用 imwrite
if not ok:
    print("★ imencode 失败")
    sys.exit(3)
with open(出, "wb") as f:
    f.write(buf.tobytes())
print("  %d 帧　%d×%d　%s　%d B" % (len(条), 板.shape[1], 板.shape[0], 出, os.path.getsize(出)))
