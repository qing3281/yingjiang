# -*- coding: utf-8 -*-
"""影匠 —— 接口/火山方舟：云端适配器骨架（火山方舟 / 豆包系列通用 HTTP 契约）。

**这个文件不发任何真实网络请求。** 它只有：
  ① 按方舟的 HTTP 契约拼包 / 拆包（纯函数）
  ② 没配 key 时给人话，而不是崩
  ③ 一套本地伪造响应，用来离线验证三段式

为什么是「骨架」而不是「能用」
------------------------------
按合同要求，本机没有 key、也不许拿真 key 去试，所以**没有任何一条真实调用被验证过**。
凡是没有被验证的，这里一律标 `未验证`，不吹成「已对接」。

方舟的 HTTP 契约（照官方文档抄的字段名，不是猜的）
--------------------------------------------------
  图片（同步，一次就出结果）
      端点  /images/generations
      体    {"model", "prompt", "image"?, "size", "response_format", "watermark"}
      回    {"data": [{"url": ...} 或 {"b64_json": ...}], "usage": {"generated_images": n}}
  视频（异步，先提交拿 id，再轮询）
      提交  /contents/generations/tasks   body {"model", "content": [{"type": "text", "text": ...}]}
      轮询  /contents/generations/tasks/{id}
      回    {"id", "status": queued|running|succeeded|failed, "content": {"video_url"}, "error": {...}}

  关键点：方舟返回的 URL 是**带签名参数的临时地址**（?X-Tos-...&X-Amz-...），
  有效期有限。所以对云的产物，**「过没过期」和「跑没跑成」是两件事**——
  过期属于「东西生成过、但我现在拿不到」，绝不能判失败（判失败就会重跑 = 再扣一次钱）。

同步 vs 异步
------------
方舟图片是同步的（一次请求就出结果），所以 `元数据()["异步能力"]` 里**没有文生图**：
契约规定同步能力只实现 buildCreate + parseCreate，`parseCreate` 返回的是**产物标识**
（data[0] 的 url / b64），非空即视为完成。视频是异步的，三段全上。

密钥
----
`ARK_API_KEY`（必需）、`ARK_BASE_URL`（可选，默认官方地址）、`ARK_MODEL_图片` /
`ARK_MODEL_视频`（可选）。密钥**只出现在 认证() 一个函数里**，绝不进提交体 ——
提交体是要被打印、被落盘、被重放的，密钥进去就等于泄了。

作者：影匠 · 接口层。纯原创实现。
"""
from __future__ import annotations

import os
import sys

这里 = os.path.dirname(os.path.abspath(__file__))
if 这里 not in sys.path:
    sys.path.insert(0, 这里)


def _装契约():
    try:
        import 契约  # type: ignore
        return 契约
    except Exception:
        import importlib.util

        p = os.path.join(这里, "契约.py")
        spec = importlib.util.spec_from_file_location("_影匠_契约", p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        return m


契约 = _装契约()

默认基址 = "https://ark.cn-beijing.volces.com/api/v3"

# 键名 -> 方舟的 model id。改这里不用动代码。
模型_图片 = os.environ.get("ARK_MODEL_图片") or "doubao-seedream-4-0-250828"
模型_视频 = os.environ.get("ARK_MODEL_视频") or "doubao-seedance-1-0-pro-250528"

# 方舟原始状态 -> 本项目五态。私有表先查，查不到再落到公共表。
状态表 = {
    "queued": 契约.排队, "pending": 契约.排队, "created": 契约.排队,
    "running": 契约.运行, "processing": 契约.运行, "in_progress": 契约.运行,
    "succeeded": 契约.完成, "success": 契约.完成, "completed": 契约.完成,
    "failed": 契约.失败, "error": 契约.失败,
    "cancelled": 契约.失败, "canceled": 契约.失败,
    # ↓ 这三个是重点：东西可能已经生成过，只是这条回包证明不了 → 未知，不是失败
    "expired": 契约.未知, "timeout": 契约.未知, "not_found": 契约.未知,
}


def 基址() -> str:
    return (os.environ.get("ARK_BASE_URL") or 默认基址).rstrip("/")


def 元数据() -> dict:
    return {
        "名称": "火山方舟",
        "能力": ["文生图", "图生视频", "图生图"],
        # 两个模型 id 都来自环境变量，所以「支持的模型列表」就是当前配置的这两个
        "模型": [模型_图片, 模型_视频],
        "费率": {
            模型_图片: {"单价": None, "单位": "张", "币种": "CNY",
                        "说明": "未验证：方舟按张计费，价目随模型/档位变，请以控制台账单为准"},
            模型_视频: {"单价": None, "单位": "次", "币种": "CNY",
                        "说明": "未验证：方舟按『分辨率×时长』计费，5 秒与 10 秒不是一个价"},
        },
        "需要联网": True,
        "是否本地": False,
        # 只有视频是「提交→轮询」；图片一次请求就出结果，属同步能力
        "异步能力": ["图生视频"],
        "备注": "骨架：HTTP 契约按官方文档抄，但**没有任何真实调用被验证过**（本机无 key）。",
        "端点": 基址(),
        "未验证": 未验证项(),
    }


# ───────────────────────────── 模型挑选 ─────────────────────────────


def 挑模型(请求: dict) -> str:
    """请求里的模型id 优先；没给就按能力给个默认。"""
    给 = 请求.get("模型id") or 请求.get("模型")
    if 给:
        return str(给)
    能 = 请求.get("能力")
    if 能 == "文生图" or 能 == "图生图":
        return 模型_图片
    if 能 == "图生视频":
        return 模型_视频
    return ""


# ───────────────────────────── 校验 ─────────────────────────────


def 校验(请求) -> list[str]:
    """请求**本身**合不合格。

    注意这里**不查 ARK_API_KEY** —— 有没有 key 是「这台机器能不能用」，
    归 凭证检查() / 注册表.可用性() 管。混进来的话，离线拼包和离线演练
    就永远过不了校验，等于把「环境没配好」和「请求写错了」搅成一团。
    """
    问题: list[str] = []
    if not isinstance(请求, dict):
        return [f"请求必须是 dict，现在是 {type(请求).__name__}"]

    能 = 请求.get("能力")
    if 能 not in ("文生图", "图生图", "图生视频"):
        return 问题 + [f"火山方舟 现在只接了 文生图 / 图生图 / 图生视频，不认「{能}」"]

    if not str(请求.get("提示词") or "").strip():
        问题.append("提示词 不能空（方舟会直接拒）")

    尺 = 请求.get("尺寸") or 请求.get("size")
    if 尺 and not isinstance(尺, str):
        问题.append(f"尺寸 必须是字符串（如 '2K' / '1024x1024'），现在是 {type(尺).__name__}")

    if 能 == "图生视频":
        秒 = 请求.get("时长秒")
        if 秒 is not None:
            if isinstance(秒, bool) or not isinstance(秒, (int, float)):
                问题.append(f"时长秒 必须是数字，现在是 {type(秒).__name__}")
            elif not (1 <= 秒 <= 60):
                问题.append(f"时长秒={秒} 超出范围 [1, 60]")
        分 = 请求.get("分辨率")
        if 分 and 分 not in ("480p", "720p", "1080p"):
            问题.append(f"分辨率 只能是 480p / 720p / 1080p，收到 {分!r}")

    if 能 == "图生图" and not (请求.get("参考图path") or 请求.get("首帧path")):
        问题.append("图生图 必须给 参考图path（/ 开头的相对路径）")

    if 能 == "文生图" and 请求.get("首帧path"):
        问题.append("文生图 不吃 首帧path（想拿图当底就写「图生图」）")

    return 问题


def 未验证项() -> list[str]:
    """哪些东西**没被验证过**。老实列出来，别让下一手误以为这是接通了的适配器。"""
    return [
        "真实鉴权没跑过（本机没有 ARK_API_KEY，也不许拿真 key 试）",
        "返回体字段名是按官方文档抄的，没跟真实回包比对过",
        "状态表 里的 expired / not_found 映射是按「可能已扣费」的逻辑推的，没实证",
        "图生图/图生视频 的图片入参需要公网 URL，本机没有上传通道 —— 这一段是**断的**",
        "费率没查价，一律 None",
    ]


# ───────────────────────────── 认证 ─────────────────────────────


def 认证() -> dict:
    """密钥只在这里出现。没 key 时抛 —— 但调用方（驱动器）会在 凭证检查() 那步先拦住。"""
    k = os.environ.get("ARK_API_KEY")
    if not k:
        raise RuntimeError(
            "没配 ARK_API_KEY。设一下再跑：$env:ARK_API_KEY='你的key'（只放环境变量，别写进代码）"
        )
    return {
        "Authorization": f"Bearer {k}",
        "Content-Type": "application/json",
    }


def 在线不() -> bool:
    return bool(os.environ.get("ARK_API_KEY"))


def 凭证检查() -> dict:
    """没 key 也不许崩 —— 这是契约的硬要求。"""
    if 在线不():
        return {
            "就绪": True, "缺": [],
            "提示": f"ARK_API_KEY 已配置（{基址()}）｜图片模型 {模型_图片}｜视频模型 {模型_视频}"
                    "｜注意：本适配器仍是骨架，没有真实调用被验证过",
        }
    return {
        "就绪": False,
        "缺": ["ARK_API_KEY"],
        "提示": (
            "没配 ARK_API_KEY —— 云端这套现在只能离线拼包。\n"
            "    配法（当前窗口有效）：$env:ARK_API_KEY='你的key'\n"
            "    永久（用户级）：[Environment]::SetEnvironmentVariable('ARK_API_KEY','你的key','User')\n"
            "    可选：ARK_BASE_URL / ARK_MODEL_图片 / ARK_MODEL_视频\n"
            "    key 只从环境变量读，代码里一个字符都没写死"
        ),
    }


# ───────────────────────────── buildCreate ─────────────────────────────


def _联网图(相对路径: str) -> str:
    """把一个项目内相对路径变成能发给方舟的 URL。

    方舟收的是 URL 或 base64，**不收本机路径**。本机文件要先传到能公网访问的地方
    （或转 base64 内联）。这里没做 —— 因为那需要对象存储/上传通道，
    而本机没有配。**所以图生图/图生视频的「真跑」这一段是断的，如实标出来。**
    """
    if isinstance(相对路径, str) and 相对路径.startswith(("http://", "https://")):
        return 相对路径
    底 = os.environ.get("影匠_素材公网前缀")
    if 底:
        return 底.rstrip("/") + "/" + str(相对路径).lstrip("/")
    return ""


def buildCreate(请求: dict) -> dict:
    """纯函数：拼方舟的请求体。不联网、不看 key（没 key 也照样能拼出来看）。"""
    能 = 请求.get("能力")
    模 = 挑模型(请求)
    提示词 = 请求.get("提示词") or ""

    if 能 in ("文生图", "图生图"):
        体: dict = {
            "model": 模,
            "prompt": 提示词,
            "response_format": 请求.get("返回形式") or "url",   # url | b64_json
            "watermark": bool(请求.get("水印", False)),
        }
        if 请求.get("尺寸"):
            体["size"] = 请求["尺寸"]
        if 请求.get("张数"):
            体["sequential_image_generation"] = "auto"
        if 能 == "图生图":
            图 = _联网图(请求.get("参考图path") or 请求.get("首帧path") or "")
            体["image"] = [图] if 图 else []
            if not 图:
                体["_警告"] = (
                    "参考图path 只能给项目内相对路径，而方舟只收 URL —— 没有配 "
                    "影匠_素材公网前缀，所以这里发出去的是空数组，方舟会当纯文生图。"
                )
        return {"端点": "/images/generations", "方法": "POST", "体": 体,
                "_说明": f"同步能力；模型 {模}"}

    if 能 == "图生视频":
        文 = 提示词
        if 请求.get("时长秒"):
            文 += f" --dur {int(请求['时长秒'])}"
        if 请求.get("分辨率"):
            文 += f" --rs {请求['分辨率']}"
        分 = []
        for 键 in ("首帧path", "尾帧path"):
            路 = 请求.get(键)
            if 路:
                分.append({"type": "image_url", "image_url": {"url": _联网图(路)},
                           "role": "first_frame" if 键 == "首帧path" else "last_frame"})
        # 方舟的 content 数组：文字必须在最前面
        体 = {"model": 模, "content": [{"type": "text", "text": 文}] + 分}
        return {"端点": "/contents/generations/tasks", "方法": "POST", "体": 体,
                "_说明": f"异步能力；模型 {模}；图 {len(分)} 张"}

    raise ValueError(f"火山方舟 拼不出「{能}」的请求体")


# ───────────────────────────── parseCreate ─────────────────────────────


def parseCreate(响应):
    """异步能力：认任务号。同步能力：交回产物标识（非空=完成）。

    认不出来就交回 "" / []，**不抛** —— 抛异常会把「回包看不懂」和「请求发失败」
    混成一件事，而这两件事该有完全不同的后续动作。
    """
    if not isinstance(响应, dict):
        return ""
    if 响应.get("error"):
        return ""
    # 异步：{"id": "cgt-..."}
    号 = 响应.get("id") or 响应.get("task_id") or 响应.get("taskId")
    if 号:
        return str(号)
    # 同步：{"data": [{"url": ...} 或 {"b64_json": ...}]}
    数 = 响应.get("data")
    if isinstance(数, list):
        出 = []
        for 项 in 数:
            if isinstance(项, dict):
                u = 项.get("url") or 项.get("b64_json") or 项.get("image_url")
                if u:
                    出.append(u)
        return 出
    return ""


def 解析错误(响应, 上限: int = 400) -> str:
    if not isinstance(响应, dict):
        return 契约.解析错误默认(响应, 上限)
    e = 响应.get("error")
    if isinstance(e, dict):
        片 = [f"方舟错误 code={e.get('code') or '?'}：{e.get('message') or ''}"]
        if e.get("param"):
            片.append(f"出错参数 {e['param']}")
        return "；".join(片)[:上限]
    if e:
        return str(e)[:上限]
    return 契约.解析错误默认(响应, 上限)


# ───────────────────────────── parseResult ─────────────────────────────


def parseResult(轮询响应, 任务id: str | None = None) -> dict:
    """纯函数：把方舟的轮询回包翻成五态。

    这里有一条云端特有的判断：
      · 拿到了 video_url  → 完成
      · 状态说失败        → 失败
      · 说还在跑          → 排队/运行
      · 说 expired / not_found / 超时 → **未知**
        理由：任务真跑过，视频可能真生成了、真扣钱了，只是链接过期取不到。
        判失败 = 上层重跑 = 再扣一次钱。判未知 = 去控制台查一眼。
    """
    成本 = {"金额": None, "币种": "CNY", "计费": "按方舟账单",
            "说明": "未验证：没有真实用量回包，没敢填数字"}

    def cost_of(原始):
        c = dict(成本)
        if isinstance(原始, dict):
            u = 原始.get("usage")
            if isinstance(u, dict):
                c["用量"] = u
                c["金额"] = u.get("total_price") or u.get("price") or None
        return c

    if not isinstance(轮询响应, dict):
        return {"状态": 契约.未知, "产物": [], "成本": 成本,
                "错误": f"轮询响应必须是 dict，收到 {type(轮询响应).__name__}"}

    原 = 轮询响应
    # 容错：驱动器可能把整个 {"task": {...}} 或者 {任务id: {...}} 递进来
    条 = 原
    if isinstance(原.get("task"), dict):
        条 = 原["task"]
    elif 任务id and isinstance(原.get(任务id), dict):
        条 = 原[任务id]
    elif isinstance(原.get("data"), dict) and ("status" in 原["data"]):
        条 = 原["data"]

    状 = 条.get("status") or 条.get("state")

    # 先看结果：有产物就是完成，不管 status 字段写没写（各家写法不一致）
    产 = _收产物(条)
    if 产:
        return {"状态": 契约.完成, "产物": 产, "错误": "", "成本": cost_of(条)}

    if 状 is None:
        return {"状态": 契约.未知, "产物": [], "成本": cost_of(条),
                "错误": "回包里既没有 status 也没有产物 —— 认不出这个任务怎么了"}

    翻 = 契约.归一(状, 状态表)
    if 翻 == 契约.失败:
        return {"状态": 契约.失败, "产物": [], "成本": cost_of(条),
                "错误": 解析错误(条) or f"方舟说失败了（status={状}）"}
    if 翻 == 契约.未知:
        return {"状态": 契约.未知, "产物": [], "成本": cost_of(条),
                "错误": (f"方舟说 status={状} —— 这个任务**可能已经生成并扣过费**了，"
                         f"别急着重跑，先去控制台/用量页查一眼。原始回包："
                         f"{契约.解析错误默认(条, 200)}")}
    if 翻 == 契约.完成:
        # status 说完成，但没解析出产物 —— 这是「完成了个寂寞」，判未知而不是失败
        return {"状态": 契约.未知, "产物": [], "成本": cost_of(条),
                "错误": (f"status={状} 说完成了，但回包里找不到 video_url / data —— "
                         f"活**多半已经干完、钱也扣了**，只是这条回包的字段名跟文档不一样。"
                         f"别急着重跑（重跑 = 再扣一次），先去控制台/用量页按任务id 查一眼。"
                         f"原始回包：{契约.解析错误默认(条, 200)}")}
    return {"状态": 翻, "产物": [], "错误": "", "成本": cost_of(条)}


def _收产物(条: dict) -> list[dict]:
    出 = []

    def 加(类型, 址, 备注=""):
        if not 址:
            return
        项 = {"类型": 类型, "路径": 址}
        if 备注:
            项["备注"] = 备注
        # 临时签名 URL：过期是必然的，提醒上层尽早下载
        if isinstance(址, str) and 址.startswith("http"):
            项["临时链接"] = True
            项["提示"] = "方舟的 URL 带签名参数，会过期 —— 拿到就尽早下载落盘"
        出.append(项)

    c = 条.get("content")
    if isinstance(c, dict):
        加("视频", c.get("video_url"))
        加("图", c.get("image_url"))
        加("音频", c.get("audio_url"))
    elif isinstance(c, list):
        for 项 in c:
            if isinstance(项, dict):
                加("视频" if 项.get("video_url") else "图",
                  项.get("video_url") or 项.get("image_url") or 项.get("url"))

    数 = 条.get("data")
    if isinstance(数, list):
        for 项 in 数:
            if isinstance(项, dict):
                址 = 项.get("url") or 项.get("image_url")
                if 址:
                    加(_看图还是视频(址), 址)
                elif 项.get("b64_json"):
                    出.append({"类型": "图", "路径": "（内联 base64，没落盘）",
                               "b64长度": len(str(项["b64_json"]))})
    for 键, 类型 in (("video_url", "视频"), ("image_url", "图")):
        加(类型, 条.get(键))
    return 出


def _看图还是视频(址: str) -> str:
    低 = str(址).lower().split("?")[0]
    for 尾 in (".mp4", ".mov", ".webm", ".mkv"):
        if 低.endswith(尾):
            return "视频"
    return "图"


# ───────────────────────────── 轮询 / 取回 ─────────────────────────────


def 轮询端点(任务id: str) -> list[dict]:
    return [{"端点": f"/contents/generations/tasks/{任务id}", "方法": "GET", "标签": "task"}]


def 取回(产物: dict, 存到: str | None = None) -> str:
    """下载云端的临时链接。**这里要做网络请求** —— 所以它不在纯函数里。

    没网/链接过期都会抛：链接过期抛的是「未知」那一类（东西生成过），
    消息里会写清楚，别把它当失败重跑。
    """
    import urllib.request

    址 = 产物.get("路径")
    if not isinstance(址, str) or not 址.startswith("http"):
        raise ValueError(
            f"这个产物没有可下载的 URL（{址!r}）。"
            "如果是 b64_json，请改 返回形式='url' 或另写解码逻辑（本骨架没做）"
        )
    到 = 存到 or os.path.join(这里, "..", "作品", "云端", os.path.basename(址.split("?")[0]))
    到 = os.path.abspath(到)
    os.makedirs(os.path.dirname(到), exist_ok=True)
    try:
        with urllib.request.urlopen(址, timeout=120) as r:
            数据 = r.read()
    except Exception as e:
        raise RuntimeError(
            f"下载失败：{e!r}。注意：如果这是签名链接过期，**任务本身是成功的**，"
            f"别重跑 —— 回方舟控制台看这条任务，或用 任务id 重新取一次链接。"
        ) from e
    with open(到, "wb") as f:
        f.write(数据)
    return 到


if __name__ == "__main__":
    import json as _json

    print("适配器：", 元数据()["名称"])
    print("凭证：", 凭证检查()["提示"].splitlines()[0])
    print("基址：", 基址())
    print()
    for 能, 请 in (
        ("文生图", {"能力": "文生图", "提示词": "水墨风格的江南小镇，清晨薄雾"}),
        ("图生视频", {"能力": "图生视频", "提示词": "镜头缓慢推近",
                      "首帧path": "/作品/试镜/首帧.png", "时长秒": 5, "分辨率": "720p"}),
    ):
        体 = buildCreate(请)
        print(f"{能} → {体['端点']}")
        print("   体：", _json.dumps(体["体"], ensure_ascii=False)[:200], "…")
        print("   校验：", 校验(请) or "（没问题）")
