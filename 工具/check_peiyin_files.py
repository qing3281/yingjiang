# -*- coding: utf-8 -*-
"""验「配音表指向的每一个 wav 都真的在磁盘上」。
为什么要有这一条：_修一人一嗓.py 是「重配 19/21/22 再把它们合并进 _配音表.json」，
合并这一步只要写错一个路径，那 3 句人声会在混音时静默消失 —— 成片照样出得来，
只是那 3 句没人说话。这是「假 PASS」最容易藏身的地方。
"""
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
配音目 = os.path.join(目, "配音")
表路 = os.path.join(配音目, "_配音表.json")

print("配音表：%s" % 表路)
if not os.path.isfile(表路):
    print("✗ 配音表不在")
    sys.exit(1)

果 = json.load(open(表路, encoding="utf-8"))
表 = 果.get("配音") or []
print("表里 %d 句　总时长字段 %s" % (len(表), 果.get("总时长")))
print()

缺 = []
空 = []
总秒 = 0.0
for it in sorted(表, key=lambda x: x.get("序号", 0)):
    号 = it.get("序号")
    路 = it.get("路") or ""
    秒 = it.get("秒")
    名 = it.get("音色") or it.get("角色") or ""
    ok = os.path.isfile(路)
    if not ok:
        缺.append((号, 路))
    else:
        n = os.path.getsize(路)
        if n < 2000:
            空.append((号, 路, n))
        try:
            总秒 += float(秒)
        except Exception:
            pass
    头 = ""
    if ok:
        with open(路, "rb") as f:
            头 = f.read(4).decode("latin-1")
    print("  #%-3s %-6s %-7s %7s 字节  头=%-5s 文件在=%s  %s"
          % (号, ("%.3f" % float(秒)) if 秒 is not None else "?", "", 
             os.path.getsize(路) if ok else "-", 头, ok, 名[:22]))

print()
print("缺文件 %d 个　过小(<2000B) %d 个" % (len(缺), len(空)))
for x in 缺:
    print("   ✗ #%s %s" % x)
for x in 空:
    print("   ✗ #%s %s %s 字节" % x)

算 = 32 * (4 * 56 / 24.0)
print("32 句人声合计 %.2f 秒　全片 %.2f 秒" % (总秒, 算))

过 = (len(表) == 32 and not 缺 and not 空)
print()
print("结论：%s" % ("✓ 32 句人声全部在磁盘上、都非空" if 过 else "✗ 有问题，见上"))
sys.exit(0 if 过 else 1)
