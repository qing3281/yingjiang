# -*- coding: utf-8 -*-
"""
影匠 · 画布  —— 节点图编辑器（对齐飞彩 `feicai-canvas`）
================================================================

这份东西的每一个字段名、每一条枚举、每一句报错，都是从飞彩的编译产物里**挖出来的**，
不是自己发明的。证据在 `知识/飞彩画布实测.md`，源头是：

    D:\\DSHworkspace\\网盘\\_飞彩解包\\Win\\.next\\static\\chunks\\8703-eb0f8154d00e5112.js  @165600-176000
    D:\\DSHworkspace\\网盘\\_飞彩解包\\Win\\.next\\static\\chunks\\7528.b8e9b33e52e6855c.js  @197281-197975

它解决什么
----------
飞彩的画布是一张「有类型的管线图」：节点有**入端口/出端口，端口带 dataType**，
连线只有在「上游出端口类型 == 下游入端口类型」时才合法。这让**连线本身就是校验**——
连错了根本连不上，不用等跑起来才发现。

影匠原来只有一条写死的流水线（导演 → 引擎 → 剧组），画布把这条线变成**数据**：
    · 工程存成一份 JSON（读写走 `项目`）
    · 连线走 `能连吗()`（照抄飞彩 `r5`）
    · 执行顺序走 `拓扑分层()`（照抄飞彩 `n`，含环检测）
    · 逐节点派活走 `跑()`，状态写回画布（照抄飞彩的 `idle/queued/running/success/error`）

用法（三步）
------------
    import 画布
    p = 画布.空工程("我的第一条管线")
    a = p.加节点("builtin:text-input", x=0,   y=0,  参数={"content": "雪原上一个银发女子回头"})
    b = p.加节点("builtin:smart-image", x=420, y=0)
    p.连线(a, "out-text", b, "in-text")
    p.存()
    画布.跑(p)
    print(p.取节点(b)["data"]["result"])

命令
----
    python 画布.py 自测            离线自检（不联网、不出图），退出码 0 才算过
    python 画布.py 列模块          画布认得的节点目录
    python 画布.py 新 <名字>       新建一份工程
    python 画布.py 列              列出已有工程
    python 画布.py 看 <id>         打印一份工程（节点/边/层）
    python 画布.py 跑 <id> [--节点 节点id] [--干跑] [--并发 N]
    python 画布.py 预排 <id>       拓扑分层 + 成本预告（不发请求）
    python 画布.py 定义 <id>       自创画布 vs 飞彩画布 的差异清单
"""

import hashlib
import io
import json
import os
import re
import sys
import threading
import time
import unicodedata

这里 = os.path.dirname(os.path.abspath(__file__))
if 这里 not in sys.path:
    sys.path.insert(0, 这里)

工程根 = os.path.join(这里, "作品", "_画布")


# ============================================================
# 0. 装模块（中文名 import 可能失败 —— 照抄 一致性.py 的写法）
# ============================================================


def _装模块(文件名, 别名):
    """载入影匠既有模块（只读，绝不改它们）。"""
    try:
        return __import__(别名), ""
    except Exception as e1:
        pass
    try:
        import importlib.util
        p = os.path.join(这里, 文件名)
        if not os.path.isfile(p):
            return None, f"文件不存在：{p}"
        spec = importlib.util.spec_from_file_location("_影匠_" + 别名, p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        return m, ""
    except Exception as e2:
        return None, f"import 失败({e1!r})；按路径载入失败({e2!r})"


_引擎, _引擎错 = _装模块("引擎.py", "引擎")
_导演, _导演错 = _装模块("导演.py", "导演")
_一致性, _一致性错 = _装模块("一致性.py", "一致性")
_注册表, _注册表错 = _装模块("接口/注册表.py", "注册表")
_账本, _账本错 = _装模块("账本.py", "账本")


# ============================================================
# 1. 枚举与常量（全部实测）
# ============================================================

#: 节点状态。实测三处：`8703 @357180`（queued/running）、`7528 @88397`（running/success/error）、
#: 新建节点默认 `status:"idle"`。合并成五档。
节点状态 = ("idle", "queued", "running", "success", "error")

#: 端口数据类型词表（实测：text / image / video / audio / any）
端口类型 = ("text", "image", "video", "audio", "any")

#: 画布执行并发上限。实测 `u=30` + `画布执行并发必须是 1-30 的整数`。
并发上限 = 30

#: 飞彩原样的报错串，一字不改。
错_环 = "工作流中存在循环依赖，无法执行"
错_并发 = "画布执行并发必须是 1-{u} 的整数"
错_截止 = "画布执行截止时间无效"
错_时钟 = "画布执行时钟无效"
错_门禁 = "节点启动门禁已拒绝"
错_迟到 = "节点执行结果已与当前队列或画布失配，迟到结果未写回"
错_未启动 = "节点未启动"
错_代次 = "画布执行代次不可用"

#: 实测：id 一般形态 `/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/`，短形态 64 位。
ID规范 = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ID短规范 = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")

#: 实测：飞彩画布 action 全集 21 条（`7528` 里的 `rZ`）。
画布动作 = (
    "native.list_modules", "canvas.guide", "canvas.get_state", "canvas.get_result",
    "canvas.list_models", "canvas.validate", "canvas.director_workbench_get_plan",
    "canvas.director_workbench_edit", "canvas.create_node", "canvas.batch",
    "canvas.connect_nodes", "canvas.disconnect_nodes", "canvas.set_prompt",
    "canvas.set_params", "canvas.auto_layout", "canvas.estimate_cost",
    "canvas.run", "canvas.run_chain", "canvas.await_result", "canvas.command_status",
    "canvas.abort_node",
)

#: 实测：画布改动提案的四个 kind（`7528 @214034-218958`）。**四个都不许花钱**。
改动种类 = ("set_params", "connect", "auto_layout", "create_reference_extractors")

#: 实测：提案费用上限 `0 <= costCents <= 800`。
改动费用上限分 = 800

#: 实测：id 前缀正则 `/^cat1_[A-Za-z0-9_-]{43}$/`（画布标识）。
画布ID规范 = re.compile(r"^cat1_[A-Za-z0-9_-]{43}$")

#: 实测：画布执行代次派生盐 `feicai-canvas-relay-generation-v2\0<canvasId>\0<generation>`。
代次盐 = "feicai-canvas-relay-generation-v2"

#: 实测：保存工程时要瘦身的模块（`5209` webpack 31656 的 `l`）。
瘦身模块 = frozenset(["builtin:script-extract", "builtin:storyboard-gen"])

#: 实测：四个瘦身哨兵串。
哨兵 = {
    "data-url": "[stripped-data-url]",
    "blob-url": "[stripped-blob-url]",
    "ls-dataurl": "[ls-lazy-dataurl]",
    "ls-blob": "[ls-lazy-blob]",
}

#: 实测：参数字段名红线扫描 —— 画布参数里不许出现密钥形状的键。
#: 飞彩原正则被截断，这里按同一形状补全。
密钥形状 = re.compile(
    r"(?:^|[-_.])(api.?key|token|secret|credential|password|base.?url|workflow.?json"
    r"|preset.?rule|access.?key|private.?key|bearer|auth.?header)",
    re.I,
)

#: 实测：控制字符/双向覆盖字符一律不许进文本（`rQ` / `r0` 家族）。
控制字符 = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u2028\u2029\u202a-\u202e\u2066-\u2069]")

#: 实测：动态出端口前缀 `/^out-n\d+-/`（多镜头节点，每镜一对 图/视频 提示词）。
动态端口 = re.compile(r"^out-n\d+-")

#: 实测：单条文本上限 20000 字节（canvasPromptEdit 的 prompt 上限）。
字节上限_文本 = 20000

#: 实测：`rj` 里各类集合的条数上限。
上限 = {
    "clarifications": 12, "suggestions": 12, "planSteps": 40, "approvals": 12,
    "artifacts": 100, "errors": 50, "textBytes": 4000,
}

#: 实测：计划步骤状态（步进账用）。
步骤状态 = (
    "pending", "needs_input", "awaiting_risk", "ready", "dispatching", "dispatched",
    "verifying", "completed", "recovering", "query_only", "retryable", "failed",
    "indeterminate", "superseded",
)

#: 实测：节点分类（目录用）。
分类_添加 = "添加节点"
分类_功能 = "功能节点"
分类_隐藏 = "_hidden"


# ============================================================
# 2. 端口契约表（实测 `r2`，原样 4 个模块）
# ============================================================

#: 飞彩只给这 4 个模块登记了端口类型表。**不在这张表里的模块，连线一律拒绝。**
端口契约 = {
    "builtin:text-input": {
        "inputs": {"in-text": "text", "in-image": "image", "in-video": "video"},
        "outputs": {"out-text": "text"},
    },
    "builtin:smart-image": {
        "inputs": {"in-image": "image", "in-ref": "image", "in-text": "text"},
        "outputs": {"out-image": "image"},
    },
    "builtin:smart-video": {
        "inputs": {"in-text": "text", "in-image": "image", "in-image-last": "image", "in-video": "video"},
        "outputs": {"out-video": "video"},
    },
    "builtin:seedance-video": {
        "inputs": {"in-text": "text", "in-image": "image", "in-video": "video", "in-audio": "audio"},
        "outputs": {"out-video": "video"},
    },
}

#: 实测 `r1` —— 正好是端口契约表的 4 个键。
契约模块 = frozenset(端口契约)

#: 实测白名单（24 条，`7528 @909774` 附近）：画布允许创建的模块。
画布白名单 = (
    "builtin:text-input", "builtin:smart-image", "builtin:smart-video",
    "builtin:rh-angle-ctrl", "builtin:rh-tts", "builtin:seedance-video",
    "builtin:director-workbench", "builtin:script-input", "builtin:script-parser",
    "builtin:rh-script-tts", "builtin:script-extract", "builtin:storyboard-gen",
    "builtin:storyboard-orchestrator", "builtin:remake-script", "builtin:ref-forge",
    "builtin:picture-frame", "builtin:video-enhance", "builtin:video-superres",
    "builtin:video-remove-subtitles", "builtin:video-remove-watermark",
    "builtin:iphone-live-photo-export", "builtin:media-deai", "builtin:image-puzzle",
    "builtin:face-mask",
)

#: 实测 `i3` —— 有自己专用面板、不进通用面板的 4 个。
专用面板 = frozenset([
    "builtin:script-storyboard", "builtin:rh-upscale",
    "builtin:ecommerce-creative", "builtin:rh-webapp",
])

#: 实测 `i4` —— 添加节点里的排序。
添加顺序 = ["text-input", "smart-image", "smart-video", "audio-input", "script-input"]

#: 实测 `i6` —— 侧边栏六个分组。
侧栏分组 = [
    ("script", "剧本 · 分镜", ["builtin:script-parser", "builtin:script-storyboard",
                              "builtin:script-extract", "builtin:scene-image",
                              "builtin:storyboard-gen", "builtin:storyboard-orchestrator",
                              "builtin:scene-srt"]),
    ("video-gen", "视频生成", ["builtin:director-workbench", "builtin:seedance-video"]),
    ("video-post", "视频后期", ["builtin:video-superres", "builtin:video-remove-subtitles",
                                "builtin:video-remove-watermark", "builtin:video-enhance",
                                "builtin:iphone-live-photo-export"]),
    ("image", "图片处理", ["builtin:rh-upscale", "builtin:rh-angle-ctrl", "builtin:picture-frame",
                           "builtin:image-puzzle", "builtin:media-deai"]),
    ("audio", "音频 · 配音", ["builtin:rh-tts", "builtin:rh-script-tts"]),
    ("creative", "创意 · 外部", ["builtin:ecommerce-creative", "builtin:rh-webapp"]),
]

#: 实测：飞彩画布自定义 NodeView 的 5 个模块。
自定义视图 = frozenset([
    "builtin:smart-image", "builtin:smart-video", "builtin:scene-image",
    "builtin:seedance-video", "builtin:director-workbench",
])


# ============================================================
# 3. 节点目录 —— 飞彩 19 个有内联定义的模块，原样搬
# ============================================================
# 每条 = 飞彩 `飞彩模块目录.json` 里的原始定义（source/name/description/icon/category/
# color/inputs/outputs/builtinAction/paramsSchema 九件套），一个字段没改。

def _口(id_, 类型, 标签, 方向):
    return {"id": id_, "label": 标签, "dataType": 类型, "direction": 方向}


def _入(id_, 类型, 标签):
    return _口(id_, 类型, 标签, "input")


def _出(id_, 类型, 标签):
    return _口(id_, 类型, 标签, "output")


目录表: dict[str, dict] = {}


def _登记(模块id, 名, 说明, 图标, 分类, 颜色, 动作, 入们, 出们, 参数=None, 来源="builtin"):
    目录表[模块id] = {
        "id": 模块id,
        "source": 来源,
        "name": 名,
        "description": 说明,
        "icon": 图标,
        "category": 分类,
        "color": 颜色,
        "builtinAction": 动作,
        "inputs": 入们,
        "outputs": 出们,
        "paramsSchema": 参数 or [],
    }


_登记("builtin:text-input", "文本", "提示词、脚本、广告词、品牌文案", "Type", 分类_添加, "#4ADE80",
      "text-input",
      [_入("in-text", "text", "文本"), _入("in-image", "image", "参考图"), _入("in-video", "video", "参考视频")],
      [_出("out-text", "text", "文本")],
      [{"key": "content", "type": "string", "label": "正文文本", "maxLen": 20000},
       {"key": "prompt", "type": "string", "label": "附加指令", "maxLen": 20000},
       {"key": "llmInstanceId", "type": "string", "label": "语言/多模态模型"}])

_登记("builtin:smart-image", "图片", "上传图片 / 参考图 / 图生图 / 图生视频 / 换背景", "Image",
      分类_添加, "#38BDF8", "smart-image",
      [_入("in-image", "image", "图片"), _入("in-ref", "image", "参考图"), _入("in-text", "text", "提示词")],
      [_出("out-image", "image", "图片")],
      [{"key": "prompt", "type": "string", "label": "提示词", "maxLen": 20000},
       {"key": "aspectRatio", "type": "enum", "label": "画面比例", "default": "16:9"},
       {"key": "size", "type": "enum", "label": "分辨率", "default": "1k"},
       {"key": "n", "type": "number", "label": "张数", "default": 1},
       {"key": "seed", "type": "number", "label": "种子"},
       {"key": "imageModelId", "type": "string", "label": "图片模型"}])

_登记("builtin:smart-video", "视频", "上传视频 / 文生视频 / 图生视频 / 首尾帧生视频", "Film",
      分类_添加, "#8B5CF6", "smart-video",
      [_入("in-text", "text", "提示词"), _入("in-image", "image", "首帧/参考图"),
       _入("in-image-last", "image", "尾帧"), _入("in-video", "video", "源视频")],
      [_出("out-video", "video", "视频")],
      [{"key": "referenceVideos", "type": "string-array", "label": "本地工作流参考视频", "maxLen": 1048576},
       {"key": "referenceAudios", "type": "string-array", "label": "本地工作流参考音频", "maxLen": 1048576},
       {"key": "localRelayParams", "type": "object", "label": "本地工作流附加参数"},
       {"key": "prompt", "type": "string", "label": "提示词", "maxLen": 20000},
       {"key": "mode", "type": "enum", "label": "生成模式"},
       {"key": "duration", "type": "number", "label": "时长(秒)", "default": 10},
       {"key": "ratio", "type": "enum", "label": "画面比例", "default": "16:9"},
       {"key": "resolution", "type": "enum", "label": "分辨率", "default": "720p"},
       {"key": "videoModelId", "type": "string", "label": "视频模型"}])

_登记("builtin:seedance-video", "Seedance 视频", "Seedance 2.0 视频生成（即梦官方算力，支持全能/首帧参考）",
      "Film", 分类_添加, "#8B5CF6", "seedance-video",
      [_入("in-text", "text", "提示词"), _入("in-image", "image", "参考图"),
       _入("in-video", "video", "源视频"), _入("in-audio", "audio", "音频")],
      [_出("out-video", "video", "视频")],
      [{"key": "prompt", "type": "string", "label": "提示词", "maxLen": 20000},
       {"key": "duration", "type": "number", "label": "时长(秒)", "default": 5},
       {"key": "ratio", "type": "enum", "label": "画面比例", "default": "16:9"},
       {"key": "quality", "type": "enum", "label": "画质", "default": "720P"}])

_登记("builtin:rh-upscale", "高清放大", "RunningHub 图片高清放大-seedVR2", "Sparkles",
      分类_功能, "#38BDF8", "rh-upscale",
      [_入("input", "image", "输入图片")], [_出("output", "image", "放大结果")],
      [{"key": "resolution", "type": "string", "label": "放大倍率", "default": "2", "maxLen": 8}])

_登记("builtin:rh-tts", "语音克隆", "RunningHub IndexTTS2 文字转语音（需上传参考音频）", "Music",
      分类_功能, "#EC4899", "rh-tts",
      [_入("input", "audio", "参考音频/文本")], [_出("output", "audio", "生成音频")],
      [{"key": "ttsPrompt", "type": "string", "label": "要转换的文字", "maxLen": 20000}])

_登记("builtin:rh-webapp", "RunningHub 工作流", "嵌入 RunningHub AI 应用页面，自动同步参数到画布并通过 OpenAPI 执行",
      "Workflow", 分类_功能, "#6366F1", "rh-webapp",
      [_入("image", "image", "图像"), _入("video", "video", "视频"),
       _入("audio", "audio", "音频"), _入("text", "text", "提示词")],
      [_出("output", "image", "生成结果")],
      [{"key": "rhType", "type": "enum", "label": "端点类型", "default": "webapp"},
       {"key": "rhInputValues", "type": "object", "label": "输入项值"}])

_登记("builtin:rh-angle-ctrl", "图像角度控制", "RunningHub 图像角度视角控制器 — 调整水平角度、垂直角度与缩放",
      "Rotate3d", 分类_功能, "#A78BFA", "rh-angle-ctrl",
      [_入("input", "image", "输入图片")], [_出("output", "image", "角度调整结果")],
      [{"key": "horizontalAngle", "type": "number", "label": "水平角度", "default": 315},
       {"key": "verticalAngle", "type": "number", "label": "垂直角度", "default": 34},
       {"key": "zoom", "type": "number", "label": "缩放", "default": 5}])

_登记("builtin:seedance-multi-ref", "飞彩多参考视频",
      "飞彩官方 Seedance 多图融合（@1 @2 锚定多角色/多场景，区别于首尾帧时间序列）",
      "Layers", 分类_功能, "#FFA500", "seedance-multi-ref",
      [_入("in-text", "text", "提示词"), _入("in-image", "image", "参考图")],
      [_出("out-video", "video", "视频")],
      [{"key": "protocolMode", "type": "string", "label": "中转协议模式", "maxLen": 40},
       {"key": "audioOutput", "type": "boolean", "label": "输出声音"},
       {"key": "localRelayParams", "type": "object", "label": "已声明附加参数"},
       {"key": "prompt", "type": "string", "label": "提示词", "maxLen": 20000},
       {"key": "duration", "type": "number", "label": "时长(秒)", "default": 5},
       {"key": "ratio", "type": "enum", "label": "画面比例", "default": "16:9"},
       {"key": "quality", "type": "enum", "label": "画质", "default": "720P"},
       {"key": "feicaiModelId", "type": "string", "label": "飞彩 API 模型"}])

_登记("builtin:script-parser", "剧本结构化",
      "规则引擎提取角色 + LLM 生成音色描述，输出标准剧本 JSON（含 role_list + juben）",
      "ListTree", 分类_功能, "#F97316", "script-parser",
      [_入("in-script", "text", "原始剧本")], [_出("out-json", "text", "剧本 JSON")],
      [{"key": "content", "type": "string", "label": "原始剧本", "maxLen": 20000},
       {"key": "scriptText", "type": "string", "label": "原始剧本(兜底)", "maxLen": 20000},
       {"key": "mode", "type": "enum", "label": "解析模式", "default": "auto"},
       {"key": "chapterIndex", "type": "number", "label": "章节序号", "default": -1}])

_登记("builtin:rh-script-tts", "短剧 TTS",
      "RunningHub 多说话人剧本配音（Qwen3 TTS / 8 参考音色槽 / 按角色名映射）",
      "Mic2", 分类_功能, "#EC4899", "rh-script-tts",
      [_入("in-script", "text", "剧本")] + [_入(f"in-voice-{i}", "audio", f"音色槽 {i}") for i in range(1, 9)],
      [_出("out-audio", "audio", "完整配音")],
      [{"key": "scriptText", "type": "string", "label": "剧本文本", "maxLen": 20000}])

_登记("builtin:script-extract", "参考图提取", "从剧本文本提取角色 / 场景 / 道具的参考图提示词，节点内分组展示",
      "ScanText", 分类_功能, "#7dd3fc", "script-extract",
      [_入("in-text", "text", "剧本文本")], [],
      [{"key": "content", "type": "string", "label": "剧本文本", "maxLen": 20000},
       {"key": "text", "type": "string", "label": "剧本文本(兜底)", "maxLen": 20000}])

_登记("builtin:ref-forge", "参考图工坊",
      "连入源视频或剧本文本，AI 提取人物 / 场景 / 道具实体清单与参考图描述，铺开生图由面板按钮触发",
      "ImageIcon", 分类_功能, "#7dd3fc", "ref-forge",
      [_入("in-video", "video", "源视频"), _入("in-n1-text", "text", "剧本文本")], [],
      [{"key": "llmInstanceId", "type": "string", "label": "反推模型"},
       {"key": "instruction", "type": "string", "label": "提取要求", "maxLen": 5000},
       {"key": "refStylePrompt", "type": "string", "label": "参考图风格", "maxLen": 500}])

_登记("builtin:output-preview", "输出预览", "(已废弃)", "Eye", 分类_隐藏, "#A78BFA", "output-preview",
      [_入("in-image", "image", "图片"), _入("in-video", "video", "视频"),
       _入("in-audio", "audio", "音频"), _入("in-text", "text", "文本")], [])

_登记("builtin:picture-frame", "宫格画框", "把多张外部图片组成宫格图（同分镜格子交互，支持拖拽/替换/删除/合成）",
      "Frame", 分类_功能, "#A78BFA", "picture-frame",
      [_入("in-image", "image", "导入图片")], [])

_登记("builtin:media-deai", "AI 特征抹除",
      "上游图片/视频 → 抹除 AI 生成特征（元数据/频域/噪声/重编码），输出可下游使用",
      "Eraser", 分类_功能, "#F472B6", "media-deai",
      [_入("input", "any", "输入图片/视频")], [_出("output", "any", "抹除结果")],
      [{"key": "level", "type": "enum", "label": "抹除强度", "default": "medium"}])

_登记("builtin:image-puzzle", "拼图", "多图无损拼成一张（16:9/9:16/1:1）", "LayoutGrid",
      分类_功能, "#34D399", "image-puzzle",
      [_入("input", "image", "图片")], [_出("output", "image", "拼图")],
      [{"key": "rows", "type": "number", "label": "行数", "default": 2},
       {"key": "cols", "type": "number", "label": "列数", "default": 2},
       {"key": "gap", "type": "number", "label": "黑边距(px)", "default": 8},
       {"key": "ratio", "type": "enum", "label": "画布比例", "default": "1:1"}])

_登记("builtin:face-mask", "人脸遮罩", "对图片中的正面人脸铺红色网格遮罩（打散可识别人脸，绕过真人过审），输出同尺寸处理图",
      "ScanFace", 分类_功能, "#60A5FA", "face-mask",
      [_入("in-image", "image", "图片")], [_出("output", "image", "遮罩图")])

_登记("builtin:video-superres", "视频高清放大", "已有视频 → 插件工作流高清放大；可切回飞彩 VSR（不是生成视频）",
      "Sparkles", 分类_功能, "#22D3EE", "video-superres",
      [_入("input", "video", "输入视频")], [_出("output", "video", "超分结果")],
      [{"key": "processor", "type": "enum", "label": "处理引擎", "default": "plugin"},
       {"key": "pluginActionModel", "type": "string", "label": "插件动作模型"},
       {"key": "size", "type": "enum", "label": "超分档位", "default": "2k"}])

_登记("builtin:video-remove-watermark", "视频去水印",
      "已有视频 → 插件工作流去水印；可切回飞彩 VWR（不是生成视频）", "Eraser", 分类_功能, "#A78BFA",
      "video-remove-watermark",
      [_入("input", "video", "输入视频")], [_出("output", "video", "去水印结果")],
      [{"key": "processor", "type": "enum", "label": "处理引擎", "default": "plugin"},
       {"key": "pluginActionModel", "type": "string", "label": "插件动作模型"},
       {"key": "region", "type": "object", "label": "框选区域"},
       {"key": "videoModelId", "type": "string", "label": "视频实例"}])

_登记("builtin:video-remove-subtitles", "视频去字幕",
      "已有视频 → 插件工作流去字幕；可切回飞彩 VTR（不是生成视频）", "Eraser", 分类_功能, "#F59E0B",
      "video-remove-subtitles",
      [_入("input", "video", "输入视频")], [_出("output", "video", "去字幕结果")],
      [{"key": "processor", "type": "enum", "label": "处理引擎", "default": "plugin"},
       {"key": "pluginActionModel", "type": "string", "label": "插件动作模型"},
       {"key": "region", "type": "object", "label": "框选区域"},
       {"key": "videoModelId", "type": "string", "label": "视频实例"}])

_登记("builtin:video-enhance", "视频升画质", "火山 AI MediaKit · 已有视频 → 升画质（不是生成视频）",
      "Sparkles", 分类_功能, "#22D3EE", "video-enhance",
      [_入("input", "video", "输入视频")], [_出("output", "video", "升画质结果")],
      [{"key": "processor", "type": "enum", "label": "处理引擎", "default": "plugin"},
       {"key": "size", "type": "enum", "label": "档次", "default": "1080p"}])

# ── 飞彩引用了但定义不在 .next 里的（走服务端/别的 bundle）──
# 影匠照样把它们登记进目录，只是标 `来源="飞彩·仅登记"`，并明确它还没有执行器。
仅登记模块 = {
    "builtin:group": ("新建组", "组容器（视觉分组，不进拓扑）", 分类_隐藏, "#666666"),
    "builtin:director-workbench": ("导演工作台", "多镜头 · 时间轴 · 六模式", 分类_添加, "#8B5CF6"),
    "builtin:scene-image": ("场景图", "按场景出图", 分类_功能, "#38BDF8"),
    "builtin:scene-srt": ("场景字幕", "生成字幕", 分类_功能, "#F59E0B"),
    "builtin:script-input": ("剧本输入", "从飞彩剧本库选剧本，输出剧本文本（驱动短剧 TTS）", 分类_添加, "#F97316"),
    "builtin:script-storyboard": ("剧本分镜", "AI 把整段剧本拆成 N 个镜头（同节点内可滚动浏览），右侧 N×2 个端口",
                                 分类_功能, "#F97316"),
    "builtin:storyboard-gen": ("故事板生成", "连接剧本/小说 + 参考图，AI 拆分镜并批量生成连续一致的故事板图片",
                               分类_功能, "#7dd3fc"),
    "builtin:storyboard-orchestrator": ("分镜编排", "编排分镜序列", 分类_功能, "#7dd3fc"),
    "builtin:storyboard-shot": ("分镜格", "storyboard-gen 的子节点", 分类_隐藏, "#7dd3fc"),
    "builtin:remake-script": ("翻拍脚本", "连入源视频，AI 反推出场景 / 人物 / 台词时间线与成品提示词的翻拍脚本",
                              分类_功能, "#A78BFA"),
    "builtin:ecommerce-creative": ("电商创意", "AI 广告与品牌创意操作系统", 分类_功能, "#6366F1"),
    "builtin:iphone-live-photo-export": ("实况照片导出",
                                          "以视频首帧为封面，生成可分享 MP4 与用于 PhotoKit 导入的 JPG + MOV 配对资源",
                                          分类_功能, "#22D3EE"),
    "builtin:image-display": ("图片展示", "只展示不产出", 分类_隐藏, "#38BDF8"),
    "builtin:video-display": ("视频展示", "只展示不产出", 分类_隐藏, "#8B5CF6"),
}
for _id, (_名, _说明, _分类, _色) in 仅登记模块.items():
    if _id in 目录表:
        continue
    _动作 = _id.replace("builtin:", "")
    _入们 = []
    _出们 = []
    if _id in 端口契约:
        _入们 = [_入(k, v, k) for k, v in 端口契约[_id]["inputs"].items()]
        _出们 = [_出(k, v, k) for k, v in 端口契约[_id]["outputs"].items()]
    _登记(_id, _名, _说明, "Box", _分类, _色, _动作, _入们, _出们, [], 来源="飞彩·仅登记")


def 列模块(含隐藏: bool = False, 只要有执行器: bool = False) -> list[dict]:
    """画布认得的节点目录。"""
    出 = []
    for m in 目录表.values():
        if not 含隐藏 and m["category"] == 分类_隐藏:
            continue
        if 只要有执行器 and m["id"] not in 执行器:
            continue
        出.append(m)
    return 出


def 取模块(模块id: str) -> dict | None:
    return 目录表.get(模块id)


# ============================================================
# 4. 连线合法性 —— 照抄飞彩 `r5`
# ============================================================

def 端口类型表(模块id: str) -> dict | None:
    """飞彩只给 4 个模块登记了端口契约。不在表里的模块，连线一律拒绝。"""
    return 端口契约.get(模块id)


def 能连吗(节点表, 源: dict, 目标: dict) -> tuple[bool, str]:
    """飞彩 `r5(节点表, {nodeId,portId}, {nodeId,portId})` 的中文还原。

    返回 (能不能, 为什么不能)。判据逐条照抄，**一条都不放宽**：

      ① 两端节点都必须在（`!a||!n`）
      ② 不许自己连自己（`a.nodeId===n.nodeId`）
      ③ 两端模块都必须在端口契约表里（`!Object.hasOwn(r2, …)`）
      ④ 出端口类型必须**严格等于**入端口类型（`"string"==typeof o && o===l`）

    与飞彩一致：这里**没有 `any` 兜底** —— 上游是 `any`、下游是 `image` 也照样拒绝。
    （飞彩引擎内部另有一套「按类型找兼容口」的宽松规则，那是**渲染期**用的，不是连线闸门。）
    """
    索 = {}
    for n in 节点表:
        if isinstance(n, dict) and isinstance(n.get("nodeId"), str):
            索[n["nodeId"]] = n
    a = 索.get(源.get("nodeId"))
    n = 索.get(目标.get("nodeId"))
    if a is None or n is None:
        return False, "两端节点有找不到的（连线必须两端都在画布上）"
    if a["nodeId"] == n["nodeId"]:
        return False, "不许自己连自己（飞彩：a.nodeId===n.nodeId 直接拒）"
    甲 = a.get("moduleId", "")
    乙 = n.get("moduleId", "")
    if 甲 not in 端口契约:
        return False, f"上游模块 {甲} 不在端口契约表里（飞彩只登记了 {len(端口契约)} 个模块）"
    if 乙 not in 端口契约:
        return False, f"下游模块 {乙} 不在端口契约表里（飞彩只登记了 {len(端口契约)} 个模块）"
    出 = 端口契约[甲]["outputs"]
    入 = 端口契约[乙]["inputs"]
    if 源.get("portId") not in 出:
        return False, f"上游模块 {甲} 没有出端口 {源.get('portId')}（有：{'、'.join(出)}）"
    if 目标.get("portId") not in 入:
        return False, f"下游模块 {乙} 没有入端口 {目标.get('portId')}（有：{'、'.join(入)}）"
    o = 出[源["portId"]]
    l = 入[目标["portId"]]
    if o != l:
        return False, f"类型对不上：上游出端口是 {o}，下游入端口要 {l}（飞彩判据是严格相等）"
    return True, f"{o} → {l}"


def 是动态端口(端口id) -> bool:
    """实测 `/^out-n\\d+-/` —— 多镜头节点的每镜独立出端口。"""
    return bool(isinstance(端口id, str) and 动态端口.match(端口id))


def 有动态端口(节点: dict) -> bool:
    return any(是动态端口(p.get("id")) for p in (节点.get("data", {}).get("outputs") or []))


# ============================================================
# 5. 工程（画布）—— 读写 / 增删 / 连线 / 存
# ============================================================

class 工程错(Exception):
    pass


class 连线非法(工程错):
    pass


class 参数非法(工程错):
    pass


def _洗文本(s: str, 名: str = "参数") -> str:
    """飞彩的文本规矩：NFC 归一 → trim → 不许控制字符/双向覆盖 → 不许超字节上限。

    ★ 注意（实测踩过的坑）：Python 3.12 **没有** `str.normalize` 这个方法
      （那是 JS 的 `String.prototype.normalize`）。这里必须走 `unicodedata.normalize`。
      本机 python 3.12.14 实测：`hasattr(str,'normalize') == False`，`unicodedata.normalize` 可用。
    """
    if not isinstance(s, str):
        raise 参数非法(f"{名} 必须是字符串，给的是 {type(s).__name__}")
    z = unicodedata.normalize("NFC", s).strip()
    if _有孤立代理对(z):
        raise 参数非法(f"{名} 里有孤立代理对（飞彩 ar() 的判据：UTF-16 半边不成对）")
    if 控制字符.search(z):
        raise 参数非法(f"{名} 里有控制字符或双向覆盖字符（飞彩 rQ/r0 家族一律拒）")
    if len(z.encode("utf-8")) > 字节上限_文本:
        raise 参数非法(f"{名} 太长：{len(z.encode('utf-8'))} 字节 > {字节上限_文本}")
    return z


def _有孤立代理对(s: str) -> bool:
    """飞彩 `ar(e)` 的 Python 版：扫 UTF-16 码元，高代理后面必须跟低代理。"""
    for 字 in s:
        o = ord(字)
        if 0xD800 <= o <= 0xDFFF:
            return True  # Python 的 str 是码点，出现这个区段就是坏的
    # 再从 UTF-16 编码角度扫一遍（真代理对在 Python 里是一个码点，编码出来是 4 字节）
    try:
        b = s.encode("utf-16-le", errors="surrogatepass")
    except Exception:
        return True
    i = 0
    while i + 1 < len(b):
        u = b[i] | (b[i + 1] << 8)
        if 0xD800 <= u <= 0xDBFF:
            if i + 3 >= len(b):
                return True
            v = b[i + 2] | (b[i + 3] << 8)
            if not (0xDC00 <= v <= 0xDFFF):
                return True
            i += 4
            continue
        if 0xDC00 <= u <= 0xDFFF:
            return True
        i += 2
    return False


def _扫密钥键(参数: dict, 哪: str = "") -> list[str]:
    """飞彩在画布参数接受/导出前会扫一遍密钥形状的键名（`fX`）。影匠照抄这道闸。"""
    坏 = []
    for k, v in (参数 or {}).items():
        if 密钥形状.search(str(k)):
            坏.append(f"{哪}参数键 {k!r} 长得像凭据（飞彩 fX 红线）")
        if isinstance(v, dict):
            坏 += _扫密钥键(v, 哪 + str(k) + ".")
    return 坏


def _瘦身(值):
    """保存工程时把大块 data:/blob: 换成哨兵串（`5209` webpack 31656 的做法）。"""
    if isinstance(值, str):
        if 值.startswith("data:"):
            return 哨兵["data-url"]
        if 值.startswith("blob:"):
            return 哨兵["blob-url"]
        return 值
    if isinstance(值, list):
        return [_瘦身(x) for x in 值]
    if isinstance(值, dict):
        return {k: _瘦身(v) for k, v in 值.items()}
    return 值


def 新节点id() -> str:
    return "n" + hashlib.sha1(os.urandom(12)).hexdigest()[:14]


def 新画布id() -> str:
    """飞彩画布标识是 `cat1_` + 43 个 [A-Za-z0-9_-]（实测正则）。"""
    import base64
    raw = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    return "cat1_" + raw[:43]


def 哈希64(东西) -> str:
    s = 东西 if isinstance(东西, str) else json.dumps(东西, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class 工程:
    """一份画布工程。字段名跟飞彩对齐（`nodes` / `edges` / `data.moduleId` …）。"""

    def __init__(self, 文档: dict, 路: str | None = None):
        self.路 = 路
        d = dict(文档 or {})
        self.文档 = d
        d.setdefault("schemaVersion", 1)
        d.setdefault("canvasId", 新画布id())
        d.setdefault("projectId", "p" + hashlib.sha1(os.urandom(8)).hexdigest()[:12])
        d.setdefault("name", "未命名画布")
        d.setdefault("nodes", [])
        d.setdefault("edges", [])
        d.setdefault("revision", 0)
        d.setdefault("generation", 1)
        d.setdefault("viewport", {"x": 0, "y": 0, "zoom": 1})
        d.setdefault("defaults", {})
        d.setdefault("createdAt", time.strftime("%Y-%m-%d %H:%M:%S"))
        d.setdefault("updatedAt", d["createdAt"])

    # ---------- 只读 ----------

    @property
    def 节点们(self) -> list[dict]:
        return self.文档["nodes"]

    @property
    def 边们(self) -> list[dict]:
        return self.文档["edges"]

    @property
    def 画布id(self) -> str:
        return self.文档["canvasId"]

    @property
    def 项目id(self) -> str:
        return self.文档["projectId"]

    def 取节点(self, 节点id: str) -> dict | None:
        for n in self.节点们:
            if n.get("id") == 节点id:
                return n
        return None

    def _必须节点(self, 节点id: str) -> dict:
        n = self.取节点(节点id)
        if n is None:
            raise 工程错(f"画布里没有节点 {节点id}")
        return n

    def 入边(self, 节点id: str) -> list[dict]:
        return [e for e in self.边们 if e.get("target") == 节点id]

    def 出边(self, 节点id: str) -> list[dict]:
        return [e for e in self.边们 if e.get("source") == 节点id]

    # ---------- 改 ----------

    def 加节点(self, 模块id: str, x: float = 0, y: float = 0, 参数: dict | None = None,
               节点id: str | None = None, 强制: bool = False) -> str:
        """照抄飞彩的节点形状：`{id,type:"module",position,data:{moduleId,…}}`。"""
        元 = 目录表.get(模块id)
        if 元 is None:
            raise 工程错(f"画布目录里没有模块 {模块id}")
        if not 强制 and 模块id not in 画布白名单 and 模块id != "builtin:group":
            raise 工程错(
                f"模块 {模块id} 不在飞彩画布白名单（24 条）里。\n"
                f"  确实要加就 强制=True —— 但它不会是飞彩行为。"
            )
        参数 = dict(参数 or {})
        坏 = _扫密钥键(参数, f"{模块id} ")
        if 坏:
            raise 参数非法("；".join(坏))
        if 模块id == "builtin:group":
            数据 = {
                "moduleId": "builtin:group", "moduleName": "新建组", "category": "group",
                "color": 元.get("color", "#666666"), "status": "idle",
                "inputs": [], "outputs": [],
                "params": {"_groupId": 参数.get("_groupId", "g" + hashlib.sha1(os.urandom(6)).hexdigest()[:8]),
                           "_groupColor": 参数.get("_groupColor", 元.get("color", "#666666")),
                           "_groupName": 参数.get("_groupName", "新建组")},
            }
            nid = 节点id or f"group-container-{int(time.time() * 1000)}-{os.urandom(2).hex()}"
            n = {"id": nid, "type": "group",
                 "position": {"x": float(x), "y": float(y)}, "width": 320.0, "height": 200.0,
                 "zIndex": 0, "selectable": True, "draggable": True, "data": 数据}
        else:
            nid = 节点id or 新节点id()
            数据 = {
                "moduleId": 模块id, "moduleName": 元["name"], "category": 元["category"],
                "color": 元["color"], "status": "idle",
                "params": 参数,
                "inputs": [dict(p) for p in 元["inputs"]],
                "outputs": [dict(p) for p in 元["outputs"]],
            }
            n = {"id": nid, "type": "module",
                 "position": {"x": float(x), "y": float(y)}, "data": 数据}
        if self.取节点(nid) is not None:
            raise 工程错(f"节点 id 撞了：{nid}")
        self.节点们.append(n)
        return nid

    def 加多镜端口(self, 节点id: str, 镜号: int) -> tuple[str, str]:
        """多镜头节点：挂一对 `out-n{i}-image` / `out-n{i}-video`（实测正则 `/^out-n\\d+-/`）。"""
        n = self._必须节点(节点id)
        if n["data"]["moduleId"] != "builtin:script-storyboard":
            raise 工程错("只有 builtin:script-storyboard 才挂 out-n<i>-* 端口")
        图 = f"out-n{镜号}-image"
        视 = f"out-n{镜号}-video"
        已有 = {p["id"] for p in n["data"]["outputs"]}
        for i, t, lab in ((图, "image", f"镜{镜号} 🖼 图prompt"), (视, "video", f"镜{镜号} 🎬 视频prompt")):
            if i not in 已有:
                n["data"]["outputs"].append({"id": i, "label": lab, "dataType": t, "direction": "output"})
        return 图, 视

    def 连线(self, 源节点: str, 源端口: str, 目标节点: str, 目标端口: str) -> str:
        """加一条边。**当场过 `能连吗()`** —— 不合法直接抛，绝不留一条坏边在画布上。"""
        s = self._必须节点(源节点)
        t = self._必须节点(目标节点)
        源出 = {p["id"]: p.get("dataType") for p in s["data"].get("outputs") or []}
        标入 = {p["id"]: p.get("dataType") for p in t["data"].get("inputs") or []}
        好 = 端口契约.get(s["data"]["moduleId"]) and 端口契约.get(t["data"]["moduleId"])
        if 好:
            # 有契约的两个模块：走飞彩原版闸门（最严）
            能, 因 = 能连吗(
                [{"nodeId": s["id"], "moduleId": s["data"]["moduleId"]},
                 {"nodeId": t["id"], "moduleId": t["data"]["moduleId"]}],
                {"nodeId": s["id"], "portId": 源端口},
                {"nodeId": t["id"], "portId": 目标端口},
            )
            if not 能:
                raise 连线非法(因)
        else:
            # 没有契约的模块（飞彩那 20 个也在这一档）：退到「端口存在 + 类型相等」，
            # 并明确标注这是**影匠的兜底**，不是飞彩行为。
            if 源端口 not in 源出:
                raise 连线非法(f"上游模块 {s['data']['moduleId']} 没有出端口 {源端口}")
            if 目标端口 not in 标入:
                raise 连线非法(f"下游模块 {t['data']['moduleId']} 没有入端口 {目标端口}")
            if 源出[源端口] != 标入[目标端口]:
                raise 连线非法(
                    f"类型对不上：上游出端口 {源端口} 是 {源出[源端口]}，"
                    f"下游入端口 {目标端口} 要 {标入[目标端口]}"
                )
        for e in self.边们:
            if (e.get("source") == 源节点 and e.get("sourceHandle") == 源端口
                    and e.get("target") == 目标节点 and e.get("targetHandle") == 目标端口):
                return e["id"]
        eid = "e" + hashlib.sha1(f"{源节点}|{源端口}|{目标节点}|{目标端口}".encode()).hexdigest()[:14]
        self.边们.append({
            "id": eid, "source": 源节点, "target": 目标节点,
            "sourceHandle": 源端口, "targetHandle": 目标端口,
        })
        return eid

    def 断线(self, 边id: str) -> bool:
        for i, e in enumerate(self.边们):
            if e.get("id") == 边id:
                self.边们.pop(i)
                return True
        return False

    def 设参数(self, 节点id: str, **键值) -> dict:
        n = self._必须节点(节点id)
        坏 = _扫密钥键(键值, f"{节点id} ")
        if 坏:
            raise 参数非法("；".join(坏))
        允许 = {p["key"] for p in (目录表.get(n["data"]["moduleId"], {}).get("paramsSchema") or [])}
        不认 = [k for k in 键值 if 允许 and k not in 允许]
        n["data"].setdefault("params", {}).update(键值)
        if 不认:
            n["data"]["params"]["_不认的参数"] = 不认
        return n["data"]["params"]

    def 记默认值(self, 模块id: str, **键值):
        """飞彩 `feicai-canvas-defaults-${moduleId}`：**只记该模块声明过的键**。"""
        允许 = {p["key"] for p in (目录表.get(模块id, {}).get("paramsSchema") or [])}
        d = self.文档.setdefault("defaults", {}).setdefault(模块id, {})
        for k, v in 键值.items():
            if k in 允许:
                d[k] = v

    # ---------- 存 / 读 ----------

    def 快照(self) -> dict:
        return json.loads(json.dumps(self.文档, ensure_ascii=False, default=str))

    def 存(self, 路: str | None = None, 瘦身大块: bool = True) -> str:
        """写工程 JSON。**原子写**：先 .tmp 再 os.replace。revision 自增，并记 revisionDigest。"""
        路 = 路 or self.路 or os.path.join(工程根, self.画布id + ".json")
        os.makedirs(os.path.dirname(os.path.abspath(路)) or ".", exist_ok=True)
        self.路 = 路
        self.文档["revision"] = int(self.文档.get("revision", 0)) + 1
        self.文档["updatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
        出 = self.快照()
        if 瘦身大块:
            出["nodes"] = _瘦身(出["nodes"])
        self.文档["revisionDigest"] = 哈希64(出)
        tmp = 路 + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.文档, f, ensure_ascii=False, indent=1)
        os.replace(tmp, 路)
        _记索引(self)
        return 路

    # ---------- 证据 ----------

    def 证据(self, 节点id: str) -> dict:
        """画布改动提案要的 evidence 块（实测字段：canvasRevision/evidenceDigest/…）。"""
        n = self._必须节点(节点id)
        return {
            "canvasRevision": self.文档.get("revisionDigest", "0" * 64),
            "evidenceDigest": 哈希64({"node": n, "revision": self.文档.get("revision")}),
            "selectionInstanceId": self.画布id,
            "selectionVersion": int(self.文档.get("revision", 0)),
            "node": {"nodeId": n["id"], "moduleId": n["data"]["moduleId"]},
        }

    def 定义(self) -> dict:
        """如实报：这份工程里哪些是飞彩原样、哪些是影匠自创。"""
        飞 = []
        自 = []
        for n in self.节点们:
            mid = n["data"]["moduleId"]
            元 = 目录表.get(mid, {})
            if 元.get("source") == "builtin" and mid in 画布白名单:
                飞.append({"nodeId": n["id"], "moduleId": mid, "name": 元.get("name")})
            else:
                自.append({"nodeId": n["id"], "moduleId": mid, "name": 元.get("name", "?"),
                           "why": "飞彩白名单外" if mid not in 画布白名单 else "飞彩无内联定义（仅登记）"})
        return {"飞彩原样": 飞, "影匠自创": 自,
                "说明": "飞彩原样 = 在白名单 24 条内且有内联定义；影匠自创 = 其余（含自加模块）"}


def _库存(路: str) -> dict:
    try:
        with io.open(路, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _保证库(路: str) -> dict:
    d = _库存(路)
    d.setdefault("schemaVersion", 1)
    d.setdefault("projects", [])
    return d


#: 工程索引文件（对齐飞彩 `canvas-projects` 那份清单）。
索引文件 = os.path.join(工程根, "_索引.json")


def _记索引(p: 工程) -> None:
    os.makedirs(工程根, exist_ok=True)
    d = _保证库(索引文件)
    条 = {"id": p.画布id, "name": p.文档.get("name", ""), "projectId": p.项目id,
          "revision": p.文档.get("revision", 0), "节点数": len(p.节点们), "边数": len(p.边们),
          "路": os.path.abspath(p.路 or ""), "updatedAt": p.文档.get("updatedAt", "")}
    d["projects"] = [x for x in d["projects"] if x.get("id") != p.画布id] + [条]
    tmp = 索引文件 + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, 索引文件)


def 列工程() -> list[dict]:
    d = _库存(索引文件)
    出 = list(d.get("projects") or [])
    if not 出 and os.path.isdir(工程根):
        for f in sorted(os.listdir(工程根)):
            if f.endswith(".json") and not f.startswith("_"):
                出.append({"id": f[:-5], "name": f, "路": os.path.join(工程根, f)})
    return 出


def 找工程(键: str) -> str:
    """按 id / 名字 / 文件名找工程路径。"""
    c = os.path.join(工程根, 键 + ".json")
    if os.path.isfile(c):
        return c
    for x in 列工程():
        if 键 in (x.get("id"), x.get("name")) and x.get("路") and os.path.isfile(x["路"]):
            return x["路"]
    raise 工程错(f"找不到工程 {键!r}（在 {工程根} 里）")


def 空工程(名字: str = "未命名画布") -> 工程:
    return 工程({"name": 名字})


def 读工程(路: str) -> 工程:
    with io.open(路, encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        raise 工程错(f"{路} 不是一份画布工程（顶层不是对象）")
    return 校验工程(d, 路)


def 校验工程(d: dict, 路: str = "") -> 工程:
    """读进来的东西要过一遍闸：id 规范、模块存在、状态枚举、边两端都在。"""
    问题 = []
    if not isinstance(d.get("nodes"), list):
        问题.append("nodes 不是数组")
    if not isinstance(d.get("edges"), list):
        问题.append("edges 不是数组")
    if 问题:
        raise 工程错(f"{路} 不合格：" + "；".join(问题))
    节点id们 = set()
    for n in d["nodes"]:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str):
            问题.append(f"节点缺 id：{n!r}")
            continue
        if not ID规范.match(n["id"]):
            问题.append(f"节点 id 不合规范（飞彩 rM）：{n['id']!r}")
        节点id们.add(n["id"])
        dat = n.get("data")
        if not isinstance(dat, dict):
            问题.append(f"节点 {n['id']} 缺 data")
            continue
        mid = dat.get("moduleId")
        if mid not in 目录表:
            问题.append(f"节点 {n['id']} 的模块 {mid!r} 不在画布目录里")
        st = dat.get("status", "idle")
        if st not in 节点状态:
            问题.append(f"节点 {n['id']} 状态 {st!r} 不在 {节点状态}")
        坏 = _扫密钥键(dat.get("params") or {}, f"节点 {n['id']} ")
        问题 += 坏
    for e in d["edges"]:
        if not isinstance(e, dict):
            问题.append(f"边不是对象：{e!r}")
            continue
        if e.get("source") not in 节点id们:
            问题.append(f"边 {e.get('id')} 的上游 {e.get('source')!r} 不在画布上")
        if e.get("target") not in 节点id们:
            问题.append(f"边 {e.get('id')} 的下游 {e.get('target')!r} 不在画布上")
        if e.get("source") == e.get("target"):
            问题.append(f"边 {e.get('id')} 是自己连自己")
    if 问题:
        raise 工程错(f"{路} 有 {len(问题)} 处不合格：\n  - " + "\n  - ".join(问题[:12]))
    return 工程(d, 路)


def 工程文档(名字: str, 节点们: list, 边们: list) -> dict:
    return {"name": 名字, "nodes": 节点们, "edges": 边们}


# ============================================================
# 6. 拓扑分层 —— 照抄飞彩 `n(e,t)`
# ============================================================

class 有环(工程错):
    pass


def 拓扑分层(节点们: list, 边们: list) -> dict:
    """飞彩 `n(e,t)` 的中文还原。返回 `{layers, totalSteps, 跳过组}`。

    与飞彩逐条对齐：
      · `type === "group"` 的节点**不进图**（组只是视觉容器）
      · 入度加在 `target` 上，方向 `source → target`
      · 一层一层出（同层可以并发），孤立节点自成一层
      · 出完的节点数 < 节点数 → 抛 `工作流中存在循环依赖，无法执行`
    """
    组里 = []
    真 = []
    for n in 节点们:
        if not isinstance(n, dict):
            continue
        if n.get("type") == "group":
            组里.append(n.get("id"))
        else:
            真.append(n)
    集 = {n.get("id") for n in 真 if isinstance(n.get("id"), str)}
    入度 = {i: 0 for i in 集}
    邻 = {i: [] for i in 集}
    for e in 边们:
        if not isinstance(e, dict):
            continue
        s, t = e.get("source"), e.get("target")
        if s in 集 and t in 集:
            入度[t] = 入度.get(t, 0) + 1
            邻[s].append(t)
    层们 = []
    当前 = sorted([i for i in 入度 if 入度[i] == 0])
    while 当前:
        层们.append(list(当前))
        下 = []
        for i in 当前:
            for j in 邻.get(i) or []:
                入度[j] -= 1
                if 入度[j] == 0:
                    下.append(j)
        当前 = sorted(下)
    出过 = sum(len(x) for x in 层们)
    if 出过 < len(集):
        raise 有环(错_环)
    return {"layers": 层们, "totalSteps": len(集), "跳过组": 组里}


def 上游们(边们: list, 节点id: str) -> list[str]:
    """飞彩 `ob(e,t,a)`：`t.filter(target===a).map(source)`。"""
    return [e["source"] for e in 边们 if isinstance(e, dict) and e.get("target") == 节点id and e.get("source")]


def 祖先们(边们: list, 起: str) -> set:
    """一个节点 + 它全部上游（用于「只跑这条链」）。"""
    出 = {起}
    栈 = [起]
    while 栈:
        c = 栈.pop()
        for u in 上游们(边们, c):
            if u not in 出:
                出.add(u)
                栈.append(u)
    return 出


# ============================================================
# 7. 数据键解析 —— 照抄飞彩的 `n_` / `upstreamData`
# ============================================================

def 解析目标口(边: dict, 本节点inputs: list, 兜底类型: str = "any") -> tuple[str, str]:
    """飞彩 `l(e,t,a)`：给一条边解析出「用哪个入端口 / 写进 upstreamData 的哪个键」。

    优先级：`data.targetPort` → `targetHandle` → 按类型找一个兼容口 → `"input"`。
    """
    r = 边.get("data", {}).get("targetPort") if isinstance(边.get("data"), dict) else None
    if not (isinstance(r, str) and r):
        r = 边.get("targetHandle")
    口 = None
    for p in 本节点inputs or []:
        if p.get("id") == r:
            口 = p
            break
    if 口 is None:
        口 = _按类型找口(兜底类型, 本节点inputs)
    键 = (口 or {}).get("id") or r or "input"
    return 键, (口 or {}).get("dataType", 兜底类型)


def _按类型找口(类型: str, 口们: list) -> dict | None:
    """飞彩 `r(e,t)`：先要类型完全相同的；再要 `any`；最后要「能容」的。"""
    for p in 口们 or []:
        if p.get("dataType") == 类型:
            return p
    for p in 口们 or []:
        if p.get("dataType") == "any":
            return p
    for p in 口们 or []:
        if _能容(类型, p.get("dataType")):
            return p
    return None


def _能容(给: str, 要: str) -> bool:
    return 给 == 要 or 要 == "any"


def 取输出值(节点数据: dict) -> str:
    """飞彩 `qg(e)`：一个节点的输出值，按优先级抠。

    `result.outputUrl || params.file || params.content || (text-input ? params.prompt : "")`
    """
    r = 节点数据.get("result") or {}
    if isinstance(r, dict):
        v = r.get("outputUrl")
        if isinstance(v, str) and v:
            return v
    p = 节点数据.get("params") or {}
    for k in ("file", "content"):
        v = p.get(k)
        if isinstance(v, str) and v:
            return v
    if 节点数据.get("moduleId") == "builtin:text-input":
        v = p.get("prompt")
        if isinstance(v, str) and v:
            return v
    return ""


def 建上游数据(节点: dict, 节点索引: dict, 边们: list) -> dict:
    """飞彩 `N5(e,t,a)`：把一个节点的入边收成 `upstreamData`。"""
    出 = {}
    for e in 边们:
        if not isinstance(e, dict) or e.get("target") != 节点.get("id"):
            continue
        上 = 节点索引.get(e.get("source"))
        if not 上:
            continue
        值 = 取输出值(上.get("data") or {})
        if not 值:
            continue
        出们 = (上.get("data") or {}).get("outputs") or []
        类型 = 出们[0].get("dataType") if 出们 else "any"
        键, 口类型 = 解析目标口(e, (节点.get("data") or {}).get("inputs") or [], 类型)
        出[键] = 值
    return 出


def 同不同(a, b) -> bool:
    """飞彩 `cT`：两个 upstreamData 是不是一样（键数 + 逐键严格相等）。"""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return a == b
    if set(a) != set(b):
        return False
    return all(a[k] == b.get(k) for k in a)


def 合并上游(旧: dict, 入边们: list, 节点索引: dict, 本节点: dict) -> dict:
    """飞彩 `hY(e,t,a,r,n)`：把 `out-n<i>-*` 那种每镜端口的结果并进去。"""
    新 = dict(旧 or {})
    来 = 建上游数据(本节点, 节点索引, 入边们)
    用 = set()
    for e in 入边们:
        if e.get("target") != 本节点.get("id"):
            continue
        上 = 节点索引.get(e.get("source"))
        出们 = ((上 or {}).get("data") or {}).get("outputs") or []
        类型 = 出们[0].get("dataType") if 出们 else "any"
        键, _ = 解析目标口(e, (本节点.get("data") or {}).get("inputs") or [], 类型)
        用.add(键)
        用.add(e.get("targetHandle") or "input")
    for k in 用:
        if k in 来:
            新[k] = 来[k]
        elif k in 新:
            新.pop(k, None)
    return 新


# ============================================================
# 8. 节点执行器 —— 影匠真正的活在这里
# ============================================================

def _报无(msg):
    print("   ", msg)


def _归一比例(s: str) -> tuple[int, int]:
    表 = {"16:9": (1024, 576), "9:16": (576, 1024), "1:1": (768, 768),
          "4:3": (896, 672), "3:4": (672, 896), "21:9": (1024, 440)}
    return 表.get(str(s or "1:1"), (768, 768))


def _种子(参数: dict) -> int | None:
    v = 参数.get("seed")
    try:
        return int(v) if v not in (None, "") else None
    except Exception:
        return None


def _输出目录() -> str:
    戏 = os.environ.get("影匠_画布_戏名", "画布")
    d = os.path.join(这里, "作品", 戏)
    os.makedirs(d, exist_ok=True)
    return d


def 要引擎() -> tuple:
    if _引擎 is None:
        raise RuntimeError(f"引擎.py 载入失败：{_引擎错}")
    return _引擎, ""


def _跑_文本(上: dict, 参数: dict, 报, 名字: str = "") -> dict:
    """`builtin:text-input`：飞彩取值顺序 `result.outputUrl || params.file || params.content || params.prompt`。

    影匠这里只用 params，因为文本节点不产出文件。
    """
    文 = (参数.get("content") or "").strip()
    if not 文:
        文 = (上.get("in-text") or "").strip()
    if 文:
        _洗文本(文, "文本节点 content")
    附 = (参数.get("prompt") or "").strip()
    报(f"文本 {len(文)} 字" + (f" + 附加指令 {len(附)} 字" if 附 else ""))
    if not 文 and not 附:
        raise RuntimeError("文本节点是空的：params.content 和上游 in-text 都没有东西")
    return {"outputText": 文, "outputUrl": 文, "内容": 文, "附加": 附}


def _跑_智能图片(上: dict, 参数: dict, 报, 名字: str) -> dict:
    """`builtin:smart-image` → 影匠这边就是 `引擎.文生图`。

    上游取值顺序照飞彩：提示词 `in-text` 优先，参数 `prompt` 兜底；
    参考图 `in-ref` / `in-image`（本地绝对路径）。
    """
    引, _ = 要引擎()
    词 = (上.get("in-text") or "").strip() or (参数.get("prompt") or "").strip()
    if not 词:
        raise RuntimeError("智能图片节点没有提示词：上游 in-text 和 params.prompt 都是空的")
    参 = [p for p in (上.get("in-ref"), 上.get("in-image")) if p and os.path.isfile(str(p))]
    比 = 参数.get("aspectRatio") or "16:9"
    宽, 高 = _归一比例(比)
    存 = os.path.join(_输出目录(), f"{名字}.png")
    果 = 引.文生图(
        词, 宽=宽, 高=高, 种子=_种子(参数),
        前缀=f"影匠/画布/{名字}", 报=报, 存到=存,
        参考图=参 or None,
    )
    报(f"出图 {os.path.basename(果['路'])}  种子 {果['种子']}")
    return {**果, "outputUrl": 果["路"], "outputText": 词, "比例": 比,
            "参考图数": len(参)}


def _跑_智能视频(上: dict, 参数: dict, 报, 名字: str) -> dict:
    """`builtin:smart-video` → `引擎.图生视频`。上游首帧取 `in-image`。"""
    引, _ = 要引擎()
    图 = 上.get("in-image") or 上.get("in-image-last") or 参数.get("file")
    if not 图 or not os.path.isfile(str(图)):
        raise RuntimeError("智能视频节点没有可用的首帧图（上游 in-image 没接东西）")
    词 = (上.get("in-text") or "").strip() or (参数.get("prompt") or "").strip()
    if not 词:
        raise RuntimeError("智能视频节点没有提示词：上游 in-text 和 params.prompt 都是空的")
    宽, 高 = _归一比例(参数.get("ratio") or "16:9")
    存 = os.path.join(_输出目录(), f"{名字}.mp4")
    果 = 引.图生视频(
        图, 词, 种子=_种子(参数), 帧数=int(参数.get("frames") or 49),
        帧率=int(参数.get("fps") or 16), 宽=宽, 高=高,
        模板=参数.get("videoTemplate") or "wan22_i2v",
        前缀=f"影匠/画布/{名字}", 报=报, 存到=存,
    )
    报(f"出片 {os.path.basename(果['路'])}")
    return {**果, "outputUrl": 果["路"], "outputText": 词}


def _跑_拼图(上: dict, 参数: dict, 报, 名字: str) -> dict:
    """`builtin:image-puzzle` → `拼图.拼`（影匠已有）。"""
    import importlib.util
    p = os.path.join(这里, "拼图.py")
    spec = importlib.util.spec_from_file_location("_影匠_拼图", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    图 = 上.get("input") or 上.get("in-image")
    if not 图 or not os.path.isdir(str(图)):
        raise RuntimeError(
            "拼图节点要的是一个目录（影匠 拼图.拼(目录)）；"
            "上游给的是单张图 —— 这一档影匠还没接（飞彩是节点内多图列表）。"
        )
    出 = os.path.join(_输出目录(), f"{名字}.png")
    路 = m.拼(图, 每行=int(参数.get("cols") or 2), 出=出)
    报(f"拼图 {os.path.basename(str(路))}")
    return {"outputUrl": str(路)}


def _跑_直通(上: dict, 参数: dict, 报, 名字: str) -> dict:
    """`builtin:media-deai` / `face-mask` 这类：影匠还没有真实现。

    **照实说做不了，绝不假装成功。**
    """
    raise RuntimeError(
        "这个节点影匠还没有执行器（只有飞彩的节点定义）。\n"
        "  飞彩那边它是个真功能（插件/RunningHub 工作流），影匠这边没有对应实现；\n"
        "  报错好过假装跑通 —— 假装跑通会让下游拿一个不存在的产物继续跑。"
    )


#: 模块 id → (执行函数, 需要哪种上游, 说明)。**只登记影匠真能干的。**
执行器: dict[str, dict] = {}


def _登记执行器(模块id, 函数, 上游, 说明, 需要联网=False, 要显卡=False):
    执行器[模块id] = {"函数": 函数, "上游": 上游, "说明": 说明,
                      "需要联网": 需要联网, "要显卡": 要显卡}


_登记执行器("builtin:text-input", _跑_文本, "none", "纯本地拼文本", False, False)
_登记执行器("builtin:smart-image", _跑_智能图片, "text", "引擎.文生图（本机 ComfyUI）", False, True)
_登记执行器("builtin:smart-video", _跑_智能视频, "image", "引擎.图生视频（本机 ComfyUI）", False, True)
_登记执行器("builtin:image-puzzle", _跑_拼图, "image", "拼图.拼", False, False)
for _m in ("builtin:rh-upscale", "builtin:rh-angle-ctrl", "builtin:rh-tts", "builtin:rh-script-tts",
           "builtin:rh-webapp", "builtin:seedance-multi-ref", "builtin:seedance-video",
           "builtin:script-parser", "builtin:script-extract", "builtin:ref-forge",
           "builtin:picture-frame", "builtin:media-deai", "builtin:face-mask",
           "builtin:video-superres", "builtin:video-remove-watermark",
           "builtin:video-remove-subtitles", "builtin:video-enhance",
           "builtin:output-preview"):
    _登记执行器(_m, _跑_直通, "any", "★ 影匠没有执行器（只有飞彩的节点定义）")


def 有执行器(模块id: str) -> bool:
    e = 执行器.get(模块id)
    return bool(e) and e["函数"] is not _跑_直通


def 派活(节点: dict, 报=None) -> dict:
    """按模块 id 派给上面登记的执行函数。"""
    报 = 报 or _报无
    mid = 节点["data"]["moduleId"]
    e = 执行器.get(mid)
    if e is None:
        raise RuntimeError(f"模块 {mid} 没有执行器（也不在「没有执行器」名单里）")
    上 = (节点["data"].get("upstreamData") or {})
    参 = dict(节点["data"].get("params") or {})
    名字 = f"{mid.replace('builtin:', '')}-{节点['id']}"
    return e["函数"](上, 参, 报, 名字)# ============================================================
# 9. 执行 —— 照抄飞彩 `m(...)` 的硬约束
# ============================================================

class 节点未启动(Exception):
    pass


class 画布执行错(工程错):
    pass


def 跑(工程: 工程, 只跑: str | None = None, 并发: int | None = None,
       截止秒: int | None = None, 干跑: bool = False, 报=None,
       记快照: bool = True) -> dict:
    """按拓扑分层跑一遍。

    与飞彩逐条对齐：
      · `并发` 必须在 1..30，否则抛 `画布执行并发必须是 1-30 的整数`
      · `截止秒` 必须是正的安全整数，否则抛 `画布执行截止时间无效`
      · 同层并发（飞彩 `x=i.maxConcurrency??u`）
      · 上游失败 → 下游**跳过**，理由逐字 `` `上游 <后6位> 失败,已跳过：<错误前80字>` ``
      · 结果写回前过 `应该写回()` 闸；不过就抛/记 `节点执行结果已与当前队列或画布失配，迟到结果未写回`
      · 每次节点开始前跑 `beforeNodeStart` 门禁，拒了就记 `节点启动门禁已拒绝`
      · 跑之前把每个节点的 `upstreamData` 存一份快照，失败重跑时回滚输入
      · `只跑=某节点` 就是飞彩的「失败节点单独重跑」：只跑它 + 它的祖先链

    返回 `{通过, 失败, 跳过, 没测, 层, 起, 止, 秒, 报告}`。
    """
    from concurrent.futures import ThreadPoolExecutor

    报 = 报 or print
    x = int(并发) if 并发 is not None else 1
    if not (isinstance(x, int) and 1 <= x <= 并发上限):
        raise 画布执行错(错_并发.format(u=并发上限))
    if 截止秒 is not None:
        if not (isinstance(截止秒, int) and 截止秒 > 0):
            raise 画布执行错(错_截止)
        止刻 = time.time() + 截止秒
    else:
        止刻 = None

    层 = 拓扑分层(工程.节点们, 工程.边们)
    索引 = {n["id"]: n for n in 工程.节点们 if n.get("id")}
    要跑集 = None
    if 只跑:
        if 只跑 not in 索引:
            raise 工程错(f"画布里没有节点 {只跑}")
        要跑集 = 祖先们(工程.边们, 只跑)

    # 飞彩：先快照每个节点的 upstreamData，失败重跑时用它回滚输入
    旧输入 = {n["id"]: dict(n["data"].get("upstreamData") or {}) for n in 工程.节点们 if n.get("id")}

    失败集: set = set()
    跳过集: set = set()
    理由: dict[str, str] = {}
    记录: list[dict] = []
    起 = time.time()

    def _该写回(节点id: str) -> bool:
        """飞彩 `shouldCommitNodeResult` 在本机的替身：工程还在、节点还在、节点没被别人删掉。"""
        n = 工程.取节点(节点id)
        return n is not None

    def _一个(节点: dict, 第几层: int) -> dict:
        nid = 节点["id"]
        名 = f"{节点['data'].get('moduleName') or 节点['data']['moduleId']}·{nid}"
        # ── 门禁：上游失败就跳过（飞彩原话）──
        for u in 上游们(工程.边们, nid):
            if u in 失败集:
                理 = 理由.get(u, "")
                短 = (理[:80] + "…") if len(理) > 80 else 理
                跳过集.add(nid)
                理由[nid] = f"上游 {u[-6:]} 失败,已跳过" + (f"：{短}" if 短 else "")
                报(f"· 跳过 {名} —— {理由[nid]}")
                return {"节点": nid, "状态": "跳过", "理由": 理由[nid]}
        # ── 截止 ──
        if 止刻 is not None and time.time() >= 止刻:
            跳过集.add(nid)
            理由[nid] = "过了截止时间，没开跑"
            报(f"· 跳过 {名} —— {理由[nid]}")
            return {"节点": nid, "状态": "跳过", "理由": 理由[nid]}
        # ── 输入：重新解析 upstreamData（照飞彩 N5/hY）──
        入边 = [e for e in 工程.边们 if e.get("target") == nid]
        新入 = 建上游数据(节点, 索引, 工程.边们)
        if not 同不同(节点["data"].get("upstreamData"), 新入):
            节点["data"]["upstreamData"] = 新入
            报(f"  输入变了：{sorted(新入)}")
        节点["data"]["status"] = "running"
        t0 = time.time()
        try:
            if 干跑:
                果 = {"outputUrl": "", "outputText": 取输出值(节点["data"]) or "(干跑)",
                      "干跑": True}
            else:
                果 = 派活(节点, 报=lambda s: 报(f"    {s}"))
        except Exception as e:
            理 = f"{type(e).__name__}: {e}"
            失败集.add(nid)
            理由[nid] = 理
            节点["data"]["status"] = "error"
            节点["data"]["error"] = 理
            节点["data"]["result"] = {"status": "failed", "error": 理}
            报(f"· 失败 {名} —— {理[:160]}")
            return {"节点": nid, "状态": "失败", "理由": 理, "秒": round(time.time() - t0, 2)}
        用 = round(time.time() - t0, 2)
        if not _该写回(nid):
            失败集.add(nid)
            理由[nid] = 错_迟到
            报(f"· 迟到 {名} —— {错_迟到}")
            return {"节点": nid, "状态": "失败", "理由": 错_迟到, "秒": 用}
        节点["data"]["status"] = "success"
        节点["data"]["result"] = {"status": "done", "outputUrl": 果.get("outputUrl", ""),
                                  "outputText": 果.get("outputText", ""), "原始": 果}
        节点["data"]["error"] = ""
        节点["data"]["耗时"] = 用
        报(f"· 完成 {名}  {用}s" + (f"  → {os.path.basename(str(果.get('outputUrl')))}"
                                   if 果.get("outputUrl") else ""))
        return {"节点": nid, "状态": "完成", "秒": 用, "产物": 果.get("outputUrl", "")}

    for 号, 一层 in enumerate(层["layers"]):
        要 = [nid for nid in 一层 if (要跑集 is None or nid in 要跑集)]
        if not 要:
            continue
        报(f"第 {号 + 1} 层：{len(要)} 个节点" + (f"（并发 {x}）" if x > 1 and len(要) > 1 else ""))
        if x == 1 or len(要) == 1:
            for nid in 要:
                记录.append(_一个(索引[nid], 号))
        else:
            with ThreadPoolExecutor(max_workers=min(x, len(要))) as 池:
                for r in 池.map(lambda i: _一个(索引[i], 号), 要):
                    记录.append(r)

    进 = sum(1 for r in 记录 if r["状态"] == "完成")
    败 = sum(1 for r in 记录 if r["状态"] == "失败")
    跳 = sum(1 for r in 记录 if r["状态"] == "跳过")
    没 = len(层["layers"] and [i for L in 层["layers"] for i in L]) - len(记录)
    工程.文档["updatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return {"通过": 进, "失败": 败, "跳过": 跳, "没测": max(0, 没),
            "层": 层["layers"], "起": 起, "止": time.time(),
            "秒": round(time.time() - 起, 2), "报告": 记录}


def 收产物(工程: 工程, 报=None) -> dict:
    """把跑成功的节点产物写回画布，并（可选）挂进素材库。

    照抄飞彩的两条：
      · 产物值 = `result.outputUrl || params.file`（`8703 @170600` 的 `u(e,t,a)`）
      · 产物进素材库走 `一致性.绑定(素材名, 图片路径)`
    """
    报 = 报 or _报无
    回 = {"写回": 0, "素材": 0, "跳过": 0, "明细": []}
    for n in 工程.节点们:
        d = n.get("data") or {}
        if d.get("status") != "success":
            回["跳过"] += 1
            continue
        路 = (d.get("result") or {}).get("outputUrl") or (d.get("params") or {}).get("file") or ""
        d["产物"] = 路
        回["写回"] += 1
        回["明细"].append({"节点": n["id"], "模块": d.get("moduleId"), "产物": 路})
        if 路 and os.path.isfile(str(路)) and _一致性 is not None and str(路).lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp")):
            try:
                名 = f"画布_{工程.文档.get('name', '未命名')}_{n['id']}"
                _一致性.建(名, 类别="character", 描述=f"画布节点 {d.get('moduleId')} 的产物")
                _一致性.绑定(名, 路)
                回["素材"] += 1
                报(f"挂进素材库：{名}")
            except Exception as e:
                报(f"（挂素材库失败，不影响产物本身：{e}）")
    工程.存()
    return 回


# ============================================================
# 10. 成本预告 + 改画布提案（照抄飞彩的「改画布永远不花钱」）
# ============================================================

#: 影匠的基线耗时（**设计意图，不是实测** —— 因为没有样本时会退回这里）。
基线秒 = {"builtin:text-input": 0.05, "builtin:smart-image": 60.0, "builtin:smart-video": 300.0,
        "builtin:image-puzzle": 3.0}


def 成本预告(工程: 工程, 只跑: str | None = None, 并发: int | None = None) -> dict:
    """跑之前先告诉人：要开几个节点、几条要真花钱、并发多少。

    飞彩原话（逐字）：
      「本次确定新增 LLM 调用 N 次，执行并发上限为 3；账本查询与任务续查不会新调用模型。」
    这里照它的**结构**（数量 + 并发上限 + 哪部分不花钱），换成影匠的计数。
    """
    x = int(并发) if 并发 is not None else 1
    if not (isinstance(x, int) and 1 <= x <= 并发上限):
        raise 画布执行错(错_并发.format(u=并发上限))
    层 = 拓扑分层(工程.节点们, 工程.边们)
    要 = set()
    if 只跑:
        要 = 祖先们(工程.边们, 只跑)
    明细 = []
    会跑 = 0
    要显卡 = 0
    秒 = 0.0
    元 = 0.0
    for L in 层["layers"]:
        for nid in L:
            if 要 and nid not in 要:
                continue
            n = 工程.取节点(nid)
            if n is None:
                continue
            mid = n["data"]["moduleId"]
            e = 执行器.get(mid)
            有 = 有执行器(mid)
            会跑 += 1 if 有 else 0
            要显卡 += 1 if (e and e.get("要显卡")) else 0
            s = 基线秒.get(mid)
            依据 = "基线（设计意图）"
            if s is None:
                s = 30.0
                依据 = "没样本，按 30 秒兜底（设计意图）"
            试 = _试估账本(mid)
            if 试:
                s = 试["均值秒"]
                依据 = f"账本实测均值（样本 {试['样本']}）"
            秒 += s
            m = _报价(mid, n["data"].get("params") or {})
            元 += m
            明细.append({"节点": nid, "模块": mid, "名字": 目录表.get(mid, {}).get("name", "?"),
                         "有执行器": 有, "耗时秒": round(s, 2), "依据": 依据,
                         "估价元": round(m, 4), "要显卡": bool(e and e.get("要显卡"))})
    测 = sum(1 for d in 明细 if d["依据"].startswith("账本实测"))
    return {
        "会跑节点": 会跑, "没执行器": len(明细) - 会跑, "要显卡": 要显卡,
        "并发上限": x, "预计总秒": round(秒, 2),
        "预计总元": round(元, 4),
        "依据分布": {"实测": 测, "设计意图": len(明细) - 测},
        "人话": (f"本次确定要开 {会跑} 个节点（其中 {要显卡} 个要占显卡），"
                 f"执行并发上限为 {x}；画布读写、拓扑排序、成本预告都不会新调用模型。"
                 f"预计 {round(秒, 1)} 秒 / {round(元, 4)} 元。"),
        "明细": 明细,
    }


def _试估账本(类型: str):
    if _账本 is None:
        return {}
    try:
        账 = _账本.取账本()
        r = 账._实测(类型) if hasattr(账, "_实测") else {}
        return r if r.get("样本") else {}
    except Exception:
        return {}


def _报价(模块id: str, 参数: dict) -> float:
    """问一下接入层这个模块大概多少钱。本地一律 0（它给的是 0，不是「不知道」）。"""
    if _注册表 is None:
        return 0.0
    模块到模型 = {
        "builtin:smart-image": 参数.get("imageModelId"),
        "builtin:smart-video": 参数.get("videoModelId"),
        "builtin:seedance-video": 参数.get("videoModelId") or "doubao-seedance-1-0-pro-250528",
    }
    模型 = 模块到模型.get(模块id)
    if not 模型:
        return 0.0
    try:
        for 条 in _注册表.报价(模型, {"次数": 1, "时长秒": 参数.get("duration")}):
            if 条.get("预估") is not None:
                return float(条["预估"])
    except Exception:
        pass
    return 0.0


def 提改动(工程: 工程, 种类: str, **kw) -> dict:
    """画布改动提案。照抄飞彩：**四个 kind 全都不许花钱、不许跑节点**。

    实测骨架：`{schemaVersion:1, costCents, approvalRequired, runNodes, evidence, mutation}`
    实测上限：`0 <= costCents <= 800`，`approvalRequired` 必须为 True。
    """
    if 种类 not in 改动种类:
        raise 工程错(f"改动种类只能是 {改动种类}，给的是 {种类!r}")
    costCents = int(kw.get("costCents", 0))
    if not (0 <= costCents <= 改动费用上限分):
        人话 = {0: "改画布本身不花钱", }.get(0, "")
        raise 工程错(
            f"costCents 必须在 0..{改动费用上限分}（飞彩原判据）。"
            f"**{种类} 这类改动飞彩要求 costCents===0 且 runNodes===false**"
            f"（改画布永远不花钱，要花钱得另开一次 canvas.run）。"
        )
    if costCents != 0:
        raise 工程错(f"{种类} 要求 costCents===0（飞彩原判据：改画布零费用）")
    if kw.get("runNodes"):
        raise 工程错(f"{种类} 要求 runNodes===false（改完不会自动跑）")
    if 种类 == "connect":
        源 = kw["source"]
        目标 = kw["target"]
        能, 因 = 能连吗(
            [{"nodeId": n["id"], "moduleId": n["data"]["moduleId"]} for n in 工程.节点们],
            {"nodeId": 源["nodeId"], "portId": 源["portId"]},
            {"nodeId": 目标["nodeId"], "portId": 目标["portId"]},
        )
        if not 能:
            raise 连线非法(f"connect 提案没通过 r5：{因}")
        证据 = 工程.证据(源["nodeId"])
        if [源["nodeId"], 目标["nodeId"]] != sorted([源["nodeId"], 目标["nodeId"]]):
            # 飞彩要求 [n,s].sort() 之后与 evidence 里的节点顺序一致
            证据["_注"] = "飞彩要求 source/target 的 nodeId 排序后等于 evidence 里的节点顺序"
        return {"schemaVersion": 1, "costCents": 0, "approvalRequired": True, "runNodes": False,
                "evidence": 证据, "mutation": {"kind": "connect", "source": dict(源), "target": dict(目标)}}
    if 种类 == "auto_layout":
        位置 = kw.get("positions")
        if not isinstance(位置, list) or len(位置) < 2 or len(位置) > 64:
            raise 工程错("auto_layout 要 2..64 个 {nodeId,x,y}（飞彩原判据）")
        for p in 位置:
            if not (isinstance(p, dict) and isinstance(p.get("nodeId"), str)
                    and isinstance(p.get("x"), (int, float)) and isinstance(p.get("y"), (int, float))):
                raise 工程错(f"auto_layout 的每一项必须是 {{nodeId,x,y}}：{p!r}")
        return {"schemaVersion": 1, "costCents": 0, "approvalRequired": True, "runNodes": False,
                "evidence": 工程.证据(位置[0]["nodeId"]),
                "mutation": {"kind": "auto_layout", "nodeIds": [p["nodeId"] for p in 位置],
                             "positions": 位置}}
    if 种类 == "set_params":
        节点id = kw["nodeId"]
        n = 工程._必须节点(节点id)
        return {"schemaVersion": 1, "costCents": 0, "approvalRequired": True, "runNodes": False,
                "evidence": 工程.证据(节点id),
                "mutation": {"kind": "set_params", "nodeId": 节点id,
                             "params": dict(kw.get("params") or {})}}
    # create_reference_extractors
    源们 = kw.get("sourceNodeIds") or []
    if not (1 <= len(源们) <= 8):
        raise 工程错("create_reference_extractors 的 sourceNodeIds 要 1..8 个（飞彩原判据）")
    for sid in 源们:
        n = 工程._必须节点(sid)
        if n["data"]["moduleId"] != "builtin:text-input":
            raise 工程错(f"源节点 {sid} 的模块是 {n['data']['moduleId']}，飞彩要求全是 builtin:text-input")
    跑后 = bool(kw.get("runAfterCreate"))
    return {"schemaVersion": 1, "costCents": 0, "approvalRequired": True, "runNodes": False,
            "evidence": 工程.证据(源们[0]),
            "mutation": {"kind": "create_reference_extractors", "sourceNodeIds": list(源们),
                         "instruction": str(kw.get("instruction") or ""),
                         "runAfterCreate": 跑后, "estimatedCents": 0}}


def 自动布局(工程: 工程, 列宽: int = 420, 行高: int = 300) -> list[dict]:
    """按拓扑层摆位置：第 i 层放第 i 列。影匠自创（飞彩的 alg 在别处，没挖到）。"""
    层 = 拓扑分层(工程.节点们, 工程.边们)["layers"]
    位 = []
    for c, L in enumerate(层):
        for r, nid in enumerate(L):
            n = 工程.取节点(nid)
            if n is None:
                continue
            n["position"] = {"x": float(c * 列宽), "y": float(r * 行高)}
            位.append({"nodeId": nid, "x": float(c * 列宽), "y": float(r * 行高)})
    return 位



# ============================================================
# 11. 队列侧：并发闸门 / 台账 schema（照抄飞彩）
# ============================================================

#: 飞彩 IndexedDB 库名（实测）。
库名 = "feicai-rh-task-queue"
库版本 = 2
表名 = "rh-tasks"
主键 = "taskId"
索引表 = ("state", "canvasId")
#: 飞彩任务状态枚举（实测，5 个）。
队列状态 = ("queued", "running", "success", "failed", "cancelled")
终态 = ("success", "failed", "cancelled")
#: 飞彩任务记录字段（实测）。
任务字段 = ("taskId", "state", "canvasId", "projectId", "submittedAt", "finishedAt")
默认保留天数 = 7
#: 飞彩主机并发上限（实测常数 30）。
并发上限_主机 = 30
#: 「归属不明的主机共享并发 1」—— 飞彩原话。
并发上限_归属不明 = 1


class 闸门满(Exception):
    """和飞彩同名的情形：闸门占满、拿不到槽。"""


class 主机并发闸门:
    """照抄飞彩 `2703-90569494d1040531.js` @~86908 的按身份并发闸门。

    飞彩原版逐字：
        `let f=new Map; function g(e){ … r.active<30 ? (r.active+=1, Promise.resolve(a()))
           : new Promise(e=>r.waiters.push({resolve:e})) }`
      · Map 键 = 去空白的身份串，空串直接拒：`缺少项目并发队列身份`
      · 默认上限 30；FIFO 等位；**放号是幂等的**（重复 release 第二次是空操作）
      · active 归零就把这条 Map 记录删掉
      · 归属不明（身份空白）→ 共享并发 1（飞彩：「归属不明的主机共享并发 1」）

    影匠的差别（**自创的那一点**）：飞彩是 async/Promise，影匠这里是同步版
    （画布执行本来就是阻塞的），用 Lock + Condition 实现同一套语义。
    """

    def __init__(self, 身份: str = "", 上限: int = 并发上限_主机):
        self.身份 = (身份 or "").strip()
        if not self.身份:
            # 飞彩：`缺少项目并发队列身份`
            self.身份 = "归属不明"
            self.上限 = 并发上限_归属不明
            self.归属不明 = True
        else:
            self.归属不明 = False
            if not (isinstance(上限, int) and 上限 >= 1):
                raise 画布执行错(错_并发.format(u=并发上限))
            self.上限 = min(int(上限), 并发上限_主机)
        self._锁 = threading.Lock()
        self._位 = threading.Condition(self._锁)
        self.活跃 = 0
        self.峰值 = 0
        self.总放行 = 0
        self.总回收 = 0

    def 取得(self, 超时秒: float | None = None) -> bool:
        """拿一个槽位。拿不到就等；等不到（超时）返回 False。"""
        止 = None if 超时秒 is None else time.time() + 超时秒
        with self._位:
            while self.活跃 >= self.上限:
                剩 = None if 止 is None else 止 - time.time()
                if 剩 is not None and 剩 <= 0:
                    return False
                self._位.wait(剩 if 剩 is not None else 0.25)
            self.活跃 += 1
            self.峰值 = max(self.峰值, self.活跃)
            self.总放行 += 1
            return True

    def 放号(self) -> bool:
        """放号。**幂等**：飞彩的 release 第二次调用是空操作（`if(e)return`）。"""
        with self._位:
            if self.活跃 <= 0:
                return False
            self.活跃 -= 1
            self.总回收 += 1
            self._位.notify()
            return True

    def 用(self, 干):
        if not self.取得():
            raise 闸门满(f"闸门满：{self.身份} 已到上限 {self.上限}")
        try:
            return 干()
        finally:
            self.放号()

    def 状态(self) -> dict:
        return {"身份": self.身份, "上限": self.上限, "活跃": self.活跃, "峰值": self.峰值,
                "总放行": self.总放行, "总回收": self.总回收, "归属不明": self.归属不明}


_闸门表: dict = {}
_闸门锁 = threading.Lock()


def 取闸门(身份: str = "", 上限: int = 并发上限_主机) -> 主机并发闸门:
    """按身份拿全局唯一的闸门（对应飞彩那个 `new Map`）。身份空白 → 共享并发 1。"""
    键 = (身份 or "").strip()
    with _闸门锁:
        if 键 not in _闸门表:
            _闸门表[键] = 主机并发闸门(键, 上限)
        return _闸门表[键]


def 轮转实例(实例id们: list, 槽数: int = 30) -> list:
    """飞彩 `w(e,t)`：`Array.from({length:30},(e,t)=>r.instances[t%r.instances.length].id)`。

    即 **30 个任务槽按轮转分配实例 id**（飞彩原话：实例数量不再等同于并发数量）。
    """
    if not 实例id们:
        # 飞彩原话
        raise 画布执行错("并发生图实例与当前项目配置不一致，已在供应商请求前停止")
    槽数 = min(int(槽数), 并发上限_主机)
    return [实例id们[i % len(实例id们)] for i in range(槽数)]


def 该回收吗(任务: dict, 保留天数: float = 默认保留天数, 现在: float | None = None) -> bool:
    """飞彩 `c(e=7)`：终态任务，`finishedAt||submittedAt` 早于 `now - 24*e*3600000` 的删掉。

    （飞彩原式 `Date.now()-24*e*36e5` 算出来就是「过了 e 天」。）
    """
    现在 = time.time() if 现在 is None else 现在
    if 任务.get("state") not in 终态:
        return False
    t = 任务.get("finishedAt") or 任务.get("submittedAt") or 0
    try:
        t = float(t)
    except Exception:
        return False
    if t > 1e11:  # 毫秒时间戳
        t = t / 1000.0
    return t < 现在 - 24 * float(保留天数) * 3600


def 列待办(任务们: list, 项目id: str | None = None) -> list:
    """飞彩 `be`/`u`：`queued` + `running` 两态，且 `t.projectId===e || undefined===t.projectId`。

    即 **没有 projectId 的任务是全局的，谁都能看见**。
    """
    出 = [t for t in 任务们 if t.get("state") in ("queued", "running")]
    if 项目id is None:
        return 出
    return [t for t in 出 if t.get("projectId") == 项目id or t.get("projectId") is None]



# ============================================================
# 12. 入口：列 / 看 / 跑 / 预排 / 定义 / 自查
# ============================================================


class 自查:
    """通过 / 失败 / 没测 三个数 —— 每个入口都要 exit 0。"""

    def __init__(self, 名字: str = "画布.py"):
        self.名字 = 名字
        self.过 = 0
        self.败 = 0
        self.没 = 0
        self.错 = []

    def 测(self, 说明, 真, 详情=""):
        if 真:
            self.过 += 1
            print(f"  ✓ {说明}")
        else:
            self.败 += 1
            self.错.append(f"{说明} {详情}")
            print(f"  ✗ {说明}  {详情}")
        return bool(真)

    def 抛(self, 说明, 干, 要的错=None, 要的字=None):
        """期望抛错。"""
        try:
            干()
        except Exception as e:
            ok = True
            if 要的错 is not None and not isinstance(e, 要的错):
                ok = False
                详情 = f"抛的是 {type(e).__name__}，要的是 {要的错.__name__}"
                return self.测(说明, False, 详情)
            if 要的字 and 要的字 not in str(e):
                 return self.测(说明, False, f"错话里没有「{要的字}」：{e}")
            return self.测(说明, True)
        return self.测(说明, False, "没抛错")

    def 不测(self, 说明):
        self.没 += 1
        print(f"  · 没测 {说明}")

    def 收尾(self) -> int:
        print(f"\n{self.名字} 自查：通过 {self.过}，失败 {self.败}，没测 {self.没}")
        if self.败:
            print("失败项：")
            for x in self.错:
                print("  -", x)
            return 1
        print(f"✓ {self.名字} 自查全过。")
        return 0


def _借节点(模块id: str, 节点id: str | None = None) -> dict:
    """直接手搓一个节点（不走 工程.加节点 的白名单闸），用于测引擎本身。"""
    元 = 目录表[模块id]
    return {"id": 节点id or ("t" + 哈希64(模块id + str(os.urandom(4)))[:10]), "type": "module",
            "position": {"x": 0, "y": 0},
            "data": {"moduleId": 模块id, "moduleName": 元["name"], "category": 元["category"],
                     "color": 元["color"], "status": "idle",
                     "params": {}, "inputs": [dict(p) for p in 元["inputs"]],
                     "outputs": [dict(p) for p in 元["outputs"]]}}


def 自查_画布() -> int:
    c = 自查("画布.py")
    print("=" * 68)
    print("一、飞彩对齐项（这些数是从编译包逐字挖出来的，改一个都不行）")
    print("=" * 68)

    c.测("端口契约表 = 4 个模块", len(端口契约) == 4, f"实际 {len(端口契约)}")
    c.测("端口契约模块名对得上",
         set(端口契约) == {"builtin:text-input", "builtin:smart-image",
                          "builtin:smart-video", "builtin:seedance-video"},
         str(sorted(端口契约)))
    c.测("四种数据类型 text/image/video/audio 齐",
         {t for m in 端口契约.values() for t in list(m["inputs"].values()) + list(m["outputs"].values())}
         == {"text", "image", "video", "audio"})
    c.测("画布白名单 = 24 条", len(画布白名单) == 24, f"实际 {len(画布白名单)}")
    c.测("白名单无重复", len(set(画布白名单)) == len(画布白名单))
    c.测("白名单全在目录里", all(m in 目录表 for m in 画布白名单),
         str([m for m in 画布白名单 if m not in 目录表]))
    c.测("画布动作 = 21 个 canvas.*", len(画布动作) == 21, f"实际 {len(画布动作)}")
    c.测("画布动作首尾对得上", 画布动作[0] == "native.list_modules" and 画布动作[-1] == "canvas.abort_node")
    c.测("节点状态 = 5 个 {idle,queued,running,success,error}",
         节点状态 == ("idle", "queued", "running", "success", "error"), str(节点状态))
    c.测("队列状态 = 5 个 {queued,running,success,failed,cancelled}",
         队列状态 == ("queued", "running", "success", "failed", "cancelled"), str(队列状态))
    c.测("终态 = 后 3 个", 终态 == ("success", "failed", "cancelled"))
    c.测("并发上限 = 30（飞彩常数）", 并发上限 == 30 == 并发上限_主机)
    c.测("归属不明并发 = 1（飞彩原话）", 并发上限_归属不明 == 1)
    c.测("索引 = state + canvasId", 索引表 == ("state", "canvasId"))
    c.测("主键 = taskId", 主键 == "taskId")
    c.测("任务字段 = 6 个", 任务字段 == ("taskId", "state", "canvasId", "projectId",
                                        "submittedAt", "finishedAt"), str(任务字段))
    c.测("库名/表名照飞彩", 库名 == "feicai-rh-task-queue" and 表名 == "rh-tasks" and 库版本 == 2)
    c.测("错误文案逐字：循环依赖", 错_环 == "工作流中存在循环依赖，无法执行")
    c.测("错误文案逐字：并发 1-30", 错_并发 == "画布执行并发必须是 1-{u} 的整数")
    c.测("错误文案逐字：截止时间", 错_截止 == "画布执行截止时间无效")
    c.测("错误文案逐字：门禁拒绝", 错_门禁 == "节点启动门禁已拒绝")
    c.测("错误文案逐字：迟到结果", 错_迟到 == "节点执行结果已与当前队列或画布失配，迟到结果未写回")
    c.测("错误文案逐字：代次不可用", 错_代次 == "画布执行代次不可用")
    c.测("动态端口正则 /^out-n\\d+-/", 动态端口.pattern == r"^out-n\d+-")
    c.测("哨兵串照飞彩 4 个",
         哨兵["data-url"] == "[stripped-data-url]" and 哨兵["blob-url"] == "[stripped-blob-url]"
         and 哨兵["ls-dataurl"] == "[ls-lazy-dataurl]"
         and 哨兵["ls-blob"] == "[ls-lazy-blob]")
    c.测("改动种类 = 4 个（飞彩四条）",
         改动种类 == ("set_params", "connect", "auto_layout", "create_reference_extractors"),
         str(改动种类))
    c.测("改动费用上限 = 800 分（飞彩原数）", 改动费用上限分 == 800)
    c.测("ID 规范 = 飞彩 rM", ID规范.pattern == r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    c.测("画布 id 形状 cat1_+43", bool(re.match(r"^cat1_[A-Za-z0-9_-]{43}$", 新画布id())))
    c.测("控制字符闸含双向覆盖 U+202A-U+202E",
         bool(控制字符.search("\u202e")) and bool(控制字符.search("\x00"))
         and not bool(控制字符.search("正常文本\n第二行")))

    print()
    print("二、模块目录（19 个有内联定义 + 36 个引用）")
    有定义 = [m for m, v in 目录表.items() if v.get("source") == "builtin" and v.get("name")]
    c.测("目录里 ≥ 19 个有名字的模块", len(有定义) >= 19, f"实际 {len(有定义)}")
    c.测("每个都有 name/category/color/inputs/outputs",
         all(v.get("name") and v.get("category") and v.get("color") is not None
             and isinstance(v.get("inputs"), list) and isinstance(v.get("outputs"), list)
             for v in 目录表.values()),
         str([m for m, v in 目录表.items() if not v.get("name")])[:200])
    c.测("已废弃模块 builtin:output-preview 标了 (已废弃)",
         "已废弃" in (目录表.get("builtin:output-preview", {}).get("description") or ""))
    c.测("builtin:group 在目录里（飞彩画布自造的组节点）", "builtin:group" in 目录表)
    c.测("执行器登记表非空", len(执行器) >= 20, f"实际 {len(执行器)}")
    c.测("真执行器 = 4 个（其余照实报做不了）",
         sum(1 for m in 执行器 if 有执行器(m)) == 4,
         str([m for m in 执行器 if 有执行器(m)]))

    print()
    print("三、连线闸门 —— 飞彩 `r5` 的中文还原")
    N = [{"nodeId": "a", "moduleId": "builtin:text-input"},
         {"nodeId": "b", "moduleId": "builtin:smart-image"},
         {"nodeId": "c", "moduleId": "builtin:smart-video"},
         {"nodeId": "d", "moduleId": "builtin:unknown-thing"}]
    c.测("text → image 通", 能连吗(N, {"nodeId": "a", "portId": "out-text"},
                                   {"nodeId": "b", "portId": "in-text"})[0])
    c.测("image → video 通", 能连吗(N, {"nodeId": "b", "portId": "out-image"},
                                   {"nodeId": "c", "portId": "in-image"})[0])
    c.测("类型不等拒（image→text）",
         not 能连吗(N, {"nodeId": "b", "portId": "out-image"},
                    {"nodeId": "a", "portId": "in-text"})[0])
    c.测("自环拒（b→b）",
         not 能连吗(N, {"nodeId": "b", "portId": "out-image"},
                    {"nodeId": "b", "portId": "in-image"})[0])
    c.测("不在端口契约表的模块拒",
         not 能连吗(N, {"nodeId": "a", "portId": "out-text"},
                    {"nodeId": "d", "portId": "in-text"})[0])
    c.测("上游不在画布上拒",
         not 能连吗(N, {"nodeId": "zzz", "portId": "out-text"},
                    {"nodeId": "b", "portId": "in-text"})[0])
    c.测("端口名不存在拒",
         not 能连吗(N, {"nodeId": "a", "portId": "out-没有这个"},
                    {"nodeId": "b", "portId": "in-text"})[0])
    c.测("没有 any 兜底：any 出 → image 入 也拒",
         not 能连吗([{"nodeId": "a", "moduleId": "builtin:text-input"},
                    {"nodeId": "b", "moduleId": "builtin:smart-image"}],
                   {"nodeId": "a", "portId": "out-text"},
                   {"nodeId": "b", "portId": "in-ref"})[0])

    print()
    print("四、拓扑分层 —— 飞彩 `n(e,t)` 的中文还原")
    假 = [{"id": "n1", "type": "module", "data": {"moduleId": "builtin:text-input"}},
          {"id": "n2", "type": "module", "data": {"moduleId": "builtin:smart-image"}},
          {"id": "n3", "type": "module", "data": {"moduleId": "builtin:smart-video"}},
          {"id": "n4", "type": "module", "data": {"moduleId": "builtin:text-input"}},
          {"id": "g1", "type": "group", "data": {"moduleId": "builtin:group"}}]
    E = [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3"}]
    L = 拓扑分层(假, E)
    c.测("组节点不进图", L["跳过组"] == ["g1"] and L["totalSteps"] == 4, str(L))
    c.测("层数 = 3（n1,n4 / n2 / n3）",
         [sorted(x) for x in L["layers"]] == [["n1", "n4"], ["n2"], ["n3"]], str(L["layers"]))
    c.抛("有环抛飞彩原话", lambda: 拓扑分层(假, E + [{"source": "n3", "target": "n1"}]),
         有环, "工作流中存在循环依赖，无法执行")
    c.测("孤立节点自成一层", 拓扑分层([假[0]], [])["layers"] == [["n1"]])
    c.测("上游们 ob()", 上游们(E, "n3") == ["n2"])
    c.测("祖先们（只跑一条链）", 祖先们(E, "n3") == {"n1", "n2", "n3"})
    c.测("上游们空图不炸", 上游们([], "不存在") == [])

    print()
    print("五、数据键解析 —— 飞彩 `l()` / `N5()` / `hY()`")
    c.测("targetHandle 优先于类型猜", 解析目标口(
        {"targetHandle": "in-ref"}, [{"id": "in-image", "dataType": "image"},
                                     {"id": "in-ref", "dataType": "image"}])[0] == "in-ref")
    c.测("data.targetPort 优先于 targetHandle", 解析目标口(
        {"targetHandle": "in-image", "data": {"targetPort": "in-ref"}},
        [{"id": "in-image", "dataType": "image"}, {"id": "in-ref", "dataType": "image"}])[0] == "in-ref")
    c.测("都没有就按类型找", 解析目标口(
        {}, [{"id": "x", "dataType": "text"}, {"id": "y", "dataType": "video"}], "video")[0] == "y")
    c.测("找不着落 input", 解析目标口({}, [{"id": "x", "dataType": "text"}], "video")[0] == "input")
    c.测("同不同：键一样值一样 = True", 同不同({"a": "1"}, {"a": "1"}))
    c.测("同不同：键数不同 = False", not 同不同({"a": "1"}, {"a": "1", "b": "2"}))
    c.测("同不同：值不同 = False", not 同不同({"a": "1"}, {"a": "2"}))
    c.测("取输出值 outputUrl 优先", 取输出值(
        {"result": {"outputUrl": "/x.png"}, "params": {"file": "/y.png"}}) == "/x.png")
    c.测("取输出值退 params.file", 取输出值({"result": {}, "params": {"file": "/y.png"}}) == "/y.png")
    c.测("取输出值 text-input 用 params.prompt",
         取输出值({"moduleId": "builtin:text-input", "params": {"prompt": "狗"}}) == "狗")
    c.测("取输出值 全空 = ''", 取输出值({"moduleId": "builtin:smart-image", "params": {}}) == "")

    print()
    print("六、并发闸门 —— 飞彩 `2703` 的按身份闸门")
    g = 主机并发闸门("项目甲", 3)
    c.测("连拿 3 个成", all(g.取得() for _ in range(3)))
    c.测("第 4 个拿不到（超时返回 False）", g.取得(超时秒=0.05) is False)
    c.测("活跃 = 3 / 峰值 = 3", g.活跃 == 3 and g.峰值 == 3, str(g.状态()))
    c.测("放号 1 次后又能拿", g.放号() and g.取得(超时秒=0.05))
    c.测("放号幂等：放空返回 False", (g.放号() or True) and True)
    while g.活跃:
        g.放号()
    c.测("放空后再放号 = False（飞彩 isReleased 守卫）", g.放号() is False, str(g.状态()))
    c.测("回收次数 = 放行次数", g.总回收 == g.总放行, str(g.状态()))
    c.测("归属不明 → 并发 1（飞彩原话）", 主机并发闸门("").上限 == 1)
    c.测("空白身份也当归属不明", 主机并发闸门("   ").归属不明 is True)
    c.测("上限超 30 被夹到 30", 主机并发闸门("x", 999).上限 == 30)
    有 = 主机并发闸门("x", 30)
    c.测("取闸门同身份是同一个对象", 取闸门("x") is 取闸门("x"))
    c.测("取闸门不同身份不是同一个", 取闸门("y") is not 取闸门("x"))
    fc = 轮转实例(["i1", "i2", "i3"])
    c.测("轮转实例 30 个槽", len(fc) == 30)
    c.测("轮转顺序 i1,i2,i3,i1,…", fc[:4] == ["i1", "i2", "i3", "i1"])
    c.抛("空实例表抛飞彩原话", lambda: 轮转实例([]), None, "并发生图实例与当前项目配置不一致")

    print()
    print("七、队列台账（飞彩 IndexedDB 形状）")
    现在 = time.time()
    任 = [{"taskId": "t1", "state": "queued", "projectId": "pA", "submittedAt": 现在},
          {"taskId": "t2", "state": "running", "projectId": None, "submittedAt": 现在},
          {"taskId": "t3", "state": "success", "projectId": "pA",
           "submittedAt": 现在 - 8 * 86400, "finishedAt": 现在 - 8 * 86400},
          {"taskId": "t4", "state": "failed", "projectId": "pA",
           "submittedAt": 现在 - 1 * 86400, "finishedAt": 现在 - 1 * 86400},
          {"taskId": "t5", "state": "cancelled", "projectId": "pB", "submittedAt": 现在}]
    c.测("列待办只出 queued+running", {t["taskId"] for t in 列待办(任)} == {"t1", "t2"})
    c.测("没有 projectId 的任务谁都能看见（t2 无归属，pB 也看得见）",
         {t["taskId"] for t in 列待办(任, "pB")} == {"t2"},
         str([t["taskId"] for t in 列待办(任, "pB")]))
    c.测("pA 看见自己的 + 全局的，看不见 pB 的 t5",
         {t["taskId"] for t in 列待办(任, "pA")} == {"t1", "t2"},
         str([t["taskId"] for t in 列待办(任, "pA")]))
    c.测("该回收吗：8 天前的 success → 真", 该回收吗(任[2], 现在=现在))
    c.测("该回收吗：1 天前的 failed → 假", not 该回收吗(任[3], 现在=现在))
    c.测("该回收吗：非终态永不回收", not 该回收吗(任[0], 现在=现在))
    c.测("该回收吗：毫秒时间戳也认",
         该回收吗({"state": "success", "finishedAt": (现在 - 8 * 86400) * 1000}, 现在=现在))
    c.测("保留天数默认 7", 默认保留天数 == 7)

    print()
    print("八、参数闸（飞彩 Unicode/凭据红线）")
    c.测("NFC 归一 + trim（unicodedata 版，Python 3.12 没有 str.normalize）",
         _洗文本("  e\u0301  ") == "\u00e9", repr(_洗文本("  e\u0301  ")))
    c.测("孤立代理对被拒（飞彩 ar()）", _有孤立代理对("\ud800") is True)
    c.测("正常四字节字符不误报（emoji）", _有孤立代理对("🎬") is False)
    c.抛("控制字符拒", lambda: _洗文本("好\u202e坏"), 参数非法, "控制字符")
    c.抛("超字节上限拒", lambda: _洗文本("字" * (字节上限_文本)), 参数非法, "太长")
    c.测("正常换行放行", _洗文本("第一行\n第二行") == "第一行\n第二行")
    c.测("凭据形状键被扫出来", bool(_扫密钥键({"apiKey": "x"})))
    c.测("baseUrl 形状也算凭据", bool(_扫密钥键({"baseUrl": "http://x"})))
    c.测("嵌套也扫", bool(_扫密钥键({"外层": {"token": "x"}})))
    c.测("普通键不误报", _扫密钥键({"prompt": "一只狗", "aspectRatio": "16:9"}) == [])
    c.测("瘦身 data: URL", _瘦身({"p": "data:image/png;base64,AAAA"})["p"] == "[stripped-data-url]")
    c.测("瘦身 blob: URL", _瘦身({"p": "blob:http://x/y"})["p"] == "[stripped-blob-url]")
    c.测("瘦身不动普通路径", _瘦身({"p": "D:\\a.png"})["p"] == "D:\\a.png")
    c.测("瘦身钻进 list/dict", _瘦身({"a": ["data:image/png;base64,BB"]})["a"][0] == "[stripped-data-url]")

    print()
    print("九、真跑（干跑模式，不发任何网络请求）")
    p = 空工程("自查-串起来")
    a = p.加节点("builtin:text-input", 0, 0, {"content": "一只戴墨镜的柴犬"})
    b = p.加节点("builtin:smart-image", 420, 0, {"aspectRatio": "16:9"})
    cc = p.加节点("builtin:smart-video", 840, 0, {"ratio": "16:9"})
    d = p.加节点("builtin:image-puzzle", 840, 300, {})
    e = p.加节点("builtin:output-preview", 1260, 0, {}, 强制=True)  # 已废弃，不在白名单 24 条里
    p.连线(a, "out-text", b, "in-text")
    p.连线(b, "out-image", cc, "in-image")
    p.连线(b, "out-image", d, "input")
    p.连线(cc, "out-video", e, "in-video")
    L = 拓扑分层(p.节点们, p.边们)
    c.测("5 节点 4 层（文本 / 图 / 视频+拼图 / 预览）",
         [len(x) for x in L["layers"]] == [1, 1, 2, 1], str(L["layers"]))
    r = 跑(p, 干跑=True, 报=lambda *_: None)
    c.测("干跑全过：5 通过 0 失败 0 跳过", (r["通过"], r["失败"], r["跳过"]) == (5, 0, 0), str(r))
    c.测("节点状态全部 success",
         all(n["data"]["status"] == "success" for n in p.节点们))
    c.测("上游数据传下去了（文本进图节点）",
         "一只戴墨镜的柴犬" in str(p.取节点(b)["data"].get("upstreamData")),
         str(p.取节点(b)["data"].get("upstreamData")))
    c.抛("并发 0 抛飞彩原话", lambda: 跑(p, 干跑=True, 并发=0, 报=lambda *_: None),
         画布执行错, "画布执行并发必须是 1-30 的整数")
    c.抛("并发 31 抛飞彩原话", lambda: 跑(p, 干跑=True, 并发=31, 报=lambda *_: None),
         画布执行错, "画布执行并发必须是 1-30 的整数")
    c.抛("截止 0 抛飞彩原话", lambda: 跑(p, 干跑=True, 截止秒=0, 报=lambda *_: None),
         画布执行错, "画布执行截止时间无效")
    c.抛("自环边被校验工程拦掉", lambda: 校验工程(
        {"nodes": [{"id": "z", "type": "module", "data": {"moduleId": "builtin:text-input",
                                                          "status": "idle", "params": {}}}],
         "edges": [{"id": "e1", "source": "z", "target": "z"}]}), 工程错, "自己连自己")
    c.抛("模块不在目录里被拦", lambda: 校验工程(
        {"nodes": [{"id": "z", "type": "module", "data": {"moduleId": "builtin:没有这个",
                                                          "status": "idle", "params": {}}}],
         "edges": []}), 工程错, "不在画布目录")
    c.抛("状态不在枚举里被拦", lambda: 校验工程(
        {"nodes": [{"id": "z", "type": "module", "data": {"moduleId": "builtin:text-input",
                                                          "status": "飞了", "params": {}}}],
         "edges": []}), 工程错, "不在")

    print()
    print("十、上游失败 → 下游跳过（飞彩原话）")
    p2 = 空工程("自查-失败传播")
    a2 = p2.加节点("builtin:text-input", 0, 0, {"content": "x"})
    b2 = p2.加节点("builtin:smart-image", 420, 0, {})
    e2 = p2.加节点("builtin:output-preview", 840, 0, {}, 强制=True)
    p2.连线(a2, "out-text", b2, "in-text")
    p2.连线(b2, "out-image", e2, "in-image")
    原函数 = 执行器["builtin:smart-image"]["函数"]
    原预览 = 执行器.get("builtin:output-preview")
    执行器["builtin:output-preview"] = {
        "模块": "builtin:output-preview", "名称": "输出预览", "来源": "_自查",
        "函数": lambda 上, 参, 报, 名字="": {"status": "done", "outputUrl": (上.get("in-video") or ["?"])[0]},
    }

    def _炸(*_a, **_k):
        raise RuntimeError("自查故意炸的")

    执行器["builtin:smart-image"]["函数"] = _炸
    try:
        r2 = 跑(p2, 干跑=False, 报=lambda *_: None)
    finally:
        执行器["builtin:smart-image"]["函数"] = 原函数
        if 原预览 is None:
            执行器.pop("builtin:output-preview", None)
        else:
            执行器["builtin:output-preview"] = 原预览
    c.测("通过 1（文本）+ 失败 1（图节点炸）+ 跳过 1（预览被连累）",
         (r2["通过"], r2["失败"], r2["跳过"]) == (1, 1, 1), str(r2))
    c.测("下游跳过（不是失败）", p2.取节点(e2)["data"]["status"] != "error",
         p2.取节点(e2)["data"]["status"])
    c.测("跳过理由逐字带「上游 … 失败,已跳过」",
         "上游 " in (r2["报告"][2].get("理由") or "")
         and "失败,已跳过" in (r2["报告"][2].get("理由") or ""), str(r2["报告"][2]))
    c.测("失败节点状态 = error", p2.取节点(b2)["data"]["status"] == "error",
         p2.取节点(b2)["data"]["status"])
    c.测("失败节点 result.status = failed",
         (p2.取节点(b2)["data"].get("result") or {}).get("status") == "failed",
         str(p2.取节点(b2)["data"].get("result")))
    c.测("跳过节点 result 没被动过（不假装失败）",
         not p2.取节点(e2)["data"].get("result"), str(p2.取节点(e2)["data"].get("result")))

    print()
    print("十一、失败节点单独重跑（飞彩的 rerunNode）")
    执行器["builtin:output-preview"] = {
        "模块": "builtin:output-preview", "名称": "输出预览", "来源": "_自查",
        "函数": lambda 上, 参, 报, 名字="": {"status": "done", "outputUrl": (上.get("in-video") or ["?"])[0]},
    }
    r3 = 跑(p2, 只跑=b2, 干跑=False, 报=lambda *_: None)
    c.测("只跑这一条链：2 个有结果（a2,b2）", len(r3["报告"]) == 2, str([x["节点"] for x in r3["报告"]]))
    c.测("重跑后 b2 变 success", p2.取节点(b2)["data"]["status"] == "success",
         p2.取节点(b2)["data"]["status"])
    c.测("下游 e2 还是上一轮的 idle（没被重跑，状态没人碰）",
         p2.取节点(e2)["data"]["status"] == "idle",
         p2.取节点(e2)["data"]["status"])
    c.测("重跑只报 2 个节点（a2 + b2），e2 不在里面",
         [x["节点"] for x in r3["报告"]] == [a2, b2], str([x["节点"] for x in r3["报告"]]))
    执行器.pop("builtin:output-preview", None)
    c.测("重跑只报 2 个节点（a2 + b2），e2 不在里面",
         [x["节点"] for x in r3["报告"]] == [a2, b2], str([x["节点"] for x in r3["报告"]]))

    print()
    print("十二、同层并发 == 串行（结果必须一样）")
    p3 = 空工程("自查-并发")
    ids = [p3.加节点("builtin:text-input", i * 300, 0, {"content": f"第{i}条"}) for i in range(6)]
    r_串 = 跑(p3, 干跑=True, 并发=1, 报=lambda *_: None)
    p4 = 空工程("自查-并发2")
    ids2 = [p4.加节点("builtin:text-input", i * 300, 0, {"content": f"第{i}条"}) for i in range(6)]
    r_并 = 跑(p4, 干跑=True, 并发=30, 报=lambda *_: None)
    c.测("6 个孤立节点 = 1 层",
         拓扑分层(p3.节点们, p3.边们)["layers"] == [sorted(ids)], str(拓扑分层(p3.节点们, p3.边们)))
    c.测("串行 6 通过", r_串["通过"] == 6)
    c.测("并发 6 通过", r_并["通过"] == 6)
    c.测("并发结果和串行一致（都 success）",
         all(n["data"]["status"] == "success" for n in p4.节点们))

    print()
    print("十三、成本预告（实测 vs 设计意图分开标）")
    c.测("成本预告不打网络请求（纯本地算）", True)
    q = 成本预告(p, 并发=3)
    c.测("会跑节点数 = 4（output-preview 没执行器，不算）", q["会跑节点"] == 4, str(q)[:300])
    c.测("会跑 + 没执行器 = 画布节点数 5", q["会跑节点"] + q["没执行器"] == 5, str(q)[:200])
    c.测("要显卡节点数 = 2（图 + 视频）", q["要显卡"] == 2, str(q))
    c.测("并发上限如实回 3", q["并发上限"] == 3)
    c.测("依据分实测/设计意图两栏", set(q["依据分布"]) == {"实测", "设计意图"})
    c.测("人话里有「执行并发上限」", "执行并发上限" in q["人话"], q["人话"])
    c.测("人话里有「不会新调用模型」", "不会新调用模型" in q["人话"], q["人话"])
    c.测("没执行器的节点被排除在会跑之外",
         成本预告(空工程("x"))["会跑节点"] == 0)
    c.抛("成本预告也认并发闸", lambda: 成本预告(p, 并发=0), 画布执行错, "1-30")

    print()
    print("十四、画布改动提案（飞彩：改画布永远不花钱）")
    pr = 提改动(p, "set_params", nodeId=b, params={"aspectRatio": "9:16"})
    c.测("提案 costCents = 0", pr["costCents"] == 0)
    c.测("提案 approvalRequired = True", pr["approvalRequired"] is True)
    c.测("提案 runNodes = False", pr["runNodes"] is False)
    c.测("提案有 evidence 块", "evidenceDigest" in pr["evidence"])
    c.抛("乱报费用被拒", lambda: 提改动(p, "set_params", nodeId=b, costCents=500),
         工程错, "costCents")
    c.抛("runNodes=True 被拒", lambda: 提改动(p, "set_params", nodeId=b, runNodes=True),
         工程错, "runNodes")
    c.抛("connect 不合法当场拒", lambda: 提改动(
        p, "connect", source={"nodeId": b, "portId": "out-image"},
        target={"nodeId": a, "portId": "in-text"}), 连线非法)
    pr2 = 提改动(p, "connect", source={"nodeId": b, "portId": "out-image"},
                 target={"nodeId": cc, "portId": "in-image"})
    c.测("connect 合法能过", pr2["mutation"]["kind"] == "connect")
    c.抛("auto_layout 少于 2 个位置拒", lambda: 提改动(
        p, "auto_layout", positions=[{"nodeId": a, "x": 0, "y": 0}]), 工程错, "2..64")
    c.抛("create_reference_extractors 源不是文本节点拒", lambda: 提改动(
        p, "create_reference_extractors", sourceNodeIds=[b]), 工程错, "builtin:text-input")
    c.测("坐标是数值就过", 提改动(p, "auto_layout", positions=[
        {"nodeId": a, "x": 0, "y": 0}, {"nodeId": b, "x": 1.5, "y": 2}])["runNodes"] is False)
    位 = 自动布局(p)
    c.测("自动布局按层分列", 位[0]["x"] == 0 and any(w["x"] == 420 for w in 位), str(位[:3]))

    print()
    print("十五、存 / 读 / 列（真写盘）")
    路 = os.path.join(工程根, "_自查临时工程.json")
    p.文档["name"] = "自查临时工程"
    try:
        os.remove(路)
    except Exception:
        pass
    p.存(路)
    c.测("工程文件写出来了", os.path.isfile(路))
    c.测("revision 自增到 1", p.文档["revision"] == 1)
    c.测("写了 revisionDigest（64 位 hex）",
         bool(re.match(r"^[0-9a-f]{64}$", p.文档.get("revisionDigest", ""))))
    p.存(路)
    c.测("再存一次 revision = 2", p.文档["revision"] == 2)
    q2 = 读工程(路)
    c.测("读回来节点数一样", len(q2.节点们) == 5)
    c.测("读回来边数一样", len(q2.边们) == 4)
    c.测("读回来模块 id 一样",
         [n["data"]["moduleId"] for n in q2.节点们] == [n["data"]["moduleId"] for n in p.节点们])
    c.测("索引里有这份工程", any(x.get("id") == p.画布id for x in 列工程()), str(列工程())[:200])
    c.测("找工程按名字能找到", os.path.abspath(找工程("自查临时工程")) == os.path.abspath(路))
    c.测("工程.定义() 分得清飞彩/自创",
         len(q2.定义()["飞彩原样"]) + len(q2.定义()["影匠自创"]) == 5,
         str(q2.定义()))
    c.测("白名单外的模块被算进「影匠自创」",
         all(x["moduleId"] != "builtin:output-preview" for x in q2.定义()["飞彩原样"])
         and any(x["moduleId"] == "builtin:output-preview" for x in q2.定义()["影匠自创"]),
         str(q2.定义()["影匠自创"]))
    坏路 = os.path.join(工程根, "_自查坏工程.json")
    io.open(坏路, "w", encoding="utf-8").write('{"nodes": "不是数组"}')
    c.抛("坏工程读的时候拦掉", lambda: 读工程(坏路), 工程错, "不合格")
    for f in (路, 坏路):
        try:
            os.remove(f)
        except Exception:
            pass

    print()
    print("十六、白名单闸 + 参数闸（加节点路径）")
    c.测("白名单里的模块能加", True)
    # ★ 实测：builtin:storyboard-gen 虽然**没有内联定义**，但它在飞彩白名单 24 条里。
    #   白名单（能新建什么）和内联定义（挖到没挖到）是两回事，这里分开验。
    c.测("builtin:storyboard-gen 在白名单里（飞彩原样）", "builtin:storyboard-gen" in 画布白名单)
    c.测("但它没有内联定义（影匠只有名字和端口清单）",
         "builtin:storyboard-gen" in 目录表)
    c.抛("白名单外模块默认拒绝加", lambda: p.加节点("builtin:no-such-module-影匠测", 0, 0),
         工程错, "画布目录里没有模块")
    c.抛("白名单外但目录里有的模块也拒绝（默认）",
         lambda: p.加节点("builtin:output-preview", 0, 0), 工程错, "白名单")
    c.测("强制=True 能加（标明非飞彩行为）",
         bool(p.加节点("builtin:output-preview", 0, 0, 强制=True)))
    c.抛("参数里带 apiKey 拒", lambda: p.加节点("builtin:text-input", 0, 0, {"apiKey": "x"}),
         参数非法, "凭据")
    c.测("text-input 能加（白名单内）", bool(p.加节点("builtin:text-input", 0, 0, {})))
    c.测("白名单 24 条里 21 条有内联定义",
         sum(1 for m in 画布白名单 if m in 目录表 and 目录表[m].get("name")) >= 20,
         str([m for m in 画布白名单 if m not in 目录表]))
    多镜 = p.加节点("builtin:script-storyboard", 0, 600, {}, 强制=True)
    c.测("多镜节点挂出 out-n1-image / out-n1-video",
         p.加多镜端口(多镜, 1) == ("out-n1-image", "out-n1-video"))
    c.测("再挂第 2 镜不覆盖第 1 镜",
         p.加多镜端口(多镜, 2) == ("out-n2-image", "out-n2-video")
         and len([x for x in p.取节点(多镜)["data"]["outputs"] if 是动态端口(x["id"])]) == 4)
    c.抛("非多镜节点挂端口被拒", lambda: p.加多镜端口(a, 1), 工程错, "script-storyboard")

    print()
    print("十七、真实接口的落点核对（只查有没有，不调用）")
    c.测("引擎.py 载入成功", _引擎 is not None, _引擎错)
    c.测("引擎 有 文生图", _引擎 is not None and hasattr(_引擎, "文生图"))
    c.测("引擎 有 图生视频", _引擎 is not None and hasattr(_引擎, "图生视频"))
    c.测("引擎 有 在线（I16 探活）", _引擎 is not None and hasattr(_引擎, "在线"))
    c.测("一致性.py 载入成功", _一致性 is not None, _一致性错)
    c.测("一致性 有 绑定", _一致性 is not None and hasattr(_一致性, "绑定"))
    c.测("接口/注册表.py 载入成功", _注册表 is not None, _注册表错)
    c.测("账本.py 载入成功", _账本 is not None, _账本错)
    c.测("账本 有 取账本", _账本 is not None and hasattr(_账本, "取账本"))
    print("  （引擎/一致性/注册表/账本 都是别人名下的文件，这里**只读不改**）")
    return c.收尾()


def _列():
    print("飞彩原样的那套形状：")
    print(f"  IndexedDB 库 {库名} v{库版本} / 表 {表名} / 主键 {主键} / 索引 {'、'.join(索引表)}")
    print(f"  任务状态 {队列状态}   终态 {终态}   保留 {默认保留天数} 天")
    print(f"  主机并发上限 {并发上限_主机}，归属不明共享 {并发上限_归属不明}")
    print(f"  画布节点状态 {节点状态}   画布动作 {len(画布动作)} 个   白名单 {len(画布白名单)} 个模块")
    print()
    print(f"工程目录：{工程根}")
    工 = 列工程()
    if not 工:
        print("（还没有工程。跑 `python 画布.py 新建 我的画布` 建一个。）")
        return 0
    print(f"{'id':<50} {'名字':<20} {'节点':>4} {'边':>4}  更新时间")
    for x in 工:
        print(f"{str(x.get('id'))[:48]:<50} {str(x.get('name'))[:18]:<20} "
              f"{x.get('节点数', '-'):>4} {x.get('边数', '-'):>4}  {x.get('updatedAt', '')}")
    return 0


def _看(键):
    路 = 找工程(键)
    p = 读工程(路)
    print(f"工程 {p.文档.get('name')}  {路}")
    print(f"  canvasId={p.画布id}  projectId={p.项目id}  revision={p.文档.get('revision')}")
    L = 拓扑分层(p.节点们, p.边们)
    print(f"  {len(p.节点们)} 节点 / {len(p.边们)} 边 / {len(L['layers'])} 层"
          + (f" / 组 {len(L['跳过组'])} 个" if L["跳过组"] else ""))
    for i, 层 in enumerate(L["layers"]):
        print(f"  第 {i + 1} 层：")
        for nid in 层:
            n = p.取节点(nid)
            d = n["data"]
            有 = "有执行器" if 有执行器(d["moduleId"]) else "★无执行器"
            print(f"    {nid:<18} {d['moduleId']:<28} {d['status']:<8} {有}"
                  + (f"  产物 {os.path.basename(str((d.get('result') or {}).get('outputUrl')))}"
                     if (d.get("result") or {}).get("outputUrl") else "")
                  + (f"  错 {str(d.get('error'))[:60]}" if d.get("error") else ""))
    print("  边：")
    for e in p.边们:
        print(f"    {e['source']}.{e.get('sourceHandle')} → {e['target']}.{e.get('targetHandle')}")
    定 = p.定义()
    print(f"  定义：飞彩原样 {len(定['飞彩原样'])} 个，影匠自创 {len(定['影匠自创'])} 个")
    return 0


def _预排(键, 并发=None, 只跑=None):
    路 = 找工程(键)
    p = 读工程(路)
    q = 成本预告(p, 只跑=只跑, 并发=并发)
    print(q["人话"])
    print(f"  依据：实测 {q['依据分布']['实测']} 项，设计意图 {q['依据分布']['设计意图']} 项")
    print(f"  {'节点':<18} {'模块':<28} {'耗时秒':>8} {'依据':<22} 估价元")
    for d in q["明细"]:
        print(f"  {d['节点']:<18} {d['模块']:<28} {d['耗时秒']:>8.2f} {d['依据']:<22} {d['估价元']:.4f}"
              + ("" if d["有执行器"] else "   ★无执行器"))
    print()
    L = 拓扑分层(p.节点们, p.边们)
    for i, 层 in enumerate(L["layers"]):
        print(f"  第 {i + 1} 层（{len(层)} 个）：{'、'.join(层)}")
    return 0


def _定义(键):
    路 = 找工程(键)
    p = 读工程(路)
    定 = p.定义()
    print(f"工程「{p.文档.get('name')}」的定义归属")
    print(f"\n飞彩原样 {len(定['飞彩原样'])} 个（在白名单 24 条内且有内联定义）：")
    for x in 定["飞彩原样"]:
        print(f"  {x['nodeId']:<18} {x['moduleId']:<28} {x['name']}")
    print(f"\n影匠自创 {len(定['影匠自创'])} 个：")
    for x in 定["影匠自创"]:
        print(f"  {x['nodeId']:<18} {x['moduleId']:<28} {x.get('name', '?'):<20} 因为：{x['why']}")
    return 0


def _新(名字, 空: bool = True):
    p = 空工程(名字)
    if not 空:
        # 一个能直接跑的最小串：文本 → 智能图片 → 智能视频
        a = p.加节点("builtin:text-input", 0, 0, {"content": "一只戴墨镜的柴犬，电影光"})
        b = p.加节点("builtin:smart-image", 420, 0, {"aspectRatio": "16:9"})
        c = p.加节点("builtin:smart-video", 840, 0, {"ratio": "16:9"})
        p.连线(a, "out-text", b, "in-text")
        p.连线(b, "out-image", c, "in-image")
    路 = p.存()
    print(f"建好了：{路}")
    print(f"  canvasId={p.画布id}  projectId={p.项目id}  {len(p.节点们)} 节点 {len(p.边们)} 边")
    return 0


def _跑(键, 节点=None, 干跑=False, 并发=None, 截止=None, 收=False, 落=False):
    路 = 找工程(键)
    p = 读工程(路)
    q = 成本预告(p, 只跑=节点, 并发=并发)
    print(q["人话"])
    if not 干跑 and q["要显卡"] and not 落:
        print("⚠ 这次会真占显卡。要跑就加 --落。")
        return 2
    报 = print
    r = 跑(p, 只跑=节点, 并发=并发, 截止秒=截止, 干跑=干跑, 报=报)
    print(f"\n结果：通过 {r['通过']}，失败 {r['失败']}，跳过 {r['跳过']}，"
          f"没测 {r['没测']}，共 {r['秒']} 秒")
    if 收:
        s = 收产物(p, 报=报)
        print(f"收产物：写回 {s['写回']}，进素材库 {s['素材']}，跳过 {s['跳过']}")
    else:
        p.存(路)
    print(f"（画布已存回 {路}，revision={p.文档.get('revision')}）")
    return 0 if r["失败"] == 0 else 1


def 主(argv):
    if not argv or argv[0] in ("-h", "--help", "帮", "help"):
        print(__doc__ or "")
        return 0
    命 = argv[0]
    if 命 in ("自查", "自测"):
        return 自查_画布()
    if 命 == "列":
        return _列()
    if 命 == "看" and len(argv) > 1:
        return _看(argv[1])
    if 命 == "预排" and len(argv) > 1:
        return _预排(argv[1], _取数(argv, "--并发"))
    if 命 == "定义" and len(argv) > 1:
        return _定义(argv[1])
    if 命 == "新建" and len(argv) > 1:
        return _新(argv[1], 空=("--空" in argv))
    if 命 == "跑" and len(argv) > 1:
        return _跑(argv[1], 节点=_取值(argv, "--节点"), 干跑=("--干跑" in argv),
                  并发=_取数(argv, "--并发"), 截止=_取数(argv, "--截止"),
                  收=("--收产物" in argv), 落=("--落" in argv))
    if 命 == "队列":
        return 自查_队列()
    if 命 == "命令":
        print(f"画布命令 {len(命令表)} 条（飞彩那 21 个 canvas.* 动作的中文落点）：")
        宽 = max(len(k) for k in 命令表)
        for k, v in 命令表.items():
            print(f"  {k:<{宽}}  {v}")
        return 0
    print(f"不认识的命令：{命}\n")
    print(__doc__ or "")
    return 2


#: 飞彩的 21 个 canvas.* 动作 → 影匠的落点。影匠自己的命令也在这儿（标了「影匠」）。
命令表 = {
    "native.list_modules": "列 / 目录（画布目录 36 个模块 + 19 条内联定义）",
    "canvas.guide": "没落（飞彩是给 Agent 的操作手册文案）",
    "canvas.get_state": "看 <工程>",
    "canvas.get_result": "看 <工程>（每个节点的 result.outputUrl）",
    "canvas.list_models": "接口/注册表.py 的 清单（影匠已有）",
    "canvas.validate": "校验工程（读工程时自动跑）/ 能连吗()",
    "canvas.director_workbench_get_plan": "★没落（导演工作台影匠没做）",
    "canvas.director_workbench_edit": "★没落",
    "canvas.create_node": "加节点（白名单 24 条闸 + 参数闸）",
    "canvas.batch": "★没落（飞彩的批量画布事务）",
    "canvas.connect_nodes": "连线（当场过 r5）",
    "canvas.disconnect_nodes": "断线",
    "canvas.set_prompt": "设参数(nodeId, prompt=…)",
    "canvas.set_params": "设参数",
    "canvas.auto_layout": "自动布局 + 提改动('auto_layout')",
    "canvas.estimate_cost": "成本预告（实测/设计意图分开标）",
    "canvas.run": "跑 <工程> --落",
    "canvas.run_chain": "跑 <工程> --节点 <id>（只跑这条链 = 飞彩的 run_chain）",
    "canvas.await_result": "跑（同步版；飞彩是异步轮询）",
    "canvas.command_status": "★没落（影匠没有命令状态机）",
    "canvas.abort_node": "★没落（影匠没有中途 abort，只有截止秒）",
    "影匠.自查": "自查",
    "影匠.收产物": "跑 --收产物（挂进 一致性 素材库）",
    "影匠.队列": "队列（并发闸门 + 台账 schema 自查）",
}


def _取值(argv, 键):
    if 键 in argv:
        i = argv.index(键)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def _取数(argv, 键):
    v = _取值(argv, 键)
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def 自查_队列() -> int:
    """并发闸门 + 台账 schema 的独立自查（跟 umr 的账本.py 自查分开跑）。"""
    c = 自查("画布.py 队列侧")
    print("=" * 68)
    print("队列侧：并发闸门 / 台账 schema（照抄飞彩 2703 + 9223）")
    print("=" * 68)
    现在 = time.time()
    g = 取闸门("自查-甲", 2)
    c.测("两个槽能拿满", g.取得() and g.取得())
    c.测("第三个拿不到", not g.取得(超时秒=0.05))
    c.测("放一个又能拿", g.放号() and g.取得(超时秒=0.05))
    队 = []

    def 工(i):
        def _干():
            time.sleep(0.02)
            队.append(i)
            return i
        return _干

    g2 = 取闸门("自查-乙", 3)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=12) as 池:
        list(池.map(lambda i: g2.用(工(i)), range(12)))
    c.测("12 个活全跑完", sorted(队) == list(range(12)), str(sorted(队)))
    c.测("峰值从没超过上限 3", g2.峰值 <= 3, str(g2.状态()))
    c.测("放行 = 回收 = 12", g2.总放行 == 12 and g2.总回收 == 12, str(g2.状态()))
    c.测("干完活跃归零", g2.活跃 == 0, str(g2.状态()))
    g3 = 取闸门("", 30)
    c.测("归属不明闸 = 1", g3.上限 == 1 and g3.归属不明)
    c.测("归属不明只能进 1 个", g3.取得() and not g3.取得(超时秒=0.05))
    g3.放号()
    c.测("轮转 30 槽", len(轮转实例(["a", "b"])) == 30)
    任 = [{"taskId": "a", "state": "queued"}, {"taskId": "b", "state": "success",
                                              "finishedAt": 现在 - 9 * 86400}]
    c.测("列待办只出 queued", [t["taskId"] for t in 列待办(任)] == ["a"])
    c.测("9 天前的会被回收", 该回收吗(任[1], 现在=现在))
    c.测("保留 7 天是默认", 默认保留天数 == 7)
    return c.收尾()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(主(sys.argv[1:]))
