# -*- coding: utf-8 -*-
"""把「改眼睛之前」那张补出来当对照。
为什么：我重出的时候直接把 楚子航_爆血.png 覆盖了，没先备份图 —— 用户看不到「改之前长什么样」。
老提示词还在 .bak-改眼睛前 里，拿它按同一个种子 808 重画一张就是原来那张。
"""
import importlib.util, json, os, shutil, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")

卡目录 = r"D:\DSHworkspace\影匠\角色卡"
j = os.path.join(卡目录, "楚子航_爆血.json")
出目录 = r"D:\DSHworkspace\影匠\作品\楚子航\_定妆卡_楚子航_爆血"

旧卡 = json.load(open(j + ".bak-改眼睛前", encoding="utf-8"))
新卡文本 = open(j, encoding="utf-8").read()

# 临时把卡换回旧的
json.dump(旧卡, open(j, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
try:
    sp = importlib.util.spec_from_file_location("定妆", r"D:\DSHworkspace\影匠\定妆.py")
    定妆 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(定妆)
    存 = os.path.join(出目录, "_旧眼睛_对照.png")
    print("  按老提示词 + 种子 %d 重画一张…" % 旧卡["种子"], flush=True)
    r = 定妆.出图("楚子航_爆血", 存到=存, 种子=旧卡["种子"])
    if os.path.exists(存):
        print("  ✓ %s  %d B" % (存, os.path.getsize(存)))
    else:
        print("  ★ 没出来：%s" % r)
finally:
    # 不管成不成，把卡换回新的
    open(j, "w", encoding="utf-8").write(新卡文本)
    print("  ✓ 卡已换回新版本（眼睛淡的那版）")
