# -*- coding: utf-8 -*-
"""check_2x拼缝.py —— 15 段是**分别**超分的，所以要专门查一件事：
段与段之间有没有亮度/色偏的台阶（段02 是超分节点自己吐的第一段，可能和其它 14 段不一致）。

段内那 14 条缝我在 `_验超分片.py` 里已经量过（最狠 3.68×）。这里量的是**另一种**东西：
「上一段最后一帧的整幅均值」vs「下一段第一帧的整幅均值」—— 段内缝量不出系统性偏色，
两段的均值差能。
"""
import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

片 = r"D:\DSHworkspace\影匠\作品\楚子航\片_官方\楚子航_官方_2x_成片_字幕.mp4"
# 每段的输入帧数（`--合` 的日志）
帧数们 = [481] + [480] * 13 + [447]

c = cv2.VideoCapture(片)
总 = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
print("片子 %d 帧" % 总)

# 每段起点 = 累加前面的帧数
起 = []
s = 0
for n in 帧数们:
    起.append(s)
    s += n
print("段数 %d　合计 %d" % (len(起), s))

print("")
print("段  起点帧　  首帧均值   末帧均值   段内均值   与上一段末帧的差")
前末 = None
坏 = []
for i, st in enumerate(起):
    en = st + 帧数们[i] - 1
    c.set(cv2.CAP_PROP_POS_FRAMES, st)
    ok, f = c.read()
    if not ok:
        print("  段%02d 读不到首帧" % (i + 1))
        continue
    首 = float(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean())
    c.set(cv2.CAP_PROP_POS_FRAMES, min(en, 总 - 1))
    ok, f2 = c.read()
    末 = float(cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY).mean())
    # 段内均值：等距抽 12 帧
    取 = np.linspace(st, en, 12).astype(int)
    值 = []
    for k in 取:
        c.set(cv2.CAP_PROP_POS_FRAMES, int(k))
        o, ff = c.read()
        if o:
            值.append(float(cv2.cvtColor(ff, cv2.COLOR_BGR2GRAY).mean()))
    内 = float(np.mean(值)) if 值 else float("nan")
    差 = "" if 前末 is None else "%+7.2f" % (首 - 前末)
    print("  段%02d %6d　%8.2f　%8.2f　%8.2f　%s" % (i + 1, st, 首, 末, 内, 差))
    if 前末 is not None:
        坏.append(abs(首 - 前末))
    前末 = 末
c.release()

print("")
if 坏:
    print("段与段之间「整幅均值」的跳变：中位 %.2f　最大 %.2f" % (float(np.median(坏)), max(坏)))
    print("（对照：格32 那次级联崩坏是 0.24 → 73.74，差 73；这里只要远小于它就算没台阶）")
