# -*- coding: utf-8 -*-
"""_试字号.py —— 量「字幕到底多大才不溢出」。

为什么要有这个：`_超分分段.py --合` 里我写了 `字号 = 22 × (宽/736)`，
以为 2× 分辨率要 2× 字号。**但 libass 本来就按画面高度缩放字号**，
我再乘一次 → 相对画面大了两倍 → 20 字的长句直接冲出画面左右两边。

做法：拿最长那句当样本，把同一张底图按几个字号各烧一遍，
「比底图亮 >60」的像素就是字幕，量它的左右边界。
"""
import os
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
工 = r"D:\DSHworkspace\_字幕试"
片 = r"D:\DSHworkspace\影匠\作品\楚子航\片_官方\楚子航_官方_2x_成片_字幕.mp4"
长句 = "好像我吃了你的女孩似的，去那里找夏弥吧。"
时刻 = 245.19          # 第 27 句（20 字，全片最长）的中点
宽 = 1472

os.makedirs(工, exist_ok=True)

c = cv2.VideoCapture(片)
c.set(cv2.CAP_PROP_POS_FRAMES, int(时刻 * 24))
ok, 底帧 = c.read()
c.release()
if not ok:
    print("✗ 取不到那一帧")
    sys.exit(1)
底 = os.path.join(工, "底.png")
cv2.imencode(".png", 底帧)[1].tofile(底)

srt = os.path.join(工, "一.srt")
with open(srt, "w", encoding="utf-8") as f:
    f.write("1\n00:00:00,000 --> 00:00:10,000\n%s\n" % 长句)

底灰 = cv2.cvtColor(底帧, cv2.COLOR_BGR2GRAY).astype(np.int16)
图 = []
for 号 in (16, 20, 22, 26, 30, 34, 44):
    o = os.path.join(工, "f%d.png" % 号)
    if os.path.isfile(o):
        os.remove(o)
    样 = ("FontName=Microsoft YaHei,FontSize=%d,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,MarginV=36" % 号)
    滤 = "subtitles='%s':force_style='%s'" % (srt.replace("\\", "/").replace(":", "\\:"), 样)
    r = subprocess.run([FF, "-y", "-v", "error", "-i", 底, "-vf", 滤, "-frames:v", "1", o],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.isfile(o):
        print("字号 %2d 失败：%s" % (号, (r.stderr or "")[-200:]))
        continue
    im = cv2.imdecode(np.fromfile(o, dtype=np.uint8), cv2.IMREAD_COLOR)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.int16)
    白 = (g - 底灰) > 60
    ys, xs = np.nonzero(白)
    if len(xs):
        l, r_ = int(xs.min()), int(xs.max())
        print("FontSize %2d → 字幕宽 %4d px（画面 %d，占 %.0f%%）　高 %3d px　左右 %d..%d　%s"
              % (号, r_ - l, 宽, 100.0 * (r_ - l) / 宽, int(ys.max() - ys.min()), l, r_,
                 "★ 溢出画面" if l <= 2 or r_ >= 宽 - 3 else "ok"))
    else:
        print("FontSize %2d → 没检出字幕" % 号)
    s = cv2.resize(im, (1100, int(1100 * im.shape[0] / im.shape[1])))
    s = cv2.copyMakeBorder(s, 22, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(s, "FontSize=%d" % 号, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    图.append(s)

if 图:
    出 = os.path.join(工, "_字号对照.jpg")
    cv2.imencode(".jpg", np.vstack(图))[1].tofile(出)
    print("图 %s" % 出)
