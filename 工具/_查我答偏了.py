# -*- coding: utf-8 -*-
"""_查我答偏了.py —— 把他本人敲的话和我下一条回答并排摆出来，逐条对。

为什么要写（用户 2026-10-16 00:55 的原话）：
    「你查一下你之前的全部的，就我最近的给你的这些回话，你看一下，
    我觉得你的记忆还有缺呢，你给我回答的问题都牛头不对马嘴。」

    光凭印象说「我没答偏」是没用的 —— 他手上有原话，我没有。

存档的真实形状（踩过一次才知道，见 `_看存档长什么样.py`）：
    每行是 `{"type": …, "seq": …, "time": …, "data": {…}}`。
    ★ **`source` 在 `data` 里面，不在顶层。** 第一版我按顶层取 `r["source"]`，
    64932 行筛出 0 条。真判据是 `r["data"]["source"]["kind"] == "user"`
    且 `r["data"]["source"]["rpcId"]` 存在（只有人从界面敲的才有）。

用法：
    python _查我答偏了.py                 # 最近 20 条
    python _查我答偏了.py --条 40
    python _查我答偏了.py --型号          # 先看 type 都有哪些
"""
import glob
import io
import json
import os
import re
import sys
from collections import Counter

import zstandard

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSH\home\sessions\--D-DSHworkspace--"
出 = r"D:\DSHworkspace\记忆\对账_答偏.md"


def 读():
    场 = sorted(glob.glob(os.path.join(根, "*", "session.v4.jsonl.zstd")), key=os.path.getmtime)
    if not 场:
        return None, []
    原 = zstandard.ZstdDecompressor().stream_reader(open(场[-1], "rb")).read()
    行们 = []
    for 行 in 原.decode("utf-8", "replace").splitlines():
        行 = 行.strip()
        if not 行:
            continue
        try:
            行们.append(json.loads(行))
        except Exception:
            pass
    return 场[-1], 行们


def 掏文本(d):
    """从 data 里掏出人写的字。"""
    if isinstance(d, str):
        return d
    if not isinstance(d, dict):
        return ""
    for k in ("text", "content", "message", "prompt", "input"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, list):
            段 = []
            for x in v:
                if isinstance(x, str):
                    段.append(x)
                elif isinstance(x, dict) and isinstance(x.get("text"), str):
                    段.append(x["text"])
            if 段:
                return "\n".join(段)
    # 兜底：整个 data 序列化出来找最长的中文串
    s = json.dumps(d, ensure_ascii=False)
    串 = re.findall(r'"([^"]{8,})"', s)
    串 = [x for x in 串 if re.search(r"[\u4e00-\u9fa5]", x)]
    return max(串, key=len) if 串 else ""


def 主(条数, 看型号):
    最新, 行们 = 读()
    if not 行们:
        print("  ✗ 读不到会话存档：%s" % 根)
        return 1
    print("  · 存档 %s" % 最新)
    print("  · %d 行" % len(行们))

    if 看型号:
        c = Counter(r.get("type") for r in 行们)
        print("  ── type 分布 ──")
        for k, v in c.most_common(24):
            print("     %-40s %d" % (k, v))
        return 0

    他 = []
    for i, r in enumerate(行们):
        d = r.get("data")
        if not isinstance(d, dict):
            continue
        s = d.get("source")
        if not isinstance(s, dict) or s.get("kind") != "user":
            continue
        if not s.get("rpcId"):
            continue
        t = 掏文本(d).strip()
        if t:
            他.append((i, t))
    print("  · 他本人敲的 %d 条" % len(他))
    if not 他:
        print("  ✗ 还是 0 条 —— 跑 `python _查我答偏了.py --型号` 看 type 都有哪些")
        return 1

    # 每条后面接「我的下一条回答」：从它往后找第一条有字、且不是 user 的
    段 = []
    for k, (i, t) in enumerate(他):
        止 = 他[k + 1][0] if k + 1 < len(他) else len(行们)
        我 = ""
        for j in range(i + 1, min(止, i + 400)):
            d2 = 行们[j].get("data")
            if not isinstance(d2, dict):
                continue
            s2 = d2.get("source") or {}
            if isinstance(s2, dict) and s2.get("kind") == "user":
                continue
            x = 掏文本(d2).strip()
            if len(x) > 30:
                我 = x
                break
        段.append((t, 我))

    段 = 段[-条数:]
    行 = ["# 他问的 vs 我答的（`_查我答偏了.py` 生成，不是我手写的）", ""]
    n偏 = 0
    for t, 我 in reversed(段):
        偏 = False
        if not 我:
            偏 = True
        else:
            有路径 = bool(re.search(r"[A-Za-z]:\\|\.py\b|\.md\b|\.png\b|\.jpg\b", 我[:400]))
            词 = [w for w in re.findall(r"[\u4e00-\u9fa5]{2,}", t)]
            接住 = any(w in 我[:500] for w in 词[:8]) if 词 else True
            if not 有路径 and not 接住:
                偏 = True
        if 偏:
            n偏 += 1
        行.append("## %s %s" % ("✗ 可能答偏" if 偏 else "✓", t[:60].replace("\n", " ")))
        行.append("")
        行.append("- **他说的**：%s" % t[:500].replace("\n", " "))
        行.append("- **我答的开头**：%s" % (我[:400].replace("\n", " ") or "（没找到回答）"))
        行.append("")

    行.append("────")
    行.append("最近 %d 条里，标了「可能答偏」的 **%d 条**。" % (len(段), n偏))
    io.open(出, "w", encoding="utf-8").write("\n".join(行))
    print()
    print("  → 最近 %d 条，可能答偏的 %d 条" % (len(段), n偏))
    print("  → 写成 %s" % 出)
    print()
    for t, 我 in list(reversed(段))[:8]:
        print("  ── 他：%s" % t[:74].replace("\n", " "))
        print("     我：%s" % (我[:96].replace("\n", " ") or "（没找到回答）"))
    return 0


if __name__ == "__main__":
    n = 20
    if "--条" in sys.argv:
        try:
            n = int(sys.argv[sys.argv.index("--条") + 1])
        except Exception:
            pass
    sys.exit(主(n, "--型号" in sys.argv))
