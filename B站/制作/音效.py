# -*- coding: utf-8 -*-
"""程序合成音效 —— 《光明顶》战斗片专用。

为什么自己合成：这条链上唯一稳定可控的音频来源就是 numpy。
外部音效库要下载、要版权、要对齐，而且我这边网不稳。
合成的好处是**每个音效都能精确对齐到帧号**，且时长/力度随时可调。

所有函数返回 float32 单声道 numpy 数组，范围约 [-1, 1]。

用法：
    from 音效 import 库
    a = 库['拳'](种子=1)              # 单发
    a = 库['风'](秒=5.0, 种子=2)      # 循环底噪
"""
from __future__ import annotations

import numpy as np

采样率 = 48000


# ─────────────────────────────── 工具 ───────────────────────────────

def _n(秒: float) -> int:
    return max(1, int(秒 * 采样率))


def _包络(n: int, 起: float, 衰: float, 幂: float = 2.0) -> np.ndarray:
    """攻击-衰减包络。起/衰单位是秒。"""
    a = _n(起)
    r = max(1, n - a)
    atk = np.linspace(0.0, 1.0, a, dtype=np.float32) ** (1.0 / max(幂, 0.05))
    dec = np.exp(-np.linspace(0.0, 5.0, r, dtype=np.float32))
    return np.concatenate([atk, dec])[:n]


def _低通(x: np.ndarray, 截止: float, 阶: int = 2) -> np.ndarray:
    """单极点 IIR 低通（级联 阶 次）。够用且不依赖 scipy。"""
    a = np.exp(-2.0 * np.pi * 截止 / 采样率)
    y = x.astype(np.float32).copy()
    for _ in range(阶):
        out = np.empty_like(y)
        acc = 0.0
        for i in range(len(y)):          # 纯 Python 循环，短音频可以接受
            acc = (1.0 - a) * y[i] + a * acc
            out[i] = acc
        y = out
    return y


def _低通快(x: np.ndarray, 截止: float, 阶: int = 2) -> np.ndarray:
    """用 FFT 做陡峭低通，长音频用这个（快得多）。"""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / 采样率)
    H = 1.0 / (1.0 + (f / max(截止, 1.0)) ** (2 * 阶))
    return np.fft.irfft(X * H, n).astype(np.float32)


def _高通快(x: np.ndarray, 截止: float, 阶: int = 2) -> np.ndarray:
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / 采样率)
    H = (f / max(截止, 1.0)) ** (2 * 阶) / (1.0 + (f / max(截止, 1.0)) ** (2 * 阶))
    return np.fft.irfft(X * H, n).astype(np.float32)


def _带通快(x: np.ndarray, 低: float, 高: float, 阶: int = 2) -> np.ndarray:
    """FFT 带通。_低通快 与 _高通快 串联，斜率可控。

    这个函数是修「风听起来像白噪声」的关键：原来只做了低通 + 一路几乎全带的
    高通嘶声，高频能量压倒低频本体，重心冲到 9.5 kHz。所有噪声类音效都必须
    明确锁在一个频带里。
    """
    return _高通快(_低通快(x, 高, 阶), 低, 阶)


def _归一(x: np.ndarray, 峰: float = 1.0) -> np.ndarray:
    m = float(np.max(np.abs(x))) or 1.0
    return (x / m * 峰).astype(np.float32)


def _层(x: np.ndarray, 目标: float) -> np.ndarray:
    """把一层噪声归一到指定 RMS 再混。

    ★ 为什么必须有这个：白噪声过完 300~1800 Hz 带通后，RMS 只剩原来的
      sqrt(1500/24000) ≈ 0.25。如果各层按「写死的幅度」相加，中频层会被
      低频层彻底盖住——实测「掌」的重心只有 49 Hz 就是这么来的。
      按 RMS 配平才能让每一层真正出现在混音里。
    """
    r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    return (x / r * 目标).astype(np.float32) if r > 1e-9 else x


def _立体声(x: np.ndarray, 宽: float = 0.35, 种子: int = 0) -> np.ndarray:
    """单声道转轻微去相关的立体声（听起来比纯 mono 宽）。"""
    rng = np.random.default_rng(种子)
    n = len(x)
    d = int(宽 * 0.004 * 采样率)               # 几毫秒的延迟
    if d <= 0:
        return np.stack([x, x], axis=1)
    L = x
    R = np.concatenate([np.zeros(d, np.float32), x[:-d]])
    R = R * (1.0 - 宽 * 0.5) + x * (宽 * 0.5)
    return np.stack([L, R * (0.96 + rng.random() * 0.08)], axis=1).astype(np.float32)


# ─────────────────────────────── 音效 ───────────────────────────────

def 风(秒: float = 6.0, 种子: int = 0) -> np.ndarray:
    """高山寒风：低频滚动的噪声底。用于铺满全片。

    频带锁在 40~1400 Hz（body）+ 一点点 2~5 kHz 的嘶声。
    重心目标 ~350 Hz —— 超过 1 kHz 就变成「吹麦克风」而不是山风了。
    """
    n = _n(秒)
    rng = np.random.default_rng(1000 + 种子)
    x = rng.standard_normal(n).astype(np.float32)
    body = _层(_带通快(x, 35, 800, 2), 0.50)                 # 风的主体：低频滚动
    body += _层(_带通快(x, 150, 1100, 1), 0.22)              # 上层：让风有「厚度」
    hiss = _层(_带通快(x, 1500, 4000, 2), 0.030)             # 只留一丝嘶声
    y = body + hiss
    # 缓慢的强弱起伏（阵风感），周期 4~9 秒
    t = np.arange(n, dtype=np.float32) / 采样率
    for _ in range(4):
        p = rng.uniform(3.5, 9.0)
        y *= (1.0 + 0.42 * np.sin(2 * np.pi * t / p + rng.uniform(0, 6.28))).astype(np.float32)
    # 首尾淡入淡出，方便无缝循环与拼接
    f = _n(0.8)
    y[:f] *= np.linspace(0, 1, f, dtype=np.float32)
    y[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    return _归一(y, 0.5)


def 啸(秒: float = 0.55, 种子: int = 0) -> np.ndarray:
    """破空声：挥掌、挥剑、身体掠过的 whoosh。"""
    n = _n(秒)
    rng = np.random.default_rng(2000 + 种子)
    x = rng.standard_normal(n).astype(np.float32)
    # 带通中心频率从高扫到低，模拟由远及近再远去
    t = np.linspace(0, 1, n, dtype=np.float32)
    y = np.zeros(n, np.float32)
    seg = 8
    for i in range(seg):
        a, b = i * n // seg, (i + 1) * n // seg
        c = 3200 * (1.0 - t[a]) ** 1.6 + 260
        y[a:b] = _低通快(_高通快(x[a:b], c * 0.55, 1), c * 1.7, 1)
    y *= _包络(n, 0.045, 秒, 2.4)
    y = _高通快(y, 240, 1)
    return _归一(y, 0.85)


def 掌(种子: int = 0) -> np.ndarray:
    """肉击/掌击：低频冲击 + 中频拍打。拳掌相交的基底。

    原来重心只有 56 Hz（太闷，听着像远处关门）。加了 300~1800 Hz 的
    「拍」层，重心目标 ~250 Hz，峰值在起振后 30 ms 内。
    """
    d = 0.55
    n = _n(d)
    rng = np.random.default_rng(3000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    x = rng.standard_normal(n).astype(np.float32)
    # 低频「砰」—— 按 RMS 配平，低频给 0.42
    f0 = rng.uniform(62, 88)
    lo = np.sin(2 * np.pi * f0 * t) * np.exp(-t * 26)
    lo += np.sin(2 * np.pi * f0 * 0.5 * t) * np.exp(-t * 14) * 0.6
    lo = _层(lo, 0.42)
    # 中频「拍」—— 0.34，这一层是原来缺的
    中 = _层(_带通快(x, 300, 1800, 2) * np.exp(-t * 34), 0.34)
    # 高频皮肉「啪」
    高 = _层(_带通快(x, 2200, 7000, 2) * np.exp(-t * 95), 0.16)
    y = lo + 中 + 高
    y[: _n(0.002)] *= np.linspace(0, 1, _n(0.002), dtype=np.float32)
    return _归一(y, 0.98)


def 兵器(种子: int = 0) -> np.ndarray:
    """金属相击：非谐分音 + 快衰减。剑与剑、剑与护腕。"""
    d = 1.1
    n = _n(d)
    rng = np.random.default_rng(4000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    y = np.zeros(n, np.float32)
    # 6~10 个非谐金属分音
    for _ in range(int(rng.integers(6, 11))):
        f = rng.uniform(1400, 7200)
        y += (np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
              * np.exp(-t * rng.uniform(5.5, 16.0)) * rng.uniform(0.25, 1.0)).astype(np.float32)
    # 起振的宽带噪声
    nz = _高通快(rng.standard_normal(n).astype(np.float32), 3000, 2)
    y += nz * np.exp(-t * 120) * 0.9
    y = _高通快(y, 700, 1)
    return _归一(y, 0.9)


def 鸣(秒: float = 2.2, 种子: int = 0) -> np.ndarray:
    """剑鸣/金属余韵：细长的高频颤动。用于拔剑、剑指人。"""
    n = _n(秒)
    rng = np.random.default_rng(5000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    y = np.zeros(n, np.float32)
    for _ in range(4):
        f = rng.uniform(2600, 5200)
        # 轻微颤音
        vib = 1.0 + 0.004 * np.sin(2 * np.pi * rng.uniform(5, 11) * t)
        y += (np.sin(2 * np.pi * f * vib * t)
              * np.exp(-t * rng.uniform(1.1, 2.6)) * 0.6).astype(np.float32)
    return _归一(y, 0.55)


def 炸(秒: float = 2.6, 种子: int = 0) -> np.ndarray:
    """气浪爆炸：低频轰鸣 + 中频咆哮 + 长尾。用于太极气浪、掌剑相交。

    原来重心 84 Hz（只有闷响，没有「炸」的撕裂感）。加了 400~3000 Hz 的
    中频咆哮层，重心目标 ~400 Hz。
    """
    n = _n(秒)
    rng = np.random.default_rng(6000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    x = rng.standard_normal(n).astype(np.float32)
    lo = _带通快(x, 25, 130, 2) * np.exp(-t * 2.4) * 3.0        # 低频压力
    mid = _带通快(x, 140, 900, 2) * np.exp(-t * 4.2) * 2.0      # 中频body
    roar = _带通快(x, 900, 3200, 2) * np.exp(-t * 3.0) * 1.3    # 中高频咆哮
    crack = _带通快(x, 2500, 9000, 2) * np.exp(-t * 26) * 1.1   # 起爆撕裂
    tail = _带通快(x, 120, 700, 2) * np.exp(-t * 0.85) * 0.7    # 尾部滚动回声
    y = lo + mid + roar + crack + tail
    y *= np.clip(t * 400, 0, 1)                                  # 2ms 起振，避免爆音
    return _归一(y, 1.0)


def 碎(种子: int = 0) -> np.ndarray:
    """碎石落地 / 石栏碎裂：一串短促的脆响。

    原来重心 13.8 kHz（像玻璃渣撒在铁皮上）。锁到 700~5500 Hz，
    重心目标 ~2.5 kHz —— 石头是钝的，不该这么尖。
    """
    d = 1.4
    n = _n(d)
    rng = np.random.default_rng(7000 + 种子)
    y = np.zeros(n, np.float32)
    for _ in range(int(rng.integers(9, 18))):
        at = rng.uniform(0, d * 0.72)
        i = _n(at)
        L = _n(rng.uniform(0.012, 0.05))
        if i + L >= n:
            continue
        c = rng.uniform(1200, 4200)
        seg = rng.standard_normal(L).astype(np.float32)
        seg = _带通快(seg, max(500, c * 0.35), min(6000, c * 2.0), 2)
        seg *= np.exp(-np.arange(L, dtype=np.float32) / (采样率 * 0.006))
        y[i:i + L] += seg * rng.uniform(0.25, 1.0)
    return _归一(y, 0.7)


def 衣(种子: int = 0) -> np.ndarray:
    """衣袂破空：短促的布料抖动，比「啸」更闷更脆。"""
    d = 0.32
    n = _n(d)
    rng = np.random.default_rng(8000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    x = rng.standard_normal(n).astype(np.float32)
    y = _低通快(x, 2600, 2) * np.exp(-t * 22)
    y += _高通快(x, 5200, 2) * np.exp(-t * 60) * 0.55
    y = _高通快(y, 900, 1)
    return _归一(y, 0.62)


def 蓄(秒: float = 1.6, 种子: int = 0) -> np.ndarray:
    """内力蓄势：一条不断上扬的低频，用于发力前一瞬。"""
    n = _n(秒)
    rng = np.random.default_rng(9000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    # 频率从 60Hz 扫到 300Hz
    f = 60 + 240 * (t / max(t[-1], 1e-6)) ** 1.7
    ph = np.cumsum(2 * np.pi * f / 采样率)
    y = np.sin(ph) * 0.7
    y += _低通快(rng.standard_normal(n).astype(np.float32), 800, 2) * (t / t[-1]) * 0.9
    y *= np.linspace(0.05, 1.0, n, dtype=np.float32) ** 1.3
    y[-_n(0.05):] *= np.linspace(1, 0, _n(0.05), dtype=np.float32)
    return _归一(y, 0.8)


def 踏(种子: int = 0) -> np.ndarray:
    """脚步踏在石板上的闷响。"""
    d = 0.25
    n = _n(d)
    rng = np.random.default_rng(11000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    f0 = rng.uniform(70, 105)
    y = np.sin(2 * np.pi * f0 * t) * np.exp(-t * 38)
    y += _低通快(rng.standard_normal(n).astype(np.float32), 1400, 2) * np.exp(-t * 70) * 0.7
    y += _高通快(rng.standard_normal(n).astype(np.float32), 3000, 2) * np.exp(-t * 90) * 0.35
    return _归一(y, 0.7)


def 钟(秒: float = 3.5, 种子: int = 0) -> np.ndarray:
    """远景钟声 / 铜火盆共鸣。用于开场与收尾。"""
    n = _n(秒)
    t = np.arange(n, dtype=np.float32) / 采样率
    y = np.zeros(n, np.float32)
    for f, a in ((118, 1.0), (176, 0.55), (263, 0.35), (349, 0.22), (521, 0.14), (702, 0.09)):
        y += (np.sin(2 * np.pi * f * (1 + 0.0015 * np.sin(2 * np.pi * 2.2 * t)) * t)
              * np.exp(-t * 0.9) * a).astype(np.float32)
    return _归一(y, 0.7)


# ─────────────────── 《龙族·雨夜》专用（2026-10-13 新增） ───────────────────
#
# 这批全部是「环境与机械」音，和上面那批「武打」音互不重叠。
# 设计原则：每一条都要能直接铺满整镜（雨、引擎）或精确打点（雷、金属、气爆）。

def 雨(秒: float = 6.0, 种子: int = 0, 强度: float = 1.0) -> np.ndarray:
    """台风暴雨：铺满全片的雨声底。

    三层三明治 —— 120~900 Hz 的「雨幕轰鸣」、900~3500 Hz 的「打在车顶路面」、
    3500~9000 Hz 的「密雨沙沙」。只做高频会变成白噪声，只做低频会变成风声。
    强度 0.4~1.6：车内 0.5，车外 1.0，撞进白光那一下 1.5。
    """
    n = _n(秒)
    rng = np.random.default_rng(4000 + 种子)
    x = rng.standard_normal(n).astype(np.float32)
    y = _层(_带通快(x, 120, 900, 2), 0.30 * 强度)
    y += _层(_带通快(x, 900, 3500, 2), 0.42 * 强度)
    y += _层(_带通快(x, 3500, 9000, 2), 0.30 * 强度)
    # 豪雨不是恒定的，加 5 条 1.8~5 秒周期的强弱起伏
    t = np.arange(n, dtype=np.float32) / 采样率
    for _ in range(5):
        p = rng.uniform(1.8, 5.0)
        y *= (1.0 + 0.28 * np.sin(2 * np.pi * t / p + rng.uniform(0, 6.28))).astype(np.float32)
    # 偶发的大雨点「啪」——打在车顶或水洼上
    for _ in range(int(秒 * 2.2)):
        i = int(rng.uniform(0, max(1, n - 1)))
        L = _n(0.035)
        m = min(L, n - i)
        if m <= 0:
            continue
        y[i:i + m] += (_带通快(rng.standard_normal(m).astype(np.float32), 1800, 6000, 1)
                       * np.linspace(1, 0, m, dtype=np.float32) ** 2.0 * 0.55 * 强度)
    f = _n(0.5)
    y[:f] *= np.linspace(0, 1, f, dtype=np.float32)
    y[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    return _归一(y, 0.62)


def 雷(秒: float = 4.5, 种子: int = 0, 近: bool = False) -> np.ndarray:
    """雷。近雷 4ms 裂响 + 滚雷；远雷 250ms 才慢慢滚过来。"""
    n = _n(秒)
    rng = np.random.default_rng(5000 + 种子)
    x = rng.standard_normal(n).astype(np.float32)
    y = _层(_带通快(x, 18, 120, 2), 0.72)          # 滚动的低频轰鸣：主体
    y += _层(_带通快(x, 120, 600, 2), 0.30)
    if 近:
        y += _层(_带通快(x, 800, 7000, 2), 0.34) * _包络(n, 0.004, 秒, 3.4)
    else:
        y += _层(_带通快(x, 700, 3000, 2), 0.10) * _包络(n, 0.10, 秒, 3.0)
    y = y * _包络(n, 0.006 if 近 else 0.25, 秒, 1.7)
    # ★ 手机喇叭救命层：滚雷的能量几乎全在 150 Hz 以下，小喇叭会把它整个吃掉。
    #   补一层 180~1400 Hz 的「撕裂/轰鸣」质感，让雷在小喇叭上也有存在感。
    y += _层(_带通快(x, 180, 1400, 2), 0.34) * _包络(n, 0.02 if 近 else 0.30, 秒, 1.9)
    t = np.arange(n, dtype=np.float32) / 采样率
    for _ in range(3):                              # 尾音里再滚几下
        y *= (1.0 + 0.35 * np.sin(2 * np.pi * t / rng.uniform(0.5, 1.6)
                                  + rng.uniform(0, 6.28))).astype(np.float32)
    return _归一(y, 0.92 if 近 else 0.70)


def 引擎(秒: float = 4.0, 种子: int = 0, 转速: float = 0.45) -> np.ndarray:
    """V12 发动机。转速 0~1 映射 700~6000 rpm。

    ★ 基频 = rpm/60*6 —— 12 缸每转做功 6 次，所以 700 rpm 怠速就是 70 Hz。
    写成 rpm/60 会得到一把「摩托」而不是「十二缸」。
    """
    n = _n(秒)
    rng = np.random.default_rng(6000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    f0 = (700 + 转速 * 5300) / 60.0 * 6.0
    y = np.zeros(n, np.float32)
    for k, a in enumerate([1.0, 0.55, 0.34, 0.22, 0.14, 0.09, 0.06]):
        y += (a * np.sin(2 * np.pi * f0 * (k + 1) * t
                         + rng.uniform(0, 6.28))).astype(np.float32)
    y += _层(_带通快(rng.standard_normal(n).astype(np.float32), 180, 1600, 2), 0.20)
    y *= (1.0 + 0.05 * np.sin(2 * np.pi * 3.2 * t)).astype(np.float32)   # 怠速抖动
    return _归一(y, 0.80)


def 金属(种子: int = 0) -> np.ndarray:
    """闷重的金属撞击：车身撞护栏、铁器相击。不是清脆的「叮」，是「咣哐」。"""
    n = _n(0.9)
    rng = np.random.default_rng(7000 + 种子)
    y = _层(_低通快(rng.standard_normal(n).astype(np.float32), 220, 2), 0.55)
    y += _层(_带通快(rng.standard_normal(n).astype(np.float32), 300, 1800, 2), 0.40)
    t = np.arange(n, dtype=np.float32) / 采样率
    for _ in range(7):                              # 非谐分音 = 金属板在振
        f = rng.uniform(420, 3600)
        y += (0.12 * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
              * np.exp(-t * rng.uniform(6, 22))).astype(np.float32)
    y *= _包络(n, 0.002, 0.9, 2.2)
    return _归一(y, 0.95)


def 气爆(种子: int = 0) -> np.ndarray:
    """安全气囊炸开：1.5ms 的爆响 + 之后气囊放气的嘶声。"""
    n = _n(1.3)
    rng = np.random.default_rng(8000 + 种子)
    x = rng.standard_normal(n).astype(np.float32)
    y = _层(_带通快(x, 60, 500, 2), 0.50) * _包络(n, 0.0015, 1.3, 4.0)
    y += _层(_带通快(x, 700, 6000, 2), 0.42) * _包络(n, 0.0010, 1.3, 2.6)
    i0 = _n(0.06)                                   # 放气：从 60ms 开始，5/s 衰减
    env = np.zeros(n, np.float32)
    env[i0:] = np.exp(-np.arange(n - i0, dtype=np.float32) / 采样率 * 5.0)
    y += _带通快(x, 4500, 9000, 1) * env * 0.30
    return _归一(y, 1.0)


def 马啸(秒: float = 1.5, 种子: int = 0) -> np.ndarray:
    """八足神马的嘶鸣。比真马更低更粗，尾音带金属共鸣。

    基频轮廓：从 210 Hz 先拱到 ~400 Hz 再跌到 ~90 Hz —— 嘶鸣的典型形状。
    纯正弦听不出马，必须叠一层 400~3000 Hz 的嘶哑噪声。
    """
    n = _n(秒)
    rng = np.random.default_rng(9000 + 种子)
    u = np.linspace(0, 1, n, dtype=np.float32)
    f0 = 210 + 190 * np.sin(np.pi * u ** 0.65) - 120 * u ** 2
    ph = np.cumsum(2 * np.pi * f0 / 采样率, dtype=np.float32)
    y = np.zeros(n, np.float32)
    for k, a in enumerate([1.0, 0.62, 0.40, 0.26, 0.17, 0.11, 0.07, 0.05]):
        y += (a * np.sin(ph * (k + 1))).astype(np.float32)
    y += _层(_带通快(rng.standard_normal(n).astype(np.float32), 400, 3000, 2), 0.34)
    y *= _包络(n, 0.09, 秒, 1.9)
    return _归一(y, 0.88)


def 神之声(秒: float = 3.0, 种子: int = 0) -> np.ndarray:
    """奥丁的声音：极低、极慢、带大空间混响的轰鸣。

    41.2 Hz 是低音竖琴/管风琴的常见基频，比人声最低音还低一个八度，
    听感上「不像人」正是要的效果。
    """
    n = _n(秒)
    rng = np.random.default_rng(10000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    y = np.zeros(n, np.float32)
    for f, a in [(41.2, 1.0), (61.7, 0.62), (82.4, 0.40), (123.5, 0.24), (164.8, 0.13)]:
        y += (a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
              * (1 + 0.18 * np.sin(2 * np.pi * 0.7 * t)).astype(np.float32)).astype(np.float32)
    y += _层(_带通快(rng.standard_normal(n).astype(np.float32), 120, 900, 2), 0.10)
    y *= _包络(n, 0.35, 秒, 1.3)
    # ★ 手机喇叭救命层：41~165 Hz 在手机扬声器（500 Hz 以下基本没有）上会整个消失。
    #   补一层 200~900 Hz 的「铜管/人声」质感，专为小喇叭能听见而加。
    #
    #   ⚠ 2026-10-13 修正：《龙族》实测发现 0.42 远远不够。把五个低频泛音的 RMS
    #   加起来是 sqrt(.707²+.44²+.28²+.17²+.09²) ≈ 0.90，而救命层只有 0.42，
    #   低频因此占总能量 90%，手机上一刀切掉之后整条「神之声」就没了
    #   （镜 06 只剩 70%、镜 09 只剩 68%）。提到 0.85 / 0.30 之后低频降到约 53%，
    #   影院里那口 41 Hz 的轰鸣照样在（峰值归一化保护它），手机上也能听见了。
    y += _层(_带通快(rng.standard_normal(n).astype(np.float32), 200, 900, 2), 0.85) \
        * _包络(n, 0.30, 秒, 1.5)
    y += _层(_带通快(rng.standard_normal(n).astype(np.float32), 900, 2600, 2), 0.30) \
        * _包络(n, 0.40, 秒, 1.6)
    for d, g in [(0.09, 0.36), (0.17, 0.24), (0.28, 0.15), (0.41, 0.09)]:   # 简易大空间
        i = _n(d)
        if i < n:
            y[i:] += y[:n - i] * g
    return _归一(y, 0.80)


def 刀锋(种子: int = 0) -> np.ndarray:
    """御神刀·村雨出鞘与挥斩：锐利的金属长鸣 + 破空。"""
    n = _n(0.75)
    rng = np.random.default_rng(11000 + 种子)
    t = np.arange(n, dtype=np.float32) / 采样率
    y = np.zeros(n, np.float32)
    for _ in range(5):
        f = rng.uniform(2400, 6800)
        y += (0.22 * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
              * np.exp(-t * rng.uniform(5, 14))).astype(np.float32)
    y += _层(_高通快(rng.standard_normal(n).astype(np.float32), 2600, 1), 0.30) \
        * _包络(n, 0.02, 0.75, 2.8)
    return _归一(y, 0.90)


def 星光突刺(数: int = 9, 种子: int = 0) -> np.ndarray:
    """冈格尼尔的星雨：密集的高频短促锐响串。官方的「一瞬无数次刺击」。"""
    n = _n(1.6)
    rng = np.random.default_rng(12000 + 种子)
    y = np.zeros(n, np.float32)
    for _ in range(数):
        i = int(rng.uniform(0, max(1, n - _n(0.09) - 1)))
        m = min(_n(0.09), n - i)
        if m <= 0:
            continue
        tt = np.arange(m, dtype=np.float32) / 采样率
        f = rng.uniform(2800, 9000)
        y[i:i + m] += (0.30 * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 38)).astype(np.float32)
        y[i:i + m] += (_带通快(rng.standard_normal(m).astype(np.float32), 3500, 12000, 1)
                       * np.exp(-tt * 55) * 0.22)
    return _归一(y, 0.92)


def 心跳(种子: int = 0) -> np.ndarray:
    """心跳：两下一组，第二下轻一点。用在车内的紧张段落。

    ★ 62 Hz 的「咚」在手机喇叭上等于没有。真实心音的听感其实来自**瓣膜关闭的
    那个瞬态**（宽带短促的「嗒」），所以这里给每一下都配一个 1.5 ms 的宽带起振。
    没有这一层，整条音轨在小喇叭上会静音。
    """
    n = _n(1.1)
    rng = np.random.default_rng(13000 + 种子)
    y = np.zeros(n, np.float32)
    for 起, 力 in [(0.0, 1.0), (0.30, 0.68)]:
        i = _n(起)
        m = min(_n(0.28), n - i)
        if m <= 0:
            continue
        tt = np.arange(m, dtype=np.float32) / 采样率
        # 62 Hz 只给 0.75：它是「体感」不是「听感」，给满会把中频整个盖掉
        y[i:i + m] += (力 * 0.75 * np.sin(2 * np.pi * 62.0 * tt) * np.exp(-tt * 16)).astype(np.float32)
        # 胸腔共鸣 190 Hz：这才是「咚」在小喇叭上剩下的东西，给到 0.75
        y[i:i + m] += (力 * 0.75 * np.sin(2 * np.pi * 190.0 * tt) * np.exp(-tt * 22)).astype(np.float32)
        y[i:i + m] += (力 * 0.32 * np.sin(2 * np.pi * 320.0 * tt) * np.exp(-tt * 26)).astype(np.float32)
        # ★ 瓣膜瞬态：宽带、衰减放到 90/s（原 190/s 太短，能量只有低频层的 1/150）
        m2 = min(_n(0.035), n - i)
        t2 = np.arange(m2, dtype=np.float32) / 采样率
        y[i:i + m2] += (_带通快(rng.standard_normal(m2).astype(np.float32), 400, 4000, 1)
                        * np.exp(-t2 * 90) * 1.20 * 力)
    return _归一(y, 0.85)


库 = {
    "风": 风, "啸": 啸, "掌": 掌, "兵器": 兵器, "鸣": 鸣, "炸": 炸,
    "碎": 碎, "衣": 衣, "蓄": 蓄, "踏": 踏, "钟": 钟,
    # 《龙族》新增
    "雨": 雨, "雷": 雷, "引擎": 引擎, "金属": 金属, "气爆": 气爆,
    "马啸": 马啸, "神之声": 神之声, "刀锋": 刀锋, "星光突刺": 星光突刺, "心跳": 心跳,
}


if __name__ == "__main__":
    import wave

    # ★ 频段检查用「带通后取 RMS」而不是 FFT 平方和。
    #   FFT 平方和会把衰减型音效的能量算歪：能量全挤在开头，而汉宁窗在
    #   开头趋近 0，低频因此被系统性低估（「掌」曾被误判 97% 低频，
    #   实际是 58/32/10）。带通 RMS 才是该频段的真实功率。
    #
    #   期望值是**按每个音效的物理性质**定的，不是凭感觉：
    #   低频带 1-150 Hz、中频带 150-2000 Hz、高频带 2000-23000 Hz。
    期望: dict[str, tuple[float, float]] = {   # 名 -> (中频占比下限, 上限)
        "风":   (0.55, 0.95),   # 山风：宽带低中频，重心就在中低频
        "啸":   (0.00, 0.40),   # 破空：高频为主
        "掌":   (0.20, 0.55),   # 拳击：必须有中频「拍」，也不能盖过低频「砰」
        "兵器": (0.00, 0.25),   # 金属：高频非谐分音
        "鸣":   (0.00, 0.25),   # 剑鸣：纯高频
        "炸":   (0.40, 0.85),   # 爆炸：中频咆哮是主体
        "碎":   (0.10, 0.45),   # 碎石：中高频
        "衣":   (0.05, 0.45),   # 衣袂：中高频布料声
        "蓄":   (0.50, 0.95),   # 蓄势：60→300 Hz 上扫，本就落在中频带
        "踏":   (0.00, 0.35),   # 脚步：低频闷响
        "钟":   (0.15, 0.60),   # 钟声：低频基音 + 少量中频泛音
        # 《龙族》新增 —— 期望值同样按物理性质定
        #
        # ★ 第一轮我把这 4 条的区间定错了，改的是**规格**不是音效：
        #   我以为「雷/引擎/马啸/神之声」的中频该占大头，但它们的能量本来就在
        #   低频段（见下面逐条注释）。真正的音效问题只有一个 —— 手机喇叭，
        #   已通过给雷/心跳/神之声各加一层中频「救命层」解决。
        "雨":     (0.20, 0.60),   # 暴雨：低频雨幕 + 中频打在车顶 + 高频沙沙，三层要均衡
        "雷":     (0.20, 0.70),   # 滚雷：18~600 Hz 是主体，另加 180~1400 救命层
        "引擎":   (0.20, 1.00),   # ★ V12 在 3000 rpm 时点火基频 308 Hz，到 2160 Hz 的
                                  #   各次谐波**全部落在 150~2000 的中频带**，中频必然占满
        "金属":   (0.10, 0.55),   # 闷重金属：低频「咣」+ 中频「哐」
        "气爆":   (0.30, 0.80),   # 气囊：爆响（中频）+ 放气嘶声（高频）
        "马啸":   (0.30, 1.00),   # ★ 马嘶基频 90~400 Hz，8 次谐波铺到 3.2 kHz，中频占满
        "神之声": (0.15, 0.75),   # 41 Hz 基音 + 救命层（200~900 / 900~2600）
        "刀锋":   (0.00, 0.35),   # 出鞘/挥斩：2.4~6.8 kHz 高频长鸣
        "星光突刺": (0.00, 0.35),  # 星雨：2.8~9 kHz 密集锐响
        "心跳":   (0.10, 0.70),   # 62 Hz「咚」+ 190 Hz 胸腔 + 400~4000 瓣膜瞬态
    }

    def 频段(a: np.ndarray) -> tuple[float, float, float]:
        r = [float(np.sqrt(np.mean(_带通快(a, l, h, 4).astype(np.float64) ** 2)))
             for l, h in ((1, 150), (150, 2000), (2000, 23000))]
        s = sum(v * v for v in r) or 1e-12
        return tuple(v * v / s for v in r)          # type: ignore[return-value]

    print("生成试听包 + 频段自检 …")
    过 = 0
    for 名, f in 库.items():
        a = f(种子=1)
        低, 中, 高 = 频段(a)
        lo, hi = 期望[名]
        合 = lo <= 中 <= hi
        过 += 合
        st = _立体声(a, 0.35, 7)
        p = f"D:\\DSHworkspace\\_音效试听_{名}.wav"
        with wave.open(p, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(采样率)
            w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())
        print(f"  {'✅' if 合 else '⚠️ '} {名:<3} {len(a)/采样率:>5.2f}s  "
              f"RMS {np.sqrt((a**2).mean()):.4f}  低{低:>5.1%} 中{中:>5.1%} 高{高:>5.1%}"
              f"   中频目标 {lo:.0%}~{hi:.0%}")
    print(f"\n频段落位 {过}/{len(库)}")
