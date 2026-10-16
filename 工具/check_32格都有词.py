# -*- coding: utf-8 -*-
"""check_32格都有词.py —— 核目标里那一条「32 格里 11 个没词的格补上字了没有」。

他 10-16 08:46 的原话里第二条：「字幕也非常非常少的可怜」，
点名的没词格是 **1/8/10/17/18/23/25/26/28/31/32**（11 个）。

这个脚本只做一件事：把 `_配音表.json` 的 32 条按「序号 = 第几格」铺开，
逐格打印台词 + 时长，再单独把那 11 个格挑出来问一句「有词吗」。
★ 只读，不改任何东西。
"""
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
表 = os.path.join(目, "配音", "_配音表.json")
点名 = [1, 8, 10, 17, 18, 23, 25, 26, 28, 31, 32]

d = json.load(open(表, encoding="utf-8"))
配 = d["配音"]
print("配音表 %s" % 表)
print("条目 %d 条　总时长字段 %s 秒　目录 %s" % (len(配), d.get("总时长"), d.get("目录")))
print()

号到 = {}
for r in 配:
    号到[int(r["序号"])] = r

print("　　格　秒　　 台词")
空 = []
for i in range(1, 33):
    r = 号到.get(i)
    if not r:
        空.append(i)
        print("  %3d  ——　　★ 表里没有这一格" % i)
        continue
    t = (r.get("文本") or "").strip()
    if not t:
        空.append(i)
    print("  %3d  %5.3f　%s%s" % (i, float(r.get("秒") or 0), t if t else "★ 空", ""))

print()
print("32 格里没有词的：%s" % (空 if 空 else "无 ✓"))
缺 = [i for i in 点名 if i in 空]
print("他点名的那 11 个格（%s）里还空着的：%s"
      % ("/".join(str(x) for x in 点名), 缺 if 缺 else "无 ✓ —— 全部补上了"))
print()
mk = [r for r in 配 if (r.get("字幕") or "").strip()]
print("带「字幕」字段的条数：%d / %d" % (len(mk), len(配)))

srt = os.path.join(目, "片_官方", "台词.srt")
if os.path.isfile(srt):
    txt = open(srt, encoding="utf-8", errors="replace").read()
    n = txt.count("-->")
    print("硬字幕用的 %s：%d 条" % (os.path.basename(srt), n))
    print("  ✓ 条数和配音表一致" if n == len(配) else "  ★ 条数对不上：srt %d vs 配音表 %d" % (n, len(配)))
else:
    print("★ 找不到 %s" % srt)
