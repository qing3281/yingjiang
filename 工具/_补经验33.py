# -*- coding: utf-8 -*-
"""_补经验33.py —— 2× 收尾又逮到两条（只追加）。"""
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\记忆\经验\流程与脚本.md"
条 = [
    ("★ **用 ffmpeg 读「这条片子有没有音轨」不能用 `-v error`** —— 我写的 `_看2x.py` 里是 "
     "`[FF, \"-v\", \"error\", \"-i\", p]` 再 grep `\"Audio:\" in stderr`，结果把**有音轨的 267.9 MB 成片和 45.4 MB 手机版都报成「音轨=无」**。"
     "原因是 `Stream #0:1: Audio:` 这行是 `info` 级别的输出，`-v error` 会把它一起咽掉 —— 于是判据永远返回 False，"
     "而它**不会报错、不会警告**，我差点按「没音轨」去重跑一遍。改用 `-hide_banner`（默认 verbosity）就正常读到 "
     "`aac (LC), 48000 Hz, mono, 186 kb/s`。",
     "判据：**凡是用「日志里有没有某个字符串」当判据的地方，先确认那行日志在当前 verbosity 下真的会打出来** —— "
     "把 verbosity 调低再 grep，等于把判据静默地变成「永远否」。"),

    ("15 段分别超分之后，除了段内那 14 条缝，还要专门量**段与段之间的整幅亮度台阶** —— "
     "段内缝量不出系统性偏色（每段自己内部是平的）。实测：上一段末帧均值 vs 下一段首帧均值，"
     "跳变中位 **2.27**、最大 **3.61**（对照：格32 那次级联崩坏是 0.24 → 73.74）。"
     "段01 首帧 51.41 / 末帧 97.59 是因为那 20 秒里火把点着了，不是台阶。"
     "顺带确认片尾：末帧均值 **8.12**（剧本 8-4 落点要求「画面慢慢变暗」，这一版真黑了）。",
     "判据：**分块处理过的片子要分两层量缝** —— ①块内相邻帧（会不会跳）②块间整幅均值（会不会偏色）。"
     "只量一层就漏另一层。"),
]

备 = 目 + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(目, 备)
原 = os.path.getsize(目)
with open(目, "a", encoding="utf-8") as f:
    f.write("\n" + "\n".join("- 2026-10-16 ★ %s\n  → %s\n" % (a, b) for a, b in 条))
新 = os.path.getsize(目)
print("✓ 追加 %d 条　%d → %d 字节（+%d）　备份 %s" % (len(条), 原, 新, 新 - 原, os.path.basename(备)))
