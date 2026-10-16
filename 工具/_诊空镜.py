import sys, os, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠"); os.chdir(r"D:\DSHworkspace\影匠")
import 剧组
p = r"D:\DSHworkspace\影匠\作品\楚子航\02-九宫格.md"
九 = 剧组.解析九宫格(p)
卡 = [c["名"] if isinstance(c, dict) else c[0] for c in 九["角色卡"]]
print("  角色卡：", 卡)
坏 = 0
for g in 九["格们"]:
    选, 备 = 剧组.挑角色(g["提示词"], 卡)
    号 = g.get("号") or g.get("标题","?")
    应空 = "画面里没有一个人" in g["提示词"] or "画面里没有任何人" in g["提示词"]
    if 应空 and 选:
        print("  ✗ 格%s 应该是空镜，却选出了 %s（备注：%s）" % (号, 选, 备)); 坏 += 1
    elif 号 in (3, 5, 8, 9, 18, 26, 32) and len(选) > 1:
        print("  ✗ 格%s 应该是空的或单人，选出 %s" % (号, 选)); 坏 += 1
print("  —— 空镜/单人判错 %d 格" % 坏)
