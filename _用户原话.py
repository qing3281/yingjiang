# -*- coding: utf-8 -*-
"""
_用户原话.py —— 从 DSH 会话存档里，把他本人敲的每一句话抽出来。

════════════════════════════════════════════════════════════════════
★ 为什么这个脚本存在（2026-10-15 01:30 立）

用户 2026-10-15 00:49 原话：
「我想要的是。越聪明，越用越懂我的 1 个 AI 助手。不是每一次都像重头来过，
每一次我都要花费这么长的时间，这么多的精力来纠正你的错误的一个。打杂的。」

要做「越用越懂他」，第一步得先知道**他到底说过什么** —— 不是我回忆里的他，
是磁盘上他真敲过的字。

════════════════════════════════════════════════════════════════════
★ 判据：怎么区分「他敲的」和「机器塞进来的」

`user/message` 这个 type 里混着十几种东西，绝大多数不是他说的。
踩了三次坑才找到唯一可靠的判据：

    data.source.kind == "user"  且  data.source.rpcId 存在

`rpcId` 是客户端发来的请求号 —— **只有人从界面上敲进去的话才有它**。
机器塞进来的（继续提示 / 队友身份 / 子代理任务书 / 运行时快照）全都没有 rpcId，
哪怕它们的 kind 也写着 "user"。

曾经用 kind=="user" 单条件筛，筛出 208 条，其中至少 17 条是
我给子代理写的任务书（「你的任务：从 ComfyUI 官方模板库…」）。
那 17 条被当成"他的原话"读进了 `用户画像.md` —— 是一个假判据。

实测分布（6 个大存档，user/message 的全部 kind）：
    kind=time-context          238
    user·有rpcId                168   ← 只有这些是他
    kind=plugin:hindsight      168
    kind=tool-jobs             117
    kind=team-message           43
    kind=subagent-settled       36
    kind=agent-message          27
    kind=goal                   23
    kind=skill-catalog          19
    kind=runtime-context        16
    kind=agent-instructions     12
    kind=compact-checkpoint     10
    user·无rpcId                  7   ← 继续提示 / 队友身份 / 子代理任务书
    kind=tool-goal               2
    kind=user-approval           1

════════════════════════════════════════════════════════════════════
用法：
    python _用户原话.py            # 扫描并写 _用户原话.json
    python _用户原话.py --看        # 只看统计，不写文件
    python _用户原话.py --验 20     # 打印前 20 条人工核对
"""

import os
import io
import re
import sys
import json
import glob
import time
import collections

sys.stdout.reconfigure(encoding="utf-8")

会话根 = r"D:\DSH\home\sessions"
出口 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_用户原话.json")


def 读存档(路):
    """解压一个 session.v4.jsonl.zstd，逐行 yield 解析好的对象。"""
    try:
        import zstandard
    except ImportError:
        print("  ✗ 缺 zstandard：用影匠的 python 跑这个脚本")
        raise SystemExit(1)
    d = zstandard.ZstdDecompressor()
    try:
        with open(路, "rb") as f:
            文 = d.stream_reader(f).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  ⚠ 解不开 {os.path.basename(os.path.dirname(路))}：{e}")
        return
    for 行 in 文.split("\n"):
        行 = 行.strip()
        if not 行:
            continue
        try:
            yield json.loads(行)
        except Exception:
            continue


def 取文(dd):
    """把 data.content 里所有 text 块拼起来。

    ★ 坑：content 是一个 [{"type":"text","text":"..."}] 的列表，不是字符串。
      直接当字符串用会得到 "<built-in method get of dict object>"。
    """
    c = dd.get("content")
    if isinstance(c, str):
        return c
    if not isinstance(c, list):
        return ""
    段 = []
    for b in c:
        if isinstance(b, dict) and b.get("type") == "text":
            段.append(b.get("text") or "")
        elif isinstance(b, str):
            段.append(b)
    return "\n".join(段).strip()


def 是他敲的(dd):
    """唯一判据：kind=='user' 且 有 rpcId。见文件头说明。"""
    src = dd.get("source") or {}
    return src.get("kind") == "user" and bool(src.get("rpcId"))


def 扫():
    档s = glob.glob(os.path.join(会话根, "*", "*", "session.v4.jsonl.zstd"))
    档s.sort(key=os.path.getsize, reverse=True)
    出 = []
    统计 = collections.Counter()
    会话数 = 0
    for p in 档s:
        会话id = os.path.basename(os.path.dirname(p))
        工作区 = os.path.basename(os.path.dirname(os.path.dirname(p)))
        会话数 += 1
        for o in 读存档(p):
            统计[o.get("type") or "?"] += 1
            if o.get("type") != "user/message":
                continue
            dd = o.get("data") or {}
            if not 是他敲的(dd):
                continue
            文 = 取文(dd)
            if not 文:
                continue
            出.append({
                "时": o.get("time") or (dd.get("time") or 0),
                "话": 文,
                "工": 工作区,
                "会": 会话id[:8],
            })
    # 去重：同一条话在同一毫秒可能被记两次
    见 = set()
    净 = []
    for x in 出:
        k = (x["时"], x["话"][:80])
        if k in 见:
            continue
        见.add(k)
        净.append(x)
    净.sort(key=lambda z: z["时"])
    return 净, 会话数, 统计


def 主():
    argv = sys.argv[1:]
    净, 会话数, 统计 = 扫()
    if not 净:
        print("  ✗ 一条都没抽到 —— 先确认 DSH 会话存档在不在")
        return

    起 = 净[0]["时"]
    止 = 净[-1]["时"]
    fmt = lambda t: time.strftime("%m-%d %H:%M", time.localtime(t / 1000))
    天 = collections.Counter(fmt(x["时"])[:5] for x in 净)

    print(f"  会话存档：{会话数} 个")
    print(f"  他本人敲的：{len(净)} 条")
    print(f"  时间跨度：{fmt(起)} → {fmt(止)}")
    print(f"  按天：{'  '.join(f'{k}={v}' for k, v in sorted(天.items()))}")
    长 = [len(x["话"]) for x in 净]
    print(f"  字数：中位 {sorted(长)[len(长)//2]}  最长 {max(长)}  合计 {sum(长):,}")

    if "--看" in argv:
        return

    if "--验" in argv:
        i = argv.index("--验")
        n = int(argv[i + 1]) if i + 1 < len(argv) and argv[i + 1].isdigit() else 10
        print(f"\n  ── 前 {n} 条，人工核对（这些必须每一句都像人话）──")
        for x in 净[:n]:
            t = re.sub(r"\s+", " ", x["话"])
            print(f"    [{fmt(x['时'])}] {t[:110]}")
        return

    with io.open(出口, "w", encoding="utf-8") as f:
        json.dump([{"时": x["时"], "话": x["话"]} for x in 净], f,
                  ensure_ascii=False, indent=1)
    print(f"  ✅ 写了 {出口}  {os.path.getsize(出口):,} B")
    print(f"     记忆台读的就是这个文件（_记忆台.py 的 扫画像()）")


if __name__ == "__main__":
    主()
