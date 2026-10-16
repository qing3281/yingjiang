# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 角色库 as r   # noqa: E402

r._载()
print(f"角色表 {len(r.角色表)} 个 / 词典 {len(r._词典)} 条")
for k, v in r.角色表.items():
    print(f"  {k:6s} 种子{v.get('种子')}  {v.get('性别')}/{v.get('年龄')}  "
          f"定妆照={'有' if v.get('定妆照') else '无'}")
    a = r.外貌串(k)
    print(f"         锚点：{a.get('串','')[:120]}")
