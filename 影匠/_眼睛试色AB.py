# -*- coding: utf-8 -*-
"""眼睛到底该怎么说才画得淡 —— 4 种说法 A/B，同一个种子 808，只换那一句。

为什么：改成「浅琥珀金色」之后出来还是亮黄。病根是那句话里「金」字出现 3 次，
模型按词频加权，把「淡得多」「最外圈接近浅灰褐」这种程度词忽略掉了。
按 AGENTS.md 第 0.05 条那条老病 —— **只描述它是什么，不描述它不是什么**。
所以四种说法里，越往后「金」字越少、颜色名词越具体。
"""
import importlib.util, json, os, shutil, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")

卡目录 = r"D:\DSHworkspace\影匠\角色卡"
j = os.path.join(卡目录, "楚子航_爆血.json")
出目录 = r"D:\DSHworkspace\影匠\作品\楚子航\_定妆卡_楚子航_爆血\_眼睛试色"
os.makedirs(出目录, exist_ok=True)

当前句 = ("**两只眼睛是浅琥珀金色、比熔金淡得多** —— **金色只在瞳孔周围那一圈最明显，"
           "往外一圈一圈淡下去、虹膜最外圈几乎接近浅灰褐色**；**虹膜里是一圈一圈细密的放射状纹理**；"
           "**瞳孔收成一条很细的竖直黑缝**；眼神是狠的、冷的。")

候选 = [
    ("A_旧熔金", "**两只眼睛都是熔金一样的金黄色**，瞳孔收成竖线，眼神是狠的、冷的。"),
    ("B_浅茶褐", "**两只眼睛是浅茶褐色的**；**只有瞳孔外面一圈是很淡的琥珀色**，"
                 "**像兑了很多水的蜂蜜那样淡**；**瞳孔收成一条很细的竖直黑缝**；眼神是狠的、冷的。"),
    ("C_极淡金", "**两只眼睛是浅褐色的**，**虹膜里只有极淡的一层金黄色、淡到几乎看不出是黄的**；"
                 "**瞳孔收成一条很细的竖直黑缝**；眼神是狠的、冷的。"),
    ("D_灰蓝琥珀", "**两只眼睛的虹膜是浅灰蓝的底色**，**瞳孔外那一圈是很薄的琥珀色**；"
                   "**瞳孔收成一条很细的竖直黑缝**；眼神是狠的、冷的。"),
]

原文本 = open(j, encoding="utf-8").read()
原卡 = json.loads(原文本)
种子 = 原卡["种子"]

print("  种子 %d　%d×%d　%s" % (种子, 原卡["宽"], 原卡["高"], 原卡["模板"]))
print()

跑 = []
for 代号, 句 in 候选:
    卡 = json.loads(原文本)
    if 代号 == "A_旧熔金":
        卡["提示词"] = 卡["提示词"].replace(当前句, 句)
    else:
        卡["提示词"] = 卡["提示词"].replace(当前句, 句)
    assert 句 in 卡["提示词"], "★ 换句失败：" + 代号
    json.dump(卡, open(j, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sp = importlib.util.spec_from_file_location("定妆", r"D:\DSHworkspace\影匠\定妆.py")
    定妆 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(定妆)
    存 = os.path.join(出目录, "%s.png" % 代号)
    print("  [%s] 出图中…" % 代号, flush=True)
    try:
        定妆.出图("楚子航_爆血", 存到=存, 种子=种子)
        print("        ✓ %d B" % os.path.getsize(存))
        跑.append((代号, 存))
    except Exception as e:
        print("        ★ 炸了：%s" % e)

open(j, "w", encoding="utf-8").write(原文本)
print()
print("  ✓ 卡已换回改好的那版（浅琥珀）")
print("  出了 %d 张：%s" % (len(跑), "、".join(a for a, _ in 跑)))
