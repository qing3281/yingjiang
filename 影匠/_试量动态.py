# -*- coding: utf-8 -*-
"""单格试：真读一个 H3 段，量邻帧差和头尾差。"""
import importlib.util
import os
import sys

根 = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("量", os.path.join(根, "_量动态_觉醒.py"))
量 = importlib.util.module_from_spec(spec)
sys.modules["量"] = 量
spec.loader.exec_module(量)

for 名 in ("格1_本机", "格2_本机", "格41_远端", "格42_远端"):
    p = os.path.join(根, "作品", "觉醒", "段", 名 + ".mp4")
    if not os.path.exists(p):
        print("  %-14s （还没出）" % 名)
        continue
    a = 量.帧差(p, "邻帧")
    b = 量.帧差(p, "头尾")
    print("  %-14s 邻帧差 %s　头尾差 %s" % (
        名,
        ("%.3f" % a) if a is not None else "读不出",
        ("%.3f" % b) if b is not None else "读不出"))
