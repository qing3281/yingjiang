# -*- coding: utf-8 -*-
"""_看超分.py —— 把远端刚出的超分小样拉回来，量「真的变清楚了吗」。

★ 为什么要量：`_出中间帧`那次（qwen_edit 单参考图）所有闸门都说「成功」，出来是全黑图。
  超分也一样 —— 节点 success=True 不等于画面变清楚了。所以这里量两个数：
    ① 尺寸/帧数/时长对不对（2× → 1472×832）
    ② 同一时刻的帧，**锐度**（拉普拉斯方差）有没有真的上去
  再铺一张原图/超分图上下对照，给人眼看。

用法：python _看超分.py
"""
import os
import sys
import json
import urllib.parse
import urllib.request

import numpy as np
import cv2

sys.stdout.reconfigure(encoding="utf-8")

远端 = "http://100.127.224.106:8188"
原 = r"D:\DSHworkspace\_连片试\试_20秒.mp4"
出目 = r"D:\DSHworkspace\_超分试"
远端名 = "SR测_20秒_00001_.mp4"
本地 = os.path.join(出目, "超分_20秒_2x.mp4")
os.makedirs(出目, exist_ok=True)

q = urllib.parse.urlencode({"filename": 远端名, "subfolder": "", "type": "output"})
print("下载 %s" % 远端名)
urllib.request.urlretrieve(远端 + "/view?" + q, 本地)
print("  → %s　%.1f MB" % (本地, os.path.getsize(本地) / 1048576))


def 读(路):
    c = cv2.VideoCapture(路)
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(c.get(cv2.CAP_PROP_FPS)) or 24.0
    w = int(c.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return c, n, fps, w, h


c1, n1, f1, w1, h1 = 读(原)
c2, n2, f2, w2, h2 = 读(本地)
print("\n原片  %d 帧　%g fps　%dx%d　%.2f 秒" % (n1, f1, w1, h1, n1 / f1))
print("超分  %d 帧　%g fps　%dx%d　%.2f 秒" % (n2, f2, w2, h2, n2 / f2))
print("倍数  %.3f× / %.3f×" % (w2 / w1, h2 / h1))

# 同一时刻抽 6 帧，比锐度
位 = [int(i * (min(n1, n2) - 1) / 5) for i in range(6)]
print("\n  帧   原片锐度   超分锐度   倍数")
比 = []
对 = []
for i in 位:
    c1.set(cv2.CAP_PROP_POS_FRAMES, i)
    ok1, a = c1.read()
    c2.set(cv2.CAP_PROP_POS_FRAMES, i)
    ok2, b = c2.read()
    if not (ok1 and ok2):
        continue
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    # 把超分帧缩回原尺寸再比，才比的是「清晰度」而不是「像素数」
    gb小 = cv2.resize(gb, (ga.shape[1], ga.shape[0]), interpolation=cv2.INTER_AREA)
    sa = float(cv2.Laplacian(ga, cv2.CV_64F).var())
    sb = float(cv2.Laplacian(gb小, cv2.CV_64F).var())
    比.append(sb / max(1e-9, sa))
    print("  %4d  %8.1f  %8.1f   %5.2f×" % (i, sa, sb, sb / max(1e-9, sa)))
    对.append((ga, gb))
c1.release()
c2.release()
比 = np.array(比)
print("  中位 %.2f×　最小 %.2f×　最大 %.2f×" % (np.median(比), 比.min(), 比.max()))
print("  " + ("✓ 变清楚了" if np.median(比) >= 1.15 else
              "★ 锐度没明显上去 —— 别急着跑整片，先看看是不是模型没起作用"))

# 铺一张 原图/超分 上下对照（都缩到同样宽）
if 对:
    行 = []
    宽 = 620
    for ga, gb in 对[:4]:
        a = cv2.resize(ga, (宽, int(ga.shape[0] * 宽 / ga.shape[1])))
        b = cv2.resize(gb, (宽, int(gb.shape[0] * 宽 / gb.shape[1])))
        cv2.putText(a, "before", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(b, "after 2x", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        行.append(np.hstack([a, b]))
    布 = np.vstack(行)
    p = os.path.join(出目, "_超分对照.jpg")
    cv2.imencode(".jpg", 布, [int(cv2.IMWRITE_JPEG_QUALITY), 92])[1].tofile(p)
    print("\n  → %s　%d x %d" % (p, 布.shape[1], 布.shape[0]))

# 音轨（经验里记过：超分节点把音轨丢了）
r = os.popen('"%s" -hide_banner -i "%s" 2>&1' % (r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe", 本地)).read()
音 = [l.strip() for l in r.splitlines() if "Stream #" in l and "Audio" in l]
print("\n超分产物音轨：%s" % ("有 " + 音[0] if 音 else "★ 没有（老毛病，装配时要 ffmpeg 贴回原音轨）"))
