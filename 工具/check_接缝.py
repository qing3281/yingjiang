# -*- coding: utf-8 -*-
"""相邻两段子镜的接缝，真接上去了没有？

## 为什么用这个判据，而不是「末帧对目标关键帧的 MAE」

上一版 `check_子镜落点.py` 拿「末帧 vs 目标关键帧」量，得到中位数 11.95，
就判成「没焊住」。**那个判据是错的** —— 因为目标关键帧是**另一张独立生成的图**，
两张独立生成的同内容图之间本来就有 10~30 的差（实测：`末_格N` vs `01_格(N+1)` 是 13.7~37.1）。

真正决定「看不看得见接缝」的是：**前一段的最后一帧，和后一段的第一帧，差多少。**
两个都在同一段视频的同一套光照/色调里，差得小就是接上了。

判据：接缝 MAE  <  同一段内相邻帧 MAE 的中位数  → 接缝比正常运动还小，看不出来

用法：python check_接缝.py
"""
import os
import sys
import statistics

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

目 = r"D:\DSHworkspace\影匠\作品\楚子航"


def 抽(路, 位):
    cap = cv2.VideoCapture(路)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if n <= 0:
        cap.release(); return None, 0
    if 位 == "首":
        位 = 0
    elif 位 == "末":
        位 = n - 1
    cap.set(cv2.CAP_PROP_POS_FRAMES, 位)
    ok, 帧 = cap.read()
    cap.release()
    return (帧 if ok else None), n


def 比(a, b):
    if a is None or b is None:
        return float("nan")
    if a.shape[:2] != b.shape[:2]:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def 主():
    # 一格之内 4 小段：1→2、2→3、3→4 是「格内接缝」；4→下一格的 1 是「跨格接缝」
    接缝 = []
    for n in range(1, 33):
        for k in (1, 2, 3):
            甲 = os.path.join(目, "子镜", "格%d_%d.mp4" % (n, k))
            乙 = os.path.join(目, "子镜", "格%d_%d.mp4" % (n, k + 1))
            if os.path.isfile(甲) and os.path.isfile(乙):
                接缝.append(("格%d_%d→%d" % (n, k, k + 1), 甲, 乙))
        甲 = os.path.join(目, "子镜", "格%d_4.mp4" % n)
        乙 = os.path.join(目, "子镜", "格%d_1.mp4" % (n + 1))
        if os.path.isfile(甲) and os.path.isfile(乙):
            接缝.append(("格%d_4→格%d_1" % (n, n + 1), 甲, 乙))
    # 只扫已经有完整 4 小段的格，避免一半一半
    有 = [x for x in 接缝 if os.path.isfile(x[1]) and os.path.isfile(x[2])]
    if not 有:
        print("✗ 还没有能比的接缝"); return 1

    缝们 = []
    内们 = []
    print("%-18s %-10s %-12s %s" % ("接缝", "缝 MAE", "段内中位数", "判读"))
    for 名, 甲, 乙 in 有:
        末, _ = 抽(甲, "末")
        首, _ = 抽(乙, "首")
        m = 比(末, 首)
        缝们.append(m)
        # 段内相邻帧 MAE 的中位数：从甲里抽 8 对相邻帧
        单 = []
        cap = cv2.VideoCapture(甲)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if n > 10:
            位们 = [int(n * (i + 1) / 10) for i in range(8)]
            前 = None
            for w in 位们:
                cap.set(cv2.CAP_PROP_POS_FRAMES, w)
                ok, 帧 = cap.read()
                if not ok:
                    continue
                if 前 is not None:
                    单.append(比(帧, 前))
                前 = 帧
        cap.release()
        if 单:
            内 = statistics.median(单)
            内们.append(内)
            判 = "✓ 比正常运动还小" if m < 内 else ("○ 差不多大" if m < 内 * 2 else "✗ 比运动还大，会跳")
        else:
            内 = float("nan"); 判 = "段内量不到"
        print("%-18s %-10.2f %-12.2f %s" % (名, m, 内, 判))

    print()
    print("  接缝 %d 条　MAE 中位数 %.2f　最大 %.2f" % (len(缝们), statistics.median(缝们), max(缝们)))
    if 内们:
        print("  段内相邻帧 MAE 中位数 %.2f（这是「正常一帧动多少」的尺子）" % statistics.median(内们))
        print("  ★ 接缝 比 正常运动 小 %.1f 倍 —— 小于 1 就是看不出来"
              % (statistics.median(内们) / statistics.median(缝们)))
    return 0


if __name__ == "__main__":
    sys.exit(主())
