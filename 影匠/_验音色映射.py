# -*- coding: utf-8 -*-
"""验 音色\角色映射.json 对《磨刀》七个说话人 + 别名能不能解析出来。

为什么不只用 here-string 跑：PowerShell 的 here-string 会把 Python 里的双引号吃掉，
`["沈砚"]` 变成 `[沈砚]` → SyntaxError。这个坑踩过（见 知识\\配音.md）。
"""
import importlib.util
import json
import os
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

spec = importlib.util.spec_from_file_location("配音", os.path.join(根, "配音.py"))
配音 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(配音)

表 = json.load(open(os.path.join(根, "音色", "角色映射.json"), encoding="utf-8"))["角色"]
原声 = os.path.join(根, "音色", "原声")

试 = ["沈砚", "沈砚（少年）", "少年沈砚", "赵崇武", "赵大人",
      "阿七", "阿七（画外）", "阿满", "周泰", "旁白", "凌霜", "不存在的人"]

行 = []
坏 = 0
for 名 in 试:
    try:
        路, 源 = 配音.角色定音色(名)
    except Exception as e:  # noqa: BLE001
        行.append(f"  {名:<12} ✗ {type(e).__name__}: {e}")
        坏 += 1
        continue
    在 = os.path.exists(os.path.join(原声, 路.replace("/", os.sep)))
    if not 在:
        坏 += 1
    行.append(f"  {名:<12} 源={源:<8} 在盘={'✓' if 在 else '✗'}  {路}")

print("\n".join(行))
print(f"\n映射表里 {len(表)} 个角色；上面 {len(试)} 个查询，{坏} 个没解析出来或不在盘上")

# 剧本里用到的说话人是否都覆盖了
台词 = os.path.join(根, "作品", "磨刀", "03-台词.md")
if os.path.exists(台词):
    import re
    说过 = set()
    for ln in open(台词, encoding="utf-8"):
        if not ln.strip().startswith("|"):
            continue
        格 = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(格) >= 2 and not 格[0].startswith("-") and 格[0] not in ("格", "格号"):
            说过.add(格[1])
    print(f"\n台词表里出现的说话人（{len(说过)} 个）：")
    没配 = []
    for 谁 in sorted(说过):
        净 = re.sub(r"[（(].*?[)）]", "", 谁).strip()
        全 = 谁.replace("（", "").replace("）", "").strip()
        命中 = 谁 in 表 or 净 in 表 or 全 in 表
        print(f"  {'✓' if 命中 else '✗'} {谁}")
        if not 命中:
            没配.append(谁)
    if 没配:
        print(f"  ⚠ 没配到音色的：{没配}")
    else:
        print("  全部有音色 ✓")
