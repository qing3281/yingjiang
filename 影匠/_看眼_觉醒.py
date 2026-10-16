# -*- coding: utf-8 -*-
"""把几张首帧的**眼部区域**裁出来拼一张，专治「眼袋画成淤青」这类局部毛病。

用法：
    python _看眼_觉醒.py                 # 默认挑特写那几格
    python _看眼_觉醒.py --格 2,4,10 --出 x.png

为什么要裁：74 格摆成联系表后每格只有 380 宽，眼下一片灰在缩略图上
和一块正常阴影分不出来。**要判「有没有淤青」，得把它放大到能看清。**
"""
import argparse
import os
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(根, "_bin", "ffmpeg.exe")


def 裁拼(图们, 出, 宽=420):
    参 = []
    for p in 图们:
        参 += ["-i", p]
    滤 = []
    for i in range(len(图们)):
        # 眼睛一般在画面上半、左右居中偏一侧 —— 裁左上到中间的这块最稳
        滤.append(f"[{i}:v]crop=iw*0.62:ih*0.44:iw*0.10:ih*0.08,scale={宽}:-1[v{i}]")
    链 = ";".join(滤) + ";" + "".join(f"[v{i}]" for i in range(len(图们))) + \
         f"hstack=inputs={len(图们)}[out]"
    r = subprocess.run([FF, "-y", "-v", "error"] + 参 +
                       ["-filter_complex", 链, "-map", "[out]", 出],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print("✗ " + (r.stderr or "")[-500:])
        return 1
    print(f"✓ {出}  {len(图们)} 格")
    return 0


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--戏", default="觉醒")
    ap.add_argument("--格", default="2,4,10,16,22,25,34,49,55")
    ap.add_argument("--出", default=None)
    参 = ap.parse_args()

    戏 = os.path.join(根, "作品", 参.戏)
    号 = [int(x) for x in 参.格.split(",") if x.strip()]
    图 = []
    for n in 号:
        p = os.path.join(戏, f"01_格{n}.png")
        if os.path.exists(p):
            图.append(p)
        else:
            print(f"  · 格{n} 没有首帧，跳过")
    if not 图:
        print("✗ 一张都没有")
        return 1
    出 = 参.出 or os.path.join(戏, "_眼部特写.png")
    return 裁拼(图, 出)


if __name__ == "__main__":
    sys.exit(主())
