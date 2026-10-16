# -*- coding: utf-8 -*-
"""影匠 —— 接口/本地ComfyUI：把本机 ComfyUI 包成适配器。

**只 import，不改 `引擎.py`。** 中文模块名在部分环境直接 import 会失败，
所以先用 `__import__` 试，失败再按路径 `spec_from_file_location` 兜底
（`一致性.py` 的 `_装模块()` 就是这个套路，这里是同套路的另写一遍）。

三段式在这里长什么样
--------------------
ComfyUI 天生就是异步的：`POST /prompt` 给你一个 `prompt_id`，活干完才写进
`/history/<prompt_id>`。所以本适配器的**两个能力都是异步的**：

    buildCreate  拼工作流（读 模板/<模型id>.json，替换提示词/种子/尺寸/帧数）
    parseCreate  从 {"prompt_id": ...} 里认号；被拒（带 error）就交回空串
    parseResult  翻译 /history 的状态，并顺带看 /queue 来区分「排队」和「运行」

模型id 在这里 = `模板/` 里的工作流名
-----------------------------------
`zimage_turbo` / `wan22_i2v` 不只是文件名，它们是「一套模型 + 一套参数」的封装。
`README.md` 说的「换模型 = 往 模板/ 放一份 API 格式 json」就是这个意思：
新丢一个 json 进来，`元数据()["模型"]` 立刻多一项，代码一行不用动。

副作用只有一处
--------------
图生视频要先把首帧图塞进 ComfyUI 的 input 目录 —— 这是**唯一**有副作用的动作，
放在可选钩子 `预备()` 里。契约要求的三个纯函数碰都不碰网络，
所以它们可以拿假响应离线测。

作者：影匠 · 接口层。纯原创实现。
"""
from __future__ import annotations

import os
import random
import sys
import time

这里 = os.path.dirname(os.path.abspath(__file__))
影匠根 = os.path.dirname(这里)
模板目录 = os.path.join(影匠根, "模板")

# 无 ffmpeg 环境下的默认负面词（自己写的，不抄任何现成表）
默认负面 = (
    "色调艳丽，过曝，欠曝，模糊，噪点，静止画面，字幕，水印，logo，"
    "畸形的手，多余的手指，扭曲的脸，肢体错位，低质量，压缩痕迹"
)


def _装模块(文件名, 别名, 目录):
    """载入既有模块（只读）。先试 import，再退回按路径载入。"""
    路径 = os.path.join(目录, 文件名)
    if not os.path.isfile(路径):
        return None, f"文件不存在：{路径}"
    if 目录 not in sys.path:
        sys.path.insert(0, 目录)
    名 = os.path.splitext(文件名)[0]
    try:
        return __import__(名), ""
    except Exception as e1:
        pass
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_影匠_" + 别名, 路径)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        return m, ""
    except Exception as e2:
        return None, f"import 失败({e1!r})；按路径载入失败({e2!r})"


契约, _契约错 = _装模块("契约.py", "契约", 这里)
if 契约 is None:
    raise ImportError(f"装不进 契约.py：{_契约错}")

引擎, _引擎错 = _装模块("引擎.py", "引擎", 影匠根)


# ───────────────────────────── 元数据 ─────────────────────────────

默认模板 = {"文生图": "zimage_turbo", "图生视频": "wan22_i2v"}

# 本适配器已经接好的能力。模板目录里可能躺着**还没接**的工作流
# （比如 qwen_edit.json 是图生图），那些不往 元数据()["模型"] 里放 ——
# 免得列出一个点下去就报错的模型id。
已接能力 = ("文生图", "图生视频")


def _列模板() -> list[str]:
    try:
        return sorted(f[:-5] for f in os.listdir(模板目录) if f.endswith(".json"))
    except Exception:
        return []


def _猜能力(wf: dict) -> str:
    """从节点构成推这套工作流是干嘛的 —— 靠结构而不是靠文件名，改名也不怕。"""
    类们 = {节.get("class_type", "") for 节 in wf.values() if isinstance(节, dict)}
    if 类们 & {"WanImageToVideo", "Wan22ImageToVideoLatent",
               "WanFirstLastFrameToVideo", "Wan22ImageToVideo",
               "CreateVideo", "SaveVideo", "VHS_VideoCombine"}:
        return "图生视频"
    if "LoadImage" in 类们:
        return "图生图"          # 要吃参考图，但不出视频
    return "文生图"


def _模板画像() -> dict:
    """{模板名: {"能力":…, "能跑吗":…}}。只读 json 头几层，很轻。"""
    出 = {}
    for 名 in _列模板():
        try:
            wf = _净模板(_读模板(名))
            能 = _猜能力(wf)
        except Exception as e:
            出[名] = {"能力": "?", "能跑吗": False, "错": repr(e)}
            continue
        出[名] = {"能力": 能, "能跑吗": 能 in 已接能力}
    return 出


def 可用模型(能力: str | None = None) -> list[str]:
    """现在**真的能跑**的模型id（= 模板名）。"""
    return [n for n, v in _模板画像().items()
            if v.get("能跑吗") and (能力 is None or v["能力"] == 能力)]


def 元数据() -> dict:
    画 = _模板画像()
    能用 = {n: v for n, v in 画.items() if v.get("能跑吗")}
    没接 = {n: v["能力"] for n, v in 画.items() if not v.get("能跑吗")}
    return {
        "名称": "本地ComfyUI",
        "能力": list(已接能力),
        "模型": list(能用) or list(默认模板.values()),
        "费率": {
            m: {
                "单价": 0.0,
                "单位": "次",
                "币种": "CNY",
                "说明": "本机显卡自跑，不产生 API 费用（只烧电）",
                "模型id含义": f"模板/{m}.json",
            }
            for m in (能用 or {m: 1 for m in 默认模板.values()})
        },
        "需要联网": False,
        "是否本地": True,
        # ComfyUI 两个能力都是「提交 → 轮询」式的，所以都是异步
        "异步能力": list(已接能力),
        "能力对应的默认模板": dict(默认模板),
        "未接入的模板": 没接,
        "备注": ("模型id = 模板名。模板/ 里丢一份 API 格式 json，只要节点构成认得出，"
                 "它就自动出现在这里（文生图=没有 LoadImage；图生视频=有 Wan*/CreateVideo）。"),
        "基址": _基址(),
    }


def _基址() -> str:
    if 引擎 is None:
        return os.environ.get("影匠_COMFY", "http://127.0.0.1:8188")
    return getattr(引擎, "COMFY", "http://127.0.0.1:8188")


def 基址() -> str:
    return _基址()


# ───────────────────────────── 路径解析 ─────────────────────────────


def 本地路径(相对路径: str) -> str:
    """把 `/` 开头的项目内相对路径落成这台机器上的绝对路径。

    因为契约禁止绝对路径，**解析永远拼在 影匠根 底下**——
    所以 `/../../windows/win.ini` 这种也跑不出去（`..` 在契约那一层就被拦了）。
    """
    if not isinstance(相对路径, str):
        raise TypeError(f"路径必须是字符串，收到 {type(相对路径).__name__}")
    段 = [x for x in 相对路径.split("/") if x not in ("", ".")]
    if ".." in 段:
        raise ValueError(f"路径里不许有 ..：{相对路径!r}")
    return os.path.join(影匠根, *段)


# ───────────────────────────── 模板 ─────────────────────────────


def _读模板(名: str) -> dict:
    路 = os.path.join(模板目录, 名 if 名.endswith(".json") else 名 + ".json")
    if not os.path.isfile(路):
        raise FileNotFoundError(
            f"没有模板「{名}」。{模板目录} 里现有：{'、'.join(_列模板()) or '（空）'}"
        )
    import json

    with open(路, "r", encoding="utf-8") as f:
        return json.load(f)


def _净模板(wf: dict) -> dict:
    """模板里允许有 `_说明` 这类注释键，值不是节点，剔掉。"""
    return {
        k: v
        for k, v in wf.items()
        if isinstance(v, dict) and v.get("class_type")
    }


def _连线(节: dict, 口: str):
    """取某个输入口连到哪个节点号。"""
    v = (节.get("inputs") or {}).get(口)
    if isinstance(v, list) and v:
        return v[0]
    return None


def _设种子(ins: dict, 种):
    if "seed" in ins:
        ins["seed"] = 种
    if "noise_seed" in ins:
        ins["noise_seed"] = 种


def _采样器(wf: dict):
    for 号, 节 in wf.items():
        if 节.get("class_type") in ("KSampler", "KSamplerAdvanced"):
            return 号, 节
    return None, None


_文本类 = ("CLIPTextEncode", "T5TextEncode",
           "TextEncodeQwenImageEdit", "TextEncodeQwenImageEditPlus")


def _找文本节点(wf: dict):
    """找出「正向」和「负向」文本节点。

    优先顺着采样器的 positive / negative 连线倒推 —— 不能「取第一个」：
    模板里可能有好几个文本节点，先遇到的那个未必是正向
    （qwen_edit.json 就是反例：正向是 TextEncodeQwenImageEditPlus，
    负向才是排在它后面的 CLIPTextEncode）。
    连线断了才退回「第一个文本节点」。
    """
    采号, 采节 = _采样器(wf)
    正 = 负 = None
    if 采节 is not None:
        正 = _连线(采节, "positive")
        负 = _连线(采节, "negative")
        if 正 is not None and not isinstance(wf.get(正), dict):
            正 = None
        if 负 is not None and not isinstance(wf.get(负), dict):
            负 = None
    if 正 is None:
        正 = next((号 for 号, 节 in wf.items() if 节.get("class_type") in _文本类), None)
    if 负 is None:
        负 = next((号 for 号, 节 in wf.items()
                   if 节.get("class_type") in _文本类 and 号 != 正), None)
    return 正, 负


# ───────────────────────────── 校验 ─────────────────────────────

_数值范围 = {
    "宽": (64, 8192), "高": (64, 8192), "步数": (1, 200),
    "帧数": (4, 600), "帧率": (1, 120), "种子": (0, 2**53),
    "批量": (1, 16),
}


def _查数值(请求: dict, 问题: list, 必填=()):
    for 键, (低, 高) in _数值范围.items():
        v = 请求.get(键)
        if v is None or v == "":
            if 键 in 必填:
                问题.append(f"{键} 不能空")
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            问题.append(f"{键} 必须是数字，现在是 {type(v).__name__}：{v!r}")
            continue
        if not (低 <= v <= 高):
            问题.append(f"{键}={v} 超出范围 [{低}, {高}]")


def 校验(请求) -> list[str]:
    """本地这套自己的规矩。一次报全，不抛。"""
    问题: list[str] = []
    if not isinstance(请求, dict):
        return [f"请求必须是 dict，现在是 {type(请求).__name__}"]

    if 引擎 is None:
        问题.append(f"`引擎.py` 没装进来（{_引擎错}），本机 ComfyUI 用不了")

    能 = 请求.get("能力")
    if 能 not in 已接能力:
        return 问题 + [f"本地ComfyUI 现在只接了 {' / '.join(已接能力)}，不认「{能}」"]

    画 = _模板画像()
    能用 = 可用模型(能)
    没接 = [n for n, v in 画.items() if not v.get("能跑吗")]
    模板名 = 请求.get("模型id") or 默认模板.get(能)
    if 模板名 not in 能用:
        尾巴 = f"；模板/ 里还有没接入的：{'、'.join(没接)}" if 没接 else ""
        if 模板名 in 画:
            问题.append(
                f"模板「{模板名}」的节点构成看着是「{画[模板名]['能力']}」，"
                f"跟你要的「{能}」不搭{尾巴}"
            )
        else:
            问题.append(
                f"没有模板「{模板名}」——本地能跑「{能}」的模型id："
                f"{'、'.join(能用) or '（一个都没有）'}{尾巴}"
            )

    if not str(请求.get("提示词") or "").strip():
        问题.append("提示词 不能空（ComfyUI 那边会照跑，但出来的不是你要的）")

    _查数值(请求, 问题)

    if 能 == "图生视频":
        首 = 请求.get("首帧path")
        if not 首:
            问题.append("图生视频 必须给 首帧path（/ 开头的相对路径）")
        elif not 契约.检查路径值(首):
            try:
                本 = 本地路径(首)
            except Exception as e:
                问题.append(f"首帧path 解析不了：{e}")
            else:
                if not os.path.isfile(本):
                    问题.append(f"首帧图不存在：{首} → 找的是 {本}")
        # 尾帧是可选的，给了就得存在
        尾 = 请求.get("尾帧path")
        if 尾 and not 契约.检查路径值(尾):
            try:
                本 = 本地路径(尾)
            except Exception as e:
                问题.append(f"尾帧path 解析不了：{e}")
            else:
                if not os.path.isfile(本):
                    问题.append(f"尾帧图不存在：{尾} → 找的是 {本}")
    else:
        if 请求.get("首帧path"):
            问题.append("文生图 不吃 首帧path（想图生视频请把 能力 写成「图生视频」）")

    return 问题


# ───────────────────────────── 预备（唯一有副作用的钩子）─────────────


def 预备(请求: dict) -> dict:
    """提交前的最后一步：把首帧/尾帧图上传进 ComfyUI，把返回的文件名记进请求。

    这是唯一允许有副作用的钩子 —— 其余三个纯函数碰都不碰网络。
    上传失败会抛（调用方接住）：这时候活**还没提交**，重试是安全的。
    """
    出 = dict(请求)
    if 引擎 is None:
        raise RuntimeError(f"`引擎.py` 没装进来（{_引擎错}）")
    if 出.get("能力") != "图生视频":
        return 出
    for 键, 存键 in (("首帧path", "_图名"), ("尾帧path", "_尾图名")):
        路 = 出.get(键)
        if not 路:
            continue
        本 = 本地路径(路)
        回 = 引擎.上传图(本)
        出[存键] = 回.get("name") or ""
        出.setdefault("_上传回执", {})[键] = 回
    return 出


# ───────────────────────────── buildCreate ─────────────────────────────


def _改文生图(wf: dict, 请求: dict, 说明: list) -> int:
    """替换提示词/尺寸/种子/步数。返回用掉的种子。"""
    种 = 请求.get("种子")
    if 种 is None:
        种 = random.randint(1, 2**53 - 1)
    正号, 负号 = _找文本节点(wf)
    改了 = False
    for 号, 节 in wf.items():
        类 = 节.get("class_type", "")
        ins = 节.setdefault("inputs", {})
        if 类 in _文本类:
            if 号 == 正号:
                ins["text"] = 请求.get("提示词") or ""
                改了 = True
            elif 号 == 负号 and 请求.get("负面"):
                ins["text"] = 请求["负面"]
        elif 类 in ("EmptySD3LatentImage", "EmptyLatentImage"):
            if 请求.get("宽"):
                ins["width"] = int(请求["宽"])
            if 请求.get("高"):
                ins["height"] = int(请求["高"])
        elif 类 in ("KSampler", "KSamplerAdvanced"):
            _设种子(ins, 种)
            if ins.get("sampler_name") not in ("", None) and 请求.get("步数"):
                ins["steps"] = int(请求["步数"])
        elif 类 in ("SaveImage", "SaveAnimatedWEBP", "SaveVideo", "VHS_VideoCombine"):
            if "filename_prefix" in ins:
                ins["filename_prefix"] = 请求.get("前缀") or "影匠"
    if not 改了:
        raise RuntimeError("模板里找不到正向文本节点，提示词改不了")
    说明.append(f"种子 {种}｜正向节点 {正号}｜负向节点 {负号 or '（没有，跳过）'}")
    return 种


def _改图生视频(wf: dict, 请求: dict, 说明: list) -> int:
    """填首帧图、正负词、尺寸、帧数、帧率、种子。"""
    采号, 采节 = _采样器(wf)
    if 采节 is None:
        raise RuntimeError("模板里没有 KSampler，图生视频没法接")
    正号, 负号 = _找文本节点(wf)
    if 正号 is None:
        raise RuntimeError("模板里找不到正向提示词节点")

    图名 = 请求.get("_图名") or ""
    if not 图名 and 请求.get("首帧path"):
        图名 = os.path.basename(str(请求["首帧path"]).replace("\\", "/"))
        说明.append("首帧图没上传过（没调 预备），只能填文件名 —— ComfyUI 多半找不到它")
    尾名 = 请求.get("_尾图名") or ""

    种 = 请求.get("种子")
    if 种 is None:
        种 = random.randint(1, 2**53 - 1)

    图序 = 0
    for 号, 节 in wf.items():
        类 = 节.get("class_type", "")
        ins = 节.setdefault("inputs", {})
        if 类 in _文本类:
            if 号 == 正号:
                ins["text"] = 请求.get("提示词") or ""
            elif 号 == 负号:
                ins["text"] = 请求.get("负面") or 默认负面
        elif 类 == "LoadImage":
            图序 += 1
            if 图序 == 1:
                ins["image"] = 图名
            elif 图序 == 2 and 尾名:
                ins["image"] = 尾名
                说明.append("第二张 LoadImage 当尾帧用")
        elif 类 in ("KSampler", "KSamplerAdvanced"):
            _设种子(ins, 种)
        elif 类 in ("WanImageToVideo", "Wan22ImageToVideoLatent",
                    "WanFirstLastFrameToVideo", "Wan22ImageToVideo"):
            if 请求.get("帧数") and "length" in ins:
                ins["length"] = int(请求["帧数"])
            if 请求.get("宽") and "width" in ins:
                ins["width"] = int(请求["宽"])
            if 请求.get("高") and "height" in ins:
                ins["height"] = int(请求["高"])
        elif 类 == "CreateVideo":
            if 请求.get("帧率"):
                ins["fps"] = int(请求["帧率"])
        elif 类 in ("SaveVideo", "VHS_VideoCombine", "SaveAnimatedWEBP"):
            if 请求.get("帧率"):
                if "frame_rate" in ins:
                    ins["frame_rate"] = int(请求["帧率"])
                if "fps" in ins:
                    ins["fps"] = int(请求["帧率"])
            if "filename_prefix" in ins:
                ins["filename_prefix"] = 请求.get("前缀") or "影匠片"

    if not any(节.get("class_type") == "LoadImage" for 节 in wf.values()):
        raise RuntimeError("模板里没有 LoadImage 节点，接不上首帧图")
    说明.append(f"种子 {种}，图 {图名 or '（空）'}")
    return 种


def 建工作流(请求: dict) -> tuple[dict, list]:
    """读模板 + 替换参数，返回 (工作流, 说明)。不发网络。"""
    能 = 请求.get("能力")
    模板名 = 请求.get("模型id") or 默认模板.get(能)
    if not 模板名:
        raise ValueError(f"不知道能力「{能}」该用哪个模板")
    if 能 not in 已接能力:
        raise ValueError(f"本地ComfyUI 不认能力「{能}」（只接了 {' / '.join(已接能力)}）")
    wf = _净模板(_读模板(模板名))
    像 = _猜能力(wf)
    if 像 != 能:
        raise ValueError(
            f"模板「{模板名}」的节点构成看着是「{像}」，不能拿来跑「{能}」"
        )
    说明 = [f"模板 {模板名}"]
    if 能 == "文生图":
        _改文生图(wf, 请求, 说明)
    else:
        _改图生视频(wf, 请求, 说明)
    wf = {k: v for k, v in wf.items() if not k.startswith("_")}
    return wf, 说明


def buildCreate(请求: dict) -> dict:
    """纯函数：拼提交体，不联网。

    图生视频要先 预备() 把图传上去（那时才碰网络）。
    """
    wf, 说明 = 建工作流(请求)
    return {
        "端点": "/prompt",
        "方法": "POST",
        "体": {"prompt": wf},
        "_说明": "；".join(说明),
    }


# ───────────────────────────── parseCreate ─────────────────────────────


def parseCreate(响应) -> str:
    """从提交回包里认号。被拒（带 error / node_errors）交回空串。"""
    if not isinstance(响应, dict):
        return ""
    if 响应.get("error"):
        return ""
    if 响应.get("node_errors"):
        # node_errors 非空 = ComfyUI 拒收，一个节点都没跑
        return ""
    号 = 响应.get("prompt_id")
    return str(号) if 号 else ""


def 解析错误(响应, 上限: int = 400) -> str:
    if not isinstance(响应, dict):
        return 契约.解析错误默认(响应, 上限)
    片 = []
    e = 响应.get("error")
    if isinstance(e, dict):
        片.append(f"{e.get('type') or '错误'}：{e.get('message') or e.get('details') or ''}")
    elif e:
        片.append(str(e))
    节错 = 响应.get("node_errors")
    if isinstance(节错, dict) and 节错:
        for 节点, 信 in list(节错.items())[:3]:
            错们 = 信.get("errors") if isinstance(信, dict) else None
            if 错们:
                for 条 in 错们[:2]:
                    片.append(
                        f"节点 {节点}（{条.get('class_type', '?')}）："
                        f"{条.get('message') or 条.get('details') or ''}"
                    )
            else:
                片.append(f"节点 {节点}：{str(信)[:200]}")
    if not 片:
        return 契约.解析错误默认(响应, 上限)
    return "；".join(片)[:上限]


# ───────────────────────────── parseResult ─────────────────────────────


def 组轮询响应(历史, 队列=None, 任务id: str | None = None) -> dict:
    """把两个 GET 的结果包成一份轮询响应，交给 parseResult。

    ComfyUI 要同时看 `/history/<id>` 和 `/queue` 才分得清「排队」和「运行」：
    history 只在**跑完**才写，所以光看 history 的话，「刚提交」和「跑到一半」
    长得一模一样。
    """
    return {"history": 历史, "queue": 队列, "任务id": 任务id}


def 轮询端点(任务id: str) -> list[dict]:
    """驱动器照这个去 GET，然后 组轮询响应() 打包。"""
    return [
        {"端点": f"/history/{任务id}", "方法": "GET", "标签": "history"},
        {"端点": "/queue", "方法": "GET", "标签": "queue"},
    ]


def _队里的号(队列, 键: str) -> list:
    出 = []
    if not isinstance(队列, dict):
        return 出
    for 项 in 队列.get(键) or []:
        # ComfyUI 的队列条目是 [序号, prompt_id, 工作流, 附加, 节点们]
        if isinstance(项, (list, tuple)) and len(项) > 1:
            出.append(str(项[1]))
        elif isinstance(项, dict) and 项.get("prompt_id"):
            出.append(str(项["prompt_id"]))
    return 出


def _看着像条目(值) -> bool:
    return isinstance(值, dict) and ("status" in 值 or "outputs" in 值)


_视频后缀 = (".mp4", ".webm", ".mkv", ".mov", ".avi")
_音频后缀 = (".mp3", ".wav", ".flac", ".ogg", ".m4a")
_图后缀 = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")


def _判类型(名: str) -> str:
    低 = (名 or "").lower()
    if 低.endswith(_视频后缀):
        return "视频"
    if 低.endswith(_音频后缀):
        return "音频"
    if 低.endswith(_图后缀):
        return "图"
    return "未知"


def _收产物(outputs: dict) -> list[dict]:
    出 = []
    for 节点号, 出项 in (outputs or {}).items():
        if not isinstance(出项, dict):
            continue
        for 来源键 in ("images", "gifs", "videos", "audio", "files"):
            项们 = 出项.get(来源键)
            if not isinstance(项们, list):
                continue
            for 项 in 项们:
                if isinstance(项, str):
                    项 = {"filename": 项}
                if not isinstance(项, dict):
                    continue
                名 = 项.get("filename") or 项.get("name") or ""
                if not 名:
                    continue
                子 = (项.get("subfolder") or "").strip("/")
                出.append({
                    "类型": _判类型(名),
                    # 远端path 是 ComfyUI 输出目录里的相对路径，**不是**项目路径。
                    # 契约里的 path 规矩只管「喂进去的输入」，别把两者搞混。
                    "远端path": "/" + (子 + "/" if 子 else "") + 名,
                    "远端名": 名,
                    "子目录": 子,
                    "类别": 项.get("type") or "output",
                    "节点": str(节点号),
                    "来源键": 来源键,
                })
    return 出


def parseResult(轮询响应, 任务id: str | None = None) -> dict:
    """纯函数：把轮询回包翻成本项目的五态之一。

    「未知」在这里是**认真判过的结论**，不是兜底：
    号在 history 里没有、在 queue 里也没有 —— 这个活可能已经被清掉了，
    也可能其实跑完了只是 history 被重置。这时**不能报失败**，报失败会让上层重跑，
    重跑就白烧一次显卡。

    收得下的形状：
      a) {"history": {...}, "queue": {...}, "任务id": ...}   ← 推荐，用 组轮询响应() 打
      b) {"<prompt_id>": {"status": ..., "outputs": ...}}     ← /history/<id> 原样
      c) {"status": {...}, "outputs": {...}}                  ← 直接给那一条
    """
    成本 = {"金额": 0.0, "币种": "CNY", "计费": "本机自跑", "说明": "不产生 API 费用"}

    if not isinstance(轮询响应, dict):
        return {"状态": 契约.未知, "产物": [], "成本": 成本,
                "错误": f"轮询响应必须是 dict，收到 {type(轮询响应).__name__}"}

    历史 = 轮询响应.get("history")
    队列 = 轮询响应.get("queue")
    号 = 任务id or 轮询响应.get("任务id")
    if 历史 is None and 队列 is None:
        历史 = 轮询响应          # 形式 c) 或裸的 /history 回包

    # 找出这个号对应的那一条
    条 = None
    if isinstance(历史, dict):
        if 号 and 号 in 历史:
            条 = 历史[号]
        elif not 号 and len(历史) == 1:
            号 = next(iter(历史))
            条 = 历史[号]
        elif _看着像条目(历史):
            条 = 历史

    if 条 is None:
        # ComfyUI 只在跑完才写 history，所以「history 里没有」本身不代表出错
        if isinstance(队列, dict):
            跑 = _队里的号(队列, "queue_running")
            排 = _队里的号(队列, "queue_pending")
            if 号 and 号 in 跑:
                return {"状态": 契约.运行, "产物": [], "成本": 成本, "错误": ""}
            if 号 and 号 in 排:
                return {"状态": 契约.排队, "产物": [], "成本": 成本, "错误": ""}
            if 号:
                return {
                    "状态": 契约.未知, "产物": [], "成本": 成本,
                    "错误": (f"任务 {号[:8]} 既不在 history 也不在 queue —— "
                             f"队列可能被清过、ComfyUI 可能重启过。产物也许已经落盘，"
                             f"去 {os.path.join(影匠根, '作品')} 看一眼再决定要不要重跑"),
                }
            return {"状态": 契约.未知, "产物": [], "成本": 成本,
                    "错误": "没给任务号，认不出这份 history 是谁的"}
        # 没给队列信息：history 没有 = 还在跑，这是 ComfyUI 的正常时序
        return {"状态": 契约.运行, "产物": [], "成本": 成本,
                "错误": ""}

    if not isinstance(条, dict):
        return {"状态": 契约.未知, "产物": [], "成本": 成本,
                "错误": f"history[{号}] 不是 dict，是 {type(条).__name__}"}

    状 = 条.get("status")
    有输出 = isinstance(条.get("outputs"), dict)

    if not isinstance(状, dict) and not 有输出:
        return {"状态": 契约.未知, "产物": [], "成本": 成本,
                "错误": "history 里有这一条，但既没有 status 也没有 outputs —— 判不了"}

    if isinstance(状, dict):
        串 = str(状.get("status_str") or "").strip().lower()
        完成没 = 状.get("completed", True)
        if 串 in ("error", "failed") or not 完成没:
            信 = 状.get("messages") or []
            细 = "；".join(
                f"{m[0]}：{str(m[1])[:200]}" for m in 信
                if isinstance(m, (list, tuple)) and len(m) >= 2
            )[:400]
            return {
                "状态": 契约.失败, "产物": [], "成本": 成本,
                "错误": f"ComfyUI 报错（status_str={串 or '?'}）：{细 or '没给细节'}",
            }

    产物 = _收产物(条.get("outputs") or {})
    if not 产物:
        return {
            "状态": 契约.失败, "产物": [], "成本": 成本,
            "错误": "跑完了但一个输出都没有 —— 检查 SaveImage / SaveVideo 接对了没",
        }
    耗时 = 条.get("_耗时")
    if 耗时:
        成本["耗时秒"] = 耗时
    return {"状态": 契约.完成, "产物": 产物, "成本": 成本, "错误": "",
            "任务id": 号}


# ───────────────────────────── 下载 / 凭证 ─────────────────────────────


def 取回(产物: dict, 存到: str | None = None) -> str:
    """把一个产物下载到本机。返回本地绝对路径。"""
    if 引擎 is None:
        raise RuntimeError(f"`引擎.py` 没装进来（{_引擎错}）")
    图 = {
        "filename": 产物.get("远端名"),
        "subfolder": 产物.get("子目录", ""),
        "type": 产物.get("类别", "output"),
    }
    if not 图["filename"]:
        raise ValueError(f"产物里没有 远端名：{产物!r}")
    return 引擎.取图(图, 存到)


def 凭证检查() -> dict:
    """本地这套不需要 key，但需要 ComfyUI 活着。"""
    if 引擎 is None:
        return {"就绪": False, "缺": ["引擎.py"], "提示": f"`引擎.py` 没装进来：{_引擎错}"}
    在 = 引擎.在线()
    if 在.get("在线"):
        return {
            "就绪": True, "缺": [],
            "提示": (f"本机 ComfyUI {在.get('版本')} 在线｜{在.get('显卡')}｜"
                     f"显存 {在.get('显存GB')}GB（空闲 {在.get('显存空闲GB')}GB）"),
            "详情": 在,
        }
    return {
        "就绪": False, "缺": ["ComfyUI 没起来"],
        "提示": (
            f"连不上本机 ComfyUI（{_基址()}）：{在.get('错')}\n"
            f"    起法：python main.py --listen 127.0.0.1 --port 8188 "
            f"--extra-model-paths-config {os.path.join(影匠根, '模型路径.yaml')}\n"
            f"    注意：**不带 --extra-model-paths-config 的话所有加载器都是空列表**"
        ),
        "详情": 在,
    }


# ───────────────────────────── 便捷：真跑一趟 ─────────────────────────────


def 真跑(请求: dict, 报=None, 存到: str | None = None,
         上限秒: int = 1800, 间隔: float = 1.2) -> dict:
    """照三段式真提交、真轮询、真下载。给业务层用的便捷入口。

    它**不是**契约要求的，只是为了证明三段式在真服务器上跑得通：
    预备 → buildCreate → 提交 → parseCreate → 轮询 → parseResult → 取回。
    """
    报 = 报 or (lambda _: None)
    if 引擎 is None:
        raise RuntimeError(f"`引擎.py` 没装进来（{_引擎错}）")

    问题 = 契约.校验(sys.modules[__name__], 请求)
    if 问题:
        raise ValueError("请求不合格：\n  - " + "\n  - ".join(问题))

    请求 = 预备(请求)
    体 = buildCreate(请求)
    报(f"提交：{体.get('_说明', '')}")
    回 = 引擎._请求(体["端点"], 体["体"], 超时=90)
    号 = parseCreate(回)
    if not 号:
        raise RuntimeError("ComfyUI 不收这个活：" + 解析错误(回))
    报(f"已排队 {号[:8]}")

    起 = time.time()
    连未知 = 0
    上次报 = 0.0
    while True:
        等 = time.time() - 起
        if 等 > 上限秒:
            raise TimeoutError(f"等了 {上限秒} 秒还没跑完（{号[:8]}）")
        try:
            史 = 引擎._请求(f"/history/{号}", 超时=20)
        except Exception as e:
            报(f"查 history 抖了一下（{e}），接着等")
            史 = {}
        try:
            队 = 引擎._请求("/queue", 超时=10)
        except Exception:
            队 = None
        果 = parseResult(组轮询响应(史, 队, 号), 号)
        状 = 果["状态"]
        if 状 == 契约.完成:
            产 = 果["产物"][0]
            报(f"完成 {产['远端名']}（{round(等, 1)} 秒）")
            路 = 取回(产, 存到)
            return {"任务id": 号, "路": 路, "产物": 果["产物"],
                    "耗时": round(等, 1), "成本": 果["成本"], "提交体": 体}
        if 状 == 契约.失败:
            raise RuntimeError("工作流跑挂了：" + (果["错误"] or "（没给原因）"))
        if 状 == 契约.未知:
            连未知 += 1
            if 连未知 >= 3:
                raise RuntimeError(
                    "连续三次认不出这个活的状态，不再瞎等：" + (果["错误"] or "")
                )
        else:
            连未知 = 0
        if time.time() - 上次报 > 5:
            上次报 = time.time()
            报(f"{状}… 已等 {int(等)} 秒")
        time.sleep(间隔)


if __name__ == "__main__":
    import json as _json

    print("适配器：", 元数据()["名称"])
    print("模型id（= 模板名）：", "、".join(元数据()["模型"]))
    print("凭证：", 凭证检查()["提示"])
    print("ComfyUI 基址：", 基址())
    print()
    print("离线演练（假响应，不联网）：")
    for 场景, 假 in (
        ("还在排队", {"history": {}, "queue": {"queue_running": [], "queue_pending": [[0, "假号", {}, {}, []]]}, "任务id": "假号"}),
        ("跑到一半", {"history": {}, "queue": {"queue_running": [[0, "假号", {}, {}, []]], "queue_pending": []}, "任务id": "假号"}),
        ("跑完了", {"history": {"假号": {"status": {"completed": True, "status_str": "success"}, "outputs": {"9": {"images": [{"filename": "影匠_0001.png", "subfolder": "", "type": "output"}]}}}}, "queue": {}, "任务id": "假号"}),
        ("跑挂了", {"history": {"假号": {"status": {"completed": False, "status_str": "error", "messages": [["execution_error", {"exception_message": "CUDA out of memory"}]]}, "outputs": {}}}, "queue": {}, "任务id": "假号"}),
        ("号不见了", {"history": {}, "queue": {"queue_running": [], "queue_pending": []}, "任务id": "假号"}),
    ):
        果 = parseResult(假, "假号")
        print(f"  {场景:<8} → {果['状态']:<4} {果['错误'][:60] or ('产物 ' + str(len(果['产物'])) + ' 个')}")
