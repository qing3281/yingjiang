# -*- coding: utf-8 -*-
"""量「台词」和「真环境音」到底差多少 dB。

## 为什么不能用「相邻两句之间的缝」当留白

2026-10-14 第一版就是这么量的，得到「台词只比留白高 2.9 dB」这个数，
但那个数**不可信**：配音排轴改成「一句都不许往回挪」之后，相邻两句
之间只剩 0.20 秒，而这个缝正好卡在侧链压缩的 release（450 ms）里 ——
量到的 -29 dB 是「环境音还没放回来」的读数，不是环境音的真实电平。

## 这一版的判据

留白窗必须**离任何一句字幕都 >= 0.6 秒**才采（侧链早就放开、环境音回到满值）。
两边都取中位数（避免个别极值拉着跑）。
"""
import io
import os
import re
import statistics as st
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(根, "_bin", "ffmpeg.exe")
片 = os.path.join(根, "作品", "觉醒", "片", "_成片_觉醒_字幕.mp4")
SRT = os.path.join(根, "作品", "觉醒", "配音", "台词.srt")
间隔 = 0.6


def 读SRT(路):
    t = io.open(路, encoding="utf-8-sig").read()
    条 = []
    for m in re.finditer(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", t):
        g = [int(x) for x in m.groups()]
        条.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000,
                   g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000))
    return 条


def 响(a, b):
    p = subprocess.run(
        [FF, "-hide_banner", "-ss", f"{a:.3f}", "-t", f"{max(0.05, b-a):.3f}", "-i", 片,
         "-af", "volumedetect", "-f", "null", "NUL"], capture_output=True)
    m = re.search(rb"mean_volume:\s*(-?[\d.]+) dB", p.stderr)
    return float(m.group(1)) if m else None


def main():
    p = subprocess.run([FF, "-hide_banner", "-i", 片], capture_output=True)
    m = re.search(rb"Duration:\s*(\d+):(\d+):(\d+\.\d+)", p.stderr)
    总 = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 302.54
    条 = 读SRT(SRT)
    print(f"  成片 {总:.2f}s　字幕 {len(条)} 条")

    留白 = []
    x = 0.5
    while x < 总 - 1.5:
        if all(not (s - 间隔 < x + 1.0 and x < e + 间隔) for s, e in 条):
            v = 响(x, x + 1.0)
            if v is not None:
                留白.append(round(v, 1))
        x += 1.0

    台词 = []
    for s, e in 条:
        c = (s + e) / 2
        v = 响(max(s, c - 0.5), min(e, c + 0.5))
        if v is not None:
            台词.append(round(v, 1))

    中点 = st.median(台词)
    中白 = st.median(留白) if 留白 else None
    print(f"\n【台词 vs 真留白】")
    print(f"  台词窗 {len(台词)} 个　中位 {中点:.1f} dB　"
          f"（低到高 {sorted(台词)[:3]} … {sorted(台词)[-3:]}）")
    if 中白 is None:
        print(f"  ✗ 一个真留白窗都没采到（全片一直被台词盖着？）")
        return 1
    print(f"  真空窗 {len(留白)} 个　中位 {中白:.1f} dB　"
          f"（低到高 {sorted(留白)[:3]} … {sorted(留白)[-3:]}）")
    离 = 中点 - 中白
    print(f"\n  → 分离度 {离:+.1f} dB", end="  ")
    if 离 >= 10:
        print("✓ 台词清楚压过环境音")
    elif 离 >= 6:
        print("△ 勉强能听，但环境音还是抢")
    else:
        print("✗ 台词被环境音埋了")
    return 0 if 离 >= 6 else 1


if __name__ == "__main__":
    sys.exit(main())
