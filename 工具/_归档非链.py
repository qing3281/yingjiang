# -*- coding: utf-8 -*-
"""把「非链式」的 2/3/4 段挪走 —— 只留每格的第 1 段（它的首帧本来就是 01_格N.png，没变）。

为什么要挪走（2026-10-16 09:5x 量出来的）：
  旧做法给第 2/3/4 段喂的首帧是**该走到的关键帧图**，不是上一段真出来的尾帧。
  实测接缝 MAE 中位 38.63，而正常一帧只动 4.05 —— 9.5 倍，等于每 2.33 秒硬跳一次。
  新做法链式：第 k 段的首帧 = 第 k-1 段的**真尾帧**（`_出子镜.py 取尾帧()`），接缝按定义是 0。
  留在原地会被 `--跳过已有` 当成合格品跳过去 —— 那样就是「改了代码，出的还是旧的」。
"""
import sys
import os
import glob
import shutil

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

子镜目 = r"D:\DSHworkspace\影匠\作品\楚子航\子镜"
挪走 = os.path.join(子镜目, "_旧非链式")


def 主():
    if not os.path.isdir(子镜目):
        print("✗ 没有 %s" % 子镜目)
        return 1
    os.makedirs(挪走, exist_ok=True)
    留 = 0
    挪 = 0
    for p in sorted(glob.glob(os.path.join(子镜目, "格*_*.mp4"))):
        b = os.path.basename(p)
        try:
            段 = int(b.split("_")[1].split(".")[0])
        except Exception:
            continue
        if 段 >= 2:
            shutil.move(p, os.path.join(挪走, b))
            挪 += 1
        else:
            留 += 1
            print("  · 留 %s（首帧本来就是 01_格N.png，链的起点）" % b)
    print("挪走 %d 个（2/3/4 段）　留下 %d 个（第 1 段）" % (挪, 留))
    剩 = len(glob.glob(os.path.join(子镜目, "格*_*.mp4")))
    print("现在 子镜\\ 里 %d 个 mp4；挪走目录里 %d 个"
          % (剩, len(glob.glob(os.path.join(挪走, "*.mp4")))))
    return 0


if __name__ == "__main__":
    sys.exit(主())
