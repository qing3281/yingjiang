# -*- coding: utf-8 -*-
"""一人一嗓：夏弥 和 耶梦加得 是同一个人（龙王耶梦加得就是夏弥），
不该用两把嗓子。用户 m01873 一句话：「两人用一个嗓子」。

做法（不重配 32 句，只重配受影响的那 3 句）：
  1. 备份 `影匠\音色\角色映射.json`
  2. 把 耶梦加得 的音色改成 夏弥 那一把（连备选一起改）
  3. 只重配 台词表 里说话人是 耶梦加得 的那几句
  4. 把新的结果并回 `配音\_配音表.json`（其余 29 条原样不动）

用法：python _修一人一嗓.py --看   /   python _修一人一嗓.py
"""
import os, sys, json, time, shutil

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
sys.path.insert(0, r"D:\DSHworkspace\影匠\作品\楚子航")

import 配音
from _台词表 import 台词表

映射路 = r"D:\DSHworkspace\影匠\音色\角色映射.json"
配音目 = r"D:\DSHworkspace\影匠\作品\楚子航\配音"
表路 = os.path.join(配音目, "_配音表.json")

合 = "耶梦加得"
源 = "夏弥"


def 干():
    d = json.load(open(映射路, encoding="utf-8"))
    角 = d["角色"]
    if 合 not in 角:
        print("✗ 映射表里没有 %s" % 合)
        return 1
    旧 = 角[合].get("音色")
    新 = 角[源].get("音色")
    print("  %s 现在 = %s" % (合, 旧))
    print("  %s 用的 = %s" % (源, 新))
    if 旧 == 新:
        print("  · 已经是一把嗓子了，不用改")
        return 0

    要配 = sorted(号 for 号, v in 台词表.items() if v[0] == 合)
    print("  受影响的行：%s（共 %d 句）" % (要配, len(要配)))

    if "--看" in sys.argv:
        print("  （--看：到此为止，什么都没写）")
        return 0

    # 1) 备份
    戳 = time.strftime("%Y%m%d-%H%M%S")
    备 = 映射路 + ".bak-" + 戳
    shutil.copy2(映射路, 备)
    print("  ✓ 备份 %s（%d B）" % (os.path.basename(备), os.path.getsize(备)))

    # 2) 改映射
    角[合]["音色"] = 新
    if isinstance(角[合].get("备选"), list):
        角[合]["备选"] = [x for x in 角[合]["备选"] if x != 旧] or [新]
    角[合]["改自"] = "原用 %s，2026-10-16 并入 %s：同一个人不配两把嗓子" % (旧, 源)
    json.dump(d, open(映射路, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    回 = json.load(open(映射路, encoding="utf-8"))
    assert 回["角色"][合]["音色"] == 新, "回读校验失败"
    print("  ✓ 映射改完并回读校验通过")

    # 3) 只重配那几句
    表 = [{"序号": 号, "台词": 台词表[号][1], "角色": 合} for 号 in 要配]
    print("  开始重配 %d 句…" % len(表))
    果 = 配音.批量(表, 输出目录=配音目, 报=lambda s: print("    " + str(s)))

    新条 = {}
    for x in 果.get("配音", []):
        if x.get("错"):
            print("    ✗ 序号 %s 出错：%s" % (x.get("序号"), x.get("错")))
            continue
        新条[str(x.get("序号"))] = x

    # 4) 并回 _配音表.json
    全 = json.load(open(表路, encoding="utf-8"))
    print("  _配音表.json 原来有 %d 条" % len(全.get("配音", [])))
    改成 = 0
    for i, x in enumerate(全.get("配音", [])):
        k = str(x.get("序号"))
        if k in 新条:
            全["配音"][i] = 新条[k]
            改成 += 1
    json.dump(全, open(表路, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("  ✓ 并回 %d 条，写 %s" % (改成, 表路))
    for x in 全.get("配音", []):
        print("    %s  %s  %s 秒  %s" % (x.get("序号"), x.get("角色"), x.get("秒"), os.path.basename(str(x.get("路")))))
    return 0


if __name__ == "__main__":
    sys.exit(干())
