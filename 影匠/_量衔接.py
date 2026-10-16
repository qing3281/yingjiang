# -*- coding: utf-8 -*-
"""量「前后两格接不接得上」—— 判「动作不连贯、前后衔接有问题」用的。

## 量的东西

对每一对相邻的格子 (N, N+1)，取 **N 的末帧** 和 **N+1 的首帧**，算三个数：

| 量 | 意思 | 大 = 什么 |
|---|---|---|
| **帧差** | 两帧逐像素灰度差平均（0–255） | 剪得太跳 |
| **色调差** | 两帧平均 RGB 的距离 | 光变了（白天↔夜里、暖↔冷） |
| **亮度差** | 两帧平均亮度的差 | 曝光跳了 |

★ **大不等于错。** 「院子里 → 灶房里」本来就该差很多，那是**剪辑**。
这个脚本只帮你**找出跳得最狠的那几刀**，是不是问题要人眼看。
它的用处是：**该连续的地方（同一场戏里挨着的两格）如果数很大，那才是毛病。**

## 用法

    python _量衔接.py 觉醒                # 74 格 →
    python _量衔接.py 觉醒 --前 12         # 只看跳得最狠的 12 刀
"""
import argparse
import glob
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")


def 取帧(路, 位置, 宽=160):
    """位置 = 'first' 或 'last'。返回 (灰度bytes, 平均亮度, 平均RGB)。"""
    if 位置 == "first":
        参 = ["-ss", "0.05"]
    else:
        # 末帧：用 -sseof 从结尾往回 0.15 秒
        参 = ["-sseof", "-0.15"]
    o = os.path.join(根, "_量衔接_临.png")
    subprocess.run([FFMPEG, "-y", *参, "-i", 路, "-frames:v", "1",
                    "-vf", f"scale={宽}:-2", o], capture_output=True)
    if not os.path.isfile(o):
        return None
    import struct, zlib
    # 用 PIL 更稳
    from PIL import Image
    im = Image.open(o).convert("RGB")
    px = list(im.getdata())
    n = len(px)
    灰 = sum((p[0] * 299 + p[1] * 587 + p[2] * 114) // 1000 for p in px) / n
    r = sum(p[0] for p in px) / n
    g = sum(p[1] for p in px) / n
    b = sum(p[2] for p in px) / n
    os.remove(o)
    # 缩略的灰度数组留着算帧差
    im2 = im.convert("L")
    return im2, 灰, (r, g, b)


def 帧差(a, b):
    pa, pb = list(a.getdata()), list(b.getdata())
    n = min(len(pa), len(pb))
    if n == 0:
        return None
    return sum(abs(pa[i] - pb[i]) for i in range(n)) / n


def 段文件(戏):
    目 = os.path.join(根, "作品", 戏, "段")
    出 = {}
    for p in glob.glob(os.path.join(目, "*.mp4")):
        m = re.match(r"^格(\d+)_(本机|远端)\.mp4$", os.path.basename(p))
        if m:
            n = int(m.group(1))
            if n not in 出 or os.path.getsize(p) > os.path.getsize(出[n]):
                出[n] = p
    return dict(sorted(出.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--前", type=int, default=15, help="只列跳得最狠的前 N 刀")
    参 = ap.parse_args()

    段 = 段文件(参.戏)
    号s = sorted(段)
    if len(号s) < 2:
        print("  ✗ 段不够两格")
        return 1

    print(f"  量 {len(号s)} 格的衔接（{len(号s)-1} 刀）")
    行s = []
    for i in range(len(号s) - 1):
        a, b = 号s[i], 号s[i + 1]
        首a, 亮a, 色a = 取帧(段[a], "last")
        首b, 亮b, 色b = 取帧(段[b], "first")
        if 首a is None or 首b is None:
            continue
        d = 帧差(首a, 首b)
        if d is None:
            continue
        色差 = sum(abs(色a[k] - 色b[k]) for k in range(3)) / 3
        亮差 = abs(亮a - 亮b)
        行s.append((d, 色差, 亮差, a, b))

    行s.sort(reverse=True)
    print(f"\n  {'刀':<12}{'帧差':>8}{'色调差':>9}{'亮度差':>9}")
    print("  " + "─" * 42)
    for d, 色差, 亮差, a, b in 行s[: 参.前]:
        print(f"  格{a:>2}→格{b:<6}{d:>8.2f}{色差:>9.1f}{亮差:>9.1f}")

    值s = sorted(x[0] for x in 行s)
    n = len(值s)
    print("  " + "─" * 42)
    print(f"  帧差：最小 {值s[0]:.2f}　中位 {值s[n//2]:.2f}　最大 {值s[-1]:.2f}　"
          f"平均 {sum(值s)/n:.2f}")
    for 阈 in (10, 20, 30, 40):
        数 = sum(1 for v in 值s if v >= 阈)
        print(f"    帧差 ≥ {阈:<4} 的：{数:>3} 刀（{数*100//n}%）")
    print("\n  ★ 大不等于错 —— 「院里→灶房」本来该大。"
          "\n     只有**同一场戏里挨着的两格**跳得狠，才是毛病。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
