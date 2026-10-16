# -*- coding: utf-8 -*-
"""看一眼角色库里有什么（避免在 PowerShell here-string 里跟引号打架）。"""
import json
import os
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

for 名 in ("角色\\角色库.json", "角色库.json"):
    p = os.path.join(根, 名)
    if os.path.exists(p):
        print(f"文件：{p}  {os.path.getsize(p):,} B")
        d = json.load(open(p, encoding="utf-8"))
        print("顶层键：", list(d))
        角 = d.get("角色") or d.get("角色库") or {}
        print(f"角色数：{len(角)}")
        for k, v in 角.items():
            if isinstance(v, dict):
                照 = v.get("定妆照") or ""
                print(f"  - {k}  名={v.get('名')}  定妆照={'有 ' + os.path.basename(照) if 照 else '无'}")
                print(f"      字段：{list(v)}")
        break
else:
    print("✗ 没找到角色库.json")

# 顺便看看 导演.立戏 / 角色库.外貌串 的签名
try:
    import 角色库

    print("\n角色库.py 里带『外貌』的函数：")
    for n in dir(角色库):
        if "外貌" in n or "串" in n:
            print("   ", n)
    print("\n能叫的角色：", [x for x in dir(角色库) if not x.startswith("_")][:40])
except Exception as e:  # noqa: BLE001
    print("import 角色库 失败：", e)
