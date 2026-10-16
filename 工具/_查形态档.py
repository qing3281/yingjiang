import sys, os, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 剧组
根 = r"D:\DSHworkspace\影匠\作品\楚子航"
九 = 剧组.解析九宫格(os.path.join(根, "02-九宫格.md"))
规格 = importlib.util.spec_from_file_location("规约", os.path.join(根, "_写作规约.py"))
规约 = importlib.util.module_from_spec(规格); 规格.loader.exec_module(规约)
print("  损伤档 keys:", sorted(规约.损伤档.keys()))
for k in sorted(规约.损伤档.keys()):
    print("    档%d %3d字  %s" % (k, len(规约.损伤档[k]), 规约.损伤档[k][:60]))
print()
print("  爆血档 keys:", sorted(规约.爆血档.keys()))
for k in sorted(规约.爆血档.keys()):
    print("    档%d %3d字  %s" % (k, len(规约.爆血档[k]), 规约.爆血档[k][:60]))
print()
print("  龙化档 keys:", sorted(规约.龙化档.keys()))
for k in sorted(规约.龙化档.keys()):
    print("    档%d %3d字  %s" % (k, len(规约.龙化档[k]), 规约.龙化档[k][:60]))
print()
for 号 in (22, 24, 26, 27, 28, 29, 30):
    g = [x for x in 九["格们"] if x["号"] == 号][0]
    t = g["提示词"]
    损 = next((k for k in sorted(规约.损伤档, reverse=True) if 规约.损伤档[k] and 规约.损伤档[k] in t), None)
    爆 = next((k for k in sorted(规约.爆血档, reverse=True) if 规约.爆血档[k] and 规约.爆血档[k] in t), None)
    龙 = next((k for k in sorted(规约.龙化档, reverse=True) if 规约.龙化档[k] and 规约.龙化档[k] in t), None)
    print("  格%-2d 长度%5d  损伤档=%s  爆血档=%s  龙化档=%s" % (号, len(t), 损, 爆, 龙))
