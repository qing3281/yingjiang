# -*- coding: utf-8 -*-
"""
影匠 · 剧组 —— 制片人的手：把整条流水线按顺序推下去
================================================================
我**不写提示词、不审片**（那是分镜师和导演的活）。我只做四件事：

    判阶段（读作品目录） → 派活（调 导演.py / 拼图.py）
        → 卡门（看片记录里没 PASS 就停） → 收尾（写 剧集进度.md）

一部戏的目录长这样：

    作品/<戏名>/
    ├─ 剧本.md                 用户给
    ├─ 01-节拍拆解.md           分镜师
    ├─ 02-九宫格.md             分镜师
    ├─ 03-四宫格.md             分镜师
    ├─ 04-动态提示词.md         动画师
    ├─ 看片记录.md              导演
    ├─ 剧集进度.md              本程序
    ├─ 01_格1.png … 01_格9.png  放映员（九宫格）
    ├─ 03_锚1格1.png …          放映员（四宫格）
    ├─ 04_锚1格1.mp4 …          放映员（成片）
    ├─ _看片表.png              拼图.py
    └─ _渲染日志.tsv            本程序（每次真渲染记一行，进度用它算耗时）

命令：

    python 剧组.py 检查       <戏名>
    python 剧组.py 出图       <戏名> [格号…]   [--重做] [--空跑]
    python 剧组.py 出图四宫格 <戏名> [锚号…]   [--重做] [--空跑]
    python 剧组.py 出片       <戏名> [锚号…]   [--重做] [--空跑]
    python 剧组.py 拼图       <戏名> [--每行 N]
    python 剧组.py 进度       <戏名>
    python 剧组.py 全部       <戏名> [--强跑] [--空跑]

约定：
  · 所有渲染都走 导演.py 的门面（立戏 / 定角 / 开镜 / 让镜动），
    不绕过它直接调 引擎.py（拼图除外，那是纯本地拼版）。
  · 解析产物时，任何认不出的行都会连**行号 + 原文**一起报出来，绝不静默跳过。
  · 文件一律 UTF-8 读写。
"""

import glob
import os
import re
import subprocess
import sys
import time
import unicodedata

# ── 输出：Windows 控制台/管道默认是 GBK，✓ ✗ ⚠ ▶ 会直接 UnicodeEncodeError。
#    这里把标准输出改成 UTF-8（改不了就退回替换字符，反正不能让打印把程序打死）。
for _流 in (sys.stdout, sys.stderr):
    try:
        _流.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

这里 = os.path.dirname(os.path.abspath(__file__))
作品根 = os.path.join(这里, "作品")
if 这里 not in sys.path:
    sys.path.insert(0, 这里)

import 导演      # noqa: E402  同目录中文模块，直接 import
import 角色库    # noqa: E402
import 风格库    # noqa: E402

U8 = "utf-8"

# 文件名
F_剧本 = "剧本.md"
F_节拍 = "01-节拍拆解.md"
F_九宫 = "02-九宫格.md"
F_四宫 = "03-四宫格.md"
F_动态 = "04-动态提示词.md"
F_看片 = "看片记录.md"
F_进度 = "剧集进度.md"
F_看片表 = "_看片表.png"
F_日志 = "_渲染日志.tsv"


# ============================================================
# 一、小工具
# ============================================================

def 安全名(s):
    """和 导演._安全名 同一套规则 —— 保证算出来的是同一个目录。"""
    for c in '\\/:*?"<>|':
        s = s.replace(c, "_")
    return s.strip() or "未命名"


def 戏目录(戏名):
    return os.path.join(作品根, 安全名(戏名))


def 读行(路径):
    with open(路径, "r", encoding=U8) as f:
        return f.read().splitlines()


def 写文(路径, 文字):
    os.makedirs(os.path.dirname(路径), exist_ok=True)
    with open(路径, "w", encoding=U8) as f:
        f.write(文字)


def 宽(s):
    """按显示宽度算（中文算 2 格），这样表格对得齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def 排(s, n):
    return s + " " * max(0, n - 宽(s))


def 大小(字节):
    if 字节 < 1024:
        return f"{字节} B"
    if 字节 < 1024 ** 2:
        return f"{字节 / 1024:.1f} KB"
    return f"{字节 / 1024 ** 2:.1f} MB"


def 时长(秒):
    if 秒 < 60:
        return f"{秒:.1f} 秒"
    return f"{秒 / 60:.1f} 分（{秒:.0f} 秒）"


def 时刻(时间戳):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(时间戳))


def 头(标题):
    print()
    print("═" * 64)
    print(f"  {标题}")
    print("═" * 64)


def 报(s):
    print(f"✓ {s}")


def 警(s):
    print(f"⚠ {s}")


def 错(s):
    print(f"✗ {s}")


def 打告警(告警们):
    """把解析告警印出来 —— 认不出的行必须见光。"""
    if not 告警们:
        return
    print(f"\n⚠ 解析告警 {len(告警们)} 条：")
    for a in 告警们:
        if a.get("行"):
            print(f"   ⚠ 第 {a['行']} 行：{a['说明']}")
            print(f"        原文：{a['原文']}")
        else:
            print(f"   ⚠ {a['说明']}")


def 记日志(目录, 命令, 对象, 秒, 状态, 备注=""):
    """往 _渲染日志.tsv 追加一行。剧集进度.md 的「总耗时」就靠它。"""
    路 = os.path.join(目录, F_日志)
    新 = not os.path.exists(路)
    with open(路, "a", encoding=U8) as f:
        if 新:
            f.write("时间\t命令\t对象\t耗时秒\t状态\t备注\n")
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{命令}\t{对象}\t{秒:.1f}\t{状态}\t{备注}\n")


def 读日志(目录):
    路 = os.path.join(目录, F_日志)
    if not os.path.exists(路):
        return []
    出 = []
    for 行 in 读行(路)[1:]:
        格 = 行.split("\t")
        if len(格) < 5:
            continue
        try:
            秒 = float(格[3])
        except ValueError:
            秒 = 0.0
        出.append({"时间": 格[0], "命令": 格[1], "对象": 格[2], "秒": 秒,
                   "状态": 格[4], "备注": 格[5] if len(格) > 5 else ""})
    return 出


# ============================================================
# 二、解析器
# ============================================================
# 格式契约（另一个 agent 写的模板已锁定，这里按它解析）：
#
#   02-九宫格.md    ## 角色卡 / ## 视觉规范 / ## 格N —— 标题 + 字段
#   03-四宫格.md    ## 锚点N —— 标题 + 字段 / ### A-B 起手|推进|冲突|落点 + 字段
#   04-动态提示词.md ## 锚点N —— 标题 / ### A-B 关键帧|起手|推进|冲突|落点 + 字段
#
# 字段行 = `- 键：值`（中英文冒号都认）；缩进 2 格以上的下一行算**续写**。

# 注意：标题必须写成「# 空格 标题」。**不能**写成 ^#\s*(.+)$ —— 那样 "## 格1 —— 标题"
# 会被当成标题吃掉（井号后面接井号，.+ 也能吞），结果所有格子都解析不出来。踩过。
_标题行 = re.compile(r"^#\s+(\S.*?)\s*$")
_段头 = re.compile(r"^##\s*(.+?)\s*$")
_格头 = re.compile(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$")
_锚头 = re.compile(r"^##\s*锚点\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$")
_子头 = re.compile(r"^###\s*(\d+)\s*-\s*(\d+)\s*(.*)$")
_字段行 = re.compile(r"^-\s*([^:：]{1,12}?)\s*[:：]\s*(.*)$")
_续行 = re.compile(r"^\s{2,}(\S.*)$")

格字段 = ("目的", "景别", "机位", "提示词", "重点")
四锚字段 = ("继承自", "人物", "场景", "光色")
四格字段 = ("提示词", "变化说明")
动格字段 = ("动作", "强度")
四格名们 = ("起手", "推进", "冲突", "落点")
动格名们 = ("关键帧", "起手", "推进", "冲突", "落点")

# 可选字段：认得（所以**不报**「不认识」的警告），也不参与必填校验。
# 例外：动态提示词里的【帧数】会被「出片」真的采纳（不给就按 49 帧）。
格可选 = ("光色", "色调", "风格", "备注", "说明")
四锚可选 = ("风格", "备注", "说明")
四格可选 = ("重点", "备注", "说明")
动格可选 = ("帧数", "时长", "备注", "说明")

# 宽容格式：角色卡 / 视觉规范 里允许不写前导「- 」（老样例就是这么写的）
_裸字段行 = re.compile(r"^([^\s:：]{1,12})[:：]\s*(.+)$")


def _标题戏名(标题):
    """从「# 九宫格 · 试镜（临时样例）」里抠戏名 —— 取 · 后面那一段，去掉括号备注。"""
    段 = [x.strip() for x in re.split(r"[·•]", 标题 or "") if x.strip()]
    名 = 段[1] if len(段) > 1 else (段[0] if 段 else "")
    return re.split(r"[（(]", 名)[0].strip()


class 解析本:
    """一张产物纸的解析过程：记行号、收告警。"""

    def __init__(self, 路径):
        self.路径 = 路径
        self.名叫 = os.path.basename(路径)
        self.存在 = os.path.exists(路径)
        self.行们 = 读行(路径) if self.存在 else []
        self.告警 = []

    def 警(self, 号, 原文, 说明):
        self.告警.append({"行": 号, "原文": (原文 or "").strip(), "说明": 说明})


def _收(本, 果):
    果["告警"] = 本.告警
    return 果


def _填(目标, 键, 值, 号):
    """字段赋值：值累加（同一字段写两次也不丢）。"""
    if 目标.get(键):
        目标[键] = f"{目标[键]} {值}".strip()
    else:
        目标[键] = 值
    目标.setdefault("字段行", {})[键] = 号


def 解析九宫格(路径):
    """读 02-九宫格.md → {戏名, 角色卡, 视觉规范, 格们, 告警}。"""
    本 = 解析本(路径)
    果 = {"戏名": "", "角色卡": [], "视觉规范": {}, "格们": [], "告警": [], "本": 本}
    if not 本.存在:
        本.警(0, "", f"文件不存在：{路径}")
        return _收(本, 果)

    段 = ""
    格 = None
    键 = None          # ("格"|"卡"|"规范", 落点) —— 续写接给谁
    for 号, 原 in enumerate(本.行们, 1):
        行 = 原.rstrip()
        if not 行.strip():
            continue

        # 顺序要紧：先认具体的（## 格N / ## 段名），最后才轮到一句话标题
        m = _格头.match(行)
        if m:
            格 = {"号": int(m.group(1)), "标题": m.group(2).strip(), "行": 号,
                   "字段行": {}}
            for k in 格字段:
                格[k] = ""
            果["格们"].append(格)
            段, 键 = "格", None
            continue

        m = _段头.match(行)
        if m:
            名 = m.group(1).strip()
            if 名 in ("角色卡", "视觉规范"):
                段, 键 = 名, None
            else:
                段, 键 = "其他", None
                本.警(号, 原, f"不认识的段落标题「{名}」（只认「角色卡」「视觉规范」和「## 格N —— 标题」）")
            continue

        m = _标题行.match(行)
        if m:
            果["戏名"] = _标题戏名(m.group(1))
            键 = None
            continue

        m = _字段行.match(行)
        if m:
            名, 值 = m.group(1).strip(), m.group(2).strip()
            if 段 == "角色卡":
                果["角色卡"].append({"名": 名, "描述": 值, "行": 号})
                键 = ("卡", len(果["角色卡"]) - 1)
                continue
            if 段 == "视觉规范":
                果["视觉规范"][名] = 值
                键 = ("规范", 名)
                continue
            if 段 == "格" and 格 is not None:
                if 名 in 格字段 or 名 in 格可选:
                    _填(格, 名, 值, 号)
                    键 = ("格", 名)
                else:
                    本.警(号, 原, f"格{格['号']} 里不认识的字段「{名}」"
                                  f"（这个段落只认：{'、'.join(格字段)}）")
                    键 = None
                continue
            if 段 == "其他":
                本.警(号, 原, f"字段「{名}」落在不认识的段落里")
                键 = None
                continue
            本.警(号, 原, f"字段「{名}」不在任何段落里（是不是漏了 ## 格N 标题？）")
            键 = None
            continue

        # 宽容：角色卡 / 视觉规范 允许不写前导「- 」（老样例是这么写的）
        if 段 in ("角色卡", "视觉规范"):
            m0 = _裸字段行.match(行)
            if m0:
                名, 值 = m0.group(1).strip(), m0.group(2).strip()
                if 段 == "角色卡":
                    果["角色卡"].append({"名": 名, "描述": 值, "行": 号})
                    键 = ("卡", len(果["角色卡"]) - 1)
                else:
                    果["视觉规范"][名] = 值
                    键 = ("规范", 名)
                continue

        m = _续行.match(行)
        if m and 键 is not None:
            新 = m.group(1).strip()
            if 键[0] == "格":
                _填(格, 键[1], 新, 号)
            elif 键[0] == "卡":
                卡 = 果["角色卡"][键[1]]
                卡["描述"] = f"{卡['描述']} {新}".strip()
            else:
                果["视觉规范"][键[1]] = f"{果['视觉规范'][键[1]]} {新}".strip()
            continue

        if m:
            本.警(号, 原, "缩进续写，但上一行不是字段 —— 不知道接给谁")
        else:
            本.警(号, 原, "这一行不是标题 / 字段 / 续写，没人认领")

    见 = {}
    for g in 果["格们"]:
        if g["号"] in 见:
            本.警(g["行"], "", f"格{g['号']} 重复出现（上一次在第 {见[g['号']]} 行）")
        见[g["号"]] = g["行"]
        if not g["提示词"]:
            本.警(g["行"], "", f"格{g['号']} 没有【提示词】—— 出不了图")
        if not g["景别"]:
            本.警(g["行"], "", f"格{g['号']} 没有【景别】—— 会退回风格默认镜头")
    return _收(本, 果)


def 解析四宫格(路径):
    """读 03-四宫格.md → {锚点们, 告警}。"""
    本 = 解析本(路径)
    果 = {"锚点们": [], "告警": [], "本": 本}
    if not 本.存在:
        本.警(0, "", f"文件不存在：{路径}")
        return _收(本, 果)

    段 = ""
    锚 = None
    格 = None
    键 = None
    for 号, 原 in enumerate(本.行们, 1):
        行 = 原.rstrip()
        if not 行.strip():
            continue

        if _标题行.match(行):
            键 = None
            continue

        m = _锚头.match(行)
        if m:
            锚 = {"号": int(m.group(1)), "标题": m.group(2).strip(), "行": 号,
                   "格们": [], "字段行": {}}
            for k in 四锚字段:
                锚[k] = ""
            果["锚点们"].append(锚)
            段, 格, 键 = "锚点", None, None
            continue

        m = _子头.match(行)
        if m and 锚 is not None:
            名 = m.group(3).strip()
            if 名 not in 四格名们:
                本.警(号, 原, f"格名「{名}」不认识（只认：{'、'.join(四格名们)}）")
            格 = {"锚": int(m.group(1)), "号": int(m.group(2)), "名": 名, "行": 号,
                   "字段行": {}}
            for k in 四格字段:
                格[k] = ""
            锚["格们"].append(格)
            段, 键 = "格", None
            continue

        m = _段头.match(行)
        if m:
            段, 键 = "其他", None
            本.警(号, 原, f"不认识的段落标题「{m.group(1).strip()}」"
                          f"（这个文件只认「## 锚点N —— 标题」和「### A-B 格名」）")
            continue

        m = _字段行.match(行)
        if m:
            名, 值 = m.group(1).strip(), m.group(2).strip()
            if 段 == "锚点" and 锚 is not None:
                if 名 in 四锚字段 or 名 in 四锚可选:
                    _填(锚, 名, 值, 号)
                    键 = ("锚", 名)
                else:
                    本.警(号, 原, f"锚点{锚['号']} 里不认识的字段「{名}」"
                                  f"（只认：{'、'.join(四锚字段)}）")
                    键 = None
                continue
            if 段 == "格" and 格 is not None:
                if 名 in 四格字段 or 名 in 四格可选:
                    _填(格, 名, 值, 号)
                    键 = ("格", 名)
                else:
                    本.警(号, 原, f"锚点{格['锚']}-{格['号']} 里不认识的字段「{名}」"
                                  f"（只认：{'、'.join(四格字段)}）")
                    键 = None
                continue
            本.警(号, 原, f"字段「{名}」不在锚点或格里")
            键 = None
            continue

        m = _续行.match(行)
        if m and 键 is not None:
            新 = m.group(1).strip()
            _填(锚 if 键[0] == "锚" else 格, 键[1], 新, 号)
            continue
        if m:
            本.警(号, 原, "缩进续写，但上一行不是字段 —— 不知道接给谁")
        else:
            本.警(号, 原, "这一行不是标题 / 字段 / 续写，没人认领")

    for a in 果["锚点们"]:
        if not a["格们"]:
            本.警(a["行"], "", f"锚点{a['号']} 下面一格都没有")
        for g in a["格们"]:
            if not g["提示词"]:
                本.警(g["行"], "", f"锚点{a['号']}-{g['号']}（{g['名']}）没有【提示词】")
    return _收(本, 果)


def 解析动态(路径):
    """读 04-动态提示词.md → {锚点们, 告警}。"""
    本 = 解析本(路径)
    果 = {"锚点们": [], "告警": [], "本": 本}
    if not 本.存在:
        本.警(0, "", f"文件不存在：{路径}")
        return _收(本, 果)

    段 = ""
    锚 = None
    格 = None
    键 = None
    for 号, 原 in enumerate(本.行们, 1):
        行 = 原.rstrip()
        if not 行.strip():
            continue

        if _标题行.match(行):
            键 = None
            continue

        m = _锚头.match(行)
        if m:
            锚 = {"号": int(m.group(1)), "标题": m.group(2).strip(), "行": 号,
                   "格们": [], "字段行": {}}
            果["锚点们"].append(锚)
            段, 格, 键 = "锚点", None, None
            continue

        m = _子头.match(行)
        if m and 锚 is not None:
            名 = m.group(3).strip()
            if 名 not in 动格名们:
                本.警(号, 原, f"格名「{名}」不认识（只认：{'、'.join(动格名们)}）")
            格 = {"锚": int(m.group(1)), "号": int(m.group(2)), "名": 名, "行": 号,
                   "字段行": {}}
            for k in 动格字段:
                格[k] = ""
            锚["格们"].append(格)
            段, 键 = "格", None
            continue

        m = _段头.match(行)
        if m:
            段, 键 = "其他", None
            本.警(号, 原, f"不认识的段落标题「{m.group(1).strip()}」")
            continue

        m = _字段行.match(行)
        if m:
            名, 值 = m.group(1).strip(), m.group(2).strip()
            if 段 == "格" and 格 is not None:
                if 名 in 动格字段 or 名 in 动格可选:
                    _填(格, 名, 值, 号)
                    键 = ("格", 名)
                else:
                    本.警(号, 原, f"锚点{格['锚']}-{格['号']} 里不认识的字段「{名}」"
                                  f"（只认：{'、'.join(动格字段)}）")
                    键 = None
                continue
            本.警(号, 原, f"字段「{名}」不在任何【### A-B 格名】下面")
            键 = None
            continue

        m = _续行.match(行)
        if m and 键 is not None:
            _填(格, 键[1], m.group(1).strip(), 号)
            continue
        if m:
            本.警(号, 原, "缩进续写，但上一行不是字段 —— 不知道接给谁")
        else:
            本.警(号, 原, "这一行不是标题 / 字段 / 续写，没人认领")

    for a in 果["锚点们"]:
        if not a["格们"]:
            本.警(a["行"], "", f"锚点{a['号']} 下面一格都没有")
        for g in a["格们"]:
            if not g["动作"]:
                本.警(g["行"], "", f"锚点{a['号']}-{g['号']}（{g['名']}）没有【动作】—— 出不了片")
            elif g.get("强度"):
                try:
                    int(str(g["强度"]).strip())
                except ValueError:
                    本.警(g["行"], "", f"锚点{a['号']}-{g['号']} 的【强度】不是数字：{g['强度']}")
            if g.get("帧数"):
                try:
                    帧 = int(str(g["帧数"]).strip())
                    if 帧 < 1 or 帧 > 512:
                        本.警(g["行"], "", f"锚点{a['号']}-{g['号']} 的【帧数】{帧} 离谱"
                                          f"（1~512），出片时会按 49 帧来")
                except ValueError:
                    本.警(g["行"], "", f"锚点{a['号']}-{g['号']} 的【帧数】不是数字：{g['帧数']}"
                                      f"（出片时会按 49 帧来）")
    return _收(本, 果)


# ── 看片记录 ────────────────────────────────────────────────

_表行 = re.compile(r"^\|(.+)\|\s*$")
_问题行 = re.compile(r"^\*\*问题\s*(\d+)\s*\*\*\s*[:：]\s*(.+?)\s*$")


def _结果(文本):
    上 = (文本 or "").upper()
    if "PASS" in 上:
        return "PASS"
    if "FAIL" in 上:
        return "FAIL"
    return None


def 解析看片记录(路径):
    """读 看片记录.md。表格行和「✓ 审核状态：PASS」块都收，按出现顺序排。

    返回 {记录们, 告警}；每条记录带 序（行号）用于取「最后一条」。
    """
    果 = {"记录们": [], "告警": []}
    if not os.path.exists(路径):
        果["告警"].append({"行": 0, "原文": "", "说明": f"文件不存在：{路径}"})
        return 果

    待定 = None
    最近标题 = ""
    for 号, 原 in enumerate(读行(路径), 1):
        行 = 原.strip()
        if not 行:
            continue
        if 行.startswith("#"):
            最近标题 = 行.lstrip("#").strip()
            continue

        m = _表行.match(行)
        if m:
            格 = [c.strip() for c in m.group(1).split("|")]
            if len(格) >= 5:
                结果 = _结果(格[2])
                if 结果:
                    果["记录们"].append({
                        "序": 号, "轮次": 格[0], "阶段": 格[1], "结果": 结果,
                        "定位": 格[3], "摘要": 格[4], "类型": "表", "标题": 最近标题,
                        "问题们": [], "原文": 行,
                    })
                    continue

        if "审核状态" in 行:
            结果 = _结果(行)
            if 结果:
                待定 = {"序": 号, "轮次": "", "阶段": "", "结果": 结果, "定位": "",
                        "摘要": "", "类型": "块", "标题": 最近标题,
                        "问题们": [], "原文": 行}
                果["记录们"].append(待定)
            continue

        if 待定 is not None and not 待定["阶段"]:
            m2 = re.search(r"【(.+?)】", 行)
            if m2:
                待定["阶段"] = m2.group(1).strip()
                continue
        if 待定 is not None:
            m3 = _问题行.match(行)
            if m3:
                待定["问题们"].append(m3.group(2))
    return 果


# ── 阶段规格：怎么从「阶段」标签认出这是哪一步的审片 ─────────
#   组 = 每组至少命中一个词；排 = 出现任一个词就不算这条阶段。

_规格 = {
    "①":       {"名": "① 节拍拆解",   "组": [["节拍", "①", "01-"]], "排": ["图", "片", "画面"]},
    "②":       {"名": "② 九宫格",     "组": [["九宫格", "②", "02-"]], "排": ["图", "片", "画面"]},
    "九宫格图":  {"名": "② 九宫格图",   "组": [["九宫格", "②", "02-"], ["图", "画面", "渲染", "帧"]], "排": []},
    "③":       {"名": "③ 四宫格",     "组": [["四宫格", "③", "03-"]], "排": ["图", "片", "画面"]},
    "四宫格图":  {"名": "③ 四宫格图",   "组": [["四宫格", "③", "03-"], ["图", "画面", "渲染", "帧"]], "排": []},
    "④":       {"名": "④ 动态提示词",  "组": [["动态", "④", "04-"]], "排": ["图", "片", "画面"]},
    "片":       {"名": "④ 成片",       "组": [["成片", "片", "视频", "mp4"]], "排": []},
}

_门顺序 = ("①", "②", "九宫格图", "③", "四宫格图", "④", "片")


def 命中(规格, 文本):
    if not 文本:
        return False
    for 词 in 规格.get("排", []):
        if 词 in 文本:
            return False
    for 组 in 规格["组"]:
        if not any(词 in 文本 for 词 in 组):
            return False
    return True


def 审片状态(记录们, 键):
    """看片记录是追加写的 —— 取**最后一条**能对上的记录当下状态。

    返回 (结果, 记录)：结果是 PASS / FAIL / "无"（没这个阶段的记录）。
    """
    规格 = _规格[键]
    命中们 = [r for r in 记录们 if 命中(规格, r.get("阶段") or r.get("标题", ""))]
    if not 命中们:
        return "无", None
    r = max(命中们, key=lambda x: x["序"])
    return r["结果"], r


# ============================================================
# 三、扫状态 / 阶段门 / 下一步
# ============================================================

def 扫状态(戏名):
    """把一部戏的目录扫成一份状态。只读，不建目录、不碰 ComfyUI。"""
    目录 = 戏目录(戏名)
    状 = {"戏名": 戏名, "目录": 目录, "有目录": os.path.isdir(目录)}
    状["有"] = {}
    for 键, 名 in (("剧本", F_剧本), ("01", F_节拍), ("02", F_九宫), ("03", F_四宫),
                   ("04", F_动态), ("看片", F_看片), ("看片表", F_看片表), ("进度", F_进度)):
        状["有"][键] = os.path.exists(os.path.join(目录, 名))

    状["记录"] = 解析看片记录(os.path.join(目录, F_看片))["记录们"]
    状["审"] = {k: 审片状态(状["记录"], k)[0] for k in _规格}

    状["九"] = 解析九宫格(os.path.join(目录, F_九宫)) if 状["有"]["02"] else None
    状["四"] = 解析四宫格(os.path.join(目录, F_四宫)) if 状["有"]["03"] else None
    状["动"] = 解析动态(os.path.join(目录, F_动态)) if 状["有"]["04"] else None

    状["格数"] = len(状["九"]["格们"]) if 状["九"] else 0
    状["四格数"] = sum(len(a["格们"]) for a in 状["四"]["锚点们"]) if 状["四"] else 0
    状["动格数"] = sum(len(a["格们"]) for a in 状["动"]["锚点们"]) if 状["动"] else 0

    状["图们"] = sorted(glob.glob(os.path.join(目录, "01_格*.png")))
    状["四图们"] = sorted(glob.glob(os.path.join(目录, "03_锚*.png")))
    状["片们"] = sorted(glob.glob(os.path.join(目录, "04_锚*.mp4")))
    状["日志"] = 读日志(目录)
    return 状


def 跳步告警(状):
    """产物在了、但上游没有 PASS 记录 —— 这就是跳步。"""
    出 = []
    if 状["有"]["02"] and 状["审"]["①"] != "PASS":
        出.append(f"{F_九宫} 已经在，但「{_规格['①']['名']}」没有 PASS 记录 —— 跳步了"
                  f"（现状：{状['审']['①']}）")
    if 状["有"]["03"] and 状["审"]["②"] != "PASS":
        出.append(f"{F_四宫} 已经在，但「{_规格['②']['名']}」没有 PASS 记录 —— 跳步了"
                  f"（现状：{状['审']['②']}）")
    if 状["有"]["04"] and 状["审"]["③"] != "PASS":
        出.append(f"{F_动态} 已经在，但「{_规格['③']['名']}」没有 PASS 记录 —— 跳步了"
                  f"（现状：{状['审']['③']}）")
    if 状["片们"] and 状["审"]["④"] != "PASS":
        出.append(f"成片已经出了 {len(状['片们'])} 段，但「{_规格['④']['名']}」没有 PASS 记录 —— 跳步了"
                  f"（现状：{状['审']['④']}）")
    return 出


def 判断下一步(状):
    """照 剧组/制片人.md 的「我怎么判断当前该干什么」表推下一步。"""
    名 = 状["戏名"]
    if not 状["有"]["剧本"]:
        return "目录里没有 剧本.md —— 先让用户给剧本；拿到后派【分镜师】做①（节拍拆解）"
    if not 状["有"]["01"]:
        return "派【分镜师】做①：剧本.md → 01-节拍拆解.md"
    if 状["审"]["①"] != "PASS":
        return "派【导演】审①：读 剧本.md + 01-节拍拆解.md，把结果写进 看片记录.md"
    if not 状["有"]["02"]:
        return "派【分镜师】做②：01-节拍拆解.md → 02-九宫格.md"
    if 状["审"]["②"] != "PASS":
        return "派【导演】审②：读 剧本.md + 01 + 02，把结果写进 看片记录.md"
    if len(状["图们"]) < max(1, 状["格数"]):
        return (f"派【放映员】出九宫格图（{len(状['图们'])}/{状['格数'] or 9}）："
                f"python 剧组.py 出图 {名}")
    if 状["审"]["九宫格图"] != "PASS":
        return "派【导演】**看图**（不是看提示词）：对着 01_格*.png 审，写进 看片记录.md"
    if not 状["有"]["03"]:
        return "派【分镜师】做③：每锚点 → 4 格，产出 03-四宫格.md"
    if 状["审"]["③"] != "PASS":
        return "派【导演】审③：读 剧本.md + 01 + 02 + 03，把结果写进 看片记录.md"
    if not 状["有"]["04"]:
        return "派【动画师】做④：03-四宫格.md → 04-动态提示词.md"
    if 状["审"]["④"] != "PASS":
        return "派【导演】审④：读 剧本.md + 01 + 02 + 03 + 04，把结果写进 看片记录.md"
    if 状["四格数"] and len(状["四图们"]) < 状["四格数"]:
        return (f"派【放映员】出四宫格图（{len(状['四图们'])}/{状['四格数']}）："
                f"python 剧组.py 出图四宫格 {名}")
    if 状["动格数"] and len(状["片们"]) < 状["动格数"]:
        return f"派【放映员】出片：python 剧组.py 出片 {名}"
    if 状["审"]["片"] != "PASS":
        return "派【导演】看片：记录帧间差异、首末帧差异、时长这些硬指标"
    if not 状["有"]["看片表"]:
        return f"收尾：拼看片表 python 剧组.py 拼图 {名}"
    if not 状["有"]["进度"]:
        return f"收尾：写档案 python 剧组.py 进度 {名}"
    return f"全 PASS —— 收尾完成。重出图/重出片随时可跑（加 --重做）。"


def 门(戏名, 键们, 强跑, 步骤):
    """卡门：上游没 PASS 就停。--强跑 可以硬闯（会留一行警告）。"""
    状 = 扫状态(戏名)
    缺 = [k for k in 键们 if 状["审"][k] != "PASS"]
    if not 缺:
        报(f"门 · {步骤}：" + "、".join(_规格[k]["名"] for k in 键们) + " 全部 PASS")
        return True
    警(f"门 · {步骤}：" + "、".join(f"{_规格[k]['名']}（{状['审'][k]}）" for k in 缺) + " —— 还没 PASS")
    if 强跑:
        警("  --强跑：硬闯。出事别怪剧组。")
        return True
    print("  停。先让【导演】审完、把 PASS 写进 看片记录.md；确认要硬闯就加 --强跑。")
    近 = [r for r in 状["记录"] if r.get("阶段")]
    if 近:
        print("  看片记录里现有的阶段标签：" + "、".join(sorted({r["阶段"] for r in 近})))
    return False


# ============================================================
# 四、角色：让角色库认得这出戏的人
# ============================================================

_性别词 = {"female": "女", "woman": "女", "girl": "女", "男": "男",
           "male": "男", "man": "男", "boy": "男",
           "androgynous": "不明", "女": "女", "男": "男", "不明": "不明"}
_年龄词 = [("young adult", "青年"), ("twenties", "青年"), ("青年", "青年"),
           ("teenage", "少年"), ("teenager", "少年"), ("teen", "少年"), ("少年", "少年"),
           ("middle-aged", "中年"), ("middle aged", "中年"), ("中年", "中年"),
           ("elderly", "老年"), ("老年", "老年")]
_发词 = ("hair", "bangs", "ponytail", "updo", "发", "辫")
_眼词 = ("eye", "eyes", "瞳", "眼")
_肤词 = ("skin", "皮", "肤")
_服词 = ("robe", "dress", "armor", "armour", "coat", "cloak", "cape", "hanfu",
        "kimono", "uniform", "suit", "gown", "tunic", "jacket", "袍", "衣", "服",
        "甲", "裙", "靴", "披风", "斗篷")
_体词 = ("tall", "slender", "petite", "curvy", "muscular", "burly", "slim",
        "statuesque", "高挑", "娇小", "清瘦", "健壮", "魁梧", "丰满", "纤瘦")


def 拆角色描述(描述):
    """把角色卡那串外貌描述拆成 角色库 认的字段。

    认得出的进结构化字段，认不出的整段塞进「补充」—— **一个字都不丢**，
    这样 角色库.外貌串() 出来的串跟角色卡里写的等价。
    """
    字段 = {}
    剩 = []
    for s in re.split(r"[，,;；、]+", 描述 or ""):
        s = s.strip()
        if not s:
            continue
        低 = s.lower()
        归 = None
        if any(w in 低 for w in _性别词):
            归 = "性别"
            字段[归] = _性别词[next(w for w in _性别词 if w in 低)]
        elif any(w in 低 for w in ("少年", "青年", "中年", "老年")):
            归 = "年龄"
            字段[归] = next(w for w in ("少年", "青年", "中年", "老年") if w in 低)
        elif any(w in 低 for w in _发词):
            归 = "发"
        elif any(w in 低 for w in _肤色 for _肤色 in _肤词):
            归 = "肤"
        elif any(w in 低 for w in _眼词):
            归 = "眼"
        elif any(w in 低 for w in _服词):
            归 = "服"
        elif any(w in 低 for w in _体词):
            归 = "体态"
        if 归 in ("性别", "年龄"):
            continue
        if 归:
            字段[归] = f"{字段[归]}, {s}" if 字段.get(归) else s
        else:
            剩.append(s)
    if 剩:
        字段["补充"] = "，".join(剩)
    return 字段


def 登记角色(角色卡们):
    """让角色库认得这出戏的人。

    **已经登记过的一律不动**（一致性全靠角色库里的那张脸和那个种子）。
    """
    名单 = []
    for 卡 in 角色卡们:
        名, 描述 = 卡["名"], 卡["描述"]
        if not 名:
            continue
        已有 = 角色库.取(名)
        if 已有:
            print(f"  ✓ 角色【{名}】角色库里已有（种子 {已有['种子']}）—— 直接复用，不覆盖")
        else:
            字段 = 拆角色描述(描述)
            导演.定角(名, **字段)
            print(f"     （角色卡原文拆成：{'、'.join(字段.keys()) or '空'}）")
        if 名 not in 名单:
            名单.append(名)
    return 名单


def 备角色(目录):
    """这出戏的人是谁：先看 02 的角色卡（顺手登记），再从 03 的「人物」里补已有的。"""
    名单 = []
    卡 = []
    路2 = os.path.join(目录, F_九宫)
    if os.path.exists(路2):
        卡 = 解析九宫格(路2)["角色卡"]
    if 卡:
        名单 += 登记角色(卡)
    路3 = os.path.join(目录, F_四宫)
    if os.path.exists(路3):
        for 锚 in 解析四宫格(路3)["锚点们"]:
            for 名 in 拆名字(锚.get("人物", "")):
                if 名 not in 名单 and 角色库.取(名):
                    名单.append(名)
    if not 名单:
        警(f"没认出这出戏有谁（{F_九宫} 里没有【角色卡】段？）—— 出图不带角色串，一致性会差")
    return 名单


def 拆名字(s):
    出 = []
    for x in re.split(r"[、，,；;/|+\s]+", s or ""):
        x = re.sub(r"[（(].*?[)）]", "", x).strip()
        if x and x not in 出:
            出.append(x)
    return 出


def 挑角色(文本, 名单):
    """这格谁出场：名字直接出现在文本里的算。

    一个都没认出来时 —— 只有 1 个角色就用它；多个就把全体带上并报一句。
    返回 (角色们, 备注)。
    """
    有 = [n for n in 名单 if n and n in (文本 or "")]
    if 有:
        return 有, ""
    if len(名单) == 1:
        return list(名单), ""
    if not 名单:
        return [], ""
    return list(名单), "提示词里没认出角色名，本格按全体角色处理（想让某格只带某几个人，就在提示词里写名字）"


def 角色种子(文本, 名单):
    """这格的种子（导演.开镜 用的就是它：锁第一个出场角色的种子）。"""
    for n in 挑角色(文本, 名单)[0]:
        r = 角色库.取(n)
        if r:
            return r["种子"]
    return None


def 取风格(视觉规范):
    """视觉规范里的「风格」→ 交给 导演.开镜。认不出来就退回戏的默认。"""
    值 = ((视觉规范 or {}).get("风格") or "").strip()
    if not 值:
        return None
    if 风格库.取(值) is None:
        警(f"视觉规范里的风格「{值}」风格库里没有 —— 这出戏按默认风格走"
          f"（python 导演.py 风格 看有哪些）")
        return None
    return 值


# ============================================================
# 五、放映员：出图 / 出片
# ============================================================

def 命令_出图(戏名, 只要=None, 重做=False, 空跑=False):
    """出九宫格：一格一张 01_格N.png（走 导演.立戏 / 定角 / 开镜）。"""
    目录 = 戏目录(戏名)
    路 = os.path.join(目录, F_九宫)
    头(f"出图 · 九宫格《{戏名}》" + ("　[空跑]" if 空跑 else ""))
    if not os.path.exists(路):
        错(f"没有 {F_九宫}：{路}\n   下一步：派【分镜师】做②（先看 01-节拍拆解.md）")
        return 2

    九 = 解析九宫格(路)
    打告警(九["告警"])
    if not 九["格们"]:
        错(f"{F_九宫} 里一格都没解析出来 —— 停。先按格式契约补上「## 格N —— 标题」。")
        return 2
    if len(九["格们"]) != 9:
        警(f"九宫格是 {len(九['格们'])} 格，不是 9 格（文件里有几格就出几格）")

    导演.立戏(戏名)
    print("▶ 角色：")
    名单 = 登记角色(九["角色卡"]) if 九["角色卡"] else []
    if not 名单:
        警(f"{F_九宫} 里没有【角色卡】段 —— 出图不带角色串，一致性会差")
    风格键 = 取风格(九["视觉规范"])
    if 风格键:
        print(f"  ✓ 风格：{风格键}（来自【视觉规范】）")

    要出 = [g for g in 九["格们"] if not 只要 or g["号"] in 只要]
    if 只要:
        缺 = sorted(set(只要) - {g["号"] for g in 九["格们"]})
        if 缺:
            警(f"{F_九宫} 里没有格 {缺} —— 跳过")
    print(f"\n▶ 要出 {len(要出)} 格" + ("（空跑，不碰 ComfyUI）" if 空跑 else ""))

    起 = time.time()
    成 = 跳 = 失 = 连败 = 0
    for g in 要出:
        出图 = os.path.join(目录, f"01_格{g['号']}.png")
        标 = f"格{g['号']}·{g['标题']}｜{g['目的'] or '—'}｜{g['景别'] or '—'}｜{g['机位'] or '—'}"
        if os.path.exists(出图) and not 重做:
            print(f"  ⏭ {标} → 01_格{g['号']}.png 已在，跳过（要重出加 --重做）")
            跳 += 1
            continue
        角色, 备注 = 挑角色(g["提示词"], 名单)
        if 备注:
            警(f"  格{g['号']}：{备注}")
        print(f"  ▶ {标}")
        print(f"     出场 {'、'.join(角色) if 角色 else '（无）'}　提示词 {g['提示词'][:50]}"
              f"{'…' if len(g['提示词']) > 50 else ''}")
        if 空跑:
            print("     · 空跑：不调 导演.开镜")
            成 += 1
            continue
        t = time.time()
        try:
            导演.开镜(g["提示词"], 风格=风格键, 角色=角色,
                      景别=g["景别"], 文件名=f"01_格{g['号']}")
        except Exception as e:
            秒 = time.time() - t
            失 += 1
            连败 += 1
            print(f"     ✗ 出图失败：{e}")
            记日志(目录, "出图", f"01_格{g['号']}", 秒, "失败", str(e)[:80])
            if 连败 >= 3:
                错("连续 3 格失败 —— 多半是 ComfyUI 没开。先停，跑 `python 引擎.py 体检` 看看。")
                break
            continue
        连败 = 0
        秒 = time.time() - t
        成 += 1
        print(f"     ✓ 01_格{g['号']}.png　⏱ {时长(秒)}")
        记日志(目录, "出图", f"01_格{g['号']}", 秒, "成功")

    总 = time.time() - 起
    print(f"\n▶ 出图收工：成功 {成}　跳过 {跳}　失败 {失}　⏱ 合计 {时长(总)}")
    return 1 if 失 else 0


def 命令_出图四宫格(戏名, 只要锚=None, 重做=False, 空跑=False):
    """出四宫格：每个锚点的每一格一张 03_锚A格B.png。"""
    目录 = 戏目录(戏名)
    路 = os.path.join(目录, F_四宫)
    头(f"出图 · 四宫格《{戏名}》" + ("　[空跑]" if 空跑 else ""))
    if not os.path.exists(路):
        错(f"没有 {F_四宫}：{路}\n   下一步：派【分镜师】做③（得先有 ① PASS + ② PASS）")
        return 2

    四 = 解析四宫格(路)
    打告警(四["告警"])
    if not 四["锚点们"]:
        错(f"{F_四宫} 里一个锚点都没解析出来 —— 停。")
        return 2

    导演.立戏(戏名)
    print("▶ 角色：")
    名单 = 备角色(目录)

    锚们 = [a for a in 四["锚点们"] if not 只要锚 or a["号"] in 只要锚]
    if 只要锚:
        缺 = sorted(set(只要锚) - {a["号"] for a in 四["锚点们"]})
        if 缺:
            警(f"{F_四宫} 里没有锚点 {缺} —— 跳过")
    格数 = sum(len(a["格们"]) for a in 锚们)
    print(f"\n▶ 要出 {len(锚们)} 个锚点 / {格数} 格" + ("（空跑，不碰 ComfyUI）" if 空跑 else ""))

    起 = time.time()
    成 = 跳 = 失 = 连败 = 0
    for 锚 in 锚们:
        人物 = 锚.get("人物", "")
        场景 = 锚.get("场景", "")
        print(f"  ◆ 锚点{锚['号']}·{锚['标题']}"
              + (f"　人物 {人物}" if 人物 else "")
              + (f"　场景 {场景[:24]}" if 场景 else ""))
        for 格 in 锚["格们"]:
            A, B = 锚["号"], 格["号"]
            出图 = os.path.join(目录, f"03_锚{A}格{B}.png")
            标 = f"锚{A}-{B} {格['名']}"
            if os.path.exists(出图) and not 重做:
                print(f"    ⏭ {标} → 03_锚{A}格{B}.png 已在，跳过（要重出加 --重做）")
                跳 += 1
                continue
            角色, 备注 = 挑角色(f"{人物} {格['提示词']}", 名单)
            if 备注:
                警(f"    锚{A}-{B}：{备注}")
            print(f"    ▶ {标}　出场 {'、'.join(角色) if 角色 else '（无）'}")
            print(f"       提示词 {格['提示词'][:50]}{'…' if len(格['提示词']) > 50 else ''}")
            if 空跑:
                print("       · 空跑：不调 导演.开镜")
                成 += 1
                continue
            t = time.time()
            try:
                导演.开镜(格["提示词"], 角色=角色, 文件名=f"03_锚{A}格{B}")
            except Exception as e:
                秒 = time.time() - t
                失 += 1
                连败 += 1
                print(f"       ✗ 出图失败：{e}")
                记日志(目录, "出图四宫格", f"03_锚{A}格{B}", 秒, "失败", str(e)[:80])
                if 连败 >= 3:
                    错("连续 3 格失败 —— 先停，跑 `python 引擎.py 体检` 看看 ComfyUI。")
                    break
                continue
            连败 = 0
            秒 = time.time() - t
            成 += 1
            print(f"       ✓ 03_锚{A}格{B}.png　⏱ {时长(秒)}")
            记日志(目录, "出图四宫格", f"03_锚{A}格{B}", 秒, "成功")
        if 连败 >= 3:
            break

    总 = time.time() - 起
    print(f"\n▶ 出图收工：成功 {成}　跳过 {跳}　失败 {失}　⏱ 合计 {时长(总)}")
    return 1 if 失 else 0


def 命令_出片(戏名, 只要锚=None, 重做=False, 空跑=False):
    """出片：04-动态提示词.md 的每一格 → 一段 04_锚A格B.mp4。

    源图对应：
      锚A 的 **关键帧**（A-0）  → 01_格A.png（九宫格那一张）
      锚A 的第 B 格（B≥1）      → 03_锚A格B.png（四宫格那张）

    帧数固定 49 / 832×480；某一段想单独改，就在 04 里给那格写【帧数：N】。
    """
    目录 = 戏目录(戏名)
    路4 = os.path.join(目录, F_动态)
    路3 = os.path.join(目录, F_四宫)
    头(f"出片《{戏名}》" + ("　[空跑]" if 空跑 else ""))
    if not os.path.exists(路4):
        错(f"没有 {F_动态}：{路4}\n   下一步：派【动画师】做④（得先有 ③ PASS）")
        return 2

    动 = 解析动态(路4)
    打告警(动["告警"])
    if not 动["锚点们"]:
        错(f"{F_动态} 里一个锚点都没解析出来 —— 停。")
        return 2
    四 = None
    if os.path.exists(路3):
        四 = 解析四宫格(路3)
        打告警(四["告警"])
    else:
        警(f"没有 {F_四宫} —— 四宫格的图会找不到，只有关键帧能出片")

    导演.立戏(戏名)
    print("▶ 角色：")
    名单 = 备角色(目录)

    # 02 的每格用了谁的种子 → 关键帧的视频种子跟着它，保证可复现
    关键帧种子 = {}
    路2 = os.path.join(目录, F_九宫)
    if os.path.exists(路2):
        for g in 解析九宫格(路2)["格们"]:
            关键帧种子[g["号"]] = 角色种子(g["提示词"], 名单)

    # 03 ↔ 04 对表
    if 四 is not None:
        有四, 有动 = {}, {}
        for a in 四["锚点们"]:
            for g in a["格们"]:
                有四[(a["号"], g["号"])] = True
        for a in 动["锚点们"]:
            for g in a["格们"]:
                有动[(a["号"], g["号"])] = True
        差1 = sorted(k for k in 有动 if k[1] >= 1 and k not in 有四)
        差2 = sorted(k for k in 有四 if k not in 有动)
        if 差1:
            警(f"{F_动态} 里这些格在 {F_四宫} 里没有："
              + "、".join(f"锚{a}格{b}" for a, b in 差1))
        if 差2:
            警(f"{F_四宫} 里这些格在 {F_动态} 里没有（出不了片）："
              + "、".join(f"锚{a}格{b}" for a, b in 差2))

    要出 = []
    for a in 动["锚点们"]:
        if 只要锚 and a["号"] not in 只要锚:
            continue
        for g in a["格们"]:
            要出.append((a, g))
    if 只要锚:
        缺 = sorted(set(只要锚) - {a["号"] for a in 动["锚点们"]})
        if 缺:
            警(f"{F_动态} 里没有锚点 {缺} —— 跳过")
    print(f"\n▶ 要出 {len(要出)} 段" + ("（空跑，不碰 ComfyUI）" if 空跑 else ""))

    起 = time.time()
    成 = 跳 = 失 = 缺图 = 连败 = 0
    for 锚, 格 in 要出:
        A, B = 锚["号"], 格["号"]
        源名 = f"01_格{A}.png" if B == 0 else f"03_锚{A}格{B}.png"
        源 = os.path.join(目录, 源名)
        目标 = os.path.join(目录, f"04_锚{A}格{B}.mp4")
        标 = f"锚{A}-{B} {格['名']}"
        动作 = 格["动作"]
        强度 = 格.get("强度", "")
        if not 动作:
            警(f"  {标} 没有【动作】—— 跳过（别把空话喂给模型）")
            缺图 += 1
            continue
        if not os.path.exists(源):
            警(f"  {标} 缺源图 {源名} —— 跳过"
              + ("（先跑：python 剧组.py 出图四宫格 %s）" % 戏名 if B >= 1
                 else "（先跑：python 剧组.py 出图 %s）" % 戏名))
            缺图 += 1
            continue
        if os.path.exists(目标) and not 重做:
            print(f"  ⏭ {标} → 04_锚{A}格{B}.mp4 已在，跳过（要重出加 --重做）")
            跳 += 1
            continue
        种子 = 关键帧种子.get(A)
        帧数 = 49                      # 想改某一段的帧数，就在 04 里给那格写【帧数：N】
        if str(格.get("帧数") or "").strip().isdigit():
            帧数 = int(str(格["帧数"]).strip())
        print(f"  ▶ {标}　源图 {源名}　强度 {强度 or '—'}　{帧数} 帧"
              + (f"　种子 {种子}" if 种子 else ""))
        print(f"     动作 {动作[:50]}{'…' if len(动作) > 50 else ''}")
        if 空跑:
            print(f"     · 空跑：不调 导演.让镜动 → 04_锚{A}格{B}.mp4")
            成 += 1
            continue
        t = time.time()
        try:
            果 = 导演.让镜动({"路": 源, "种子": 种子}, 动作,
                             帧数=帧数, 帧宽=832, 帧高=480)
            # 让镜动 按源图名落盘（01_格1.mp4）；这里挪到 04_锚A格B.mp4
            if os.path.abspath(果["路"]) != os.path.abspath(目标):
                os.replace(果["路"], 目标)
        except Exception as e:
            秒 = time.time() - t
            失 += 1
            连败 += 1
            print(f"     ✗ 出片失败：{e}")
            记日志(目录, "出片", f"04_锚{A}格{B}", 秒, "失败", str(e)[:80])
            if 连败 >= 3:
                错("连续 3 段失败 —— 先停，跑 `python 引擎.py 体检` 看看 ComfyUI。")
                break
            continue
        连败 = 0
        秒 = time.time() - t
        成 += 1
        print(f"     ✓ 04_锚{A}格{B}.mp4　⏱ {时长(秒)}")
        记日志(目录, "出片", f"04_锚{A}格{B}", 秒, "成功")

    总 = time.time() - 起
    print(f"\n▶ 出片收工：成功 {成}　跳过 {跳}　缺源图/动作 {缺图}　失败 {失}　⏱ 合计 {时长(总)}")
    return 1 if 失 else 0


# ============================================================
# 六、收尾：拼图 / 进度
# ============================================================

def 命令_拼图(戏名, 每行=2):
    """调同目录的 拼图.py 生成 _看片表.png（这一步是纯本地拼版，不走 导演.py）。"""
    目录 = 戏目录(戏名)
    头(f"拼图《{戏名}》")
    脚本 = os.path.join(这里, "拼图.py")
    if not os.path.exists(脚本):
        错(f"找不到 拼图.py：{脚本}")
        return 2
    if not os.path.isdir(目录):
        错(f"没有这个戏的目录：{目录}")
        return 1
    图们 = [f for f in os.listdir(目录)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) and not f.startswith("_")]
    if not 图们:
        错("目录里没有图 —— 先跑 出图 / 出图四宫格")
        return 1

    print(f"▶ 调 拼图.py：{len(图们)} 张图，每行 {每行} 张")
    起 = time.time()
    环 = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, 脚本, 目录, str(每行)],
                       capture_output=True, env=环)
    for 行 in (r.stdout or b"").decode(U8, "replace").splitlines():
        print(f"    {行}")
    if r.returncode != 0:
        错(f"拼图.py 退出码 {r.returncode}")
        for 行 in (r.stderr or b"").decode(U8, "replace").splitlines()[-8:]:
            print(f"    {行}")
        return 1
    出 = os.path.join(目录, F_看片表)
    if os.path.exists(出):
        报(f"{F_看片表}　{大小(os.path.getsize(出))}　⏱ {时长(time.time() - 起)}")
    else:
        警(f"拼图.py 跑完了但没看到 {F_看片表}")
    return 0


def 命令_进度(戏名):
    """生成/更新 剧集进度.md：几镜、几轮返工、每轮在改什么、总耗时。"""
    目录 = 戏目录(戏名)
    头(f"进度《{戏名}》")
    if not os.path.isdir(目录):
        错(f"没有这个戏的目录：{目录}")
        return 1
    状 = 扫状态(戏名)
    记录们 = 状["记录"]
    表行们 = [r for r in 记录们 if r["类型"] == "表"]
    块们 = [r for r in 记录们 if r["类型"] == "块"]

    # 轮次 / 返工：优先数表格里的行；没有表格就数 PASS/FAIL 块
    if 表行们:
        总轮 = max((int(r["轮次"]) for r in 表行们 if str(r["轮次"]).isdigit()), default=len(表行们))
        返工们 = [r for r in 表行们 if r["结果"] == "FAIL"]
        依据 = "看片记录.md 的表"
    else:
        总轮 = len(块们)
        返工们 = [r for r in 块们 if r["结果"] == "FAIL"]
        依据 = "看片记录.md 的 PASS/FAIL 块"
    通过们 = [r for r in 记录们 if r["结果"] == "PASS"]

    # 耗时：渲染日志累计 + 产物挂钟跨度
    日志 = 状["日志"]
    成功 = [x for x in 日志 if x["状态"] == "成功"]
    失败 = [x for x in 日志 if x["状态"] == "失败"]
    渲染秒 = sum(x["秒"] for x in 成功)
    分命令 = {}
    for x in 成功:
        分命令[x["命令"]] = 分命令.get(x["命令"], [0, 0.0])
        分命令[x["命令"]][0] += 1
        分命令[x["命令"]][1] += x["秒"]

    时间们 = []
    for f in os.listdir(目录):
        if f in (F_进度, F_日志):
            continue
        try:
            时间们.append(os.path.getmtime(os.path.join(目录, f)))
        except OSError:
            pass
    首, 末 = (min(时间们), max(时间们)) if 时间们 else (None, None)

    阶 = "、".join(f"{_规格[k]['名']} {状['审'][k]}" for k in _门顺序)
    L = []
    L.append(f"# 剧集进度 · {戏名}\n")
    L.append(f"> 由 `python 剧组.py 进度 {戏名}` 生成于 "
             f"{time.strftime('%Y-%m-%d %H:%M:%S')}。**本文件每次生成都整体覆盖**，"
             f"要留手写备注请写在别的文件里。\n")
    L.append("## 一、规模\n")
    L.append("| 项 | 数 | 状态 |")
    L.append("|---|---|---|")
    L.append(f"| 九宫格镜数 | {状['格数']} | {'✓' if 状['格数'] else '—'} |")
    L.append(f"| 九宫格图 | {len(状['图们'])} / {状['格数'] or 9} | "
             f"{'✓ 齐' if 状['格数'] and len(状['图们']) >= 状['格数'] else '⚠ 缺'} |")
    L.append(f"| 四宫格镜数 | {状['四格数']} | {'✓' if 状['四格数'] else '—'} |")
    L.append(f"| 四宫格图 | {len(状['四图们'])} / {状['四格数'] or '?'} | "
             f"{'✓ 齐' if 状['四格数'] and len(状['四图们']) >= 状['四格数'] else '⚠ 缺'} |")
    L.append(f"| 成片段数 | {len(状['片们'])} / {状['动格数'] or '?'} | "
             f"{'✓ 齐' if 状['动格数'] and len(状['片们']) >= 状['动格数'] else '⚠ 缺'} |")
    L.append(f"| 看片表 | {'有' if 状['有']['看片表'] else '无'} | "
             f"{'✓' if 状['有']['看片表'] else '⚠'} |")
    L.append(f"| 审片总轮次 | {总轮} | 依据：{依据} |")
    L.append(f"| 返工轮数（FAIL） | {len(返工们)} | "
             f"{'✓ 一次过' if not 返工们 else '⚠ 有回炉'} |")
    L.append("")
    L.append("## 二、审片流水\n")
    if 表行们:
        L.append("| 轮次 | 阶段 | 结果 | 问题定位 | 意见摘要 |")
        L.append("|---|---|---|---|---|")
        for r in 表行们:
            L.append(f"| {r['轮次']} | {r['阶段']} | "
                     f"{'✅ PASS' if r['结果'] == 'PASS' else '❌ FAIL'} | "
                     f"{r['定位'] or '—'} | {r['摘要'] or '—'} |")
    elif 块们:
        for r in 块们:
            L.append(f"- {'✅ PASS' if r['结果'] == 'PASS' else '❌ FAIL'}"
                     f"（第 {r['序']} 行）阶段：{r['阶段'] or r.get('标题') or '未标注'}")
    else:
        L.append("（看片记录.md 里没有可识别的审片记录 —— 还没审过，或者格式不对）")
    L.append("")
    L.append(f"**各阶段当前状态**：{阶}\n")
    L.append("## 三、每轮在改什么\n")
    if 返工们:
        for r in 返工们:
            头衔 = f"第 {r['轮次']} 轮 · {r['阶段'] or '未标注阶段'} FAIL" if r.get("轮次") \
                else f"第 {r['序']} 行的 FAIL · {r['阶段'] or r.get('标题') or '未标注阶段'}"
            L.append(f"- **{头衔}**（定位：{r['定位'] or '—'}）")
            if r["摘要"]:
                L.append(f"  - 意见：{r['摘要']}")
            for q in r["问题们"]:
                L.append(f"  - 问题：{q}")
    else:
        L.append("- 没有 FAIL 轮 —— 一次过，没什么要改的。")
    for r in 通过们:
        if r.get("轮次"):
            L.append(f"- 第 {r['轮次']} 轮 · {r['阶段'] or '未标注阶段'} ✅ PASS"
                     + (f"：{r['摘要']}" if r["摘要"] else ""))
    L.append("")
    L.append("## 四、耗时\n")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| 渲染耗时合计（真跑过的渲染） | {时长(渲染秒) if 渲染秒 else '0.0 秒'} |")
    for 命, (次, 秒) in sorted(分命令.items()):
        L.append(f"| └ {命} | {次} 次 · {时长(秒)} |")
    if 失败:
        L.append(f"| 失败的渲染 | {len(失败)} 次（没算进合计） |")
    if 首 and 末:
        L.append(f"| 挂钟跨度（首个产物 → 最近改动） | {时刻(首)} → {时刻(末)}"
                 f"（{(末 - 首) / 3600:.1f} 小时） |")
    L.append("")
    L.append("> 「渲染耗时」来自 `_渲染日志.tsv`（每次真渲染由 剧组.py 记一行）；"
             "审片、写提示词的时间不在里面，挂钟跨度里包含它们。")
    L.append("")
    L.append("## 五、下一步\n")
    L.append(f"{判断下一步(状)}")
    L.append("")

    写文(os.path.join(目录, F_进度), "\n".join(L))
    报(f"{F_进度} 已写：{len(记录们)} 条审片记录、返工 {len(返工们)} 轮、"
       f"渲染 {len(成功)} 次 / {时长(渲染秒)}")
    print(f"    {os.path.join(目录, F_进度)}")
    return 0


# ============================================================
# 七、检查
# ============================================================

产物表 = [
    # (键, 标签, 文件名或通配, 阶段规格, 谁写的)
    ("剧本", "剧本.md", F_剧本, None, "用户"),
    ("01", "01-节拍拆解.md", F_节拍, "①", "分镜师"),
    ("02", "02-九宫格.md", F_九宫, "②", "分镜师"),
    ("图", "01_格*.png", "01_格*.png", "九宫格图", "放映员"),
    ("03", "03-四宫格.md", F_四宫, "③", "分镜师"),
    ("四图", "03_锚*.png", "03_锚*.png", "四宫格图", "放映员"),
    ("04", "04-动态提示词.md", F_动态, "④", "动画师"),
    ("片", "04_锚*.mp4", "04_锚*.mp4", "片", "放映员"),
    ("看片", "看片记录.md", F_看片, None, "导演"),
    ("看片表", "_看片表.png", F_看片表, None, "拼图.py"),
    ("进度", "剧集进度.md", F_进度, None, "剧组.py"),
]


def 扫产物(状):
    目录 = 状["目录"]
    期望 = {"图": 状["格数"] or 9, "四图": 状["四格数"] or 0, "片": 状["动格数"] or 0}
    行们 = []
    for 键, 标签, 模式, 规格, 谁 in 产物表:
        if "*" in 模式:
            们 = sorted(glob.glob(os.path.join(目录, 模式)))
            大小和 = sum(os.path.getsize(p) for p in 们 if os.path.exists(p))
        else:
            路 = os.path.join(目录, 模式)
            们 = [路] if os.path.exists(路) else []
            大小和 = os.path.getsize(路) if 们 else 0
        在 = bool(们)
        状态 = "在" if 在 else "缺"
        if "*" in 模式 and 期望.get(键):
            状态 = f"{len(们)}/{期望[键]}"
        行们.append({"键": 键, "标签": 标签, "在": 在, "数": len(们), "状态": 状态,
                     "大小": 大小和, "规格": 规格, "谁": 谁, "期望": 期望.get(键)})
    return 行们


def 命令_检查(戏名):
    """扫作品目录，打一张进度表 + 下一步该干什么。"""
    目录 = 戏目录(戏名)
    print()
    print("═" * 64)
    print(f"  影匠 · 剧组检查《{戏名}》")
    print(f"  {目录}")
    print("═" * 64)
    if not os.path.isdir(目录):
        错(f"没有这个戏的目录：{目录}")
        print("   先建戏：python 导演.py 或者 导演.立戏(\"戏名\")；"
              "或者 戏名 写错了（作品/ 下有的是："
              + "、".join(sorted(os.listdir(作品根)) if os.path.isdir(作品根) else []) + "）")
        return 1

    状 = 扫状态(戏名)

    print("\n▶ 产物")
    print(f"  {排('', 2)}{排('文件 / 产物', 26)}{排('状态', 10)}{排('大小', 11)}审片")
    print("  " + "─" * 60)
    for r in 扫产物(状):
        符 = "✓" if r["在"] else "✗"
        结果 = "—"
        if r["规格"]:
            审 = 状["审"][r["规格"]]
            结果 = {"PASS": "✓ PASS", "FAIL": "✗ FAIL"}.get(审, "— 无记录")
        print(f"  {符} {排(r['标签'], 24)}{排(r['状态'], 10)}"
              f"{排(大小(r['大小']) if r['在'] else '—', 11)}{结果}")

    print("\n▶ 阶段门（看片记录.md 里最后一条对得上的审片）")
    有记录 = False
    for k in _门顺序:
        r = 审片状态(状["记录"], k)[1]
        if r is None:
            print(f"  — {排(_规格[k]['名'], 16)}无记录")
            continue
        有记录 = True
        符 = "✓" if r["结果"] == "PASS" else "✗"
        定位 = f"　{r['定位']}" if r.get("定位") else ""
        摘要 = f"　{r['摘要'][:34]}" if r.get("摘要") else ""
        print(f"  {符} {排(_规格[k]['名'], 16)}{排(r['结果'], 8)}"
              f"第 {r['序']} 行 · {r['阶段'] or r.get('标题') or '未标注阶段'}{定位}{摘要}")
    if not 有记录:
        警(f"{F_看片} 里没有能对上的审片记录 —— 一个阶段都没正式 PASS 过")

    警们 = 跳步告警(状)
    print("\n▶ 跳步检查")
    if 警们:
        for x in 警们:
            警(x)
    else:
        报("没发现跳步")

    解析警 = []
    for k in ("九", "四", "动"):
        if 状[k]:
            解析警 += 状[k]["告警"]
    if 解析警:
        print("\n▶ 产物解析")
        打告警(解析警)

    print("\n▶ 下一步（照 剧组/制片人.md 的表）")
    print(f"  {判断下一步(状)}")
    print()
    return 0


# ============================================================
# 八、全部：一条龙，每步之间卡门
# ============================================================

def 命令_全部(戏名, 强跑=False, 空跑=False):
    """检查 → 出图九宫格 → 出图四宫格 → 出片 → 拼图 → 进度。

    每步之间卡门：上游没有 PASS 就停下来报警，除非 --强跑。
    """
    头(f"全部《{戏名}》" + ("　[强跑]" if 强跑 else "") + ("　[空跑]" if 空跑 else ""))
    命令_检查(戏名)

    if not 门(戏名, ["①", "②"], 强跑, "出九宫格图"):
        return 3
    命令_出图(戏名, 空跑=空跑)

    if not 门(戏名, ["③"], 强跑, "出四宫格图"):
        return 3
    命令_出图四宫格(戏名, 空跑=空跑)

    if not 门(戏名, ["④"], 强跑, "出片"):
        return 3
    命令_出片(戏名, 空跑=空跑)

    if 空跑:
        print("\n▶ 空跑：跳过 拼图 和 进度")
        return 0
    命令_拼图(戏名)
    命令_进度(戏名)
    print("\n▶ 全部跑完（图/片/看片表/进度都看在作品目录里）")
    return 0


# ============================================================
# 九、命令行
# ============================================================

命令们 = {
    "检查": "扫目录，打进度表 + 下一步该干什么",
    "出图": "读 02-九宫格.md，一格出一张 01_格N.png",
    "出图四宫格": "读 03-四宫格.md，一格出一张 03_锚A格B.png",
    "出片": "读 04-动态提示词.md，一格出一段 04_锚A格B.mp4",
    "拼图": "调 拼图.py 生成 _看片表.png",
    "进度": "写 剧集进度.md（几镜、几轮返工、每轮在改什么、总耗时）",
    "全部": "检查 → 出图 → 出图四宫格 → 出片 → 拼图 → 进度（每步卡门）",
}
别名 = {"四宫格": "出图四宫格", "出图4": "出图四宫格", "检查进度": "检查"}


def 用法():
    print(__doc__)
    print("命令：")
    for k, v in 命令们.items():
        print(f"  {k:<12} {v}")
    print("\n开关：--重做 强制重出　--空跑 只演一遍不碰 ComfyUI　--强跑 门没过也硬闯　--每行 N 拼图几列")


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "帮", "用法"):
        用法()
        return 0
    命令 = 别名.get(argv[1], argv[1])
    if 命令 not in 命令们:
        错(f"不认识这个命令：{argv[1]}")
        用法()
        return 2
    if len(argv) < 3:
        错(f"命令 {命令} 要跟一个戏名，例如：python 剧组.py {命令} 试镜")
        return 2

    戏名 = argv[2]
    参数 = argv[3:]
    开关 = {x for x in 参数 if x.startswith("-")}
    位 = [x for x in 参数 if not x.startswith("-")]
    重做 = "--重做" in 开关 or "-重做" in 开关
    空跑 = "--空跑" in 开关 or "-空跑" in 开关
    强跑 = "--强跑" in 开关 or "-强跑" in 开关
    每行 = 2
    for i, x in enumerate(参数):
        if x in ("--每行", "-每行") and i + 1 < len(参数):
            try:
                每行 = max(1, int(参数[i + 1]))
            except ValueError:
                警(f"--每行 后面的「{参数[i + 1]}」不是数字，按 {每行} 来")
        elif re.fullmatch(r"\d+", x) and 命令 in ("检查", "进度"):
            警(f"命令 {命令} 不吃数字参数「{x}」，忽略")

    if 命令 == "检查":
        return 命令_检查(戏名)
    if 命令 == "出图":
        格号 = {int(x) for x in 位 if x.isdigit()}
        return 命令_出图(戏名, 格号 or None, 重做=重做, 空跑=空跑)
    if 命令 == "出图四宫格":
        锚号 = {int(x) for x in 位 if x.isdigit()}
        return 命令_出图四宫格(戏名, 锚号 or None, 重做=重做, 空跑=空跑)
    if 命令 == "出片":
        锚号 = {int(x) for x in 位 if x.isdigit()}
        return 命令_出片(戏名, 锚号 or None, 重做=重做, 空跑=空跑)
    if 命令 == "拼图":
        return 命令_拼图(戏名, 每行=每行)
    if 命令 == "进度":
        return 命令_进度(戏名)
    if 命令 == "全部":
        return 命令_全部(戏名, 强跑=强跑, 空跑=空跑)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
