# -*- coding: utf-8 -*-
"""看一眼角色卡里到底有哪些字段，以及 外貌串() 吐出来的锚点长什么样。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 角色库  # noqa: E402

角 = 角色库.取("凌霜")
print("=== 角色卡字段 ===")
for k, v in (角 or {}).items():
    print(f"  {k:14} = {v!r}")

print("\n=== 外貌串('凌霜') ===")
print(" ", 角色库.外貌串("凌霜"))

print("\n=== 公开接口 ===")
print(" ", [x for x in dir(角色库) if not x.startswith("_")])
