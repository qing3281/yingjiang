# -*- coding: utf-8 -*-
"""子镜的最后一帧，到底落在它该落的那张关键帧上没有？

## 为什么必须量这个

`_出子镜.py` 的整个设计前提是：**每一小段的末帧 = 下一张关键帧（硬边界）**。
如果 56 帧太短、模型根本不听末帧的，那 128 张关键帧就没起到「焊死」的作用，
「把 96 张中间帧接进出片」就只是摆了个样子 —— 这正是用户骂的「判据说 OK 其实什么都没量」。

判据：
    末帧 对 「本该落的那张关键帧」的 MAE  <  末帧 对 「起点那张」的 MAE      → 它往对的方向走了
    而且前者越小越好（旧路 107 帧 FL2VA 实测能到 3.17）

用法：python check_子镜落点.py        # 扫所有已出的子镜
      python check_子镜落点.py 2 3    # 只看 格2 第3小段
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

目 = r"D:\DSHworkspace\影匠\作品\楚子航"


def 读图(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def 关键帧们(号):
    d = 目
    们 = [os.path.join(d, "01_格%d.png" % 号)]
    for k in (1, 2, 3):
        们.append(os.path.join(d, "02_中%d_%d.png" % (号, k)))
    们.append(os.path.join(d, "末帧", "末_格%d.png" % 号))
    return [p for p in 们 if os.path.isfile(p)]


def 末帧(路):
    cap = cv2.VideoCapture(路)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if n <= 0:
        cap.release(); return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, n - 1)
    ok, 帧 = cap.read()
    cap.release()
    return 帧 if ok else None


def 比(a, b):
    if a is None or b is None:
        return float("nan")
    if a.shape[:2] != b.shape[:2]:
        a = cv2.resize(a, (b.shape[1], b.shape[0]))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def 主():
    if len(sys.argv) >= 3:
        清单 = [(int(sys.argv[1]), int(sys.argv[2]))]
    else:
        清单 = []
        for n in range(1, 33):
            for k in range(1, 5):
                if os.path.isfile(os.path.join(目, "子镜", "格%d_%d.mp4" % (n, k))):
                    清单.append((n, k))
    if not 清单:
        print("✗ 一个子镜都还没出"); return 1
    print("%-9s %-11s %-11s %-11s %s" % ("子镜", "对终点帧", "对起点帧", "终点-起点", "判读"))
    差们 = []
    for n, k in 清单:
        帧图 = 关键帧们(n)
        if len(帧图) < k + 1:
            print("%-9s （关键帧不够）" % ("格%d_%d" % (n, k))); continue
        起 = 帧图[k - 1]; 终 = 帧图[k]
        p = os.path.join(目, "子镜", "格%d_%d.mp4" % (n, k))
        末 = 末帧(p)
        a = 比(末, 读图(终)); b = 比(末, 读图(起))
        差们.append(a)
        if a != a or b != b:
            判 = "读不动"
        elif a < 8:
            判 = "✓ 焊住了"
        elif a < b:
            判 = "○ 往对的方向走了，但没焊住"
        else:
            判 = "✗ 没动（停在起点）"
        print("%-9s %-11.2f %-11.2f %-11.2f %s" % ("格%d_%d" % (n, k), a, b, b - a, 判))
    好 = [x for x in 差们 if x == x]
    if 好:
        import statistics
        print()
        print("  子镜 %d 个　对终点帧 MAE：最小 %.2f　中位数 %.2f　最大 %.2f"
              % (len(好), min(好), statistics.median(好), max(好)))
        print("  （判据：中位数 < 8 才算「128 张关键帧真的当硬边界用上了」；3.17 是旧路 107 帧 FL2VA 的实测值）")
    return 0


if __name__ == "__main__":
    sys.exit(主())
