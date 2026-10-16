# -*- coding: utf-8 -*-
"""开工自查 —— 每次会话第一件事跑这个。只读，不改任何东西。

## 为什么要有这个文件

2026-10-15 凌晨，用户问了一句很要命的话：

    我怎么知道你以后还记不记得这个事儿呢？……你没有形成一个真正的系统，
    或者是一个很好的方案来记住之前犯过的错、出现的问题以及获得的一些收获。

查下来病因是**文件放错了层**：

    AGENTS.md    85 行    DSH 每次会话【自动注入】到眼前
    接续.md     436 行    【不会】自动出现，靠我主动去读   ← 规矩全在这，所以失效

`接续.md:275` 记着用户 10-14 01:39 作废「学设计不抄代码」那条规矩，
写得一字不差 —— 而当晚我还是犯了同形状的错。**文件存在、内容正确、就是没在我眼前。**

## 这个脚本解决什么

把一个**指针**换成一次**打印**。
指针我跳得过去（「等下再看」），打印出来的字就在眼前。

    python _开工.py            # 全打
    python _开工.py --短        # 只打欠账和最近教训

输出四段：
    【一】欠你的账 —— `要求台账.md` 里状态不是 ✅ 的条目
    【二】最近教训 —— `影匠\\知识\\*复盘*.md` 和 `教训.md` 的标题
    【三】当前在做 —— `接续.md` §零
    【四】硬要求 —— `AGENTS.md` 第三节的原文
"""
import argparse
import io
import os
import re
import sys

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根


def 读(名) -> str:
    p = os.path.join(根, 名)
    if not os.path.isfile(p):
        return ""
    return io.open(p, encoding="utf-8", errors="replace").read()


def 欠账():
    """从 `要求台账.md` 抠出所有状态列不是 ✅ 的行。

    ★ 只扫「## 一、」往后的正文，**跳过 §〇 的汇总表** ——
    那张表是同一批条目的复述，扫进去会重复计数（第一次就多算了 14 条）。
    """
    文 = 读("要求台账.md")
    if not 文:
        return None, []
    m = re.search(r"^##\s*一、.*$", 文, re.M)
    正文 = 文[m.start():] if m else 文
    欠 = []
    for 行 in 正文.split("\n"):
        if not 行.startswith("|"):
            continue
        if re.match(r"^\|[\s:\-|]+\|$", 行):      # 分隔行
            continue
        格 = [c.strip() for c in 行.strip("|").split("|")]
        if len(格) < 4:
            continue
        if 格[0] in ("日期", "时间", "编号", "#"):
            continue
        # 状态是「含状态符号的那一格」—— 不按下标猜，表格列数会变
        态 = next((c for c in 格 if re.search(r"[✅🟡✗⛔]", c)), "")
        if not 态:
            continue
        if "✅" in 态 and not re.search(r"[🟡✗⛔]", 态):
            continue
        if "已废" in 态 or "作废" in 态:
            continue
        欠.append([格[0], 格[1], 态, 格[-1] if len(格) > 3 else ""])
    return 文, 欠


def 教训():
    """扫知识目录里所有「复盘 / 教训 / 病根」类文件的二级标题。"""
    出 = []
    目 = os.path.join(根, "影匠", "知识")
    if not os.path.isdir(目):
        return 出
    for f in sorted(os.listdir(目)):
        if not f.endswith(".md"):
            continue
        if not re.search(r"复盘|教训|病根|病|错误|坑", f):
            continue
        文 = io.open(os.path.join(目, f), encoding="utf-8", errors="replace").read()
        条 = re.findall(r"^##\s+(.+)$", 文, re.M)
        出.append((f, 条[:6]))
    return 出


def 在做():
    文 = 读("接续.md")
    m = re.search(r"^##\s*零[^\n]*\n(.*?)(?=^##\s|\Z)", 文, re.M | re.S)
    if not m:
        return []
    行s = [l.strip() for l in m.group(1).split("\n")]
    return [l for l in 行s if l and not l.startswith(">")][:22]


def 硬要求():
    文 = 读("AGENTS.md")
    m = re.search(r"^##\s*[三3][^\n]*硬规矩[^\n]*\n(.*?)(?=^##\s|\Z)", 文, re.M | re.S)
    if not m:
        return []
    return [l.rstrip() for l in m.group(1).split("\n") if l.strip()][:40]


def 空转():
    """上一个会话里，我的思考有多少是废话。

    ★ 为什么放在【零】—— 用户 2026-10-15 说过三次，我三次都「知道了」然后照旧：
        10-14 02:19 「思考里刷空转」
        10-15 01:20 「你的思考怎么还在空转」
        10-15 01:50 「我不想再说下一次了」
      承诺不产生数字，所以承诺不管用。这个数字每轮开工出现在第一行。
      判据在 `_空转账.py`：<=14 字的句子、每个词都是「催促词」= 一次空转。
    """
    try:
        import glob
        import zstandard as zstd
        from datetime import datetime, timezone, timedelta
    except ImportError:
        return None, "（这台机器没有 zstandard，量不了）"
    d = r"D:\DSH\home\sessions\--D-DSHworkspace--"
    场 = sorted(glob.glob(os.path.join(d, "*", "session.v4.jsonl.zstd")),
                key=os.path.getmtime, reverse=True)
    if not 场:
        return None, "（找不到会话存档）"
    北京 = timezone(timedelta(hours=8))
    out = []
    for p in 场[:3]:
        try:
            with open(p, "rb") as f:
                文 = zstd.ZstdDecompressor().stream_reader(f).read().decode("utf-8", "replace")
        except Exception:
            continue
        import json as _j
        段 = 坏 = 0
        for 行 in 文.splitlines():
            if '"reasoning"' not in 行:
                continue
            try:
                j = _j.loads(行)
            except Exception:
                continue
            msg = ((j.get("data") or {}).get("message") or {})
            for c in (msg.get("content") or []):
                if not isinstance(c, dict) or c.get("type") != "reasoning":
                    continue
                t = c.get("text") or ""
                if not t:
                    continue
                段 += 1
                for s in re.split(r"[\n。！？!?；;]+", t):
                    干 = re.sub(r"[.。，,！!？?：:；;、…~～\-—\s]+", " ", s).strip().lower()
                    if 干 and len(干) <= 14:
                        词 = 干.split()
                        if 词 and all(w in _催促 for w in 词):
                            坏 += 1
        if 段:
            t = datetime.fromtimestamp(os.path.getmtime(p), 北京).strftime("%m-%d %H:%M")
            out.append((t, 段, 坏))
    if not out:
        return None, "（读不出推理）"
    t, 段, 坏 = out[0]
    return (t, 段, 坏), None


_催促 = {
    "emit", "go", "write", "writing", "ok", "okay", "enough", "now", "hmm", "wait",
    "actually", "let", "me", "here", "nope", "yes", "good", "right", "so", "and",
    "but", "first", "next", "then", "done", "alright", "fine", "sure", "just",
    "嗯", "好", "行", "开始", "写", "做", "走", "来", "继续", "那么", "现在",
}


def 动记忆():
    """距上次动记忆多久了 —— `AGENTS.md` 第 0.7 条立的判据。

    用户 2026-10-15 原话：
        「你要定时整理你的记忆……你自己考虑一下以一种什么样的频次，
          然后想办法把这个东西给固定下来。每一次完成大的任务之后都得去做。
          **而且你得确保自己做了这个事儿。**」

    最后一句是关键：靠「我会记得」是不行的，得有个数每轮开工顶在眼前。
    判据：`记忆\\经验\\`、`记忆\\心得\\`、`记忆\\索引.md` 三处里最新的一次修改。
    达标线 24 小时。
    """
    from datetime import datetime, timedelta, timezone
    北京 = timezone(timedelta(hours=8))
    目s = [os.path.join(根, "记忆", "经验"), os.path.join(根, "记忆", "心得")]
    最新, 哪 = 0.0, ""
    for d in 目s:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".md"):
                continue
            t = os.path.getmtime(os.path.join(d, f))
            if t > 最新:
                最新, 哪 = t, f"记忆\\{os.path.basename(d)}\\{f}"
    p = os.path.join(根, "记忆", "索引.md")
    if os.path.isfile(p) and os.path.getmtime(p) > 最新:
        最新, 哪 = os.path.getmtime(p), "记忆\\索引.md"

    # 经验文件里一共几条
    条 = 0
    d = os.path.join(根, "记忆", "经验")
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.endswith(".md"):
                条 += len(re.findall(r"^-\s", io.open(os.path.join(d, f),
                                                    encoding="utf-8", errors="replace").read(), re.M))
    if not 最新:
        return None, 条, "（`记忆\\经验\\` 还是空的）"
    小 = (datetime.now(北京).timestamp() - 最新) / 3600.0
    return 小, 条, f"{哪}（{datetime.fromtimestamp(最新, 北京).strftime('%m-%d %H:%M')}）"


def 复发(根):
    """把 `_找复发.py` 数出来的「犯过两次以上的病」打在最上面。

    这个函数**故意只读数、不重新扫**：`_找复发.py` 是全量扫（72 条经验），
    开工自查要快。所以流程是「开工时读上次的结果，开工后有空就重扫一遍」。

    用户 2026-10-15 02:06 原话：「**记住你前面出现过的所有问题，我不想再看见了。**」
    """
    路 = os.path.join(根, "记忆", "模式.md")
    if not os.path.isfile(路):
        print("    ✗ `记忆\\模式.md` 还没有 —— 先跑一次 `python _找复发.py`")
        return
    import io
    import re as _re
    import time as _time
    文 = io.open(路, encoding="utf-8").read()
    行们 = [l for l in 文.splitlines() if l.startswith("## ")]
    m = _re.search(r"^##\s+(.+?)　（(\d+) 次）", 文, _re.M)
    龄 = (_time.time() - os.path.getmtime(路)) / 3600
    脏 = []
    for l in 行们:
        mm = _re.search(r"^##\s+(.+?)　（(\d+) 次）", l)
        if mm and int(mm.group(2)) >= 3:
            脏.append((mm.group(1), int(mm.group(2))))
    print(f"    共 {len(行们)} 类复发，其中 {len(脏)} 类已经犯到 3 次以上（{龄:.1f} 小时前数的）")
    if 龄 > 24:
        print("    ⚠ 这份数超过一天没重扫了，跑一下 `python _找复发.py`")
    for 名, 次 in 脏[:5]:
        print(f"      ★ {名}　—— {次} 次")
    if len(脏) > 5:
        print(f"      …… 还有 {len(脏) - 5} 类，全在 `记忆\\模式.md`")
    print("    ★ **这一轮开始动手之前，先看一眼上面这几种是不是又要犯。**")


def 接管单(根):
    """他在影匠控制台上按「交给 agent」写下的那几件（`_等Agent.md`）。

    用户 2026-10-15 任务单 ⑤：「能调 ComfyUI 官方 API，**也能让 agent 接管**」。
    软件本身不给 agent 开后门 —— 它只负责把话说到纸上，我下次开工看到。

    ★ 为什么要专门写一个函数去打它，而不是让它躺在磁盘上：
      **一份没人念的单子等于没写。** 他按按钮的时候是有期待的，
      如果那份期待要等到我自己想起来去翻文件才被看到，那他又白按了。
    """
    import io
    import os.path
    路 = os.path.join(根, "_等Agent.md")
    if not os.path.isfile(路):
        print("    ✓ 他在控制台上没有交给我接的事")
        return
    件 = []
    for 线 in io.open(路, encoding="utf-8").read().splitlines():
        线 = 线.strip()
        if not 线.startswith("|"):
            continue
        格 = [x.strip() for x in 线.strip("|").split("|")]
        if len(格) >= 5 and 格[0] != "什么时候" and set(格[0]) != {"-"}:
            件.append(格)
    if not 件:
        print("    ✓ 他在控制台上没有交给我接的事")
        return
    等 = [x for x in 件 if x[4].startswith("⬜")]
    print(f"    他按了 {len(件)} 件，其中 {len(等)} 件我还没接：")
    for x in 件:
        print(f"      {x[4]}　{x[0]}　{x[1]}")
        if x[3] and x[3] not in ("—", "-"):
            print(f"            要我做：{x[3]}")
    if 等:
        print("    ★ 接完一件就把 `_等Agent.md` 里那行的 ⬜ 改成 ✅（改完要能指到磁盘路径）")


def 点头(根):
    """等你点头的事有幾件 —— 台账 #13 / #14 要的那个「固定动作」。

    用户把同一句话说了四遍，四遍都没成为动作：

        10-13 00:54  「正式生成前必须把内容给我审核」
        10-13 01:02  「先审核再生成」
        10-13 18:47  「必要时先给他看」
        台账 #13/#14  两条一直挂着 🟡「没形成固定动作」

    **说了四遍还是没成为动作，说明缺的不是记性，是位置。**
    所以给它在开工自查里一个固定位置 —— 这个函数。
    """
    路 = os.path.join(根, "_待你点头.md")
    if not os.path.isfile(路):
        print("    ✗ `_待你点头.md` 还没有 —— 跑 `python _候你点头.py --加 \"事\" \"花多少\" \"为什么\"`")
        return
    import io
    import re as _re
    等 = []
    for 线 in io.open(路, encoding="utf-8").read().splitlines():
        m = _re.match(r"\|\s*(\d+)\s*\|(.+)\|\s*$", 线)
        if not m:
            continue
        格 = [x.strip() for x in m.group(2).split("|")]
        if len(格) >= 5 and 格[4].startswith("⬜"):
            等.append((int(m.group(1)), 格[0], 格[1], 格[3]))
    if not 等:
        print("    ✓ 没有欠着的点头")
        return
    print(f"    **欠你 {len(等)} 个点头** —— 这几件我不动手，等你开口：")
    for 号, 事, 花, 从 in 等:
        print(f"      [{号}] {事}")
        print(f"           要花：{花}　（从 {从} 起等）")
    print("    ★ **这一轮如果要碰上面任何一件 —— 停手，先问。**")
    print("      自己觉得「这事很小不用问」就是又犯了（`_找复发.py` 词表里有这一类）。")


def 原话账():
    """他的原话存档还新不新、覆盖到哪儿 —— 台账 #6 要的那件事。

    用户 2026-10-15 原话（台账 #6）：
        「**记忆系统搞好，把我给你说的每个指令都记一下**」
    10-14 13:12 又说过：
        「我感觉你的记忆系统是不是有问题，优化下，怎么经常以前做过的任务，
          安排过的事要给忘了」

    `_用户原话.py` 抽的就是他本人敲的每一句（判据 `kind=='user'` 且 `source.rpcId` 存在）。
    可它**不会自己跑** —— 跑完一次是几点，记忆台看到的就停在几点。
    所以这里每轮开工打一个数：**距上次刷新几小时**。
    达标线 2 小时（他醒着的时候，说的话不该在半天里看不见）。
    """
    import json
    from datetime import datetime, timedelta, timezone
    北京 = timezone(timedelta(hours=8))
    p = os.path.join(根, "_用户原话.json")
    if not os.path.isfile(p):
        print("    ✗ 还没有 `_用户原话.json` —— 先跑 `python _用户原话.py`")
        return
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        print(f"    ✗ 读不了 `_用户原话.json`：{e}")
        return
    改 = os.path.getmtime(p)
    小 = (datetime.now(北京).timestamp() - 改) / 3600
    fmt = lambda t: datetime.fromtimestamp(t / 1000, 北京).strftime("%m-%d %H:%M")
    末 = fmt(d[-1]["时"]) if d else "—"
    首 = fmt(d[0]["时"]) if d else "—"
    字 = sum(len(x["话"]) for x in d)
    print(f"    他本人敲过的：{len(d)} 条　{首} → {末}　合计 {字:,} 字")
    print(f"    上次刷新：{小:.1f} 小时前")
    if 小 < 2:
        print("    ✓ 达标（2 小时内刷过）")
        return
    print(f"    ✗ 超了（>2 小时）。记忆台看的就是这个文件，**它现在停在第 {末}**。")
    print("      这一轮开工前先跑：`python _用户原话.py`")
    if 小 > 12:
        print("      ★ 超过 12 小时了 —— 他的新指令一条都没进记忆台。先刷它，再干别的。")


def 压缩段位():
    """当前上下文到哪一档了 —— `AGENTS.md` 第 0.9 条 / 用户 m20016 立的判据。

    用户 2026-10-15 原话：
        「你得保证你自己的压缩也能起到这个压缩的效果，你不能你的效果还比 DSH 自带的
          还差了。你要影响之后的绘画就不行了。」

    DSH 自带的压缩一动手，**原文就被替换掉了、取不回来**；我的压缩（ACP）能 decompress
    还原。所以正确答案不是「比谁压得好」，是**别让自带的那套有机会动手**。

    判据从哪来：会话存档里每条 assistant/message 都带 `usage`，
    `inputTokens + cacheReadTokens` ≈ 这一轮喂进去的全部上下文。
    曲线掉下来就是发生过一次压缩。实测本场掉过 105 次，典型位置 110K~230K。
    ★ 这一段不用我记，也不用我上报 —— 数字是 DSH 自己记的。
    """
    try:
        sys.path.insert(0, 根)
        import _压缩台账 as 台
    except Exception as e:
        return "?", f"（读不了 `_压缩台账.py`：{e}）"
    try:
        信 = 台.当前段位()
        if not 信:
            return "?", "（读不到当前段位）"
        级, 话 = 台.段位话(信)
        # ★ 顺手把台账增量化一次 —— 回答用户 m20016 的第二件事「压缩台账：每次压缩记档
        #   并接入记忆台搜索」。病根：台账原先只有 `python _压缩台账.py --扫` 手动跑，
        #   于是「每次压缩记档」实际是「我想起来的时候才记档」，最新一条停在 02:21。
        #   放在这里是因为开工必经，而 `写台账()` 自己按 (场, seq) 去重、只追加，增量很便宜。
        try:
            新 = 台.写台账()
            共 = len(台.看台账(10 ** 9))
            话 += f"\n       压缩台账：这次新增 {len(新)} 行，共 {共} 行"
        except Exception as e:
            话 += f"\n       压缩台账：记档失败（{e}）"
        return 级, 话
    except Exception as e:
        return "?", f"（读存档出错：{e}）"


def 问知识(词):
    """「动手前先查知识库」的落地 —— `AGENTS.md` 第 0.10 条。

    用户 2026-10-15 问了三次：「你怎么保证以后你做一个任务的时候，不是看着任务就开始
    动手就做了，而是去先去自己的知识库也好，而是自己的技能区也好，去查询……」
    「你积累的知识经验不在以后加以运用，就是白干。」

    病根：知识躺在 156 份文件里，而我开工时看不见它们。`AGENTS.md` 第四节只列了 7 份。
    修法：`_知识索引.py` 给每份抽关键词，这里按词检索。
    """
    try:
        sys.path.insert(0, 根)
        import _知识索引 as 索
    except Exception as e:
        print(f"    ✗ 读不了 `_知识索引.py`：{e}")
        return
    出 = 索.查(词, 8)
    if 出 is None:
        print("    ✗ 还没建索引，跑 `python _知识索引.py --建`")
        return
    if not 出:
        print(f"    （「{词}」在 {索.载()['份数']} 份知识里没命中 —— 要么真没有，要么换个词）")
        return
    print(f"    「{词}」该先看这 {len(出)} 份：")
    for 分, it, 由 in 出:
        print(f"      [{分:>3}] {it['相对']}    {it['标题'][:40]}")
    print(f"    ★ 看完再动手。说「查过」时要能指到上面这几行。")


def main():
    参 = argparse.ArgumentParser()
    参.add_argument("--短", action="store_true")
    参.add_argument("--问", default="", help="这个任务该先看哪几份知识")
    参 = 参.parse_args()

    if 参.问:
        print(f"【问知识】{参.问}")
        问知识(参.问)
        return 0

    print("=" * 74)
    print("  开工自查 —— 读 `AGENTS.md` 是自动的，读这个要你亲手敲一下")
    print("=" * 74)

    print("\n【零】我的思考空转（上一场的实数）")
    数, 错 = 空转()
    if 错:
        print("    " + 错)
    else:
        t, 段, 坏 = 数
        每 = 坏 / max(1, 段)
        print(f"    {t} 那场：推理 {段:,} 段，空转 {坏:,} 次，平均每段 {每:.1f} 次")
        if 每 <= 0.5:
            print("    ✓ 达标（目标每段 0.5 次以下）")
        else:
            print(f"    ✗ 没达标。**这一轮不许再出现 `Go.` `Emit.` `Write.` 这类只有催促、没有内容的句子。**")
            print( "      做法：决定好下一步就**直接调工具**，不要为了预热开一个思考块。")

    print("\n【零点五】动记忆的时效（`AGENTS.md` 第 0.7 条）")
    小, 条, 哪 = 动记忆()
    if 小 is None:
        print("    " + 哪)
    else:
        print(f"    距上次动记忆 {小:.1f} 小时 —— {哪}，经验共 {条} 条")
        if 小 < 24:
            print("    ✓ 达标（24 小时内动过）")
        else:
            print(f"    ✗ 超了 {小:.0f} 小时。**这一轮开工前先干这两件事：**")
            print( "      ① 把上一轮任务的心得追加进 `记忆\\经验\\<主题>.md`")
            print( "      ② 跑 `python _整理记忆.py --写索引`")

    文, 欠 = 欠账()

    # ★ 这一节是用户 2026-10-15 02:06「记住你前面出现过的所有问题，我不想再看见了」要的那道闸。
    #   `AGENTS.md` 第 0.7 条写了「出现 ≥2 次的升级成模式写进 记忆\模式.md」，
    #   但一直没落地 —— `_找复发.py` 就是它。数不出来才算合格。
    print("\n【零点八】犯过两次以上的病（`AGENTS.md` 第 0.7 条 / 用户 02:06「我不想再看见了」）")
    复发(根)

    print("\n【零点七】他的原话存档（台账 #6「把我给你说的每个指令都记一下」）")
    原话账()

    # 台账 #13/#14：「正式生成前必须把内容给我审核」/「提示词先给我看」/「必要时先给他看」
    # —— 同一句话说四遍，四遍都没成为动作。缺的不是记性，是位置。
    print("\n【零点六五】等你点头的事（台账 #13/#14）")
    点头(根)

    # ★ 用户 2026-10-15 任务单 ⑤「…也能让 agent 接管」，他按一下写在影匠控制台上。
    #   为什么放在开工自查里：那份单子躺在磁盘上没人看就等于没写。
    #   这是**唯一一条从「他按的按钮」通到「我这轮开工」的路**。
    print("\n【零点六二】他在控制台上交给我接的（任务单 ⑤）")
    接管单(根)

    print("\n【零点六】上下文段位（`AGENTS.md` 第 0.9 条 / 用户 m20016 要的「压缩红线」）")
    级, 话 = 压缩段位()
    print(f"    {级} {话}")

    print("\n【一】欠你的账")
    if 文 == "":
        print("    ✗ 还没有 `要求台账.md` —— 说明这份账还没建起来")
    else:
        if not 欠:
            print("    ✓ 台账里没有未结的条目")
        else:
            print(f"    共 {len(欠)} 条状态不是 ✅：")
            for 格 in 欠[:60]:
                print("      · " + "  |  ".join(格[:4]))
            if len(欠) > 60:
                print(f"      … 还有 {len(欠)-60} 条")

    if not 参.短:
        print("\n【二】踩过的坑（每个文件的二级标题）")
        for f, 条 in 教训():
            print(f"    ── {f}")
            for t in 条:
                print(f"        · {t}")

    print("\n【三】当前在做（`接续.md` §零）")
    for l in 在做():
        print("    " + l)

    if not 参.短:
        print("\n【四】硬规矩（`AGENTS.md` 原文）")
        for l in 硬要求():
            print("    " + l)

    print("\n" + "=" * 74)
    print("  ★ 汇报第一行必须写：我加的条件：___（没有就写「无」）")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
