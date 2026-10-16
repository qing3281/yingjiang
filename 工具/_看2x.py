# -*- coding: utf-8 -*-
"""_看2x.py —— 最终交付前看一眼：2× 成片横向抽 12 帧拼条 + 手机版属性核对。"""
import os
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
出 = r"D:\DSHworkspace\_验超分"
os.makedirs(出, exist_ok=True)

片 = r"D:\DSHworkspace\影匠\作品\楚子航\片_官方\楚子航_官方_2x_成片_字幕.mp4"
手 = r"D:\DSHworkspace\影匠\作品\楚子航\片_官方\楚子航_官方_2x_成片_字幕_手机版.mp4"


def 属性(p):
    c = cv2.VideoCapture(p)
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(c.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
    f = c.get(cv2.CAP_PROP_FPS)
    c.release()
    # ★ 这里**不能**加 `-v error` —— 它会把 `Stream #0:1: Audio:` 这行一起咽掉，
    #   于是「有没有音轨」永远报「无」。第一版就是这么写的，差点把一条有音轨的片子判成没音轨。
    #   要读流信息就用默认 verbosity 加 `-hide_banner`。
    r = subprocess.run([FF, "-hide_banner", "-i", p], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    有音 = "Audio:" in (r.stderr or "")
    音行 = [L.strip() for L in (r.stderr or "").splitlines() if "Audio:" in L]
    音 = 音行[0].split("Audio:")[-1].strip()[:60] if 音行 else "无"
    return n, w, h, f, 音


for 名, p in (("2x 成片", 片), ("手机版", 手)):
    if not os.path.isfile(p):
        print("%s ★ 不在" % 名)
        continue
    n, w, h, f, 音 = 属性(p)
    print("%-8s %d 帧　%d×%d　%.3f fps　%.2f 秒　%.1f MB"
          % (名, n, w, h, f, n / f if f else 0, os.path.getsize(p) / 1048576))
    print("         音轨：%s" % 音)
print("")
c = cv2.VideoCapture(片)
总 = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
取 = np.linspace(0, 总 - 2, 12).astype(int)
图 = []
for k in 取:
    c.set(cv2.CAP_PROP_POS_FRAMES, int(k))
    o, f = c.read()
    if not o:
        continue
    s = cv2.resize(f, (1000, int(1000 * f.shape[0] / f.shape[1])))
    cv2.putText(s, "%.1fs" % (k / 24.0), (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    图.append(s)
c.release()
上 = np.hstack(图[:6])
下 = np.hstack(图[6:])
out = np.vstack([上, 下])
p2 = os.path.join(出, "_2x全片12帧.jpg")
cv2.imencode(".jpg", out)[1].tofile(p2)
print("✓ %s　%d×%d" % (p2, out.shape[1], out.shape[0]))
