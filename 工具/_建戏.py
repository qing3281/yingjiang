# -*- coding: utf-8 -*-
import io, os, shutil, sys
sys.stdout.reconfigure(encoding="utf-8")
源 = r"D:\DSHworkspace\影匠\作品\_剧本试验\楚子航_四步.md"
根 = r"D:\DSHworkspace\影匠\作品\楚子航"
os.makedirs(根, exist_ok=True)
本 = io.open(源, encoding="utf-8").read()
# 剧本.md 的抬头改成片名
本 = 本.replace("# 剧本 · 楚子航耶梦加得", "# 剧本 · 楚子航耶梦加得\n\n（3 分钟 · 战斗 · 雨夜跨江大桥 · 楚子航 vs 龙王耶梦加得）", 1)
io.open(os.path.join(根, "剧本.md"), "w", encoding="utf-8", newline="\n").write(本)
print("  ✓ 建戏目录", 根)
print("  ✓ 剧本.md", os.path.getsize(os.path.join(根, "剧本.md")), "字节")
# 把修鞋的四份当格式参照拷过去（只读参照，不改）
参 = r"D:\DSHworkspace\影匠\作品\修鞋"
print("\n  格式参照（修鞋）：")
for f in ("01-节拍拆解.md", "02-九宫格.md", "03-四宫格.md", "04-动态提示词.md"):
    p = os.path.join(参, f)
    if os.path.exists(p):
        print("    %-20s %6d 字节" % (f, os.path.getsize(p)))
