# -*- coding: utf-8 -*-
"""_连片进度3.py —— 量出「一个渲染窗的真实总时长」（采样 + 模型重载 + 解码 + 合并）。

上一版（`_连片进度2.py`）只拿日志里的 `s/it` × 8 步当窗时长 → 推出 14:08 落地，
结果 14:08 还没落地。差别就在**每个窗还有一段采样之外的开销**：
日志里能看到每个窗都重来一次 `Requested to load MiniMaxH3` / `prepared for dynamic VRAM loading`，
那是模型重载，采样时间之外还要算进去。

这个脚本只干一件事：把日志里那几类里程碑的时间戳打出来，让我们看清一个窗的完整周期。

用法：python _连片进度3.py
"""
import re
import sys
import json
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
远端 = "http://100.127.224.106:8188"

里程碑 = [
    ("★ 模型重载开始", r"Requested to load MiniMaxH3"),
    ("  模型装好", r"prepared for dynamic VRAM loading"),
    ("  采样中", r"(\d+)/8 \["),
    ("  解码/VAE", r"VAEDecode|VAE decode|Decoding"),
    ("  落盘", r"SaveVideo|Saving|saved|\.mp4"),
]

with urllib.request.urlopen(远端 + "/internal/logs/raw", timeout=20) as r:
    条 = json.loads(r.read().decode("utf-8", "replace"))["entries"]

行 = [(e["t"][11:19], re.sub(r"\x1b\[[0-9;]*m", "", e.get("m", ""))) for e in 条]
print("日志 %d 条，覆盖 %s → %s" % (len(行), 行[0][0], 行[-1][0]))
print("（★ 远端只留最近 300 条 —— 只够看 ~1.5 个窗，所以数不出总进度）\n")

for 名, 式 in 里程碑:
    命中 = [t for t, m in 行 if re.search(式, m)]
    print("%-14s %2d 次　%s" % (名, len(命中), "　".join(命中[-6:])))

# 用「模型重载开始 → 最后一次进度」估一个窗里采样占多少
载 = [t for t, m in 行 if re.search(里程碑[0][1], m)]
进 = [(t, m) for t, m in 行 if re.search(r"(\d+)/8 \[", m)]
if 载 and 进:
    def 秒(s):
        h, mi, se = (int(x) for x in s.split(":"))
        return h * 3600 + mi * 60 + se
    a = 秒(载[-1])
    b = 秒(进[-1][0])
    print("\n最后一次重载 %s → 最后一条进度 %s　= 这个窗已经过了 %d 秒" % (载[-1], 进[-1][0], b - a))
    m = re.search(r"(\d+)/8 \[(\d+):(\d+)<(\d+):(\d+),\s*([\d.]+)s/it\]", 进[-1][1])
    if m:
        步, 已 = int(m.group(1)), int(m.group(2)) * 60 + int(m.group(3))
        print("  其中采样已用 %d 秒（%d/8 步，%.2f 秒/步）" % (已, 步, float(m.group(6))))
        print("  → 非采样的固定开销 ≈ %d 秒/窗（装模型 + 解码 + 合并落盘）" % max(0, (b - a) - 已))
        print("  ★ 所以一个窗的真实周期 ≈ %.0f 秒（拿 s/it×8 估会偏小）" % (max(0, (b - a) - 已) + 8 * float(m.group(6))))
