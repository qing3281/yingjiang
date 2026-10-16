# -*- coding: utf-8 -*-
"""把同一格的两版并排量 —— 只为回答一个问题：末帧钉死，到底会不会跳。

两版：
  `子镜\\格N_段.mp4`      = 本次生产版（`--全无末帧`，自由收尾）
  `子镜_试用\\格N_段.mp4` = 对照版（末帧钉死 = 他让我生成的那 96 张中间帧当刻度，**并且**首帧仍然链式）

三个数每段各算一遍：
  接缝      MAE(上一段真尾帧, 这一段真首帧)  —— 链有没有焊住
  落点差    MAE(这一段真尾帧, 它该落到的那张关键帧)  —— 有没有走到刻度上
  跳变倍数  max(相邻帧差) ÷ 中位(相邻帧差)  —— ★ 关键：>10 就是中途一刀跳（瞬移）
            上一版 107 帧时量到的是 24.7×，去掉末帧后降到 1.67×。
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
宽 = 320
号 = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def 读图(p):
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    h = max(1, int(im.shape[0] * 宽 / im.shape[1]))
    return cv2.resize(im, (宽, h)).astype(np.float32)


def 差(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.abs(a - b).mean())


def 读视频(p):
    帧 = []
    cap = cv2.VideoCapture(p)
    while True:
        好, f = cap.read()
        if not 好:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        h = max(1, int(g.shape[0] * 宽 / g.shape[1]))
        帧.append(cv2.resize(g, (宽, h)).astype(np.float32))
    cap.release()
    return 帧


def 段内(帧):
    if len(帧) < 8:
        return None, None, None
    d = np.array([np.abs(帧[i] - 帧[i - 1]).mean() for i in range(1, len(帧))])
    m = float(np.median(d))
    mx = float(d.max())
    # 头尾各掐掉 2 帧，避开编码器起手/收尾的伪影
    if len(d) > 6:
        mx = float(d[2:-2].max())
    return m, mx, (mx / m if m > 0 else float("inf"))


目标 = {1: "02_中%d_1.png" % 号, 2: "02_中%d_2.png" % 号, 3: "02_中%d_3.png" % 号,
        4: os.path.join("末帧", "末_格%d.png" % 号)}

版 = {}
for 名, 目子 in (("生产版(全无末帧)", "子镜"), ("对照版(末帧钉死)", "子镜_试用")):
    段 = {}
    for s in (1, 2, 3, 4):
        p = os.path.join(目, 目子, "格%d_%d.mp4" % (号, s))
        if os.path.isfile(p) and os.path.getsize(p) > 10000:
            段[s] = p
    版[名] = 段

print("═══ 格%d　两版并排 ═══" % 号)
print("%-20s %-4s %8s %9s %10s %8s" % ("版本", "段", "接缝", "落点差", "跳变倍数", "帧数"))
for 名, 段 in 版.items():
    if not 段:
        print("%-20s （一段都没有）" % 名)
        continue
    帧表 = {}
    for s in sorted(段):
        帧表[s] = 读视频(段[s])
    for s in sorted(段):
        帧 = 帧表[s]
        m, mx, 倍 = 段内(帧)
        接 = 差(帧表[s - 1][-1], 帧[0]) if (s - 1) in 帧表 else None
        标 = 读图(os.path.join(目, 目标[s]))
        落 = 差(帧[-1], 标)
        print("%-20s %-4d %8s %9s %10s %8d" % (
            名, s,
            ("%.2f" % 接) if 接 is not None else "—",
            ("%.2f" % 落) if 落 is not None else "—",
            ("%.2f×" % 倍) if 倍 is not None else "—",
            len(帧)))

print()
print("怎么读：")
print("  接缝    越小越好（< 段内正常帧动 = 焊住；> 30 = 硬接）")
print("  落点差  越小说明越走到了他生成的那张中间帧上（这才是「96 张进片了」）")
print("  跳变倍数 > 10 就是中途一刀瞬移 —— 上一版 107 帧时是 24.7×，这是末帧钉死的代价")
