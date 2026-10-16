# -*- coding: utf-8 -*-
"""check_官方动没动.py —— 量官方长片里**每一格有没有在动**。

为什么要量：旧版（128 段拼的）最致命的毛病就是「一镜里像看图片」——
格13 那 9.33 秒基本就是一张脸的特写，模型从第一帧出发接不到别的关键帧，
干脆原地不动。官方那条是「一条隐空间时间线」，**理论上**每格都该真的走完
它那 9.33 秒的动作。但「理论上」不算数 —— 这个脚本把它逐格量出来。

判据：
  中位帧间差 = 这一格「平常一帧动多少」。< 1.0 就是几乎静止。
  最大帧间差  = 这一格里最狠的一刀。> 15 值得拉出来看（不代表是硬切，
                火把一亮也能有 40 —— 亮度差大 ≠ 硬切）。
  静止帧占比  = 相邻帧差 < 0.8 的帧占多少。> 60% 就是幻灯片。

用法：
    python check_官方动没动.py                      # 默认量官方源片
    python check_官方动没动.py --文件 <绝对路径>
    python check_官方动没动.py --格 13 3 22          # 只看这几格
"""
import argparse
import os
import statistics as st
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

默认片 = r"D:\DSHworkspace\_连片试\官方_chuzihang_20261016_115413.mp4"
格数 = 32


def 逐格量(路, 只看=None, 缩=0.5):
    cap = cv2.VideoCapture(路)
    if not cap.isOpened():
        print("✗ 打不开：%s" % 路)
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    总帧 = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    宽 = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    高 = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    每格帧 = 总帧 / float(格数)
    print("▶ %s" % os.path.basename(路))
    print("  %d 帧　%.2f fps　%d×%d　%.2f 秒　每格 %.1f 帧（%.2f 秒）"
          % (总帧, fps, 宽, 高, 总帧 / fps, 每格帧, 每格帧 / fps))

    上 = None
    行 = []
    当前格 = -1
    差们 = []

    def 收尾(格, 差们):
        if not 差们:
            return
        差 = np.array(差们, dtype=np.float64)
        静止 = float((差 < 0.8).mean())
        行.append({
            "格": 格,
            "中位": float(np.median(差)),
            "均": float(差.mean()),
            "最大": float(差.max()),
            "argmax": int(差.argmax()),
            "静止占比": 静止,
            "n": len(差),
        })

    i = 0
    while True:
        ok, 帧 = cap.read()
        if not ok:
            break
        格 = int(i // 每格帧)
        if 格 >= 格数:
            格 = 格数 - 1
        if 格 != 当前格:
            if 当前格 >= 0:
                收尾(当前格, 差们)
            当前格 = 格
            差们 = []
            上 = None
        if 缩 and 缩 != 1.0:
            帧 = cv2.resize(帧, None, fx=缩, fy=缩, interpolation=cv2.INTER_AREA)
        灰 = cv2.cvtColor(帧, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if 上 is not None:
            差们.append(float(np.abs(灰 - 上).mean()))
        上 = 灰
        i += 1
    if 当前格 >= 0:
        收尾(当前格, 差们)
    cap.release()

    if 只看:
        行 = [r for r in 行 if r["格"] + 1 in 只看]
    return {"行": 行, "总帧": 总帧, "fps": fps, "宽": 宽, "高": 高, "每格帧": 每格帧}


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--文件", default=默认片)
    ap.add_argument("--格", type=int, nargs="*", default=None)
    a = ap.parse_args()

    if not os.path.isabs(a.文件) or not os.path.exists(a.文件):
        print("✗ 要本机绝对路径，且文件要存在：%s" % a.文件)
        sys.exit(1)

    r = 逐格量(a.文件, 只看=a.格)
    if not r:
        sys.exit(1)
    行 = r["行"]
    if not 行:
        print("✗ 一格都没量到")
        sys.exit(1)

    中位们 = [x["中位"] for x in 行]
    print("")
    print("格  中位    最大    @帧     静止帧占比   判")
    print("--  ------  ------  ------  ----------  ------------------------")
    坏 = []
    for x in 行:
        判 = ""
        if x["中位"] < 1.0:
            判 = "★ 几乎静止"
            坏.append(x["格"] + 1)
        elif x["静止占比"] > 0.60:
            判 = "★ 幻灯片"
            坏.append(x["格"] + 1)
        if x["最大"] > 15:
            判 += ("  " if 判 else "") + "有刀 %.1f（第%d帧）" % (x["最大"], x["argmax"] + 1)
        print("%2d  %6.3f  %6.2f  %6d  %9.1f%%  %s"
              % (x["格"] + 1, x["中位"], x["最大"], x["argmax"] + 1,
                 x["静止占比"] * 100, 判))

    print("")
    print("▶ 汇总：%d 格　中位帧间差 中位 %.3f　最小 %.3f　最大 %.3f"
          % (len(行), st.median(中位们), min(中位们), max(中位们)))
    静止 = [x for x in 行 if x["中位"] < 1.0]
    幻灯 = [x for x in 行 if x["静止占比"] > 0.60]
    print("   中位 < 1.0 的格：%s" % (sorted(x["格"] + 1 for x in 静止) or "无"))
    print("   静止帧占比 > 60%% 的格：%s" % (sorted(x["格"] + 1 for x in 幻灯) or "无"))
    if not 静止 and not 幻灯:
        print("   ✓ 32 格都真的在动")
    sys.exit(0)


if __name__ == "__main__":
    主()
