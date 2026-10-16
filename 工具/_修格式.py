# -*- coding: utf-8 -*-
"""把三份提示词文件的标题层级与字段名改成 `剧组.py` 认的那种。

契约（`剧组.py` L224–255）：
    02-九宫格.md     ## 角色卡 / ## 视觉规范 / ## 格N —— 标题
                     字段：目的 景别 机位 提示词 重点（可选 光色 色调 风格 备注 说明）
    03-四宫格.md     ## 锚点N —— 标题（字段：继承自 人物 场景 光色）
                     ### A-B 起手|推进|冲突|落点（字段：提示词 变化说明）
    04-动态提示词.md  ## 锚点N —— 标题
                     ### A-B 关键帧|起手|推进|冲突|落点（字段：动作 强度）
关键两条：
  ① **格头必须是二级** `## 格N —— 标题`；我写成了 `###`，所以 `_格头` 一条都匹配不上 → 格数 0。
  ② **字段名不许带 `**`** —— `_字段行 = ^-\s*([^:：]{1,12}?)\s*[:：]` 会把 `**继承自**` 整串当字段名，
     然后报「锚点里不认识的字段」。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
落 = r"D:\DSHworkspace\影匠\作品\楚子航"

# ── 02-九宫格.md ─────────────────────────────────────────────
p = os.path.join(落, "02-九宫格.md")
行 = open(p, encoding="utf-8").read().splitlines()
出, 改 = [], {"格头": 0, "场头": 0}
for s in 行:
    m = re.match(r"^###\s*(格\s*\d+.*)$", s)
    if m:                                    # ### 格1 —— xxx  →  ## 格1 —— xxx
        出.append("## " + m.group(1).strip()); 改["格头"] += 1; continue
    m = re.match(r"^##\s*(第\s*\d+\s*场.*)$", s)
    if m:                                    # ## 第 1 场 · …   →  > **第 1 场 · …**
        出.append("> **" + m.group(1).strip() + "**"); 改["场头"] += 1; continue
    # 场标题下面的空行 / `---` 留着没关系（解析器会跳过空行，`---` 也会被跳）
    出.append(s)
open(p, "w", encoding="utf-8").write("\n".join(出) + "\n")
print("  02-九宫格.md   格头降级 %d 处 / 场头转引用 %d 处" % (改["格头"], 改["场头"]))

# ── 03-四宫格.md：去掉字段名里的 ** ───────────────────────────
p = os.path.join(落, "03-四宫格.md")
文 = open(p, encoding="utf-8").read()
n = len(re.findall(r"^-\s*\*\*[^*]+\*\*\s*[:：]", 文, re.M))
文 = re.sub(r"^-\s*\*\*([^*]+)\*\*\s*[:：]\s*", r"- \1：", 文, flags=re.M)
open(p, "w", encoding="utf-8").write(文)
print("  03-四宫格.md   去掉加粗字段名 %d 处" % n)

# ── 04-动态提示词.md：同上一并查一遍 ─────────────────────────
p = os.path.join(落, "04-动态提示词.md")
文 = open(p, encoding="utf-8").read()
n = len(re.findall(r"^-\s*\*\*[^*]+\*\*\s*[:：]", 文, re.M))
if n:
    文 = re.sub(r"^-\s*\*\*([^*]+)\*\*\s*[:：]\s*", r"- \1：", 文, flags=re.M)
    open(p, "w", encoding="utf-8").write(文)
print("  04-动态提示词.md 去掉加粗字段名 %d 处" % n)
