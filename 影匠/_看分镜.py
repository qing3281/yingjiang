# -*- coding: utf-8 -*-
"""自检：分镜 md 能不能被 _出片.py 正确读出来。出图之前必跑。"""
import importlib.util as u
import os
import sys

sys.path.insert(0, r"D:\DSHworkspace\影匠")
s = u.spec_from_file_location("出片", r"D:\DSHworkspace\影匠\_出片.py")
m = u.module_from_spec(s)
s.loader.exec_module(m)

路 = os.path.join(r"D:\DSHworkspace\影匠\作品\磨刀", "02-九宫格.md")
g = m.读格(路)
print(f"读到 {len(g)} 格")
号 = [x["号"] for x in g]
print(f"号连续性：{'✓ 1..%d 连续' % len(g) if 号 == list(range(1, len(g) + 1)) else '✗ ' + str(号)}")

键 = ("景别", "机位", "提示词", "重点", "光色", "动作")
坏 = [(x["号"], [k for k in 键 if not x[k]]) for x in g if any(not x[k] for k in 键)]
print(f"缺字段的格：{坏 if 坏 else '✓ 一格不缺'}")

print(f"\n人物字段：{'有' if any(x['人物'] for x in g) else '没有（按规矩不喂锚点，提示词自带）'}")

print("\n景别分布：")
from collections import Counter  # noqa: E402
for k, v in Counter(x["景别"] for x in g).most_common():
    print(f"  {v:3d}  {k}")

print("\n提示词长度：", end="")
长 = [len(x["提示词"]) for x in g]
print(f"最短 {min(长)} / 最长 {max(长)} / 平均 {sum(长)//len(长)} 字")
短 = [(x["号"], len(x["提示词"])) for x in g if len(x["提示词"]) < 150]
if 短:
    print(f"  ⚠ 偏短的格：{短}")

print("\n动作字段长度：", end="")
长 = [len(x["动作"]) for x in g]
print(f"最短 {min(长)} / 最长 {max(长)} / 平均 {sum(长)//len(长)} 字")

print("\n前 3 格速览：")
for x in g[:3]:
    print(f"  格{x['号']}  {x['标题']}")
    print(f"    {x['景别']}｜{x['机位'][:40]}")
    print(f"    词 {x['提示词'][:100]}…")
    print(f"    动 {x['动作'][:80]}…")
