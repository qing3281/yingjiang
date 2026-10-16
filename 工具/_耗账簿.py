#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_耗账簿.py —— 我到底烧得多快。实测，不估。

## 为什么要有

用户 2026-10-15 02:20 原话：
    「你这就给我跟你要做什么，什么时候做完，要花多少的资源、多少的时间，
      需要一些什么样的协助、人力物力……你要花多少的 token、要花多少的空间、
      要花多少的时间、要花什么资源，这些你也得有一个详细的计划。」
    「以后你做一个任务之前，你得先对他进行一个分析，或者是预估，或者是定下一个计划。」

**他问的是「花多少」，我上一版计划只回答了「做什么」。**
而估数如果不从实测来，就又是一次假判据（`影匠/知识/假判据族.md` 那七种形状之一）。

## 数据来源

`D:\\DSH\\home\\sessions\\--D-DSHworkspace--\\<id>\\session.v4.jsonl.zstd` 里
`assistant/message` 的 `data.usage`：
    {inputTokens, outputTokens, totalTokens, cacheReadTokens, reasoningTokens}

这些数**不是我上报的，是客户端自己记的**，所以能当证据用。

## 用法

    python _耗账簿.py            总账 + 每小时速率
    python _耗账簿.py --按天      按天看
    python _耗账簿.py --场次      逐场看（最近 15 场）
"""
import glob
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

北京 = timezone(timedelta(hours=8))
存档根 = r"D:\DSH\home\sessions\--D-DSHworkspace--"


def 读一场(路):
    """返回 [(时刻, 用量dict), ...]"""
    try:
        import zstandard as zstd
        with open(路, "rb") as f:
            文 = zstd.ZstdDecompressor().stream_reader(f).read().decode("utf-8", "replace")
    except Exception:
        return []
    出 = []
    for 行 in 文.splitlines():
        if '"usage"' not in 行:
            continue
        try:
            j = json.loads(行)
        except Exception:
            continue
        if j.get("type") != "assistant/message":
            continue
        d = j.get("data") or {}
        u = d.get("usage") or {}
        if not u:
            continue
        t = j.get("time")
        if not t:
            continue
        出.append((t / 1000.0, u))
    return 出


def 场次表():
    出 = []
    for p in glob.glob(os.path.join(存档根, "*", "session.v4.jsonl.zstd")):
        点s = 读一场(p)
        if not 点s:
            continue
        出.append({
            "id": os.path.basename(os.path.dirname(p))[:8],
            "起": min(t for t, _ in 点s),
            "止": max(t for t, _ in 点s),
            "点s": 点s,
        })
    出.sort(key=lambda x: x["止"])
    return 出


def 合(点s):
    r = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0,
         "cacheReadTokens": 0, "reasoningTokens": 0}
    for _, u in 点s:
        for k in r:
            r[k] += int(u.get(k) or 0)
    return r


def 万(n):
    return n / 10000.0


def main():
    参 = sys.argv[1:]
    场s = 场次表()
    if not 场s:
        print("读不到任何会话存档")
        return 1

    if "--按天" in 参:
        print("=" * 78)
        print("  按天 —— 我一天烧多少")
        print("=" * 78)
        天 = {}
        for c in 场s:
            for t, u in c["点s"]:
                d = datetime.fromtimestamp(t, 北京).strftime("%m-%d")
                天.setdefault(d, []).append((t, u))
        print(f"{'日期':<8}{'消息':>6}{'输入万':>10}{'缓存读万':>11}{'输出万':>9}"
              f"{'其中推理万':>11}{'合计万':>10}{'每小时万':>10}")
        for d in sorted(天):
            点 = 天[d]
            r = 合(点)
            跨 = (max(t for t, _ in 点) - min(t for t, _ in 点)) / 3600.0
            每 = 万(r["totalTokens"]) / max(0.1, 跨)
            print(f"{d:<8}{len(点):>6}{万(r['inputTokens']):>10.1f}"
                  f"{万(r['cacheReadTokens']):>11.1f}{万(r['outputTokens']):>9.1f}"
                  f"{万(r['reasoningTokens']):>11.1f}{万(r['totalTokens']):>10.1f}{每:>10.1f}")
        return 0

    if "--场次" in 参:
        print("=" * 78)
        print("  逐场（最近 15 场）")
        print("=" * 78)
        print(f"{'场次':<10}{'起':<12}{'止':<12}{'小时':>6}{'消息':>6}"
              f"{'合计万':>9}{'每小时万':>10}")
        for c in 场s[-15:]:
            r = 合(c["点s"])
            跨 = (c["止"] - c["起"]) / 3600.0
            f = lambda t: datetime.fromtimestamp(t, 北京).strftime("%m-%d %H:%M")
            print(f"{c['id']:<10}{f(c['起']):<12}{f(c['止']):<12}{跨:>6.1f}"
                  f"{len(c['点s']):>6}{万(r['totalTokens']):>9.1f}"
                  f"{万(r['totalTokens'])/max(0.05, 跨):>10.1f}")
        return 0

    # 总账
    print("=" * 78)
    print("  我的总账（数据来自客户端记的 usage，不是我上报的）")
    print("=" * 78)
    全 = []
    for c in 场s:
        全 += c["点s"]
    r = 合(全)
    起 = min(t for t, _ in 全)
    止 = max(t for t, _ in 全)
    跨 = (止 - 起) / 3600.0
    print(f"  会话场次      {len(场s)}")
    print(f"  时间跨度      {datetime.fromtimestamp(起, 北京):%m-%d %H:%M} → "
          f"{datetime.fromtimestamp(止, 北京):%m-%d %H:%M}  （{跨:.1f} 小时）")
    print(f"  助手消息      {len(全):,} 条")
    print()
    print(f"  输入（新）    {r['inputTokens']:>15,}   {万(r['inputTokens']):>9.1f} 万")
    print(f"  缓存读        {r['cacheReadTokens']:>15,}   {万(r['cacheReadTokens']):>9.1f} 万")
    print(f"  输出          {r['outputTokens']:>15,}   {万(r['outputTokens']):>9.1f} 万")
    print(f"    其中推理    {r['reasoningTokens']:>15,}   {万(r['reasoningTokens']):>9.1f} 万"
          f"   （占输出 {100*r['reasoningTokens']/max(1,r['outputTokens']):.0f}%）")
    print(f"  合计          {r['totalTokens']:>15,}   {万(r['totalTokens']):>9.1f} 万")
    print()
    print(f"  ★ 平均每小时烧 {万(r['totalTokens'])/max(0.1,跨):.1f} 万 token")
    print(f"  ★ 平均每条消息烧 {万(r['totalTokens'])/max(1,len(全)):.1f} 万 token")
    print()
    print("  白话：")
    小 = 万(r["totalTokens"])
    print(f"    这一整段历史一共烧了约 {小:,.0f} 万 token。")
    print(f"    按每小时 {万(r['totalTokens'])/max(0.1,跨):.0f} 万算，"
          f"干 10 小时约 {万(r['totalTokens'])/max(0.1,跨)*10:,.0f} 万。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
