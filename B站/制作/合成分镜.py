# -*- coding: utf-8 -*-
"""把「Q 版角色」和「实景背景」分开出，再合成 —— 这样角色的画风不会被背景吃掉。

用户 m03244 的要求：「你人物不要融入背景的风格了」。

问题根源：让 Qwen-Image-Edit 一步到位「把角色画进场景里」时，模型会为了画面统一，
把 Q 版角色的渲染风格往背景（写实/厚涂）上靠，角色就"糊"进背景了。

解法（三步分开做，每步都可控）：
  1. 只画角色，站在**纯白背景**上 —— 模型这时会老老实实按参考图的赛璐璐画风画
  2. 白底抠图 → 带 alpha 的角色 PNG（不需要 rembg，纯白底用阈值就能抠干净）
  3. 把角色贴到单独出的场景图上，位置/缩放/描边都由我控制

用法：
    python 合成分镜.py --出角色 --参考 '净版\\DS_Q版_立绘.png' --词 "..." --名 ds_站
    python 合成分镜.py --合成 --角色 <角色png> --场景 <场景png> --x 0.5 --y 0.85 --高 0.62
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 出镜_Qwen参考 import 参考根, 跑  # noqa: E402

角色根 = r"D:\DSHworkspace\B站\成片\不烧心\角色切片"
场景根 = r"D:\DSHworkspace\B站\成片\不烧心\场景"
出根 = r"D:\DSHworkspace\B站\成片\不烧心\分镜合成"

# 白底提示词模板：只描述角色，明确「纯白背景、不要场景」
白底词 = (
    "A single character standing on a PURE SOLID WHITE background (#FFFFFF), "
    "full body, head to toe, centered, facing the camera. "
    "ABSOLUTELY NO background scenery, no floor, no shadow on the ground, no props, "
    "no panel borders, no text, no watermark. "
    "CRITICAL: the character must be drawn in FLAT 2D JAPANESE ANIME CEL-SHADING — "
    "thick clean black outlines, flat solid color fills, simple two-tone shadows, "
    "bright saturated colors, like a sticker or a TV anime screencap. "
    "Do NOT render her in a photorealistic, 3D, painterly or cinematic style. "
    "Keep the character design EXACTLY as in the reference image. "
    "The character is: "
)


def 抠白底(路: str, 阈值=242, 羽化=0.8) -> Image.Image:
    """把纯白背景抠成透明。返回 RGBA。"""
    im = Image.open(路).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    # 三个通道都很亮才算背景（避免把白色衣服也抠掉——白衣服有描边和阴影，不会是纯 255）
    白 = (a[:, :, 0] >= 阈值) & (a[:, :, 1] >= 阈值) & (a[:, :, 2] >= 阈值)
    # 从四边向内泛洪，只把「和画布边缘连通的白色」当背景，角色内部的白色（如白围裙）保留
    from collections import deque

    h, w = 白.shape
    背景 = np.zeros_like(白)
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if 白[y, x] and not 背景[y, x]:
                背景[y, x] = True
                dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if 白[y, x] and not 背景[y, x]:
                背景[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and 白[ny, nx] and not 背景[ny, nx]:
                背景[ny, nx] = True
                dq.append((ny, nx))

    alpha = np.where(背景, 0, 255).astype(np.uint8)
    am = Image.fromarray(alpha, "L")
    if 羽化:
        # 边缘缩一点再模糊，去掉白边
        am = am.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(羽化))
    out = im.convert("RGBA")
    out.putalpha(am)
    return out


def 最大连通块(alpha: np.ndarray) -> tuple[int, int, int, int] | None:
    """找 alpha 里最大的连通区域，返回 (l,t,r,b)。用来在模型的拼贴输出里定位角色。"""
    from scipy import ndimage

    标, n = ndimage.label(alpha > 40)
    if n == 0:
        return None
    尺寸 = ndimage.sum(alpha > 40, 标, range(1, n + 1))
    最大 = int(np.argmax(尺寸)) + 1
    ys, xs = np.where(标 == 最大)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def 出角色(参考: str, 词: str, 名: str, 种子=8001, 宽=1536, 高=1536,
          高质量=True) -> str | None:
    os.makedirs(角色根, exist_ok=True)
    print(f"→ 出角色切片「{名}」（高质量={'开' if 高质量 else '关'}）")
    路 = 参考 if os.path.isabs(参考) else os.path.join(参考根, 参考)
    if not os.path.isfile(路):
        print(f"❌ 找不到参考图：{路}")
        return None
    r = 跑([路], 白底词 + 词, 种子=种子, 宽=宽, 高=高, 高质量=高质量)
    if not r:
        return None
    im = Image.open(r).convert("RGB")
    # 先抠白底，再找最大连通块 = 角色本体（模型的拼贴输出里，角色是最大的一块）
    rgba = 抠白底(r)
    a = np.asarray(rgba)[:, :, 3]
    box = 最大连通块(a)
    if box:
        l, t, rr, b = box
        边 = 12
        rgba = rgba.crop((max(0, l - 边), max(0, t - 边),
                          min(rgba.width, rr + 边), min(rgba.height, b + 边)))
        print(f"   ✂ 定位角色 {rgba.size}")
    p = os.path.join(角色根, 名 + ".png")
    rgba.save(p)
    print(f"   ✓ {p}")
    return p


def 合成(角色: str, 场景: str, 出: str, x=0.5, y=0.92, 高占比=0.66,
        描边=0, 阴影=True) -> str:
    """把角色贴到场景图上。x/y 是角色脚底在画面里的相对位置（0~1）。"""
    os.makedirs(出根, exist_ok=True)
    bg = Image.open(场景).convert("RGB")
    ch = Image.open(角色).convert("RGBA")

    目标高 = int(bg.height * 高占比)
    目标宽 = int(ch.width * 目标高 / ch.height)
    ch = ch.resize((目标宽, 目标高), Image.LANCZOS)

    if 描边 > 0:
        a = ch.split()[3]
        for _ in range(描边):
            a = a.filter(ImageFilter.MaxFilter(3))
        ring = Image.new("RGBA", ch.size, (255, 255, 255, 255))
        ring.putalpha(a)
        ring.alpha_composite(ch)
        ch = ring

    px = int(bg.width * x - ch.width / 2)
    py = int(bg.height * y - ch.height)

    if 阴影:
        # 在角色脚下画一个柔和的椭圆影，免得像贴纸浮在空中
        sh = Image.new("L", bg.size, 0)
        from PIL import ImageDraw

        d = ImageDraw.Draw(sh)
        rx, ry = int(ch.width * 0.36), max(6, int(ch.height * 0.035))
        d.ellipse((px + ch.width // 2 - rx, py + ch.height - ry,
                   px + ch.width // 2 + rx, py + ch.height + ry), fill=90)
        sh = sh.filter(ImageFilter.GaussianBlur(max(4, ch.width // 40)))
        dark = Image.new("RGB", bg.size, (0, 0, 0))
        bg = Image.composite(dark, bg, sh.point(lambda v: int(v * 0.55)))

    bg = bg.convert("RGBA")
    bg.alpha_composite(ch, (px, py))
    到 = os.path.join(出根, 出)
    bg.convert("RGB").save(到)
    print(f"✓ 合成 → {到}  {bg.size}  角色 {ch.size} @ ({px},{py})")
    return 到


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--出角色", action="store_true")
    ap.add_argument("--合成", action="store_true")
    ap.add_argument("--参考")
    ap.add_argument("--词", default="")
    ap.add_argument("--名", default="角色")
    ap.add_argument("--种子", type=int, default=8001)
    ap.add_argument("--宽", type=int, default=1536)
    ap.add_argument("--高", type=int, default=1536)
    ap.add_argument("--快", action="store_true", help="用 4 步档（快但糊）")
    ap.add_argument("--角色")
    ap.add_argument("--场景")
    ap.add_argument("--出")
    ap.add_argument("--x", type=float, default=0.5)
    ap.add_argument("--y", type=float, default=0.92)
    ap.add_argument("--h", dest="高占比", type=float, default=0.66)
    ap.add_argument("--描边", type=int, default=0)
    ap.add_argument("--无阴影", action="store_true")
    a = ap.parse_args()

    if a.出角色:
        if not a.参考:
            print("❌ --出角色 需要 --参考")
            return 1
        return 0 if 出角色(a.参考, a.词, a.名, a.种子, a.宽, a.高, not a.快) else 1

    if a.合成:
        if not (a.角色 and a.场景 and a.出):
            print("❌ --合成 需要 --角色 --场景 --出")
            return 1
        合成(a.角色, a.场景, a.出, a.x, a.y, a.高占比, a.描边, not a.无阴影)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
