import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠"); os.chdir(r"D:\DSHworkspace\影匠")
import 剧组
九 = 剧组.解析九宫格(r"D:\DSHworkspace\影匠\作品\楚子航\02-九宫格.md")
卡 = [c["名"] if isinstance(c, dict) else c[0] for c in 九["角色卡"]]
print("  角色卡：", 卡)
print()
双 = 0
for g in 九["格们"]:
    选, 备 = 剧组.挑角色(g["提示词"], 卡)
    出现 = [n for n in 卡 if n in g["提示词"]]
    if len(选) != len(出现):
        print("  ✗ 格%-3d 挑=%-22s 出现=%-22s" % (g["号"], "、".join(选) or "（空）", "、".join(出现) or "（空）"))
    if len(选) > 1: 双 += 1
print("\n  两人同框的格数：%d / 32" % 双)
for g in 九["格们"]:
    选, _ = 剧组.挑角色(g["提示词"], 卡)
    print("  格%-3d %-10s %s" % (g["号"], g["景别"], "、".join(选) or "（空镜）"))
