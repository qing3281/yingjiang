import sys, os, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
根 = r"D:\DSHworkspace\影匠\作品\楚子航"
格 = []
for f in ("_格数据_上.py", "_格数据_下.py"):
    spec = importlib.util.spec_from_file_location("q"+f[-6:-3], os.path.join(根, f))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); 格 += m.格
格.sort(key=lambda g: g["号"])
坏词 = ["隧道口","天光","洞口","枕木","碎石","煤渣","拱顶","道砟","出口"]
print("格  还在用铁路/天光的词")
总 = {}
for g in 格:
    文 = g["位置"] + g["画面"] + g.get("特效","") + g["机"]
    命 = [w for w in 坏词 if w in 文]
    if 命:
        print("  %-3d %s" % (g["号"], "/".join(命)))
        for w in 命: 总[w] = 总.get(w,0)+1
print()
print("★ 合计：", 总)
