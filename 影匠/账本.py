# -*- coding: utf-8 -*-
"""
影匠 · 任务账本 —— 每一格图、每一段片，都得有一笔账
================================================================
零第三方依赖：只用 sqlite3 / json / os / time / hashlib（+ 少量标准库）。

一句话设计
----------
**本机只有一张 5080，一次只能跑一个活。所以「谁在跑、跑过几遍、花了多少、
有没有跑出个说不清的中间态」必须落盘记清楚 —— 进程被强杀也不许丢。**

本项目最重要的一条铁律
----------------------
    当一次外部调用「可能已经送达供应商、但结果或计费状态无法确认」时，
    绝不自动重试，必须停在「未知」态交给人工核对。

为什么？因为自动重试一笔「可能已经扣过钱」的调用，会在你毫不知情的情况下
再扣一次。宁可让流程停下来问你一句，也不许机器替你花第二次钱。

状态机（TERMINAL = 终态）
-------------------------
    排队 ──领取()──▶ 运行 ──完成()──▶ 完成   [终态]
      │               │
      │               ├──失败(明确失败)──▶ 失败 [终态，可 重试() 开新任务]
      │               │
      │               └──未知(说不清)────▶ 未知 [终态，可能已计费 → 禁止自动重试]
      │                                    │
      │                                    ├──对账(--结果 成了)──▶ 完成
      │                                    └──对账(--结果 没成)──▶ 失败 [清掉可能已计费 → 可 重试()]
      └──取消()──▶ 取消 [终态]

    「未知」是终态，正常迁移表不许它动。**对账() 是唯一的人工出口** ——
    它不是自动流程，是"人已经去供应商后台看过了"这件事的落账。

用法（库）
----------
    import 账本
    t = 账本.新建("出图", 戏名="凌霜单骑闯关", 格号="1", 估算成本=1)
    账本.领取(t)                       # 过闸门；满则抛 闸门满
    账本.开始(t, 供应商任务号="abc123")  # 记下供应商侧的单号（有就一定记！）
    try:
        ...
        账本.记完成(t, 输出路径=r"...\\01_格1.png", 实际成本=1)
    except 引擎.提交未知 as e:          # ← 「交出去了，然后跟丢了」= 钱可能已经花出去
        账本.未知因为(t, e)             # 一行记成「未知」态：提示号/可能已计费 自动带进去
    except Exception as e:
        v = 账本.分类异常(e)
        if v["可自动重试"]:
            账本.记失败(t, 错=e)
        else:
            账本.记未知(t, 因=e)          # ← 铁律：说不清就停在这儿

    # 之后（可能是第二天，可能是另一个人）：拿提示号去 ComfyUI 的 history 看一眼，
    # python 账本.py 对账 <id>                      ← 只会告诉你该去查什么，不动账
    # python 账本.py 对账 <id> --结果 成了 --产物 <路径>   ← 真跑出来了：结到「完成」
    # python 账本.py 对账 <id> --结果 没成                ← 真没跑成：结到「失败」，之后才允许 重试()

用法（命令行）
--------------
    python 账本.py 列表 [--状态 X] [--戏名 Y] [--类型 Z] [--限 N]
    python 账本.py 新建 --类型 出图 [--戏名 Y] [--镜头 A] [--格号 1] [--估算成本 1] [--输入摘要 "…"]
    python 账本.py 领取 <id>                          ← 过并发闸门：排队 → 运行
    python 账本.py 开始 <id> [--供应商任务号 X]        ← 不改状态，只登记对端单号
    python 账本.py 完成 <id> [--输出 路径] [--实际成本 1]
    python 账本.py 失败 <id> --错 "…" [--实际成本 0]
    python 账本.py 未知 <id> --因 "…" [--可能已计费] [--供应商任务号 X]
    python 账本.py 对账                             ← 列出所有「未知」账 + 逐条核对指引
    python 账本.py 对账 <id>                        ← 只打这一条的核对指引（不动账）
    python 账本.py 对账 <id> --结果 成了 --产物 路径   ← 人工核对完：结到「完成」
    python 账本.py 对账 <id> --结果 没成             ← 人工核对完：结到「失败」，此后才可 重试
    python 账本.py 待人工                            ← 只看「未知」账（= 列表 --状态 待人工）
    python 账本.py 重试 <id> [--强开]
    python 账本.py 未完成
    python 账本.py 统计
    python 账本.py 预估 <类型> <数量> [--模板 T] [--宽 W] [--高 H] [--帧数 F] [--步数 S]
    python 账本.py 闸门 [--上限 N]
    python 账本.py 恢复 <id> [--备注 "…"]
    python 账本.py 自查

    「领取」和「开始」是两件事，别混：
      领取 = 占坑（检查并发闸门、尝试次数 +1、记开始时间），会把账推进「运行」；
      开始 = 你已经在别处把活交出去了，回来补登一个供应商任务号，不动状态。
      所以「排队」的账只能 领取()，不能 开始()：绕过闸门会让本机同时跑好几条。

环境变量
--------
    影匠_账本      数据库路径，默认 <项目根>/作品/_账本/账本.db
    影匠_电价      元/度，默认 0.56（阶梯电价的粗估，见知识文档）
    影匠_整机瓦数  整机满载瓦数，默认 600
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time

# ── 控制台：Windows 默认 GBK，✓ ✗ ⚠ 会直接 UnicodeEncodeError。
for _流 in (sys.stdout, sys.stderr):
    try:
        _流.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

__all__ = [
    "排队", "运行", "完成", "失败", "未知", "取消",
    "终态", "全部状态",
    "账本错", "需人工核对", "闸门满", "状态非法", "找不到任务",
    "账本", "取账本",
    "新建", "开始", "记完成", "记失败", "记未知", "记取消",
    "重试", "恢复", "可重试", "未知因为", "对账",
    "未完成", "待人工", "取", "列表", "统计", "预估", "闸门", "置上限",
    "领取", "释放", "分类异常", "建议", "输入摘要", "自查",
    "提交后失联",
]

这里 = os.path.dirname(os.path.abspath(__file__))
作品根 = os.path.join(这里, "作品")
默认账本路 = os.path.join(作品根, "_账本", "账本.db")
电价 = float(os.environ.get("影匠_电价", "0.56"))
整机瓦数 = float(os.environ.get("影匠_整机瓦数", "600"))

# ───────────────────────────── 状态 ─────────────────────────────

排队 = "排队"
运行 = "运行"
完成 = "完成"
失败 = "失败"
未知 = "未知"          # = indeterminate：可能已送达/可能已计费，说不清
取消 = "取消"

全部状态 = (排队, 运行, 完成, 失败, 未知, 取消)
终态 = (完成, 失败, 未知, 取消)

_迁移表 = {
    排队: (运行, 取消, 未知, 失败),
    运行: (运行, 完成, 失败, 未知, 取消),
    完成: (),
    失败: (运行,),      # 恢复() 把它标回可继续（同一条任务接着跑）
    未知: (),           # ★ 铁律：未知态不接任何自动迁移，只能人工处理
    取消: (),
}

# 「状态不变、只补字段」的自我迁移（X → X）。写在这里而不是散落在各方法里，
# 是为了让 _换态() 只有一条判断路径。
# 目前只有 开始() 用它：活已经交出去了，回来补登一个供应商任务号，
# 状态该是「运行」还是「运行」—— 这不是状态变化，不该被状态机挡住。
# 终态（完成/失败/未知/取消）故意**不在**这里：终态就是不许再改。
for _自我态 in (排队, 运行):
    _迁移表[_自我态] = tuple(_迁移表[_自我态]) + (_自我态,)

# ── 成本预告用的本机基准（不是供应商报价！这是「本机跑一次大概多少积分」的
#    内部记账单位：1 积分 ≈ 一枚 5080 跑 1 张 8 步 1024² 图的电费与机时）
计价表 = {
    "出图":       {"单位": "张", "基准积分": 1,   "基准秒": 4.0,   "来源": "本机实测基线"},
    "出图四宫格": {"单位": "张", "基准积分": 1,   "基准秒": 4.0,   "来源": "本机实测基线"},
    "出片":       {"单位": "段", "基准积分": 60,  "基准秒": 260.0, "来源": "本机实测基线"},
    "配音":       {"单位": "句", "基准积分": 3,   "基准秒": 12.0,  "来源": "设计意图（未实测）"},
    "拼图":       {"单位": "张", "基准积分": 0.2, "基准秒": 2.0,   "来源": "设计意图（未实测）"},
    "其他":       {"单位": "次", "基准积分": 1,   "基准秒": 5.0,   "来源": "设计意图（未实测）"},
}


# ───────────────────────────── 异常 ─────────────────────────────


class 账本错(Exception):
    """账本自己的错。"""


class 状态非法(账本错):
    pass


class 找不到任务(账本错):
    pass


class 闸门满(账本错):
    """并发闸门满了 —— 任务留在「排队」，不是错误，是等待。"""


class 需人工核对(账本错):
    """★ 铁律的落点：这条任务可能已经送达供应商、可能已经计费，
    账本拒绝自动重试，必须人去供应商后台看一眼。

    异常消息里带【去哪查】【查什么】【查完怎么办】，照着做就行。
    """

    def __init__(self, 任务: dict, 供应商: str = "ComfyUI", 原因: str = ""):
        self.任务 = dict(任务 or {})
        self.供应商 = 供应商
        self.原文 = 原因
        t = self.任务
        行 = [
            "✗ 不能自动重试：这条任务处于「" + str(t.get("状态", "未知")) + "」态 —— 可能已经送达供应商，",
            "  可能已经计费。自动重试会在你不知情的情况下再花一次钱/再跑一遍。",
            "",
            f"  任务     {t.get('id', '?')}",
            f"  活       {t.get('类型', '?')}"
            + (f" · 《{t['戏名']}》" if t.get("戏名") else "")
            + (f" · 镜头 {t['镜头']}" if t.get("镜头") else "")
            + (f" · 格号 {t['格号']}" if t.get("格号") else ""),
            f"  可能已计费 {'是' if t.get('可能已计费') else '否'}"
            f"（不过「否」只是没证据，不代表没送达）",
        ]
        if t.get("供应商任务号"):
            行.append(f"  供应商任务号 {t['供应商任务号']}  ← 拿这个号去查最快")
        if t.get("输出路径"):
            行.append(f"  当时在写的输出 {t['输出路径']}  ← 先看这个文件在不在、能不能播")
        if t.get("错误"):
            行.append(f"  当时的原因 {str(t['错误'])[:200]}")
        if 原因:
            行.append(f"  现在想重试的理由 {原因}")
        行 += [
            "",
            f"  【去哪查】{供应商} 后台 / 队列 / 历史记录（本机 ComfyUI: http://127.0.0.1:8188 的 queue 与 history）",
            "  【查什么】这个任务到底跑没跑完、出没出片、算没算钱；有输出路径就直接看文件",
            "  【怎么办】没跑成 → python 账本.py 对账 <id> --结果 没成   （结到「失败」，之后才允许重试）",
            "           跑成了 → python 账本.py 对账 <id> --结果 成了 --产物 <路径>",
            "           拿不准 → python 账本.py 对账 <id>   （把这条该查什么再打一遍，不动账）",
            "           （老办法也留着：python 账本.py 恢复 <id> 直接标回「排队」重跑）",
        ]
        super().__init__("\n".join(行))


# ───────────────────────────── 小工具 ─────────────────────────────


def 输入摘要(东西) -> str:
    """把输入（字符串/字典/列表/工作流）压成一个短指纹。"""
    if isinstance(东西, (dict, list)):
        原 = json.dumps(东西, ensure_ascii=False, sort_keys=True)
    else:
        原 = "" if 东西 is None else str(东西)
    return hashlib.sha256(原.encode("utf-8")).hexdigest()[:16]


_警告: list[str] = []


def _记警告(文本: str) -> None:
    """开库期的警告（比如没抢到 WAL）。不抛异常，但会打出来让人看见。"""
    _警告.append(文本)
    print(f"⚠ {文本}", file=sys.stderr)


def _连(路: str) -> sqlite3.Connection:
    """开库并把它调成「摔不死」的配置。

    顺序有讲究，别乱动：
      1) busy_timeout 必须**最先**设。它管的是「库被别人占着时等一会儿再试」，
         而 journal_mode=WAL 恰恰需要一个短暂的独占窗口。以前先跑 WAL 再设
         busy_timeout，多个进程同时开工时 WAL 立刻抛 database is locked ——
         进程会死在 __init__ 里，连 self._库 都还没建好；更糟的是它当时还攥着
         .lck，别人要等 20 秒才报「账本被另一个进程锁着」，整条产线一起卡死。
      2) WAL 是「锦上添花」不是「必须」：抢不到就先按默认日志模式跑，
         库照样能用，绝不让它把开库搞崩。
      3) synchronous=FULL 是硬要求（强杀后靠它回滚半截事务），这个不能退让。
    """
    os.makedirs(os.path.dirname(os.path.abspath(路)) or ".", exist_ok=True)
    库 = sqlite3.connect(路, timeout=15, isolation_level=None)
    try:
        库.row_factory = sqlite3.Row
        库.execute("PRAGMA busy_timeout=15000")      # 先设这个，见上面第 1 条
        上次 = time.time()
        while True:
            try:
                库.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError:
                # 别的进程正拿着库（也可能正开着 WAL）。等一会儿再试；
                # 实在等不到就退一步：不用 WAL 也能跑，只是并发读差一点。
                if time.time() - 上次 > 10:
                    现在 = 库.execute("PRAGMA journal_mode").fetchone()[0]
                    _记警告(f"抢不到 WAL（现在是 {现在}），先这么跑：{路}")
                    break
                time.sleep(0.1)
        库.execute("PRAGMA synchronous=FULL")
    except Exception:
        库.close()
        raise
    return 库


def _确保表(库: sqlite3.Connection) -> None:
    库.execute(
        """
        CREATE TABLE IF NOT EXISTS 任务(
          id             TEXT PRIMARY KEY,
          类型           TEXT NOT NULL,
          戏名           TEXT,
          镜头           TEXT,
          格号           TEXT,
          状态           TEXT NOT NULL,
          尝试次数       INTEGER NOT NULL DEFAULT 0,
          创建时间       TEXT NOT NULL,
          开始时间       TEXT,
          结束时间       TEXT,
          用时           REAL,
          估算成本       REAL,
          实际成本       REAL,
          可能已计费     INTEGER NOT NULL DEFAULT 0,
          输入摘要       TEXT,
          输出路径       TEXT,
          错误           TEXT,
          重试链         TEXT,
          重试自         TEXT,
          供应商任务号   TEXT,
          备注           TEXT
        )"""
    )
    库.execute("CREATE INDEX IF NOT EXISTS 按状态 ON 任务(状态)")
    库.execute("CREATE INDEX IF NOT EXISTS 按戏名 ON 任务(戏名)")
    库.execute("CREATE INDEX IF NOT EXISTS 按类型 ON 任务(类型)")
    库.execute("CREATE TABLE IF NOT EXISTS 设置(键 TEXT PRIMARY KEY, 值 TEXT)")
    库.execute("CREATE TABLE IF NOT EXISTS 事件(序号 INTEGER PRIMARY KEY AUTOINCREMENT, 时间 TEXT, 任务 TEXT, 事件 TEXT, 详情 TEXT)")


def _时刻(t: float | None = None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t if t is not None else time.time()))


def _id新() -> str:
    s = f"{time.time():.6f}-{os.getpid()}-{os.urandom(4).hex()}"
    return "t" + hashlib.sha1(s.encode()).hexdigest()[:14]


def _行(r) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["可能已计费"] = bool(d.get("可能已计费"))
    return d


class _锁:
    """跨进程互斥锁。

    为什么不用 .tmp + os.replace 直接换数据库文件？
    -------------------------------------------------
    因为 sqlite 的库文件是「活的」：WAL 里可能还压着没回写的事务。把一个
    手写的 .tmp 覆盖上去，等于把 WAL 里的事务直接扔掉 —— 那才是真的丢数据。
    所以这里的硬保证分三层：

      1) 账本自己的写全部在**一个 SQLite 事务**里（要么全成，要么全不成）；
      2) PRAGMA synchronous=FULL + WAL：进程被强杀，SQLite 靠它自己的日志
         回滚半截事务，库不会「半截」；
      3) 关闭/每次写后抬一次 .bak 快照（先写 .tmp 再 os.replace，原子换名）。
         就算库文件真的被砸坏，_自愈() 会拿 .bak 恢复。

    这个锁文件只是把「同机多进程同时改账本」串起来，避免互相打架。
    锁里写 pid，进程被强杀留下的死锁会被自动识别并接管（不会永久卡死）。

    等待策略（实测改过一轮）
    ------------------------
    最早这里是「最多干等 20 秒，然后抛错」。作品\\账本自测 的并发段实测下来，
    这个 20 秒救不了任何东西，反而害人：
      · 一把**活锁**本来再等一会儿就能拿到，等到 20 秒反而抛错，看起来像账本坏了；
      · 一把**死锁**本来能立刻接管，如果接管时正好赶上持有人释放，就会白等满 20 秒。
    所以现在：等待窗口长得多（默认 90 秒，环境变量 影匠_锁等秒 可调），并且每次
    重试都**重新读一遍锁文件** —— 持有人一死，下一次循环就接管，不耗完整个窗口。
    """

    def __init__(self, 目标: str, 等秒: float | None = None):
        self.路 = 目标 + ".lck"
        self.拿了 = False
        self.等秒 = float(
            等秒 if 等秒 is not None else (os.environ.get("影匠_锁等秒") or 90)
        )

    @staticmethod
    def _活着(pid: int) -> bool:
        """这个 pid 现在还活着吗？

        这里有个实测踩到的坑：**pid <= 0 必须直接当死**。
        Windows 上 OpenProcess(0) 是能成功的（0 = System Idle Process，永远活着），
        所以「锁文件还没写完 / 读不出 pid」如果拿 0 去问，会得到「活着」，
        于是所有进程都以为锁被一个不存在的家伙占着，干等到超时。
        作品\\账本自测 的并发段就是这么白等了 20 秒。
        """
        if pid <= 0:
            return False
        if os.name == "nt":
            import ctypes

            核 = ctypes.windll.kernel32
            h = 核.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            try:
                码 = ctypes.c_ulong()
                核.GetExitCodeProcess(h, ctypes.byref(码))
                return 码.value == 259  # STILL_ACTIVE
            finally:
                核.CloseHandle(h)
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def __enter__(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.路)) or ".", exist_ok=True)
    def _锁里写了什么(self) -> tuple[int, str, float]:
        """把锁文件读成 (pid, 原文, 文件修改时间)。读不动就当成 (0, "", 0)。

        pid=0 表示「读不出持有人」—— 调用方按 0 处理（见 _活着 的说明）。
        """
        try:
            with open(self.路, "r", encoding="utf-8") as f:
                原 = f.read()
        except OSError:
            return 0, "", 0.0
        try:
            时 = os.path.getmtime(self.路)
        except OSError:
            时 = 0.0
        for 行 in 原.splitlines():
            行 = 行.strip()
            if not 行:
                continue
            try:
                return int(行), 原.strip().replace("\n", " · "), 时
            except ValueError:
                continue
        return 0, 原.strip().replace("\n", " · "), 时

    def __enter__(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.路)) or ".", exist_ok=True)
        起 = time.time()
        上次持有人 = -1
        我 = os.getpid()
        等秒 = self.等秒
        while True:
            try:
                fd = os.open(self.路, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, f"{我}\n{_时刻()}\n".encode("utf-8"))
                finally:
                    os.close(fd)
                self.拿了 = True
                return self
            except FileExistsError:
                pass
            except OSError as e:
                raise 账本错(f"建不了锁文件 {self.路}：{e}") from None

            # ── 有人拿着。每一轮都重新读一遍，因为它可能刚刚换了人 ──
            pid, 谁, 何时 = self._锁里写了什么()
            if pid == 我:
                # 锁文件里是我自己的 pid。同一个进程不可能同时跑两个需要加锁的
                # 写操作（都是同步调用），所以这只可能是上一次没收干净（被强杀、
                # 或 remove 失败）。我还活着，因此它绝不可能是「别人的活锁」，
                # 现在接管是安全的。
                self._清(为什么="锁文件里写的是我自己的 pid，上一次没收干净")
                continue
            if pid <= 0 or not self._活着(pid):
                # 读不出 pid，或者写锁的进程已经没了 → 死锁，接管。
                self._清(
                    为什么=(
                        f"锁文件里没有可用的 pid（内容是 {谁!r}）"
                        if pid <= 0
                        else f"写锁的进程 {pid} 已经不在了"
                    )
                )
                continue
            if time.time() - 起 > 等秒:
                多久 = ""
                if 何时:
                    多久 = f"，锁写了 {(time.time() - 何时):.0f} 秒了"
                raise 账本错(
                    f"等了 {等秒:.0f} 秒还没轮到：{self.路}\n"
                    f"  现在拿着它的是进程 {pid}{多久}。\n"
                    "  它可能正在跑一条很长的任务（出片一条要几分钟，这是正常的）。\n"
                    "  要么等它跑完再试，要么确认它已经死了再删掉这个 .lck 文件。\n"
                    "  （不自动删活锁，是怕把正在跑的写操作劈成两半。）\n"
                    "  想等更久：设环境变量 影匠_锁等秒=300。\n"
                    "  想看看是谁：type " + os.path.basename(self.路)
                ) from None
            if 上次持有人 != pid:
                上次持有人 = pid
                time.sleep(0.05)  # 刚换人，短睡一下再确认，别在交接缝上抢
            else:
                time.sleep(0.2)

    def _清(self, 为什么: str = "") -> None:
        """把锁文件拿走。拿不走也不抛 —— 下一轮循环会再试。"""
        try:
            os.remove(self.路)
        except OSError:
            pass
        else:
            if 为什么:
                _记警告(f"接管了锁文件 {os.path.basename(self.路)}：{为什么}")

    def __exit__(self, *a):
        if self.拿了:
            self.拿了 = False
            try:
                os.remove(self.路)
            except OSError:
                pass
        return False


# ───────────────────────────── 账本 ─────────────────────────────


class 账本:
    """一个 SQLite 任务账本。线程内用；跨进程靠 _锁 串行。"""

    def __init__(self, 路: str | None = None, 自动快照: bool = True):
        self.路 = os.path.abspath(路 or os.environ.get("影匠_账本") or 默认账本路)
        self.自动快照 = 自动快照
        os.makedirs(os.path.dirname(self.路) or ".", exist_ok=True)
        self._自愈()
        self._库 = _连(self.路)
        _确保表(self._库)

    # ---------- 自愈 ----------

    def _自愈(self) -> None:
        """库文件坏了？先隔离，再拿 .bak 快照恢复。绝不静默。"""
        if not os.path.exists(self.路):
            return
        try:
            测 = sqlite3.connect(self.路, timeout=10)
            try:
                行 = 测.execute("PRAGMA integrity_check").fetchone()
            finally:
                测.close()
            if 行 and str(行[0]).lower() == "ok":
                return
            毛病 = str(行[0]) if 行 else "integrity_check 无返回"
        except Exception as e:
            毛病 = f"{type(e).__name__}: {e}"

        坏 = self.路 + f".坏.{int(time.time())}"
        os.replace(self.路, 坏)
        for 尾 in ("-wal", "-shm"):
            if os.path.exists(self.路 + 尾):
                try:
                    os.replace(self.路 + 尾, 坏 + 尾)
                except OSError:
                    pass
        备 = self.路 + ".bak"
        if os.path.exists(备):
            os.replace(备, self.路)
            sys.stderr.write(
                f"⚠ 账本文件损坏，已从快照恢复：\n   坏文件 {坏}\n   用的备份 {备}\n"
                f"   原因 {毛病}\n   备份之后记的账可能少了，请人工核一遍。\n"
            )
        else:
            sys.stderr.write(
                f"⚠ 账本文件损坏且没有备份，已隔离为 {坏}（原因 {毛病}），现在开一个空账本。\n"
            )

    def _快照(self) -> str:
        """把当前账本内容原子地抬一份到 <路>.bak（先 .tmp 再 os.replace）。"""
        tmp = self.路 + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)
        对 = sqlite3.connect(tmp)
        try:
            self._库.backup(对)
        finally:
            对.close()
        if os.environ.get("影匠_账本_快照注入损坏") == "1":
            with open(tmp, "ab") as f:          # 只给自测用：制造一个坏掉的备份
                f.write(b"\x00\x00NOT-A-SQLITE-FILE")
        os.replace(tmp, self.路 + ".bak")
        if self.自动快照:
            for 尾 in ("-wal", "-shm"):
                p = self.路 + 尾
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        return self.路 + ".bak"

    # ---------- 底层 ----------

    def _写(self, sql: str, 参=()):
        with _锁(self.路):
            self._库.execute("BEGIN IMMEDIATE")
            try:
                果 = self._库.execute(sql, 参)
                self._库.execute("COMMIT")
            except Exception:
                try:
                    self._库.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        return 果

    def _记(self, 任务id: str, 事件: str, 详情: str = "") -> None:
        self._库.execute(
            "INSERT INTO 事件(时间,任务,事件,详情) VALUES(?,?,?,?)",
            (_时刻(), 任务id, 事件, 详情[:800]),
        )

    def 取(self, 任务id: str) -> dict | None:
        r = self._库.execute("SELECT * FROM 任务 WHERE id=?", (任务id,)).fetchone()
        return _行(r)

    def _必须(self, 任务id: str) -> dict:
        t = self.取(任务id)
        if t is None:
            raise 找不到任务(f"账本里没有任务 {任务id}　（跑 `python 账本.py 列表` 看现有 id）")
        return t

    def _换态(self, 任务id: str, 目标: str, 额外: dict | None = None) -> dict:
        当前 = self._必须(任务id)
        源 = 当前["状态"]
        if 目标 not in _迁移表.get(源, ()):
            raise 状态非法(
                f"任务 {任务id} 现在是「{源}」，不能改成「{目标}」。\n"
                f"  「{源}」允许的去向：{'、'.join(_迁移表.get(源, ())) or '（终态，哪都不去）'}"
                + (
                    "\n  ★「未知」是终态：可能已送达供应商/可能已计费，"
                    "只能用 恢复() 人工确认后再动。"
                    if 源 == 未知
                    else ""
                )
            )
        段 = ["状态=?"]
        值: list = [目标]
        for k, v in (额外 or {}).items():
            段.append(f"{k}=?")
            值.append(v)
        值.append(任务id)
        自我 = self
        with _锁(self.路):
            self._库.execute("BEGIN IMMEDIATE")
            try:
                self._库.execute(f"UPDATE 任务 SET {','.join(段)} WHERE id=?", 值)
                自我._记(任务id, 目标, json.dumps(额外 or {}, ensure_ascii=False, default=str))
                self._库.execute("COMMIT")
            except Exception:
                try:
                    self._库.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        return self._必须(任务id)

    # ---------- 记账 ----------

    def 新建(
        self,
        类型: str,
        戏名: str = "",
        镜头: str = "",
        格号: str = "",
        估算成本: float | None = None,
        输入=None,
        重试自: str | None = None,
        备注: str = "",
        初始状态: str = 排队,
    ) -> str:
        """开一笔账。默认进「排队」。返回任务 id。"""
        if 初始状态 not in 全部状态:
            raise 状态非法(f"没有这个状态：{初始状态}（有：{'、'.join(全部状态)}）")
        rid = _id新()
        时 = _时刻()
        if 输入 is not None and not isinstance(输入, str):
            输入 = 输入摘要(输入)
        with _锁(self.路):
            self._库.execute("BEGIN IMMEDIATE")
            try:
                self._库.execute(
                    "INSERT INTO 任务(id,类型,戏名,镜头,格号,状态,尝试次数,创建时间,"
                    "估算成本,输入摘要,重试自,备注) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, 类型, 戏名, 镜头, 格号, 初始状态, 0, 时,
                     估算成本, 输入, 重试自, 备注),
                )
                if 重试自:
                    self._库.execute("UPDATE 任务 SET 重试链=? WHERE id=?", (rid, 重试自))
                self._记(rid, "新建", f"{类型} {戏名} {镜头} {格号}")
                self._库.execute("COMMIT")
            except Exception:
                try:
                    self._库.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        return rid

    def 领取(self, 任务id: str) -> dict:
        """过并发闸门并开跑：排队 → 运行，尝试次数 +1，记开始时间。

        闸门满 → 抛 闸门满（任务留在「排队」，不是失败）。
        """
        上限 = self.取上限()
        with _锁(self.路):
            self._库.execute("BEGIN IMMEDIATE")
            try:
                t = self._库.execute("SELECT * FROM 任务 WHERE id=?", (任务id,)).fetchone()
                if t is None:
                    raise 找不到任务(f"账本里没有任务 {任务id}")
                if t["状态"] != 排队:
                    raise 状态非法(
                        f"任务 {任务id} 现在是「{t['状态']}」，只有「排队」的才能领取。"
                    )
                在跑 = self._库.execute(
                    "SELECT COUNT(*) FROM 任务 WHERE 状态=?", (运行,)
                ).fetchone()[0]
                if 在跑 >= 上限:
                    raise 闸门满(
                        f"并发闸门满了：上限 {上限}，现在有 {在跑} 条在跑。\n"
                        f"  任务 {任务id} 留在「排队」，等前一个跑完再 领取()。\n"
                        f"  （本机只有一张卡，默认上限 1；确实要放开：python 账本.py 闸门 --上限 N）"
                    )
                self._库.execute(
                    "UPDATE 任务 SET 状态=?, 尝试次数=尝试次数+1, 开始时间=?, 结束时间=NULL,"
                    " 用时=NULL, 错误=NULL WHERE id=?",
                    (运行, _时刻(), 任务id),
                )
                self._记(任务id, "运行", f"第 {t['尝试次数'] + 1} 次尝试")
                self._库.execute("COMMIT")
            except Exception:
                try:
                    self._库.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        return self._必须(任务id)

    def 开始(self, 任务id: str, 供应商任务号: str = "") -> dict:
        """记开始时间/供应商单号（不改状态，供已由 领取() 开跑的任务补记）。"""
        额外: dict = {"开始时间": _时刻()}
        if 供应商任务号:
            额外["供应商任务号"] = 供应商任务号
        t = self._必须(任务id)
        if t["状态"] in 终态:
            raise 状态非法(f"任务 {任务id} 已经是「{t['状态']}」（终态），不能记开始。")
        if t["状态"] == 排队:
            raise 状态非法(
                f"任务 {任务id} 还在「排队」，先 领取() 过闸门再 开始()。\n"
                f"  （直接 开始() 会绕过并发闸门，本机一张卡扛不住两个活。）"
            )
        return self._换态(任务id, t["状态"], 额外)

    def 完成(self, 任务id: str, 输出路径: str = "", 实际成本: float | None = None) -> dict:
        # 注意：这里必须写字符串 "完成"，不能写裸名 完成 —— 同名形参会遮蔽模块常量。
        当前 = self._必须(任务id)
        用 = self._用时(当前)
        实际 = 当前["实际成本"] if 实际成本 is None else 实际成本
        return self._换态(
            任务id, "完成",
            {"结束时间": _时刻(), "用时": 用, "输出路径": 输出路径 or 当前["输出路径"],
             "实际成本": 实际, "可能已计费": 1 if 当前["可能已计费"] else 0},
        )

    def 失败(self, 任务id: str, 错="", 实际成本: float | None = None) -> dict:
        """明确失败：供应商那边确定没成、也没计费。这种可以退避重试。

        ★ 如果你不确定它到底成没成 —— 别调这个，调 未知()。
        """
        当前 = self._必须(任务id)
        return self._换态(
            任务id, "失败",
            {"结束时间": _时刻(), "用时": self._用时(当前),
             "错误": str(错)[:2000],
             "实际成本": 当前["实际成本"] if 实际成本 is None else 实际成本},
        )

    def 未知(self, 任务id: str, 因="", 可能已计费: bool = True, 供应商任务号: str = "") -> dict:
        """★ 说不清就跑这个：可能已送达供应商、结果或计费状态无法确认。

        进了「未知」就**不能自动重试**（重试() 会抛 需人工核对）。
        """
        当前 = self._必须(任务id)
        额外 = {
            "结束时间": _时刻(),
            "用时": self._用时(当前),
            "错误": str(因)[:2000],
            "可能已计费": 1 if 可能已计费 else 0,
        }
        if 供应商任务号:
            额外["供应商任务号"] = 供应商任务号
        return self._换态(任务id, "未知", 额外)

    def 未知因为(self, 任务id: str, 错, 因: str = "") -> dict:
        """★ 接线口：把一个「说不清」的异常**一步**记成未知态。

        跟 未知() 的区别：先问一遍 分类异常(错)，认得出「提交后失联」就把
        供应商任务号 / 可能已计费 自动带进账里 —— 调用方不用自己拆异常属性，
        也就没机会漏掉那个提示号（漏了，人就得满 ComfyUI 翻历史找是哪条活）。

            try:
                r = 引擎.派工(wf)
            except 引擎.提交未知 as e:
                账本.未知因为(任务id, e)      # ← 就这一行

        认不出来的异常也照样记未知（铁律：说不清一律交人工）。
        """
        v = 分类异常(错)
        文 = (因 or str(错 or "")).strip()
        if v["类别"] not in 文:
            文 = f"[{v['类别']}] {文}"
        return self.未知(
            任务id,
            因=文,
            可能已计费=bool(v["动作"] == "未知" or getattr(错, "可能已计费", False)),
            供应商任务号=str(v.get("供应商任务号") or ""),
        )

    def 取消(self, 任务id: str, 因: str = "") -> dict:
        当前 = self._必须(任务id)
        return self._换态(
            任务id, "取消",
            {"结束时间": _时刻(), "错误": str(因)[:2000],
             "实际成本": 当前["实际成本"]},
        )

    @staticmethod
    def _用时(t: dict) -> float | None:
        if not t.get("开始时间"):
            return None
        try:
            起 = time.mktime(time.strptime(t["开始时间"], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            return t.get("用时")
        return round(time.time() - 起, 2)

    # ---------- 重试 ----------

    def 可重试(self, 任务id: str) -> tuple[bool, str]:
        """能不能自动重试？返回 (能不能, 人话理由)。

        判定顺序：状态 → 可能已计费 → 异常类别。任一条说不行就不行。
        """
        t = self._必须(任务id)
        供应商 = self._供应商(t)
        if t["状态"] == 未知:
            return False, (
                f"「未知」态：可能已送达 {供应商}、可能已计费 —— 铁律禁止自动重试，"
                f"先去 {供应商} 核对（重试会抛 需人工核对）"
            )
        if t["可能已计费"]:
            return False, (
                f"这条任务的「可能已计费」是开着的（可能是上次未知态留下的）—— "
                f"先去 {供应商} 核对，别自动重试"
            )
        if t["状态"] == 完成:
            return False, f"已经「完成」了（输出 {t['输出路径'] or '—'}），重试等于白跑一遍"
        if t["状态"] == 运行:
            return False, "还在「运行」—— 先等它结束，或者确认它死了再 未知()/失败()"
        if t["状态"] == 排队:
            return False, "还在「排队」，直接 领取() 就行，不用重试"
        if t["状态"] == 取消:
            return False, "是你自己取消的；确实要重跑，用 --强开 开一条新的"
        # 失败态：**先看有没有人工对账的流水** —— 人真去供应商后台看过了，
        # 这件事比机器的文本分类可信，机器永远只能猜。
        if self._人工对账过(任务id) == "没成":
            return True, ("人工已经去供应商后台核对过：这条没跑成、没计费 —— 可以重试"
                          "（核对流水在 事件 表里，事件='对账'）")
        # 失败态：看上次到底为什么失败
        v = 分类异常(str(t.get("错误") or ""))
        下一步 = 建议(t.get("错误") or "", 连败=t["尝试次数"])
        if v["动作"] == "退避后重试":
            return True, (
                f"上次是「{v['类别']}」明确失败，可以退避重试"
                + (f"（建议等 {下一步['等待秒']:.0f} 秒）" if 下一步["等待秒"] else "")
            )
        if v["动作"] == "停":
            return False, (
                f"上次是「{v['类别']}」：{v['说明']}\n"
                f"  这种失败重试一百遍也一样，先把环境修好（{v['下一步']}）"
            )
        return False, (
            f"上次是「{v['类别']}」：说不清供应商收没收到 —— 先去 {供应商} 核对，"
            f"确认没送达再用 恢复() 或者手工重跑"
        )

    def 重试(self, 任务id: str, 强开: bool = False, 估算成本: float | None = None) -> str:
        """开一条**新**任务接着失败的那条跑。

        ★ 可能已计费 / 未知态 → 抛 需人工核对，拒绝。
        """
        t = self._必须(任务id)
        if not 强开:
            能, 理由 = self.可重试(任务id)
            if not 能:
                if t["状态"] == 未知 or t["可能已计费"]:
                    raise 需人工核对(t, self._供应商(t), 理由)
                raise 账本错(f"不重试任务 {任务id}：{理由}")
        新id = self.新建(
            t["类型"],
            戏名=t["戏名"] or "",
            镜头=t["镜头"] or "",
            格号=t["格号"] or "",
            估算成本=t["估算成本"] if 估算成本 is None else 估算成本,
            输入=t["输入摘要"] or None,
            重试自=任务id,
            备注=f"重试自 {任务id}" + ("（强开）" if 强开 else ""),
        )
        with _锁(self.路):
            self._库.execute("BEGIN IMMEDIATE")
            try:
                self._库.execute("UPDATE 任务 SET 重试链=? WHERE id=?", (新id, 任务id))
                self._记(任务id, "派了重试", 新id)
                self._库.execute("COMMIT")
            except Exception:
                try:
                    self._库.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        return 新id

    def 恢复(self, 任务id: str, 备注: str = "人工核对后恢复") -> dict:
        """人工核对完了：把非终态 / 未知态的任务标回可继续（→ 排队）。

        「运行」也要能恢复 —— 进程被强杀时任务就停在「运行」，
        这正是断点恢复最主要的场景；它不是"已经好好的"，是"卡住了"。
        """
        t = self._必须(任务id)
        if t["状态"] == 排队:
            return t
        if t["状态"] == 完成:
            raise 状态非法(f"任务 {任务id} 已经「完成」，不需要恢复。")
        with _锁(self.路):
            self._库.execute("BEGIN IMMEDIATE")
            try:
                self._库.execute(
                    "UPDATE 任务 SET 状态=?, 结束时间=NULL, 错误=NULL,"
                    " 可能已计费=0, 备注=? WHERE id=?",
                    (排队, f"{t['备注'] or ''}｜{备注}｜{_时刻()}".strip("｜"), 任务id),
                )
                self._记(任务id, "恢复", f"从「{t['状态']}」标回排队：{备注}")
                self._库.execute("COMMIT")
            except Exception:
                try:
                    self._库.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        return self._必须(任务id)

    # ---------- 对账：把「未知」结掉 ----------

    def _人工对账过(self, 任务id: str) -> str:
        """最后一条「对账」流水说的是什么：成了 / 没成 / ""（没对过账）。

        记号写在 事件 表里（只增不改的流水），不写在 备注 里 —— 备注是给人看的
        自由文本，拿它当开关，谁手滑改一个字就能把铁律绕过去。
        """
        try:
            行 = self._库.execute(
                "SELECT 详情 FROM 事件 WHERE 任务=? AND 事件='对账' ORDER BY 序号 DESC LIMIT 1",
                (任务id,),
            ).fetchone()
        except Exception:
            return ""
        文 = (行["详情"] if 行 else "") or ""
        if "没成" in 文:
            return "没成"
        if "成了" in 文:
            return "成了"
        return ""

    def 对账(self, 任务id: str, 结果: str = "", 产物: str = "",
             备注: str = "", 实际成本: float | None = None) -> dict:
        """人工核对完了：把一条「未知」账按**人看到的事实**结掉。

            结果="成了"  → 状态=完成（带了产物路径就记上；这条活确实跑过了，钱照记）
            结果="没成"  → 状态=失败（可能已计费清 0，并留下人工核对过的流水 ——
                            此后 重试() 放行，因为「到底跑没跑」已经有人真去查过了）

        ★ 「未知」是终态，_迁移表 不许它动。对账是**唯一**的人工作业出口：
          它不是自动流程，是"人已经去过供应商后台了"这件事的落账。
          没对过账的「未知」账，重试() 一律抛 需人工核对（铁律）。

        返回结完之后的整行。
        """
        t = self._必须(任务id)
        if t["状态"] != 未知:
            raise 状态非法(
                f"任务 {任务id} 现在不是「未知」态（是「{t['状态']}」），不用对账。"
                + {"排队": "排队中的活直接 领取() 就行。",
                   "运行": "还在跑的活等它结束，或者确认它死了再 未知()/失败()。",
                   "完成": "这条已经结完了。",
                   "失败": "已经是「失败」了；要重跑就 重试()。",
                   "取消": "是你自己取消的；要重跑就 重试 --强开。"}.get(t["状态"], "")
            )
        结果 = (结果 or "").strip()
        if 结果 not in ("成了", "没成"):
            raise 账本错(f"对账要 --结果 成了 / --结果 没成，收到：{结果!r}")
        if 结果 == "成了" and not (产物 or t["输出路径"]):
            raise 账本错(
                f"对账 {任务id}：说「成了」就得给 --产物 <输出路径> —— "
                "结到「完成」的账要能让人按路径找到那条片，不然等于没结。"
            )
        现 = _时刻()
        用 = self._用时(t)
        记号 = f"【人工对账·{结果}】{现}" + (f"｜{备注}" if 备注 else "")
        新备注 = f"{t['备注'] or ''}｜{记号}".strip("｜")

        with _锁(self.路):
            self._库.execute("BEGIN IMMEDIATE")
            try:
                if 结果 == "成了":
                    产 = 产物 or t["输出路径"] or ""
                    实 = t["实际成本"] if 实际成本 is None else 实际成本
                    # 「可能已计费」是对未知的**猜测**；人已经确认它真跑成了，
                    # 猜测就作废（钱确实花了，记在 实际成本 上）—— 留着会让
                    # 统计() 把它算成待核对的账，也会让 重试() 报成「需人工核对」
                    # 而不是老老实实说「已经完成了」。
                    self._库.execute(
                        "UPDATE 任务 SET 状态=?, 结束时间=?, 用时=?, 输出路径=?,"
                        " 实际成本=?, 可能已计费=0, 备注=? WHERE id=?",
                        ("完成", 现, 用, 产, 实, 新备注, 任务id),
                    )
                    详情 = f"人工核对：成了（从「未知」结到「完成」）产物 {产 or '—'}｜{备注}"
                else:
                    原错 = t["错误"] or ""
                    self._库.execute(
                        "UPDATE 任务 SET 状态=?, 结束时间=?, 用时=?, 可能已计费=0,"
                        " 错误=?, 备注=? WHERE id=?",
                        ("失败", 现, 用,
                         f"[人工对账·没成] 供应商那边确认没跑成、没计费。原记录：{原错}"[:2000],
                         新备注, 任务id),
                    )
                    详情 = f"人工核对：没成（从「未知」结到「失败」，已清 可能已计费）｜{备注}"
                self._记(任务id, "对账", 详情)
                self._库.execute("COMMIT")
            except Exception:
                try:
                    self._库.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        return self._必须(任务id)

    # ---------- 查询 ----------

    def 未完成(self, 戏名: str = "") -> list[dict]:
        """所有非终态任务 —— 断点恢复看这个。

        注意：「未知」是终态（等人工），所以不在这里；它会出现在 待人工() 里。
        """
        sql = "SELECT * FROM 任务 WHERE 状态 IN (?,?)"
        参: list = [排队, 运行]
        if 戏名:
            sql += " AND 戏名=?"
            参.append(戏名)
        sql += " ORDER BY 创建时间, id"
        return [_行(r) for r in self._库.execute(sql, 参).fetchall()]

    def 待人工(self, 戏名: str = "") -> list[dict]:
        """卡在「未知」态、等你去供应商后台核对的账。"""
        sql = "SELECT * FROM 任务 WHERE 状态=?"
        参: list = [未知]
        if 戏名:
            sql += " AND 戏名=?"
            参.append(戏名)
        sql += " ORDER BY 创建时间, id"
        return [_行(r) for r in self._库.execute(sql, 参).fetchall()]

    def 列表(
        self,
        状态: str = "",
        戏名: str = "",
        类型: str = "",
        限: int = 0,
        只未结算: bool = False,
    ) -> list[dict]:
        段, 参 = ["1=1"], []
        if 状态:
            段.append("状态=?")
            参.append(状态)
        if 戏名:
            段.append("戏名=?")
            参.append(戏名)
        if 类型:
            段.append("类型=?")
            参.append(类型)
        if 只未结算:
            段.append("实际成本 IS NULL")
        sql = "SELECT * FROM 任务 WHERE " + " AND ".join(段) + " ORDER BY 创建时间 DESC, id DESC"
        if 限:
            sql += f" LIMIT {int(限)}"
        return [_行(r) for r in self._库.execute(sql, 参).fetchall()]

    def 统计(self, 戏名: str = "") -> dict:
        尾 = " WHERE 戏名=?" if 戏名 else ""
        参 = (戏名,) if 戏名 else ()
        出: dict = {
            "总数": self._库.execute(f"SELECT COUNT(*) FROM 任务{尾}", 参).fetchone()[0],
            "按状态": {},
            "按类型": {},
            "估算成本": 0.0,
            "实际成本": 0.0,
            "可能已计费": 0,
            "待人工": 0,
            "最久一件": None,
            "总用时秒": 0.0,
        }
        for r in self._库.execute(
            f"SELECT 状态, COUNT(*) n FROM 任务{尾} GROUP BY 状态", 参
        ):
            出["按状态"][r["状态"]] = r["n"]
        for r in self._库.execute(
            f"SELECT 类型, COUNT(*) n, SUM(实际成本) 实, SUM(估算成本) 估 FROM 任务{尾} GROUP BY 类型",
            参,
        ):
            出["按类型"][r["类型"]] = {
                "件数": r["n"],
                "实际成本": round(r["实"] or 0, 3),
                "估算成本": round(r["估"] or 0, 3),
            }
        r = self._库.execute(
            f"SELECT SUM(估算成本) a, SUM(实际成本) b, SUM(可能已计费) c,"
            f" SUM(CASE WHEN 状态='{未知}' THEN 1 ELSE 0 END) d, SUM(用时) e"
            f" FROM 任务{尾}",
            参,
        ).fetchone()
        出["估算成本"] = round(r["a"] or 0, 3)
        出["实际成本"] = round(r["b"] or 0, 3)
        出["可能已计费"] = r["c"] or 0
        出["待人工"] = r["d"] or 0
        出["总用时秒"] = round(r["e"] or 0, 2)
        最 = self._库.execute(
            f"SELECT id,类型,用时 FROM 任务{尾}{' AND' if 尾 else ' WHERE'} 用时 IS NOT NULL"
            " ORDER BY 用时 DESC LIMIT 1",
            参,
        ).fetchone()
        if 最:
            出["最久一件"] = {"id": 最["id"], "类型": 最["类型"], "秒": 最["用时"]}
        return 出

    # ---------- 并发闸门 ----------

    def 取上限(self) -> int:
        r = self._库.execute("SELECT 值 FROM 设置 WHERE 键='并发上限'").fetchone()
        try:
            return max(1, int(r["值"])) if r else 1
        except Exception:
            return 1

    def 置上限(self, n: int) -> int:
        n = max(1, int(n))
        with _锁(self.路):
            self._库.execute("BEGIN IMMEDIATE")
            try:
                self._库.execute(
                    "INSERT INTO 设置(键,值) VALUES('并发上限',?)"
                    " ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
                    (str(n),),
                )
                self._库.execute("COMMIT")
            except Exception:
                try:
                    self._库.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        return n

    def 闸门(self) -> dict:
        上限 = self.取上限()
        在跑 = self._库.execute("SELECT COUNT(*) FROM 任务 WHERE 状态=?", (运行,)).fetchone()[0]
        排队数 = self._库.execute("SELECT COUNT(*) FROM 任务 WHERE 状态=?", (排队,)).fetchone()[0]
        return {"上限": 上限, "在跑": 在跑, "排队": 排队数, "还能开": max(0, 上限 - 在跑)}

    def 释放(self, 任务id: str, 输出路径: str = "", 实际成本: float | None = None) -> dict:
        """把一个「运行」中的任务正常收尾，腾出闸门位。"""
        return self.完成(任务id, 输出路径=输出路径, 实际成本=实际成本)

    # ---------- 成本预告 ----------

    def _实测(self, 类型: str, 模板: str = "") -> dict:
        段, 参 = ["类型=?", "用时 IS NOT NULL"], [类型]
        if 模板:
            段.append("输入摘要=?")
            参.append(输入摘要({"模板": 模板}))
        r = self._库.execute(
            f"SELECT COUNT(*) n, AVG(用时) a FROM 任务 WHERE {' AND '.join(段)}", 参
        ).fetchone()
        if not r or not r["n"]:
            return {}
        return {"样本": r["n"], "均值秒": round(r["a"], 2)}

    def 预估(
        self,
        类型: str,
        数量: int = 1,
        模板: str = "",
        宽: int = 0,
        高: int = 0,
        帧数: int = 0,
        步数: int = 0,
        供应商报价: float | None = None,
    ) -> dict:
        """成本预告：给个数 + 说清这个数是怎么来的（估算 or 实测均值）。

        返回 {类型,数量,单位,积分,秒,金额,依据,说明,分项}
        """
        数量 = max(1, int(数量))
        基 = 计价表.get(类型) or 计价表["其他"]
        实测 = self._实测(类型, 模板)
        依据 = "实测均值"
        明细 = ""
        if 实测:
            秒 = 实测["均值秒"]
            系数 = 1.0
            if 类型 in ("出图", "出图四宫格"):
                系数 = (宽 / 1024) * (高 / 1024) if (宽 and 高) else 1.0
                系数 = max(0.3, min(4.0, 系数))
            elif 类型 == "出片" and 帧数:
                系数 = max(0.4, min(3.0, 帧数 / 49.0))
            秒 = round(秒 * 系数, 2)
            积分 = round(秒 / 基["基准秒"] * 基["基准积分"], 3)
            明细 = (
                f"账本里有 {实测['样本']} 条同类实测，均值 {实测['均值秒']} 秒/件"
                + (f"，按尺寸/帧数系数 {系数:.2f} 归一" if abs(系数 - 1.0) > 1e-9 else "")
                + "；再按基线换算积分"
            )
            if 实测["样本"] < 3:
                依据 = "实测均值（样本少）"
        else:
            秒 = 基["基准秒"]
            if 类型 in ("出图", "出图四宫格") and 宽 and 高:
                秒 = round(基["基准秒"] * max(0.3, min(4.0, (宽 / 1024) * (高 / 1024))), 2)
            elif 类型 == "出片" and 帧数:
                秒 = round(基["基准秒"] * max(0.4, min(3.0, 帧数 / 49.0)), 2)
            积分 = round(秒 / 基["基准秒"] * 基["基准积分"], 3)
            依据 = "基线估算" if 基["来源"] == "本机实测基线" else "设计意图估算"
            明细 = f"账本里还没有「{类型}」的实测样本，用本机基线 {基['基准秒']} 秒/件 × 基线 {基['基准积分']} 积分/件"

        总秒 = round(秒 * 数量, 2)
        总积分 = round(积分 * 数量, 2)
        度 = 整机瓦数 / 1000.0 * (总秒 / 3600.0)
        金额 = round(度 * 电价, 4)
        说明 = (
            f"{类型} × {数量}{基['单位']}：约 {总积分} 积分 / {总秒} 秒墙钟 / "
            f"约 {金额} 元电费（{整机瓦数:.0f}W × {总秒 / 3600:.2f}h × {电价} 元/度）。"
            f"来源：{依据}。{明细}。"
        )
        if 供应商报价 is not None:
            说明 += f" 供应商报价口径：{供应商报价 * 数量}（按件计，与你给的单价相乘）。"
        return {
            "类型": 类型, "数量": 数量, "单位": 基["单位"],
            "积分": 总积分, "单件积分": 积分,
            "秒": 总秒, "单件秒": 秒,
            "金额": 金额, "元每度": 电价, "整机瓦数": 整机瓦数,
            "依据": 依据, "说明": 说明,
            "分项": {"基线来源": 基["来源"], "实测样本": 实测.get("样本", 0)},
        }

    # ---------- 收尾 ----------

    def 供应商(self, 东西) -> str:
        """这件活该去谁家后台核对。接受任务 dict 或类型字符串。"""
        类型 = 东西.get("类型", "") if isinstance(东西, dict) else str(东西 or "")
        return {
            "出图": "ComfyUI（本机 5080 上的 http://127.0.0.1:8188，没有外部供应商计费）",
            "出图四宫格": "ComfyUI（本机 5080 上的 http://127.0.0.1:8188，没有外部供应商计费）",
            "出片": "ComfyUI（本机 5080 上的 http://127.0.0.1:8188，没有外部供应商计费）",
            "配音": "TTS 供应商后台（配音.py 用的那家）",
        }.get(类型, "对应供应商的后台")

    _供应商 = 供应商

    def 快照(self) -> str:
        """手动抬一份备份。"""
        return self._快照()

    def 关(self) -> None:
        """收工：抬备份 + 关连接。每次改完账都能抬，抬失败不阻断。"""
        if self.自动快照:
            try:
                self._快照()
            except Exception as e:
                sys.stderr.write(f"⚠ 快照失败（记账本身没问题）：{type(e).__name__}: {e}\n")
        try:
            self._库.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.关()
        return False


# ───────────────────────────── 异常分类 ─────────────────────────────
#
# ★ 这一段的诚实边界：它只看异常**文本**。
#   「字面写着连不上」→ 判为「服务真没起」，快速失败；
#   「字面写着超时/拒绝」→ 判为「说不清」，建议进未知态；
#   认不出来的 → 一律按最保守的「说不清」处理，绝不当成明确失败去自动重试。
#   它不能真的知道供应商收没收到包。真要确定，只能去供应商后台查。

_类别表 = [
    (
        "服务没起（连不上）",
        ("连不上", "connection refused", "connectionrefused", "econnrefused",
         "max retries exceeded", "failed to establish", "名称解析", "getaddrinfo",
         "no route to host", "目标计算机积极拒绝", "actively refused"),
        "停",
        "对端 TCP 都没建立起来 —— 请求到不了它手里，所以不可能被计费，"
        "重试一百遍也一样。",
        "把服务拉起来：ComfyUI 开没开、端口对不对（python 引擎.py 体检）",
        False,
    ),
    (
        "鉴权/权限问题",
        (" 401", " 403", "unauthorized", "forbidden", "invalid api key", "无权限", "鉴权"),
        "停",
        "请求被对端拒在门外，通常没进业务、没计费。",
        "先修 key/权限，再重试",
        False,
    ),
    (
        "请求格式/参数被拒",
        (" 400", " 404", " 422", "bad request", "not found", "validation", "参数"),
        "停",
        "对端明确说这个请求不合法，它没有开始干活。",
        "按报错改参数，再重试",
        False,
    ),
    (
        "本地错误（没派出去）",
        ("找不到图", "没有模板", "找不到模板", "filenotfounderror",
         "no such file", "fileexistserror", "permissionerror", "oserror"),
        "停",
        "错误发生在本地准备阶段，活根本没派出去。",
        "修本地文件/路径，再重试",
        False,
    ),
    (
        "对端宕机/限流",
        (" 502", " 503", " 504", " 429", "server error", "bad gateway",
         "service unavailable", "rate limit", "too many requests", "限流", "过载"),
        "退避后重试",
        "对端自己出问题了。但 503/504 有时代码已经跑了一半 —— 这种「明确失败」的"
        "把握不如连不上那一类高，所以只在低风险任务（出图）上退避重试；"
        "出片这种贵的，先按未知态走人工核对更稳。",
        "等一会儿再试",
        True,
    ),
    (
        "超时（说不清）",
        ("timeout", "timed out", "超时", "read timed out", "readtimeout",
         "sockettimeout", "等待超时", "还没跑完", "等了 "),
        "未知",
        "请求**可能已经送达**并开始跑，只是我们没等到回音 —— 结果和计费都说不清。"
        "（派工超时就是这一类：工作流已经交上去了，提示号都拿到了。）",
        "先去供应商后台查这个号跑没跑；查不到再 恢复()",
        True,
    ),
    (
        "中止/断链（说不清）",
        ("remotedisconnected", "connection reset", "connection aborted",
         "broken pipe", "connectionreseterror", "连接被", "中断", "eof occurred"),
        "未知",
        "连接是在中途断的：包可能已经过去了 —— 说不清。",
        "同上：先查后台，再决定恢复还是重跑",
        True,
    ),
    (
        "引擎报错（明确失败，可退避重试）",
        ("工作流跑挂了", "拒绝了这个工作流", "跑完了但没有输出", "comfyui 返回"),
        "退避后重试",
        "对端回了明确的错误体：它确实跑了并失败了，这条活没成、也没出片。"
        "这就是「抖动」—— 换种子/改提示词/降分辨率之后可以退避重试。",
        "看报错改工作流或提示词，退避后重试",
        False,
    ),
]

_动作含义 = {
    "停": "别自动重试，先把环境/参数修好（快速失败）",
    "退避后重试": "明确失败，可以退避重试",
    "未知": "说不清，交人工核对（禁止自动重试）",
}


# 「提交后失联」—— 供应商适配器（引擎.py 的 提交未知 异常）报到账本时用的类别名。
# 它**不靠文本匹配**：异常自己带 可能已计费=True + 供应商任务号，账本认这两个属性。
# 为什么非要有这条属性快路：纯文本匹配会把「提交之后连不上」认成
# 「服务没起（连不上）」—— 那一类的动作是「停」，可真相是活已经交出去了，
# 钱可能已经花了。一字之差，一个让上层放心重跑，一个必须停下来问人。
提交后失联 = "提交后失联（钱可能已经花出去）"


def 分类异常(错) -> dict:
    """把异常/错误文本分成三类处置：
    「停」（快速失败）/「退避后重试」（抖动）/「未知」（交人工）。

    返回 {类别, 动作, 可自动重试, 快速失败, 说明, 下一步, 存疑, 原文}
    （属性快路命中时还会多带一个 供应商任务号）

    ★ 两条路，先属性后文本：
      ① **属性快路**：异常自带 可能已计费=True + 供应商任务号/提示号 ——
         只有「提交之后才跟丢」的适配器会这么写（引擎.提交未知），必定归「未知」；
      ② **文本路**：按 _类别表 匹配错误文本。

    ★ 诚实边界：文本路只看字面，不知道供应商到底收没收到包。
      所以认不出来的一律按最保守的「未知」处理。
    """
    文 = str(错 or "")
    低 = 文.lower()

    # ① 属性快路：供应商适配器自己承认「我交出去了，然后跟丢了」
    号 = str(getattr(错, "供应商任务号", "") or getattr(错, "提示号", "") or "")
    if getattr(错, "可能已计费", False) and 号:
        return {
            "类别": 提交后失联,
            "动作": "未知",
            "可自动重试": False,
            "快速失败": False,
            "说明": "工作流**已经交到供应商手里**了（连任务号都拿到了），之后才跟丢 —— "
                    "它可能正在跑、可能已经跑完、也可能压根没收到。结果和计费都说不清。",
            "下一步": f"拿任务号 {号} 去供应商那边查这一个号跑没跑，查完用 对账() 结掉",
            "存疑": True,
            "原文": 文[:400],
            "供应商任务号": 号,
        }

    for 类, 键们, 动作, 说明, 下步, 存疑 in _类别表:
        for k in 键们:
            if k in 低 or k in 文:
                return {
                    "类别": 类,
                    "动作": 动作,
                    "可自动重试": 动作 == "退避后重试",
                    "快速失败": 动作 == "停",
                    "说明": 说明,
                    "下一步": 下步,
                    "存疑": 存疑,
                    "原文": 文[:400],
                }
    return {
        "类别": "说不清（默认最保守）",
        "动作": "未知",
        "可自动重试": False,
        "快速失败": False,
        "说明": "账本认不出这个错误属于哪一类，按铁律一律当「说不清」处理，"
                "宁可停下来问人，也不许自动重试一笔可能已经花掉的调用。",
        "下一步": "人工判断：能确定没送达 → 记失败()；否则 → 记未知()",
        "存疑": True,
        "原文": 文[:400],
    }


def 建议(错, 连败: int = 0) -> dict:
    """重试策略（人话版）：抖动 → 退避重试；服务真没起 → 快速失败。

    返回 {动作, 等待秒, 类别, 原因}，动作 ∈ {重试, 退避后重试, 未知, 停}

    退避是「指数退避 + 封顶」，且**永远不封顶次数** —— 连败太多就由调用方
    自己决定是不是该停了（账本只给建议，不给次数上限）。
    """
    v = 分类异常(错)
    动 = v["动作"]
    if 动 == "停":
        return {"动作": "停", "等待秒": 0, "类别": v["类别"],
                "原因": f"{v['类别']}：{v['说明']}{v['下一步']}（重试也是白搭，别浪费退避时间）"}
    if 动 == "退避后重试":
        if v["类别"] == "对端宕机/限流":
            等 = min(60.0, 5.0 * (2 ** min(连败, 4)))
            因 = f"{v['类别']}：对端在恢复期，退避 {等:.0f} 秒再试（第 {连败 + 1} 次）；连续失败就别硬撑"
        else:
            等 = min(30.0, 2.0 * (2 ** min(连败, 4))) if 连败 else 0.0
            因 = (f"{v['类别']}：明确失败，"
                  + (f"退避 {等:.0f} 秒后重试第 {连败 + 1} 次" if 等 else "可以直接重试"))
        return {"动作": "退避后重试" if 等 else "重试", "等待秒": round(等, 1),
                "类别": v["类别"], "原因": 因}
    return {"动作": "未知", "等待秒": 0, "类别": v["类别"],
            "原因": f"{v['类别']}：{v['说明']}停在这里，交人工核对。"}


# ───────────────────────────── 模块级门面 ─────────────────────────────

_默认: 账本 | None = None


def 取账本(路: str | None = None) -> 账本:
    """拿一个账本（默认单例）。"""
    global _默认
    if 路 is not None:
        return 账本(路)
    if _默认 is None:
        _默认 = 账本()
    return _默认


def 新建(*a, **kw) -> str:
    return 取账本().新建(*a, **kw)


def 开始(任务id: str, **kw) -> dict:
    return 取账本().开始(任务id, **kw)


def 记完成(任务id: str, **kw) -> dict:
    """模块级门面。叫「记完成」而不是「完成」，是为了不和模块常量 完成 撞名 ——
    在函数自己作用域里，裸名 完成 只会解析成形参，不会解析成状态常量。"""
    return 取账本().完成(任务id, **kw)


def 记失败(任务id: str, **kw) -> dict:
    return 取账本().失败(任务id, **kw)


def 记未知(任务id: str, **kw) -> dict:
    return 取账本().未知(任务id, **kw)


def 记取消(任务id: str, **kw) -> dict:
    return 取账本().取消(任务id, **kw)


def 重试(任务id: str, **kw) -> str:
    return 取账本().重试(任务id, **kw)


def 恢复(任务id: str, **kw) -> dict:
    return 取账本().恢复(任务id, **kw)


def 未知因为(任务id: str, 错, **kw) -> dict:
    return 取账本().未知因为(任务id, 错, **kw)


def 对账(任务id: str, **kw) -> dict:
    return 取账本().对账(任务id, **kw)


def 未完成(戏名: str = "") -> list[dict]:
    return 取账本().未完成(戏名)


def 待人工(戏名: str = "") -> list[dict]:
    return 取账本().待人工(戏名)


def 取(任务id: str) -> dict | None:
    return 取账本().取(任务id)


def 列表(**kw) -> list[dict]:
    return 取账本().列表(**kw)


def 统计(戏名: str = "") -> dict:
    return 取账本().统计(戏名)


def 预估(类型: str, 数量: int = 1, **kw) -> dict:
    return 取账本().预估(类型, 数量, **kw)


def 闸门() -> dict:
    return 取账本().闸门()


def 置上限(n: int) -> int:
    return 取账本().置上限(n)


def 领取(任务id: str) -> dict:
    return 取账本().领取(任务id)


def 释放(任务id: str, **kw) -> dict:
    return 取账本().释放(任务id, **kw)


def 可重试(任务id: str) -> tuple[bool, str]:
    return 取账本().可重试(任务id)


# ───────────────────────────── 自查 ─────────────────────────────


def _隔离账本(tag: str = "") -> 账本:
    路 = os.path.join(
        作品根, "_账本", f"_自查_{tag or ''}{os.getpid()}_{int(time.time() * 1000)}.db"
    )
    return 账本(路)


def 自查(悄悄: bool = False) -> int:
    """跑一遍内部自检。全过 → 0；有任何一条不过 → 1。"""
    行: list[str] = []

    def 说(s=""):
        行.append(s)
        if not 悄悄:
            print(s)

    def 检查(名: str, 过: bool, 补充: str = ""):
        说(f"  [{'✓' if 过 else '✗'}] {名}" + (f"　{补充}" if 补充 else ""))
        return 过

    好 = True
    L = None
    try:
        L = _隔离账本("自我检查")
        说(f"任务账本 · 自查　（临时库 {L.路}）")

        # 1 基础往返
        a = L.新建("出图", 戏名="自查戏", 格号="1", 估算成本=1, 输入={"提示词": "x"})
        好 = 检查("新建 → 排队", L.取(a)["状态"] == 排队, a) and 好
        好 = 检查("输入摘要非空", bool(L.取(a)["输入摘要"])) and 好
        L.领取(a)
        t = L.取(a)
        好 = 检查("领取 → 运行 且记开始时间/尝试次数", t["状态"] == 运行 and t["尝试次数"] == 1) and 好
        L.完成(a, 输出路径="作品/自查/01_格1.png", 实际成本=1)
        t = L.取(a)
        好 = 检查("完成 → 终态 + 用时", t["状态"] == 完成 and t["用时"] is not None) and 好

        # 2 状态机不许乱跳
        try:
            L.领取(a)
            好 = 检查("完成态不能再领取", False, "竟然过了") and 好
        except 状态非法:
            好 = 检查("完成态不能再领取（状态机挡住）", True) and 好

        # 3 未知态拒绝重试（铁律）
        b = L.新建("出片", 戏名="自查戏", 镜头="锚1", 估算成本=60)
        L.领取(b)
        L.未知(b, 因="等了 3600 秒还没跑完（提示号 abc12345）", 可能已计费=True)
        t = L.取(b)
        好 = 检查("未知 → 终态且可能已计费=True", t["状态"] == 未知 and t["可能已计费"]) and 好
        try:
            L.重试(b)
            好 = 检查("★ 未知态重试被拒（铁律）", False, "竟然重试了！") and 好
        except 需人工核对 as e:
            话 = str(e)
            过了 = all(k in 话 for k in ("去哪查", "查什么", "怎么办", "可能已计费"))
            好 = 检查("★ 未知态重试抛 需人工核对 且说人话", 过了,
                       f"消息 {len(话)} 字") and 好
        好 = 检查("未知态不接自动迁移", 未知 not in _迁移表[未知] and _迁移表[未知] == ()) and 好
        好 = 检查("未知态不在 未完成() 里（它等人工，不是断点）",
                   b not in [x["id"] for x in L.未完成()]) and 好
        好 = 检查("未知态出现在 待人工() 里", b in [x["id"] for x in L.待人工()]) and 好

        # 4 恢复：人工核对后标回可继续
        L.恢复(b, 备注="自查：供应商后台确认没跑")
        t = L.取(b)
        好 = 检查("恢复 → 回排队、清可能已计费",
                   t["状态"] == 排队 and t["可能已计费"] == 0) and 好

        # 5 明确失败 → 可退避重试，且重试链接得上
        c = L.新建("出图", 戏名="自查戏", 格号="2", 估算成本=1)
        L.领取(c)
        L.失败(c, 错="ComfyUI 工作流跑挂了：{'error': 'OOM'}")
        v = 分类异常("ComfyUI 工作流跑挂了：{'error': 'OOM'}")
        好 = 检查("明确失败 → 动作=退避后重试（可自动重试）",
                   v["动作"] == "退避后重试" and v["可自动重试"] and not v["快速失败"]) and 好
        能, 理 = L.可重试(c)
        好 = 检查("可重试() 对明确失败放行", 能, 理[:60]) and 好
        d = L.重试(c)
        t = L.取(d)
        好 = 检查("重试开新任务并接父链",
                   t["重试自"] == c and L.取(c)["重试链"] == d) and 好

        # 6 抖动 vs 服务没起 vs 说不清
        v1 = 建议("ComfyUI 工作流跑挂了：xxx", 连败=0)
        v2 = 建议("ComfyUI 工作流跑挂了：xxx", 连败=3)
        v3 = 建议("连不上 ComfyUI（http://127.0.0.1:8188）：Connection refused")
        v4 = 建议("等了 1800 秒还没跑完（提示号 1a2b3c）")
        v5 = 建议("某个我从来没见过的怪错")
        v6 = 建议("ComfyUI 返回 503：Service Unavailable")
        好 = 检查("首次抖动 → 直接重试", v1["动作"] == "重试" and v1["等待秒"] == 0) and 好
        好 = 检查("连续抖动 → 退避加长", v2["动作"] == "退避后重试" and v2["等待秒"] > v1["等待秒"]) and 好
        好 = 检查("连不上 → 快速失败（不退避）", v3["动作"] == "停" and v3["等待秒"] == 0) and 好
        好 = 检查("超时 → 建议进未知态（不自动重试）", v4["动作"] == "未知") and 好
        好 = 检查("认不出的错 → 默认最保守（未知）", v5["动作"] == "未知") and 好
        好 = 检查("503 → 退避重试", v6["动作"] == "退避后重试" and v6["等待秒"] > 0) and 好
        好 = 检查("分类器自洽（动作与两个布尔位一致）",
                   all(
                       (分类异常(x)["动作"] == "退避后重试") == 分类异常(x)["可自动重试"]
                       and (分类异常(x)["动作"] == "停") == 分类异常(x)["快速失败"]
                       for x in ("连不上 ComfyUI", "超时", "工作流跑挂了", "怪错", " 401")
                   )) and 好

        # 6b 连不上 → 快速失败，且不给自动重试
        c2 = L.新建("出图", 戏名="自查戏", 格号="3")
        L.领取(c2)
        L.失败(c2, 错="连不上 ComfyUI（http://127.0.0.1:8188）：Connection refused")
        能2, 理2 = L.可重试(c2)
        好 = 检查("服务没起 → 可重试() 说不（快速失败）", not 能2, 理2.splitlines()[0][:60]) and 好

        # 7 并发闸门
        L.置上限(1)
        好 = 检查("默认并发上限 1", L.取上限() == 1) and 好
        e1 = L.新建("出图", 戏名="自查戏")
        e2 = L.新建("出图", 戏名="自查戏")
        L.领取(e1)
        try:
            L.领取(e2)
            好 = 检查("闸门满时第二条被挡", False, "竟然放行了") and 好
        except 闸门满:
            好 = 检查("闸门满 → 抛 闸门满 且任务留排队", L.取(e2)["状态"] == 排队) and 好
        L.完成(e1, 输出路径="x.png", 实际成本=1)
        L.领取(e2)
        好 = 检查("前一个跑完 → 闸门放行", L.取(e2)["状态"] == 运行) and 好
        L.完成(e2, 输出路径="y.png", 实际成本=1)
        L.置上限(2)
        好 = 检查("上限可配置", L.取上限() == 2) and 好
        L.置上限(1)

        # 8 原子快照
        快 = L.快照()
        好 = 检查("快照落盘（.tmp 已被 os.replace 换走）",
                   os.path.exists(快) and not os.path.exists(L.路 + ".tmp")) and 好
        测 = sqlite3.connect(快)
        n = 测.execute("SELECT COUNT(*) FROM 任务").fetchone()[0]
        测.close()
        好 = 检查("快照内容完整且能读", n == L.统计()["总数"], f"{n} 条") and 好

        # 9 自愈：喂一个坏备份 + 喂一个坏库
        坏库 = L.路 + ".坏测试.db"
        with open(坏库, "wb") as f:
            f.write(b"this is definitely not a sqlite file" * 10)
        坏路 = os.path.join(
            作品根, "_账本", f"_自查_坏_{os.getpid()}_{int(time.time() * 1000)}.db"
        )
        os.replace(坏库, 坏路)
        import shutil

        shutil.copy2(快, 坏路 + ".bak")            # .bak 位置放一份真备份
        with open(坏路, "wb") as f:                # 再把主库砸坏
            f.write(b"NOT A DATABASE" * 100)
        L2 = 账本(坏路, 自动快照=False)
        n2 = L2.统计()["总数"]
        好 = 检查("库坏了 → 自动隔离并拿 .bak 恢复", n2 == n, f"恢复出 {n2} 条（原 {n} 条）") and 好
        好 = 检查("坏文件被留下来（不静默丢）",
                   any(x.startswith(os.path.basename(坏路) + ".坏.") for x in os.listdir(os.path.dirname(坏路)))) and 好
        L2.关()
        for p in (坏路, 坏路 + ".bak"):
            if os.path.exists(p):
                os.remove(p)

        # 10 成本预告
        # 注意别把「算出来是 0.0」当成 bug：预估的秒数来自**本库的实测均值**，
        # 而自查库里那些出片任务的「用时」都是毫秒级（根本没真跑），
        # 四舍五入到 3 位小数就是 0.0。这里要验的是**算法**没坏、来源标注对：
        #   ① 数字是数、不是 NaN/负；
        #   ② 依据字段老实标了是实测还是估算；
        #   ③ 说明里写了算法与数据来源；
        #   ④ 没有实测样本时，必须退回基线估算（不能拿 0 当均值）。
        预 = L.预估("出片", 2, 帧数=49)
        好 = 检查("预估给数（可以为 0，但不能是负/NaN）",
                   isinstance(预["积分"], (int, float)) and 预["积分"] >= 0
                   and isinstance(预["秒"], (int, float)) and 预["秒"] >= 0,
                   f"{预['积分']} 积分 / {预['秒']} 秒 / {预['金额']} 元 · {预['依据']}") and 好
        好 = 检查("预估标明了依据（估算 or 实测均值）",
                   预["依据"] in ("实测均值", "实测均值（样本少）", "基线估算",
                                  "设计意图估算", "基线+实测混合"),
                   f"依据={预['依据']}　样本={预['分项'].get('实测样本')}") and 好
        好 = 检查("预估说明里带了算法与数据来源", "来源" in 预["说明"] and "电费" in 预["说明"]) and 好
        预生 = L.预估("从来没记过账的类型", 1)
        好 = 检查("没样本的类型 → 退回基线估算（不拿 0 当均值）",
                   预生["分项"].get("实测样本") == 0 and 预生["依据"] in ("基线估算", "设计意图估算"),
                   f"{预生['依据']} · 单件 {预生['单件秒']} 秒") and 好
        预多 = L.预估("出片", 500, 帧数=49)
        好 = 检查("数量放大后数字跟着放大（线性）",
                   预多["积分"] >= 预["积分"] and 预多["秒"] > 预["秒"],
                   f"2 段 {预['秒']}s → 500 段 {预多['秒']}s") and 好
        L.关()
        L = None
        好 = 检查("收工后连接已关", True) and 好
    except Exception as e:
        import traceback

        说(f"  [✗] 自查自己抛了异常：{type(e).__name__}: {e}")
        说(traceback.format_exc())
        好 = False
    finally:
        if L is not None:
            try:
                L.关()
            except Exception:
                pass

    说("")
    说(("✓ 自查全过 —— 账本可用。" if 好 else "✗ 自查有不过的项，看上面 [✗]。"))
    return 0 if 好 else 1


# ───────────────────────────── 命令行 ─────────────────────────────


def _拿参(argv: list[str], 名: str, 默认=None):
    for i, a in enumerate(argv):
        if a == 名:
            return argv[i + 1] if i + 1 < len(argv) else 默认
        if a.startswith(名 + "="):
            return a.split("=", 1)[1]
    return 默认


def _有开关(argv: list[str], 名: str) -> bool:
    return 名 in argv


# 会「吃掉下一个参数」的选项。写全了，位置参数才不会被它们的值顶包。
_吃一格的选项 = (
    "--库", "--状态", "--戏名", "--类型", "--限", "--估算成本", "--输入摘要",
    "--备注", "--错", "--因", "--供应商任务号", "--输出", "--实际成本",
    "--结果", "--产物", "--模板", "--宽", "--高", "--帧数", "--步数", "--上限",
)


def _位置参(argv: list[str]) -> list[str]:
    """挑出真正的**位置参数**（id / 类型 / 数量）。

    反例：`账本.py 对账 --库 X <id>` —— 朴素的「不以 - 开头就当位置参数」会把
    库路径 X 当成 id，然后报「找不到任务 X」，人看着一脸问号。
    """
    出 = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _吃一格的选项:
            i += 2
            continue
        if any(a.startswith(o + "=") for o in _吃一格的选项):
            i += 1
            continue
        if a.startswith("-"):
            i += 1                      # 开关（--强开 / --可能已计费 …），不吃值
            continue
        出.append(a)
        i += 1
    return 出


def _打印表(行们: list[dict], 列: list[tuple[str, str, int]] | None = None) -> None:
    if not 行们:
        print("（没有匹配的账）")
        return
    if 列 is None:
        列 = [("id", "id", 16), ("类型", "类型", 12), ("戏名", "戏名", 16),
              ("镜头", "镜头", 8), ("格号", "格号", 5), ("状态", "状态", 6),
              ("尝试次数", "试", 3), ("用时", "用时", 8), ("实际成本", "实", 6),
              ("创建时间", "创建", 19)]
    宽 = [c[2] for c in 列]
    print("  ".join(f"{c[1]:<{w}}" for c, w in zip(列, 宽)))
    for r in 行们:
        格 = []
        for (键, _标, w) in 列:
            v = r.get(键)
            if 键 == "可能已计费":
                v = "是" if v else ""
            if v is None:
                v = ""
            s = str(v)
            格.append(f"{s[:w]:<{w}}")
        print("  ".join(格))


def _核对指引(L: 账本, t: dict) -> str:
    """给一条「未知」账生成人话核对指引。

    直接复用 需人工核对 异常的那三段（【去哪查】【查什么】【怎么办】）——
    指引只有一处实现，以后改的时候不会两边走偏。
    """
    return str(需人工核对(t, L.供应商(t), t.get("错误") or ""))


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help", "帮", "用法"):
        print(__doc__)
        return 0
    命 = argv[1]
    余 = argv[2:]

    if 命 == "自查":
        return 自查()

    路 = _拿参(余, "--库")
    L = 取账本(路)
    try:
        if 命 == "列表":
            if _拿参(余, "--状态") == "待人工":
                行们 = L.待人工(_拿参(余, "--戏名", "") or "")
            else:
                行们 = L.列表(
                    状态=_拿参(余, "--状态", "") or "",
                    戏名=_拿参(余, "--戏名", "") or "",
                    类型=_拿参(余, "--类型", "") or "",
                    限=int(_拿参(余, "--限", 0) or 0),
                )
            _打印表(行们)
            g = L.闸门()
            print(f"\n闸门 {g['在跑']}/{g['上限']} 在跑，{g['排队']} 条排队")
            return 0

        if 命 == "新建":
            位 = _位置参(余)
            类型 = _拿参(余, "--类型") or (位[0] if 位 else None)
            if not 类型:
                print("用法：账本.py 新建 --类型 出图 [--戏名 Y] [--镜头 A] [--格号 1] [--估算成本 1] [--输入摘要 …]")
                return 2
            估 = _拿参(余, "--估算成本")
            rid = L.新建(
                类型,
                戏名=_拿参(余, "--戏名", "") or "",
                镜头=_拿参(余, "--镜头", "") or "",
                格号=_拿参(余, "--格号", "") or "",
                估算成本=float(估) if 估 is not None else None,
                输入=_拿参(余, "--输入摘要"),
                备注=_拿参(余, "--备注", "") or "",
            )
            print(rid)
            return 0

        if 命 in ("领取", "开始", "完成", "失败", "未知", "取消", "恢复", "重试", "释放"):
            位 = _位置参(余)
            if not 位:
                print(f"用法：账本.py {命} <id> [选项]")
                return 2
            rid = 位[0]
            if 命 == "领取":
                t = L.领取(rid)
            elif 命 == "开始":
                t = L.开始(rid, 供应商任务号=_拿参(余, "--供应商任务号", "") or "")
            elif 命 == "完成":
                实 = _拿参(余, "--实际成本")
                t = L.完成(rid, 输出路径=_拿参(余, "--输出", "") or "",
                           实际成本=float(实) if 实 is not None else None)
            elif 命 == "失败":
                错文 = _拿参(余, "--错", "") or ""
                if not 错文:
                    print('用法：账本.py 失败 <id> --错 "原因"')
                    return 2
                实 = _拿参(余, "--实际成本")
                t = L.失败(rid, 错=错文, 实际成本=float(实) if 实 is not None else None)
            elif 命 == "未知":
                因 = _拿参(余, "--因", "") or ""
                if not 因:
                    print('用法：账本.py 未知 <id> --因 "为什么说不清" [--可能已计费]')
                    return 2
                t = L.未知(rid, 因=因,
                           可能已计费=not _有开关(余, "--不可能已计费"),
                           供应商任务号=_拿参(余, "--供应商任务号", "") or "")
            elif 命 == "取消":
                t = L.取消(rid, 因=_拿参(余, "--因", "") or "")
            elif 命 == "恢复":
                t = L.恢复(rid, 备注=_拿参(余, "--备注", "人工核对后恢复") or "人工核对后恢复")
            elif 命 == "释放":
                实 = _拿参(余, "--实际成本")
                t = L.释放(rid, 输出路径=_拿参(余, "--输出", "") or "",
                           实际成本=float(实) if 实 is not None else None)
            else:
                try:
                    新id = L.重试(rid, 强开=_有开关(余, "--强开"))
                except 需人工核对 as e:
                    print(str(e))
                    return 3
                print(新id)
                return 0
            print(json.dumps({k: v for k, v in t.items() if v not in (None, "")},
                             ensure_ascii=False, indent=2))
            return 0

        if 命 == "未完成":
            行们 = L.未完成(_拿参(余, "--戏名", "") or "")
            _打印表(行们)
            待 = L.待人工(_拿参(余, "--戏名", "") or "")
            if 待:
                print(f"\n★ 另有 {len(待)} 条卡在「未知」态（可能已计费，等人工核对）：")
                _打印表(待)
                print(f"\n  去看：去供应商后台拿提示号逐个查，查完 python 账本.py 对账 --结果 成了|没成 结掉")
            if not 行们 and not 待:
                print("✓ 没有断点：账本里没有排队/运行中的活。")
            return 0

        if 命 == "对账":
            位 = _位置参(余)
            结果 = _拿参(余, "--结果", "") or ""
            if not 位:
                待 = L.待人工(_拿参(余, "--戏名", "") or "")
                if not 待:
                    print("✓ 没有等人工核对的账（「未知」态是空的）。")
                    return 0
                print(f"★ {len(待)} 条「未知」账等人工核对 —— "
                      f"拿供应商任务号/提示号去后台查，查完用 --结果 结掉：")
                _打印表(待)
                for t in 待:
                    print()
                    print(_核对指引(L, t))
                return 0
            rid = 位[0]
            if not 结果:
                print(_核对指引(L, L._必须(rid)))
                print()
                print("查完了就这么结（对账是「未知」态唯一的出口）：")
                print(f"  真跑出来了  python 账本.py 对账 {rid} --结果 成了 --产物 <输出路径>")
                print(f"  确实没跑成  python 账本.py 对账 {rid} --结果 没成")
                return 0
            if 结果 not in ("成了", "没成"):
                print("用法：账本.py 对账 <id> --结果 成了 --产物 <路径> [--实际成本 N] [--备注 …]")
                print("     账本.py 对账 <id> --结果 没成 [--备注 …]")
                print("     账本.py 对账                     ← 列出所有等人工核对的账 + 逐条指引")
                return 2
            实 = _拿参(余, "--实际成本")
            t = L.对账(rid, 结果=结果,
                       产物=_拿参(余, "--产物", "") or "",
                       备注=_拿参(余, "--备注", "") or "",
                       实际成本=float(实) if 实 is not None else None)
            print(json.dumps({k: v for k, v in t.items() if v not in (None, "")},
                             ensure_ascii=False, indent=2))
            if 结果 == "成了":
                print("✓ 已结到「完成」，产物记在 输出路径 上。")
            else:
                print(f"✓ 已结到「失败」，并清掉「可能已计费」。接着跑：python 账本.py 重试 {rid}")
            return 0

        if 命 == "待人工":
            行们 = L.待人工(_拿参(余, "--戏名", "") or "")
            _打印表(行们)
            if not 行们:
                print("✓ 没有等人工核对的账（「未知」态是空的）。")
            else:
                print(f"\n★ 这 {len(行们)} 条要人去看供应商后台："
                      f"python 账本.py 对账   （会连着核对指引一起打出来）")
            return 0

        if 命 == "统计":
            s = L.统计(_拿参(余, "--戏名", "") or "")
            print(json.dumps(s, ensure_ascii=False, indent=2))
            if s["待人工"]:
                print(f"\n★ 有 {s['待人工']} 条「未知」账等人工核对：python 账本.py 对账   （连核对指引一起打出来）")
            return 0

        if 命 == "预估":
            位 = _位置参(余)
            if len(位) < 2:
                print("用法：账本.py 预估 <类型> <数量> [--模板 T] [--宽 W] [--高 H] [--帧数 F] [--步数 S]")
                print("      类型：" + "、".join(计价表))
                return 2
            类型, 量 = 位[0], int(位[1])
            r = L.预估(类型, 量,
                       模板=_拿参(余, "--模板", "") or "",
                       宽=int(_拿参(余, "--宽", 0) or 0),
                       高=int(_拿参(余, "--高", 0) or 0),
                       帧数=int(_拿参(余, "--帧数", 0) or 0),
                       步数=int(_拿参(余, "--步数", 0) or 0))
            print(r["说明"])
            print(json.dumps({k: v for k, v in r.items() if k != "说明"},
                             ensure_ascii=False, indent=2))
            return 0

        if 命 == "闸门":
            上限 = _拿参(余, "--上限")
            if 上限 is not None:
                L.置上限(int(上限))
            g = L.闸门()
            print(f"并发上限 {g['上限']}　在跑 {g['在跑']}　排队 {g['排队']}　还能开 {g['还能开']}")
            return 0

        print(f"不认识的命令：{命}")
        print(__doc__)
        return 2
    except 需人工核对 as e:
        print(str(e))
        return 3
    except (账本错, 状态非法, 找不到任务) as e:
        print(f"✗ {e}")
        return 2
    finally:
        if 命 in ("列表", "未完成", "统计", "闸门") and 路 is None and _默认 is None:
            pass          # 只读且压根没开过库，没什么可收的
        try:
            L.关()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv))
