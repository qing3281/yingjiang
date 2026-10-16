# -*- coding: utf-8 -*-
"""旧的 96 张中间帧 vs 新重出的（拿 01_格N.png 当参考图）并排看。

上排 = 旧（纯文生图，每次都重掷构图）　下排 = 新（qwen_edit 从首帧改出来，构图被锁住）
两排左边第一张和右边最后一张是同一张，所以**只有中间三张不一样**。
如果新的这三张和左右两张长得像同一个镜头，就说明这条路对。

用法：python _看新中帧.py 3 [4 ...]
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
出 = r"D:\DSHworkspace\_看新中帧.jpg"
宽 = 400


def 图(p):
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        return None
    h = max(1, int(im.shape[0] * 宽 / im.shape[1]))
    return cv2.resize(im, (宽, h))


def 贴(画, x, y, im, 字, 色=(255, 255, 255)):
    if im is None:
        return
    h, w = im.shape[:2]
    画[y:y + h, x:x + w] = im
    cv2.putText(画, 字, (x + 6, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(画, 字, (x + 6, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 色, 1, cv2.LINE_AA)


块 = []
for g in [int(x) for x in sys.argv[1:] or ["3"]]:
    旧 = [图(os.path.join(目, "01_格%d.png" % g))]
    新 = [图(os.path.join(目, "01_格%d.png" % g))]
    for k in (1, 2, 3):
        旧.append(图(os.path.join(目, "02_中%d_%d.png" % (g, k))))
        新.append(图(os.path.join(目, "02_试中%d_%d.png" % (g, k))))
    末 = 图(os.path.join(目, "末帧", "末_格%d.png" % g))
    旧.append(末)
    新.append(末)

    hh = 旧[0].shape[0] if 旧[0] is not None else 220
    w = 宽 * 5
    条 = np.full((hh * 2 + 30, w, 3), 245, np.uint8)
    for i in range(5):
        标 = ["01_格%d" % g, "中%d_1" % g, "中%d_2" % g, "中%d_3" % g, "末_格%d" % g][i]
        贴(条, i * 宽, 0, 旧[i], ("旧 " + 标) if 0 < i < 4 else 标, (255, 210, 160))
        贴(条, i * 宽, hh, 新[i], ("新 " + 标) if 0 < i < 4 else 标, (160, 255, 190))
    cv2.putText(条, ("格 %d　上排 = 旧中间帧（纯文生图）　下排 = 新中间帧（从首帧改出来）" % g),
                (6, hh * 2 + 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
    块.append(条)
    块.append(np.full((10, w, 3), 255, np.uint8))

大 = np.vstack(块)
cv2.imencode(".jpg", 大)[1].tofile(出)
print("拼好了 %s  %dx%d  %d 字节" % (出, 大.shape[1], 大.shape[0], os.path.getsize(出)))
