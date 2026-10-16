# -*- coding: utf-8 -*-
"""影匠 —— 接口/契约：模型接入层的「合同」。

这个文件只定义**规矩**，不实现任何一家供应商，也不碰网络。
零依赖：只用 Python 标准库。

为什么要有它
------------
「调用哪个模型」以前散在业务代码里。现在业务代码只认这本合同：

    业务：我要「文生图」，提示词是……
    注册表：谁有这能力？→ 挑一个适配器
    合同：先 校验(请求) 把所有毛病一次报全
    适配器：buildCreate → parseCreate → parseResult

三段式异步
----------
异步任务被拆成三个**纯函数**，各自只吃一个字典、只吐一个结果：

    buildCreate(请求)   -> 提交体      （只拼包，不发网络）
    parseCreate(响应)   -> 任务id      （只认号，不发网络）
    parseResult(轮询响应) -> {状态, 产物, 错误, 成本}   （只翻译，不发网络）

拆开的理由：**「发出去了」和「跑完了」之间隔着一次网络事故**。
合在一起写，超时那一刻你分不清是「没提交上去」还是「提交成功但回包丢了」——
前者该重试，后者重试就是**多花一次钱**。拆成三段以后，任务id 在本地落定，
网络怎么抖都不影响「这个活到底存不存在」这个事实。

同步任务（一次请求就出结果，比如方舟文生图）只实现 buildCreate + parseCreate：
parseCreate 这时返回的是**产物标识**（非空即视为已完成），不是任务号。

状态只有五个
------------
    排队 / 运行 / 完成 / 失败 / 未知

「未知」不是「失败」的委婉说法，它是一条硬规矩：

    请求**可能已经送达**、结果无法确认 → 必须判「未知」。

超时、连接被重置、502/503、轮询到一个不认识的 id、结果过了有效期——
这些情况下服务器那边**很可能已经扣了钱、跑完了活**。
判成「失败」会让上层「失败就重试」，重试 = 重复扣费 / 重复干活。
判成「未知」则逼上层去**查**（查历史、查用量、人工看一眼），而不是蒙头重来。

path 类字段
-----------
键名以 ``path`` / ``路径`` 结尾的字段，值必须是 **``/`` 开头的项目内相对路径**，
不许出现盘符、UNC、URL、``..``。理由：一份请求要能在本机 ComfyUI 与云端之间
原样搬运、能被打印进日志、能被重放。绝对路径一进去，请求就绑死在这台机器上。
``检查路径()`` 强制这条规矩。

作者：影匠 · 接口层。纯原创实现。
"""
from __future__ import annotations

import json
import re

__all__ = [
    # 状态
    "状态全集", "排队", "运行", "完成", "失败", "未知",
    "能力全集", "可选钩子",
    "归一", "可疑未知", "是终态", "是异步", "终态全集",
    # 校验
    "是路径字段", "检查路径值", "检查路径", "看着像绝对路径",
    "扫描绝对路径", "校验元数据", "校验", "缺什么函数",
    # 提交体
    "提交体必填", "校验提交体", "完整网址",
    # 注册
    "注册", "取", "要", "全部", "找能力", "有", "清空", "名字们",
    # 演练
    "解析错误默认", "走一遍",
]

# ───────────────────────────── 状态 ─────────────────────────────

排队, 运行, 完成, 失败, 未知 = "排队", "运行", "完成", "失败", "未知"
状态全集 = (排队, 运行, 完成, 失败, 未知)
终态全集 = (完成, 失败)          # 「未知」不是终态：它要求你再去查，而不是收工


def 是终态(状态: str) -> bool:
    """完成/失败 才是终态。未知不是 —— 未知要你继续查。"""
    return 状态 in 终态全集


# 各家供应商的原始写法往往指同一件事，这里是公共别名表。
# 适配器可以用 归一(原始, 表) 传自己的私有表，私有表优先。
_别名_排队 = (
    "queued", "queue", "pending", "submitted", "created", "waiting",
    "in_queue", "inqueue", "not_start", "notstart", "not_started", "starting",
    "排队", "排队中", "等待", "等待中", "已提交", "提交成功", "待处理", "准备中",
)
_别名_运行 = (
    "running", "run", "processing", "in_progress", "inprogress", "generating",
    "executing", "started", "working", "active",
    "运行", "运行中", "处理中", "生成中", "执行中", "跑着",
)
_别名_完成 = (
    "succeeded", "succeed", "success", "successful", "completed", "complete",
    "done", "finished", "ok", "ready", "ready_url",
    "完成", "已完成", "成功", "出图", "出片", "就好了",
)
_别名_失败 = (
    "failed", "fail", "failure", "error", "errored", "cancelled", "canceled",
    "cancel", "rejected", "denied", "expired_failed", "timeout_failed",
    "失败", "错误", "出错", "已取消", "取消", "被拒", "拒绝",
)
# 关键：这些词必须判「未知」。它们共同的语义是
#「东西可能已经在对面了，但这条回包不能证明它成没成」。
_别名_未知 = (
    # 网络层
    "timeout", "timedout", "timed_out", "etimedout", "connection_reset",
    "connectionerror", "connection_error", "connection_aborted", "econnreset",
    "network_error", "networkerror", "socket_error", "broken_pipe",
    "bad_gateway", "gateway_timeout", "service_unavailable", "unavailable",
    "internal_error", "server_error", "upstream_error", "5xx", "502", "503", "504",
    "dns", "ssl_error", "read_timeout",
    # 业务层「查不到 ≠ 没干」
    "unknown", "unknown_task", "task_not_found", "not_found", "404",
    "expired", "no_such_task", "taskid_invalid", "invalid_task_id",
    "lost", "orphan", "unconfirmed", "indeterminate", "unknown_state",
    # 中文
    "超时", "连接超时", "网络错误", "网络异常", "连接被重置", "连接中断",
    "未知", "无法确认", "查不到", "任务不存在", "找不到任务", "已过期",
    "结果过期", "网关错误", "服务不可用", "服务器错误", "中断", "断了", "不确定",
)

_表_公共 = {}
for _词 in _别名_排队:
    _表_公共[_词] = 排队
for _词 in _别名_运行:
    _表_公共[_词] = 运行
for _词 in _别名_完成:
    _表_公共[_词] = 完成
for _词 in _别名_失败:
    _表_公共[_词] = 失败
for _词 in _别名_未知:
    _表_公共[_词] = 未知
del _词


def _洗(原始) -> str:
    if 原始 is None:
        return ""
    return str(原始).strip().lower().replace("-", "_").replace(" ", "_")


def 可疑未知(原始) -> bool:
    """这条原始状态是不是「可能已送达、但无法确认」那一类？

    单独暴露出来，方便适配器在自己映射前先问一句。
    """
    s = _洗(原始)
    if not s:
        return True                      # 空状态 = 什么都不知道 = 未知
    if s in _别名_未知:
        return True
    # 子串兜底： "task not found"、"read timeout after 30s" 这类长句
    # 注意 _洗() 会把 - 和空格换成 _，所以长句里的 "timed out" 到这里是 "timed_out"，
    # 只写 "timeout" 会漏 —— 三个词都得在。
    for 词 in ("timeout", "timed_out", "timedout", "超时", "not_found", "not found",
               "查不到", "unknown", "无法确认", "连接", "connection", "unavailable",
               "expired", "过期"):
        if 词 in s:
            return True
    return False


def 归一(原始, 表: dict | None = None) -> str:
    """供应商原始状态 → 本项目五态之一。

    「未知」优先：只要沾了「可能已送达但无法确认」的边，一律判未知，
    绝不让它掉进「失败」——失败会触发重试，重试会重复扣费。

    表 里没写、公共表也没有的 -> 未知（不是失败）。
    """
    s = _洗(原始)
    if not s:
        return 未知
    if 表:
        私有 = {_洗(k): v for k, v in 表.items()}
        if s in 私有:
            return 私有[s]
    if s in _表_公共:
        # 公共表里「未知」的优先级高于其它：一个词同时像失败又像未知时，取未知
        return _表_公共[s]
    if 可疑未知(s):
        return 未知
    # 认识不到的一律未知：宁可让上层去查，也不要误判失败
    return 未知


# ───────────────────────────── 能力 ─────────────────────────────

能力全集 = (
    "文生图", "图生图", "图生视频", "文生视频", "首尾帧视频", "配音", "配乐",
    "超分", "补帧", "抠像", "理解", "翻译",
)


# ───────────────────────────── 路径规矩 ─────────────────────────────


def 是路径字段(键) -> bool:
    """键名以 path / 路径 结尾，就当成路径字段来查。"""
    k = _洗(键)
    return k.endswith("path") or k.endswith("路径")


_绝对路径样式 = (
    re.compile(r"^[A-Za-z]:[\\/]"),     # D:\  C:/
    re.compile(r"^\\\\"),               # \\服务器\共享
    re.compile(r"^file://", re.I),      # file:///D:/x
)


def 看着像绝对路径(值) -> bool:
    """这台机器上的绝对路径（盘符 / UNC / file://）。URL 不算。"""
    if not isinstance(值, str) or not 值:
        return False
    for 式 in _绝对路径样式:
        if 式.match(值):
            return True
    return False


_盘非法字符 = re.compile(r'[<>:"|?*\x00-\x1f]')


def 检查路径值(值) -> list[str]:
    """查一个 path 类字段的值。返回问题列表（可能是空的）。"""
    if 值 is None or 值 == "":
        return []                        # 没填不算「格式错」，必填与否归适配器管
    if isinstance(值, (list, tuple)):
        问题 = []
        for i, 项 in enumerate(值):
            问题 += [f"第{i + 1}项：{p}" for p in 检查路径值(项)]
        return 问题
    if not isinstance(值, str):
        return [f"必须是字符串（/ 开头的相对路径），现在是 {type(值).__name__}：{值!r}"]

    if 看着像绝对路径(值):
        return [f"必须是 / 开头的相对路径，不能是绝对路径：{值!r}"]
    if not 值.startswith("/"):
        return [f"必须以 / 开头（以项目根为根的相对路径）：{值!r}"]
    if 值.startswith("//"):
        return [f"不能以 // 开头（那是网络路径）：{值!r}"]
    if "\\" in 值:
        return [f"路径分隔符只能用 /，不能用 \\：{值!r}"]
    if "://" in 值:
        return [f"不能是 URL，要项目内的相对路径：{值!r}"]
    if 值.endswith("/"):
        return [f"不能以 / 结尾（要指到具体文件）：{值!r}"]
    段 = [x for x in 值.split("/") if x != ""]
    if not 段:
        return [f"只有一个 /，没指到文件：{值!r}"]
    if ".." in 段:
        return [f"不能含 ..（会跑出项目根）：{值!r}"]
    if "." in 段:
        return [f"不能含 . 段（当前目录）：{值!r}"]
    坏 = _盘非法字符.search(值)
    if 坏:
        return [f"含 Windows 非法字符 {坏.group(0)!r}：{值!r}"]
    return []


def 检查路径(请求) -> list[str]:
    """递归查一份请求里所有 path 类字段。"""
    问题: list[str] = []

    def 走(值, 位置: str):
        if isinstance(值, dict):
            for k, v in 值.items():
                位 = f"{位置}.{k}" if 位置 else str(k)
                if 是路径字段(k):
                    for p in 检查路径值(v):
                        问题.append(f"{位}：{p}")
                else:
                    走(v, 位)
        elif isinstance(值, (list, tuple)):
            for i, v in enumerate(值):
                走(v, f"{位置}[{i}]")

    走(请求, "")
    return 问题


def 扫描绝对路径(体) -> list[str]:
    """整个提交体里**任何位置**都不许出现本机绝对路径 / file:// 。

    这是第二道闸：path 规矩只管字段名，这道管内容。
    防的是「适配器不小心把 D:\\... 塞进 body 发出去」——那会把本机路径泄给云端。
    """
    问题: list[str] = []

    def 走(值, 位置: str):
        if isinstance(值, dict):
            for k, v in 值.items():
                走(v, f"{位置}.{k}" if 位置 else str(k))
        elif isinstance(值, (list, tuple)):
            for i, v in enumerate(值):
                走(v, f"{位置}[{i}]")
        elif isinstance(值, str):
            if 看着像绝对路径(值):
                问题.append(f"{位置 or '（根）'}：漏了本机绝对路径 {值!r}")

    走(体, "")
    return 问题


# ───────────────────────────── 提交体的形状 ─────────────────────────────

提交体必填 = ("端点", "方法", "体")
_方法全集 = ("GET", "POST", "PUT", "PATCH", "DELETE")


def 校验提交体(体) -> list[str]:
    """提交体统一长这样：

        {"端点": "/prompt", "方法": "POST", "体": {...}}

    「端点」是**相对路径**，主机名由适配器的 ``基址()`` 提供 —— 换环境只改一处。
    以 ``_`` 开头的键是给日志和人看的附注，驱动器原样忽略。

    顺带把第三道闸拉上：整个提交体（含附注）里不许出现本机绝对路径。
    """
    问题: list[str] = []
    if not isinstance(体, dict):
        return [f"提交体必须是 dict，现在是 {type(体).__name__}"]
    for k in 提交体必填:
        if k not in 体:
            问题.append(f"缺字段：{k}")
    if 问题:
        return 问题

    端 = 体["端点"]
    if not isinstance(端, str) or not 端.startswith("/"):
        问题.append(f"端点 必须以 / 开头（主机名交给 基址()）：{端!r}")
    elif "://" in 端 or 看着像绝对路径(端):
        问题.append(f"端点 只能是相对路径，不能带主机：{端!r}")

    方 = str(体["方法"]).upper()
    if 方 not in _方法全集:
        问题.append(f"方法 只能是 {'/'.join(_方法全集)}，收到 {体['方法']!r}")

    if not isinstance(体["体"], dict):
        问题.append(f"体 必须是 dict（GET 也要给，给空 dict）：{type(体['体']).__name__}")

    for p in 扫描绝对路径(体):
        问题.append(p)
    return 问题


def 完整网址(适配器, 提交体) -> str:
    """按适配器的 ``基址()`` 拼出可以直接请求的完整网址。

    适配器不实现 基址() 也能用 —— 那就得自己在提交体里给完整的 端点。

    飞彩原样的**第二道闸**在这里落地：``端点`` 只能是 ``/`` 开头的相对路径，
    物理上没法把请求打到别的域。这里对 ``://`` 直接判死，堵住
    「校验提交体 与 完整网址 一个拦一个放」的错位漏洞。
    """
    端 = str(提交体.get("端点") or "")
    if "://" in 端 or 看着像绝对路径(端):
        raise ValueError(f"端点只能是 / 开头的相对路径，不能带主机：{端!r}")
    底 = ""
    钩 = getattr(适配器, "基址", None)
    if callable(钩):
        try:
            底 = str(钩() or "")
        except Exception:
            底 = ""
    if not 底:
        底 = str(提交体.get("基址") or "")
    if not 底:
        return 端
    return 底.rstrip("/") + "/" + 端.lstrip("/")


# ───────────────────────────── 元数据校验 ─────────────────────────────

_元数据必填 = ("名称", "能力", "模型", "费率", "需要联网", "是否本地")


def 校验元数据(元) -> list[str]:
    问题 = []
    if not isinstance(元, dict):
        return [f"元数据必须是 dict，现在是 {type(元).__name__}"]
    for k in _元数据必填:
        if k not in 元:
            问题.append(f"元数据缺字段：{k}")
    if 问题:
        return 问题

    if not isinstance(元["名称"], str) or not 元["名称"].strip():
        问题.append("名称 必须是非空字符串")

    能力 = 元["能力"]
    if not isinstance(能力, (list, tuple)) or not 能力:
        问题.append("能力 必须是非空列表")
    else:
        for c in 能力:
            if c not in 能力全集:
                问题.append(f"能力 {c!r} 不在允许的集合里：{'/'.join(能力全集)}")

    模型 = 元["模型"]
    if not isinstance(模型, (list, tuple)):
        问题.append("模型 必须是列表（可以是空的：表示由适配器自己决定）")
    else:
        for m in 模型:
            if not isinstance(m, str) or not m.strip():
                问题.append(f"模型 id 必须是非空字符串，现在是 {m!r}")

    费率 = 元["费率"]
    if not isinstance(费率, dict):
        问题.append("费率 必须是 dict：{模型id: {单价, 单位, 币种}}")
    else:
        for mk, mv in 费率.items():
            if not isinstance(mv, dict):
                问题.append(f"费率[{mk}] 必须是 dict")
                continue
            for 键 in ("单价", "单位", "币种"):
                if 键 not in mv:
                    问题.append(f"费率[{mk}] 缺 {键}")
            # 单价允许 None —— 那是「不知道多少钱」的正经表达。
            # 逼适配器填数字的话，它只好编一个，比 None 危险得多。
            if "单价" in mv and mv["单价"] is not None and not isinstance(mv["单价"], (int, float)):
                问题.append(f"费率[{mk}].单价 必须是数字或 None，现在 {type(mv['单价']).__name__}")
            if mv.get("单价") is None and not str(mv.get("说明") or "").strip():
                问题.append(f"费率[{mk}].单价 是 None（不知道价），那就必须用 说明 写清为什么不知道")

    for k in ("需要联网", "是否本地"):
        if not isinstance(元[k], bool):
            问题.append(f"{k} 必须是 True/False，现在 {type(元[k]).__name__}")

    异 = 元.get("异步能力")
    if 异 is not None:
        if not isinstance(异, (list, tuple)):
            问题.append("异步能力 必须是列表（里面放能力名）")
        else:
            for c in 异:
                if isinstance(能力, (list, tuple)) and c not in 能力:
                    问题.append(f"异步能力里的 {c!r} 不在自己的能力列表里")

    return 问题


# ───────────────────────────── 适配器的形状 ─────────────────────────────

_必有同步 = ("元数据", "校验", "buildCreate", "parseCreate")
_必有异步 = ("parseResult",)
# 可选钩子（有就用，没有就跳过）：
#   预备(请求) -> 请求   —— 唯一允许有副作用的钩子（上传图、建会话）
#   认证() -> dict       —— 请求头，密钥只在这一个函数里出现，不进提交体
#   凭证检查() -> dict   —— {就绪, 缺, 提示}，给 注册表.可用性() 用，无 key 也不许崩
#   解析错误(响应) -> str
#   轮询端点(任务id) -> [提交体]   —— 告诉驱动器该 GET 谁
#   取回(产物, 存到) -> 本地路径
可选钩子 = ("预备", "认证", "凭证检查", "解析错误", "轮询端点", "取回", "成本")


def 是异步(适配器, 能力: str) -> bool:
    """这项能力是不是三段式异步？"""
    元 = 适配器.元数据()
    异 = 元.get("异步能力")
    if 异 is None:
        return bool(元.get("异步", False))
    return 能力 in 异


def 缺什么函数(适配器) -> list[str]:
    """适配器该有的函数缺了哪些。"""
    问题 = []
    for 名 in _必有同步:
        if not callable(getattr(适配器, 名, None)):
            问题.append(f"缺函数 {名}()")
    if 问题:
        return 问题
    try:
        元 = 适配器.元数据()
    except Exception as e:
        return [f"元数据() 一调就炸：{e!r}"]
    for 能 in (元.get("能力") or []):
        if 是异步(适配器, 能) and not callable(getattr(适配器, "parseResult", None)):
            问题.append(f"能力「{能}」声明是异步的，但没有 parseResult()")
    return 问题


def 校验(适配器, 请求) -> list[str]:
    """通用校验 + 适配器自己的校验。**一次报全，不抛异常。**

    调用方拿到非空列表就该停手，不要拿一份坏请求去 buildCreate。
    """
    问题: list[str] = []
    if not isinstance(请求, dict):
        return [f"请求必须是 dict，现在是 {type(请求).__name__}"]

    元问题 = 校验元数据(适配器.元数据())
    问题 += [f"（适配器自己的元数据有问题）{p}" for p in 元问题]

    能 = 请求.get("能力")
    if not 能:
        问题.append("请求缺 能力")
    elif 能 not in (适配器.元数据().get("能力") or []):
        问题.append(f"适配器「{适配器.元数据().get('名称')}」不支持能力「{能}」")

    模 = 请求.get("模型id") or 请求.get("模型")
    模型表 = 适配器.元数据().get("模型") or []
    if 模 and 模型表 and 模 not in 模型表:
        问题.append(f"模型「{模}」不在适配器支持的列表里：{'、'.join(map(str, 模型表))}")

    问题 += 检查路径(请求)
    问题 += 扫描绝对路径(请求)

    # 适配器自己的规矩，最后加
    try:
        自家 = 适配器.校验(请求)
    except Exception as e:
        自家 = [f"适配器.校验() 自己抛异常了（契约要求返回问题列表）：{e!r}"]
    if 自家 is None:
        自家 = []
    if isinstance(自家, str):
        自家 = [自家]
    问题 += [str(x) for x in 自家]

    # 去重但保序
    出, 见 = [], set()
    for p in 问题:
        if p not in 见:
            见.add(p)
            出.append(p)
    return 出


# ───────────────────────────── 注册表 ─────────────────────────────

_库: dict[str, object] = {}


def 注册(适配器, 覆盖: bool = False) -> str:
    """登记一个适配器。返回它的名字。形状不对就抛（这是装配期错误，该早炸）。"""
    问题 = 缺什么函数(适配器)
    if 问题:
        raise ValueError(
            f"适配器形状不对，注册不了：{'; '.join(问题)}"
        )
    元问题 = 校验元数据(适配器.元数据())
    if 元问题:
        raise ValueError(f"适配器元数据不合格：{'; '.join(元问题)}")
    名 = 适配器.元数据()["名称"]
    if 名 in _库 and not 覆盖:
        raise ValueError(f"已经有叫「{名}」的适配器了（想顶掉就传 覆盖=True）")
    _库[名] = 适配器
    return 名


def 取(名称):
    """按名字拿。没有就返回 None。"""
    return _库.get(名称)


def 要(名称):
    """按名字拿。没有就抛 —— 调用方明确知道自己要谁时用这个。"""
    a = _库.get(名称)
    if a is None:
        raise KeyError(f"没有叫「{名称}」的适配器。已登记：{'、'.join(_库) or '（空）'}")
    return a


def 全部() -> list:
    return list(_库.values())


def 找能力(能力: str) -> list:
    return [a for a in _库.values() if 能力 in (a.元数据().get("能力") or [])]


def 有(名称: str) -> bool:
    return 名称 in _库


def 名字们() -> list[str]:
    return list(_库)


def 清空():
     _库.clear()


# ───────────────────────────── 演练 ─────────────────────────────


def 解析错误默认(响应, 上限: int = 300) -> str:
    """从一份响应里尽力捞一句人话。适配器没实现 解析错误() 时用这个。"""
    if 响应 is None:
        return "（响应为空）"
    if isinstance(响应, dict):
        for k in ("错误", "error", "message", "msg", "detail", "reason",
                  "error_message", "errmsg"):
            v = 响应.get(k)
            if v:
                if isinstance(v, dict):
                    v = v.get("message") or v.get("msg") or v.get("code") or json.dumps(
                        v, ensure_ascii=False)
                return f"{k}: {str(v)[:上限]}"
    try:
        文 = json.dumps(响应, ensure_ascii=False)
    except Exception:
        文 = repr(响应)
    return 文[:上限]


def 走一遍(适配器, 请求, 提交响应, 轮询响应们=None, 最多轮: int = 200) -> dict:
    """拿**假响应**把三段式跑通一遍：校验 → buildCreate → parseCreate → parseResult。

    这是契约自带的演练台。真适配器、假响应 —— 不联网也能验逻辑，
    也就不会因为「没 key / 服务器忙」而假装测过了。

    返回一份带 通过/问题 的轨迹，任何一步出岔子都记下来，不抛。
    """
    轨迹 = {
        "适配器": None, "请求": 请求, "提交体": None, "任务id": None,
        "轮询": [], "状态": None, "产物": [], "错误": "", "成本": None,
        "通过": False, "问题": [],
    }
    try:
        轨迹["适配器"] = 适配器.元数据().get("名称")
    except Exception as e:
        轨迹["问题"].append(f"元数据() 炸了：{e!r}")
        return 轨迹

    # ① 校验
    问题 = 校验(适配器, 请求)
    if 问题:
        轨迹["问题"] += 问题
        return 轨迹

    # ② 拼包
    try:
        提交体 = 适配器.buildCreate(请求)
    except Exception as e:
        轨迹["问题"].append(f"buildCreate() 抛异常了：{e!r}")
        return 轨迹
    if not isinstance(提交体, dict):
        轨迹["问题"].append(f"buildCreate() 必须返回 dict，返回了 {type(提交体).__name__}")
        return 轨迹
    轨迹["提交体"] = 提交体

    for p in 校验提交体(提交体):
        轨迹["问题"].append(f"提交体不合格：{p}")

    # ③ 认号
    try:
        任务id = 适配器.parseCreate(提交响应)
    except Exception as e:
        轨迹["问题"].append(f"parseCreate() 抛异常了：{e!r}")
        return 轨迹
    轨迹["任务id"] = 任务id

    异步 = 是异步(适配器, 请求.get("能力", ""))

    # 同步能力：parseCreate 交回来的就是产物标识，非空即完成
    if not 异步:
        if 任务id:
            轨迹["状态"] = 完成
            轨迹["产物"] = [任务id] if not isinstance(任务id, (list, tuple)) else list(任务id)
            轨迹["通过"] = not 轨迹["问题"]
        else:
            轨迹["状态"] = 失败
            轨迹["错误"] = _拿错误(适配器, 提交响应)
        return 轨迹

    # 异步能力：任务id 空 = 明确被拒 = 失败（不是未知：我们拿到了回包，回包说没成）
    if not 任务id:
        轨迹["状态"] = 失败
        轨迹["错误"] = _拿错误(适配器, 提交响应)
        轨迹["通过"] = not 轨迹["问题"]
        return 轨迹

    # ④ 轮询
    轮询响应们 = list(轮询响应们 or [])
    if not 轮询响应们:
        轨迹["状态"] = 排队
        轨迹["问题"].append("没有给任何轮询响应，只能停在「排队」")
        return 轨迹

    for i, 响应 in enumerate(轮询响应们[:最多轮]):
        try:
            果 = 适配器.parseResult(响应)
        except Exception as e:
            轨迹["问题"].append(f"parseResult() 第{i + 1}轮抛异常了：{e!r}")
            return 轨迹
        if not isinstance(果, dict):
            轨迹["问题"].append(f"parseResult() 必须返回 dict，第{i + 1}轮返回了 {type(果).__name__}")
            return 轨迹
        for 键 in ("状态", "产物", "错误", "成本"):
            if 键 not in 果:
                轨迹["问题"].append(f"parseResult() 第{i + 1}轮少了键「{键}」")
        状 = 果.get("状态")
        if 状 not in 状态全集:
            轨迹["问题"].append(f"parseResult() 第{i + 1}轮状态 {状!r} 不在五态里")
        轨迹["轮询"].append({"第几轮": i + 1, "状态": 状})
        轨迹["状态"] = 状
        轨迹["产物"] = 果.get("产物") or []
        轨迹["错误"] = 果.get("错误") or ""
        轨迹["成本"] = 果.get("成本")
        if 状 in 终态全集:
            break

    轨迹["通过"] = (not 轨迹["问题"]) and (轨迹["状态"] in 终态全集)
    return 轨迹


def _拿错误(适配器, 响应) -> str:
    自家 = getattr(适配器, "解析错误", None)
    if callable(自家):
        try:
            return str(自家(响应))
        except Exception as e:
            return f"解析错误() 自己炸了：{e!r}；原始响应：{解析错误默认(响应)}"
    return 解析错误默认(响应)


# ═══════════════════════ 飞彩 SDK 的四道安全闸门 ═══════════════════════
#
# 出处（实测，逐字）：`D:\DSHworkspace\素材\网盘\_飞彩解包\Win\docs\model-plugin-example\echo-image\`
# 的 adapter.js 顶部注释与 plugin.json：
#
#   「适配器是「纯函数」:不发网络请求、不读密钥、不碰文件系统。它只做两件事:
#     ① 把宿主给的归一化请求 → 拼成 HTTP 意图(方法 + 相对路径 + body)
#     ② 把宿主拿回的上游响应 JSON → 解析成归一化结果。
#     其余一切(拼实例 baseUrl、注入鉴权、发请求、b64 落盘换短链)由宿主执行。
#     注意:path 只能是 "/" 开头的相对路径 —— 你物理上无法把请求打到别的域。」
#
# 四道闸门（plugin.json 字段 → 闸门）：
#   ① allowedHosts: ["api.example.com"]   —— 只许打这些域
#   ② path 必须以 "/" 开头                —— 物理上出不了这个域
#   ③ auth.type: "bearer"                 —— 密钥由宿主注入，适配器碰不到
#   ④ requiredSdk: 1                      —— SDK 版本门
#
# 影匠的落法：①②已由 检查路径值/校验提交体/完整网址 强制；
# ③④按「纯函数」这条原则压成可测的 纯函数闸。

_SDK_本版 = 1

# 纯函数如果 import 了这些，就等于把「发网络」写进了自己身上。
_网络模块名 = ("requests", "httpx", "aiohttp", "urllib", "urllib3", "http.client",
             "socket", "ftplib", "telnetlib", "smtplib", "websocket", "websockets",
             "pycurl", "treq", "niquests")


def 校验SDK(适配器) -> list[str]:
    """第④道闸：requiredSdk 版本门。适配器可以不写（默认跟本版一致）。"""
    问题: list[str] = []
    要 = getattr(适配器, "要求SDK", None)
    if 要 is None:
        return []
    if not isinstance(要, int) or isinstance(要, bool):
        问题.append(f"要求SDK 必须是整数，现在是 {type(要).__name__}")
    elif 要 > _SDK_本版:
        问题.append(f"插件要求 SDK {要}，本机只有 {_SDK_本版} —— 拒绝装载（飞彩 requiredSdk 同款）")
    return 问题


def 校验宿主(适配器, 网址: str) -> list[str]:
    """第①道闸：allowedHosts。适配器可以不声明（就是「本机/内置」，不算违规）。

    声明了就必须命中 —— 支持 ``*.example.com`` 通配前缀。
    """
    允许 = getattr(适配器, "允许主机", None)
    if 允许 is None:
        return []
    if not isinstance(允许, (list, tuple)) or not 允许:
        return ["允许主机 必须是非空列表，比如 [\"api.example.com\"]"]
    主 = _取主机(网址)
    if not 主:
        return [f"网址里认不出主机名：{网址!r}"]
    for 条 in 允许:
        条 = str(条).strip().lower()
        if not 条:
            continue
        if 条.startswith("*."):
            if 主 == 条[2:] or 主.endswith(条[1:]):
                return []
        elif 主 == 条:
            return []
    return [f"主机 {主!r} 不在适配器声明的白名单里：{'/'.join(map(str, 允许))} "
            f"（飞彩 allowedHosts 同款）"]


def _取主机(网址: str) -> str:
    s = str(网址 or "")
    if "://" in s:
        s = s.split("://", 1)[1]
    s = s.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in s:
        s = s.rsplit("@", 1)[1]
    if s.startswith("["):                       # [::1]:8188
        return s[1:].split("]", 1)[0].lower()
    if ":" in s:
        s = s.split(":", 1)[0]
    return s.strip().lower()


def 校验成对(适配器, 能力: str) -> list[str]:
    """异步协议 buildPoll / parsePoll 必须成对（飞彩 adapter.js 逐字规矩）。

    影匠的钩子名是 ``轮询端点`` / ``parseResult``：声明了 ``异步能力`` 里有这一项，
    两个就都得在；只写一个就是「只会提交、不会收尾」，会把任务永远吊在「运行」。
    """
    if not 是异步(适配器, 能力):
        return []
    有端点, 有解析 = True, True
    钩 = getattr(适配器, "轮询端点", None)
    # 轮询端点 是可选钩子：没有的话由驱动器按任务id 猜 —— 但 parseResult 是必有异步
    有端点 = callable(钩)
    有解析 = callable(getattr(适配器, "parseResult", None))
    if 有解析 and not 有端点:
        return []          # 驱动器兜底：没有 轮询端点 就按 id 拼，不算错
    if not 有解析:
        return [f"能力 {能力!r} 是异步的，但 parseResult 不在 —— 提交出去就收不回来了"]
    return []


def 校验纯函数(适配器) -> list[str]:
    """第③道闸 + 「纯函数」原则：适配器不许自己发网络、不许 import 网络库。

    查的是**适配器自己那个文件的源码**，不是运行时行为 —— 所以零副作用、不联网。
    """
    问题: list[str] = []
    源 = getattr(适配器, "__file__", None) or getattr(
        __import__("sys").modules.get(getattr(适配器, "__name__", ""), None), "__file__", None)
    try:
        import inspect
        文件 = inspect.getsourcefile(适配器)
    except Exception:
        文件 = 源
    if not 文件:
        return []                                    # 查不到源码就不乱扣帽子
    try:
        with open(文件, "r", encoding="utf-8") as f:
            文 = f.read()
    except Exception as e:
        问题.append(f"读不到适配器源码（{e!r}）——纯函数闸没法查")
        return 问题
    脏 = []
    for 名 in _网络模块名:
        if re.search(r"(?m)^\s*(?:import|from)\s+" + re.escape(名) + r"\b", 文):
            脏.append(名)
    if 脏:
        问题.append("适配器自己 import 了网络库：" + "、".join(脏)
                    + "（飞彩规矩：发请求由宿主做，适配器是纯函数）")
    无副 = getattr(适配器, "有副作用钩子", None)
    if 无副 is None:
        问题.append("缺 有副作用钩子 声明 —— 哪几个钩子会碰网络必须写出来，"
                    "不然「纯函数」只是句口号")
    return 问题


# ═══════════════════════════ 自测 ═══════════════════════════


class _数:
    def __init__(self):
        self.过 = self.败 = self.没测 = 0
        self.败项: list[str] = []

    def 测(self, 名, 条件, 详情=""):
        if 条件:
            self.过 += 1
            print(f"  ✓ {名}")
        else:
            self.败 += 1
            self.败项.append(名)
            print(f"  ✗ {名} {详情}")

    def 抛(self, 名, 函数, 异常, 含=""):
        try:
            函数()
        except 异常 as e:
            if 含 and 含 not in str(e):
                self.测(名, False, f"异常话里没有「{含}」：{e}")
            else:
                self.测(名, True)
            return
        except Exception as e:
            self.测(名, False, f"抛的是 {type(e).__name__}，不是 {异常.__name__}：{e}")
            return
        self.测(名, False, "没抛")

    def 小结(self, 谁):
        print()
        print(f"{谁} 自测：通过 {self.过}，失败 {self.败}，没测 {self.没测}")
        if self.败项:
            print("失败项：")
            for x in self.败项:
                print(f"  - {x}")
        print("✓ 自测全过。" if not self.败 else "✗ 自测没过。")


class _假适配器:
    """一份合格的假适配器。测试时按需改坏某一个点。"""
    __file__ = __file__
    名称 = "假适配器"
    有副作用钩子 = ("预备",)          # 飞彩规矩：会碰网络的钩子必须写出来

    要求SDK = 1

    def 元数据(self):
        return {"名称": "假适配器", "能力": ["文生图"], "模型": ["m1"],
                "费率": {"m1": {"单价": 0.0, "单位": "张", "币种": "CNY"}},
                "需要联网": False, "是否本地": True}

    def 校验(self, 请求):
        return []

    def buildCreate(self, 请求):
        return {"端点": "/v1/gen", "方法": "POST", "体": {"prompt": 请求.get("提示词", "")}}

    def parseCreate(self, 响应):
        return " 任务-1 "

    def 基址(self):
        return "http://127.0.0.1:9999"


def 自测() -> int:
    c = _数()
    假 = _假适配器()

    print("一、状态机与终态（飞彩五态）")
    c.测("五态齐全", 状态全集 == ("排队", "运行", "完成", "失败", "未知"), str(状态全集))
    c.测("未知 不是终态", not 是终态(未知))
    c.测("完成 / 失败 是终态", 是终态(完成) and 是终态(失败))
    c.测("可疑未知：空状态 = 什么都不知道", 可疑未知(""))
    c.测("可疑未知：超时长句", 可疑未知("Read timed out"))
    c.测("可疑未知：查不到长句", 可疑未知("task not found after 3 tries"))
    c.测("可疑未知：认不出的错默认最保守", 可疑未知("喵喵喵") is False
         and 归一("喵喵喵") == 未知)
    c.测("归一：502 判未知（不是失败）", 归一("502") == 未知)
    c.测("归一：connection reset 判未知", 归一("ConnectionReset") == 未知)
    c.测("归一：超时判未知", 归一("timeout") == 未知)
    c.测("归一：明确失败还是失败（未知没把所有东西都吃掉）", 归一("failed") == 失败)

    print()
    print("二、第①道闸 allowedHosts（飞彩 plugin.json 字段）")
    c.测("没声明白名单 = 不拦（内置适配器）", 校验宿主(假, "http://any.host/x") == [])
    假.允许主机 = ["127.0.0.1"]
    c.测("命中的放行", 校验宿主(假, "http://127.0.0.1:9999/v1") == [])
    c.测("不命中的拦下", 校验宿主(假, "https://evil.com/x") != [])
    c.测("换域被拦（端点写相对路径也白搭）",
         校验宿主(假, "https://api.openai.com/v1") != [])
    假.允许主机 = ["*.volces.com"]
    c.测("通配 *.volces.com 命中子域",
         校验宿主(假, "https://ark.cn-beijing.volces.com/api/v3") == [])
    c.测("通配不命中别的域", 校验宿主(假, "https://volces.com.evil.com/x") != [])
    del 假.允许主机
    c.测("_取主机 会剥端口", _取主机("http://a.b:8188/x") == "a.b")
    c.测("_取主机 认 IPv6", _取主机("http://[::1]:8188/x") == "::1")
    c.测("_取主机 剥掉 user:pass@", _取主机("http://u:p@a.b/x") == "a.b")

    print()
    print("三、第②道闸 path 只能是 / 开头的相对路径")
    c.测("相对路径放行", 检查路径值("/a/b.png") == [])
    c.测("盘符拒", 检查路径值("D:\\a.png") != [])
    c.测("UNC 拒", 检查路径值("\\\\服务器\\共享") != [])
    c.测("file:// 拒", 检查路径值("file:///D:/a.png") != [])
    c.测("URL 拒", 检查路径值("/x") == [] and 检查路径值("http://a/b") != [])
    c.测(".. 拒", 检查路径值("/a/../../etc/passwd") != [])
    c.测("反斜杠拒", 检查路径值("/a\\b") != [])
    c.测("整份请求里递归查 path 键",
         检查路径({"图path": "D:\\x.png"}) != [])
    c.测("扫描绝对路径：体里混进本机路径也拦",
         扫描绝对路径({"body": {"u": "D:\\secret.png"}}) != [])
    c.抛("完整网址 堵掉带主机的端点（错位漏洞）",
         lambda: 完整网址(假, {"端点": "https://evil.com/steal", "方法": "POST", "体": {}}),
         ValueError, "相对路径")
    c.测("端点相对 + 基址 → 拼成完整网址",
         完整网址(假, {"端点": "/v1/gen", "方法": "POST", "体": {}}) == "http://127.0.0.1:9999/v1/gen")

    print()
    print("四、第③道闸「适配器是纯函数」")
    c.测("合格适配器过闸", 校验纯函数(假) == [], str(校验纯函数(假)))

    class _带网络:
        __file__ = __file__
        有副作用钩子 = ("预备",)

    import tempfile, os
    临 = os.path.join(tempfile.gettempdir(), "_契约自测_网络适配器.py")
    with open(临, "w", encoding="utf-8") as f:
        f.write("import requests\n有副作用钩子 = ('预备',)\n")
    器 = type("_器", (), {"__file__": 临})()
    问 = 校验纯函数(器)
    c.测("import requests 的适配器被拦", any("requests" in x for x in 问), str(问))
    os.unlink(临)

    临2 = os.path.join(tempfile.gettempdir(), "_契约自测_无声明.py")
    with open(临2, "w", encoding="utf-8") as f:
        f.write("# 干干净净，但没说哪个钩子有副作用\n")
    器2 = type("_器2", (), {"__file__": 临2})()
    c.测("不声明 有副作用钩子 的被拦",
         any("有副作用钩子" in x for x in 校验纯函数(器2)), str(校验纯函数(器2)))
    os.unlink(临2)

    print()
    print("五、第④道闸 requiredSdk + 异步成对")
    c.测("不写 要求SDK = 跟随本版，放行", 校验SDK(假) == [])
    假.要求SDK = 99
    c.测("要求 SDK 99 被拒", 校验SDK(假) != [], str(校验SDK(假)))
    假.要求SDK = 1
    c.测("要求 SDK 1 放行", 校验SDK(假) == [])

    异 = type("_异", (), {
        "元数据": lambda self: {"名称": "x", "能力": ["图生视频"], "模型": [], "费率": {},
                                "需要联网": False, "是否本地": True, "异步能力": ["图生视频"]},
    })()
    c.测("异步但没 parseResult → 拦（飞彩：buildPoll/parsePoll 必须成对）",
         校验成对(异, "图生视频") != [], str(校验成对(异, "图生视频")))
    异.parseResult = lambda *a, **k: {}
    c.测("成对了就放行", 校验成对(异, "图生视频") == [], str(校验成对(异, "图生视频")))
    c.测("同步能力不受成对闸管", 校验成对(假, "文生图") == [])

    print()
    print("六、元数据 / 提交体 的老闸没被改坏")
    c.测("假适配器元数据合格", 校验元数据(假.元数据()) == [], str(校验元数据(假.元数据())))
    坏 = 假.元数据()
    坏["费率"]["m1"].pop("币种")
    c.测("费率缺币种被拦", 校验元数据(坏) != [])
    坏2 = 假.元数据()
    坏2["费率"]["m1"]["单价"] = None
    c.测("单价 None 但没写说明 → 拦（不许编价）", 校验元数据(坏2) != [])
    坏2["费率"]["m1"]["说明"] = "本地不算钱"
    c.测("写了说明就放行", 校验元数据(坏2) == [], str(校验元数据(坏2)))
    c.测("提交体合格", 校验提交体({"端点": "/x", "方法": "POST", "体": {}}) == [])
    c.测("提交体缺字段被拦", 校验提交体({"端点": "/x"}) != [])
    c.测("端点带主机被拦",
         校验提交体({"端点": "https://a/b", "方法": "POST", "体": {}}) != [])

    print()
    print("七、走一遍（离线驱动，给假响应）")
    轨 = 走一遍(假, {"能力": "文生图", "提示词": "一只猫"},
                {"data": [{"url": "http://x/1.png"}]}, None)
    c.测("同步能力一把过", 轨.get("通过") is True, str(轨))
    c.测("产物拿到了", bool(轨.get("产物")), str(轨.get("产物")))

    c.小结("契约.py")
    return 0 if c.败 == 0 else 1


if __name__ == "__main__":
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
    命 = _sys.argv[1] if len(_sys.argv) > 1 else "自测"
    if 命 in ("自测", "自查", "test"):
        raise SystemExit(自测())
    print(f"用法：python 契约.py 自测")
    raise SystemExit(2)
