import sys, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 角色库 as K
print("  词典条数：", len(K._词典))
试 = ["黑色短发被雨淋透贴在额头上","右眼下方一道两厘米长的旧疤","黑色校服外套的左袖口撕裂到肘部",
      "二十一岁","嘴角有干掉的血痕","脸上全是雨水","右手从手背到手腕缠着白色绷带",
      "绷带被雨泡成灰色","绷带头从手腕垂下来一截随动作甩动","右手握刀",
      "金色长发垂到腰","金色竖瞳","白皮肤","黑色长风衣","风衣下摆是鳞片",
      "龙王人形","一根都没湿","嘴裂到耳根","牙齿是三角形","脚是爪子","踩在桥面上留出三道白痕",
      "嘴里叼着一块带卡塞尔学院银色徽章的蓝色校服布"]
坏 = []
for s in 试:
    try:
        r = K._译(s)
    except Exception as e:
        r = "!!" + type(e).__name__
    if not r or re.search(r"[\u4e00-\u9fff]", str(r)):
        坏.append((s, r))
    print(f"    {s[:22]:24s} -> {str(r)[:64]}")
print()
print("  ★ 还有中文没译出的：", len(坏))
for s, r in 坏:
    print("     -", s, "->", r)
