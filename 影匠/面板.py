# -*- coding: utf-8 -*-
"""影匠 —— 面板：一眼看清现在什么情况。

只读。绝不写盘。只读状态、只打印。

    python 面板.py              等价于 看
    python 面板.py 看           打一次快照
    python 面板.py 盯           每 3 秒刷新（Ctrl+C 退），屏幕清空重画
    python 面板.py 看 --json    输出 JSON（给别的程序吃）
    python 面板.py 看 --战情    只打「需要你动手的」那几行（待人工/失败/卡住）

回答四个问题
------------
1. 现在有没有活在跑？跑到哪了？（引擎 / 在跑什么）
2. 钱花到哪了？还有没有可能白花的账？（要人管的事 / 钱和时间）
3. 上次断在哪？怎么接着跑？（断点）
4. 下一步要多少时间/显存？模型齐了没？（模型 / 钱和时间）

退出码
------
0  一切正常
2  有数据源问不到（面板不崩，但那几行会写「问不到：<原因>」）
3  有「要人管的事」（未知态 / 失败 / 卡住的排队）—— 这个优先级比 2 高

设计原则
--------
1. **一个数据源挂了不许拖垮整个面板**：每个分区单独 try/except，
   挂了就在那一行显示「问不到：<原因>」，其他分区照常显示。
2. **拿不到就写「问不到」，绝不填假数字**。
3. **不碰重活**：只做轻量 HTTP 查询，不调 文生图 / 让镜动 之类的真跑活。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
import time

这里 = os.path.dirname(os.path.abspath(__file__))

# ───────────────────────── 宽度 / 颜色 ─────────────────────────
#
# 终端是 UTF-8，但中文是双宽字符，len() 数出来的是「字符数」不是「格数」。
# 排版对齐必须按格数算，否则列会歪。宽度上限 100 格。

宽 = 100


def 格数(s: str) -> int:
    """这个字符串在终端占几格。CJK / 全角标点算 2 格。"""
    n = 0
    for ch in str(s):
        o = ord(ch)
        if (
            0x1100 <= o <= 0x115F
            or 0x2E80 <= o <= 0xA4CF
            or 0xAC00 <= o <= 0xD7A3
            or 0xF900 <= o <= 0xFAFF
            or 0xFE30 <= o <= 0xFE6F
            or 0xFF00 <= o <= 0xFF60
            or 0xFFE0 <= o <= 0xFFE6
            or 0x1F300 <= o <= 0x1F9FF
            or 0x20000 <= o <= 0x3FFFD
        ):
            n += 2
        elif 0x0300 <= o <= 0x036F:  # 组合附加符号，零宽
            n += 0
        else:
            n += 1
    return n


def 排(s, n: int) -> str:
    """左对齐补空格到 n 格。超了就截断（按格数截）。"""
    s = str(s)
    出 = []
    用 = 0
    for ch in s:
        c = 格数(ch)
        if 用 + c > n:
            break
        出.append(ch)
        用 += c
    return "".join(出) + " " * (n - 用)


def 排右(s, n: int) -> str:
    """右对齐。"""
    s = str(s)
    w = 格数(s)
    if w >= n:
        return 排(s, n)
    return " " * (n - w) + s


def 截(s, n: int) -> str:
    s = str(s)
    if 格数(s) <= n:
        return s
    出, 用 = [], 0
    for ch in s:
        c = 格数(ch)
        if 用 + c > n - 1:
            break
        出.append(ch)
        用 += c
    return "".join(出) + "…"


def 大小(字节) -> str:
    """人类看得懂的大小。"""
    try:
        n = float(字节)
    except Exception:
        return "?"
    for 单, 名 in ((1024**4, "T"), (1024**3, "G"), (1024**2, "M"), (1024, "K")):
        if n >= 单:
            return f"{n / 单:.2f}{名}"
    return f"{int(n)}B"


def 时长(秒) -> str:
    """秒 → 人话。"""
    try:
        s = float(秒 or 0)
    except Exception:
        return "?"
    if s < 60:
        return f"{s:.0f}秒"
    if s < 3600:
        return f"{s / 60:.1f}分"
    return f"{s / 3600:.1f}时"


def _现在() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _距今(时刻文: str) -> float | None:
    """'2026-10-14 01:22:37' → 距今多少秒。解析不了返回 None。"""
    if not 时刻文:
        return None
    for 式 in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return time.time() - time.mktime(time.strptime(str(时刻文)[:19], 式))
        except Exception:
            continue
    return None


# ───────────────────────── 装模块 ─────────────────────────


def _装模块(名):
    """中文模块名 import 可能失败（编码 / 路径），兜底从文件直接装。"""
    try:
        return __import__(名)
    except Exception:
        import importlib.util

        p = os.path.join(这里, 名 + ".py")
        spec = importlib.util.spec_from_file_location(名, p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m


# 模块级只装一次。装不上就留着 None，后面每个分区各自报「问不到」。
_引擎 = None
_账本 = None
_装错: dict = {}


def _拿引擎():
    global _引擎
    if _引擎 is None and "引擎" not in _装错:
        try:
            _引擎 = _装模块("引擎")
        except Exception as e:
            _装错["引擎"] = f"{type(e).__name__}: {e}"
    if "引擎" in _装错:
        raise RuntimeError(f"装不上 引擎.py（{_装错['引擎']}）")
    return _引擎


def _拿账本():
    global _账本
    if _账本 is None and "账本" not in _装错:
        try:
            _账本 = _装模块("账本")
        except Exception as e:
            _装错["账本"] = f"{type(e).__name__}: {e}"
    if "账本" in _装错:
        raise RuntimeError(f"装不上 账本.py（{_装错['账本']}）")
    return _账本


# ───────────────────────── 常量 ─────────────────────────

共享根 = r"D:\Comfy-Desktop\ComfyUI-Shared\models"
私有根 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models"

# 关键模型：名字写全（含子目录），ComfyUI 认不认用 引擎.有模型() 问。
关键模型 = [
    # (键, 用途, [候选文件名…], 走不走 ComfyUI 的 object_info)  —— 候选里任一命中就算齐
    ("锁脸", "参考图锁脸（②九宫格 / ③四宫格）", ["diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors"], True),
    ("文生图", "文生图（④动态首帧）", ["diffusion_models/z_image_turbo_int8_convrot.safetensors"], True),
    ("文生图备", "文生图备选（fp8 大卡）", ["diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors"], True),
    ("出片高噪", "出片 Wan2.2 i2v 高噪（④出片）", ["diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"], True),
    ("出片低噪", "出片 Wan2.2 i2v 低噪（④出片）", ["diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"], True),
    ("出片加速", "Wan2.2 加速 LoRA（4 步）", [
        "loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
        "loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
    ], True),
    # IndexTTS-2.5 有自己独立的模型目录，不注册到 ComfyUI 的 model 列表里，
    # 所以「走不走 object_info」= 否，只查文件在不在。
    ("配音", "配音（IndexTTS-2.5，私有根独立目录）", ["IndexTTS-2.5/codec.pth"], False),
]

# 作品目录下这些名字不是戏，是自测 / 账本 / 接口用的杂物间
非戏前缀 = ("_", "账本自测", "接口自测")

# 阶段产物：按 剧组.py 的 产物表 对齐
# (标号, 说明, 匹配模式, 期望件数或 None)
阶段产物 = [
    ("①", "节拍", ["剧本.md"], None),
    ("①", "节拍拆解", ["01-节拍拆解.md"], None),
    ("②", "九宫格", ["02-九宫格.md"], None),
    ("②", "九宫格图", ["01_格*.png"], 9),
    ("③", "四宫格", ["03-四宫格.md"], None),
    ("③", "四宫格图", ["03_锚*.png"], None),
    ("④", "动态", ["04-动态提示词.md"], None),
    ("④", "成片", ["04_锚*.mp4"], None),
]


# ───────────────────────── 工具：扫描 ─────────────────────────


def _走目录(根: str) -> list:
    """把一个根下的所有文件走一遍。返回 [(相对路径, 字节数, 绝对路径)]。

    只走一遍 —— 面板要快，别对同一个根 glob 十几次。
    """
    出 = []
    根 = os.path.abspath(根)
    for 底, 子们, 文件们 in os.walk(根):
        for f in 文件们:
            全 = os.path.join(底, f)
            try:
                大 = os.path.getsize(全)
            except OSError:
                大 = -1
            出.append((os.path.relpath(全, 根).replace("\\", "/"), 大, 全))
    return 出


# ───────────────────────── ① 引擎 ─────────────────────────


def 收引擎() -> dict:
    """轻量问 ComfyUI：在线吗、版本、显卡、队列里几个活。

    只打 /system_stats 和 /queue 两个读接口，绝不提交工作流。
    """
    引 = _拿引擎()
    出: dict = {"问不到": None}

    在 = 引.在线()  # 这个函数自己吞异常，返回 {"在线": False, "错": ...}
    出["在线"] = bool(在.get("在线"))
    if not 出["在线"]:
        出["错"] = 在.get("错", "说不清")
        # 顺手把地址带出来，方便排查
        try:
            出["地址"] = getattr(引, "COMFY", "?")
        except Exception:
            出["地址"] = "?"
        return 出

    出["地址"] = getattr(引, "COMFY", "?")
    出["版本"] = 在.get("版本", "?")
    出["显卡"] = 在.get("显卡", "?")
    出["显存GB"] = 在.get("显存GB", 0)
    出["显存空闲GB"] = 在.get("显存空闲GB", 0)

    # /queue 不是 引擎.py 的公开函数，用它的 _请求 打（同一条连接、同一个超时口径）
    try:
        队 = 引._请求("/queue", 超时=8)
        跑 = 队.get("queue_running") or []
        排 = 队.get("queue_pending") or []
        出["队列跑"] = len(跑)
        出["队列排"] = len(排)
        名 = None
        if 跑:
            条 = 跑[0]
            # ComfyUI 的 queue_running 是 [编号, 提示号, 工作流, 附加, 客户端]
            if isinstance(条, (list, tuple)) and len(条) > 2 and isinstance(条[2], dict):
                for 节 in 条[2].values():
                    if isinstance(节, dict) and 节.get("class_type"):
                        名 = 节["class_type"]
                        break
        出["正在跑节点"] = 名
    except Exception as e:
        出["队列问不到"] = f"{type(e).__name__}: {e}"
    return 出


def 打引擎(d: dict, 行: list):
    if d.get("问不到"):
        行.append(f"  问不到：{d['问不到']}")
        return False
    if not d.get("在线"):
        行.append(f"  ✗ ComfyUI 没开 —— {d.get('错', '')}")
        行.append(f"    地址 {d.get('地址', '?')}（改地址：设环境变量 影匠_COMFY）")
        行.append("    启动提示：开 ComfyUI Desktop，或命令行 "
                  r"python main.py --listen 127.0.0.1 --port 8188")
        行.append("    没引擎就只能看账本和磁盘，出图/出片都跑不了。")
        return False
    行.append(
        f"  ✓ 在线 {d.get('地址')} · 版本 {d.get('版本')} · {d.get('显卡')}"
    )
    行.append(
        f"    显存 {d.get('显存空闲GB')}G 空闲 / {d.get('显存GB')}G 总共"
    )
    if "队列问不到" in d:
        行.append(f"    队列问不到：{d['队列问不到']}")
    else:
        跑, 排 = d.get("队列跑", 0), d.get("队列排", 0)
        符 = "●" if 跑 else "○"
        尾 = f" · 正在跑 {d['正在跑节点']}" if d.get("正在跑节点") else ""
        行.append(f"    {符} 队列：跑 {跑} · 排 {排}{尾}")
    return True


# ───────────────────────── ② 模型 ─────────────────────────


def _有模型(名: str) -> bool | None:
    """问 ComfyUI 认不认。True/False；问不到（引擎挂）返回 None。"""
    try:
        引 = _拿引擎()
        return bool(引.有模型(名))
    except Exception:
        return None


def 收模型() -> dict:
    """关键模型齐备度 + 半截下载。两条腿：问 ComfyUI（权威）+ 查文件（给大小）。"""
    出: dict = {"问不到": None, "条目": [], "半截": [], "根": {}}

    # 两个根各走一遍，建 relpath → 字节 的索引
    索引: dict = {}
    根错 = []
    for 根 in (共享根, 私有根):
        if not os.path.isdir(根):
            根错.append(f"没有这个目录：{根}")
            出["根"][根] = {"在": False}
            continue
        try:
            们 = _走目录(根)
        except Exception as e:
            根错.append(f"{根} 走不动：{type(e).__name__}: {e}")
            出["根"][根] = {"在": True, "问不到": str(e)}
            continue
        出["根"][根] = {"在": True, "文件数": len(们)}
        for 相对, 大, 全 in 们:
            索引[相对] = (大, 全)

    if 根错 and not 索引:
        出["问不到"] = "；".join(根错)
        return 出
    if 根错:
        出["根警告"] = 根错

    引擎通 = _有模型("__探测__") is not None

    for 键, 用途, 候选, 走引擎 in 关键模型:
        命中 = None
        for c in 候选:
            if c in 索引:
                命中 = c
                break
            # 名字可能带子目录前缀差异，退一步按 basename 找
            基 = os.path.basename(c)
            for 相对 in 索引:
                if os.path.basename(相对) == 基:
                    命中 = 相对
                    break
            if 命中:
                break
        if 走引擎:
            认 = _有模型(命中) if (命中 and 引擎通) else (None if not 引擎通 else False)
        else:
            认 = None
        大 = 索引[命中][0] if 命中 else -1
        出["条目"].append({
            "键": 键,
            "用途": 用途,
            "文件": 命中 or "（本机没有）",
            "大小字节": 大,
            "引擎认": 认,
            "非ComfyUI": not 走引擎,
            "在": bool(命中),
        })

    # 半截下载：两个根里所有 .part / .incomplete / .tmp
    半 = []
    for 相对, (大, 全) in 索引.items():
        低 = 相对.lower()
        if 低.endswith((".part", ".incomplete", ".tmp", ".download", ".crdownload")):
            半.append({"文件": 相对, "大小字节": 大, "根": 共享根 if 全.startswith(共享根) else 私有根})
    半.sort(key=lambda x: -x["大小字节"])
    出["半截"] = 半
    return 出


def 打模型(d: dict, 行: list):
    if d.get("问不到"):
        行.append(f"  问不到：{d['问不到']}")
        return False
    for 根, 情 in (d.get("根") or {}).items():
        短 = "共享根" if 根 == 共享根 else ("私有根" if 根 == 私有根 else 根)
        if not 情.get("在"):
            行.append(f"  ⚠ {短}不在：{根}")
        elif 情.get("问不到"):
            行.append(f"  ⚠ {短}走不动：{情['问不到']}")
        else:
            行.append(f"    {短} {根}（{情.get('文件数', 0)} 个文件）")
    for w in d.get("根警告") or []:
        行.append(f"  ⚠ {w}")

    行.append("    " + 排("键", 10) + 排("状态", 6) + 排("大小", 11)
              + 排("引擎认", 10) + "文件")
    for 条 in d["条目"]:
        符 = "✓" if 条["在"] else "✗"
        if 条.get("非ComfyUI"):
            认 = "— 不走这"
        else:
            认 = {True: "✓ 认", False: "✗ 不认", None: "? 问不到"}[条["引擎认"]]
            # 「文件在但引擎不认」是最坑的情况（没重启 / 路径不对），单独标
            if 条["在"] and 条["引擎认"] is False:
                认 = "⚠ 不认"
        行.append(
            "    "
            + 排(条["键"], 10)
            + 排(符, 6)
            + 排(大小(条["大小字节"]) if 条["大小字节"] >= 0 else "—", 11)
            + 排(认, 10)
            + 截(条["文件"], 50)
        )
    if d["半截"]:
        行.append(f"  ◐ 下到一半（{len(d['半截'])} 个）—— 这些不算数，重下或删掉：")
        for 半 in d["半截"][:6]:
            行.append(f"      {排(大小(半['大小字节']), 10)}{截(半['文件'], 82)}")
        if len(d["半截"]) > 6:
            行.append(f"      …还有 {len(d['半截']) - 6} 个")
    else:
        行.append("    ✓ 没有半截下载")
    return True


# ───────────────────────── ③ 在跑什么 ─────────────────────────


def 收在跑() -> dict:
    本 = _拿账本()
    出: dict = {"问不到": None}
    出["闸门"] = 本.闸门()
    出["运行"] = 本.列表(状态="运行")
    出["排队"] = 本.列表(状态="排队")
    return 出


def _带前缀(值, 前缀: str) -> str:
    """镜头/格号挂个前缀再显示。

    账本里有人写「镜01」有人写「01」，直接 f"镜{值}" 会印出「镜镜01」。
    已经有了就不重复加。
    """
    s = str(值 or "").strip()
    if not s:
        return ""
    return s if s.startswith(前缀) else 前缀 + s


def _一件(件: dict, 详: bool = False) -> str:
    尾 = []
    if 件.get("戏名"):
        尾.append(f"《{件['戏名']}》")
    if 件.get("镜头"):
        尾.append(_带前缀(件["镜头"], "镜"))
    if 件.get("格号"):
        尾.append(_带前缀(件["格号"], "格"))
    s = f"{件.get('类型', '?')} " + " ".join(尾)
    if 详:
        距 = _距今(件.get("开始时间") or 件.get("创建时间"))
        if 距 is not None:
            s += f"（{时长(距)}）"
    return s.strip()


def 打在跑(d: dict, 行: list):
    if d.get("问不到"):
        行.append(f"  问不到：{d['问不到']}")
        return False
    闸 = d["闸门"]
    占 = 闸.get("在跑", 0)
    符 = "●" if 占 else "○"
    行.append(
        f"  {符} 闸门 {占}/{闸.get('上限')} 占用 · 还能开 {闸.get('还能开')} · "
        f"排队 {闸.get('排队')}"
    )
    if 闸.get("上限", 1) <= 1:
        行.append("    ⚠ 并发上限是 1 —— 本机只有一张 5080，一次只能跑一个，别硬抬。")

    for 名, 们 in (("正在跑", d["运行"]), ("排队中", d["排队"])):
        if not 们:
            行.append(f"    {名}：无")
            continue
        行.append(f"    {名}（{len(们)}）：")
        for 件 in 们[:8]:
            行.append(f"      {排(件.get('id', '?'), 18)}{截(_一件(件, True), 74)}")
        if len(们) > 8:
            行.append(f"      …还有 {len(们) - 8} 件")
    return True


# ───────────────────────── ④ 要人管的事 ─────────────────────────
#
# 这是面板最重要的分区。铁律：钱可能已经花掉时绝不自动重试，必须人工核对。
# 所以「未知态」排最上面、用最显眼的标记。

卡住分钟 = 30  # 排队超过这么久还没动 = 可能卡住了


def 收要人管() -> dict:
    本 = _拿账本()
    出: dict = {"问不到": None}
    出["待人工"] = 本.待人工()
    出["失败"] = 本.列表(状态="失败")

    卡 = []
    for 件 in 本.列表(状态="排队"):
        距 = _距今(件.get("创建时间"))
        if 距 is not None and 距 > 卡住分钟 * 60:
            件 = dict(件)
            件["_等了秒"] = 距
            卡.append(件)
    卡.sort(key=lambda x: -x["_等了秒"])
    出["卡住"] = 卡
    出["共"] = len(出["待人工"]) + len(出["失败"]) + len(卡)
    return 出


def 打要人管(d: dict, 行: list):
    if d.get("问不到"):
        行.append(f"  问不到：{d['问不到']}")
        return False

    if not d["共"]:
        行.append("  ✓ 没你的事 —— 没有未知态、没有失败、没有卡住的排队。")
        return True

    if d["待人工"]:
        行.append(f"  ⚠⚠⚠ 未知态 {len(d['待人工'])} 件 —— 钱可能已经花了，"
                  "必须人工核对，绝不许自动重试 ⚠⚠⚠")
        for 件 in d["待人工"][:6]:
            行.append(f"    ▶ {排(件.get('id', '?'), 18)}{截(_一件(件), 60)}")
            行.append(
                f"      可能已计费 {'是' if 件.get('可能已计费') else '否（没证据，不等于没送达）'}"
                + (f" · 供应商任务号 {件['供应商任务号']}" if 件.get("供应商任务号") else "")
            )
            if 件.get("输出路径"):
                路 = 件["输出路径"]
                行.append(f"      先看这个文件在不在：{截(路, 70)}"
                          + ("  ← 在" if os.path.exists(路) else "  ← 不在"))
            if 件.get("错误"):
                行.append(f"      当时的原因 {截(str(件['错误']), 68)}")
            try:
                供 = _拿账本().取账本().供应商(件)
            except Exception:
                供 = "对应供应商的后台"
            行.append(f"      去哪查：{截(供, 78)}")
            行.append(f"      怎么办：python 账本.py 恢复 {件.get('id')}"
                      "   （或 python 账本.py 完成 <id> --输出 <路径>）")
        if len(d["待人工"]) > 6:
            行.append(f"    …还有 {len(d['待人工']) - 6} 件，看全的：python 账本.py 待人工")

    if d["失败"]:
        行.append(f"  ✗ 失败 {len(d['失败'])} 件 —— 看一眼再决定重不重跑：")
        for 件 in d["失败"][:6]:
            行.append(f"    ✗ {排(件.get('id', '?'), 18)}{截(_一件(件, True), 46)}"
                      f" {截(str(件.get('错误') or '（没记原因）'), 30)}")
            行.append(f"      重试：python 账本.py 重试 {件.get('id')}")
        if len(d["失败"]) > 6:
            行.append(f"    …还有 {len(d['失败']) - 6} 件")

    if d["卡住"]:
        行.append(f"  ◐ 卡住的排队 {len(d['卡住'])} 件（排队超 {卡住分钟} 分钟）：")
        for 件 in d["卡住"][:6]:
            行.append(f"    ◐ {排(件.get('id', '?'), 18)}{截(_一件(件), 48)}"
                      f" 等了 {时长(件['_等了秒'])}")
    return True


# ───────────────────────── ⑤ 断点 ─────────────────────────


def 收断点() -> dict:
    本 = _拿账本()
    出: dict = {"问不到": None}
    出["未完成"] = 本.未完成()
    出["按戏"] = {}
    for 件 in 出["未完成"]:
        戏 = 件.get("戏名") or "（没写戏名）"
        出["按戏"].setdefault(戏, []).append(件)
    return 出


def _接着跑(戏名: str) -> list:
    """这个戏该怎么接着跑。按产物缺到哪一步给命令。"""
    命 = []
    目 = os.path.join(这里, "作品", 戏名)
    if not os.path.isdir(目):
        return [f"目录都没了：{目}"]
    if not os.path.exists(os.path.join(目, "01-节拍拆解.md")):
        命.append(f"python 剧组.py 节拍 {戏名}")
    elif not os.path.exists(os.path.join(目, "02-九宫格.md")):
        命.append(f"python 剧组.py 九宫格 {戏名}")
    elif not glob.glob(os.path.join(目, "01_格*.png")):
        命.append(f"python 剧组.py 出图 {戏名}")
    elif not os.path.exists(os.path.join(目, "03-四宫格.md")):
        命.append(f"python 剧组.py 四宫格 {戏名}")
    elif not os.path.exists(os.path.join(目, "04-动态提示词.md")):
        命.append(f"python 剧组.py 动态 {戏名}")
    elif not glob.glob(os.path.join(目, "04_锚*.mp4")):
        命.append(f"python 剧组.py 出片 {戏名}")
    if not 命:
        命.append(f"python 剧组.py 检查 {戏名}   （产物看着齐了，跑一遍检查）")
    return 命


def 打断点(d: dict, 行: list):
    if d.get("问不到"):
        行.append(f"  问不到：{d['问不到']}")
        return False
    if not d["未完成"]:
        行.append("  ✓ 没有断点 —— 账本里没有「排队」或「运行」的任务。")
        return True
    行.append(f"  ◐ 没跑完 {len(d['未完成'])} 件（{len(d['按戏'])} 部戏）：")
    for 戏, 们 in sorted(d["按戏"].items()):
        行.append(f"    《{戏}》{len(们)} 件：")
        for 件 in 们[:5]:
            行.append(f"      {排(件.get('状态', '?'), 6)}{排(件.get('id', '?'), 18)}"
                      f"{截(_一件(件), 60)}")
        if len(们) > 5:
            行.append(f"      …还有 {len(们) - 5} 件")
        行.append("      接着跑：")
        for c in _接着跑(戏):
            行.append(f"        {c}")
    return True


# ───────────────────────── ⑥ 钱和时间 ─────────────────────────

估的类型 = [("出图", 1), ("出图四宫格", 1), ("出片", 1), ("配音", 1)]


def 收钱() -> dict:
    本 = _拿账本()
    出: dict = {"问不到": None}
    出["统计"] = 本.统计()
    出["预估"] = []
    for 类, 数 in 估的类型:
        try:
            出["预估"].append(本.预估(类, 数))
        except Exception as e:
            出["预估"].append({"类型": 类, "问不到": f"{type(e).__name__}: {e}"})
    # 一部戏的全流程大概多少（9 张图 + 9 段片）—— 这是「下一步要花多少」的正题
    try:
        出["一部戏"] = [
            本.预估("出图", 9),
            本.预估("出片", 9),
        ]
    except Exception as e:
        出["一部戏"] = [{"问不到": f"{type(e).__name__}: {e}"}]
    return 出


def 打钱(d: dict, 行: list):
    if d.get("问不到"):
        行.append(f"  问不到：{d['问不到']}")
        return False
    统 = d["统计"]
    行.append(
        f"  账本共 {统.get('总数', 0)} 件 · 估算 {统.get('估算成本', 0)} 元 · "
        f"实际 {统.get('实际成本', 0)} 元 · 可能已计费 {统.get('可能已计费', 0)} 件"
    )
    if 统.get("按状态"):
        段 = " · ".join(f"{k} {v}" for k, v in sorted(统["按状态"].items()))
        行.append(f"    按状态：{截(段, 86)}")
    else:
        行.append("    按状态：还没有任何任务 —— 还没数据。")

    实 = 统.get("实际成本") or 0
    估 = 统.get("估算成本") or 0
    if not 统.get("总数"):
        行.append("    ⚠ 还没有数据：下面的秒数/积分全是本机基线估算，不是实测均值。")
    elif 实 == 0 and 估 > 0:
        行.append("    ⚠ 有估算但没有实际成本 —— 说明任务没结算过，下面的依据看「实测均值」那栏。")

    if 统.get("最久一件"):
        最 = 统["最久一件"]
        行.append(f"    最久一件 {最.get('id')}（{最.get('类型')}）{时长(最.get('秒'))}"
                  f" · 总机时 {时长(统.get('总用时秒'))}")

    行.append("    下一步大概要多久（依据栏说清是实测均值还是基线）：")
    行.append("      " + 排("活", 12) + 排("数量", 6) + 排("积分", 10)
              + 排("墙钟", 10) + 排("电费", 12) + "依据")
    for 条 in d["预估"]:
        if 条.get("问不到"):
            行.append(f"      {排(条.get('类型', '?'), 12)}问不到：{截(条['问不到'], 60)}")
            continue
        行.append(
            "      "
            + 排(条.get("类型", "?"), 12)
            + 排(条.get("数量", 1), 6)
            + 排(条.get("积分", 0), 10)
            + 排(时长(条.get("秒", 0)), 10)
            + 排(f"{条.get('金额', 0)}元", 12)
            + 截(条.get("依据", "?"), 30)
        )
    for 条 in d.get("一部戏") or []:
        if 条.get("问不到"):
            continue
        行.append(f"      一部戏（9{条.get('单位', '件')}）："
                  f"约 {条.get('积分', 0)} 积分 / {时长(条.get('秒', 0))} / {条.get('金额', 0)} 元电费"
                  f"  ← {条.get('依据', '?')}")
    # 依据里如果出现「未实测」，把话说透
    未 = [条.get("类型") for 条 in d["预估"]
          if isinstance(条, dict) and "未实测" in str(条.get("依据", ""))]
    if 未:
        行.append(f"    ⚠ 这些的依据是设计意图、没实测过：{'、'.join(未)}")
    return True


# ───────────────────────── ⑦ 每部戏的进度 ─────────────────────────


def 收戏() -> dict:
    """扫 作品/ 下每个子目录，报六个阶段到哪一步了。"""
    根 = os.path.join(这里, "作品")
    出: dict = {"问不到": None, "戏们": [], "杂物": []}
    if not os.path.isdir(根):
        出["问不到"] = f"没有作品目录：{根}"
        return 出

    for 名 in sorted(os.listdir(根)):
        目 = os.path.join(根, 名)
        if not os.path.isdir(目):
            continue
        if 名.startswith(非戏前缀) or 名 in 非戏前缀:
            出["杂物"].append(名)
            continue
        情: dict = {"戏名": 名, "目录": 目, "阶段": [], "件数": 0}
        for 阶段标, 阶段说明, 模式, 期望 in 阶段产物:
            命中 = []
            for m in 模式:
                命中 += glob.glob(os.path.join(目, m))
            在 = len(命中)
            大小和 = 0
            for p in 命中:
                try:
                    大小和 += os.path.getsize(p)
                except OSError:
                    pass
            情["阶段"].append({
                "标": 阶段标, "说明": 阶段说明, "在": 在,
                "期望": 期望, "大小字节": 大小和,
            })
            情["件数"] += 在
        情["审片记录"] = os.path.exists(os.path.join(目, "看片记录.md"))
        出["戏们"].append(情)
    return 出


def 打戏(d: dict, 行: list):
    if d.get("问不到"):
        行.append(f"  问不到：{d['问不到']}")
        return False
    if not d["戏们"]:
        行.append("  ○ 作品/ 下一部戏都没有。开一部：python 导演.py 立戏 \"戏名\"")
        return True

    行.append("  " + 排("戏", 16) + 排("①节拍", 8) + 排("②九宫", 8)
              + 排("②图", 7) + 排("③四宫", 8) + 排("④动态", 8) + "④成片")
    for 情 in d["戏们"]:
        段 = {s["说明"]: s for s in 情["阶段"]}
        # ① 节拍 = 剧本 + 节拍拆解 都在才算
        节拍 = all(段[k]["在"] for k in ("节拍", "节拍拆解"))
        九宫 = bool(段["九宫格"]["在"])
        图 = 段["九宫格图"]["在"]
        期望 = 段["九宫格图"]["期望"] or 9
        四宫 = bool(段["四宫格"]["在"])
        动态 = bool(段["动态"]["在"])
        片 = 段["成片"]["在"]

        def m(过, 数=None):
            if 过:
                return "✓" if 数 is None else f"{数}"
            return "○"
        行.append(
            "  "
            + 排(截(情["戏名"], 15), 16)
            + 排(m(节拍), 8)
            + 排(m(九宫), 8)
            + 排("✓" if 图 else "○" if not 九宫 else f"{图}/{期望}", 7)
            + 排(m(四宫), 8)
            + 排(m(动态), 8)
            + m(片)
        )
        # 哪一步卡住了 → 直接把命令写出来
        if 情["件数"] == 0:
            行.append(f"      ○ 《{情['戏名']}》还什么都没做。先写 剧本.md，再 python 剧组.py 节拍 {情['戏名']}")
        elif not 片:
            步 = _接着跑(情["戏名"])
            行.append(f"      → 下一步：{步[0] if 步 else '?'}")

    if d["杂物"]:
        行.append(f"  （非戏目录，跳过 {len(d['杂物'])} 个：{'、'.join(d['杂物'][:6])}"
                  + ("…" if len(d["杂物"]) > 6 else "") + "）")
    return True


# ───────────────────────── ⑧ 磁盘 ─────────────────────────

盘们 = ["C:", "D:", "E:"]
D盘警告GB = 30


def 收磁盘() -> dict:
    出: dict = {"问不到": None, "盘": []}
    错 = []
    for 名 in 盘们:
        根 = 名 + os.sep
        if not os.path.exists(根):
            # 没这个盘是正常事，不是故障 —— 别报成「问不到」，也别报警告
            出["盘"].append({"盘": 名, "不存在": True,
                             "总GB": 0, "可用GB": 0, "已用%": 0, "警告": False})
            continue
        try:
            用 = shutil.disk_usage(根)
            出["盘"].append({
                "盘": 名, "总GB": round(用.total / 1024**3, 1),
                "可用GB": round(用.free / 1024**3, 1),
                "已用%": round(用.used / 用.total * 100, 1) if 用.total else 0,
                "警告": (名 == "D:" and 用.free / 1024**3 < D盘警告GB),
            })
        except Exception as e:
            出["盘"].append({"盘": 名, "问不到": f"{type(e).__name__}: {e}"})
            错.append(名)
    if len(错) == len(盘们):
        出["问不到"] = "所有盘都问不到"
    return 出


def 打磁盘(d: dict, 行: list):
    if d.get("问不到"):
        行.append(f"  问不到：{d['问不到']}")
        return False
    for p in d["盘"]:
        if p.get("不存在"):
            行.append(f"  ○ {排(p['盘'], 6)}没有这个盘（正常，不是故障）")
            continue
        if p.get("问不到"):
            行.append(f"  ⚠ {排(p['盘'], 6)}问不到：{截(p['问不到'], 70)}")
            continue
        符 = "⚠" if p.get("警告") else "✓"
        尾 = f"  ⚠ D 盘是模型盘，低于 {D盘警告GB}GB 了 —— 下模型前先腾地方" if p.get("警告") else ""
        行.append(
            f"  {符} {排(p['盘'], 6)}{排('可用 ' + str(p['可用GB']) + 'G', 16)}"
            f"/ 总 {p['总GB']}G（已用 {p['已用%']}%）{尾}"
        )
    return True


# ───────────────────────── 汇总 ─────────────────────────

分区表 = [
    ("引擎", 收引擎, 打引擎),
    ("模型", 收模型, 打模型),
    ("在跑什么", 收在跑, 打在跑),
    ("要人管的事", 收要人管, 打要人管),
    ("断点", 收断点, 打断点),
    ("钱和时间", 收钱, 打钱),
    ("每部戏的进度", 收戏, 打戏),
    ("磁盘", 收磁盘, 打磁盘),
]


def 收齐() -> dict:
    """把八个分区全收一遍。任何一块挂了都只影响那一块。"""
    果: dict = {
        "生成时间": _现在(),
        "分区": {},
        "问不到": [],
    }
    for 名, 收, _打 in 分区表:
        try:
            果["分区"][名] = 收()
        except Exception as e:
            果["分区"][名] = {"问不到": f"{type(e).__name__}: {e}"}
            果["问不到"].append({"分区": 名, "原因": f"{type(e).__name__}: {e}"})

    # 退出码判定
    要人 = 果["分区"].get("要人管的事") or {}
    果["要人管件数"] = 要人.get("共", 0) if not 要人.get("问不到") else 0
    果["退出码"] = 3 if 果["要人管件数"] else (2 if 果["问不到"] else 0)
    return 果


def _关账本():
    """把单例账本的连接关掉。只读，但连接要还。"""
    try:
        本 = _拿账本()
        单 = 本.取账本()
        单.自动快照 = False  # 关的时候不许顺手抬快照 —— 面板绝不写盘
        单.关()
    except Exception:
        pass


# ───────────────────────── 打印 ─────────────────────────


def 打一屏(果: dict, 战情: bool = False) -> None:
    print("═" * 宽)
    print(f"  影匠 · 面板{'（战情）' if 战情 else ''}   {果['生成时间']}")
    print("═" * 宽)

    for 名, _收, 打 in 分区表:
        d = 果["分区"].get(名) or {}
        if 战情 and 名 not in ("要人管的事", "断点"):
            continue
        行: list = []
        try:
            打(d, 行)
        except Exception as e:
            行 = [f"  问不到（打印这一块时自己崩了）：{type(e).__name__}: {e}"]
        print(f"\n▶ {名}")
        for s in 行:
            if 格数(s) > 宽:
                s = 截(s, 宽)
            print(s)

    if 战情:
        if not 果["要人管件数"]:
            print("\n✓ 没你的事 —— 没有未知态、没有失败、没有卡住的排队。")
    print()
    print("─" * 宽)
    码 = 果["退出码"]
    注 = {0: "一切正常", 3: "有要人管的事（未知态 / 失败 / 卡住）",
          2: "有数据源问不到"}.get(码, "?")
    print(f"  退出码 {码} —— {注}")
    if 果["问不到"]:
        for 条 in 果["问不到"]:
            print(f"    ⚠ {条['分区']}：{截(条['原因'], 76)}")
    print("─" * 宽)


def 打JSON(果: dict, 战情: bool = False) -> None:
    if 战情:
        要 = 果["分区"].get("要人管的事") or {}
        断 = 果["分区"].get("断点") or {}
        出 = {
            "生成时间": 果["生成时间"],
            "待人工": 要.get("待人工", []),
            "失败": 要.get("失败", []),
            "卡住": 要.get("卡住", []),
            "断点": 断.get("未完成", []),
            "问不到": 果["问不到"],
            "退出码": 果["退出码"],
        }
    else:
        出 = 果
    print(json.dumps(出, ensure_ascii=False, indent=2, default=str))


# ───────────────────────── 盯 ─────────────────────────


def 盯(每几秒: float = 3.0) -> int:
    """每 N 秒刷新，屏幕清空重画。Ctrl+C 退，退得干净。"""
    try:
        while True:
            try:
                果 = 收齐()
            except Exception as e:
                果 = {
                    "生成时间": _现在(), "分区": {}, "问不到": [
                        {"分区": "全部", "原因": f"{type(e).__name__}: {e}"}],
                    "要人管件数": 0, "退出码": 2,
                }
            # 清屏：Windows 用 cls，其他用 ANSI
            os.system("cls" if os.name == "nt" else "clear")
            try:
                打一屏(果, 战情=False)
            except Exception as e:
                print(f"⚠ 打印崩了（不影响下一轮）：{type(e).__name__}: {e}")
            print(f"  ↻ 每 {每几秒:g} 秒刷新一次，Ctrl+C 退。")
            time.sleep(每几秒)
    except KeyboardInterrupt:
        print("\n（盯模式停了。退出码按最后一轮算。）")
        try:
            return 果["退出码"]
        except Exception:
            return 0


# ───────────────────────── 命令行 ─────────────────────────


def _参():
    阿 = argparse.ArgumentParser(
        prog="面板.py",
        description="影匠 · 可用性面板（只读，绝不写盘）",
        add_help=True,
    )
    阿.add_argument("命令", nargs="?", default="看", choices=["看", "盯"],
                    help="看 = 打一次快照（默认）；盯 = 每 3 秒刷新")
    阿.add_argument("--json", action="store_true", help="输出 JSON（给别的程序吃）")
    阿.add_argument("--战情", action="store_true",
                    help="只打「需要你动手的」那几行（待人工/失败/卡住）")
    阿.add_argument("--每", type=float, default=3.0, help="盯模式的刷新间隔秒数（默认 3）")
    return 阿.parse_args()


def main(参=None) -> int:
    参 = _参() if 参 is None else 参
    try:
        if 参.命令 == "盯":
            return 盯(参.每)
        果 = 收齐()
        if 参.json:
            打JSON(果, 战情=参.战情)
        else:
            打一屏(果, 战情=参.战情)
        return 果["退出码"]
    except KeyboardInterrupt:
        print("\n（中断。）")
        return 2
    finally:
        _关账本()


if __name__ == "__main__":
    sys.exit(main())
