# -*- coding: utf-8 -*-
"""_看官方刀.py —— 把官方长片里「单帧差最大」的那几处各抽 5 帧拼成一条对照图。

为什么：`check_官方动没动.py` 量出 32 格里**每一格都在动**（中位帧间差 5.31，
最小 1.95 —— 旧版「一镜里像看图片」的毛病没了），但同一张表也报出 7 处
**单帧像素差 > 60**：格12@2511、格15@3305、格19@4129、格20@4270、
格21@4485、格28@6176。
「亮度差」量不出这些（火把一亮也能有 40），得看帧才知道是**换镜头**、
是**有人凭空出现**，还是**模型自己闪了一下**。

用法：
    python _看官方刀.py --文件 <绝对路径> --帧 4270 4129 3305 --出 <jpg>
    python _看官方刀.py --自动          # 用上面的七个点
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

默认片 = r"D:\DSHworkspace\_连片试\官方_chuzihang_20261016_115413.mp4"
默认帧 = [2511, 3305, 4129, 4270, 4485, 6176]
默认出 = r"D:\DSHworkspace\_验官方\_官方那几刀.jpg"


def 读n(cap, n):
    """从当前打开的位置读到第 n 帧（0 基）。"""
    cap.set(cv2.CAP_PROP_POS_FRAMES, n)
    ok, 帧 = cap.read()
    return 帧 if ok else None


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--文件", default=默认片)
    ap.add_argument("--帧", type=int, nargs="*", default=None)
    ap.add_argument("--出", default=默认出)
    ap.add_argument("--旁", type=int, default=2, help="每边抽几帧（含中心共 2*旁+1 张）")
    a = ap.parse_args()

    帧们 = a.帧 if a.帧 else 默认帧
    if not os.path.isabs(a.文件) or not os.path.exists(a.文件):
        print("✗ 要本机绝对路径且文件存在：%s" % a.文件)
        sys.exit(1)

    cap = cv2.VideoCapture(a.文件)
    if not cap.isOpened():
        print("✗ 打不开")
        sys.exit(1)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    总帧 = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    每行 = 2 * a.旁 + 1
    条们 = []
    for 中 in 帧们:
        行 = []
        for d in range(-a.旁, a.旁 + 1):
            n = 中 + d
            if n < 0 or n >= 总帧:
                continue
            帧 = 读n(cap, n)
            if 帧 is None:
                continue
            行.append((n, 帧))
        if len(行) < 每行:
            print("⚠ 第 %d 帧附近抽不满（拿到 %d / %d）" % (中, len(行), 每行))
        if 行:
            条们.append((中, 行))
    cap.release()

    if not 条们:
        print("✗ 一张都没抽到")
        sys.exit(1)

    高 = max(f.shape[0] for _, 行 in 条们 for _, f in 行)
    宽 = max(f.shape[1] for _, 行 in 条们 for _, f in 行)
    尺 = 0.55  # 缩一点，横向拼 5 张也放得下
    宽2, 高2 = int(宽 * 尺), int(高 * 尺)

    画布 = []
    for 中, 行 in 条们:
        排 = np.zeros((高2, 宽2 * 每行, 3), np.uint8)
        for i, (n, f) in enumerate(行):
            g = cv2.resize(f, (宽2, 高2), interpolation=cv2.INTER_AREA)
            标 = "%d  %.2fs%s" % (n, n / fps, "  ★跳" if n == 中 else "")
            cv2.rectangle(g, (0, 0), (宽2, 26), (0, 0, 0), -1)
            cv2.putText(g, 标, (5, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 255) if n == 中 else (255, 255, 255), 1, cv2.LINE_AA)
            排[:, i * 宽2:(i + 1) * 宽2] = g
        画布.append(排)
        画布.append(np.full((6, 宽2 * 每行, 3), 255, np.uint8))

    图 = np.vstack(画布[:-1])
    os.makedirs(os.path.dirname(a.出), exist_ok=True)
    # 中文路径：cv2.imwrite 会静默失败，必须走 imencode + tofile
    ok, buf = cv2.imencode(".jpg", 图, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        print("✗ 编码失败")
        sys.exit(1)
    buf.tofile(a.出)
    print("▶ %d 处 × %d 帧 → %s" % (len(条们), 每行, a.出))
    print("   %d×%d　%.0f KB" % (图.shape[1], 图.shape[0], os.path.getsize(a.出) / 1024.0))
    for 中, 行 in 条们:
        print("   第 %d 帧（%.2f 秒 = 格%d 第%d 帧）" % (中, 中 / fps, 中 // 224 + 1, 中 % 224 + 1))
    sys.exit(0)


if __name__ == "__main__":
    主()
