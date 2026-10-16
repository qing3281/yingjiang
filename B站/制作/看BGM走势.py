# -*- coding: utf-8 -*-
"""看 BGM 的强弱走势：每 2 秒一块的 RMS 画成简易柱状图。
挑曲不只看平均响度 —— 要看它**会不会在需要安静的地方真的静下来**。
"""
import os
import av
import numpy as np

基 = r"D:\DSHworkspace\B站\素材\BGM"
候选 = [
    "admiralbob77_-_The_Broken.mp3",
    "imperial-china-cinematic.mp3",
    "光明顶_Year_Of_The_Dragon.mp3",
]

for f in 候选:
    c = av.open(os.path.join(基, f))
    a = c.streams.audio[0]
    sr = a.rate
    xs = [fr.to_ndarray().reshape(-1) for fr in c.decode(a)]
    c.close()
    x = np.concatenate(xs).astype(np.float32)
    if x.max() > 2:
        x = x / 32768.0

    W = int(sr * 2.0)
    n = len(x) // W
    r = np.sqrt((x[: n * W].reshape(n, W) ** 2).mean(axis=1))
    db = 20 * np.log10(r + 1e-9)
    lo, hi = float(db.min()), float(db.max())
    # 只看前 60 块（=120 秒），够覆盖 72 秒正片 + 淡出
    头 = db[:60]
    柱 = "▁▂▃▄▅▆▇█"
    s = "".join(柱[min(7, max(0, int((v - lo) / (hi - lo + 1e-9) * 7.99)))] for v in 头)
    print(f"\n{f}")
    print(f"  范围 {lo:6.1f} ~ {hi:6.1f} dB   动态 {hi-lo:5.1f} dB   共 {len(x)/sr:.0f} 秒")
    print(f"  前 120 秒走势（每格 2 秒）：")
    for i in range(0, len(s), 60):
        print(f"    {i*2:>4}s │{s[i:i+60]}")
