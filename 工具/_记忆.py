# -*- coding: utf-8 -*-
"""把「用户到底说过什么」从会话存档里全部挖出来，落成可 grep 的纯文本。

## 为什么有这个东西

用户 2026-10-14 原话：

> 你的记忆到底到多久？ 为什么我之前让你给我全部寄的时候，你只给到今天下午的，
> 或者今天早上的，昨天晚上的呢？你先想办法把你的全部记忆系统给搞好。
> 把我给你说的每个指令都给记一下，然后以及你的回答。我发现你根本就记不住我
> 之前告诉你的很多的事情。这个搞不好的话，之后再有什么经验，再有什么踩坑，
> 再有什么要求，过了就是过了，还是给我忘了，那么每一次都是重新来。

**他说到根子上了。** 排查结果（2026-10-14 23:55）：

| 存哪 | 有多少 | 我实际用过吗 |
|---|---|---|
| `.memsearch\\memory\\*.md` | **只有 3 天**（10-12 / 10-13 / 10-14） | 只读了「今天」那一份 |
| `D:\\DSH\\home\\sessions\\--D-DSHworkspace--\\` | **90 场会话**，10-12 02:28 起 | **一场都没读过** |
| `接续.md` | 一份 | 读过 |
| `影匠\\知识\\*.md` | 20 多份 | 读过一部分 |

**所以「记忆」实际上等于「当前窗口里还剩下的东西 + 我临时去翻的那几份」。**
窗口一滚，前面说过的话就真的没了 —— 而他以为我记着。

## 干什么

把 90 场会话存档全部解开，抽出每一条 **用户消息**（带时间、带是哪一场），
写成一天一个纯文本文件：

    D:\\DSHworkspace\\记忆\\指令\\YYYY-MM-DD.md

过滤掉三类不是人说的话：
- `<system-reminder>` 开头（队友/子代理的框架注入）
- `Current runtime context.` 开头（每轮自动附的运行时快照）
- 以 `This is an automatically generated checkpoint` 开头（上下文压缩留下的）

## 用法

    python _记忆.py                 # 全部重扫，写出所有日期的文件
    python _记忆.py --看 2026-10-13  # 只看某一天
    python _记忆.py --统计          # 只报数，不写文件
"""
import argparse
import collections
import glob
import io
import json
import os
import re
import sys
import time

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根
存档根 = r"D:\DSH\home\sessions"
出根 = os.path.join(根, "记忆", "指令")

不是人说的 = (
    "<system-reminder>",
    "Current runtime context.",
    "This is an automatically generated checkpoint",
    "<hindsight_knowledge_refresh>",
    "<hindsight_knowledge>",
    "[Compressed conversation section]",
    "Time sampled while preparing turn",
    "background job pwsh-",
    "Browser time zone for this request:",
    "Elapsed since the preceding",
    "The approval policy changed",
    "The permission mode changed",
    "The file policy changed",
    # ★ 2026-10-15：下面三类**不是用户说的**，是系统/我自己的话被塞进了用户位：
    #   ① goal_round —— 目标续跑时框架自动投的，一晚上十几次
    #   ② Agent xxx sent a … / Background subagent … —— 子代理完成通知
    #   ③ 「你在 Windows 上…」「You are …」「Reply with exactly」—— 我写给子代理的任务书
    "<goal_round>",
    "Agent ",
    "Background subagent",
    "你在 Windows 上",
    "你在 ",
    "You are ",
    "Reply with exactly",
    "你是本项目的",
)

# 通知/任务书还有别的开头，用正则兜一层
不是人说的正则 = (
    re.compile(r"^Agent [0-9a-f]{8}-"),
    re.compile(r"^Background subagent [0-9a-f]{8}-"),
    re.compile(r"^<goal_round>"),
    re.compile(r"^<goal>"),
    re.compile(r"sent a (message|note) to you"),
    re.compile(r"^(你已经|请以|请为|你的任务是)"),
)

# ★ 2026-10-15：同一场会话会被**重复存**（续接、分叉、增量落盘都会让同一段历史
#   出现在多个 .zstd 里）。第一版台账里「我现在想要进行手机连接」出现了 4 次。
#   去重判据：同一天 + 同一段正文 + 时间差在 120 秒以内 → 只留最早那条。
去重窗毫秒 = 120_000


def 去重(条s):
    """条s: [(t, 号, 文)] 或 [(t, 号, 角色, 文)]。按 (正文, 角色) 分组，保留最早的。"""
    出 = []
    见过 = {}
    for x in sorted(条s, key=lambda y: y[0]):
        t, 文 = x[0], x[-1]
        角 = x[2] if len(x) == 4 else "用户"
        键 = (角, 文)
        上 = 见过.get(键)
        if 上 is not None and abs(t - 上) <= 去重窗毫秒:
            continue
        见过[键] = t
        出.append(x)
    return 出


def 是自动尾巴(文):
    """框架加在用户话后面的括号说明（「继续」那条就是），只留人打的那部分。"""
    for 标 in ("\n\n(上一步工具", "\n(上一步工具"):
        if 标 in 文:
            return 文.split(标)[0].strip()
    return 文


def 存档们():
    """返回 [(会话号, 目录, 文件)]，按时间排。"""
    出 = []
    for 工作区 in glob.glob(os.path.join(存档根, "*")):
        if not os.path.isdir(工作区):
            continue
        for d in glob.glob(os.path.join(工作区, "*")):
            for f in glob.glob(os.path.join(d, "*.zstd")):
                出.append((os.path.basename(d), d, f, os.path.getmtime(f)))
    出.sort(key=lambda t: t[3])
    return 出


def 抠文本(条):
    """从一条消息里把**正文**拼出来。

    ★ 两种壳子（实测 2026-10-15，第一版只认了 user 那种，结果「我答的」一条没抽到）：
      · `user/message`      → `data.content`        是 `[{type:"text", text:...}]`
      · `assistant/message` → `data.message.content` 是 `[{type:"reasoning"|"text", ...}]`
    只收 `type == "text"`；`reasoning` 是思考过程，不是回答，**不要**。
    """
    if isinstance(条, str):
        return 条
    if not isinstance(条, dict):
        return ""
    # assistant 的壳：data.message.content
    m = 条.get("message")
    if isinstance(m, dict) and m.get("content") is not None:
        条 = m
    出 = []
    for c in 条.get("content") or []:
        if isinstance(c, dict):
            if c.get("type") == "text":
                出.append(c.get("text") or "")
        elif isinstance(c, str):
            出.append(c)
    return "\n".join(出).strip()


def 扫一场(路):
    """解一场会话，返回 [(毫秒时间, 角色, 文本)]。

    角色：
      "用户"     —— 用户本人说的话
      "答"       —— 我对这一轮的**最终**回答（turn/end 之前最后一条 assistant/message）
      "过程"     —— 中间步骤的文字（想做什么、看到什么）。默认不写进文件，
                    但记下来，因为「我到底干了什么」要能查。
    """
    import zstandard as z
    出 = []
    这轮答 = None          # 本轮的候选最终回答
    轮内 = False
    try:
        with open(路, "rb") as fh:
            r = z.ZstdDecompressor().stream_reader(fh)
            for ln in io.TextIOWrapper(r, encoding="utf-8", errors="replace"):
                if not any(k in ln for k in
                           ('"user/message"', '"assistant/message"',
                            '"turn/end"', '"turn/start"')):
                    continue
                try:
                    j = json.loads(ln)
                except Exception:
                    continue
                t = j.get("type")
                if t == "turn/start":
                    轮内, 这轮答 = True, None
                    continue
                if t == "turn/end":
                    # 本轮收尾：把攒下的最后一条正文当成「我的回答」
                    if 这轮答:
                        出.append((这轮答[0], "答", 这轮答[1]))
                    轮内, 这轮答 = False, None
                    continue
                if t == "assistant/message":
                    文 = 抠文本(j.get("data") or {})
                    if 文:
                        这轮答 = (j.get("time") or 0, 文)
                    continue
                if t != "user/message":
                    continue
                文 = 抠文本(j.get("data") or {})
                if not 文:
                    continue
                if any(文.startswith(p) or p in 文[:200] for p in 不是人说的):
                    continue
                if any(r.search(文) for r in 不是人说的正则):
                    continue
                文 = 是自动尾巴(文)
                if not 文 or len(文) < 2:
                    continue
                出.append((j.get("time") or 0, "用户", 文))
                # 新的一轮开始 —— 别让上一轮没 turn/end 的回答串进来
                这轮答 = None
    except Exception as e:
        print(f"      ! {os.path.basename(os.path.dirname(路))}: {type(e).__name__} {e}")
    return 出


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--统计", action="store_true", help="只报数，不写文件")
    ap.add_argument("--看", default="", help="只打印某一天")
    ap.add_argument("--限", type=int, default=0, help="每段截断到多少字（0=不截）")
    ap.add_argument("--台账", action="store_true",
                    help="另出一份 记忆\\要求台账.md：只留真正在提要求的那些话（去寒暄、去重）")
    ap.add_argument("--对话", action="store_true",
                    help="另出一份 记忆\\对话\\YYYY-MM-DD.md：**你问的 + 我答的**成对排在一起")
    ap.add_argument("--答限", type=int, default=2400,
                    help="--对话 里我的回答每条截到多少字（0=不截）")
    参 = ap.parse_args()

    存 = 存档们()
    print(f"  会话存档 {len(存)} 场")
    按天 = collections.defaultdict(list)          # 日 → [(t, 号, 文)]  只放用户说的
    对话 = collections.defaultdict(list)          # 日 → [(t, 号, 角色, 文)]  用户 + 我的回答
    场数 = collections.Counter()
    坏 = 0
    for i, (号, d, f, mt) in enumerate(存, 1):
        msgs = 扫一场(f)
        if not msgs:
            坏 += 1
        for t, 角色, 文 in msgs:
            if not t:
                continue
            日 = time.strftime("%Y-%m-%d", time.localtime(t / 1000))
            if 角色 == "用户":
                按天[日].append((t, 号, 文))
                场数[日] += 1
            对话[日].append((t, 号, 角色, 文))
        if i % 20 == 0:
            print(f"      … {i}/{len(存)}")

    print()
    print("  ── 去重前后（同一场会话被续接/分叉时会重复落盘）")
    for 日 in sorted(按天):
        原 = len(按天[日])
        按天[日] = 去重(按天[日])
        对话[日] = 去重(对话[日])
        print(f"      {日}   用户 {原:4d} → {len(按天[日]):4d} 条")

    print()
    print("  ── 每天有多少条用户消息 / 我回了几条")
    总 = 0
    答总 = 0
    for 日 in sorted(按天):
        n = len(按天[日])
        a = sum(1 for x in 对话[日] if x[2] == "答")
        总 += n
        答总 += a
        print(f"      {日}   用户 {n:4d} 条   我答 {a:4d} 条   来自 {len(set(x[1] for x in 按天[日]))} 场会话")
    print(f"      ────────────────────────────────────────")
    print(f"      合计   用户 {总:4d} 条   我答 {答总:4d} 条")
    if 坏:
        print(f"      （{坏} 场会话里一条用户消息都没抽到 —— 可能只是工具会话）")

    if 参.看:
        日 = 参.看
        print()
        print(f"  ══ {日} 的全部用户消息")
        for t, 号, 文 in sorted(按天.get(日, [])):
            时 = time.strftime("%H:%M:%S", time.localtime(t / 1000))
            print(f"\n  【{时}】({号[:8]})")
            for 行 in 文.splitlines():
                print(f"      {行}")
        return 0

    if 参.统计:
        return 0

    os.makedirs(出根, exist_ok=True)
    写 = 0
    for 日, 条s in sorted(按天.items()):
        路 = os.path.join(出根, f"{日}.md")
        条s.sort()
        o = [f"# {日} —— 用户说过的每一句话", "",
             f"> 这一天共 **{len(条s)}** 条用户消息，来自 {len(set(x[1] for x in 条s))} 场会话。",
             "> 由 `_记忆.py` 从 `D:\\DSH\\home\\sessions\\` 的会话存档里自动挖出，**不是摘要，是原文**。",
             "> 框架注入的 system-reminder / runtime context / 压缩检查点已经滤掉。", "", "---", ""]
        for t, 号, 文 in 条s:
            时 = time.strftime("%H:%M:%S", time.localtime(t / 1000))
            if 参.限:
                文 = 文[:参.限] + ("　…（截断）" if len(文) > 参.限 else "")
            o.append(f"## 【{时}】　{号[-8:]}")
            o.append("")
            o.append(文)
            o.append("")
            o.append("---")
            o.append("")
        io.open(路, "w", encoding="utf-8", newline="\n").write("\n".join(o))
        写 += 1
        print(f"      ✓ {路}　{os.path.getsize(路):,} 字节")
    print(f"\n  写好了 {写} 个文件 → {出根}")

    if 参.台账:
        写台账(按天)
    if 参.对话:
        写对话(对话, 参.答限)
    return 0


# ── 台账：只留真正在提要求的那些话 ──────────────────────────────
#
# 判据：太短的（「继续」「好」）不是要求；太长的如果是在转述工具输出也不是。
# 这条判据只是**筛**，不是**判** —— 筛错了的后果是漏掉一条要求，
# 所以宁可放松：留 12 字以上、且不像工具噪音的。

噪音 = ("finished [status:", "finished and will do no further work",
        "已被中断", "工具「", "job_output", "The following is a system",
        "Background subagent", "background job")


def 写台账(按天):
    路 = os.path.join(根, "记忆", "要求台账.md")
    条s = []
    for 日 in sorted(按天):
        for t, 号, 文 in 按天[日]:
            文 = 文.strip()
            if len(文) < 12:
                continue
            if any(n in 文[:120] for n in 噪音):
                continue
            条s.append((t, 号, 文))
    条s.sort()

    o = ["# 要求台账 —— 你说过的每一件要我做的事", "",
         "> 由 `_记忆.py --台账` 从 98 场会话存档里自动挖出。**原文，不是摘要。**",
         "> 判据只是「12 字以上、且不像工具噪音」—— 宁可多留，不敢漏。",
         f"> 共 **{len(条s)}** 条，跨 {len(set(x[0]//86400000 for x in 条s))} 天。",
         "",
         "## 怎么用这份东西",
         "",
         "**每次接手新活之前，先搜这里**：`grep -n 关键词 记忆\\要求台账.md`。",
         "你要的答案多半在里面 —— 而不是在我的印象里。",
         "",
         "---", ""]
    上日 = ""
    for t, 号, 文 in 条s:
        日 = time.strftime("%Y-%m-%d", time.localtime(t / 1000))
        时 = time.strftime("%H:%M:%S", time.localtime(t / 1000))
        if 日 != 上日:
            o += [f"# {日}", ""]
            上日 = 日
        o.append(f"## 【{时}】{号[-8:]}")
        o.append("")
        o.append(文)
        o.append("")
        o.append("---")
        o.append("")
    io.open(路, "w", encoding="utf-8", newline="\n").write("\n".join(o))
    print(f"  ✓ 台账 {路}　{len(条s)} 条　{os.path.getsize(路):,} 字节")


def 写对话(对话, 答限):
    """一天一份：**你问的** 和 **我答的** 成对排在一起，按时间。

    用户 2026-10-14 原话：「把我给你说的每个或，每个指令都给记一下。
    **然后以及你的回答。**」—— 只记他说过什么不够，还得记我当初怎么答的，
    否则没法核对「我到底有没有照他说的做」。

    ★ 这里只收「答」，不收中间过程。一轮里我可能想了十几步、调了几十个工具，
    那些不是「回答」；`turn/end` 之前最后一条正文才算。
    """
    出根2 = os.path.join(根, "记忆", "对话")
    os.makedirs(出根2, exist_ok=True)
    写 = 0
    for 日, 条s in sorted(对话.items()):
        条s = sorted(条s, key=lambda x: x[0])
        if not any(x[2] == "用户" for x in 条s):
            continue
        路 = os.path.join(出根2, f"{日}.md")
        n用 = sum(1 for x in 条s if x[2] == "用户")
        n答 = sum(1 for x in 条s if x[2] == "答")
        o = [f"# {日} —— 你问的，和我答的", "",
             f"> 你说 **{n用}** 条，我答 **{n答}** 条。原文，不是摘要，由 `_记忆.py --对话` 从会话存档挖出。",
             "> 只收「一轮的最终回答」；中间调工具的过程不收（要看那个去 `记忆\\指令\\` 和会话存档）。",
             "> 框架注入的 system-reminder / runtime context / 压缩检查点已滤掉。", "", "---", ""]
        for t, 号, 角色, 文 in 条s:
            if 角色 != "用户" and 角色 != "答":
                continue
            时 = time.strftime("%H:%M:%S", time.localtime(t / 1000))
            if 角色 == "答" and 答限 and len(文) > 答限:
                文 = 文[:答限] + f"\n\n　…（回答还有 {len(文)-答限} 字，看会话存档 {号[-8:]}）"
            标 = "你" if 角色 == "用户" else "我"
            o.append(f"## 【{时}】{标}　{号[-8:]}")
            o.append("")
            o.append(文)
            o.append("")
            o.append("---")
            o.append("")
        io.open(路, "w", encoding="utf-8", newline="\n").write("\n".join(o))
        写 += 1
        print(f"      ✓ 对话 {路}　{n用} 问 / {n答} 答　{os.path.getsize(路):,} 字节")
    print(f"\n  写好了 {写} 个对话文件 → {出根2}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(主())
