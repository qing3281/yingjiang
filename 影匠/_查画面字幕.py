# -*- coding: utf-8 -*-
"""查 H3 出的段里有没有「模型把提示词当字幕画进画面」。

## 怎么发现的

格55 的提示词是：

    周执伸手指着册子上的一行，内门执事点了一下头，把手里的笔往旁边挪过去准备翻下一册

抽帧一看，**画面底部有字**，而且**字在变**：
- 0.3 秒：「周执伸子册」
- 2.2 秒：「内门执事了一下」

**模型在把提示词逐段「读」出来当字幕画。** 这是训练数据里有大量带字幕视频留下的毛病：
提示词是中文句子，它就当成一条字幕来渲染。

## 这个脚本干什么

把每格**底部中段**（字幕通常出现的位置）横切一条出来拼成大图，
一眼看完 74 格有没有字。比逐格抽帧看快得多。

    python _查画面字幕.py 觉醒                 # 默认：一条一格，横向拼
    python _查画面字幕.py 觉醒 --两行           # 双行铺开，图窄一点
"""
import argparse
import glob
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")


def 段文件(戏: str):
    目 = os.path.join(根, "作品", 戏, "段")
    出 = {}
    for p in glob.glob(os.path.join(目, "*.mp4")):
        m = re.match(r"^格(\d+)_(本机|远端)\.mp4$", os.path.basename(p))
        if not m:
            continue
        n = int(m.group(1))
        if n not in 出 or os.path.getsize(p) > os.path.getsize(出[n]):
            出[n] = p
    return dict(sorted(出.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--带", type=float, default=0.30, help="底部切多高（占画面高的比例）")
    ap.add_argument("--列", type=int, default=1, help="一行几张（默认 1 = 全部横排）")
    ap.add_argument("--时刻", type=float, default=2.2, help="取第几秒的帧")
    ap.add_argument("--宽", type=int, default=1280, help="每格缩放到多宽")
    参 = ap.parse_args()

    段 = 段文件(参.戏)
    if not 段:
        print(f"  ✗ 作品\\{参.戏}\\段\\ 下没有 格N_本机|远端.mp4")
        return 1
    print(f"  段：{len(段)} 格　{min(段)}..{max(段)}　取第 {参.时刻} 秒的帧")

    临 = os.path.join(根, "作品", 参.戏, "_字幕条_临时")
    os.makedirs(临, exist_ok=True)

    from PIL import Image, ImageDraw

    条s = []
    for i, (n, p) in enumerate(段.items(), 1):
        o = os.path.join(临, f"{n:02d}.png")
        subprocess.run(
            [FFMPEG, "-y", "-ss", str(参.时刻), "-i", p,
             "-vf", f"crop=iw:ih*{参.带:.3f}:0:ih*(1-{参.带:.3f})",
             "-frames:v", "1", o],
            capture_output=True)
        if os.path.isfile(o):
            条s.append((n, o))
        if i % 25 == 0:
            print(f"    抽了 {i}/{len(段)}")
    if not 条s:
        print("  ✗ 一条都没抽出来")
        return 1

    图s = [Image.open(o).convert("RGB") for _, o in 条s]
    每宽 = 参.宽
    每高 = max(1, int(图s[0].height * 每宽 / 图s[0].width))
    图s = [im.resize((每宽, 每高), Image.LANCZOS) for im in 图s]

    列 = 参.列 if 参.列 > 0 else len(图s)
    行 = (len(图s) + 列 - 1) // 列
    标 = 22
    版 = Image.new("RGB", (每宽 * 列, (每高 + 标) * 行), (10, 10, 10))
    笔 = ImageDraw.Draw(版)
    for i, im in enumerate(图s):
        行i, 列i = divmod(i, 列)
        x, y = 列i * 每宽, 行i * (每高 + 标)
        版.paste(im, (x, y))
        笔.text((x + 6, y + 每高 + 3), "格%d" % 条s[i][0], fill=(255, 220, 80))

    出 = os.path.join(根, "作品", 参.戏, f"_{参.戏}_底部条_{len(条s)}格.png")
    版.save(出)
    import shutil
    shutil.rmtree(临, ignore_errors=True)
    print(f"\n  ✓ {出}")
    print(f"     {版.width}×{版.height}　{列} 列 × {行} 行　顺序 格{条s[0][0]} → 格{条s[-1][0]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
