# -*- coding: utf-8 -*-
"""把已出的 H3 段抽中间帧拼成联系表 —— 用于**目视检查连贯性**。

为什么抽中间帧而不是首帧：首帧就是喂进去的那张图，看不出模型有没有动。
抽中间帧能同时看到「动没动」和「跟首帧偏了多少」。

用法：
    python _段联系表.py 觉醒                 # 全部已出的段
    python _段联系表.py 觉醒 --列 8
"""
import argparse
import os
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")
PY = sys.executable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--列", type=int, default=8)
    ap.add_argument("--宽", type=int, default=320)
    ap.add_argument("--时刻", type=float, default=-1, help="抽第几秒，默认取中点")
    参 = ap.parse_args()

    段目录 = os.path.join(根, "作品", 参.戏, "段")
    帧目录 = os.path.join(根, "作品", 参.戏, "_检查帧")
    os.makedirs(帧目录, exist_ok=True)

    找到 = {}
    for f in sorted(os.listdir(段目录)):
        if not f.endswith(".mp4") or f.startswith("_"):
            continue
        try:
            号 = int(f.split("_")[0].replace("格", ""))
        except ValueError:
            continue
        路 = os.path.join(段目录, f)
        if 号 not in 找到 or os.path.getsize(路) > os.path.getsize(找到[号]):
            找到[号] = 路

    if not 找到:
        print("✗ 一段都没有")
        return 1
    print(f"段：{len(找到)} 格　{min(找到)}..{max(找到)}")

    帧们 = []
    for 号 in sorted(找到):
        出 = os.path.join(帧目录, f"_{号:02d}.jpg")
        时刻 = 参.时刻
        if 时刻 < 0:      # 取中点
            # 没有 ffprobe —— 用 ffmpeg 的 stderr 读 Duration
            r = subprocess.run([FFMPEG, "-i", 找到[号]], capture_output=True,
                               text=True, errors="replace")
            import re
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
            时刻 = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                    + float(m.group(3))) / 2 if m else 2.0
        subprocess.run([FFMPEG, "-y", "-ss", f"{时刻:.2f}", "-i", 找到[号],
                        "-frames:v", "1", "-vf", f"scale={参.宽}:-1", 出],
                       capture_output=True)
        if os.path.exists(出):
            帧们.append(出)

    print(f"抽帧 {len(帧们)} 张")

    # 用 PIL 拼（本机 venv 有 Pillow）
    from PIL import Image, ImageDraw
    图们 = [Image.open(p).convert("RGB") for p in 帧们]
    单宽, 单高 = 图们[0].size
    列 = min(参.列, len(图们))
    行 = (len(图们) + 列 - 1) // 列
    标 = 22
    表 = Image.new("RGB", (列 * 单宽, 行 * (单高 + 标)), (18, 18, 18))
    画 = ImageDraw.Draw(表)
    号们 = sorted(找到)
    for i, im in enumerate(图们):
        x = (i % 列) * 单宽
        y = (i // 列) * (单高 + 标)
        表.paste(im, (x, y))
        画.text((x + 4, y + 单高 + 4), f"格 {号们[i]}", fill=(230, 230, 230))
    出 = os.path.join(根, "作品", 参.戏, f"_段联系表_{len(图们)}格.jpg")
    表.save(出, quality=88)
    print(f"✓ {出}  {表.size[0]}×{表.size[1]}  {os.path.getsize(出) / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
