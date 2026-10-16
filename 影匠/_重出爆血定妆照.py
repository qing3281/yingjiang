# -*- coding: utf-8 -*-
"""重出「楚子航_爆血」定妆照 —— 眼睛改淡之后。
出 3 张：种子 808（原来那张的脸）+ 另外两个种子，让用户挑。
"""
import importlib.util, os, sys, json, time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")

sp = importlib.util.spec_from_file_location("定妆", r"D:\DSHworkspace\影匠\定妆.py")
定妆 = importlib.util.module_from_spec(sp)
sp.loader.exec_module(定妆)

出目录 = r"D:\DSHworkspace\影匠\作品\楚子航\_定妆卡_楚子航_爆血"
os.makedirs(出目录, exist_ok=True)

print("  原卡：种子 %d　%d×%d　模板 %s" % (定妆.种子("楚子航_爆血"), *定妆.尺寸("楚子航_爆血"), 定妆.卡("楚子航_爆血")["模板"]))
print()

种子们 = [808, 20261016, 777]
结果 = []
for i, 种 in enumerate(种子们, 1):
    名 = "楚子航_爆血.png" if 种 == 808 else "楚子航_爆血_种%d.png" % 种
    存 = os.path.join(出目录, 名)
    t0 = time.time()
    print("  [%d/%d] 种子 %d → %s" % (i, len(种子们), 种, 名), flush=True)
    try:
        r = 定妆.出图("楚子航_爆血", 存到=存, 种子=种)
        用时 = time.time() - t0
        if os.path.exists(存):
            print("        ✓ %.0f 秒　%d B" % (用时, os.path.getsize(存)))
            结果.append((名, 存, 用时))
        else:
            print("        ★ 没生成：%s" % r)
    except Exception as e:
        print("        ★ 炸了：%s" % e)

print()
print("══ 出完了 ══")
for 名, 存, 用时 in 结果:
    print("  %s  %.0f 秒  %d B" % (名, 用时, os.path.getsize(存)))
