# -*- coding: utf-8 -*-
"""《龙族 · 雨夜》成片合成。

和《不烧心》合成器的根本区别
----------------------------
《不烧心》是**对白片**：音频主体是 MiniMax 生成的对白，我只垫了 BGM。
《光明顶》是**武打片**：模型音轨全部丢弃，音频从零合成。
**《龙族》沿用《光明顶》的路子 —— 模型音轨全丢，雨声 + BGM + 51 击打点全部自己造。**

理由：MiniMax 的音频轨在动作镜头里会念提示词（《不烧心》翻过的车），而这一部
全程是雨、雷、引擎、金属 —— 这些用程序合成既干净又能**精确对齐到帧**。

构成
----
    全程暴雨底噪（逐镜不同雨量）+ BGM + 逐击打点的音效（见 龙族音效表.py）

时长：14 镜 × 124 帧 @24fps = 72.33 秒。
"""

from __future__ import annotations

import argparse
import os
import time

import av
import numpy as np

import 音效 as 效

# ★ 音效表可按片替换：默认是初版 14 镜那套；后 30 秒重做版用
#   `--音效表 龙族后30秒音效表` 换成 8 镜那套（94 击）。
import 龙族音效表 as _默认表

音效表 = _默认表.音效表
雨量 = _默认表.雨量

# ─────────────────────────────── 常量 ───────────────────────────────

镜根 = r"D:\DSHworkspace\B站\成片\龙族\镜"
成片根 = r"D:\DSHworkspace\B站\成片\龙族"
BGM路 = r"D:\DSHworkspace\B站\素材\BGM\imperial-china-cinematic.mp3"

# ★ 音量
#   BGM 0.30：这首的 RMS 是 0.2178，乘 0.30 后 ≈ 0.065 —— 刚好垫在雨声底下。
#   选它的理由不是音色而是**结构**：它在第 44 秒有一整段推起，
#   而镜 09（黑影涌出，8×5.17=41.3s）正好是冲突开始的地方，卡点天然对齐。
#   对比：The_Broken 第 4 秒就满、Year_Of_The_Dragon 全程平 —— 都撑不起这个片子。
BGM音量 = 0.30
BGM淡入 = 1.5
BGM淡出 = 6.0

# ★ 雨音量 0.55：这一部**雨就是主角之一**，比《光明顶》的山风（0.5）再顶一点。
#   逐镜的雨量在 龙族音效表.雨量 里（车内 0.45 / 一般 1.0 / 突围 1.5）。
雨音量 = 0.55

音效峰上限 = 0.85       # 单镜内所有打点叠加后的峰值上限（超过就只压这一镜）
目标RMS = 0.135         # 全片响度目标，和《光明顶》同档
软限阈值 = 0.55
峰值上限 = 0.56         # ★ 必须留足：AAC 是有损变换编码，瞬态处会过冲 +5.6 dB
采样率 = 48000

字幕号 = 46
字幕边距 = 46
描边 = 4

# ★ 字幕表：镜号 → [(镜内起秒, 镜内止秒, 文字), …]
#   原设计写在《龙族_剧本.md》文末的独立表里（带镜内时间窗），
#   而每镜字段里没有「字幕」这一项 —— 所以必须在这张表里读，别指望 j["字幕"]。
字幕表: dict[int, list[tuple[float, float, str]]] = {
    10: [(2.2, 4.0, "不要怕，睁大眼睛。")],
    11: [(1.8, 3.2, "跑！")],
    14: [(1.6, 3.8, "儿子！开车走！")],
}


def 软限(x: np.ndarray, 阈值: float = 0.62, 上限: float = 0.94) -> np.ndarray:
    """tanh 软膝限幅：阈值以下完全线性，以上渐进压到上限。

    ★ 不能用硬限幅代替 —— 硬限幅在打点处会产生削顶失真，
      而软膝只把尖峰「掰弯」，听感上几乎无痕。
    """
    a = np.abs(x)
    if a.max() <= 阈值:
        return x
    超 = a > 阈值
    y = x.copy()
    余 = 上限 - 阈值
    y[超] = np.sign(x[超]) * (阈值 + 余 * np.tanh((a[超] - 阈值) / 余))
    return y


def 读BGM(要长: float, sr: int) -> np.ndarray | None:
    """把 BGM 解成 (2, N) float32。不够长就从 0 秒循环补齐。"""
    if not os.path.isfile(BGM路):
        print(f"  ⚠ BGM 不存在：{BGM路}")
        return None
    c = av.open(BGM路)
    a = c.streams.audio[0]
    xs = [f.to_ndarray().reshape(-1) for f in c.decode(a)]
    c.close()
    x = np.concatenate(xs).astype(np.float32)
    if x.max() > 2:
        x = x / 32768.0
    src = a.rate
    if src != sr:                                   # 线性重采样（够用，音质损失可忽略）
        n = int(len(x) / src * sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    if x.ndim == 1:
        x = np.stack([x, x])
    elif x.shape[0] == 1:
        x = np.repeat(x, 2, axis=0)
    要样 = int(round(要长 * sr))
    if x.shape[1] < 要样:                            # 循环补齐
        次 = int(np.ceil(要样 / x.shape[1]))
        x = np.tile(x, (1, 次))
    x = x[:, :要样].copy()
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
    总样 = int(round(总秒 * sr))
    print(f"\n  音轨总长 {总秒:.2f} 秒（{len(片段)} 镜，{总样} 样）")

    # ① 暴雨底噪：每个镜单独生成再拼。
    #    不跨镜连续是**有意的** —— 切镜时雨的相位一变，听感上就是「换了个机位」。
    雨轨 = np.zeros((2, 总样), dtype=np.float32)
    位 = 0
    for j, _, d in 片段:
        量 = 0.0
        for 号, v in 雨量:
            if 号 == j["号"]:
                量 = v
        n = int(d * sr)
        if 量 > 0:
            # +0.5 秒是为了让尾部淡出落在镜外，拼接处不会听到雨的断口
            w = 效.雨(秒=d + 0.5, 种子=j["号"] * 13 + 3, 强度=量)
            w = 效._立体声(w, 0.30, j["号"] * 7)
            m = min(n, w.shape[0])
            雨轨[:, 位:位 + m] += w[:m].T * (雨音量 * 量)
        位 += n
    print(f"  ✓ 雨声铺完  有效 RMS {np.sqrt((雨轨**2).mean()):.4f}")

    # ② 音效：逐镜、逐点叠加
    #
    # ★ 先按「镜」为单位把这一镜的所有打点铺进一个临时缓冲，量出这一镜的
    #   叠加峰值，**按镜**缩放。整体缩放会把安静的镜一起拖下去。
    效轨 = np.zeros((2, 总样), dtype=np.float32)
    位 = 0
    共 = 0
    压: list[tuple[int, float, float]] = []
    for j, _, d in 片段:
        cues = 音效表.get(j["号"], [])
        n = int(d * sr)
        if not cues:
            位 += n
            continue
        本镜 = np.zeros((2, n), dtype=np.float32)
        有效 = 0
        for k, (t, 名, 音) in enumerate(cues):
            if 名 not in 效.库:
                print(f"    ⚠ 镜 {j['号']:02d} 未知音效「{名}」")
                continue
            if t >= d:
                print(f"    ⚠ 镜 {j['号']:02d} 的打点 {t}s 超出镜长 {d:.2f}s，已丢")
                continue
            # 同一镜内同音效换种子，避免听出是同一采样
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
    混 = 雨轨 + 效轨
    if 用BGM:
        bg = 读BGM(总样 / sr, sr)
        if bg is not None:
            混[:, :bg.shape[1]] += bg
            print(f"  ✓ BGM 已混入（{os.path.basename(BGM路)}，音量 {BGM音量}）")
    峰 = float(np.abs(混).max())
    if 峰 > 0.98:
        混 *= 0.98 / 峰
        print(f"  ✓ 削顶保护：整条缩放 {20*np.log10(0.98/峰):.1f} dB（峰值 {峰:.3f} → 0.980）")

    # ★ 响度归一：顺序是「先按 RMS 提到目标 → 再用软膝把尖峰收下来」。
    #   反过来写（提到目标、超了就整体缩回）会先撞顶再被压回去，RMS 纹丝不动。
    前 = float(np.sqrt((混 ** 2).mean()))
    混 = 软限(混 * (目标RMS / max(前, 1e-6)), 软限阈值, 峰值上限)
    print(f"  ✓ 响度归一：RMS {前:.4f} → 目标 {目标RMS}，软限阈值 {软限阈值}，峰值上限 {峰值上限}")

    过 = int((np.abs(混) > 1.0).sum())
    print(f"  ✓ 成品音轨 RMS {np.sqrt((混**2).mean()):.4f}  "
          f"峰值 {np.abs(混).max():.3f}  过载 {过} 个采样")
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

    出来 = 出来 or os.path.join(成片根, "龙族_雨夜_成片.mp4")
    os.makedirs(os.path.dirname(出来), exist_ok=True)

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
        条 = 字幕表.get(j["号"], [])
        fk = -1
        with av.open(p) as c:
            v = c.streams.video[0]
            for f in c.decode(v):                 # ★ 只解视频，模型音轨直接不要
                fk += 1
                ts = fk / fr                      # 镜内秒数
                im = f.to_image()
                if 字 is not None and 条:
                    for 起, 止, s in 条:
                        if 起 <= ts <= 止:
                            dr = ImageDraw.Draw(im)
                            bb = dr.textbbox((0, 0), s, font=字, stroke_width=描边)
                            tw = bb[2] - bb[0]
                            dr.text(((w - tw) // 2, h - 字幕边距 - (bb[3] - bb[1])),
                                    s, font=字, fill=(255, 255, 255),
                                    stroke_width=描边, stroke_fill=(0, 0, 0))
                            break
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
    for i in range(0, 混.shape[1], 采样率 * 10):
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
    global 镜根, 成片根, 音效表, 雨量
    ap = argparse.ArgumentParser(description="《龙族 · 雨夜》成片合成")
    ap.add_argument("--只", nargs="*", type=int, default=[])
    ap.add_argument("--出", default=None)
    ap.add_argument("--干声", action="store_true", help="不垫 BGM")
    ap.add_argument("--烧字幕", action="store_true")
    ap.add_argument("--剧本", default=None, help="换剧本（默认用 做龙族.剧本路）")
    ap.add_argument("--根", default=None, help="换素材根目录（镜/ 与成片输出都跟着走）")
    ap.add_argument("--音效表", dest="音效表名", default=None, help="音效表模块名")
    a = ap.parse_args()

    if a.根:
        成片根 = a.根
        镜根 = os.path.join(成片根, "镜")
    if a.音效表名:
        import importlib

        新表 = importlib.import_module(a.音效表名)
        音效表 = 新表.音效表
        雨量 = 新表.雨量

    from 做龙族 import 剧本路 as 默认剧本路, 读剧本

    剧本 = a.剧本 or 默认剧本路
    镜表 = 读剧本(剧本)
    要 = [j for j in 镜表 if not a.只 or j["号"] in a.只]
    漏 = [j["号"] for j in 要 if j["号"] not in 音效表]
    if 漏:
        print(f"  ⚠ 镜 {漏} 在音效表里没有打点")
    出 = 拼(要, not a.干声, a.出, a.烧字幕)
    return 0 if 出 else 1


if __name__ == "__main__":
    raise SystemExit(main())
