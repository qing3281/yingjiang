# -*- coding: utf-8 -*-
"""关键一测：段0 的**真·最后一帧**，跟它被指定的尾帧图（03_锚1格1.png）差多少？
   差得小 = 真落在尾帧上（那接缝就是缝上的，我上面抽帧抽错了）
   差得大 = 模型只是「朝那张图靠」，不落在上面"""
import os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
import numpy as np
ff = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
目 = r"D:\DSHworkspace\影匠\作品\修鞋"
tmp = r"D:\DSHworkspace\影匠\作品\_超分试验"

def 灰(p):
    return np.asarray(Image.open(p).convert("L").resize((160, 90)), dtype=float)

def 抽(视频, 出):
    subprocess.run([ff, "-y", "-v", "error", "-i", 视频, "-update", "1", "-frames:v", "1", 出],
                   capture_output=True)

片0 = os.path.join(目, "04_锚1格0.mp4")
# 探时长与帧数
r = subprocess.run([ff, "-hide_banner", "-i", 片0, "-f", "null", "-"],
                   capture_output=True, text=True, errors="replace")
for 行 in (r.stderr or "").splitlines():
    if "Duration" in 行 or "fps" in 行 and "Video" in 行:
        print("   ", 行.strip()[:110])

尾帧图 = os.path.join(目, "03_锚1格1.png")
首帧图 = os.path.join(目, "01_格1.png")
真尾 = os.path.join(tmp, "_真尾帧.png")
真头 = os.path.join(tmp, "_真头帧.png")
# 最后一帧：用 -sseof 0（到尾）再取最后一帧
subprocess.run([ff, "-y", "-v", "error", "-sseof", "-0.05", "-i", 片0, "-update", "1", "-frames:v", "1", 真尾],
               capture_output=True)
抽(片0, 真头)

for 名, a, b in (("段0头帧 ↔ 它该是的首帧图 01_格1.png", 真头, 首帧图),
                 ("段0尾帧 ↔ 它被指定的尾帧图 03_锚1格1.png", 真尾, 尾帧图)):
    if os.path.exists(a) and os.path.exists(b):
        print(f"   {名}　平均差 {float(np.abs(灰(a)-灰(b)).mean()):6.2f} / 255")
    else:
        print(f"   ✗ {名} 文件缺（{os.path.exists(a)} / {os.path.exists(b)}）")
