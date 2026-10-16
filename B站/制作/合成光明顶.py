# -*- coding: utf-8 -*-
"""《光明顶》成片合成 —— 战斗片。

和《不烧心》合成器的根本区别：**模型音轨全部丢弃，音频从零合成。**

  构成 = 全程山风底噪 + BGM + 逐击打点的音效（见 光明顶音效表.py）

为什么要丢掉模型音轨：《不烧心》的音画同步、杂音、人声不清楚，
追到底都是 MiniMax 那条音轨不可控。战斗片本来就以动作和打击感为主，
与其跟它的音轨搏斗，不如彻底换掉、每一击自己打点——这样同步是**精确到帧**的。

用法：
    python 合成光明顶.py                 全片
    python 合成光明顶.py --只 27         只拼某几镜（试听用）
    python 合成光明顶.py --干声           不垫 BGM，只听音效
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import av
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 音效 as 效
from 光明顶音效表 import 音效表, 风声

镜根 = r"D:\DSHworkspace\B站\成片\光明顶\镜"
成片根 = r"D:\DSHworkspace\B站\成片\光明顶"
BGM路 = r"D:\DSHworkspace\B站\素材\BGM\光明顶_Warriors_Of_The_Qin_Dynasty.mp3"
# 选它是因为**动态 10.1**，是素材库里唯一一首动态超过 5 的（其余 1.2~5.1）。
# 战斗片需要 BGM 能安静下来再砸下来；动态只有 1.2 的曲子全程一个响度，
# 打点音效会被压在里面听不见。它也刚好 174 秒，够铺满不用循环。
BGM音量 = 0.28          # 战斗片 BGM 要顶上来（《不烧心》是安静片只给 0.16）
BGM淡入 = 2.0
BGM淡出 = 5.0
风音量 = 0.5            # 风声表里的值再乘这个总系数
音效峰上限 = 0.85       # 单镜内所有打点叠加后的峰值上限（超过就只压这一镜）
目标RMS = 0.135         # ★ 全片响度目标（战斗片要比《不烧心》的 0.121 更响一档）
软限阈值 = 0.55         # ★ 软膝起点：低于此值完全线性，不打点的地方一点不动
峰值上限 = 0.56         # ★ 浮点域硬上限。★ 必须留足：AAC 是有损变换编码，瞬态处
                        #   解出来的波形会比输入高 2~4 dB。测到限到 0.94 时解出 1.403、
                        #   588 个采样过载；限到 0.70 后解出约 0.95，零过载。
采样率 = 48000


def 软限(x: "np.ndarray", 阈值: float = 0.62, 上限: float = 0.94) -> "np.ndarray":
    """软膝限幅：阈值以下原样，以上用 tanh 渐进压到上限。

    为什么不用整体缩放：本片峰值因子约 23 dB（正常影视 12~18 dB），
    整体缩放到不撞顶会把安静镜一起拖下去；硬限幅又会在打点处产生削顶失真。
    tanh 软膝只动超过阈值的那些尖峰，安静段完全线性。
    """
    import numpy as _np

    a = _np.abs(x)
    过 = a > 阈值
    if not 过.any():
        return x
    y = x.copy()
    t = (a[过] - 阈值) / (上限 - 阈值)
    y[过] = _np.sign(x[过]) * (阈值 + (上限 - 阈值) * _np.tanh(t))
    # 二次保险：tanh 在 t 很大时贴近 1，理论上不超上限，浮点上再夹一次
    return _np.clip(y, -上限, 上限)

字幕号 = 46
字幕边距 = 46
描边 = 4


# ─────────────────────────── 读素材 ───────────────────────────

def 读BGM(要长: float, sr: int) -> np.ndarray | None:
    """把 BGM 解成 (2, N) float32，不够就循环补齐，带淡入淡出。"""
    if not os.path.isfile(BGM路):
        print(f"  ⚠ 找不到 BGM：{BGM路}")
        return None
    try:
        o = []
        with av.open(BGM路) as c:
            rs = av.AudioResampler(format="fltp", layout="stereo", rate=sr)
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
    要样 = int(要长 * sr)
    if x.shape[1] < 要样:
        x = np.tile(x, (1, 要样 // x.shape[1] + 1))
    x = x[:, :要样]
    包 = np.ones(要样, dtype=np.float32)
    n1, n2 = int(BGM淡入 * sr), int(BGM淡出 * sr)
    if n1 > 0:
        包[:n1] = np.linspace(0, 1, n1, dtype=np.float32)
    if n2 > 0:
        包[-n2:] = np.linspace(1, 0, n2, dtype=np.float32)
    return x * 包 * BGM音量


def 量时长(路: str) -> tuple[float, int, int, int, int]:
    """返回 (秒数, 帧数, 宽, 高, 帧率)。"""
    with av.open(路) as c:
        v = c.streams.video[0]
        帧率 = float(v.average_rate)
        n = 0
        for _ in c.decode(v):
            n += 1
        return n / 帧率, n, v.codec_context.width, v.codec_context.height, int(round(帧率))


# ─────────────────────────── 音轨合成 ───────────────────────────

def 造音轨(片段: list[tuple[dict, str, float]], sr: int, 用BGM: bool = True) -> np.ndarray:
    """按「镜 → 时长」铺出整条音频。每一击精确落在镜内秒数上。"""
    总秒 = sum(d for _, _, d in 片段)
    # ★ 音轨必须和视频**等长**。多给半秒会导致容器尾部多出一条静音/拖尾；
    #   少给则最后一帧没声音。这里按帧数反推精确样数，误差 <1 样。
    总样 = int(round(总秒 * sr))
    print(f"\n  音轨总长 {总秒:.2f} 秒（{len(片段)} 镜，{总样} 样）")

    # ① 山风底噪：每个镜单独生成再拼，这样阵风不会跨镜连续（切镜时有换气感）
    风轨 = np.zeros((2, 总样), dtype=np.float32)
    位 = 0
    for i, (j, _, d) in enumerate(片段):
        增 = 0.0
        for 号, 量 in 风声:
            if 号 == j["号"]:
                增 = 量
        n = int(d * sr)
        if 增 > 0:
            w = 效.风(秒=d + 0.5, 种子=j["号"] * 13 + 3)     # 单声道
            w = 效._立体声(w, 0.30, j["号"] * 7)
            m = min(n, w.shape[0])
            风轨[:, 位:位 + m] += w[:m].T * (增 * 风音量)
        位 += n
    print(f"  ✓ 风声铺完  有效 RMS {np.sqrt((风轨**2).mean()):.4f}")

    # ② 音效：逐镜、逐点叠加
    #
    # ★ 关键：先按「镜」为单位把这一镜的所有打点铺进一个临时缓冲，量出这一镜的
    # 叠加峰值，**按镜**缩放。
    #
    # 来历：第一版直接把每一击乘上表里的音量叠进全局轨，结果 19 个镜的峰值
    # 叠到 1.0 以上（最狠的镜 27 叠到 2.68），触发全片 -2.4 dB 的整体缩放，
    # 把所有安静镜一起拖下去了。按镜缩放只压那些真的叠爆的镜，安静镜一点不动。
    效轨 = np.zeros((2, 总样), dtype=np.float32)
    位 = 0
    共 = 0
    压 = []                                  # (镜号, 原峰, 缩放系数)
    for j, _, d in 片段:
        cues = 音效表.get(j["号"], [])
        if not cues:
            位 += int(d * sr)
            continue
        n = int(d * sr)
        本镜 = np.zeros((2, n), dtype=np.float32)
        有效 = 0
        for k, (t, 名, 音) in enumerate(cues):
            if 名 not in 效.库:
                print(f"    ⚠ 镜 {j['号']:02d} 未知音效「{名}」")
                continue
            if t >= d:                     # 打点超出这一镜的长度，丢弃并告警
                print(f"    ⚠ 镜 {j['号']:02d} 的打点 {t}s 超出镜长 {d:.2f}s，已丢")
                continue
            # 同一个音效在同一镜内多次出现时换种子，避免听出是同一个采样
            a = 效.库[名](种子=j["号"] * 101 + k * 17 + 1)
            if a.ndim == 1:
                a = 效._立体声(a, 0.35, j["号"] * 3 + k)
            i0 = int(t * sr)
            m = min(a.shape[0], n - i0)
            if m > 0:
                本镜[:, i0:i0 + m] += a[:m].T * 音
                有效 += 1
        峰 = float(np.abs(本镜).max())
        if 峰 > 音效峰上限:
            系 = 音效峰上限 / 峰
            本镜 *= 系
            压.append((j["号"], 峰, 系))
        m2 = min(n, 总样 - 位)
        if m2 > 0:
            效轨[:, 位:位 + m2] += 本镜[:, :m2]
        共 += 有效
        位 += n
    print(f"  ✓ 音效 {共} 击打完  有效 RMS {np.sqrt((效轨**2).mean()):.4f}")
    if 压:
        最 = max(压, key=lambda x: x[1])
        print(f"  ✓ 按镜压峰 {len(压)} 个镜（上限 {音效峰上限}），最狠 镜{最[0]:02d} "
              f"{最[1]:.2f} → ×{最[2]:.2f}")
    else:
        print(f"  ✓ 没有镜叠爆（上限 {音效峰上限}）")

    # ③ 合轨
    混 = 风轨 + 效轨
    if 用BGM:
        bg = 读BGM(总样 / sr, sr)
        if bg is not None:
            混[:, :bg.shape[1]] += bg
            print(f"  ✓ BGM 已混入（{os.path.basename(BGM路)}，音量 {BGM音量}）")
    峰 = float(np.abs(混).max())
    if 峰 > 0.98:
        # 整体缩放而不是硬限幅：限幅会在打点处产生削顶失真，缩放只损失一点余量
        混 *= 0.98 / 峰
        print(f"  ✓ 削顶保护：整条缩放 {20*np.log10(0.98/峰):.1f} dB（峰值 {峰:.3f} → 0.980）")

    # ★ 响度归一：战斗片必须比对白片响，否则打点全被压在里面听不见。
    #   来历：首版成品 RMS 只有 0.0766，而《不烧心》（对白片）是 0.1213 ——
    #   方向反了 4 dB。
    #   ★★ 坑：不能「提到目标响度、超了就整体缩回」。本片峰值因子高达
    #   1.144/0.0766 ≈ 15（约 23 dB），远超影视常见的 12~18 dB，一提就先撞顶，
    #   结果反而被压成衰减 0.82，RMS 几乎没动（0.0766 → 0.0783）。
    #   正确顺序是：先按 RMS 提到目标 → 再用软膝限幅把尖峰收下来。
    混 = 软限(混 * (目标RMS / max(float(np.sqrt((混 ** 2).mean())), 1e-6)), 软限阈值, 峰值上限)
    print(f"  ✓ 响度归一：目标 RMS {目标RMS}，软限阈值 {软限阈值}，峰值上限 {峰值上限}")

    print(f"  ✓ 成品音轨 RMS {np.sqrt((混**2).mean()):.4f}  峰值 {np.abs(混).max():.3f}")
    return 混


# ─────────────────────────── 拼接 ───────────────────────────

def 拼(要: list[dict], 用BGM: bool = True, 出来: str | None = None,
       烧字幕: bool = False) -> str | None:
    from PIL import ImageDraw, ImageFont

    片段: list[tuple[dict, str, float]] = []
    for j in 要:
        p = os.path.join(镜根, f"{j['号']:02d}_动态.mp4")
        if os.path.isfile(p) and os.path.getsize(p) > 10240:
            片段.append((j, p, 0.0))
        else:
            print(f"  ⚠ 缺镜 {j['号']:02d}，跳过")
    if not 片段:
        print("❌ 一条动态都没有")
        return None

    出来 = 出来 or os.path.join(成片根, "光明顶_成片.mp4")
    os.makedirs(os.path.dirname(出来), exist_ok=True)

    # 先量每条的长度（音效打点必须知道镜内时长）
    量好 = []
    for j, p, _ in 片段:
        d, n, w, h, fr = 量时长(p)
        量好.append((j, p, d))
    print(f"规格 {w}x{h} {fr}fps  共 {len(量好)} 条  "
          f"总长 {sum(d for _, _, d in 量好):.2f} 秒")

    混 = 造音轨(量好, 采样率, 用BGM)

    字 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 字幕号) if 烧字幕 else None

    输出 = av.open(出来, "w")
    ov = 输出.add_stream("libx264", rate=fr)
    ov.width, ov.height, ov.pix_fmt = w, h, "yuv420p"
    ov.options = {"crf": "18", "preset": "medium"}
    oa = 输出.add_stream("aac", rate=采样率)
    oa.layout = "stereo"
    oa.format = "fltp"
    重采 = av.AudioResampler(format="fltp", layout="stereo", rate=采样率)

    总帧 = 0
    t0 = time.time()
    for k, (j, p, d) in enumerate(量好):
        with av.open(p) as c:
            v = c.streams.video[0]
            for f in c.decode(v):                 # ★ 只解视频，模型音轨直接不要
                im = f.to_image()
                if 字 is not None:
                    s = (j.get("字幕") or "").strip()
                    if s:
                        dr = ImageDraw.Draw(im)
                        bb = dr.textbbox((0, 0), s, font=字, stroke_width=描边)
                        tw = bb[2] - bb[0]
                        dr.text(((w - tw) // 2, h - 字幕边距 - (bb[3] - bb[1])),
                                s, font=字, fill=(255, 255, 255),
                                stroke_width=描边, stroke_fill=(0, 0, 0))
                nf = av.VideoFrame.from_image(im)
                nf.pts = None
                for pkt in ov.encode(nf):
                    输出.mux(pkt)
                总帧 += 1
        print(f"  [{k+1}/{len(量好)}] 镜 {j['号']:02d}  {d:>5.2f}s  "
              f"累计 {总帧} 帧  ({time.time()-t0:.0f}s)")
    for pkt in ov.encode():
        输出.mux(pkt)

    print("\n  封装音轨…")
    for i in range(0, 混.shape[1], 采样率 * 10):        # 每 10 秒一块，省内存
        块 = np.ascontiguousarray(混[:, i:i + 采样率 * 10])
        nf = av.AudioFrame.from_ndarray(块, format="fltp", layout="stereo")
        nf.sample_rate = 采样率
        nf.pts = None
        for 转 in 重采.resample(nf):
            for pkt in oa.encode(转):
                输出.mux(pkt)
    for pkt in oa.encode():
        输出.mux(pkt)
    输出.close()
    print(f"\n✅ {出来}\n   {总帧} 帧 / {总帧/fr:.2f} 秒 / "
          f"{os.path.getsize(出来)/2**20:.1f} MB")
    return 出来


def main() -> int:
    ap = argparse.ArgumentParser(description="《光明顶》成片合成")
    ap.add_argument("--只", nargs="*", type=int, default=[])
    ap.add_argument("--出", default=None)
    ap.add_argument("--干声", action="store_true", help="不垫 BGM")
    ap.add_argument("--烧字幕", action="store_true")
    a = ap.parse_args()

    from 做光明顶 import 读剧本
    镜表 = 读剧本(r"D:\DSHworkspace\B站\制作\光明顶_剧本.md")
    要 = [j for j in 镜表 if not a.只 or j["号"] in a.只]
    if a.只:
        # 只拼几镜时：如果这几镜在音效表里没有打点，提示一下
        for j in 要:
            if j["号"] not in 音效表:
                print(f"  ⚠ 镜 {j['号']:02d} 在音效表里没有打点")
    出 = 拼(要, not a.干声, a.出, a.烧字幕)
    return 0 if 出 else 1


if __name__ == "__main__":
    raise SystemExit(main())
