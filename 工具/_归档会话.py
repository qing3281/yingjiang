# -*- coding: utf-8 -*-
"""
_归档会话.py —— 把 DSH 里的会话，从「一个只有 DSH 自己看得懂的压缩包」变成
「他双击就能看的一堆 markdown」。

════════════════════════════════════════════════════════════════════
★ 为什么要有这个脚本（用户 2026-10-16 m37867 亲口点的第一条活）

User said (m37867)：「我明天早上起来会验收你做的视频。以及你的各个分镜。……
以及你所列的任务目标计划。……」—— 其中第一条就是
**「归档之前所有会话，并做成每天定时自动做的固定动作」。**

存档现在长这样：
    D:\\DSH\\home\\sessions\\--D-DSHworkspace--\\<会话id>\\session.v4.jsonl.zstd
**一个 184 个目录的压缩包堆。他打不开、搜不了、看不了。**
这个脚本把它翻成 `D:\\DSHworkspace\\会话存档\\` 下的 markdown。

════════════════════════════════════════════════════════════════════
★ 每天一份，不是每个会话一份

为什么按天分：他要的是「我哪天跟你说了什么」，不是「第 37 号会话里有什么」。
一天里可能开了七八个会话（每次继续、每次重启都是一个新会话），
按会话分他会看到七八个碎片。**按天合成一份，他翻一天就是一整天的来龙去脉。**

════════════════════════════════════════════════════════════════════
★ 怎么区分「他敲的」和「机器塞进来的」（这个判据踩了三次坑，见 _用户原话.py 文件头）

    data.source.kind == "user"  且  data.source.rpcId 存在

`rpcId` 是客户端发来的请求号 —— **只有人从界面上敲进去的话才有它**。

════════════════════════════════════════════════════════════════════
用法：
    python _归档会话.py             # 扫全部会话、写 会话存档\\
    python _归档会话.py --看         # 只看统计，不写
    python _归档会话.py --天 2026-10-16   # 只归档某一天（调试用）
"""

import collections
import glob
import io
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

会话根 = r"D:\DSH\home\sessions"
出口目录 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "会话存档")


# ══════════════════════════════════════════════════════════════════
# 读存档（这段抄 _用户原话.py 的 读存档()，能用就用、能抄就抄）
# ══════════════════════════════════════════════════════════════════
def 读存档(路):
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
    """把 data.content 里所有 text 块拼起来（content 是列表，不是字符串）。"""
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
    src = dd.get("source") or {}
    return src.get("kind") == "user" and bool(src.get("rpcId"))


def 是机器塞的(dd):
    """机器塞进来的 user/message：kind=='user' 但没有 rpcId（继续提示 / 任务书 / 队友身份）。"""
    src = dd.get("source") or {}
    return src.get("kind") == "user" and not src.get("rpcId")


def 是工具(dd):
    """他开的工具调用。只留名字 + 一句话摘要，不留全文（全文会把归档撑爆）。"""
    名 = dd.get("name") or dd.get("toolName") or ""
    if not 名:
        return ""
    参 = dd.get("input") or dd.get("args") or {}
    摘 = ""
    if isinstance(参, dict):
        for k in ("command", "file_path", "path", "description", "pattern", "query", "prompt"):
            if 参.get(k):
                摘 = re.sub(r"\s+", " ", str(参[k]))[:90]
                break
    return f"{名}　{摘}".strip()


# ══════════════════════════════════════════════════════════════════
# 扫
# ══════════════════════════════════════════════════════════════════
def 扫():
    档s = glob.glob(os.path.join(会话根, "*", "*", "session.v4.jsonl.zstd"))
    档s.sort(key=os.path.getsize, reverse=True)
    事 = []          # 按时间排好的一件事一件事
    会话数 = 0
    for p in 档s:
        会话id = os.path.basename(os.path.dirname(p))
        工作区 = os.path.basename(os.path.dirname(os.path.dirname(p)))
        会话数 += 1
        for o in 读存档(p):
            t = o.get("type") or "?"
            dd = o.get("data") or {}
            ts = o.get("time") or dd.get("time") or 0
            if not ts:
                continue
            if t == "user/message" and 是他敲的(dd):
                文 = 取文(dd)
                if 文:
                    事.append({"时": ts, "谁": "他", "文": 文, "会": 会话id[:8], "工": 工作区})
            elif t == "user/message" and 是机器塞的(dd):
                文 = 取文(dd)
                # 「继续」这类自动续跑只留一行，不占地方
                if 文:
                    事.append({"时": ts, "谁": "自动", "文": 文, "会": 会话id[:8], "工": 工作区})
            elif t in ("tool/call", "tool_call"):
                名 = 是工具(dd)
                if 名:
                    事.append({"时": ts, "谁": "工具", "文": 名, "会": 会话id[:8], "工": 工作区})
            elif t == "assistant/message":
                # 他关心的是「我说了什么」，不是「我思考了什么」—— 只取正文，不取 reasoning
                #
                # ★★ 2026-10-16 04:0x 修：这里原来判的是 b.get("kind") == "text"，
                #    实测存档里内容块的键是 **`type`**，不是 `kind` ——
                #    {"type": "reasoning", "text": ...} / {"type": "text", "text": ...}
                #    / {"type": "tool-call", "id", "name", "arguments"}
                #    所以「我回的」一条都抽不到（193 个会话、10,990 条 assistant/message → 0 条）。
                #    判据：`python _归档会话.py --看` 里「我 N」那一位，之前恒等于 0。
                #    `kind` 留着当兜底，两条形状都认。
                m = dd.get("message") if isinstance(dd.get("message"), dict) else None
                c = m.get("content") if m else dd.get("content")
                文 = ""
                if isinstance(c, list):
                    for b in c:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "text" or b.get("kind") == "text":
                            文 += (b.get("text") or "")
                文 = 文.strip()
                if 文:
                    事.append({"时": ts, "谁": "我", "文": 文, "会": 会话id[:8], "工": 工作区})

    # 去重（同一条在同一毫秒可能被记两次）
    见 = set()
    净 = []
    for x in 事:
        k = (x["时"], x["谁"], x["文"][:80])
        if k in 见:
            continue
        见.add(k)
        净.append(x)
    净.sort(key=lambda z: z["时"])
    return 净, 会话数


def 哪一天(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts / 1000))


def 几点(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts / 1000))


# ══════════════════════════════════════════════════════════════════
# 写一天
# ══════════════════════════════════════════════════════════════════
def 写一天(天, 条s):
    行 = []
    行.append(f"# {天}　他和我说的每一句话\n")
    行.append(f"> 这一天 DSH 里一共 {len(条s)} 条记录。"
               f"他亲手敲的 {sum(1 for x in 条s if x['谁'] == '他')} 条，"
               f"我回的 {sum(1 for x in 条s if x['谁'] == '我')} 条，"
               f"工具 {sum(1 for x in 条s if x['谁'] == '工具')} 次。\n")
    行.append("> **`他`那一行是他一个字一个字敲进来的原话，一个字都没改。**\n")
    行.append("\n---\n")

    前一秒 = None
    for x in 条s:
        t = 几点(x["时"])
        谁 = x["谁"]
        文 = x["文"].strip()
        if 谁 == "他":
            行.append(f"\n### 【{t}】他说\n")
            for 段 in 文.split("\n"):
                段 = 段.rstrip()
                行.append(("> " + 段) if 段 else ">")
            行.append("")
        elif 谁 == "我":
            行.append(f"\n**【{t}】我回**\n")
            # 我的回复常常很长，归档里只留前 40 行（要全文去 DSH 里翻）
            段s = 文.split("\n")
            截 = 段s[:40]
            行.append("\n".join(截))
            if len(段s) > 40:
                行.append(f"\n*（还有 {len(段s) - 40} 行，略）*")
            行.append("")
        elif 谁 == "工具":
            行.append(f"- `{t}` {文}")
        else:
            行.append(f"- `{t}` *（机器自动塞的）* {文[:120]}")
        前一秒 = t

    os.makedirs(出口目录, exist_ok=True)
    路 = os.path.join(出口目录, f"{天}.md")
    with io.open(路, "w", encoding="utf-8") as f:
        f.write("\n".join(行))
    return 路


def 主():
    argv = sys.argv[1:]
    净, 会话数 = 扫()
    if not 净:
        print("  ✗ 一条都没抽到 —— 先确认 DSH 会话存档在不在")
        return

    按天 = collections.OrderedDict()
    for x in 净:
        按天.setdefault(哪一天(x["时"]), []).append(x)

    fmt = lambda t: time.strftime("%m-%d %H:%M", time.localtime(t / 1000))
    print(f"  会话存档：{会话数} 个")
    print(f"  记录总数：{len(净):,} 条（他 {sum(1 for x in 净 if x['谁'] == '他'):,} / "
          f"我 {sum(1 for x in 净 if x['谁'] == '我'):,} / 工具 {sum(1 for x in 净 if x['谁'] == '工具'):,}）")
    print(f"  时间跨度：{fmt(净[0]['时'])} → {fmt(净[-1]['时'])}")
    print(f"  天数：{len(按天)} 天")

    if "--看" in argv:
        for 天, 条s in 按天.items():
            print(f"    {天}  {len(条s):5d} 条")
        return

    只 = None
    if "--天" in argv:
        i = argv.index("--天")
        只 = argv[i + 1] if i + 1 < len(argv) else None

    os.makedirs(出口目录, exist_ok=True)
    写了 = []
    for 天, 条s in 按天.items():
        if 只 and 天 != 只:
            continue
        写了.append((天, len(条s), 写一天(天, 条s)))

    # 索引
    索 = ["# 会话存档　索引\n",
          f"> 这份目录是 `_归档会话.py` 生成的。**每天一份，一份里就是那一天的来龙去脉。**\n",
          f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}　"
          f"共 {len(按天)} 天 / {len(净):,} 条记录 / {会话数} 个会话存档\n",
          "\n| 天 | 记录 | 他说的 | 我回的 | 工具 | 文件 |",
          "|---|---|---|---|---|---|"]
    for 天, 条s in 按天.items():
        一 = os.path.join(出口目录, f"{天}.md")
        索.append(f"| {天} | {len(条s)} | "
                  f"{sum(1 for x in 条s if x['谁'] == '他')} | "
                  f"{sum(1 for x in 条s if x['谁'] == '我')} | "
                  f"{sum(1 for x in 条s if x['谁'] == '工具')} | "
                  f"[{天}.md]({天}.md) |")
    索.append("\n---\n")
    索.append("**怎么看**：在 DSH 侧边栏的「全局搜索」里搜一个词，或者直接打开某一天的 .md。")
    索.append("**怎么重跑**：`python _归档会话.py`　（只看统计加 `--看`）")
    索.append("**谁在跑它**：`dsh-yingjiang-panel` 插件每天随 DSH 起来时跑一次 —— "
              "不占开机启动、不占计划任务（用户 2026-10-16 02:0x 立的规矩）。")
    with io.open(os.path.join(出口目录, "索引.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(索))

    print(f"\n  ✅ 写了 {len(写了)} 天到 {出口目录}")
    总 = sum(os.path.getsize(p) for _, _, p in 写了) + os.path.getsize(os.path.join(出口目录, "索引.md"))
    print(f"     合计 {总:,} B")
    for 天, n, p in 写了[-6:]:
        print(f"     {天}  {n:5d} 条  {os.path.getsize(p):>8,} B  {os.path.basename(p)}")


if __name__ == "__main__":
    主()
