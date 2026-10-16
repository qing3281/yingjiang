# -*- coding: utf-8 -*-
"""_试边距.py —— 定下 2× 那条片子的字幕字号/边距。

配合 `_试字号.py` 用：字号那一维已经量出来了（FontSize 30 → 最长句占画面 86%，
34 → 94% 贴边，44 → 溢出）。这一支只扫 MarginV，看字幕落在画面哪个高度最舒服。

★ 为什么不是简单乘 2：`_超分分段.py --合` 第一版把字号和边距都乘了 `宽/736`，
而 libass 已经按画面高度缩放过一次 → 相当于放大两倍 → 20 字的长句冲出画面。
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
句 = "好像我吃了你的女孩似的，去那里找夏弥吧。"
时刻 = 245.19

os.makedirs(工, exist_ok=True)
c = cv2.VideoCapture(片)
c.set(cv2.CAP_PROP_POS_FRAMES, int(时刻 * 24))
ok, 底帧 = c.read()
c.release()
底 = os.path.join(工, "底.png")
cv2.imencode(".png", 底帧)[1].tofile(底)
srt = os.path.join(工, "一.srt")
with open(srt, "w", encoding="utf-8") as f:
    f.write("1\n00:00:00,000 --> 00:00:10,000\n%s\n" % 句)
底灰 = cv2.cvtColor(底帧, cv2.COLOR_BGR2GRAY).astype(np.int16)
高 = 底帧.shape[0]

图 = []
for 字号, 边距 in ((30, 24), (30, 36), (30, 48), (30, 60), (30, 72), (22, 36)):
    o = os.path.join(工, "m%d_%d.png" % (字号, 边距))
    if os.path.isfile(o):
        os.remove(o)
    样 = ("FontName=Microsoft YaHei,FontSize=%d,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,MarginV=%d" % (字号, 边距))
    滤 = "subtitles='%s':force_style='%s'" % (srt.replace("\\", "/").replace(":", "\\:"), 样)
    r = subprocess.run([FF, "-y", "-v", "error", "-i", 底, "-vf", 滤, "-frames:v", "1", o],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.isfile(o):
        print("字号%d边距%d 失败：%s" % (字号, 边距, (r.stderr or "")[-200:]))
        continue
    im = cv2.imdecode(np.fromfile(o, dtype=np.uint8), cv2.IMREAD_COLOR)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.int16)
    ys, xs = np.nonzero((g - 底灰) > 60)
    if len(ys):
        print("FontSize %2d MarginV %2d → 字幕顶 %4d / 底 %4d（画面高 %d）　字底距画面底 %d px（%.0f%% 高）"
              % (字号, 边距, int(ys.min()), int(ys.max()), 高, 高 - int(ys.max()),
                 100.0 * (高 - int(ys.max())) / 高))
    s = cv2.resize(im, (1100, int(1100 * im.shape[0] / im.shape[1])))
    s = cv2.copyMakeBorder(s, 22, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(s, "FontSize=%d MarginV=%d" % (字号, 边距), (6, 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    图.append(s)

if 图:
    出 = os.path.join(工, "_边距对照.jpg")
    cv2.imencode(".jpg", np.vstack(图))[1].tofile(出)
    print("图 %s" % 出)
