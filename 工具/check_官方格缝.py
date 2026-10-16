# -*- coding: utf-8 -*-
"""check_官方格缝.py —— 量官方长片里**32 格之间那 31 条缝**有没有跳。

为什么单独量：`check_官方动没动.py` 量的是「每一格内部」的帧间差，
**不含**格与格交界的那一帧。而「格」是 RelayPlan 里 32 条局部提示词
按 auto_equal 切出来的（7179 / 32 ≈ 224.3 帧）——那里换的是提示词，
最容易出问题就是它。旧版（128 段拼的）每一格交界都是一条硬焊的缝。

判据：拿格缝处的帧间差和**本格内的中位帧间差**比。
    缝 ≈ 格内中位 → 过（平滑过渡）
    缝 > 格内中位 5 倍 → 是一次切（要拉出来看是「有意的换镜头」还是「模型自己闪」）

用法：
    python check_官方格缝.py --文件 <绝对路径>
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

默认片 = r"D:\DSHworkspace\_连片试\官方_chuzihang_20261016_115413.mp4"


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--文件", default=默认片)
    ap.add_argument("--格数", type=int, default=32)
    a = ap.parse_args()
    if not os.path.isabs(a.文件) or not os.path.exists(a.文件):
        print("✗ 要本机绝对路径且文件存在：%s" % a.文件)
        sys.exit(1)

    cap = cv2.VideoCapture(a.文件)
    if not cap.isOpened():
        print("✗ 打不开")
        sys.exit(1)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    总帧 = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    # 边界帧：第 k 格的**第一帧**（k = 1 .. 格数-1），从 1 基换算到 0 基
    界 = [int(round(总帧 * k / float(a.格数))) for k in range(1, a.格数)]
    界 = [x for x in 界 if 0 < x < 总帧]

    上 = None
    差 = np.full(总帧, np.nan, dtype=np.float64)
    i = 0
    while True:
        ok, 帧 = cap.read()
        if not ok:
            break
        帧 = cv2.resize(帧, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        灰 = cv2.cvtColor(帧, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if 上 is not None:
            差[i] = float(np.abs(灰 - 上).mean())
        上 = 灰
        i += 1
    cap.release()
    if i < 总帧:
        总帧 = i

    每格 = 总帧 / float(a.格数)
    行 = []
    for n in 界:
        格 = int(n // 每格)  # 0 基，这是缝**右边**那一格
        左 = 差[max(0, int((格 - 1) * 每格) + 1):n]
        右 = 差[n + 1:int(格 * 每格)]
        底 = np.nanmedian(np.concatenate([左, 右])) if (len(左) + len(右)) else float("nan")
        行.append({"帧": n, "秒": n / fps, "缝": 差[n], "底": 底,
                   "倍": (差[n] / 底) if 底 and 底 > 0 else float("nan")})

    print("▶ %s　%d 帧　%.2f fps　%.2f 秒　每格 %.1f 帧"
          % (os.path.basename(a.文件), 总帧, fps, 总帧 / fps, 每格))
    print("")
    print("缝#  格N|格N+1   第几帧   秒       缝值    格内中位   倍数   判")
    print("--  ----------  -------  -------  ------  --------  -----  ------------------")
    大 = []
    for k, r in enumerate(行, 1):
        if not np.isfinite(r["缝"]):
            continue
        判 = ""
        if r["倍"] and r["倍"] > 5:
            判 = "★ 是切"
            大.append(k)
        elif r["倍"] and r["倍"] > 2:
            判 = "偏大"
        print("%2d   %2d|%-2d     %6d  %6.2fs  %6.2f  %8.2f  %5.2f  %s"
              % (k, k, k + 1, r["帧"], r["秒"], r["缝"], r["底"], r["倍"] or 0, 判))

    缝们 = np.array([r["缝"] for r in 行 if np.isfinite(r["缝"])])
    倍们 = np.array([r["倍"] for r in 行 if np.isfinite(r["倍"])])
    print("")
    print("▶ %d 条缝：缝值 中位 %.2f　最大 %.2f　倍数 中位 %.2f　最大 %.2f"
          % (len(缝们), float(np.median(缝们)), float(缝们.max()),
             float(np.median(倍们)), float(倍们.max())))
    print("   倍数 > 5（是切）的缝：%s" % (大 or "无"))
    if not 大:
        print("   ✓ 31 条格缝全部平滑过渡，没有一条是硬切")
    sys.exit(0)


if __name__ == "__main__":
    主()
