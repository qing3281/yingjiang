# -*- coding: utf-8 -*-
"""把「那一刀」摊开看 —— 找出片子中间跳得最狠的那一帧，把它左右各两帧并排。

目的：上面量出来「末帧钉死」这版跳变倍数是 59～105×（生产版只有 3.9～4.6×）。
     倍数是个数，我要把它变成一张看得见的图 —— 跳的那一帧前后到底差了什么。

用法：python _看跳帧.py <视频路径> [视频路径2 ...]
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

出 = r"D:\DSHworkspace\_看跳帧.jpg"
宽 = 360


def 读帧(p):
    帧 = []
    cap = cv2.VideoCapture(p)
    while True:
        好, f = cap.read()
        if not 好:
            break
        帧.append(f)
    cap.release()
    return 帧


def 缩(im):
    h = max(1, int(im.shape[0] * 宽 / im.shape[1]))
    return cv2.resize(im, (宽, h))


条 = []
for p in sys.argv[1:]:
    if not os.path.isfile(p):
        print("✗ 不在：%s" % p)
        continue
    帧 = 读帧(p)
    if len(帧) < 12:
        print("✗ 太短：%s" % p)
        continue
    灰 = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in 帧]
    d = np.array([np.abs(灰[i] - 灰[i - 1]).mean() for i in range(1, len(灰))])
    # 头尾各掐 3 帧，避开编码器起手/收尾
    i = int(np.argmax(d[3:-3])) + 3 + 1          # 帧号
    中位 = float(np.median(d))
    最 = float(d[i - 1])
    print("%-46s 帧数 %3d  中位 %.2f  最狠 f%d 差 %.2f  = %.1f×"
          % (os.path.basename(p), len(帧), 中位, i, 最, 最 / 中位 if 中位 else 0))

    序号 = [max(0, i - 2), max(0, i - 1), i, min(len(帧) - 1, i + 1), min(len(帧) - 1, i + 2)]
    上 = [缩(帧[j]) for j in 序号]
    hh = 上[0].shape[0]
    w = 宽 * 5
    带 = np.full((hh + 30, w, 3), 245, np.uint8)
    for c, (j, im) in enumerate(zip(序号, 上)):
        带[0:hh, c * 宽:(c + 1) * 宽] = im
        字 = "f%d" % j + ("  ★跳" if j == i else "")
        色 = (0, 0, 220) if j == i else (255, 255, 255)
        cv2.putText(带, 字, (c * 宽 + 6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(带, 字, (c * 宽 + 6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, 色, 1, cv2.LINE_AA)
    cv2.putText(带, "%s   最狠一刀 %.1f×（中位 %.2f）" % (os.path.basename(p), 最 / 中位 if 中位 else 0, 中位),
                (6, hh + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
    条.append(带)
    条.append(np.full((8, w, 3), 255, np.uint8))

if 条:
    大 = np.vstack(条)
    cv2.imencode(".jpg", 大)[1].tofile(出)
    print("\n拼好了 %s  %dx%d  %d 字节" % (出, 大.shape[1], 大.shape[0], os.path.getsize(出)))
