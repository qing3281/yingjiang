# -*- coding: utf-8 -*-
"""把 02-九宫格.md 的 34 格收成 8 格。
★ 真实结构（读 剧组.py 命令_出片 得知）：九宫格的「格N」= 锚点N 的**关键帧**，
  而一个锚点 = 5 段视频（格0 关键帧 + 格1..4 四宫格）。
  34 格 × 5 段 = 170 段 ≈ 12.6 分钟，那不是 3 分钟片。
  8 场 → 8 锚点 → 40 段 × 4.4583 秒 ≈ 178 秒。"""
import io, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
根 = r"D:\DSHworkspace\影匠\作品\楚子航"
p = os.path.join(根, "02-九宫格.md")
s = io.open(p, encoding="utf-8").read()

头 = s[:s.index("## 格1 ")]
块s = re.split(r"(?m)^## 格", s)[1:]
格 = {}
for b in 块s:
    号 = int(re.match(r"(\d+)", b).group(1))
    格[号] = "## 格" + b.rstrip() + "\n"

print("  解析到 %d 格" % len(格))
# 每一场的第一格
选 = [1, 4, 8, 14, 17, 23, 27, 31]
for n in 选:
    t = re.search(r"——\s*(.+?)（", 格[n])
    print("    锚点 ← 原格%-2d  %s" % (n, t.group(1) if t else "?"))

新 = 头.rstrip() + "\n\n"
for i, n in enumerate(选, 1):
    新 += re.sub(r"^## 格\d+", "## 格%d" % i, 格[n]) + "\n"
io.open(p, "w", encoding="utf-8", newline="\n").write(新)
print("\n  ✓ 02-九宫格.md 收成 8 格　%d 字节" % os.path.getsize(p))

# 把 34 格的原文留一份给写 03/04 的用（下划线开头，流水线会忽略）
素 = 头.rstrip() + "\n\n" + "".join(格[n] + "\n" for n in sorted(格))
io.open(os.path.join(根, "_34格素材.md"), "w", encoding="utf-8", newline="\n").write(素)
print("  ✓ _34格素材.md 留档　%d 字节" % os.path.getsize(os.path.join(根, "_34格素材.md")))
