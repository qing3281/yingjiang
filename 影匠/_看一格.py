# -*- coding: utf-8 -*-
"""把一段 mp4 的几帧抽出来拼成一条，看这一格里画面到底动没动。

用户骂过的病（`影匠\\知识\\一镜里像看图片.md`）：**一格里像看图片 —— 格内不动、格间乱跳。**
判据：把第 0 / 1/4 / 1/2 / 3/4 / 末 五帧并排，**五张要明显不是一个样子**，
而且第 0 帧要接近上一格的末帧。

用法：
    python _看一格.py 段\\格1_远端.mp4 [输出.jpg]
"""
import os
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
# ★ 这台机器上只有 ffmpeg.exe，没有 ffprobe.exe（`_bin` 里就一个文件）。
#   所以参数一律用 OpenCV 读，别去调 ffprobe。


def 参数(路):
    cap = cv2.VideoCapture(路)
    总 = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    宽 = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    高 = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return {"nb_frames": 总, "width": 宽, "height": 高,
            "r_frame_rate": "%.4f" % fps, "时长秒": 总 / fps if fps else 0}


if __name__ == "__main__":
    路 = sys.argv[1]
    print("  %s" % 路)
    参 = 参数(路)
    print("  %d 帧　%d×%d　%.4f fps　%.2f 秒" % (
        参["nb_frames"], 参["width"], 参["height"],
        float(参["r_frame_rate"]), 参["时长秒"]))
    cap = cv2.VideoCapture(路)
    总 = 参["nb_frames"]
    要 = [0, 总 // 4, 总 // 2, 总 * 3 // 4, 总 - 1]
    图s = []
    for i in 要:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if not ok:
            continue
        f = cv2.resize(f, (448, 256))
        cv2.putText(f, "f%d" % i, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 5)
        cv2.putText(f, "f%d" % i, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        图s.append(f)
    cap.release()
    条 = np.hstack(图s)
    出 = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(路)[0] + "_五帧.jpg"
    cv2.imencode(".jpg", 条, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tofile(出)
    # 动没动：相邻两帧的平均绝对差
    print("  相邻帧差（越大越动）：", end="")
    for a, b in zip(图s, 图s[1:]):
        print("  %.1f" % np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))), end="")
    print()
    print("  ✓ %s" % 出)
