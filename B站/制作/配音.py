# -*- coding: utf-8 -*-
"""
配音 —— 给无声成片加「旁白 + 背景音乐」

为什么需要它：视频拼接.py / 图集运镜.py 出的 mp4 是纯画面的（末尾只打印一句
「BGM 未处理 —— 需要单独混音步骤」）。这个脚本就是那一步。

本机 ffmpeg 不在 PATH，所以全程走 PyAV：
  · 解码音频用 AudioResampler 统一到 48kHz / fltp / stereo，拿到 numpy 直接相加
  · 视频默认**直接 remux 复制**（不重编码，几秒完事）
  · 只有当旁白比画面长、需要把画面「冻住最后一帧」拉长时才重编码
  · 编码用 AAC，混完做峰值保护（限幅到 -1 dBFS），避免叠加削顶爆音

用法：
  # 最简：一条旁白 + 一条 BGM
  python 配音.py --视频 成片.mp4 --旁白 旁白01.wav --bgm 音乐.mp3 --输出 成片_有声.mp4

  # 多段旁白按顺序拼（两种写法都行）
  python 配音.py --视频 成片.mp4 --旁白 01.wav 02.wav 03.wav --bgm 音乐.mp3 --输出 out.mp4
  python 配音.py --视频 成片.mp4 --旁白 01.wav --旁白 02.wav --bgm 音乐.mp3 --输出 out.mp4

  # 旁白 0.5 秒后开口，段间留 0.4 秒，BGM 压低一点
  python 配音.py --视频 成片.mp4 --旁白 01.wav 02.wav --bgm 音乐.mp3 ^
      --旁白起始 0.5 --间隔 0.4 --bgm音量 0.15 --旁白音量 1.2 --输出 out.mp4

  # 旁白比画面长 30 秒：把画面最后一帧冻住补 30 秒（会重编码，慢）
  python 配音.py --视频 成片.mp4 --旁白 长旁白.wav --超长处理 延长视频 --输出 out.mp4

  # 旁白比画面长：干脆把多余的旁白切掉
  python 配音.py --视频 成片.mp4 --旁白 长旁白.wav --超长处理 裁掉 --输出 out.mp4

参数速查：
  --视频        无声（或有声）mp4，必填
  --旁白        一个或多个 wav/mp3/flac/m4a，按给出顺序拼接。可省略（只加 BGM）
  --bgm         mp3/wav，比目标时长短会自动循环，末尾 3 秒淡出
  --旁白音量    默认 1.0（人声是主角，一般别动）
  --bgm音量     默认 0.18（BGM 是衬底；0.35 以上会盖住人声）
  --原声音量    视频自带音轨的音量，默认 1.0；视频本来无声就无所谓
  --旁白起始    旁白整体延后几秒开口，默认 0.0
  --间隔        相邻两段旁白之间插几秒静音，默认 0.25
  --超长处理    「旁白比画面长」怎么办：延长视频(默认) / 裁掉 / 报错
  --目标时长    强制输出时长（秒）。不填则 = max(画面, 旁白)
  --输出        输出 mp4，必填

退出码：0 成功；1 参数或素材有问题；2 混音/编码失败
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from fractions import Fraction

import av
import numpy as np
from av.audio.resampler import AudioResampler

# ----------------------------------------------------------------- 基础设置
采样率 = 48000          # 输出统一 48k，避免重采样二次损失
声道布局 = "stereo"
峰值上限 = 0.891        # -1 dBFS，混音后限幅，防削顶
淡出秒 = 3.0            # BGM 收尾淡出
淡入秒 = 0.8            # BGM 开头淡入
时基视频 = Fraction(1, 1_000_000)   # 重编码画面时统一用微秒时基

音频后缀 = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma"}


def 报(*a):
    print(*a, flush=True)


# ----------------------------------------------------------------- 音频解码
def 解码音频(路径: str) -> np.ndarray:
    """把任意音频解成 float32 (2, N) @48k。失败抛异常。"""
    if not os.path.exists(路径):
        raise FileNotFoundError(f"找不到音频：{路径}")
    重采样 = AudioResampler(format="fltp", layout=声道布局, rate=采样率)
    块: list[np.ndarray] = []
    with av.open(路径) as 容器:
        if not 容器.streams.audio:
            raise ValueError(f"这个文件里没有音轨：{路径}")
        流 = 容器.streams.audio[0]
        for 帧 in 容器.decode(流):
            for 出 in 重采样.resample(帧):
                块.append(出.to_ndarray())
        for 出 in 重采样.resample(None):      # flush，冲掉重采样器里的尾巴
            块.append(出.to_ndarray())
    if not 块:
        return np.zeros((2, 0), dtype=np.float32)
    数据 = np.concatenate(块, axis=1)
    if 数据.shape[0] == 1:                    # 单声道复制成双声道
        数据 = np.repeat(数据, 2, axis=0)
    return np.ascontiguousarray(数据[:2], dtype=np.float32)


def 读时长(路径: str) -> float:
    try:
        with av.open(路径) as c:
            return float(c.duration / av.time_base) if c.duration else 0.0
    except Exception:
        return 0.0


def 造静音(秒: float) -> np.ndarray:
    return np.zeros((2, max(0, int(round(秒 * 采样率)))), dtype=np.float32)


# ----------------------------------------------------------------- 旁白拼接
def 拼旁白(文件们: list[str], 起始: float, 间隔: float, 已有: np.ndarray,
           上限样本: int | None) -> tuple[np.ndarray, list[float]]:
    """把多段旁白按顺序拼进 (起始 + 间隔) 的时间轴。返回 (音轨, 每段起点秒)"""
    片段: list[np.ndarray] = [已有]
    起点表: list[float] = []
    光标 = 起始
    for i, 路 in enumerate(文件们):
        数据 = 解码音频(路)
        段长 = 数据.shape[1] / 采样率
        起点表.append(光标)
        # 把光标对齐到 起始 + 已排布的总长
        应有 = int(round(光标 * 采样率))
        if 应有 > 片段总长(片段):
            片段.append(造静音((应有 - 片段总长(片段)) / 采样率))
        片段.append(数据)
        光标 += 段长
        if i != len(文件们) - 1:
            片段.append(造静音(间隔))
            光标 += 间隔
    轨 = np.concatenate(片段, axis=1)
    if 上限样本 is not None:
        轨 = 轨[:, :上限样本]
    return 轨, 起点表


def 铺旁白表(表: list[dict], 底轨: np.ndarray | None,
            上限样本: int | None) -> tuple[np.ndarray, list[float]]:
    """按**显式时间点**铺旁白，而不是「首尾相接」。

    短剧里每句话必须落在它那个镜头上，不能顺着往前排，所以需要这张表：
        [{"文件": "001.wav", "起始": 2.40}, {"文件": "002.wav", "起始": 7.85}]

    与前一段重叠是合法的（对白叠旁白），重叠处直接相加——所以这里是往一个
    大缓冲里累加，不是拼接。
    """
    条目 = []
    最大末 = 0
    for 项 in 表:
        路 = 项["文件"] if isinstance(项, dict) else str(项)
        if not os.path.isabs(路):
            路 = os.path.abspath(路)
        if not os.path.exists(路):
            raise SystemExit(f"❌ 旁白表里的文件不存在：{路}")
        起 = float((项 or {}).get("起始", 0.0)) if isinstance(项, dict) else 0.0
        数据 = 解码音频(路)
        起样 = max(0, int(round(起 * 采样率)))
        条目.append((起样, 数据))
        最大末 = max(最大末, 起样 + 数据.shape[1])

    总 = 上限样本 if 上限样本 is not None else 最大末
    总 = max(总, 最大末)
    轨 = np.zeros((2, 总), dtype=np.float32)
    if 底轨 is not None and 底轨.shape[1]:
        n = min(底轨.shape[1], 总)
        轨[:, :n] += 底轨[:, :n]

    起点表 = []
    for 起样, 数据 in 条目:
        n = min(数据.shape[1], 总 - 起样)
        if n > 0:
            轨[:, 起样:起样 + n] += 数据[:, :n]
        起点表.append(起样 / 采样率)
    return 轨, 起点表


def 片段总长(片段: list[np.ndarray]) -> int:
    return sum(x.shape[1] for x in 片段)


# ----------------------------------------------------------------- BGM 处理
def 铺BGM(路径: str, 目标样本: int, 音量: float) -> np.ndarray:
    原始 = 解码音频(路径)
    if 原始.shape[1] == 0:
        return np.zeros((2, 目标样本), dtype=np.float32)
    次数 = int(np.ceil(目标样本 / 原始.shape[1]))
    铺满 = np.tile(原始, (1, 次数))[:, :目标样本].copy()
    n = 铺满.shape[1]
    # 淡入
    淡入n = min(int(淡入秒 * 采样率), n)
    if 淡入n > 0:
        铺满[:, :淡入n] *= np.linspace(0.0, 1.0, 淡入n, dtype=np.float32)
    # 淡出
    淡出n = min(int(淡出秒 * 采样率), n)
    if 淡出n > 0:
        铺满[:, n - 淡出n:] *= np.linspace(1.0, 0.0, 淡出n, dtype=np.float32)
    return 铺满 * np.float32(音量)


# ----------------------------------------------------------------- 编码
def 建音轨(容器):
    """只创建 AAC 流，不写任何包。必须在 mux 第一个视频包之前调用。"""
    流 = 容器.add_stream("aac", rate=采样率)
    流.bit_rate = 192_000
    流.layout = 声道布局
    流.time_base = Fraction(1, 采样率)      # 不显式设的话这里是 None，mux 会炸
    return 流


def 写音频(容器, 流, 轨: np.ndarray) -> int:
    """轨: float32 (2, N) @48k → AAC 流，返回流对象"""
    帧长 = 流.codec_context.frame_size or 1024    # 编码器 open 之前读出的是 0
    总 = 轨.shape[1]

    包数 = 0
    i = 0
    while i < 总:
        块 = 轨[:, i:i + 帧长]
        if 块.shape[1] < 帧长:                     # 最后一帧补零凑满
            块 = np.pad(块, ((0, 0), (0, 帧长 - 块.shape[1])))
        帧 = av.AudioFrame.from_ndarray(np.ascontiguousarray(块), format="fltp",
                                         layout=声道布局)
        帧.sample_rate = 采样率
        帧.pts = i                                 # 单位 = 帧时基 = 1/采样率
        帧.time_base = Fraction(1, 采样率)
        for 包 in 流.encode(帧):
            容器.mux(包)
            包数 += 1
        i += 帧长
    for 包 in 流.encode():                          # flush 编码器缓冲
        容器.mux(包)
        包数 += 1
    return 包数


# ----------------------------------------------------------------- 视频
def 建视频流(容器, 入流, fps: float, 速度: str = "veryfast"):
    """只创建 H.264 流，不写任何包。必须在 mux 第一个包之前调用。"""
    流 = 容器.add_stream("libx264", rate=Fraction(int(round(fps * 1000)), 1000))
    流.width = 入流.codec_context.width
    流.height = 入流.codec_context.height
    流.pix_fmt = "yuv420p"
    流.time_base = 时基视频
    流.options = {"crf": "18", "preset": 速度}
    return 流


def 帧时刻(帧号: int, fps: float) -> int:
    """第 n 帧在 时基视频（微秒）下的 pts。整数 fps 精确，23.976 之类误差 <1µs/帧"""
    return int(round(帧号 * 1_000_000 / fps))


def 重编码视频(入容器, 出容器, 出流, 入流, 目标帧数: int | None, fps: float):
    """解码 → 重编码，末帧冻住补齐到 目标帧数。用于「延长视频」模式。"""
    最后帧 = None
    n = 0
    包数 = 0
    for 帧 in 入容器.decode(入流):
        if 目标帧数 is not None and n >= 目标帧数:
            break
        新 = 帧.reformat(format="yuv420p")
        新.pts = 帧时刻(n, fps)
        新.time_base = 时基视频
        for 包 in 出流.encode(新):
            出容器.mux(包)
            包数 += 1
        最后帧 = 新
        n += 1
    # 冻住最后一帧，补到目标帧数
    if 目标帧数 is not None and 最后帧 is not None:
        while n < 目标帧数:
            新 = 最后帧.reformat(format="yuv420p")
            新.pts = 帧时刻(n, fps)
            新.time_base = 时基视频
            for 包 in 出流.encode(新):
                出容器.mux(包)
                包数 += 1
            n += 1
    for 包 in 出流.encode():
        出容器.mux(包)
        包数 += 1
    return n, 包数


# ----------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser(
        description="给无声视频加旁白 + BGM（纯 PyAV，不需要 ffmpeg 命令行）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--视频", required=True)
    ap.add_argument("--旁白", nargs="+", action="extend", default=[], metavar="WAV")
    ap.add_argument("--旁白表", default=None, metavar="JSON",
                    help="按显式时间点铺旁白（短剧必备）："
                         '[{"文件":"001.wav","起始":2.4}, ...]；'
                         "与 --旁白 二选一，重叠处相加（对白叠旁白）")
    ap.add_argument("--bgm", default=None)
    ap.add_argument("--旁白音量", type=float, default=1.0)
    ap.add_argument("--bgm音量", type=float, default=0.18)
    ap.add_argument("--原声音量", type=float, default=1.0)
    ap.add_argument("--旁白起始", type=float, default=0.0)
    ap.add_argument("--间隔", type=float, default=0.25)
    ap.add_argument("--超长处理", choices=["延长视频", "裁掉", "报错"], default="延长视频")
    ap.add_argument("--目标时长", type=float, default=None)
    ap.add_argument("--编码速度", default="veryfast",
                    help="重编码时 libx264 preset，默认 veryfast")
    ap.add_argument("--输出", required=True)
    args = ap.parse_args()

    # ---------------- 校验素材
    if not os.path.exists(args.视频):
        return 报错返回(f"❌ 找不到视频：{args.视频}", 1)

    # 旁白表：按显式时间点铺（短剧用）
    旁白表 = None
    if args.旁白表:
        if not os.path.exists(args.旁白表):
            return 报错返回(f"❌ 找不到旁白表：{args.旁白表}", 1)
        try:
            with open(args.旁白表, encoding="utf-8-sig") as f:
                原始 = json.load(f)
        except Exception as e:
            return 报错返回(f"❌ 旁白表读不了（要 UTF-8 JSON）：{e}", 1)
        if isinstance(原始, dict):
            原始 = 原始.get("清单") or 原始.get("旁白") or 原始.get("台词") or []
        if not isinstance(原始, list):
            return 报错返回("❌ 旁白表要是一个 JSON 数组", 1)
        旁白表 = 原始
        报(f"📋 旁白表 {len(旁白表)} 句（按时间点铺）")
    elif args.旁白:
        for p in args.旁白:
            if not os.path.exists(p):
                return 报错返回(f"❌ 找不到旁白：{p}", 1)

    if args.bgm and not os.path.exists(args.bgm):
        return 报错返回(f"❌ 找不到 BGM：{args.bgm}", 1)
    if not 旁白表 and not args.旁白 and not args.bgm:
        return 报错返回("❌ 既没给旁白也没给 BGM，那就不用混音了", 1)

    画面时长 = 读时长(args.视频)
    if 旁白表 is not None:
        旁白末尾 = 0.0
        for 项 in 旁白表:
            路 = 项["文件"] if isinstance(项, dict) else str(项)
            起 = float(项.get("起始", 0.0)) if isinstance(项, dict) else 0.0
            旁白末尾 = max(旁白末尾, 起 + 读时长(路))
        报(f"🎬 画面 {画面时长:.2f}s   旁白表末尾 {旁白末尾:.2f}s（{len(旁白表)} 句）")
    else:
        旁白时长 = sum(读时长(p) for p in args.旁白) + args.间隔 * max(0, len(args.旁白) - 1)
        旁白末尾 = args.旁白起始 + 旁白时长 if args.旁白 else 0.0
        报(f"🎬 画面 {画面时长:.2f}s   旁白排布 {旁白末尾:.2f}s "
           f"（{len(args.旁白)} 段，起始 {args.旁白起始}s，间隔 {args.间隔}s）")

    # ---------------- 决定目标时长
    需要画面至少 = 0.0
    if args.目标时长:
        目标时长 = args.目标时长
    else:
        目标时长 = max(画面时长, 旁白末尾)
    if args.目标时长 and args.目标时长 < 旁白末尾:
        报(f"   ⚠ --目标时长 {args.目标时长}s 比旁白末尾 {旁白末尾:.2f}s 短，"
           f"按 --超长处理={args.超长处理} 处理")

    # 旁白比画面长的分支
    延长秒 = 0.0
    if 旁白末尾 > 画面时长 + 0.02:
        超出 = 旁白末尾 - 画面时长
        报(f"   ⚠ 旁白比画面长 {超出:.2f}s → {args.超长处理}")
        if args.超长处理 == "报错":
            return 报错返回("❌ 旁白比画面长，按 --超长处理=报错 中止", 1)
        if args.超长处理 == "裁掉":
            目标时长 = 画面时长
        else:
            目标时长 = 旁白末尾
            延长秒 = 超出
    else:
        目标时长 = min(目标时长, 画面时长) if 旁白末尾 <= 画面时长 else 目标时长

    目标样本 = int(round(目标时长 * 采样率))
    报(f"🎯 目标时长 {目标时长:.2f}s（{目标样本} 样本 @{采样率}Hz）")

    # ---------------- 拼音频
    空轨 = np.zeros((2, 0), dtype=np.float32)
    if 旁白表 is not None:
        旁白轨, 起点表 = 铺旁白表(旁白表, 空轨, 目标样本)
    else:
        旁白轨, 起点表 = 拼旁白(args.旁白, args.旁白起始, args.间隔, 空轨, 目标样本)
    for i, t in enumerate(起点表, 1):
        报(f"   旁白[{i}] 起点 {t:.2f}s")

    混 = np.zeros((2, 目标样本), dtype=np.float32)
    if 旁白轨.shape[1] and args.旁白音量:
        n = min(旁白轨.shape[1], 目标样本)
        混[:, :n] += 旁白轨[:, :n] * np.float32(args.旁白音量)

    # 视频原声（如果有）
    有原声 = False
    try:
        with av.open(args.视频) as c:
            有原声 = bool(c.streams.audio)
    except Exception:
        pass
    if 有原声 and args.原声音量:
        报("   ℹ 视频自带音轨，一并混入")
        原 = 解码音频(args.视频)
        n = min(原.shape[1], 目标样本)
        混[:, :n] += 原[:, :n] * np.float32(args.原声音量)

    if args.bgm and args.bgm音量:
        混 += 铺BGM(args.bgm, 目标样本, args.bgm音量)
        报(f"   🎵 BGM 音量 {args.bgm音量}（不足自动循环，首 {淡入秒}s 淡入 / 末 {淡出秒}s 淡出）")

    # ---------------- 峰值保护
    峰 = float(np.max(np.abs(混))) if 混.size else 0.0
    if 峰 > 峰值上限:
        增益 = 峰值上限 / 峰
        混 *= np.float32(增益)
        报(f"   🔉 峰值 {峰:.3f} → 限幅 {峰值上限:.3f}（整体 ×{增益:.3f}）")
    else:
        报(f"   🔉 峰值 {峰:.3f}，未触发限幅")
    混 = np.ascontiguousarray(np.clip(混, -1.0, 1.0), dtype=np.float32)

    # ---------------- 写输出
    目录 = os.path.dirname(os.path.abspath(args.输出))
    os.makedirs(目录, exist_ok=True)
    末尾秒 = 目标时长

    try:
        with av.open(args.视频) as 入:
            入流 = 入.streams.video[0]
            fps = float(入流.average_rate) if 入流.average_rate else 24.0
            with av.open(args.输出, mode="w", options={"movflags": "+faststart"}) as 出:
                # ★ 先把所有流建好 —— mp4 复用器不接受「写了包之后再 add_stream」
                音轨 = 建音轨(出)
                if 延长秒 > 0.005:
                    视频轨 = 建视频流(出, 入流, fps, args.编码速度)
                    目标帧数 = int(round(目标时长 * fps))
                    报(f"   🔄 重编码画面（{args.编码速度}），补到 {目标帧数} 帧，"
                       f"末帧冻住 +{延长秒:.2f}s …")
                    n, 视频包 = 重编码视频(入, 出, 视频轨, 入流, 目标帧数, fps)
                    报(f"      写出 {n} 帧 / {视频包} 包")
                else:
                    # PyAV 18 的 add_stream() 不再接受 template=，改用这个专用方法
                    视频轨 = 出.add_stream_from_template(入流)
                    视频包 = 0
                    for 包 in 入.demux(入流):
                        if 包.dts is None and 包.pts is None:
                            continue
                        包.stream = 视频轨
                        if 包.pts is not None:
                            包.pts -= 入流.start_time or 0
                        if 包.dts is not None:
                            包.dts -= 入流.start_time or 0
                        出.mux(包)
                        视频包 += 1
                    报(f"   📼 画面直拷 {视频包} 个包（未重编码）")
                音频包 = 写音频(出, 音轨, 混)
                报(f"   🔊 音轨写出 {音频包} 个包（{目标时长:.2f}s）")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 报错返回(f"❌ 混音失败：{type(e).__name__}: {e}", 2)

    # ---------------- 校验产物
    try:
        with av.open(args.输出) as c:
            d = float(c.duration / av.time_base) if c.duration else -1
            v = c.streams.video[0]
            a = c.streams.audio[0]
            校验 = (f"画面 {v.codec_context.width}x{v.codec_context.height} "
                    f"{float(v.average_rate):.0f}fps {v.codec_context.name} | "
                    f"音轨 {a.codec_context.name} {a.rate}Hz {a.layout.name}")
    except Exception as e:
        校验 = f"（产物校验失败：{e}）"
        d = -1

    大小 = os.path.getsize(args.输出) / 1024 / 1024
    报(f"\n✅ {args.输出}")
    报(f"   时长 {d:.2f}s   大小 {大小:.1f} MB")
    报(f"   {校验}")
    if d > 0 and abs(d - 末尾秒) > 1.0:
        报(f"   ⚠ 产时长与目标差 {abs(d - 末尾秒):.2f}s（mp4 音视频轨长不一致时属正常）")
    return 0


def 报错返回(消息: str, 码: int) -> int:
    print(消息, file=sys.stderr, flush=True)
    return 码


if __name__ == "__main__":
    sys.exit(main())
