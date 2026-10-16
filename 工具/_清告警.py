# -*- coding: utf-8 -*-
"""最后一遍清告警。

剩下的告警只有两类，都好办：
  ① `---` 分隔线 —— 解析器认不出（不是标题/字段/续写）。删掉即可，它本来就是排版用的。
  ② `03-四宫格.md` 里我抄了一份 `## 人物卡` / `## 视觉规范` ——
     **这个文件的解析器只认「## 锚点N —— 标题」**，它会把这两节报成「不认识的段落标题」。
     人物卡与视觉规范本来就该住在 `02-九宫格.md`（那边认这两节），
     所以从 03 里删掉，改在 04 的说明里留一句指向。

判据：三份文件解析 **告警 0 条**，格/锚点/条目数量一个不少（32 / 8+32 / 8+40）。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
落 = r"D:\DSHworkspace\影匠\作品\楚子航"

# ① 删掉所有 `---` 分隔线
for f in ("02-九宫格.md", "03-四宫格.md", "04-动态提示词.md"):
    p = os.path.join(落, f)
    行 = open(p, encoding="utf-8").read().splitlines()
    留 = [s for s in 行 if s.strip() != "---"]
    干 = []
    for s in 留:
        if not s.strip() and (not 干 or not 干[-1].strip()):
            continue
        干.append(s)
    open(p, "w", encoding="utf-8").write("\n".join(干).rstrip() + "\n")
    print("  %-18s 删掉 --- %d 行，剩 %d 行" % (f, len(行) - len(留), len(干)))

# ② 03 里的「## 人物卡」「## 视觉规范」两节整段搬走
p = os.path.join(落, "03-四宫格.md")
行 = open(p, encoding="utf-8").read().splitlines()
留, 搬 = [], []
在搬 = False
for s in 行:
    if re.match(r"^##\s*(人物卡|视觉规范)", s):
        在搬 = True
    elif re.match(r"^##\s*锚点", s):
        在搬 = False
    (搬 if 在搬 else 留).append(s)
干 = []
for s in 留:
    if not s.strip() and (not 干 or not 干[-1].strip()):
        continue
    干.append(s)
open(p, "w", encoding="utf-8").write("\n".join(干).rstrip() + "\n")
open(os.path.join(落, "_提示词说明.md"), "a", encoding="utf-8").write(
    "\n## 从 03-四宫格.md 搬出来的（那边的解析器不认这两节，只认「## 锚点N —— 标题」）\n"
    + "\n".join(搬) + "\n")
print("  03-四宫格.md       搬走人物卡/视觉规范 %d 行，剩 %d 行" % (len(搬), len(干)))
