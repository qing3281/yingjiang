# -*- coding: utf-8 -*-
"""把「楚子航_爆血」的黄金瞳从「熔金色」改成「浅琥珀金」。
为什么改：用户 2026-10-16 看着定妆照说「你这眼睛的黄色怎么这么怪呢？能不能颜色稍微淡一点？」

病根：旧提示词写的是「熔金一样的金黄色」——「熔金」这个词给的是纯饱和黄，
模型就画成一块贴上去的色块。**要给虹膜结构 + 给一个"稀释过"的比方**，黄才不会糊成一片。
"""
import json, os, re, sys, shutil

sys.stdout.reconfigure(encoding="utf-8")

卡目录 = r"D:\DSHworkspace\影匠\角色卡"
j = os.path.join(卡目录, "楚子航_爆血.json")
m = os.path.join(卡目录, "楚子航_爆血.md")

for p in (j, m):
    shutil.copy2(p, p + ".bak-改眼睛前")

d = json.load(open(j, encoding="utf-8"))
旧 = d["提示词"]

# 旧句 → 新句。旧句在 JSON 里前面带 **
旧句 = "**两只眼睛都是熔金一样的金黄色**，瞳孔收成竖线，眼神是狠的、冷的。"
新句 = ("**两只眼睛是浅琥珀金色、比熔金淡得多** —— **金色只在瞳孔周围那一圈最明显，"
        "往外一圈一圈淡下去、虹膜最外圈几乎接近浅灰褐色**；**虹膜里是一圈一圈细密的放射状纹理**；"
        "**瞳孔收成一条很细的竖直黑缝**；眼神是狠的、冷的。")

if 旧句 not in 旧:
    print("★ 没找到旧句，实际文本是：")
    i = 旧.find("熔金")
    print("  ...%s..." % 旧[max(0, i - 120):i + 120] if i >= 0 else "  （连「熔金」都没有）")
    sys.exit(1)

新 = 旧.replace(旧句, 新句)
d["提示词"] = 新
d["版本"] = d.get("版本", 0) + 1
d["眼睛改动"] = "2026-10-16 用户要求淡一点：熔金色 → 浅琥珀金，加虹膜放射纹理 + 细竖缝瞳"
json.dump(d, open(j, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  ✓ .json 改好，版本 → %d" % d["版本"])

# .md 同步改（人看的那份）
t = open(m, encoding="utf-8").read()
if 旧句 in t:
    t = t.replace(旧句, 新句)
    t = t.replace("| 种子 | `808` |", "| 种子 | `808` |\n| 版本 | `%d` |" % d["版本"])
    open(m, "w", encoding="utf-8").write(t)
    print("  ✓ .md 同步改好")
else:
    print("  ★ .md 里没这句，跳过（.json 已改）")

print()
print("  新旧对照：")
print("    旧：两只眼睛都是熔金一样的金黄色，瞳孔收成竖线")
print("    新：浅琥珀金色、金色只在瞳孔周围一圈最明显、往外淡到浅灰褐、虹膜有放射纹理、瞳孔是很细的竖直黑缝")
