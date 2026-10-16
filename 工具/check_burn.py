# -*- coding: utf-8 -*-
"""出片前最后一道验证：**拿真的段，跑真的接片/出srt/烧字幕函数**，落在临时目录。

## 为什么要这样测

`影匠\\作品\\楚子航\\_接片楚子航.py` 的 `烧()` 里那一行

    -vf "subtitles='<路径>':force_style='FontName=Microsoft YaHei,...'"

是整条链上唯一一处 **Windows 路径 + 中文文件名 + ffmpeg 滤镜转义 + 中文字体**
四件事挤在一行的地方。它错了，用户早上拿到的就是一部没有字幕的片子 ——
而「要硬字幕」是他重复说得最多的一条。

## 所以不重写、不抄过滤器

把这个生产模块 **import 进来**，只改掉它的输出目录，调它自己的
`接片()` / `出srt()` / `烧()`。**测的代码就是生产要跑的代码。**

## 判据不是「文件生成了」

判据是 **像素有没有变**：同一条台词的时间点，从「无声片」和「成片」各切一条
底部下来比。**一个字都没变 = 字幕根本没烧上去**（这正是「判据说 OK 其实什么都没量」）。
"""
import importlib.util
import os
import subprocess
import sys

根 = r"D:\DSHworkspace"
戏目 = os.path.join(根, "影匠", "作品", "楚子航")
临 = os.path.join(根, "_试烧临时")
FF = os.path.join(根, "影匠", "_bin", "ffmpeg.exe")
要试的格 = [1, 2, 3]


def 装模块():
    sys.path.insert(0, 戏目)
    spec = importlib.util.spec_from_file_location(
        "jiepian", os.path.join(戏目, "_接片楚子航.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def 切条(v, t, 出):
    """切底部 35% 一帧。"""
    subprocess.run(
        [FF, "-y", "-v", "error", "-ss", "%.3f" % t, "-i", v,
         "-vf", "crop=iw:ih*0.35:0:ih*0.65", "-frames:v", "1", 出],
        capture_output=True)
    return os.path.isfile(出) and os.path.getsize(出) > 0


def main():
    import shutil
    if os.path.isdir(临):
        shutil.rmtree(临, ignore_errors=True)
    os.makedirs(临, exist_ok=True)

    m = 装模块()
    m.片目 = 临          # ★ 只改输出目录；函数本身、过滤器本身一个字不动
    print("  段目（真的，不复制）= %s" % m.段目)
    print("  片目（改到临时）  = %s" % m.片目)

    print("\n【1】接片()  —— 真调生产函数")
    无 = m.接片(要试的格)
    if not 无:
        print("  ✗ 接片失败")
        return 1

    print("\n【2】出srt()  —— 真调生产函数")
    srt = m.出srt(要试的格)
    print("  ── srt 原文 ──")
    for ln in open(srt, encoding="utf-8").read().strip().splitlines():
        print("  | " + ln)

    print("\n【3】烧()  —— 真调生产函数")
    成 = m.烧(无, srt)
    if not 成:
        print("  ✗ 烧字幕失败")
        return 1

    # ── 判据：像素到底变没变 ──────────────────────────────
    print("\n【4】判据：同一条台词的时间点，无声片 vs 成片，底部切条比像素")
    import re
    from PIL import Image, ImageChops

    条s = []
    差s = []
    正文 = open(srt, encoding="utf-8").read()
    块们 = re.findall(
        r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)\n(.+)", 正文)
    for i, (h1, m1, s1, ms1, h2, m2, s2, ms2, 词) in enumerate(块们):
        起 = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000.0
        终 = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000.0
        中 = (起 + 终) / 2.0
        a = os.path.join(临, "_比_%d_无声.png" % i)
        b = os.path.join(临, "_比_%d_成片.png" % i)
        if not 切条(无, 中, a) or not 切条(成, 中, b):
            print("  ✗ 第 %d 条抽帧失败" % (i + 1))
            return 1
        ia = Image.open(a).convert("RGB")
        ib = Image.open(b).convert("RGB")
        差 = ImageChops.difference(ia, ib)
        最大 = max(差.getextrema(), key=lambda x: x[1])[1]
        差s.append(最大)
        条s.append((中, 词, b))
        print("    %d) t=%.2fs  「%s」  最大像素差 = %d %s"
              % (i + 1, 中, 词, 最大,
                 "✓ 画面上真的多了东西" if 最大 > 0 else "✗ 一模一样 —— 字幕没烧上"))

    if not 条s:
        print("  ✗ srt 里一条台词都没有，没法验")
        return 1

    # 拼一张给我看的图
    图s = []
    for 中, 词, b in 条s:
        图s.append(Image.open(b).convert("RGB"))
    W = 1100
    每高 = max(1, int(图s[0].height * W / 图s[0].width))
    图s = [im.resize((W, 每高), Image.LANCZOS) for im in 图s]
    版 = Image.new("RGB", (W, (每高 + 30) * len(图s)), (12, 12, 12))
    from PIL import ImageDraw
    笔 = ImageDraw.Draw(版)
    for i, im in enumerate(图s):
        y = i * (每高 + 30)
        版.paste(im, (0, y))
        笔.text((8, y + 每高 + 6), "t=%.2fs  %s" % (条s[i][0], 条s[i][1]),
                fill=(255, 225, 90))
    图 = os.path.join(根, "_试烧字幕_底部条.png")
    版.save(图)

    print("\n【5】结论")
    print("  成片       = %s  (%.2f MB)" % (成, os.path.getsize(成) / 1048576))
    print("  接片时长   = %.2f 秒（应 ≈ %.2f）" % (m.时长(成), 3 * m.一格秒))
    print("  抽给我看的图 = %s" % 图)
    if min(差s) > 0:
        print("  ✓ 每一条台词的画面上都真的多了像素 —— 硬字幕烧上去了")
        return 0
    print("  ✗ 有一条台词画面上什么都没变 —— 那一条没烧上")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
