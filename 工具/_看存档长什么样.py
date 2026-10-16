# -*- coding: utf-8 -*-
"""_看存档长什么样.py —— 会话存档里一条记录到底有哪些字段。

为什么要有这个：`_查我答偏了.py` 按 `source.kind == "user"` 且 `source.rpcId` 去筛他本人敲的话，
**一条都没筛出来**（64920 行，0 条）。说明我对存档结构的假设是错的。
先把真字段打出来再改筛法 —— 不要猜。
"""
import glob
import io
import json
import os
import sys
import zstandard

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSH\home\sessions\--D-DSHworkspace--"


def 主():
    场 = sorted(glob.glob(os.path.join(根, "*", "session.v4.jsonl.zstd")), key=os.path.getmtime)
    print("  存档 %d 个，取最新的：%s" % (len(场), 场[-1] if 场 else "（无）"))
    if not 场:
        return 1
    原 = zstandard.ZstdDecompressor().stream_reader(open(场[-1], "rb")).read()
    行们 = []
    for 行 in 原.decode("utf-8", "replace").splitlines():
        行 = 行.strip()
        if 行:
            try:
                行们.append(json.loads(行))
            except Exception:
                pass
    print("  解析出 %d 条" % len(行们))
    if not 行们:
        return 1

    # ① 顶层键的分布
    from collections import Counter
    键 = Counter()
    for r in 行们:
        键.update(r.keys())
    print()
    print("  ── 顶层键（出现次数）──")
    for k, v in 键.most_common(20):
        print("     %-24s %d" % (k, v))

    # ② source 的形态
    print()
    print("  ── source 字段的取值（前 12 种）──")
    c2 = Counter()
    for r in 行们:
        s = r.get("source")
        if isinstance(s, dict):
            c2["dict: kind=%s rpcId=%s" % (s.get("kind"), "有" if s.get("rpcId") else "无")] += 1
        elif s is None:
            c2["None"] += 1
        else:
            c2["%s" % type(s).__name__] += 1
    for k, v in c2.most_common(12):
        print("     %-46s %d" % (k, v))

    # ③ 一条长得像「人说的话」的记录，原样打出来
    print()
    print("  ── 找一条像人话的，原样打印（截 1400 字）──")
    for r in 行们:
        s = json.dumps(r, ensure_ascii=False)
        if "rpcId" in s or '"user"' in s:
            print(s[:1400])
            break
    return 0


if __name__ == "__main__":
    sys.exit(主())
