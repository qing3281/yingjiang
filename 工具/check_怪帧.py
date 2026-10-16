# -*- coding: utf-8 -*-
"""自动找「诡异的帧」—— 用户点过的名：「中间还有很多很诡异的情况」。

## 判据怎么定的（不是拍脑袋）

一段视频里，相邻两帧的差（MAE，0~255）应该**大体平稳**。
要是某一帧突然比它旁边大很多倍，那一处就是**跳帧 / 闪白 / 画面崩了** —— 那是模型出错，
不是剧情的动作。用户看到的「诡异」就是这一类。

所以：对每一段，算出「相邻帧 MAE」的中位数（= 这一段正常一帧动多少），
再看最大的一处是中位数的几倍。

    倍数 < 4     正常（动作大的地方本来就跳得多）
    倍数 >= 4    ★ 标出来给人看

**为什么用「几倍」而不是绝对值**：每段的运动幅度天差地别（打斗段一帧动 30，静景一帧动 1），
绝对值会把打斗段全部误报。这跟接缝那条教训是同一个 —— 要用相对尺子。

用法：
    python check_怪帧.py            # 扫所有已出的子镜，只列可疑的
    python check_怪帧.py --全部      # 连正常的也列
"""
import os
import sys
import statistics

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

子镜目 = r"D:\DSHworkspace\影匠\作品\楚子航\子镜"
阈值 = 4.0


def 扫(路):
    cap = cv2.VideoCapture(路)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if n <= 2:
        cap.release(); return None
    前 = None
    差们 = []
    while True:
        ok, 帧 = cap.read()
        if not ok:
            break
        灰 = cv2.cvtColor(帧, cv2.COLOR_BGR2GRAY).astype(np.int16)
        if 前 is not None:
            差们.append(float(np.abs(灰 - 前).mean()))
        前 = 灰
    cap.release()
    if len(差们) < 3:
        return None
    中 = statistics.median(差们)
    最 = max(差们)
    位 = 差们.index(最)
    return {"帧数": n, "中位数": 中, "最大": 最, "位": 位, "倍数": (最 / 中) if 中 > 1e-6 else 999.0}


def 主():
    要全部 = "--全部" in sys.argv
    夹 = 子镜目
    if "--目录" in sys.argv:
        夹 = sys.argv[sys.argv.index("--目录") + 1]
    们 = []
    if os.path.basename(夹) == os.path.basename(子镜目):
        for a in range(1, 33):
            for b in range(1, 5):
                p = os.path.join(夹, "格%d_%d.mp4" % (a, b))
                if os.path.isfile(p) and os.path.getsize(p) > 10000:
                    们.append((a, b, p))
    else:
        # 别的目录（比如昨晚那一批 `段\格N_本机.mp4`）：拿文件名里的数字当编号
        import re
        for f in sorted(os.listdir(夹)):
            if not f.lower().endswith(".mp4"):
                continue
            p = os.path.join(夹, f)
            if os.path.getsize(p) <= 10000:
                continue
            m = re.search(r"(\d+)", f)
            们.append((int(m.group(1)) if m else 0,
                      1 if "本机" in f else 2, p))
    if not 们:
        print("✗ 这个目录里没有 mp4：" + 夹); return 1

    怪 = []
    print("目录：%s" % 夹)
    print("%-14s %-7s %-9s %-9s %-8s %s" % ("文件", "帧数", "中位数", "最大", "倍数", "第几帧最跳"))
    for a, b, p in 们:
        r = 扫(p)
        if r is None:
            print("%-14s （读不动）" % os.path.basename(p)); continue
        怪不 = r["倍数"] >= 阈值
        if 怪不 or 要全部:
            print("%-14s %-7d %-9.2f %-9.2f %-8.2f %s"
                  % (os.path.basename(p), r["帧数"], r["中位数"], r["最大"], r["倍数"],
                     ("第 %d 帧" % r["位"]) + ("　★ 跳" if 怪不 else "")))
        if 怪不:
            怪.append((a, b, r))
    print()
    print("  扫了 %d 段　★ 可疑（倍数 >= %.1f）%d 段（%.0f%%）"
          % (len(们), 阈值, len(怪), 100.0 * len(怪) / len(们)))
    return 0


if __name__ == "__main__":
    sys.exit(主())
