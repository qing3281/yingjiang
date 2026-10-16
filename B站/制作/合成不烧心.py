# -*- coding: utf-8 -*-
"""把 30 条 MiniMax 动态拼成一条成片，并把剧本里的「字幕」烧进画面。

## 为什么不用 ffmpeg

本机没装 ffmpeg，但装了 PyAV 18.1.0（就是 ffmpeg 的 Python 绑定），
所以直接用 PyAV 一边解一边编，字幕用 PIL 画上去。

## 为什么字幕要烧进画面

MiniMax 出的是「画面 + 对白音频」，**不会画字幕**。
而《不烧心》是模仿短视频平台上那种 AI 市井短剧，那种片子字幕是必须的。
所以这里逐帧画。

## 音频怎么处理

每条动态自带一条 AAC 对白轨。这里全部解码成 PCM，
按顺序接起来，最后统一编成一条 AAC。155 秒的音频，内存没问题。

## 用法

```
python 合成不烧心.py                    # 拼 + 烧字幕
python 合成不烧心.py --不烧字幕          # 只拼
python 合成不烧心.py --只 1 2 3          # 只拼指定几条（调试用）
```
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 做不烧心 import 读剧本, 提台词  # noqa: E402

镜根 = r"D:\DSHworkspace\B站\成片\不烧心\镜"
成片根 = r"D:\DSHworkspace\B站\成片\不烧心"
字体路 = r"C:\Windows\Fonts\msyhbd.ttc"

# —— BGM ——
# 从素材库里挑的这一首：203 秒、RMS 0.071、过零率 0.046，是五首里
# 最安静、最「暖」的一首（其它几首要么鼓点重、要么太吵），
# 垫在对白底下不抢戏。成片 155 秒，够用，不用循环。
BGM路 = r"D:\DSHworkspace\B站\素材\BGM\zeos_-_Photo_theme_Window_like.mp3"
BGM音量 = 0.16       # 对白满刻度是 1.0，BGM 压到这个量级（约 -16 dB）
BGM淡入 = 3.0        # 秒
BGM淡出 = 6.0        # 秒

字幕号 = 46          # 字幕字号（1536 宽的画面）
字幕边距 = 46        # 距底边
描边 = 4


def 读BGM(要长: float, 采样率: int) -> np.ndarray | None:
    """把 BGM 解成 (2, N) 的 float32，截/补到 要长 秒。读不到就返回 None。"""
    if not os.path.isfile(BGM路):
        print(f"  ⚠ 找不到 BGM：{BGM路}")
        return None
    try:
        o = []
        with av.open(BGM路) as c:
            rs = av.AudioResampler(format="fltp", layout="stereo", rate=采样率)
            for f in c.decode(c.streams.audio[0]):
                for g in rs.resample(f):
                    o.append(g.to_ndarray())
        x = np.concatenate(o, axis=1).astype(np.float32)
    except Exception as e:
        print(f"  ⚠ BGM 读取失败：{e}")
        return None
    if x.shape[0] == 1:
        x = np.repeat(x, 2, axis=0)
    x = x[:2]
    要样 = int(要长 * 采样率)
    if x.shape[1] < 要样:                      # 不够就循环补齐
        次 = 要样 // x.shape[1] + 1
        x = np.tile(x, (1, 次))
    x = x[:, :要样]
    # 淡入淡出，避免开头结尾一刀切
    坡 = np.ones(要样, dtype=np.float32)
    n1, n2 = int(BGM淡入 * 采样率), int(BGM淡出 * 采样率)
    if n1 > 0:
        坡[:n1] = np.linspace(0, 1, n1, dtype=np.float32)
    if n2 > 0:
        坡[-n2:] = np.linspace(1, 0, n2, dtype=np.float32)
    return x * 坡 * BGM音量


def 取字幕(镜: dict) -> str:
    """「字幕」字段优先；没有就用「台词」里真正说出口的那句。"""
    s = (镜.get("字幕") or "").strip()
    if s:
        s = re.sub(r"^\s*[（(][^）)]*[）)]\s*", "", s)   # 去掉开头的（音效）之类
        s = re.sub(r"\*\*", "", s).strip()
        return s
    return 提台词(镜.get("台词", ""))


def 画字幕(im: Image.Image, 文: str, 字: ImageFont.FreeTypeFont) -> Image.Image:
    """底部居中，黑描边白字。太长了自动按 22 字折行。"""
    if not 文:
        return im
    d = ImageDraw.Draw(im)
    行 = []
    剩 = 文
    while len(剩) > 22:
        切 = 剩[:22]
        # 尽量在标点后断
        m = max(切.rfind(c) for c in "。，、！？；：…")
        if m >= 12:
            切 = 剩[:m + 1]
        行.append(切)
        剩 = 剩[len(切):]
    if 剩:
        行.append(剩)
    行 = 行[-2:]      # 最多两行

    高 = 字.size + 14
    y = im.height - 字幕边距 - 高 * len(行)
    for i, t in enumerate(行):
        w = d.textlength(t, font=字)
        x = (im.width - w) / 2
        yy = y + i * 高
        d.text((x, yy), t, font=字, fill=(255, 255, 255),
               stroke_width=描边, stroke_fill=(0, 0, 0))
    return im


def 拼(镜表: list[dict], 烧字幕: bool = True, 出来: str | None = None) -> str | None:
    片段 = []
    for j in 镜表:
        p = os.path.join(镜根, f"{j['号']:02d}_动态.mp4")
        if os.path.isfile(p) and os.path.getsize(p) > 10240:
            片段.append((j, p))
        else:
            print(f"  ⚠ 缺镜 {j['号']:02d}，跳过")
    if not 片段:
        print("❌ 一条动态都没有")
        return None

    出来 = 出来 or os.path.join(成片根, "不烧心_成片.mp4")
    os.makedirs(os.path.dirname(出来), exist_ok=True)
    字 = ImageFont.truetype(字体路, 字幕号) if 烧字幕 else None

    # 用第一条的参数定规格
    with av.open(片段[0][1]) as c:
        vs = c.streams.video[0]
        宽, 高 = vs.codec_context.width, vs.codec_context.height
        帧率 = vs.average_rate
        sr = c.streams.audio[0].codec_context.sample_rate if c.streams.audio else 48000
    print(f"规格 {宽}x{高} {帧率}fps  音频 {sr}Hz  共 {len(片段)} 条")

    输出 = av.open(出来, "w")
    ov = 输出.add_stream("libx264", rate=帧率)
    ov.width, ov.height, ov.pix_fmt = 宽, 高, "yuv420p"
    ov.options = {"crf": "18", "preset": "medium"}
    oa = 输出.add_stream("aac", rate=sr)
    oa.layout = "stereo"
    oa.format = "fltp"
    # ★ 坑：解出来的是 fltp（float32 平面），不是 s16 —— 别 astype(np.int16)
    重采 = av.AudioResampler(format="fltp", layout="stereo", rate=sr)

    总帧 = 0
    总样 = 0
    对白: list[np.ndarray] = []
    t0 = time.time()
    for k, (j, p) in enumerate(片段):
        文 = 取字幕(j) if 烧字幕 else ""

        # ★ 坑：在同一个 av.open() 里先 c.decode(v) 解完视频，再 c.decode(a) 解音频，
        #   音频一帧都拿不到（解复用器已经走到 EOF）。所以音频单独开一次容器。
        样 = []
        with av.open(p) as ca:
            if ca.streams.audio:
                for af in ca.decode(ca.streams.audio[0]):
                    样.append(af.to_ndarray())

        with av.open(p) as c:
            v = c.streams.video[0]
            for f in c.decode(v):
                im = f.to_image()
                if 文:
                    im = 画字幕(im, 文, 字)
                nf = av.VideoFrame.from_image(im)
                nf.pts = None
                for pkt in ov.encode(nf):
                    输出.mux(pkt)
                总帧 += 1

        if 样:
            x = np.concatenate(样, axis=1)
            if x.shape[0] == 1:
                x = np.repeat(x, 2, axis=0)
            x = x[:2]
            对白.append(x.astype(np.float32))
            总样 += x.shape[1]
        print(f"  [{k+1}/{len(片段)}] 镜 {j['号']:02d}  累计 {总帧} 帧 / {总样/sr:.1f} 秒"
              f"  ({time.time()-t0:.0f}s)")

    for pkt in ov.encode():
        输出.mux(pkt)

    # —— 音频：先把手里的对白接成整条，再把 BGM 垫进去 ——
    # ★ 坑：AudioFrame.from_ndarray 用 format="s16" 时要求 shape[0]==1（交错），
    #   但 c.decode(a) 出来的是 (声道, 样本) 的平面数据 → 必须用带 p 的格式名，
    #   再拿 AudioResampler 转成编码器要的 fltp。不这么干会直接
    #   ValueError: Expected packed `array.shape[0]` to equal `1` but got `2`
    混 = np.concatenate(对白, axis=1) if 对白 else np.zeros((2, 0), dtype=np.float32)
    print(f"\n  对白 {混.shape[1]/sr:.1f} 秒，垫 BGM…")
    bg = 读BGM(混.shape[1] / sr, sr) if 混.shape[1] else None
    if bg is not None:
        n = min(混.shape[1], bg.shape[1])
        混 = 混[:, :n] + bg[:, :n]
        峰 = float(np.abs(混).max())
        if 峰 > 0.98:                     # 别削顶
            混 = 混 * (0.98 / 峰)
        print(f"  ✓ BGM 已混入（音量 {BGM音量}），混后峰值 {np.abs(混).max():.3f}")

    for i in range(0, 混.shape[1], sr * 10):          # 每 10 秒喂一块，省内存
        块 = 混[:, i:i + sr * 10]
        nf = av.AudioFrame.from_ndarray(
            np.ascontiguousarray(块), format="fltp", layout="stereo")
        nf.sample_rate = sr
        nf.pts = None
        for 转 in 重采.resample(nf):
            for pkt in oa.encode(转):
                输出.mux(pkt)
    for pkt in oa.encode():
        输出.mux(pkt)
    输出.close()
    print(f"\n✅ {出来}  {总帧} 帧 / {总样/sr:.2f} 秒 / "
          f"{os.path.getsize(出来)/2**20:.1f} MB")
    return 出来


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--不烧字幕", action="store_true")
    ap.add_argument("--只", nargs="*", type=int, default=[])
    ap.add_argument("--出", default=None)
    ap.add_argument("--剧本", default=r"D:\DSHworkspace\B站\制作\不烧心_剧本.md")
    a = ap.parse_args()

    镜表 = 读剧本(a.剧本)
    要 = [j for j in 镜表 if not a.只 or j["号"] in a.只]
    出 = 拼(要, not a.不烧字幕, a.出)
    return 0 if 出 else 1


if __name__ == "__main__":
    raise SystemExit(main())
