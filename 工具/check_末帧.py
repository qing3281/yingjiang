# -*- coding: utf-8 -*-
"""子镜的最后一帧，到底落在哪张图上？

## 为什么这件事要专门量

`_备末帧.py` 的规矩是 —— **末_格N 是 01_格(N+1).png 的逐字节拷贝**（为的是「把 32 段焊死」）。

所以 `_出子镜.py` 里第 4 小段（中3 → 末_格N）**两端落在两个不同的镜头里**：
起点是第 N 格的中景，终点是**第 N+1 格的开场画面**。

要是模型真的把最后一帧拉到了 01_格(N+1)，那这 2.33 秒就是一个**跨镜头的变形（morph）**，
不是切。用户骂的「前后还根本不连贯」很可能就是它。

判据（不是我说了算）：
    末帧 对 01_格(N+1) 的 MAE   <  8   → 真的被拉过去了，就是 morph
    末帧 对 中3(本格) 的 MAE    小     → 它其实停在本格里，那就是硬切，没问题

用法：python check_末帧.py 1 4        # 看 格1_4.mp4 的最后一帧
"""
import os
import sys
import glob

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np


def 读图(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def 抽(路, 第几帧):
    cap = cv2.VideoCapture(路)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if n <= 0:
        cap.release(); return None
    位 = 0 if 第几帧 == "首" else n - 1
    cap.set(cv2.CAP_PROP_POS_FRAMES, 位)
    ok, 帧 = cap.read()
    cap.release()
    return 帧 if ok else None


def 缩(帧, 参):
    if 帧.shape[:2] != 参.shape[:2]:
        帧 = cv2.resize(帧, (参.shape[1], 参.shape[0]))
    return 帧.astype(np.int16)


def 比(a, b):
    return float(np.abs(缩(a, b) - b.astype(np.int16)).mean())


def 主():
    目 = r"D:\DSHworkspace\影匠\作品\楚子航"
    if len(sys.argv) >= 3:
        对 = [(int(sys.argv[1]), int(sys.argv[2]))]
    else:
        对 = [(n, 4) for n in range(1, 33)
              if os.path.isfile(os.path.join(目, "子镜", "格%d_4.mp4" % n))]
    if not 对:
        print("✗ 一个 第4小段 都还没出")
        return 1
    print("%-8s %-10s %-16s %-16s %s" % ("子镜", "末帧", "对 01_格(N+1)", "对 本格中3", "判读"))
    for 格, k in 对:
        p = os.path.join(目, "子镜", "格%d_%d.mp4" % (格, k))
        if not os.path.isfile(p):
            continue
        帧 = 抽(p, "末")
        if 帧 is None:
            continue
        下 = os.path.join(目, "01_格%d.png" % (格 + 1))
        中3 = os.path.join(目, "02_中%d_3.png" % 格)
        首 = os.path.join(目, "01_格%d.png" % 格)
        甲 = os.path.join(目, "子镜", "格%d_%d.mp4" % (格, k))
        if os.path.isfile(下):
            a = 比(帧, 读图(下))
        else:
            a = float("nan")
        b = 比(帧, 读图(中3)) if os.path.isfile(中3) else float("nan")
        c = 比(帧, 读图(首)) if os.path.isfile(首) else float("nan")
        if not (a != a):
            if a < 8:
                判 = "★ 被拉到下一格了 —— 这是 morph，不是切"
            elif b == b and b < a:
                判 = "停在本格里（硬切，对的）"
            else:
                判 = "两边都不像（自己编的，要看一眼）"
        else:
            判 = "没有下一格首帧（格32）"
        print("%-8s %-10s %-16.2f %-16.2f %s" % ("格%d_%d" % (格, k), "末", a, b, 判))
    print()
    print("（对照：01_格N 对 中3(格N) 的 MAE 通常在 20~60；小于 8 才算「被拉过去了」）")
    return 0


if __name__ == "__main__":
    sys.exit(主())
