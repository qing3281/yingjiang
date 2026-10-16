# -*- coding: utf-8 -*-
"""一格一图：把**文件名烧进画面**，看这一格到底有没有模型画上去的字。

## 为什么要单独写这一个

2026-10-14 我拿拼图（4 行候选、每行一个文件）判「哪一份是干净的」，
**靠数行数把行对到文件上，数错了**，于是把一份有字的段装进了成片，
还对外说了「8 格都修好了」。装完才发现成片里那两格的字还在。

错不在拼图，在**判据的形状**：拼图上的行和文件之间只有「位置」这一层关系，
中间隔了一次人眼计数，而计数是会错的。
于是把文件名直接画进像素里 —— 图和文件之间不再有任何需要推断的东西。

同类教训见 `影匠/知识/假判据族.md`：**判据要量的，必须就是你要断言的那件事。**

## 它怎么判

不看「某一秒有没有字」，而是**从头到尾密集取样**：
默认每 0.35 秒抽一帧切底部，全部横排成一行。
只要**任何一帧**有字，这一格就带字 —— 因为字是间歇冒出来的，抽稀了必然漏。

    python _逐格查字幕.py 觉醒 --格 13,18,19,26,35,55,56,59
    python _逐格查字幕.py 觉醒 --来源 _重抽          # 查候选，不查生产段
    python _逐格查字幕.py 觉醒 --全部               # 74 格全查（慢）
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")


def 找源(戏: str, 来源: str):
    """返回 {格号: [候选路径, ...]}"""
    目 = os.path.join(根, "作品", 戏, 来源)
    出 = {}
    for p in glob.glob(os.path.join(目, "*.mp4")):
        名 = os.path.basename(p)
        m = re.search(r"格(\d+)", 名)
        if not m or 名.startswith("_"):
            continue
        出.setdefault(int(m.group(1)), []).append(p)
    for n in 出:
        出[n].sort(key=os.path.getmtime, reverse=True)   # 新的在前
    return dict(sorted(出.items()))


def 时长(路):
    r = subprocess.run([FFMPEG, "-i", 路], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--来源", default="段", help="段 / _重抽 / …（相对 作品\\<戏>\\）")
    ap.add_argument("--格", default="", help="逗号分隔的格号，缺省 = 全部")
    ap.add_argument("--全部", action="store_true")
    ap.add_argument("--步", type=float, default=0.35, help="取样间隔（秒）")
    ap.add_argument("--带", type=float, default=0.26, help="底部切多高（比例）")
    ap.add_argument("--每格几条", type=int, default=3, help="每个格最多看几份候选")
    ap.add_argument("--条宽", type=int, default=250, help="每帧缩到多宽")
    参 = ap.parse_args()

    源 = 找源(参.戏, 参.来源)
    if not 源:
        print(f"  ✗ 作品\\{参.戏}\\{参.来源}\\ 下没有段文件")
        return 1
    if 参.格:
        要 = [int(x) for x in re.split(r"[,\s]+", 参.格.strip()) if x.strip().isdigit()]
    elif 参.全部:
        要 = list(源)
    else:
        要 = list(源)
    要 = [n for n in 要 if n in 源]
    if not 要:
        print("  ✗ 没选中任何格")
        return 1

    from PIL import Image, ImageDraw
    临 = os.path.join(根, "作品", 参.戏, f"_{参.来源}逐格临时")
    shutil.rmtree(临, ignore_errors=True)
    os.makedirs(临, exist_ok=True)

    行s = []          # (文字, [帧图...])
    for n in 要:
        候 = 源[n][:参.每格几条]
        for p in 候:
            时 = 时长(p)
            ts = []
            t = 0.25
            while t < 时 - 0.1:
                ts.append(t)
                t += 参.步
            帧 = []
            for j, t in enumerate(ts):
                o = os.path.join(临, "%d_%d_%d.png" % (n, len(行s), j))
                subprocess.run([FFMPEG, "-y", "-ss", "%.3f" % t, "-i", p,
                                "-vf", f"crop=iw:ih*{参.带:.3f}:0:ih*(1-{参.带:.3f})",
                                "-frames:v", "1", o], capture_output=True)
                if os.path.isfile(o):
                    帧.append(o)
            if 帧:
                标 = "格%d  %s" % (n, os.path.basename(p))
                行s.append((标, 帧))
                print("  ✓ %s  %d 帧（0.25s 起每 %.2fs）" % (标, len(帧), 参.步))

    if not 行s:
        print("  ✗ 一帧都没抽到")
        return 1

    W = 参.条宽
    im0 = Image.open(行s[0][1][0])
    H = max(1, int(im0.height * W / im0.width))
    最宽 = max(len(f) for _, f in 行s)
    标宽 = 300
    版 = Image.new("RGB", (标宽 + W * 最宽, (H + 4) * len(行s)), (12, 12, 12))
    笔 = ImageDraw.Draw(版)
    for i, (标, 帧) in enumerate(行s):
        y = i * (H + 4)
        笔.rectangle([0, y, 标宽 - 1, y + H - 1], fill=(24, 24, 30))
        笔.text((6, y + H // 2 - 7), 标, fill=(255, 225, 90))
        for j, o in enumerate(帧):
            im = Image.open(o).convert("RGB").resize((W, H), Image.LANCZOS)
            版.paste(im, (标宽 + j * W, y))
    出 = os.path.join(根, "作品", 参.戏, f"_{参.来源}_逐格字幕_%d格.png" % len(行s))
    版.save(出)
    shutil.rmtree(临, ignore_errors=True)

    print(f"\n  ✓ {出}")
    print(f"     {版.width}×{版.height}　{len(行s)} 行　左栏是文件名，右边每一小格是一帧")
    print(f"     ★ 每一行都从头到尾扫过 —— 任何一小格有字，这一格就带字")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
