# -*- coding: utf-8 -*-
"""列出《磨刀》分镜里被改过词的那些格，供重出首帧/重出段用。

三处改动（都写进了 `_修服词_磨刀.py`）：
  深靛蓝军服          → 古代武官袍（模型会画成民国军官制服）
  银补子              → 银线绣补子（模型会画成发亮的金属牌）
  洗得发白的旧牛皮围裙 → 深褐色的旧牛皮围裙（模型把「发白」当成了颜色，画出白围裙）
"""
import io
import os
import re
import sys

分镜 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "作品", "磨刀", "02-九宫格.md")

新词 = ["古代武官袍", "银线绣补子", "深褐色的旧牛皮围裙"]

s = io.open(分镜, encoding="utf-8").read()
块 = re.split(r"^##\s*格\s*(\d+)", s, flags=re.M)

受 = []
for i in range(1, len(块), 2):
    号 = int(块[i])
    文 = 块[i + 1]
    if any(w in 文 for w in 新词):
        受.append(号)

print(f"分镜：{分镜}")
print(f"共 {len(块)//2} 格，受影响的 {len(受)} 格：")
print("  " + ",".join(str(n) for n in 受))

段目录 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "作品", "磨刀", "段")
已有 = set()
if os.path.isdir(段目录):
    for f in os.listdir(段目录):
        if f.endswith(".mp4"):
            try:
                已有.add(int(f.split("_")[0].replace("格", "")))
            except ValueError:
                pass
要重跑 = sorted(受)
print(f"\n已出段的 {len(已有)} 格；要重跑的 {len(要重跑)} 格，其中已经有段的：")
print("  " + ",".join(str(n) for n in 要重跑 if n in 已有))
print(f"\n一行命令（重出首帧）：")
print("  python _出片.py 磨刀 --图 --只格 " + ",".join(str(n) for n in 要重跑))
本 = [n for n in 要重跑 if n <= 25]
远 = [n for n in 要重跑 if n > 25]
if 本:
    print(f"  python _出片.py 磨刀 --段 --端点 本机 --只格 " + ",".join(str(n) for n in 本))
if 远:
    print(f"  python _出片.py 磨刀 --段 --端点 远端 --只格 " + ",".join(str(n) for n in 远))
sys.exit(0)
