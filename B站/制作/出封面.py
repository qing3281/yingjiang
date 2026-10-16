# -*- coding: utf-8 -*-
"""出封面.py —— 从成片里挑一帧，加上标题，做成 B 站封面。

用法：
    python 出封面.py 光明顶                 # 用默认那一镜
    python 出封面.py 光明顶 --镜 27          # 换个镜当底图
    python 出封面.py 光明顶 --金句 "一个人，一双手" --小字 "六大门派围攻光明顶 · AI 动画"

为什么用成片里的帧而不是重新生成：
    封面必须和观众点进去看到的东西长得一样。重新生成一张更漂亮的图，点进去会有
    落差感——这是封面点击率最大的杀手。所以宁可稍微朴素一点，也要保证同源。

B 站封面规格：官方要求 16:10，最小 1146×717。这里出 1152×720。
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

成片根 = r"D:\DSHworkspace\B站\成片"

字体粗 = r"C:\Windows\Fonts\msyhbd.ttc"
字体常 = r"C:\Windows\Fonts\msyh.ttc"

宽, 高 = 1152, 720


def 取帧(片: str, 秒: float) -> Image.Image:
    import av

    with av.open(片) as c:
        s = c.streams.video[0]
        for f in c.decode(s):
            if float(f.pts * f.time_base) >= 秒:
                return f.to_image().convert("RGB")
    raise SystemExit(f"❌ 片子里抽不出 {秒} 秒的帧：{片}")


def 描边字(d, 位置, 文字, 字体, 填充, 宽度=5, 描边色=(0, 0, 0)):
    """PIL 没有描边 API，就朝一圈偏移各画一次再画正脸。"""
    x, y = 位置
    for dx in range(-宽度, 宽度 + 1):
        for dy in range(-宽度, 宽度 + 1):
            if dx * dx + dy * dy <= 宽度 * 宽度:
                d.text((x + dx, y + dy), 文字, font=字体, fill=描边色)
    d.text((x, y), 文字, font=字体, fill=填充)


def 压暗两侧(im: Image.Image, 上部: float = 0.55) -> Image.Image:
    """左上角压一层渐变黑，保证白字在任何底图上都读得出来。"""
    a = np.asarray(im).astype(np.float32)
    h, w, _ = a.shape
    # 从左到右、从上到下渐弱
    gx = np.linspace(1.0, 0.0, w) ** 0.8
    gy = np.linspace(1.0, 0.15, h) ** 1.4
    遮 = (gx[None, :] * gy[:, None]) * 上部
    遮 = 遮[:, :, None]
    return Image.fromarray(np.clip(a * (1 - 遮), 0, 255).astype(np.uint8))


def 做(片: str, 秒: float, 标题: str, 金句: str, 小字: str, 出: str) -> str:
    底 = 取帧(片, 秒)
    # 先按 16:10 居中裁，再缩到封面尺寸，避免拉伸变形
    比 = 宽 / 高
    w0, h0 = 底.size
    if w0 / h0 > 比:
        新w = int(h0 * 比)
        底 = 底.crop(((w0 - 新w) // 2, 0, (w0 + 新w) // 2, h0))
    else:
        新h = int(w0 / 比)
        底 = 底.crop((0, (h0 - 新h) // 2, w0, (h0 + 新h) // 2))
    底 = 底.resize((宽, 高), Image.LANCZOS)
    底 = 压暗两侧(底)
    d = ImageDraw.Draw(底)

    f标 = ImageFont.truetype(字体粗, 96)
    f句 = ImageFont.truetype(字体粗, 42)
    f小 = ImageFont.truetype(字体常, 27)

    描边字(d, (54, 40), 标题, f标, (255, 255, 255), 6)
    if 金句:
        描边字(d, (58, 158), 金句, f句, (255, 214, 92), 4)
    if 小字:
        描边字(d, (60, 220), 小字, f小, (226, 230, 240), 3)

    底.save(出)
    return 出


def main() -> int:
    ap = argparse.ArgumentParser(description="从成片抽帧做 B 站封面")
    ap.add_argument("片名", nargs="?", default="光明顶")
    ap.add_argument("--镜", type=int, default=26, help="用第几镜的画面（默认 26：九阳全力）")
    ap.add_argument("--秒", type=float, default=0.0, help="片头起算的秒数；不给就按镜号算")
    ap.add_argument("--标题", default="光明顶")
    ap.add_argument("--金句", default="一个人，一双手，把六派绝技全还了回去")
    ap.add_argument("--小字", default="六大门派围攻光明顶 · 全流程 AI 生成")
    ap.add_argument("--出", default="")
    a = ap.parse_args()

    目录 = os.path.join(成片根, a.片名)
    候选 = [f for f in os.listdir(目录)
            if f.lower().endswith(".mp4") and not os.path.basename(f).startswith("_")]
    if not 候选:
        raise SystemExit(f"❌ {目录} 里没有成片 mp4")
    片 = os.path.join(目录, sorted(候选, key=lambda f: -os.path.getsize(os.path.join(目录, f)))[0])
    print(f"底图来源：{片}")

    # 每镜 5.17 秒；取这一镜的中段，避开转场的第一帧
    秒 = a.秒 if a.秒 > 0 else (a.镜 - 1) * 124 / 24 + 2.0
    print(f"抽第 {秒:.1f} 秒（约第 {a.镜} 镜中段）")

    封面夹 = os.path.join(目录, "封面")
    os.makedirs(封面夹, exist_ok=True)
    出 = a.出 or os.path.join(封面夹, "封面_主.png")
    r = 做(片, 秒, a.标题, a.金句, a.小字, 出)
    w, h = Image.open(r).size
    print(f"✅ {r}  {w}×{h}  {os.path.getsize(r)/1024:.0f} KB")
    if w < 1146 or h < 717:
        print(f"⚠ B 站要求至少 1146×717，当前偏小")
    return 0


if __name__ == "__main__":
    sys.exit(main())
