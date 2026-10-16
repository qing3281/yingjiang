# -*- coding: utf-8 -*-
"""量一遍 BGM 素材：时长 / 响度 / 峰值 / 动态 / 频段。
选曲看两个数：动态越大越能衬托打点；低中高频分布决定它会不会和人声/音效打架。
"""
import os
import av
import numpy as np

基 = r"D:\DSHworkspace\B站\素材\BGM"
头 = "%-46s %7s %8s %7s %9s   %s" % ("曲目", "秒", "RMS", "峰", "动态", "低 / 中 / 高")
print(头)
print("-" * len(头.encode("gbk", "ignore")))

for f in sorted(os.listdir(基)):
    if not f.endswith(".mp3"):
        continue
    c = av.open(os.path.join(基, f))
    a = c.streams.audio[0]
    sr = a.rate
    xs = [fr.to_ndarray().reshape(-1) for fr in c.decode(a)]
    c.close()
    x = np.concatenate(xs).astype(np.float32)
    if x.max() > 2:
        x = x / 32768.0

    秒 = len(x) / sr
    rms = float(np.sqrt((x ** 2).mean()))
    峰 = float(np.abs(x).max())

    块 = len(x) // int(sr * 0.5)
    动 = 0.0
    if 块 > 4:
        bl = x[: 块 * int(sr * 0.5)].reshape(块, -1)
        r = np.sqrt((bl ** 2).mean(axis=1)) + 1e-9
        动 = float(20 * np.log10(np.percentile(r, 95) / np.percentile(r, 10)))

    n = min(len(x), sr * 60)
    X = np.abs(np.fft.rfft(x[:n] * np.hanning(n))) ** 2
    fr = np.fft.rfftfreq(n, 1 / sr)
    T = X.sum() + 1e-12
    lo = X[(fr >= 20) & (fr < 150)].sum() / T * 100
    mi = X[(fr >= 150) & (fr < 2000)].sum() / T * 100
    hi = X[fr >= 2000].sum() / T * 100

    print("%-46s %7.1f %8.4f %7.3f %7.1fdB   %4.0f/%4.0f/%4.0f"
          % (f[:44], 秒, rms, 峰, 动, lo, mi, hi))
