# -*- coding: utf-8 -*-
"""量「子镜到底动了多少」——I2VA 版的代价是不是「不动」。

判据（为什么不用「相邻帧差」）：
  「相邻帧差中位数」只说明平不平顺，不说明走了多远。
  真正要问的是：这一小段应该从关键帧 A 走到关键帧 B（两张真图的像素差就是距离），
  它实际走了多少？→ 用「片尾帧对片首帧的 MAE」比「B 对 A 的 MAE」。

用法：python _量动没动.py [--目录 D:\...\子镜] [--限 N]
"""
import sys
import os
import glob

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

import importlib.util

目楚 = r"D:\DSHworkspace\影匠\作品\楚子航"

_spec = importlib.util.spec_from_file_location(
    "_tcs", os.path.join(目楚, "_台词表.py"))
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)
格_小段数 = T.格_小段数


def 读图(p):
    if not os.path.isfile(p):
        return None
    a = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    return a


def 灰(a):
    return cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)


def 差(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None
    return float(np.abs(灰(a) - 灰(b)).mean())


def 首末帧(p):
    cap = cv2.VideoCapture(p)
    首 = 末 = None
    n = 0
    while True:
        好, f = cap.read()
        if not 好:
            break
        if 首 is None:
            首 = f
        末 = f
        n += 1
    cap.release()
    return 首, 末, n


def 关键帧路(号, 段):
    """这一小段的起点图和「本该走到的终点图」。"""
    p = [os.path.join(目楚, "01_格%d.png" % 号),
         os.path.join(目楚, "02_中%d_1.png" % 号),
         os.path.join(目楚, "02_中%d_2.png" % 号),
         os.path.join(目楚, "02_中%d_3.png" % 号),
         os.path.join(目楚, "末帧", "末_格%d.png" % 号)]
    i = 段 - 1
    if i + 1 >= len(p):
        return None, None
    return p[i], p[i + 1]


def 主():
    目录 = os.path.join(目楚, "子镜")
    限 = 0
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == "--目录" and i + 1 < len(a):
            目录 = a[i + 1]
        elif x == "--限" and i + 1 < len(a):
            限 = int(a[i + 1])

    文件们 = sorted(glob.glob(os.path.join(目录, "格*_*.mp4")))
    if 限:
        文件们 = 文件们[:限]
    print("目录 %s　%d 个文件" % (目录, len(文件们)))
    print("%-10s %8s %8s %8s %8s" % ("子镜", "帧数", "片内首末", "该走距离", "走了几成"))
    比值们 = []
    for p in 文件们:
        b = os.path.basename(p)
        try:
            号 = int(b.split("_")[0][1:])
            段 = int(b.split("_")[1].split(".")[0])
        except Exception:
            continue
        首, 末, n = 首末帧(p)
        if 首 is None:
            continue
        走 = 差(首, 末)
        a路, b路 = 关键帧路(号, 段)
        距 = 差(读图(a路), 读图(b路)) if a路 else None
        成 = (走 / 距) if (走 is not None and 距) else None
        if 成 is not None:
            比值们.append(成)
        print("%-10s %8d %8s %8s %8s" % (
            b, n,
            "%.1f" % 走 if 走 is not None else "-",
            "%.1f" % 距 if 距 is not None else "-",
            "%.0f%%" % (成 * 100) if 成 is not None else "-"))
    if 比值们:
        print("\n走了几成　中位 %.0f%%　最小 %.0f%%　最大 %.0f%%　（n=%d）"
              % (float(np.median(比值们)) * 100, min(比值们) * 100,
                 max(比值们) * 100, len(比值们)))
        print("★ 1.0 左右 = 它真的走到了那张终点图；0.2 = 它几乎没动就交差了")
    return 0


if __name__ == "__main__":
    sys.exit(主())
