#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频.py —— 影匠的「视频链」，功能对齐飞彩（FEICAI-Studio）的视频模块。

这个模块干的事：把静帧变成片子，并把片子规格化、接起来、放大、留档。
它**不重造轮子** —— 底层推给 引擎.py（ComfyUI 派工/取图/上传），
门面留给 导演.py（让镜动），本模块补的是 飞彩有、影匠没有 的那一段。

────────────────────── 飞彩原样（证据 → 见 知识\\视频.md） ──────────────────────
创作模式（逐字，飞彩 app\\video\\page-98bed2277334d79e.js）：
    single 图生视频 / firstlast 首尾帧视频 / multiref 全能参考 / v2v 视频参考
运镜（6 个字面量，飞彩分镜卡 `<select>`，chunks\\8703-eb0f8154d00e5112.js 偏移 90996）：
    固定 / 推进 / 拉远 / 横移 / 环绕 / 升降
景别（同处）：特写 / 近景 / 中景 / 全景 / 远景
时长（分镜卡解析规则，同文件）：
    Number(x) 有限且 > 0 → Math.max(1, Math.min(30, Math.trunc(x)))，非法静默不写入
超分（**不是本地 RealESRGAN**，chunks\\app\\studio\\page-83d9e30888cbdf79.js 偏移 1190260）：
    原图当参考图 + 超分提示词喂**同一个图像模型**；提示词必写
    `This is NOT image regeneration. Do NOT redraw or reimagine` + `PIXEL-PERFECT copy`
    + 五级增强优先级「轮廓线 > 细节 > 面部 > 去伪影 > 材质」。
    档位 → 像素：4K→4096、2K→2048、其它→1024。
失败语义（飞彩贯穿全链的设计哲学）：
    超分/查询失败**不判失败**，一律 status:"indeterminate" 保留原产物；
    「超时 ≠ 失败」—— 活已经交出去了，钱可能已经花了。

────────────────────── 影匠实况（照实写，不粉饰） ──────────────────────
· 本机 ComfyUI `http://127.0.0.1:8188` 有 H3 原生节点：
  `MiniMaxH3ImageToVideo`（必填 clip/vae/prompt/width/height/length，
   可选 first_frame、last_frame —— **首尾帧是原生能力，不用外挂模型**）
  `MiniMaxH3ReferenceToVideo`（ref_images ≤9 / ref_videos ≤3 / ref_audios ≤3）
  `EmptyMiniMaxH3LatentAV`（纯文生视频用）
· 尺寸硬约束：width/height 步进 **32**；length 在 **24 fps** 下对齐 **17k+5** 网格
  （5、22、39、…、124=5.0s，训练区间 ≈124–362 帧 ≈ 5.1–15.1 秒）。
· ComfyUI 那台环境**没有 ffmpeg** —— 所以生成侧的「转场/接龙」走飞彩的路子：
  **上一镜的末帧 = 下一镜的首帧**（首尾帧模式），加提示词层的「节奏时序」档
  （一镜到底/起承转合/快切多段/渐入渐出）。末帧从生成好的 mp4 里取，走 ComfyUI 的
  LoadVideo→GetVideoComponents→SaveImage，纯 HTTP，不需要 ffmpeg。
· **但剪辑侧有 ffmpeg**（`_bin\ffmpeg.exe`，6.1.1）—— 「接片」用 xfade 做真转场，
  **不占卡**。飞彩零本地转场实现（见 知识\视频.md §1.10），这一层是影匠自建。

用法（跟 剧组.py 一个风格；退出码 0=成 1=败 2=用法错）：
    python 视频.py                      # 用法
    python 视频.py 模型                 # 列飞彩的模型能力表 + 本机 H3 模板在不在
    python 视频.py 规格 --时长 5 --比例 16:9     # 只算规格，不碰 ComfyUI
    python 视频.py 文生视频 "一句话" --时长 5
    python 视频.py 图生视频 图.png "怎么动" --时长 5
    python 视频.py 首尾帧 首.png 尾.png "怎么动" --运镜 推进 --时长 5
    python 视频.py 全能参考 参考1.png 参考2.png "一句话"
    python 视频.py 超分 图.png --档 4K [--增强关键词 "..." --存到 出.png]
                       # 参考图通道缺模型时**默认拒绝出图**（见 超分() 的 允许降级）；
                       # 确实只想要「照着提示词重画一张」才加 --允许降级
    python 视频.py 转场 --列                 # 列转场词表（不花钱）
    python 视频.py 接龙 镜1.mp4 镜2.mp4 --转场 叠化
    python 视频.py 状态                     # 看留档的任务账本
    python 视频.py 自测 [--真跑]             # 自测；--真跑 才会真提交一段视频

开关：--空跑 只演一遍不碰 ComfyUI　--json 机器可读　--真跑 自测里真提交
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

# 影匠既有模块导入：脚本目录可能不在 sys.path，先补上。
_根 = os.path.dirname(os.path.abspath(__file__))
if _根 not in sys.path:
    sys.path.insert(0, _根)


def _装模块(文件名, 别名):
    """
    载入影匠既有模块（**只读，绝不改它们**）。
    中文文件名在部分环境直接 import 会失败，所以先试 import，再退回按路径载入。
    —— 照抄 一致性.py:53 的写法，不另行发明。
    """
    try:
        return __import__(别名), ""
    except Exception as e1:  # noqa: BLE001
        pass
    try:
        import importlib.util
        p = os.path.join(_根, 文件名)
        if not os.path.isfile(p):
            return None, f"文件不存在：{p}"
        spec = importlib.util.spec_from_file_location("_影匠_" + 别名, p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        return m, ""
    except Exception as e2:  # noqa: BLE001
        return None, f"import 失败({e1!r})；按路径载入失败({e2!r})"


_引擎, _引擎错 = _装模块("引擎.py", "引擎")

# 引擎.py 不在就真没法干活了 —— 但**导入本模块本身不能炸**（自测要能把这条报成人话）
COMFY = os.environ.get("影匠_COMFY", "http://127.0.0.1:8188")

作品目录 = os.path.join(_根, "作品")
视频目录 = os.path.join(作品目录, "视频")
状态文件 = os.path.join(_根, "视频状态.json")
_work目录 = os.path.join(_根, "_work")

__all__ = [
    "模型能力表", "创作模式", "运镜表", "运镜别名", "景别表", "转场表", "节奏表",
    "列模式", "列运镜", "列转场", "能力", "在不在",
    "剪辑转场表", "剪辑转场别名", "规整剪辑转场", "列剪辑转场", "ffmpeg路", "FFMPEG",
    "探视频", "归一视频", "读接片清单", "接片",
    "比例数", "选尺寸", "规整帧数", "规整时长", "规格", "规整运镜", "规整景别",
    "运镜提示", "转场提示", "拼提示词",
    "超分提示词", "二次超分后缀",
    "拼H3", "拼Wan", "出片", "文生视频", "图生视频", "首尾帧", "全能参考", "视频参考",
    "超分", "取末帧", "接龙",
    "载状态", "存状态", "记任务", "改任务", "列任务",
    "自测", "main",
]

# ============================================================
# 一、飞彩的模型能力表（逐字搬，不另行创作）
# ============================================================

# 时长档（飞彩逐字）：UI 通用档、按模型的覆盖档、按分辨率的覆盖档
时长通用 = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
时长_按模型 = {
    "seedance-2.5": list(range(4, 31)),          # 4..30
    "video-3.5-pro": [5, 10, 12],
    "video-3.0-pro": [5, 10],
    "video-3.0": [5, 10],
    "video-3.0-fast": [5, 10],
}
时长_按分辨率 = {
    "seedance-1.5-pro-vv-720p-feicai": [4, 5, 10, 12],
    "seedance-2.0-vip-720p-azhw-feicai": list(range(4, 16)),        # 4..15
    "seedance-2.0-vip-1080p-azhw-feicai": list(range(4, 12)),       # 4..11 —— 1080P 硬上限 11 秒
    "jimeng-video-seedance-2.5-vip-720p-azhw-feicai": list(range(4, 31)),
    "sora-v4-15-933Z-1080-hj-feicai": [15],
    "wan2.7-me-feicai": [15],
}
分辨率_按模型 = {
    "seedance-2.5": ["480P", "720P"],
    "seedance-2.0-mini": ["720P"],
    "seedance-2.0-fast-vip": ["720P"],
    "seedance-2.0-vip": ["720P", "1080P"],
}
分辨率缺省 = ["720P", "1080P"]

# 宽高比：视频页（逐字） vs 通用能力位（逐字）
比例_视频页 = ["16:9", "9:16", "1:1", "4:3", "3:4"]
比例_默认 = "16:9"
比例_通用 = ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]

# 创作模式（逐字）
创作模式 = [
    {"值": "single", "名": "图生视频"},
    {"值": "firstlast", "名": "首尾帧视频"},
    {"值": "multiref", "名": "全能参考"},
    {"值": "v2v", "名": "视频参考"},
]
创作模式_带批量 = 创作模式 + [{"值": "batchRelay", "名": "批量参考"}]
模式白名单 = [m["值"] for m in 创作模式_带批量]

# 镜头类型（逐字）：非法值静默回落第一个 —— 这条照搬，别「改进」成报错
镜头类型 = ["对话场景", "动作场景", "情绪特写", "环境空镜", "转场镜头"]

# 能力位（逐字，飞彩 9009 函数 m）：每项 null 即丢弃、不报错
能力位字段 = (
    "kind", "model", "family", "durationsByResolution", "durations", "resolutions",
    "modes", "refImageCap", "refVideoCap", "refAudioCap", "refMediaTotalCap",
    "audioInput", "audioRequiresVisualReference", "textToVideo", "v2vReferenceMedia",
    "audioOutput", "asyncMode", "publicMedia",
)
参考上限_特殊 = {"video-3.0-pro", "video-3.0-fast"}    # 这两个给 MAX_REF_CAP，其余 DEFAULT_MAX_REF_CAP

# 超时与轮询（逐字）：飞彩的端名里带 `-zm-feicai` / `-mgdb-15s-feicai` 就给 2100 秒，其余 1200 秒
超时标准_毫秒 = 1200000
超时长_毫秒 = 2100000
超时长的端名标记 = ("-zm-feicai", "-mgdb-15s-feicai")
轮询上限_毫秒 = 3000000                        # 50 分钟
轮询间隔_秒 = 5
批量并发上限 = 8                               # 飞彩 Math.min(8, e.length)
状态账本键 = "feicai-video-states"             # 飞彩的 localStorage key（影匠落成文件）

# 影匠本机 H3 的硬约束（问 ComfyUI /object_info 得到，不是猜的）
H3_尺寸步进 = 32
H3_帧组 = 17
H3_帧偏移 = 5
H3_帧率 = 24
H3_帧数下限 = 5
H3_训练帧区间 = (124, 362)
H3_分辨率秒数上限 = {"1080P": 11}              # 照飞彩：1080P 上限 11 秒

# 模型能力表：飞彩的引擎名 → 能力位。影匠这边补上「本机能不能真跑」。
模型能力表 = {
    "seedance-2.5": {
        "family": "seedance", "durations": 时长_按模型["seedance-2.5"],
        "resolutions": 分辨率_按模型["seedance-2.5"],
        "modes": ["single", "firstlast", "multiref", "batchRelay"],
        "refImageCap": 4, "textToVideo": True, "audioInput": False, "asyncMode": True,
    },
    "seedance-2.0": {
        "family": "seedance", "durations": 时长通用, "resolutions": 分辨率缺省,
        "modes": ["single", "firstlast", "multiref"], "refImageCap": 4,
        "textToVideo": True, "asyncMode": True,
    },
    "seedance-2.0-fast": {
        "family": "seedance", "durations": 时长通用, "resolutions": 分辨率缺省,
        "modes": ["single", "firstlast", "multiref"], "refImageCap": 4,
        "textToVideo": True, "asyncMode": True,
    },
    "seedance-2.0-mini": {
        "family": "seedance", "durations": 时长通用, "resolutions": 分辨率_按模型["seedance-2.0-mini"],
        "modes": ["single", "firstlast"], "refImageCap": 2, "asyncMode": True,
    },
    "seedance-2.0-fast-vip": {
        "family": "seedance", "durations": 时长通用,
        "resolutions": 分辨率_按模型["seedance-2.0-fast-vip"],
        "modes": ["single", "firstlast", "multiref"], "refImageCap": 4, "asyncMode": True,
    },
    "seedance-2.0-vip": {
        "family": "seedance", "durations": 时长通用,
        "resolutions": 分辨率_按模型["seedance-2.0-vip"],
        "durationsByResolution": {"1080P": 时长_按分辨率["seedance-2.0-vip-1080p-azhw-feicai"]},
        "modes": ["single", "firstlast", "multiref"], "refImageCap": 4,
        "textToVideo": True, "audioInput": True, "asyncMode": True,
    },
    "video-3.5-pro": {
        "family": "jimeng", "durations": 时长_按模型["video-3.5-pro"], "resolutions": 分辨率缺省,
        "modes": ["single", "firstlast"], "refImageCap": 3, "asyncMode": True,
    },
    "video-3.0-pro": {
        "family": "jimeng", "durations": 时长_按模型["video-3.0-pro"], "resolutions": 分辨率缺省,
        "modes": ["single", "firstlast", "multiref"], "refImageCap": 6, "asyncMode": True,
    },
    "video-3.0": {
        "family": "jimeng", "durations": 时长_按模型["video-3.0"], "resolutions": 分辨率缺省,
        "modes": ["single", "firstlast"], "refImageCap": 3, "asyncMode": True,
    },
    "video-3.0-fast": {
        "family": "jimeng", "durations": 时长_按模型["video-3.0-fast"], "resolutions": 分辨率缺省,
        "modes": ["single", "firstlast"], "refImageCap": 6, "asyncMode": True,
    },
    # ── 影匠本机真能跑的两条 ──
    # ★ 原生画布 (1344, 768)：官方 video_minimax_h3_i2v.json 的 MarkdownNote 逐字 ——
    #   "H3's native canvas is a 768px short edge, capped at 768x1344 pixels,
    #    rounded to a multiple of 32"，尺寸参考表最后一行
    #   "| 0.98 | 16:9 | 1344 x 768 (official 768p) |"。
    "minimax-h3-fl2va": {
        "family": "h3", "本机": True,
        "模型": "minimax_h3_fl2va_pruned_w6a8.safetensors",
        "LoRA": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
        "原生画布": (1344, 768),
        "resolutions": ["720P", "1080P"], "durations": 时长通用,
        "modes": ["single", "firstlast"],
        "帧率": H3_帧率, "尺寸步进": H3_尺寸步进, "帧组": (H3_帧组, H3_帧偏移),
        "textToVideo": True, "audioOutput": True,
        "备注": "文生视频/图生视频/首尾帧三合一（fl2va）；带 8 步 turbo LoRA；出声（audio VAE 联合解码）",
    },
    "minimax-h3-ref2va": {
        "family": "h3", "本机": True,
        "模型": "minimax_h3_ref2va_pruned_w6a8.safetensors",
        "LoRA": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
        "原生画布": (1344, 768),
        "resolutions": ["720P"], "durations": 时长通用,
        "modes": ["multiref", "v2v", "batchRelay"],
        "帧率": H3_帧率, "尺寸步进": H3_尺寸步进, "帧组": (H3_帧组, H3_帧偏移),
        "refImageCap": 9, "refVideoCap": 3, "refAudioCap": 3, "refMediaTotalCap": 9,
        "audioInput": True, "audioOutput": True,
        "备注": "全能参考/视频参考；ref_images ≤9、ref_videos ≤3、ref_audios ≤3",
    },
    "wan2.2-ti2v-5b": {
        "family": "wan", "本机": True,
        "模型": "wan2.2_ti2v_5B_fp16.safetensors",
        "resolutions": ["480P", "720P"], "durations": [2, 3, 4, 5, 6, 8, 10],
        "modes": ["single", "firstlast"],
        "帧率": 16, "尺寸步进": 16, "帧组": (4, 1), "帧数下限": 5,
        "textToVideo": False,
        "备注": "影匠原有通道（导演.让镜动 走这条）；首尾帧走 WanFirstLastFrameToVideo 节点",
    },
}

# 飞彩的计费单位是「积分/秒」（逐字）
计费 = {
    "dreamina_seedance_40_pro": {"720P": 5, "1080P": 8},
    "dreamina_seedance_40": {"720P": 3, "1080P": 5},
    "video-3.5-pro": {"*": 8},
    "video-3.0-pro": {"*": 10},
    "video-3.0": {"*": 2},
    "video-3.0-fast": {"*": 2},
}


def 能力(模型: str) -> dict | None:
    """取一个模型的能力位。不认识的返回 None（飞彩的语义：能力位每一项 null 就丢弃）。"""
    return 模型能力表.get(模型)


def 在不在(模型: str) -> bool:
    """这个模型在本机能不能真跑（只看表，不碰磁盘 —— 磁盘用 引擎.有模型）。"""
    c = 模型能力表.get(模型) or {}
    return bool(c.get("本机"))


def 列模式() -> list:
    return [dict(m) for m in 创作模式]


# ============================================================
# 二、运镜 / 景别 / 转场词表（飞彩逐字 + 影匠扩写）
# ============================================================

# 飞彩分镜卡的 6 个字面量（`<select>`，不是自由文本）
运镜表 = ["固定", "推进", "拉远", "横移", "环绕", "升降"]

# 提取侧用的词表 + 反查表（逐字）
提取词表 = ["运镜", "景别", "机位", "过渡", "转场"]
反查表 = {
    "推": ["推", "推进", "推近", "push", "zoom in", "dolly in"],
    "拉": ["拉", "拉远", "拉出", "pull", "zoom out", "dolly out"],
    "摇": ["摇", "摇镜", "横移", "平移", "pan", "truck"],
    "移": ["移", "移动", "跟移", "tracking", "dolly"],
    "跟": ["跟", "跟拍", "跟随", "follow"],
    "升降": ["升", "降", "升降", "吊臂", "crane", "boom", "jib"],
    "环绕": ["环绕", "绕", "旋转", "orbit", "arc"],
    "固定": ["固定", "固定机位", "静止", "static", "locked"],
}

# 别名词表：用户说「推」也能落成飞彩的「推进」
运镜别名 = {
    "推": "推进", "推近": "推进", "推镜": "推进", "push": "推进", "zoom in": "推进",
    "拉": "拉远", "拉出": "拉远", "拉镜": "拉远", "pull": "拉远", "zoom out": "拉远",
    "摇": "横移", "摇镜": "横移", "摇移": "横移", "平移": "横移", "pan": "横移", "truck": "横移",
    "移": "横移", "移动": "横移", "dolly": "横移",
    "跟": "升降", "跟拍": "升降", "跟随": "升降", "follow": "升降",
    "升": "升降", "降": "升降", "吊臂": "升降", "crane": "升降", "boom": "升降", "jib": "升降",
    "绕": "环绕", "旋转": "环绕", "orbit": "环绕", "arc": "环绕",
    "静止": "固定", "静止机位": "固定", "static": "固定", "locked": "固定",
}

景别表 = ["特写", "近景", "中景", "全景", "远景"]
景别别名 = {
    "大特写": "特写", "极特写": "特写", "close": "特写", "close-up": "特写",
    "wide": "远景", "全": "全景", "远": "远景", "medium": "中景",
}

# 运镜 → 提示词短句。
# ★ 这里照抄飞彩的**语言规范**（chunks\\8703 偏移 535191 视频提示词扩写器）：
#   「选项 value 用「导演语言」完整短句（如「镜头从中景缓缓推近至主体特写」），
#     与推/拉/横移/环绕/固定/景别/过渡等镜头语汇同源，
#     杜绝「更流畅 / 丝滑 / 高质量」」
运镜提示 = {
    "固定": "Static locked-off camera, no camera movement; only the subject moves within the frame",
    "推进": "Camera pushes in slowly from a medium shot toward the subject, gradual dolly-in, no cut",
    "拉远": "Camera pulls back slowly, revealing more of the surroundings, gradual dolly-out, no cut",
    "横移": "Camera pans horizontally, gliding smoothly and steadily along the scene",
    "环绕": "Camera arcs around the subject in a slow orbit, keeping it centred",
    "升降": "Camera rises smoothly with a crane movement, the view opening up as it lifts",
}
运镜中文 = {
    "固定": "固定机位，镜头不动，只有主体在画面里动",
    "推进": "镜头从中景缓缓推近至主体特写",
    "拉远": "镜头缓慢拉远，逐步交代环境",
    "横移": "镜头横向平移，平稳匀速地扫过场景",
    "环绕": "镜头绕主体缓慢环绕，主体保持在画面中心",
    "升降": "镜头用升降臂平稳升起，视野随之打开",
}

# 转场（镜与镜之间）。
# 飞彩把「过渡」归在**镜头语汇**里（与推/拉/横移/环绕/固定同源，
# chunks\\8703 偏移 535191），节奏时序档逐字为：
节奏表 = ["一镜到底", "起承转合", "快切多段", "渐入渐出"]
节奏提示 = {
    "一镜到底": "Single continuous take, no cuts from start to finish",
    "起承转合": "Four-beat structure — setup, development, turn, resolution — with matched lighting across beats",
    "快切多段": "Fast cutting between short segments, quick rhythmic edit",
    "渐入渐出": "Gradual fade in at the start and fade out at the end; lighting, colour and camera axis stay continuous across the transition",
}
转场表 = {
    "无": {"名": "无（硬切）", "文案": "", "手法": "本机无 ffmpeg，硬切靠「上镜末帧 = 下镜首帧」对齐"},
    "直接切": {"名": "直接切", "文案": "Cut directly to the next shot on the same camera axis",
               "手法": "首尾帧：上镜末帧当下镜首帧"},
    "叠化": {"名": "叠化", "文案": "Dissolve smoothly from the previous shot into this one",
             "手法": "首尾帧 + 提示词层叠化"},
    "淡入黑场": {"名": "淡入黑场", "文案": "Fade in from black at the start of the shot",
                 "手法": "提示词层，画面自黑场亮起"},
    "淡出黑场": {"名": "淡出黑场", "文案": "Fade out to black at the end of the shot",
                 "手法": "提示词层，画面收进黑场"},
    "白闪": {"名": "白闪", "文案": "Brief white flash covering the cut, then the new shot is fully visible",
             "手法": "提示词层，靠一次过曝白帧掩盖切换"},
    "匹配剪辑": {"名": "匹配剪辑", "文案": "Match cut — the subject keeps the same screen position and facing across the cut",
                 "手法": "首尾帧 + 屏幕站位锁定（左/右站位、面向一致）"},
}
转场别名 = {
    "硬切": "直接切", "切": "直接切", "cut": "直接切",
    "dissolve": "叠化", "融化": "叠化",
    "淡入": "淡入黑场", "淡出": "淡出黑场", "黑场": "淡入黑场",
    "闪白": "白闪", "flash": "白闪",
    "匹配": "匹配剪辑", "match": "匹配剪辑",
    "none": "无",
}

# 「转场镜头」是飞彩的镜头类型之一（逐字），但它不是运镜 —— 这里给提示词模板
转场镜头提示 = (
    "Transition shot: a brief bridging beat with no dialogue and no new story information; "
    "keep the light direction, colour temperature and camera axis continuous with the shots before and after"
)


def 列运镜() -> list:
    return [{"词": k, "中文": 运镜中文[k], "提示词": 运镜提示[k]} for k in 运镜表]


def 列转场() -> list:
    return [{"词": k, **v} for k, v in 转场表.items()]


def 规整运镜(s: str) -> str:
    """
    用户怎么写都能落成飞彩的 6 个字面量之一。
    ★ 飞彩分镜卡那边是**白名单枚举、非法静默丢弃**（不报错、不回落）；
      这里是「人敲命令」的入口，静默丢弃等于让人白敲，所以改成**报错**，
      把「静默丢弃」留给解析 04-动态提示词.md 的路径（剧组的活）。
    """
    s = (s or "").strip()
    if not s:
        return "固定"
    if s in 运镜表:
        return s
    k = 运镜别名.get(s.lower(), 运镜别名.get(s))
    if k:
        return k
    for 键, 词们 in 反查表.items():
        if 键 in s or any(w in s.lower() for w in 词们):
            return 运镜别名.get(键, 键 if 键 in 运镜表 else "固定")
    raise ValueError(f"不认识的运镜「{s}」。飞彩的字面量只有这 6 个：{' / '.join(运镜表)}；"
                     f"别名（推/拉/摇/移/跟/升降/环绕）也认。")


def 规整景别(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if s in 景别表:
        return s
    k = 景别别名.get(s.lower(), 景别别名.get(s))
    if k:
        return k
    raise ValueError(f"不认识的景别「{s}」。飞彩的字面量只有这 5 个：{' / '.join(景别表)}")


def 运镜提示词(运镜: str, 景别: str = "") -> str:
    """运镜 + 景别 → 一句导演语言（飞彩的语言规范，见上方注释）。"""
    运镜 = 规整运镜(运镜) if 运镜 else "固定"
    句 = 运镜提示.get(运镜, 运镜提示["固定"])
    if 景别:
        景别 = 规整景别(景别)
        if 景别:
            句 = f"{景别}景起手，{句}" if 景别 != "特写" else f"以特写为主，{句}"
    return 句


def 转场提示(转场: str) -> dict:
    """转场词 → {文案, 手法, 名}。不认识就报错（别静默丢）。"""
    转场 = (转场 or "").strip()
    if not 转场:
        return {"词": "无", **转场表["无"]}
    if 转场 in 转场表:
        return {"词": 转场, **转场表[转场]}
    k = 转场别名.get(转场.lower(), 转场别名.get(转场))
    if k:
        return {"词": k, **转场表[k]}
    raise ValueError(f"不认识的转场「{转场}」。认得这些：{' / '.join(转场表)}（别名：硬切/淡入/淡出/闪白/匹配/叠化）")


# ============================================================
# 三、规格化与校验（时长 / fps / 尺寸 / 帧数）
# ============================================================

比例数 = {
    "21:9": 21 / 9, "16:9": 16 / 9, "9:16": 9 / 16, "4:3": 4 / 3, "3:4": 3 / 4,
    "1:1": 1.0, "3:2": 3 / 2, "2:3": 2 / 3,
}

# 分辨率档 → 长边像素（照飞彩：4K→4096、2K→2048、其它→1024）
档位像素 = {"4K": 4096, "2K": 2048, "1080P": 1920, "720P": 1280, "480P": 854}


def _对齐(值: float, 步进: int) -> int:
    return max(步进, int(round(值 / 步进)) * 步进)


def 选尺寸(比例: str = "16:9", 长边: int | None = None, 档: str | None = None,
           步进: int = H3_尺寸步进, 总像素上限: float | None = None) -> tuple[int, int]:
    """
    宽高比 + 档位 → (宽, 高)，两边都是 步进 的整数倍。

    ★ 尺寸不是「比例 × 长边」四舍五入就完事 —— 步进对齐会把比例带偏，
      所以这里在 ±1 个步进的邻域里挑**比例最贴近目标**的那一对。
      实测教训：1344×768 是 16:9 的正解；直接 round 出 1365×768 会被 H3 拒。
    """
    比例 = str(比例 or "16:9").strip()
    if 比例 not in 比例数:
        raise ValueError(f"不认识的宽高比「{比例}」。飞彩视频页只有：{' / '.join(比例_视频页)}")
    目标 = 比例数[比例]

    if 长边 is None:
        档 = (档 or "720P").upper()
        长边 = 档位像素.get(档)
        if 长边 is None:
            raise ValueError(f"不认识的档「{档}」。飞彩的档：4K / 2K；本机常用：1080P / 720P / 480P")

    # 先按「长边」定长的那一边
    横 = 目标 >= 1.0
    if 横:
        宽0, 高0 = 长边, 长边 / 目标
    else:
        高0, 宽0 = 长边, 长边 * 目标

    # ★ 「理想尺寸」怎么定，是这一步的全部要害 —— 定错了后面怎么搜都是错的。
    #   规则：先按长边算理想宽高；如果它有预算（H3 原生画布 1344×768）且超了，
    #   就**等比压进预算**（保持比例），不超就用它自己。理想像素 = 这个理想尺寸的面积。
    #   踩过的坑（都真炸过，别再走回头路）：
    #   ① 只把「理想像素」截到上限、不缩宽高 → 锚点留在超预算的位置，
    #      候选全被上限丢掉，直接报「算不出尺寸」（16:9@1080P、1:1@720P 都这么炸过）。
    #   ② 拿「比例误差」单指标挑 → 16:9@1344 会挑中 1312×736（误差 0.0048），
    #      但那是把长边丢了 32 px 换来的假精确；用户要的是 1344 那一档。
    #   ③ 拿「像素量」单指标挑 → 16:9@1344 会挑中 1376×736（比正解更贴理想像素），
    #      但它根本不是 16:9。
    #   ④ 于是两个误差各自归一化后加权：`比例误差 × 0.5 + 像素差 / 理想像素`。
    #      这一组权重（0.5 = 比例按两倍于像素的容忍度看待）实测全部落在正解上：
    #      16:9@1344 → 1344×768、16:9@1920 → 1920×1088（恰好整除，不许落成 1888×1056）、
    #      4:3@1024 → 1024×768、21:9@1344 → 1344×576、9:16@1344 → 736×1376；
    #      带 H3 预算（1344×768）时：16:9@720P → 1344×768、16:9@1080P → 1344×768
    #      （1080P 超 H3 原生，收口回原生画布）、9:16@720P → 736×1376、
    #      21:9@720P → 1344×576、1:1@720P → 1024×1024、4:3@720P → 1152×896。
    #      关键三组对比（16:9@预算 1344×768）：
    #        1344×768 = 0.5×0.0278 + 0.0000 = 0.0139 ← 正解
    #        1312×736 = 0.5×0.0048 + 0.0530 = 0.0554   （丢了长边）
    #        1376×736 = 0.5×0.0051 + 0.0333 = 0.0359   （像素贴近但不是 16:9）
    理想宽, 理想高 = 宽0, 高0
    预算 = float(总像素上限) if 总像素上限 else None
    if 预算 and 理想宽 * 理想高 > 预算:
        缩 = (预算 / (理想宽 * 理想高)) ** 0.5
        理想宽, 理想高 = 理想宽 * 缩, 理想高 * 缩
    理想像素 = 理想宽 * 理想高

    # 候选：步进对齐全靠这一步凑。
    # ⑤ 邻域必须够宽：1344/32=42 是整除，只取 //32 与 //32+1 会把 1344×768 漏掉（落成 1312×736）；
    #    21:9@720P 的正解 1344×576 也在 ±2 格之外。取 ±6 格，再靠加权收敛。
    # ⑥ 超预算的候选**不硬丢、改成罚**：H3 的 1344×768 本身略高于理想（+5.1%），
    #    硬丢会把正解一起丢掉。罚 0.4×超出比例，刚好既挡住 1536×672（超出 15.7% → 罚 0.0628），
    #    又不伤 1344×768。
    基宽 = max(1, int(round(理想宽 / 步进)))
    基高 = max(1, int(round(理想高 / 步进)))
    最好 = None
    for bw in range(max(1, 基宽 - 6), 基宽 + 7):
        宽 = bw * 步进
        if 宽 < 步进:
            continue
        for bh in range(max(1, 基高 - 6), 基高 + 7):
            高 = bh * 步进
            if 高 < 步进:
                continue
            像素 = 宽 * 高
            键 = (round(abs(宽 / 高 - 目标), 6) * 0.5
                  + abs(像素 - 理想像素) / 理想像素)
            if 预算 and 像素 > 预算:
                键 += 0.4 * (像素 / 预算 - 1.0)
            if 最好 is None or 键 < 最好[0]:
                最好 = (键, 宽, 高)
    if 最好 is None:
        raise ValueError(f"算不出尺寸：比例 {比例} 长边 {长边} 步进 {步进} 预算 {总像素上限}")
    return 最好[1], 最好[2]


def 规整帧数(秒: float, 帧率: int = H3_帧率, 帧组: tuple = (H3_帧组, H3_帧偏移),
             下限: int = H3_帧数下限) -> int:
    """
    秒 → 帧数，并对齐模型的帧网格。

    ★ H3 的约束（ComfyUI 节点 tooltip 逐字）：
      "Frame count at 24 fps, snapped up to the model's 17k+5 grid (124 = ~5s;
       trained range is ~124-362, longer is untested)"
      → 合法帧数 = 17k + 5（5、22、39、…、124、141…）；**下限是 5，不是 124**。
        124–362 是「训练区间」，出了区间只警告、不拦（跟飞彩一个态度：
        它也不拦，只是把「未验证」说出来）。节点自己 min=5 step=17，短于 5 的会被它顶上来。
    Wan 那边是 4k + 1，同一套算法换个 (组, 偏移) 就行。
    """
    k, 偏 = 帧组
    帧 = max(下限, int(round(float(秒) * 帧率)))
    if k <= 1:
        return 帧
    if 帧 <= 偏:
        return 偏 if 偏 >= 下限 else 下限
    kk = (帧 - 偏 + k - 1) // k          # 向上取整到最近的 17k+5
    return kk * k + 偏


def 规整时长(秒, 模型: str = "minimax-h3-fl2va", 分辨率: str = "720P") -> dict:
    """
    秒 → 该模型真能跑的时长。返回 {要的, 给的, 帧数, 说明, 钳过}。

    改的是「飞彩那套 UI 时长档校验」，不是另发明：
      · 先夹到模型允许的档（飞彩逐字：u=后端时长表，1080P 上限 11 秒）；
      · 再按帧网格对齐到**不小于**用户要的时长（宁可多给一点，不可少给）；
      · 超出训练区间只警告，不拦 —— 但要把「未验证」四个字说出来。
    """
    try:
        要的 = float(秒)
    except (TypeError, ValueError):
        raise ValueError(f"时长「{秒}」不是数字") from None
    if 要的 <= 0:
        raise ValueError(f"时长必须 > 0，收到 {要的}")

    c = 模型能力表.get(模型) or {}
    帧率 = int(c.get("帧率", H3_帧率))
    帧组 = tuple(c.get("帧组", (H3_帧组, H3_帧偏移)))
    下限 = int(c.get("帧数下限", H3_帧数下限))
    分辨率 = (分辨率 or "720P").upper()

    说明 = []
    允许 = c.get("durations") or 时长通用
    按分辨率 = (c.get("durationsByResolution") or {}).get(分辨率)
    if 按分辨率:
        允许 = 按分辨率
        说明.append(f"{分辨率} 的时长档是 {按分辨率[0]}–{按分辨率[-1]} 秒（飞彩硬约束）")
    上限 = H3_分辨率秒数上限.get(分辨率) if c.get("family") == "h3" else None
    if 上限 and 要的 > 上限:
        说明.append(f"{分辨率} 上限 {上限} 秒，{要的:g} → {上限}（照飞彩）")
        要的 = float(上限)

    给的 = 要的
    最高 = max(允许)
    最低 = min(允许)
    # ★ 时长档只当「上限」用 —— 飞彩的档是给 UI 下拉用的，不是硬校验：
    #   要 3 秒、档里第一个是 4，硬顶上去等于偷偷改用户的意图。
    #   帧网格自己会保证不低于模型下限（H3 是 5 帧）。
    if 给的 > 最高:
        说明.append(f"模型最长 {最高} 秒，{给的:g} → {最高}")
        给的 = float(最高)

    帧 = 规整帧数(给的, 帧率=帧率, 帧组=帧组, 下限=下限)
    实际 = 帧 / 帧率
    if abs(实际 - 给的) > 1e-6:
        说明.append(f"帧数对齐 {帧组[0]}k+{帧组[1]} 网格：{给的:.2f}s → {帧} 帧 = {实际:.2f}s")
    训练 = c.get("训练帧区间") or (H3_训练帧区间 if c.get("family") == "h3" else None)
    if 训练 and (帧 < 训练[0] or 帧 > 训练[1]):
        说明.append(f"⚠ {帧} 帧在训练区间 {训练[0]}–{训练[1]} 之外，**未验证**，可能糊或崩")

    return {"要的": 秒, "给的": round(给的, 3), "实际秒": round(实际, 3),
            "帧数": 帧, "帧率": 帧率, "说明": 说明,
            "钳过": bool(说明 and any("→" in s for s in 说明))}


def 规格(时长=5, 比例: str = "16:9", 模型: str = "minimax-h3-fl2va",
         分辨率: str = "", 帧率=None, 宽=0, 高=0, 档: str = "") -> dict:
    """一句话规格化 + 校验。返回 {模型, 比例, 宽, 高, 帧数, 帧率, 秒, 分辨率, 警告们, 提示们}。"""
    c = 模型能力表.get(模型)
    if c is None:
        raise ValueError(f"不认识模型「{模型}」。已知：{' / '.join(模型能力表)}")
    警告 = []
    提示 = []

    比例 = str(比例 or 比例_默认).strip()
    if 比例 not in 比例_视频页 and 比例 not in 比例_通用:
        raise ValueError(f"不认识的宽高比「{比例}」。视频页：{' / '.join(比例_视频页)}；"
                         f"通用档：{' / '.join(比例_通用)}")
    if 比例 not in 比例_视频页:
        提示.append(f"「{比例}」是飞彩的通用能力位档，不在视频页那 5 档里")

    步进 = int(c.get("尺寸步进", H3_尺寸步进))
    if 宽 and 高:
        宽, 高 = int(宽), int(高)
        for 名, 值 in (("宽", 宽), ("高", 高)):
            if 值 % 步进:
                调 = _对齐(值, 步进)
                警告.append(f"{名} {值} 不是 {步进} 的整数倍，对齐到 {调}")
                if 名 == "宽":
                    宽 = 调
                else:
                    高 = 调
        实际比例 = 宽 / 高
        目标 = 比例数.get(比例)
        if 目标 and abs(实际比例 - 目标) / 目标 > 0.02:
            提示.append(f"手写的 {宽}×{高} 跟 {比例} 差 {(实际比例/目标-1)*100:+.1f}%")
    else:
        档 = (档 or 分辨率 or "720P").upper()
        长边 = 档位像素.get(档)
        if 长边 is None:
            raise ValueError(f"不认识的档「{档}」。4K / 2K / 1080P / 720P / 480P")
        # ★ H3 的原生画布是「短边 768、上限 1344×768、32 的倍数」（官方模板逐字），
        #   720P 档不能真按「长边 1280」算 —— 官方 768p 就是 1344×768。
        像素上限 = None
        if c.get("family") == "h3":
            长边 = 1344 if 档 == "720P" else 长边
            上限宽, 上限高 = c.get("原生画布", (1344, 768))
            像素上限 = 上限宽 * 上限高
            if 档 in ("1080P", "2K", "4K"):
                警告.append(f"H3 原生上限是 {上限宽}×{上限高}（官方 768p）；"
                             f"{档} 超出原生能力，成片实际仍是原生分辨率 —— "
                             f"要更大请走 超分/`MiniMaxH3LatentUpscaleCombined` 潜空间放大")
        宽, 高 = 选尺寸(比例, 长边=长边, 步进=步进, 总像素上限=像素上限)
        分辨率 = 档

    允许分辨率 = c.get("resolutions") or []
    if 分辨率 and 允许分辨率 and 分辨率.upper() not in 允许分辨率:
        警告.append(f"模型 {模型} 的能力位里没有 {分辨率}（它有 {'/'.join(允许分辨率)}）")

    t = 规整时长(时长, 模型=模型, 分辨率=(分辨率 or "720P"))
    帧率 = int(帧率 or c.get("帧率", H3_帧率))
    if 帧率 != int(c.get("帧率", H3_帧率)):
        警告.append(f"{模型} 的原生帧率是 {c.get('帧率', H3_帧率)}，你要 {帧率}；"
                     f"帧数按 {帧率} 算，但成片播放帧率由模型定")
    警告.extend(x for x in t["说明"] if x.startswith("⚠"))
    提示.extend(x for x in t["说明"] if not x.startswith("⚠"))

    if c.get("family") == "h3" and 帧率 != H3_帧率:
        提示.append("H3 的 length 是「24 fps 下的帧数」，改 fps 只影响播放速度感知，不改帧数")

    return {"模型": 模型, "比例": 比例, "宽": 宽, "高": 高,
            "帧数": t["帧数"], "帧率": 帧率, "秒": t["实际秒"], "要的秒": t["要的"],
            "分辨率": 分辨率 or "720P", "警告们": 警告, "提示们": 提示, "钳过": t["钳过"]}


# ============================================================
# 四、提示词拼装（飞彩的扩写器语言规范）
# ============================================================

def 拼提示词(正文: str, 运镜: str = "", 景别: str = "", 转场: str = "", 节奏: str = "",
             时长秒: float | None = None, 时代: str = "") -> str:
    """
    把「主体/动作」正文 + 运镜 + 景别 + 转场 + 节奏 拼成一条给视频模型的提示词。

    ★ 飞彩的维度优先级（chunks\\8703 偏移 535191，逐字）：
        运镜 > 主体动态幅度 > 成片取向 > 节奏时序 > 情绪氛围 > 景别
      这里按这个次序排。转场按飞彩归入「镜头语汇」，跟在运镜后。
    ★ 参数禁区（飞彩逐字）：时长 / 画面比例 / 分辨率 / 首尾帧 **不进提示词**，
      它们是参数。所以本函数**不**把秒数写进正文 —— 只用它做一句节奏副词。
    """
    段 = []
    正文 = (正文 or "").strip()
    if 时代:
        段.append(f"ERA / WORLD BACKGROUND: {时代}. Keep all visual elements consistent with this setting.")
    if 正文:
        段.append(正文)
    if 运镜 or 景别:
        段.append(运镜提示词(运镜 or "固定", 景别))
    if 转场:
        转 = 转场提示(转场)
        if 转["文案"]:
            段.append(转["文案"])
    if 节奏:
        节奏 = 节奏.strip()
        if 节奏 not in 节奏提示:
            raise ValueError(f"不认识的节奏「{节奏}」。飞彩的节奏时序档：{' / '.join(节奏表)}")
        段.append(节奏提示[节奏])
    if 时长秒:
        try:
            s = float(时长秒)
            if s <= 3:
                段.append("Keep the action tight and readable within a very short beat")
            elif s >= 10:
                段.append("Sustain the action across a long take without cutting away")
        except (TypeError, ValueError):
            pass
    # 一条铁律，跟 一致性.py 的「零文字铁律」同源
    段.append("No subtitles, no captions, no on-screen text or watermarks. Keep identity, wardrobe and "
              "lighting continuous with the reference images.")
    return "\n".join(段)


# ============================================================
# 五、超分（★ 飞彩的真机制：原图当参考图 + 超分提示词喂同一个图像模型）
# ============================================================

超分英文 = """Super-resolution task: Reproduce this reference image at {档} resolution ({长边}px long edge).

CRITICAL — This is NOT image regeneration. Do NOT redraw or reimagine the scene.
- Output a PIXEL-PERFECT copy of the input, only at higher resolution with enhanced sharpness
- Preserve EXACTLY: composition, colors, lighting, shadows, style, every character, pose, expression
- Do NOT add, remove, or alter any visual element whatsoever

ENHANCEMENT PRIORITIES (in order):
1. EDGES & LINES — Reconstruct thin, crisp, clean outlines. This is the #1 priority. Avoid thick, soft, or blurry lines.
2. FINE DETAILS — Sharpen individual hair strands, fabric weave patterns, skin micro-texture, eyelashes, iris detail
3. FACIAL CLARITY — Eyes with visible iris detail, defined eyelid creases, natural skin pores, sharp lip edges
4. ARTIFACT REMOVAL — Clean compression blocks, color banding, and ringing. Smooth gradients without posterization
5. TEXTURE FIDELITY — Preserve material qualities (metal, wood, cloth, skin) without over-smoothing or plastic look

The output MUST look like a native {档} render — not an upscaled low-res image. Thin sharp lines, not thick blurry ones."""

超分中文 = """超分辨率任务：将此图精确复刻为{档}高清版本。

【铁律】这是超分放大，不是重新绘制！禁止重绘、禁止改变任何内容。输出必须与原图像素级一致，仅提升分辨率和清晰度。

【增强重点】（按优先级排序）
1. 边缘线条：重建纤细、锐利、干净的轮廓线——这是最重要的！避免线条变粗变糊
2. 精细细节：锐化发丝、织物纹理、皮肤质感、睫毛、虹膜细节
3. 面部清晰：眼睛有虹膜纹理、眼睑清晰、皮肤毛孔自然、唇线锋利
4. 去除伪影：消除压缩色块、色带、振铃效应，平滑渐变过渡
5. 材质保真：保持金属、木材、布料、皮肤的真实质感，不要过度平滑

输出必须像原生{档}渲染，而非低分辨率放大。{时代}"""

超分Gemini = """Generate a {档} ultra-high-definition version of this exact image with crisp, sharp details. The image should faithfully preserve every element: same composition, same characters, same poses, same colors, same lighting, same art style. Enhanced with razor-sharp edges, fine hair strands, visible fabric textures, detailed facial features with clear irises and natural skin, clean gradients, and authentic material qualities throughout.{比例}{时代}"""

# 二次超分的固定后缀（飞彩 xA，逐字）
二次超分后缀 = (
    "\n\nAdditionally: rebuild ultra-fine micro-texture, remove all residual compression artifacts, "
    "and keep every edge razor sharp without thickening."
)


def 超分提示词(档: str = "4K", 通道: str = "英文", 比例: str = "", 时代: str = "",
               像素: int | None = None) -> str:
    """
    飞彩的超分提示词，三种通道逐字搬（studio 页 偏移 1190260）。

    通道选择照飞彩原逻辑：
        agentDispatch 或 非 jimeng → 英文；geminiTab 通道 → Gemini 变体；jimeng → 中文。
    档位 → 像素：4K→4096、2K→2048、其它→1024。
    """
    档 = (档 or "4K").strip().upper()
    长边 = 像素 if 像素 else (4096 if 档 == "4K" else 2048 if 档 == "2K" else 1024)
    时代行 = f"\n时代背景：{时代}。确保还原后的画面符合该世界观设定。" if 时代 else ""
    时代行英 = f"\nERA / WORLD BACKGROUND: {时代}. Ensure all visual elements are consistent with this setting." if 时代 else ""
    比例行 = ""
    if 比例:
        方向 = "portrait, taller than wide" if 比例 == "9:16" else "landscape, wider than tall"
        比例行 = f"\nIMPORTANT: Output image MUST be {比例} aspect ratio ({方向})."

    通道 = (通道 or "英文").strip().lower()
    if 通道 in ("中文", "jimeng", "即梦"):
        return 超分中文.format(档=档, 时代=时代行.strip("\n"))
    if 通道 in ("gemini", "geminilab", "geminitab"):
        return 超分Gemini.format(档=档, 比例=比例行, 时代=时代行英)
    return 超分英文.format(档=档, 长边=长边) + 比例行 + 时代行英


# LLM 关键词提取的 system prompt（飞彩 x$ 逐字）
关键词系统提示 = """Extract the most visually distinctive elements from this image.
Focus on:
- Subject & characters (appearance, clothing, pose, expression)
- Art style & medium (e.g. anime, oil painting, photorealistic)
- Composition & camera angle
- Lighting & color palette
- Background & environment
- Mood & atmosphere

Rules:
- Output ONLY keywords, no explanations or sentences
- Maximum 200 characters total
- Focus on visually distinctive elements
- Use concise English phrases"""


def 超分(图路: str, 档: str = "4K", 通道: str = "英文", 比例: str = "", 时代: str = "",
         增强关键词: str = "", 强度: float | None = None, 模板: str = "qwen_edit",
         种子: int | None = None, 存到: str = "", 报=None, 空跑: bool = False,
         允许降级: bool = False) -> dict:
    """
    超分：把原图当**参考图**，+ 超分提示词，喂同一个图像模型。

    ★ 这不是 RealESRGAN，也不是任何本地放大器 —— 飞彩就是这么干的，
      上游 `知识\\一致性系统.md` 已实证，别再自己发明。

    增强关键词：非空走「二次超分」路径 —— 飞彩的二次超分是
      LLM 提关键词 + AI 画质增强，strength=0.35，且**必须先做过一次超分**。
      影匠没有 LLM 通道，关键词由调用方给（或从文件名/备注拿），
      没有关键词时只做固定后缀拼接。
    强度：不传=首次超分（改图模型默认去噪）；传 0.35 = 二次超分。

    ★ 允许降级（默认 False，**这是刻意的**）：
      引擎.文生图 在「参考图通道缺模型」时会**静默降级成纯文生图**，
      只打一行 ⚠，返回值里没有「降级了」这个字段。
      对超分来说这是**语义性的致命伤** —— 超分全靠「喂原图 + 复刻」，
      模型没看见原图就等于**重新生成**，飞彩那条
      `This is NOT image regeneration` 铁律在实现上直接不成立。
      所以默认**宁可报错也不出废图**；确实只想要「照着提示词重画一张」时，
      显式传 允许降级=True。
    """
    报 = 报 or (lambda _: None)
    图路 = os.path.abspath(图路)
    if not os.path.exists(图路):
        raise RuntimeError(f"找不到图：{图路}")
    档 = (档 or "4K").strip().upper()
    长边 = 4096 if 档 == "4K" else 2048 if 档 == "2K" else 1024

    提示 = 超分提示词(档=档, 通道=通道, 比例=比例, 时代=时代, 像素=长边)
    二次 = bool(增强关键词) or 强度 is not None
    if 二次:
        关键词 = (增强关键词 or "").strip()
        if 关键词:
            留 = max(0, 800 - len(二次超分后缀) - 2)
            提示 = f"{提示[:留]}\n{关键词[:200]}{二次超分后缀}"
            报(f"二次超分：关键词 {len(关键词[:200])} 字 + 固定后缀 {len(二次超分后缀)} 字")
        else:
            提示 = 提示 + 二次超分后缀
            报("二次超分：没给关键词，只拼固定后缀（影匠没有 LLM 通道，关键词得调用方给）")

    报(f"超分 {os.path.basename(图路)} → {档}（{长边}px 长边）  模型通道=同一个图像模型")
    报(f"  提示词铁律：This is NOT image regeneration. Do NOT redraw or reimagine")
    if 空跑:
        return {"路": "", "档": 档, "长边": 长边, "提示词": 提示, "空跑": True,
                "二次": 二次, "强度": 强度}

    if _引擎 is None:
        raise RuntimeError(f"引擎.py 载不进来，超分出不了：{_引擎错}")

    # ★ 参考图通道能不能用，先自己查 —— 不让它静默降级
    缺 = _引擎.模板缺什么(模板) if hasattr(_引擎, "模板缺什么") else []
    if 缺 and not 允许降级:
        raise RuntimeError(
            f"超分做不了：参考图通道不可用 —— 模板 {模板} 缺模型：{'；'.join(缺)}。\n"
            f"  超分靠「喂原图 + 复刻」，没有参考图通道就等于重新生成，"
            f"飞彩那条 `This is NOT image regeneration` 就不成立了。\n"
            f"  补上模型再跑；确实只想要「照着提示词重画一张」就显式传 --允许降级。")
    if 缺:
        报(f"⚠ 参考图通道不可用（{'；'.join(缺)}）—— 你显式要了降级，本次等于纯文生图重画")

    # 参考图槽位按 引擎.文生图 的规矩：图必须是本机绝对路径
    果 = _引擎.文生图(提示, 模板=模板, 种子=种子, 参考图=[图路], 前缀="影匠/超分",
                      报=报, 存到=(存到 or None))
    挂了 = 果.get("挂了几张")
    if not 缺 and not 挂了 and not 允许降级:
        raise RuntimeError(
            f"超分做不了：引擎报了成功，但参考图一张都没挂上（挂了几张={挂了!r}）——"
            f"产物是纯文生图重画，不是超分。要接受这种结果请显式传 --允许降级。")
    return {"路": 果["路"], "档": 档, "长边": 长边, "提示词": 提示, "二次": 二次,
            "强度": 强度, "种子": 果.get("种子"), "耗时": 果.get("耗时"), "空跑": False,
            "挂了参考图": 挂了, "降级": bool(缺) or not 挂了}


# ============================================================
# 六、拼工作流（H3 原生节点 / Wan 原生节点）
# ============================================================

H3_CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
H3_VAE_视频 = "minimax_h3_video_vae_int8_convrot.safetensors"
H3_VAE_音频 = "minimax_h3_audio_vae_fp32.safetensors"


def _H3骨架(模型档: dict, 提示词: str, 宽: int, 高: int, 帧数: int, 种子: int,
            用LoRA: bool = True, 步数=None) -> dict:
    """搭 H3 的公共骨架（照官方模板 video_minimax_h3_i2v.json 的接线，一处不改）。"""
    c = 模型档
    unet = c.get("模型") or "minimax_h3_fl2va_pruned_w6a8.safetensors"
    lora = c.get("LoRA")
    wf = {
        "6": {"class_type": "UNETLoader",
              "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "13": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": H3_CLIP, "type": "minimax", "device": "default"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": H3_VAE_视频}},
        "24": {"class_type": "VAELoader", "inputs": {"vae_name": H3_VAE_音频}},
        "15": {"class_type": "RandomNoise", "inputs": {"noise_seed": int(种子),
                                                       "control_after_generate": "fixed"}},
        "17": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "24n": {"class_type": "VAEDecodeAudio",
                "inputs": {"vae": ["24", 0], "samples": ["14", 0]}},
        "10": {"class_type": "VAEDecode", "inputs": {"vae": ["11", 0], "samples": ["14", 0]}},
        "91": {"class_type": "CreateVideo",
               "inputs": {"images": ["10", 0], "fps": float(H3_帧率), "audio": ["24n", 0],
                          "bit_depth": 8}},
    }
    模型源 = ["6", 0]
    if 用LoRA and lora:
        wf["121"] = {"class_type": "LoraLoaderModelOnly",
                     "inputs": {"model": ["6", 0], "lora_name": lora, "strength_model": 1.0}}
        模型源 = ["121", 0]
        if 步数 is None:
            步数 = 8 if "8step" in lora else (4 if "4step" in lora else 20)
    if 步数 is None:
        步数 = 20
    wf["9"] = {"class_type": "BasicScheduler",
               "inputs": {"model": 模型源, "scheduler": "simple", "steps": int(步数),
                          "denoise": 1.0}}
    wf["16"] = {"class_type": "BasicGuider", "inputs": {"model": 模型源}}
    wf["14"] = {"class_type": "SamplerCustomAdvanced",
                "inputs": {"noise": ["15", 0], "guider": ["16", 0], "sampler": ["17", 0],
                           "sigmas": ["9", 0]}}
    wf["92"] = {"class_type": "SaveVideo",
                "inputs": {"video": ["91", 0], "filename_prefix": "影匠片/H3",
                           "format": "auto", "codec": "auto"}}
    return wf


def 拼H3(提示词: str, 模式: str = "single", 宽: int = 1344, 高: int = 768, 帧数: int = 124,
         种子: int | None = None, 首帧: str | None = None, 尾帧: str | None = None,
         参考图们: list | None = None, 参考视频们: list | None = None,
         上传名们: dict | None = None, 用LoRA: bool = True, 模型档: dict | None = None,
         前缀: str = "影匠片/H3", 报=None) -> dict:
    """
    拼一个 H3 工作流。**上传已经在外面做完了** —— 这里只吃「ComfyUI input 里的文件名字」。

    模式：
      single     文生视频 / 图生视频（给首帧就是图生视频；给首帧+尾帧就是首尾帧）
      firstlast  同上，语义化别名
      multiref   全能参考（ref_images ≤9）
      v2v        视频参考（ref_videos ≤3）
    """
    报 = 报 or (lambda _: None)
    种子 = 种子 if 种子 is not None else random.randint(1, 2**31)
    上传名们 = 上传名们 or {}
    c = dict(模型档 or 模型能力表["minimax-h3-fl2va"])

    if 模式 in ("single", "firstlast"):
        wf = _H3骨架(c, 提示词, 宽, 高, 帧数, 种子, 用LoRA=用LoRA)
        wf["104"] = {"class_type": "MiniMaxH3ImageToVideo",
                     "inputs": {"clip": ["13", 0], "vae": ["11", 0], "prompt": 提示词,
                                "width": int(宽), "height": int(高), "length": int(帧数)}}
        wf["14"]["inputs"]["latent_image"] = ["104", 1]
        wf["16"]["inputs"]["conditioning"] = ["104", 0]
        if 首帧:
            名 = 上传名们.get(首帧) or 上传名们.get(os.path.abspath(首帧))
            if not 名:
                raise RuntimeError(f"首帧没上传成功：{首帧}")
            wf["113"] = {"class_type": "LoadImage", "inputs": {"image": 名}}
            wf["104"]["inputs"]["first_frame"] = ["113", 0]
        if 尾帧:
            名 = 上传名们.get(尾帧) or 上传名们.get(os.path.abspath(尾帧))
            if not 名:
                raise RuntimeError(f"尾帧没上传成功：{尾帧}")
            wf["114"] = {"class_type": "LoadImage", "inputs": {"image": 名}}
            wf["104"]["inputs"]["last_frame"] = ["114", 0]
        wf["92"]["inputs"]["filename_prefix"] = 前缀
        return wf

    if 模式 in ("multiref", "v2v", "batchRelay"):
        c2 = 模型能力表["minimax-h3-ref2va"] if 模式 in ("multiref", "batchRelay") else c
        wf = _H3骨架(c2, 提示词, 宽, 高, 帧数, 种子, 用LoRA=用LoRA)
        wf["136"] = {"class_type": "MiniMaxH3ReferenceToVideo",
                     "inputs": {"clip": ["13", 0], "prompt": 提示词, "width": int(宽),
                                "height": int(高), "length": int(帧数), "ref_image_size": "match"}}
        wf["136"]["inputs"]["vae"] = ["11", 0]
        wf["136"]["inputs"]["audio_vae"] = ["24", 0]
        wf["125"] = {"class_type": "EmptyMiniMaxH3LatentAV",
                     "inputs": {"width": int(宽), "height": int(高), "length": int(帧数)}}
        wf["14"]["inputs"]["latent_image"] = ["125", 0]
        wf["16"]["inputs"]["conditioning"] = ["136", 0]
        槽 = 0
        for i, p in enumerate(参考图们 or []):
            名 = 上传名们.get(p) or 上传名们.get(os.path.abspath(p))
            if not 名:
                raise RuntimeError(f"参考图没上传成功：{p}")
            号 = f"20{i}"
            wf[号] = {"class_type": "LoadImage", "inputs": {"image": 名}}
            wf["136"]["inputs"][f"ref_image_{i}"] = [号, 0]
            槽 += 1
        if 槽 > 9:
            raise RuntimeError(f"ref_images 上限 9 张，给了 {槽} 张（ComfyUI 节点 tooltip 逐字：max 9）")
        for i, p in enumerate(参考视频们 or []):
            名 = 上传名们.get(p) or 上传名们.get(os.path.abspath(p))
            if not 名:
                raise RuntimeError(f"参考视频没上传成功：{p}")
            号 = f"30{i}"
            wf[号] = {"class_type": "LoadVideo", "inputs": {"file": 名}}
            wf[f"31{i}"] = {"class_type": "GetVideoComponents", "inputs": {"video": [号, 0]}}
            wf["136"]["inputs"][f"ref_video_{i}"] = [f"31{i}", 0]
        if len(参考视频们 or []) > 3:
            raise RuntimeError("ref_videos 上限 3 条（ComfyUI 节点 tooltip 逐字：max 3）")
        wf["92"]["inputs"]["filename_prefix"] = 前缀
        return wf

    raise ValueError(f"不认识模式「{模式}」。飞彩的创作模式：{' / '.join(模式白名单)}")


def 拼Wan(提示词: str, 负面: str = "", 模式: str = "single", 宽: int = 832, 高: int = 480,
          帧数: int = 49, 种子: int | None = None, 首帧: str | None = None,
          尾帧: str | None = None, 上传名们: dict | None = None, 模型档: dict | None = None,
          帧率: int = 16, 前缀: str = "影匠片/Wan", 步数: int = 20, cfg: float = 5.0) -> dict:
    """
    Wan2.2 TI2V-5B 通道（影匠原有那条）。首尾帧走 `WanFirstLastFrameToVideo` 节点 ——
    ★ 影匠现状：模板 `wan22_i2v.json` 用的是 `Wan22ImageToVideoLatent`（**只有首帧**），
      引擎.图生视频 虽然认 `WanFirstLastFrameToVideo` 这个类名，但模板里没有它，
      所以走不到尾帧。这里把尾帧这条真接上。
    注意节点签名（问 /object_info 得的，不是猜的）：
      WanFirstLastFrameToVideo: positive / negative / vae / width(step16) / height(step16) /
                                length(step4) / batch_size / [start_image] / [end_image]
    """
    种子 = 种子 if 种子 is not None else random.randint(1, 2**31)
    上传名们 = 上传名们 or {}
    c = dict(模型档 or 模型能力表["wan2.2-ti2v-5b"])
    wf = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": c.get("模型", "wan2.2_ti2v_5B_fp16.safetensors"),
                         "weight_dtype": "default"}},
        "2": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "3": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": 提示词}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["3", 0], "text": 负面 or "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，"
                                                    "静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的"}},
        "9": {"class_type": "KSampler",
              "inputs": {"model": ["2", 0], "positive": ["6", 0], "negative": ["7", 0],
                         "latent_image": ["8", 2] if 模式 != "single" or 尾帧 else ["8", 0],
                         "seed": 种子, "steps": int(步数), "cfg": float(cfg),
                         "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["4", 0]}},
        "11": {"class_type": "CreateVideo", "inputs": {"images": ["10", 0], "fps": float(帧率)}},
        "12": {"class_type": "SaveVideo",
               "inputs": {"video": ["11", 0], "filename_prefix": 前缀, "format": "auto",
                          "codec": "auto"}},
    }
    if 尾帧:
        wf["8"] = {"class_type": "WanFirstLastFrameToVideo",
                   "inputs": {"positive": ["6", 0], "negative": ["7", 0], "vae": ["4", 0],
                              "width": int(宽), "height": int(高), "length": int(帧数),
                              "batch_size": 1}}
        wf["9"]["inputs"]["latent_image"] = ["8", 2]
    else:
        wf["8"] = {"class_type": "Wan22ImageToVideoLatent",
                   "inputs": {"vae": ["4", 0], "width": int(宽), "height": int(高),
                              "length": int(帧数), "batch_size": 1}}
        wf["9"]["inputs"]["latent_image"] = ["8", 0]
    if 首帧:
        名 = 上传名们.get(首帧) or 上传名们.get(os.path.abspath(首帧))
        if not 名:
            raise RuntimeError(f"首帧没上传成功：{首帧}")
        wf["5"] = {"class_type": "LoadImage", "inputs": {"image": 名}}
        wf["8"]["inputs"]["start_image"] = ["5", 0]
    if 尾帧:
        名 = 上传名们.get(尾帧) or 上传名们.get(os.path.abspath(尾帧))
        if not 名:
            raise RuntimeError(f"尾帧没上传成功：{尾帧}")
        wf["5b"] = {"class_type": "LoadImage", "inputs": {"image": 名}}
        wf["8"]["inputs"]["end_image"] = ["5b", 0]
    return wf


# ============================================================
# 六点五、本地前置校验（提交前先把 ComfyUI 会拒的接错揪出来）
# ============================================================

_节点规格缓存: dict = {}


def 节点规格(刷新: bool = False) -> dict:
    """问 ComfyUI 要 /object_info（节点签名表）。缓存一份，自测里反复用。"""
    if _节点规格缓存 and not 刷新:
        return _节点规格缓存
    import urllib.request

    with urllib.request.urlopen(f"{COMFY}/object_info", timeout=60) as r:
        数 = json.loads(r.read().decode("utf-8", "replace"))
    _节点规格缓存.clear()
    _节点规格缓存.update(数)
    return _节点规格缓存


def _规格字段(定义: dict):
    """把 input 定义整成 {名: (类型, 是否必填)} + 默认值表。"""
    必填 = {}
    默认 = {}
    段 = 定义.get("input") or {}
    for 组 in ("required", "optional"):
        for 名, 项 in (段.get(组) or {}).items():
            型 = 项[0] if isinstance(项, (list, tuple)) and 项 else 项
            if isinstance(型, list):  # COMBO：选项表
                型 = f"COMBO[{len(型)}]"
            if 组 == "required":
                必填[名] = 型
            # 默认值：必填组里第 2 项是 dict 且带 default
            if isinstance(项, (list, tuple)) and len(项) > 1 and isinstance(项[1], dict) \
                    and "default" in 项[1]:
                默认[名] = 项[1]["default"]
    return 必填, 默认


def 校验工作流(wf: dict, 规格表: dict | None = None) -> list:
    """
    本地把工作流过一遍，返回**问题清单**（空 = 能交）。

    ★ 为什么非要这一层：ComfyUI 的 400 只告诉你「required_input_missing」，
      但等你看到它的时候活儿已经交出去一次了。而且真跑那次暴露的坑很隐蔽 ——
      「节点都在、连线也不悬空」这条检查**照样全绿**，因为 `VAEDecodeAudio` 和
      `VAEDecode` 是**建在骨架里、输入字典是空的**：节点在、引用不悬空，
      但必填的 `vae`/`samples` 一个都没接。于是 400。
    所以这里查三件事：
      ① 每个节点名都得在 /object_info 里（叫错类名当场揪出来）；
      ② **必填输入一个都不能少**（这才是那次 400 的真凶）；
      ③ 连线指向的节点必须存在，槽位号不能越界（负号 = 输出占位，放行）。
    """
    问题 = []
    表 = 规格表 if 规格表 is not None else 节点规格()
    for 号, 节 in (wf or {}).items():
        类 = (节 or {}).get("class_type")
        if not 类:
            问题.append(f"节点 {号} 没有 class_type")
            continue
        定义 = 表.get(类)
        if 定义 is None:
            问题.append(f"节点 {号} 的类「{类}」本机没有 —— 名字拼错了，或者没装")
            continue
        必填, _ = _规格字段(定义)
        进了 = set(((节 or {}).get("inputs") or {}).keys())
        缺 = [x for x in 必填 if x not in 进了]
        if 缺:
            问题.append(f"节点 {号}({类}) 缺必填输入：{'、'.join(sorted(缺))}")
        出数 = len(定义.get("output") or [])
        for 名, 值 in ((节 or {}).get("inputs") or {}).items():
            if not (isinstance(值, (list, tuple)) and len(值) == 2
                    and isinstance(值[0], str)):
                continue
            源, 槽 = 值[0], 值[1]
            if 源.startswith("-"):
                continue
            if 源 not in wf:
                问题.append(f"节点 {号}({类}) 的 {名} 指向不存在的节点 {源}")
                continue
            源类 = (wf[源] or {}).get("class_type")
            源出 = len((表.get(源类) or {}).get("output") or [])
            if 源出 and isinstance(槽, int) and (槽 < 0 or 槽 >= 源出):
                问题.append(f"节点 {号}({类}) 的 {名} 取了 {源}({源类}) 的槽 {槽}，"
                             f"但它只有 {源出} 个输出")
    return 问题


# ============================================================
# 七、上传（图 / 视频 / 音频都用它）+ 出片
# ============================================================

def 上传(路: str, 类别: str = "input") -> dict:
    """
    把本地文件塞进 ComfyUI 的 input 目录。返回 {name, subfolder, type}。

    ★ 为什么不用 引擎.上传图：
      1) 它只发 `image` 字段、MIME 猜图 —— 视频/音频塞不进去（LoadVideo 要 mp4）；
      2) 中文文件名在 HTTP 头里是 latin-1 的雷 —— 这里跟它一样重命名成
         `yjs_<内容哈希>.<后缀>`，顺便自带去重（同内容只传一份）。
      服务端 `/upload/image` 的实现（server.py:400 image_upload）**不校验类型**，
      原样 `image.file.read()` 落盘，所以名字虽然叫 image，视频也能进。
    """
    import hashlib
    import mimetypes
    import uuid

    路 = os.path.abspath(路)
    if not os.path.exists(路):
        raise RuntimeError(f"找不到文件：{路}")
    with open(路, "rb") as f:
        内容 = f.read()
    if not 内容:
        raise RuntimeError(f"文件是空的：{路}")
    后缀 = os.path.splitext(路)[1].lower() or ".bin"
    名 = f"yjs_{hashlib.md5(内容).hexdigest()[:12]}{后缀}"
    类 = mimetypes.guess_type(名)[0] or "application/octet-stream"

    界 = "----yjs" + uuid.uuid4().hex
    体 = b"".join([
        f"--{界}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{名}"\r\n'.encode("ascii"),
        f"Content-Type: {类}\r\n\r\n".encode("ascii"),
        内容,
        f"\r\n--{界}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        COMFY + "/upload/image", data=体,
        headers={"Content-Type": f"multipart/form-data; boundary={界}"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            果 = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"上传失败 {e.code}：{e.read().decode('utf-8', 'replace')[:400]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"连不上 ComfyUI（{COMFY}）：{e}") from None
    果.setdefault("name", 名)
    名全 = 果["name"]
    if 果.get("subfolder"):
        名全 = f"{果['subfolder']}/{果['name']}"
    果["全名"] = 名全
    return 果


def _文本模型(模型: str) -> str:
    """别名归一：用户敲 h3 / 首尾 / minimax 都能落到表里的键。"""
    模型 = (模型 or "minimax-h3-fl2va").strip()
    if 模型 in 模型能力表:
        return 模型
    低 = 模型.lower()
    别名 = {"h3": "minimax-h3-fl2va", "minimax": "minimax-h3-fl2va",
            "fl2va": "minimax-h3-fl2va", "flf": "minimax-h3-fl2va",
            "ref2va": "minimax-h3-ref2va", "r2v": "minimax-h3-ref2va",
            "wan": "wan2.2-ti2v-5b", "wan2.2": "wan2.2-ti2v-5b", "ti2v": "wan2.2-ti2v-5b"}
    if 低 in 别名:
        return 别名[低]
    for k in 模型能力表:
        if 低 and 低 in k.lower():
            return k
    raise ValueError(f"不认识模型「{模型}」。本机能跑的："
                     f"{' / '.join(k for k, v in 模型能力表.items() if v.get('本机'))}")


def 出片(提示词: str, 模型: str = "minimax-h3-fl2va", 模式: str = "single",
         首帧: str = "", 尾帧: str = "", 参考图们: list | None = None,
         参考视频们: list | None = None, 时长=5, 比例: str = "16:9", 宽: int = 0, 高: int = 0,
         档: str = "", 分辨率: str = "", 帧率=None, 运镜: str = "", 景别: str = "",
         转场: str = "", 节奏: str = "", 时代: str = "", 种子: int | None = None,
         步数=None, 用LoRA: bool = True, 存到: str = "", 空跑: bool = False,
         上限秒: int = 3600, 报=None) -> dict:
    """
    出一条片子。参数照飞彩的能力位走，尺寸/帧数一律先过 规格()。

    返回 {路, 种子, 耗时, 规格, 提示词, 模式, 模型, 模板, 空跑}。
    """
    报 = 报 or (lambda _: None)
    模型 = _文本模型(模型)
    c = 模型能力表[模型]
    模式 = (模式 or "single").strip()
    if 模式 not in 模式白名单:
        raise ValueError(f"不认识模式「{模式}」。飞彩的创作模式：{' / '.join(模式白名单)}")
    允许模式 = c.get("modes") or []
    if 允许模式 and 模式 not in 允许模式:
        raise ValueError(f"模型 {模型} 不支持模式「{模式}」（它支持：{'/'.join(允许模式)}）")
    if 模式 == "firstlast" and not 尾帧:
        报("⚠ 模式 firstlast 但没给尾帧 —— 按单帧图生视频走（飞彩那边缺尾帧也是这个行为）")

    规 = 规格(时长=时长, 比例=比例, 模型=模型, 分辨率=分辨率, 帧率=帧率,
              宽=宽, 高=高, 档=档)
    for w in 规["警告们"]:
        报(f"⚠ {w}")
    长提示 = 拼提示词(提示词, 运镜=运镜, 景别=景别, 转场=转场, 节奏=节奏,
                      时长秒=规["秒"], 时代=时代)

    报(f"模型 {模型}  模式 {模式}  {规['宽']}×{规['高']}  {规['帧数']}帧 @{规['帧率']}fps "
       f"≈{规['秒']:.2f} 秒")
    if 规["钳过"]:
        报(f"（你要 {时长} 秒，模型给 {规['秒']:.2f} 秒）")

    骨 = {"路": "", "种子": 种子, "耗时": 0.0, "规格": 规, "提示词": 长提示,
          "模式": 模式, "模型": 模型, "模板": "程序拼（不走 模板/*.json）", "空跑": bool(空跑)}
    if 空跑:
        报("[空跑] 不碰 ComfyUI")
        return 骨
    if _引擎 is None:
        raise RuntimeError(f"引擎.py 载不进来：{_引擎错}")

    上传名们 = {}
    for p in [x for x in (首帧, 尾帧) if x] + list(参考图们 or []) + list(参考视频们 or []):
        if not os.path.isabs(p):
            raise RuntimeError(f"必须是本机绝对路径：{p}")
        果 = 上传(p)
        上传名们[p] = 果["全名"]
        上传名们[os.path.abspath(p)] = 果["全名"]
        报(f"上传 {os.path.basename(p)} → {果['全名']}")

    种子 = 种子 if 种子 is not None else random.randint(1, 2**31)
    骨["种子"] = 种子
    前缀 = f"影匠片/{os.path.splitext(os.path.basename(首帧 or 尾帧 or 模型))[0]}"
    if c.get("family") == "h3":
        wf = 拼H3(长提示, 模式=模式, 宽=规["宽"], 高=规["高"], 帧数=规["帧数"], 种子=种子,
                  首帧=首帧 or None, 尾帧=尾帧 or None, 参考图们=参考图们,
                  参考视频们=参考视频们, 上传名们=上传名们, 用LoRA=用LoRA, 模型档=c,
                  前缀=前缀, 报=报)
    else:
        wf = 拼Wan(长提示, 模式=模式, 宽=规["宽"], 高=规["高"], 帧数=规["帧数"], 种子=种子,
                   首帧=首帧 or None, 尾帧=尾帧 or None, 上传名们=上传名们, 模型档=c,
                   帧率=规["帧率"], 步数=步数 or 20, 前缀=前缀)

    报(f"提交 {len(wf)} 个节点：" + ",".join(f"{k}:{v['class_type']}" for k, v in sorted(wf.items(), key=lambda x: str(x[0]))))
    # ★ 交出去之前先自查 —— 真跑那次就是「节点都在、连线也不悬空」全绿，
    #   结果 VAEDecodeAudio/VAEDecode 的必填输入空着，白挨一个 400。
    毛病 = 校验工作流(wf)
    if 毛病:
        raise RuntimeError("工作流自查没过，没提交（省一次往返）：\n  · " + "\n  · ".join(毛病))
    果 = _引擎.派工(wf, 报=报, 上限秒=上限秒)
    出 = 果["图们"][0]
    if not 存到:
        os.makedirs(视频目录, exist_ok=True)
        存到 = os.path.join(视频目录, f"{datetime.now():%m%d-%H%M%S}-{种子}.mp4")
    路 = _引擎.取图(出, 存到)
    报(f"出片：{os.path.basename(路)}  {os.path.getsize(路)/1048576:.1f} MB  {果['耗时']}s")
    骨.update({"路": 路, "耗时": 果["耗时"], "原始": 出, "提示号": 果["提示号"]})
    return 骨


def 文生视频(提示词: str, **kw) -> dict:
    """纯文生视频。飞彩的 `single` 没图时也是先出首帧再图生视频 —— 这里走 H3 原生。"""
    kw.setdefault("模型", "minimax-h3-fl2va")
    kw["模式"] = "single"
    return 出片(提示词, **kw)


def 图生视频(图路: str, 动作描述: str = "", **kw) -> dict:
    """图生视频（单首帧）。"""
    kw.setdefault("模型", "minimax-h3-fl2va")
    kw["模式"] = "single"
    kw["首帧"] = 图路
    return 出片(动作描述 or "镜头内的自然运动，主体保持动作连贯", **kw)


def 首尾帧(首帧: str, 尾帧: str, 动作描述: str = "", **kw) -> dict:
    """
    首尾帧生视频 —— 飞彩的 `firstlast`，影匠之前**没有**的那一条。

    机制：H3 的 `MiniMaxH3ImageToVideo` 原生有两个可选槽 first_frame / last_frame，
    首尾都锚上，模型自己把中间补出来。不用外挂 FLF2V 模型。
    """
    kw.setdefault("模型", "minimax-h3-fl2va")
    kw["模式"] = "firstlast"
    kw["首帧"] = 首帧
    kw["尾帧"] = 尾帧
    return 出片(动作描述 or "从首帧自然过渡到尾帧，动作连贯不断裂", **kw)


def 全能参考(参考图们: list, 提示词: str = "", **kw) -> dict:
    """飞彩的 `multiref`（参考图生视频）。ref_images ≤9。"""
    kw.setdefault("模型", "minimax-h3-ref2va")
    kw["模式"] = "multiref"
    kw["参考图们"] = list(参考图们 or [])
    return 出片(提示词 or "Keep the referenced subjects exactly as they are; add natural motion only",
                **kw)


def 视频参考(参考视频们: list, 提示词: str = "", **kw) -> dict:
    """飞彩的 `v2v`（视频参考 / 视频生视频）。ref_videos ≤3。"""
    kw.setdefault("模型", "minimax-h3-ref2va")
    kw["模式"] = "v2v"
    kw["参考视频们"] = list(参考视频们 or [])
    return 出片(提示词 or "Restyle the referenced video, keeping its motion and timing",
                **kw)


# ============================================================
# 八、取末帧 / 接龙（没有 ffmpeg 也能干）
# ============================================================

def 取末帧(视频路: str, 存到: str = "", 第几帧: int = -1, 空跑: bool = False,
           上限秒: int = 900, 报=None) -> str:
    """
    从一段 mp4 里抠出一帧（默认末帧）存成 png。

    ★ 本机没有 ffmpeg，所以走 ComfyUI：上传 mp4 → LoadVideo → GetVideoComponents
      → ImageFromBatch → SaveImage。纯 HTTP，不需要任何本地解码器。
      （这也是为什么「转场/接龙」能在这台机器上成立。）
    """
    报 = 报 or (lambda _: None)
    视频路 = os.path.abspath(视频路)
    if not os.path.exists(视频路):
        raise RuntimeError(f"找不到视频：{视频路}")
    if not 存到:
        os.makedirs(视频目录, exist_ok=True)
        存到 = os.path.join(视频目录, os.path.splitext(os.path.basename(视频路))[0] + f"_帧{第几帧}.png")
    if 空跑:
        报(f"[空跑] 取帧 {os.path.basename(视频路)} → {os.path.basename(存到)}")
        return 存到
    if _引擎 is None:
        raise RuntimeError(f"引擎.py 载不进来：{_引擎错}")
    上 = 上传(视频路)
    报(f"上传 {os.path.basename(视频路)} → {上['全名']}")
    wf = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": 上["全名"]}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "ImageFromBatch",
              "inputs": {"image": ["2", 0], "batch_index": int(第几帧), "length": 1}},
        "4": {"class_type": "SaveImage",
              "inputs": {"images": ["3", 0], "filename_prefix": "影匠片/末帧"}},
    }
    果 = _引擎.派工(wf, 报=报, 上限秒=上限秒)
    路 = _引擎.取图(果["图们"][0], 存到)
    报(f"取帧：{os.path.basename(路)}")
    return 路


def 接龙(片子们: list, 转场: str = "直接切", 节奏: str = "", 模型: str = "",
         时长=0, 报=None, 空跑: bool = False, 上限秒: int = 3600) -> dict:
    """
    把几段片子接成一串连续镜头（飞彩的「转场」在影匠的落地方式）。

    ★ 飞彩和影匠都没有本地 ffmpeg 拼接这一层，而且飞彩把「过渡」归在**镜头语汇**里、
      把「节奏时序」做成提示词档。所以这里的真机制是：
        1) 取「上一段片子的末帧」→ 当「下一段片子的首帧」喂首尾帧模式（硬衔接的真做法）；
        2) 转场词进提示词（叠化/淡入黑场/白闪/匹配剪辑…）；
        3) 节奏档进提示词（一镜到底/起承转合/快切多段/渐入渐出）。
      想真拼成一个 mp4 得有 ffmpeg —— 本机没有，这里不假装有。
    """
    报 = 报 or (lambda _: print("   ", _))
    转 = 转场提示(转场)
    如果 = []
    for i, p in enumerate(片子们):
        p = os.path.abspath(p)
        if not os.path.exists(p):
            raise RuntimeError(f"找不到片子：{p}")
        如果.append({"序": i + 1, "路": p,
                     "秒": 时长 or _mp4秒数(p),
                     "转场": "" if i == 0 else 转["词"],
                     "转场文案": "" if i == 0 else 转["文案"],
                     "接法": "" if i == 0 else 转["手法"]})
    首 = os.path.splitext(os.path.basename(片子们[0]))[0]
    计划 = {
        "片数": len(如果),
        "总秒": round(sum(x["秒"] for x in 如果), 2),
        "转场": 转["词"], "手法": 转["手法"], "节奏": 节奏 or "（不指定）",
        "镜头": 如果,
        "说明": "本机无 ffmpeg：硬衔接靠「上镜末帧 = 下镜首帧」；转场在提示词层实现。"
                "要真出一个合并 mp4，得装 ffmpeg（或用 ComfyUI 的 LoadVideo→ImageBatch→CreateVideo 通道）。",
    }
    if 空跑:
        计划["空跑"] = True
        return 计划
    计划["末帧们"] = []
    for i, x in enumerate(如果[:-1]):
        try:
            帧 = 取末帧(x["路"], 报=报)
            计划["末帧们"].append({"从": x["路"], "末帧": 帧, "喂给": 如果[i + 1]["路"]})
        except Exception as e:  # noqa: BLE001
            报(f"⚠ 第 {i+1} 段末帧没取到（{e}）—— 这一段跟下一段接不上，但不影响已出的片子")
            计划["末帧们"].append({"从": x["路"], "末帧": "", "错": str(e)})
    return 计划


def _mp4秒数(路: str) -> float:
    """
    纯标准库读 mp4 时长（mvhd box）。
    读不出来返回 0.0 —— **不抛**：时长只是报告用的，不该让接龙整条挂掉。
    """
    try:
        with open(路, "rb") as f:
            头 = f.read(4096)
        i = 头.find(b"mvhd")
        if i < 0:
            return 0.0
        节 = 头[i + 4:i + 4 + 32]
        版 = 节[0]
        if 版 == 1:
            刻度 = int.from_bytes(节[20:24], "big")
            时长 = int.from_bytes(节[24:32], "big")
        else:
            刻度 = int.from_bytes(节[12:16], "big")
            时长 = int.from_bytes(节[16:20], "big")
        return round(时长 / 刻度, 3) if 刻度 else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


# ============================================================
# 八·五、剪辑层转场 / 接片（ffmpeg —— 不占卡）
# ============================================================
#
# ★ 这一层是**影匠自建**，不是对齐飞彩，也不许写成对齐飞彩。
#   飞彩全量 grep（`转场|叠化|淡入|淡出|硬切|黑场|渐隐|渐显|交叉溶解|切黑|闪白|过渡方式`）
#   的结论是「**零本地实现**」：转场在飞彩里只是 ①分镜模板要求输出的一个字段、
#   ②`remainingInstruction` 的一句「或完成平滑转场」、③提示词扩写器的一个维度。
#   真正的镜间融合飞彩没做。所以下面这些转场是**影匠补空白**，标注必须老实。
#
# ★ 为什么用 ffmpeg 而不是 ComfyUI：转场是**剪辑层**的事，不该占卡。
#   （`_bin\ffmpeg.exe`，6.1.1-essentials_build-www.gyan.dev，82.8 MB，本机已就位。）

def ffmpeg路() -> str:
    """找 ffmpeg。依次看：环境变量 → `_bin\\ffmpeg.exe` → 飞彩解包里那份 → PATH。"""
    候选 = [
        os.environ.get("影匠_FFMPEG", ""),
        os.path.join(_根, "_bin", "ffmpeg.exe"),
        os.path.join(_根, "_bin", "ffmpeg"),
        r"D:\DSHworkspace\素材\网盘\_飞彩解包\Win\node_modules\ffmpeg-static\ffmpeg.exe",
        "ffmpeg",
    ]
    for c in 候选:
        if not c:
            continue
        if c == "ffmpeg" or os.path.exists(c):
            return c
    return ""


FFMPEG = ffmpeg路()


# 转场表：中文名 → ffmpeg xfade 的 transition 字面量（本机 6.1.1 实测 17/17 都跑得动）
# `xfade` 为空串 = 硬切，走 concat demuxer（不重编码，最快）
剪辑转场表 = {
    "硬切": {"xfade": "", "名": "硬切", "说明": "直接切，无融合（concat demuxer，不重编码）"},
    "交叉溶解": {"xfade": "fade", "名": "交叉溶解", "说明": "两画面交叉淡变（xfade=fade）"},
    "叠化": {"xfade": "dissolve", "名": "叠化", "说明": "带噪点感的软溶解（xfade=dissolve，比 fade 更「化学」）"},
    "淡入淡出": {"xfade": "fadeblack", "名": "淡入淡出（黑场）", "说明": "先淡到黑再淡出（xfade=fadeblack）"},
    "黑场过渡": {"xfade": "fadeblack", "名": "黑场过渡", "说明": "同 fadeblack；语义上强调「中间是纯黑」"},
    "闪白": {"xfade": "fadewhite", "名": "闪白", "说明": "过曝白帧盖住切换（xfade=fadewhite）"},
    "划像": {"xfade": "wipeleft", "名": "划像（左）", "说明": "硬边从左往右扫过（xfade=wipeleft）"},
    "划像右": {"xfade": "wiperight", "名": "划像（右）", "说明": "硬边从右往左扫过（xfade=wiperight）"},
    "推入": {"xfade": "slideleft", "名": "推入", "说明": "新画面从右侧推入（xfade=slideleft）"},
    "拉出": {"xfade": "slideup", "名": "拉出（上）", "说明": "新画面从下往上拉入（xfade=slideup）"},
    "平滑推": {"xfade": "smoothleft", "名": "平滑推", "说明": "带缓入缓出的推（xfade=smoothleft）"},
    "圆形开幕": {"xfade": "circleopen", "名": "圆形开幕", "说明": "从中心圆扩开（xfade=circleopen）"},
    "径向": {"xfade": "radial", "名": "径向", "说明": "径向扫过（xfade=radial）"},
    "放大切入": {"xfade": "zoomin", "名": "放大切入", "说明": "旧画面放大淡出（xfade=zoomin）"},
    "像素化": {"xfade": "pixelize", "名": "像素化", "说明": "马赛克过渡（xfade=pixelize）"},
    "模糊过渡": {"xfade": "hblur", "名": "模糊过渡", "说明": "横向模糊拉丝（xfade=hblur）"},
    "挤压": {"xfade": "squeezev", "名": "挤压", "说明": "纵向挤压（xfade=squeezev）"},
    "匹配剪辑": {"xfade": "", "名": "匹配剪辑", "说明": "不做融合 —— 靠剪辑点本身对上（硬切的语义版）"},
}

# 硬切/匹配剪辑 = 无融合；其余都走 xfade
剪辑转场别名 = {
    "cut": "硬切", "none": "硬切", "无": "硬切", "直接切": "硬切",
    "dissolve": "叠化", "融化": "叠化", "crossdissolve": "交叉溶解", "cross": "交叉溶解",
    "fade": "交叉溶解", "淡入淡出黑场": "淡入淡出", "fadeblack": "淡入淡出",
    "black": "黑场过渡", "黑": "黑场过渡",
    "fadewhite": "闪白", "flash": "闪白", "白闪": "闪白",
    "wipe": "划像", "wipeleft": "划像", "wiperight": "划像右",
    "slideleft": "推入", "推": "推入", "slideup": "拉出", "拉": "拉出",
    "smoothleft": "平滑推", "circleopen": "圆形开幕", "radial": "径向",
    "zoomin": "放大切入", "pixelize": "像素化", "hblur": "模糊过渡",
    "squeezev": "挤压", "match": "匹配剪辑", "匹配": "匹配剪辑",
}


def 规整剪辑转场(s: str) -> str:
    """用户怎么写都能落成一个剪辑转场名。不认识就报错（别静默丢）。"""
    s = (s or "").strip()
    if not s:
        return "硬切"
    if s in 剪辑转场表:
        return s
    k = 剪辑转场别名.get(s.lower(), 剪辑转场别名.get(s))
    if k:
        return k
    for 名, v in 剪辑转场表.items():          # xfade 原生名也认
        if v["xfade"] and v["xfade"] == s.lower():
            return 名
    raise ValueError(f"不认识的剪辑转场「{s}」。认得这些：{' / '.join(剪辑转场表)}")


def 列剪辑转场() -> list:
    return [{"词": k, **v} for k, v in 剪辑转场表.items()]


def _跑ffmpeg(参数: list, 超时: int = 1800) -> tuple:
    """跑 ffmpeg，返回 (退出码, stderr)。stderr 里有 ffmpeg 的全部诊断。"""
    import subprocess
    if not FFMPEG:
        raise RuntimeError("找不到 ffmpeg：设 影匠_FFMPEG，或把 ffmpeg.exe 放到 _bin\\ 下")
    r = subprocess.run([FFMPEG, "-hide_banner", "-y", *参数],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=超时)
    return r.returncode, (r.stderr or "")


def 探视频(路: str) -> dict:
    """问 ffmpeg 要时长 / 帧率 / 尺寸 / 有没有音轨 / 编码。纯解析 stderr。"""
    import re as _re
    路 = os.path.abspath(路)
    if not os.path.exists(路):
        raise RuntimeError(f"找不到视频：{路}")
    _, 文 = _跑ffmpeg(["-i", 路], 超时=120)
    d = {"路": 路, "名": os.path.basename(路), "字节": os.path.getsize(路),
         "秒": 0.0, "帧率": 0.0, "宽": 0, "高": 0, "有音频": False,
         "视频编码": "", "音频编码": ""}
    m = _re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", 文)
    if m:
        d["秒"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = _re.search(r"Video:\s*([A-Za-z0-9_]+)", 文)
    if m:
        d["视频编码"] = m.group(1)
    m = _re.search(r"Audio:\s*([A-Za-z0-9_]+)", 文)
    if m:
        d["有音频"] = True
        d["音频编码"] = m.group(1)
    m = _re.search(r"(\d+(?:\.\d+)?)\s*fps", 文)
    if m:
        d["帧率"] = float(m.group(1))
    m = _re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", 文, _re.S)
    if m:
        d["宽"], d["高"] = int(m.group(1)), int(m.group(2))
    return d


def 归一视频(入: str, 出p: str, 宽: int, 高: int, 帧率: float,
             补静音: bool = True, 质量: int = 18) -> str:
    """
    把任意一段 mp4 规整成「固定尺寸 / 固定帧率 / 立体声 48k / yuv420p」。

    ★ 为什么必须归一：接片的两段常常不同源 —— 实测
      `真跑_叶云_wan.mp4` 是 1280x720 @16fps **无音轨**，
      `真跑_首尾帧_红球.mp4` 是 1344x768 @24fps **有音轨**。
      xfade 硬要求同尺寸同帧率，acrossfade 硬要求两边都有音轨；
      不先归一，只会在 filter_complex 里炸得莫名其妙。
    方案：等比缩放 + 居中补黑边（不裁内容），没音轨的补 anullsrc 静音。
    """
    vf = (f"scale={宽}:{高}:force_original_aspect_ratio=decrease,"
          f"pad={宽}:{高}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={帧率}")
    参 = ["-i", 入]
    # ★ 2026-10-14 修的一个**静默毁音** bug：老代码在 `补静音` 为真时无条件
    #   `-map 1:a:0`，也就是**永远拿 anullsrc 的静音顶掉输入自己的音轨**，
    #   从来没 map 过 `0:a:0`。后果：H3 出的每一格都自带雨声/脚步/环境音，
    #   归一化这步**一声不响地全换成数字静音**，接片那边 `有音=True`、
    #   输出也真有音频流，日志全绿 —— 只有拿 volumedetect 量才发现是 -91 dB。
    #   正确语义：输入有音就留输入的，没有才补静音（acrossfade 要求两边都有轨）。
    有音 = 探视频(入)["有音频"]
    if 有音:
        参 += ["-map", "0:v:0", "-map", "0:a:0"]
    elif 补静音:
        参 += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
               "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    else:
        参 += ["-map", "0:v:0"]
    参 += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", str(质量),
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
           出p]
    码, 文 = _跑ffmpeg(参)
    if 码 != 0 or not os.path.exists(出p):
        raise RuntimeError(f"归一化失败（{os.path.basename(入)}）：{文.strip()[-400:]}")
    # ★ 复验：输入有音、输出却是静的 → 当场抛，别让它静默地一路混到成片里
    if 有音:
        出音 = 探视频(出p)["有音频"]
        入响 = _响度(入)
        出响 = _响度(出p)
        if (not 出音) or (入响 > 0.002 and 出响 < 0.002):
            raise RuntimeError(
                f"归一化把音轨吃掉了：{os.path.basename(入)} 有效值 {入响:.4f} → "
                f"{os.path.basename(出p)} 有效值 {出响:.4f}（有音轨={出音}）")
    return 出p


def _响度(路: str) -> float:
    """量一段片子中间 2 秒的有效值（线性）。用来抓「音轨被吃掉了」这类静默故障。"""
    import re as _re
    秒 = 探视频(路)["秒"] or 0.0
    起 = max(0.0, 秒 * 0.4)
    _, 文 = _跑ffmpeg(["-ss", f"{起:.2f}", "-t", "2", "-i", 路,
                       "-af", "volumedetect", "-f", "null",
                       os.devnull], 超时=120)
    m = _re.search(r"mean_volume:\s*(-?[\d.]+)", 文 or "")
    if not m:
        return 0.0
    try:
        return 10 ** (float(m.group(1)) / 20)
    except Exception:  # noqa: BLE001
        return 0.0


def 读接片清单(清单路: str) -> list:
    """
    接片清单：一行一段。

        # 注释行、空行都跳过
        D:\\...\\镜1.mp4
        D:\\...\\镜2.mp4  交叉溶解
        D:\\...\\镜3.mp4 | 闪白

    第二列（可选）是**这一段入点的转场**（即「从上一段切到这一段」用什么），
    可以空格分隔也可以 `|` 分隔。没写就用命令行 `--转场`。
    路径带空格时用 `|` 更保险。找不到文件就报错 —— 别默默少接一段。
    """
    清单路 = os.path.abspath(清单路)
    if not os.path.exists(清单路):
        raise RuntimeError(f"找不到清单：{清单路}")
    with open(清单路, "r", encoding="utf-8-sig") as f:
        行们 = f.readlines()
    段们 = []
    for 号, 原 in enumerate(行们, 1):
        行 = 原.strip()
        if not 行 or 行.startswith("#") or 行.startswith("//"):
            continue
        路, 转 = 行, ""
        if "|" in 行:
            路, _, 尾 = 行.partition("|")
            路, 转 = 路.strip(), 尾.strip()
        else:
            # 路径可能有空格 → 从右往左试：把尾部一个词当转场名
            块 = 行.rsplit(None, 1)
            if len(块) == 2:
                try:
                    规整剪辑转场(块[1])
                    路, 转 = 块[0], 块[1]
                except ValueError:
                    pass
        路 = 路.strip().strip('"').strip("'")
        if not os.path.isabs(路):
            路 = os.path.abspath(os.path.join(os.path.dirname(清单路), 路))
        if not os.path.exists(路):
            raise RuntimeError(f"清单第 {号} 行的片子不存在：{路}")
        段们.append({"序": 号, "路": 路, "转场": 转})
    if not 段们:
        raise RuntimeError(f"清单是空的：{清单路}")
    return 段们


def 接片(清单路: str = "", 片子们: list | None = None, 转场: str = "硬切",
         每段: float = 0.5, 存到: str = "", 宽: int = 0, 高: int = 0, 帧率: float = 0,
         质量: int = 18, 无音轨: bool = False, 留中间: bool = False,
         空跑: bool = False, 上限秒: int = 7200, 报=None) -> dict:
    """
    接片：把 N 段 mp4 用真转场合成一个（ffmpeg xfade，**不占卡**）。

    ★ 影匠自建（飞彩零本地转场实现，见本节注释）。不许写成「对齐飞彩」。

    转场    —— 见 `剪辑转场表`。清单每行可以覆盖 `--转场`。
    每段    —— 转场时长（秒）。会被夹到「相邻较短那段 × 0.6」，防 xfade 越界。
    宽高帧率 —— 缺省跟**第一段**（宽高取偶数，libx264 要求）。
    无音轨  —— 干脆不要音轨（素材本来就没声时更快）。
    """
    报 = 报 or (lambda _: None)
    if not FFMPEG:
        raise RuntimeError("找不到 ffmpeg —— 转场这一层干不了。"
                           "把 ffmpeg.exe 放到 _bin\\ 下，或设 影匠_FFMPEG。")
    段们 = 读接片清单(清单路) if 清单路 else [
        {"序": i + 1, "路": os.path.abspath(p), "转场": ""} for i, p in enumerate(片子们 or [])]
    if not 段们:
        raise RuntimeError("接片要至少一段 mp4")
    for x in 段们:
        if not os.path.exists(x["路"]):
            raise RuntimeError(f"找不到片子：{x['路']}")

    全局转 = 规整剪辑转场(转场)
    for i, x in enumerate(段们):                    # 每段的入点转场（第 1 段没有入点）
        x["用转场"] = "" if i == 0 else (规整剪辑转场(x["转场"]) if x["转场"] else 全局转)

    for x in 段们:
        x.update(探视频(x["路"]))

    真宽 = int(宽 or 段们[0]["宽"] or 1280)
    真高 = int(高 or 段们[0]["高"] or 720)
    真帧 = float(帧率 or 段们[0]["帧率"] or 24)
    真宽 -= 真宽 % 2                                # libx264 要偶数
    真高 -= 真高 % 2
    有音 = (not 无音轨) and any(x["有音频"] for x in 段们)

    计划 = []                                       # 每个入点转场的实际时长（夹紧后）
    for i, x in enumerate(段们):
        d = 0.0
        if i > 0 and 剪辑转场表[x["用转场"]]["xfade"]:
            d = max(0.04, min(float(每段), min(段们[i - 1]["秒"], x["秒"]) * 0.6))
        计划.append(d)
    总秒 = sum(x["秒"] for x in 段们) - sum(计划)

    报(f"接片 {len(段们)} 段 → {真宽}×{真高} @{真帧:g}fps  音频={'有' if 有音 else '无'}")
    for i, x in enumerate(段们):
        报(f"  {i + 1}. {x['名']}  {x['秒']:.2f}s  {x['宽']}×{x['高']} @{x['帧率']:g}fps"
           + (f"  入点转场 {x['用转场']} {计划[i]:.2f}s" if i else "  （首段）"))
    报(f"预计成片 {总秒:.2f}s")

    if not 存到:
        os.makedirs(视频目录, exist_ok=True)
        存到 = os.path.join(视频目录,
                            f"{os.path.splitext(段们[0]['名'])[0]}_接片{len(段们)}段.mp4")
    存到 = os.path.abspath(存到)

    if 空跑:
        return {"路": 存到, "段数": len(段们), "总秒": round(总秒, 2), "宽": 真宽, "高": 真高,
                "帧率": 真帧, "有音频": 有音, "转场": 全局转, "每段": 每段,
                "镜头": [{"序": x["序"], "路": x["路"], "秒": x["秒"],
                          "转场": x["用转场"], "转场秒": round(计划[i], 3)}
                         for i, x in enumerate(段们)],
                "说明": "软转场走 ffmpeg xfade+acrossfade；硬切走 concat demuxer(-c copy)。",
                "空跑": True}

    os.makedirs(os.path.dirname(存到), exist_ok=True)
    工作 = os.path.join(os.path.dirname(存到), "_接片工作")
    os.makedirs(工作, exist_ok=True)

    # ── 1. 全部归一化（同尺寸 / 同帧率 / 都有音轨）──
    归 = []
    for i, x in enumerate(段们):
        p = os.path.join(工作, f"n{i:02d}.mp4")
        报(f"归一 {i + 1}/{len(段们)} → {os.path.basename(p)}")
        归一视频(x["路"], p, 真宽, 真高, 真帧, 补静音=有音, 质量=质量)
        归.append(p)

    # ── 2. 没有任何融合 → concat demuxer，不重编码 ──
    if not any(计划):
        清单 = os.path.join(工作, "_concat.txt")
        with open(清单, "w", encoding="utf-8") as f:
            for p in 归:
                f.write("file '" + p.replace("\\", "/").replace("'", "'\\''") + "'\n")
        码, 文 = _跑ffmpeg(["-f", "concat", "-safe", "0", "-i", 清单, "-c", "copy", 存到],
                          超时=上限秒)
        if 码 != 0 or not os.path.exists(存到):
            raise RuntimeError(f"硬切拼接失败：{文.strip()[-400:]}")
        实 = 探视频(存到)
        报(f"硬切拼成（不重编码）：{os.path.basename(存到)}  {实['秒']:.2f}s")
        return {"路": 存到, "段数": len(段们), "总秒": 实["秒"], "宽": 实["宽"], "高": 实["高"],
                "帧率": 实["帧率"], "有音频": 实["有音频"], "转场": 全局转, "每段": 每段,
                "计划秒": round(总秒, 2), "字节": 实["字节"], "空跑": False,
                "手法": "concat demuxer（无融合，-c copy，不重编码）"}

    # ── 3. 有融合 → 一条 filter_complex 串到底 ──
    #    xfade 的 offset 是**累加**的：第 i 个 offset = 前面所有段的时长之和
    #    减去前面所有已发生的转场时长之和，再减本段转场。
    #    （实测三段 0.5s×2：5.08+5.17+5.17−1.0 = 14.42s，与 ffmpeg 实得差 +0.000s。）
    秒们 = [探视频(p)["秒"] for p in 归]
    v图, a图 = "", ""              # 已经搭好的链（第一次迭代才写入 [0:v]）
    v尾, a尾 = "[0:v]", "[0:a]"      # 链的**末端标签**（要跟新链头拼起来）
    for i in range(1, len(归)):
        d = 计划[i]
        v出, a出 = f"[v{i}]", f"[a{i}]"
        if d > 0.0001:
            off = sum(秒们[:i]) - sum(计划[1:i + 1])
            t = 剪辑转场表[段们[i]["用转场"]]["xfade"]
            v图 += (f"{v尾}[{i}:v]xfade=transition={t}:duration={d:.3f}:"
                    f"offset={max(0.0, off):.3f}{v出};")
            a图 += f"{a尾}[{i}:a]acrossfade=d={d:.3f}:c1=tri:c2=tri{a出};"
        else:
            v图 += f"{v尾}[{i}:v]concat=n=2:v=1:a=0{v出};"
            a图 += f"{a尾}[{i}:a]concat=n=2:v=0:a=1{a出};"
        v尾, a尾 = v出, a出
    fc = f"{v图}{a图}" if 有音 else v图
    参 = []
    for p in 归:
        参 += ["-i", p]
    参 += ["-filter_complex", fc, "-map", v尾]
    if 有音:
        参 += ["-map", a尾, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    参 += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(质量),
           "-pix_fmt", "yuv420p", 存到]
    报(f"合成（{sum(1 for d in 计划 if d > 0)} 个转场）…")
    码, 文 = _跑ffmpeg(参, 超时=上限秒)
    if 码 != 0 or not os.path.exists(存到):
        raise RuntimeError(f"接片失败：{文.strip()[-600:]}")
    实 = 探视频(存到)
    报(f"成片 {os.path.basename(存到)}  {实['秒']:.2f}s  {实['字节'] / 1e6:.2f} MB")
    if not 留中间:
        import shutil
        shutil.rmtree(工作, ignore_errors=True)
    return {"路": 存到, "段数": len(段们), "总秒": 实["秒"], "宽": 实["宽"], "高": 实["高"],
            "帧率": 实["帧率"], "有音频": 实["有音频"], "转场": 全局转, "每段": 每段,
            "段们": [{"序": x["序"], "路": x["路"], "秒": x["秒"], "转场": x["用转场"]} for x in 段们],
            "计划秒": round(总秒, 2), "字节": 实["字节"], "空跑": False,
            "手法": "ffmpeg xfade + acrossfade（剪辑层，不占卡）"}


# ============================================================
# 九、任务账本（飞彩 localStorage `feicai-video-states` 的影匠版）
# ============================================================

def 载状态() -> dict:
    try:
        with open(状态文件, "r", encoding="utf-8") as f:
            数 = json.load(f)
        if isinstance(数, dict):
            数.setdefault("任务", {})
            return 数
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 状态文件读不动（{e}），当空的用：{状态文件}")
    return {"版本": 1, "说明": f"飞彩 localStorage `{状态账本键}` 的影匠版（落成文件）", "任务": {}}


def 存状态(数: dict) -> None:
    临时 = 状态文件 + ".tmp"
    with open(临时, "w", encoding="utf-8") as f:
        json.dump(数, f, ensure_ascii=False, indent=1)
    os.replace(临时, 状态文件)


def 记任务(号: str | None = None, **字段) -> dict:
    """
    留一条任务档。**提交之前**先落一条 —— 飞彩的全部设计哲学就一句话：
    「超时 ≠ 失败」，活交出去了钱就可能已经花了，所以账要先记。

    状态取值（照飞彩）：submitting / pending / running / succeeded / failed / indeterminate
    """
    数 = 载状态()
    号 = 号 or f"yjv-{datetime.now():%Y%m%d%H%M%S}-{random.randint(100, 999)}"
    条 = 数["任务"].get(号) or {"号": 号, "建": datetime.now().isoformat(timespec="seconds")}
    条.update(字段)
    条["更"] = datetime.now().isoformat(timespec="seconds")
    数["任务"][号] = 条
    存状态(数)
    return 条


def 改任务(号: str, 状态: str = "", **字段) -> dict:
    """
    改一条任务档。
    ★ **失败不覆盖成 success，超时不覆盖成 failed** —— 超时只能标 indeterminate。
    """
    if 状态 and 状态 not in ("submitting", "pending", "running", "succeeded", "failed", "indeterminate"):
        raise ValueError(f"不认识的状态「{状态}」")
    旧 = 载状态()["任务"].get(号) or {}
    return 记任务(号, 状态=状态 or 旧.get("状态", "indeterminate"), **字段)


def 列任务(只未完成: bool = False) -> list:
    数 = 载状态()
    未完成 = {"submitting", "pending", "running", "indeterminate"}
    行 = list(数["任务"].values())
    if 只未完成:
        行 = [x for x in 行 if x.get("状态") in 未完成]
    return sorted(行, key=lambda x: x.get("建", ""), reverse=True)


# ============================================================
# 十、自测
# ============================================================

class _计数器:
    def __init__(self):
        self.通过 = 0
        self.失败 = 0
        self.没测 = 0
        self.问题们 = []

    def 是(self, 条件, 名, 细节=""):
        if 条件:
            self.通过 += 1
            print(f"    ✓ {名}" + (f"  {细节}" if 细节 else ""))
        else:
            self.失败 += 1
            self.问题们.append(名)
            print(f"    ✗ {名}  {细节}")
        return bool(条件)

    def 同(self, 实得, 该得, 名):
        ok = 实得 == 该得
        if not ok:
            self.问题们.append(f"{名}（得 {实得!r} 该 {该得!r}）")
        return self.是(ok, 名, f"得 {实得!r}" + ("" if ok else f" 该 {该得!r}"))

    def 跳(self, 名, 原因):
        self.没测 += 1
        print(f"    – {名}：没测（{原因}）")

    def 汇总(self):
        return {"通过": self.通过, "失败": self.失败, "没测": self.没测, "问题们": self.问题们}


def 自测(真跑: bool = False, 图路: str = "", json出: bool = False) -> dict:
    """
    自测。**exit 0 靠的是「结构性事实全对」，不靠「本机模型跑得动」。**
    --真跑 才真提交一段视频（默认不跑：H3 是 24B int8 + 32B 文本编码器，很吃显存和时间）。
    """
    计 = _计数器()
    P = print
    P("=" * 78)
    P("视频.py 自测")
    P("=" * 78)

    # ── 1. 依赖 ──
    P("\n[1] 依赖")
    计.是(_引擎 is not None, "引擎.py 载得进来", _引擎错 or f"COMFY={COMFY}")
    if _引擎 is not None:
        在 = _引擎.在线()
        计.是(在.get("在线"), "ComfyUI 在线", json.dumps(在, ensure_ascii=False)[:160])
    else:
        计.跳("ComfyUI 在线", "引擎.py 没载进来")

    # ── 2. 词表（飞彩逐字） ──
    P("\n[2] 词表（对照飞彩逐字）")
    计.同(运镜表, ["固定", "推进", "拉远", "横移", "环绕", "升降"], "运镜 6 个字面量")
    计.同(景别表, ["特写", "近景", "中景", "全景", "远景"], "景别 5 个字面量")
    计.同([m["值"] for m in 创作模式], ["single", "firstlast", "multiref", "v2v"], "创作模式 4 档")
    计.同([m["名"] for m in 创作模式], ["图生视频", "首尾帧视频", "全能参考", "视频参考"], "创作模式中文名")
    计.同(比例_视频页, ["16:9", "9:16", "1:1", "4:3", "3:4"], "视频页宽高比 5 档")
    计.同(镜头类型, ["对话场景", "动作场景", "情绪特写", "环境空镜", "转场镜头"], "镜头类型 5 档")
    计.同(节奏表, ["一镜到底", "起承转合", "快切多段", "渐入渐出"], "节奏时序 4 档")
    计.同(时长_按分辨率["seedance-2.0-vip-1080p-azhw-feicai"][-1], 11, "1080P 时长上限 11 秒（飞彩硬约束）")
    计.同(时长_按模型["video-3.5-pro"], [5, 10, 12], "video-3.5-pro 时长档")

    # ── 3. 别名词表 ──
    P("\n[3] 运镜/转场别名")
    for 敲, 该 in (("推", "推进"), ("拉", "拉远"), ("摇", "横移"), ("移", "横移"),
                   ("跟", "升降"), ("升降", "升降"), ("环绕", "环绕"), ("固定", "固定"),
                   ("zoom in", "推进"), ("Static", "固定")):
        得 = 规整运镜(敲)
        计.同(得, 该, f"运镜别名 {敲} → {该}")
    try:
        规整运镜("乱写的东西")
        计.是(False, "非法运镜要报错")
    except ValueError:
        计.是(True, "非法运镜报错（不静默）")
    for 敲, 该 in (("硬切", "直接切"), ("淡入", "淡入黑场"), ("闪白", "白闪"), ("dissolve", "叠化")):
        计.同(转场提示(敲)["词"], 该, f"转场别名 {敲} → {该}")

    # ── 4. 规格化 ──
    P("\n[4] 规格化（尺寸 / 帧数 / 时长）")
    计.同(选尺寸("16:9", 长边=1344, 步进=32), (1344, 768), "16:9 @720P(H3) = 1344×768")
    计.同(选尺寸("9:16", 长边=1344, 步进=32), (736, 1376), "9:16 @720P(H3) = 736×1376（32 的倍数落不到 1344×2389 上，取比例最贴的）")
    计.同(选尺寸("1:1", 长边=960, 步进=32), (960, 960), "1:1 = 960×960")
    计.同(选尺寸("4:3", 长边=1024, 步进=32), (1024, 768), "4:3 = 1024×768")
    计.同(选尺寸("21:9", 长边=1344, 步进=32), (1344, 576), "21:9 = 1344×576")
    计.同(选尺寸("16:9", 长边=1920, 步进=32), (1920, 1088), "16:9 1080P = 1920×1088（恰好整除，不许落成 1888×1056）")
    for 比, 长 in (("16:9", 1344), ("9:16", 1344), ("4:3", 1024), ("21:9", 1344)):
        w, h = 选尺寸(比, 长边=长, 步进=32)
        计.是(w % 32 == 0 and h % 32 == 0, f"{比} 尺寸两边都是 32 的倍数", f"{w}×{h}")
    计.同(规整帧数(5.0, 24), 124, "5 秒 @24fps → 124 帧（H3 的 17k+5）")
    计.同(规整帧数(10.0, 24), 243, "10 秒 @24fps → 243 帧")
    计.同(规整帧数(2.0, 24), 56, "2 秒 → 56 帧（H3 网格下限是 5 帧，不是 124）")
    计.同(规整帧数(5.0, 16, 帧组=(4, 1), 下限=5), 81, "5 秒 @16fps → 81 帧（Wan 的 4k+1）")
    for 秒 in (1, 2, 5, 10, 15):
        帧 = 规整帧数(秒, 24)
        计.是((帧 - 5) % 17 == 0, f"{秒} 秒 → {帧} 帧，落在 17k+5 网格上")
    计.同(规整时长(5, "minimax-h3-fl2va", "720P")["帧数"], 124, "规整时长 5s → 124 帧")
    计.是(规整时长(20, "minimax-h3-fl2va", "1080P")["给的"] <= 11, "1080P 20 秒被钳到 ≤11 秒")
    计.同(规整时长(5, "wan2.2-ti2v-5b", "480P")["帧数"], 81, "Wan 5s → 81 帧 @16fps")
    try:
        规格(时长=5, 比例="7:5", 模型="minimax-h3-fl2va")
        计.是(False, "非法宽高比要报错")
    except ValueError:
        计.是(True, "非法宽高比报错")
    try:
        规格(时长=5, 比例="16:9", 模型="不存在的模型")
        计.是(False, "非法模型要报错")
    except ValueError:
        计.是(True, "非法模型报错")

    # ── 5. 超分提示词（★ 飞彩铁律） ──
    P("\n[5] 超分提示词（★ 飞彩铁律三条要在）")
    英 = 超分提示词("4K")
    计.是("This is NOT image regeneration. Do NOT redraw or reimagine" in 英, "英文版含铁律句")
    计.是("PIXEL-PERFECT copy" in 英, "英文版含 PIXEL-PERFECT copy")
    计.是("4096px long edge" in 英, "4K → 4096 长边")
    中 = 超分提示词("2K", 通道="中文")
    计.是("这是超分放大，不是重新绘制" in 中, "中文版含铁律句")
    计.是("边缘线条" in 中 and "精细细节" in 中 and "面部清晰" in 中 and "去除伪影" in 中 and "材质保真" in 中,
          "中文版五级优先级齐（轮廓线>细节>面部>去伪影>材质）")
    计.是(英.index("1. EDGES & LINES") < 英.index("2. FINE DETAILS") < 英.index("3. FACIAL CLARITY")
          < 英.index("4. ARTIFACT REMOVAL") < 英.index("5. TEXTURE FIDELITY"), "英文版五级顺序正确")
    G = 超分提示词("4K", 通道="gemini")
    计.是("Generate a 4K ultra-high-definition version" in G, "Gemini 通道变体在")
    计.同(超分提示词("2K").count("2048"), 1, "2K → 2048 只出现一次")
    计.是(len(关键词系统提示) > 200 and "Maximum 200 characters" in 关键词系统提示, "关键词 system prompt 在（≤200 字硬限）")
    计.是(len(二次超分后缀) > 50, "二次超分固定后缀在")

    # ── 6. 提示词拼装 ──
    P("\n[6] 提示词拼装（飞彩语言规范）")
    句 = 拼提示词("少女抬头看向窗外，雨滴滑落", 运镜="推进", 景别="近景", 转场="叠化",
                 节奏="渐入渐出", 时长秒=5)
    计.是("pushes in" in 句, "运镜进了提示词")
    计.是("Dissolve" in 句, "转场进了提示词")
    计.是("fade in" in 句.lower(), "节奏档进了提示词")
    计.是("5" not in 句.split("No subtitles")[0][-40:], "时长秒没被写进正文（飞彩参数禁区）")
    for 禁 in ("更流畅", "丝滑", "高质量"):
        计.是(禁 not in 句, f"没出现被禁的空话「{禁}」")
    计.是("No subtitles" in 句, "零文字铁律在")

    # ── 7. 拼工作流（不提交） ──
    P("\n[7] 拼工作流（只拼不提交）")
    try:
        wf = 拼H3("测试提示词", 模式="firstlast", 宽=1344, 高=768, 帧数=124, 种子=42,
                  首帧="/tmp/a.png", 尾帧="/tmp/b.png",
                  上传名们={"/tmp/a.png": "a.png", "/tmp/b.png": "b.png"})
        类 = {v["class_type"] for v in wf.values()}
        计.是("MiniMaxH3ImageToVideo" in 类, "H3 首尾帧节点在")
        n = wf["104"]["inputs"]
        计.同(n["first_frame"], ["113", 0], "first_frame 接在 LoadImage 上")
        计.同(n["last_frame"], ["114", 0], "★ last_frame 接在第二个 LoadImage 上（影匠原来没有的那条）")
        计.同(n["length"], 124, "length = 124 帧")
        计.同(n["width"], 1344, "width = 1344")
        计.同(wf["14"]["inputs"]["latent_image"], ["104", 1], "采样器吃 H3 的 LATENT 输出")
        计.同(wf["16"]["inputs"]["conditioning"], ["104", 0], "guider 吃 H3 的 CONDITIONING 输出")
        计.是("VAEDecodeAudio" in 类 and wf["91"]["inputs"]["audio"] == ["24n", 0], "音频轨接上了（H3 联合出声）")
        计.同(wf["91"]["inputs"]["fps"], 24.0, "CreateVideo fps = 24")
        计.是("SaveVideo" in 类, "SaveVideo 在")
        # 接线完整性：每个引用的节点号都要真在
        坏 = [f"{k}.{kk}→{v[0]}" for k, 节 in wf.items() for kk, v in 节.get("inputs", {}).items()
              if isinstance(v, list) and len(v) == 2 and str(v[0]) not in {str(x) for x in wf}]
        计.同(坏, [], "所有连线指向的节点都在（没有悬空引用）")
        # ★ 真跑那次 400 就是这条漏过去的：VAEDecodeAudio / VAEDecode 建在骨架里、
        #   输入字典是空的 —— 节点在、连线也不悬空，必填输入却一个没接。
        #   现在用 ComfyUI 自己的 /object_info 逐节点查必填，本地就拦住。
        try:
            表 = 节点规格()
            计.是(len(表) > 100, "拿到 /object_info", f"{len(表)} 个节点")
        except Exception as e:  # noqa: BLE001
            表 = {}
            计.跳("本地前置校验", f"/object_info 没问到：{e!r}")
        if 表:
            计.同(校验工作流(wf, 表), [], "★ H3 首尾帧工作流通过本地前置校验（必填输入齐）")
            坏例 = dict(wf)
            坏例["10"] = {"class_type": "VAEDecode", "inputs": {"vae": ["11", 0]}}
            计.是(any("samples" in x for x in 校验工作流(坏例, 表)),
                  "★ 校验器抓得住「缺必填 samples」这种坑（就是真跑踩的那个）")
            坏例2 = dict(wf)
            坏例2["99"] = {"class_type": "不存在的节点类", "inputs": {}}
            计.是(any("本机没有" in x for x in 校验工作流(坏例2, 表)), "校验器抓得住类名拼错")
    except Exception as e:  # noqa: BLE001
        计.是(False, "拼 H3 工作流", repr(e))
    try:
        wf2 = 拼H3("测试", 模式="multiref", 宽=1344, 高=768, 帧数=124, 种子=1,
                   参考图们=["/tmp/x.png"], 上传名们={"/tmp/x.png": "x.png"})
        计.是("MiniMaxH3ReferenceToVideo" in {v["class_type"] for v in wf2.values()},
              "全能参考走 MiniMaxH3ReferenceToVideo")
        计.同(wf2["136"]["inputs"]["ref_image_0"], ["200", 0], "ref_image_0 接上了")
    except Exception as e:  # noqa: BLE001
        计.是(False, "拼全能参考工作流", repr(e))
    try:
        wf3 = 拼Wan("测试", 尾帧="/tmp/b.png", 首帧="/tmp/a.png", 帧数=81,
                    上传名们={"/tmp/a.png": "a.png", "/tmp/b.png": "b.png"})
        计.是("WanFirstLastFrameToVideo" in {v["class_type"] for v in wf3.values()},
              "Wan 尾帧走 WanFirstLastFrameToVideo 节点")
        计.同(wf3["8"]["inputs"]["start_image"], ["5", 0], "Wan start_image 接上")
        计.同(wf3["8"]["inputs"]["end_image"], ["5b", 0], "★ Wan end_image 接上")
    except Exception as e:  # noqa: BLE001
        计.是(False, "拼 Wan 首尾帧工作流", repr(e))

    # ── 8. 空跑（不碰 ComfyUI 的全链路） ──
    P("\n[8] 空跑全链路（不碰 ComfyUI）")
    try:
        果 = 首尾帧("/tmp/a.png", "/tmp/b.png", "抬头", 时长=5, 运镜="推进",
                    空跑=True, 报=lambda _: None)
        计.同(果["空跑"], True, "首尾帧空跑返回")
        计.同(果["规格"]["帧数"], 124, "空跑也算规格：124 帧")
        计.是("pushes in" in 果["提示词"], "空跑也拼了提示词（运镜进了正文）", 果["提示词"][:60])
    except Exception as e:  # noqa: BLE001
        计.是(False, "首尾帧空跑", repr(e))
    try:
        果 = 文生视频("一句话", 时长=10, 比例="9:16", 空跑=True, 报=lambda _: None)
        计.同((果["规格"]["宽"], 果["规格"]["高"]), (736, 1376), "文生视频 9:16 空跑尺寸")
        计.同(果["规格"]["帧数"], 243, "文生视频 10 秒空跑帧数")
    except Exception as e:  # noqa: BLE001
        计.是(False, "文生视频空跑", repr(e))
    try:
        果 = 超分("/tmp/x.png", 档="4K", 空跑=True) if os.path.exists("/tmp/x.png") else \
            超分(os.path.join(_根, "README.md"), 档="2K", 空跑=True)
        计.同(果["长边"], 2048, "超分空跑 2K → 2048")
        计.是("NOT image regeneration" in 果["提示词"], "超分空跑也带铁律")
    except Exception as e:  # noqa: BLE001
        计.是(False, "超分空跑", repr(e))
    # ★ 参考图通道缺模型时，超分必须**拒绝出图**而不是静默降级成「照着提示词重画」
    #   （2026-10-14 实测踩过：qwen_edit 模板缺 unet 时引擎只打一行 ⚠ 就退回纯文生图，
    #    产出的 `作品\超分_00001_.png` 模型根本没看见原图。）
    try:
        if _引擎 is None or not hasattr(_引擎, "模板缺什么"):
            计.跳("超分拒降级", "引擎.py 不可用，问不了模板缺什么")
        else:
            缺 = _引擎.模板缺什么("qwen_edit")
            if not 缺:
                计.跳("超分拒降级", "本机 qwen_edit 参考图通道现在是好的，构造不出缺模型场景")
            else:
                _试 = os.path.join(_根, "README.md")
                try:
                    超分(_试, 档="2K", 模板="qwen_edit", 报=lambda _: None)
                    计.是(False, "超分拒降级", "参考图通道缺模型，超分却没拒绝 —— 会出废图")
                except RuntimeError as e2:
                    计.是("参考图通道不可用" in str(e2), "超分缺参考图通道时拒绝出图")
                    计.是(("NOT image regeneration" in str(e2)) or ("重新生成" in str(e2)),
                          "拒绝理由点明「等于重新生成」")
                    果2 = 超分(_试, 档="2K", 模板="qwen_edit", 允许降级=True,
                              报=lambda _: None, 空跑=True)
                    计.是(果2.get("空跑") is True, "显式 --允许降级 时放行（空跑验证）")
    except Exception as e:  # noqa: BLE001
        计.是(False, "超分拒降级", repr(e))

    # ── 9. 接龙（纯标准库读 mp4） ──
    P("\n[9] 接龙 / 取末帧")
    计.同(转场提示("叠化")["手法"].startswith("首尾帧"), True, "叠化的接法是「上镜末帧=下镜首帧」")
    try:
        计.是(callable(取末帧) and callable(接龙), "取末帧/接龙在")
        计.同(_mp4秒数(os.path.join(_根, "视频.py")), 0.0, "非 mp4 文件读时长返回 0（不抛）")
    except Exception as e:  # noqa: BLE001
        计.是(False, "接龙接口", repr(e))

    # ── 9b. 剪辑层接片（★ 真跑 ffmpeg，拿本机现成的两段当素材） ──
    P("\n[9b] 剪辑层接片（ffmpeg 真转场，影匠自建）")
    if not FFMPEG:
        计.跳("剪辑层接片", "找不到 ffmpeg（放 _bin\\ffmpeg.exe 或设 影匠_FFMPEG）")
    else:
        P(f"    ffmpeg：{FFMPEG}")
        # 词表与规整
        try:
            计.是(len(剪辑转场表) >= 10, "剪辑转场有 10 种以上", f"{len(剪辑转场表)} 种")
            计.同(规整剪辑转场("硬切"), "硬切", "硬切")
            计.同(规整剪辑转场("dissolve"), "叠化", "dissolve → 叠化（别名）")
            计.同(规整剪辑转场("fade"), "交叉溶解", "fade → 交叉溶解（别名）")
            计.同(规整剪辑转场("fadeblack"), "淡入淡出", "fadeblack → 淡入淡出")
            计.同(规整剪辑转场("match"), "匹配剪辑", "match → 匹配剪辑")
            计.同(剪辑转场表["硬切"]["xfade"], "", "硬切没有 xfade（走 concat）")
            计.是(all(剪辑转场表[k]["xfade"] for k in
                      ("交叉溶解", "叠化", "淡入淡出", "闪白", "划像", "推入", "拉出", "匹配剪辑")
                      if k != "匹配剪辑"), "软转场都有 xfade 字面量")
            try:
                规整剪辑转场("瞎写一个")
                计.是(False, "剪辑转场不认识的要报错")
            except ValueError:
                计.是(True, "剪辑转场不认识的要报错")
        except Exception as e:  # noqa: BLE001
            计.是(False, "剪辑转场词表", repr(e))

        # 找两段真素材
        素材 = []
        for 候 in (os.path.join(视频目录, "真跑_叶云_wan.mp4"),
                   os.path.join(视频目录, "真跑_首尾帧_红球.mp4")):
            if os.path.exists(候):
                素材.append(候)
        if len(素材) < 2:
            计.跳("剪辑层真合成", f"本机只找到 {len(素材)} 段现成 mp4（要两段）")
        else:
            try:
                d0, d1 = 探视频(素材[0]), 探视频(素材[1])
                计.是(d0["秒"] > 0 and d0["宽"] > 0, "探视频读到时长/尺寸",
                      f"{d0['名']} {d0['宽']}×{d0['高']} @{d0['帧率']:g}fps {d0['秒']:.2f}s "
                      f"音轨={d0['有音频']}")
                计.是(d0["帧率"] != d1["帧率"] or d0["宽"] != d1["宽"] or
                      d0["有音频"] != d1["有音频"],
                      "两段素材确实不同源（不同帧率/尺寸/有无音轨都算）",
                      f"甲 {d0['帧率']:g}fps {d0['宽']}×{d0['高']} 音轨={d0['有音频']} / "
                      f"乙 {d1['帧率']:g}fps {d1['宽']}×{d1['高']} 音轨={d1['有音频']}")
            except Exception as e:  # noqa: BLE001
                计.是(False, "探视频", repr(e))

            # 空跑：不落盘，先验规格与计划
            try:
                果 = 接片(片子们=素材, 转场="交叉溶解", 每段=0.5, 空跑=True)
                计.是(果["空跑"] is True and 果["段数"] == 2, "接片空跑给计划")
                计.同(round(果["总秒"], 2),
                      round(d0["秒"] + d1["秒"] - 0.5, 2), "空跑总时长 = 两段之和 − 转场")
                计.同(果["镜头"][0]["转场"], "", "第一段没有入点转场")
                计.同(果["镜头"][1]["转场"], "交叉溶解", "第二段入点转场")
            except Exception as e:  # noqa: BLE001
                计.是(False, "接片空跑", repr(e))

            # ★ 真合成：软转场
            出 = os.path.join(_work目录, "自测_接片_交叉溶解.mp4")
            try:
                os.makedirs(_work目录, exist_ok=True)
                果 = 接片(片子们=素材, 转场="交叉溶解", 每段=0.5, 存到=出,
                          报=lambda s: P(f"      {s}"))
                计.是(os.path.exists(出) and os.path.getsize(出) > 10000,
                      "★ 真合成出 mp4", f"{os.path.getsize(出) / 1e6:.2f} MB")
                实 = 探视频(出)
                计.同(实["宽"], d0["宽"] - d0["宽"] % 2, "成片宽度跟第一段（取偶）")
                计.同(实["高"], d0["高"] - d0["高"] % 2, "成片高度跟第一段（取偶）")
                计.同(round(实["帧率"]), round(d0["帧率"]), "成片帧率跟第一段")
                期 = d0["秒"] + d1["秒"] - 0.5
                计.是(abs(实["秒"] - 期) < 1.2, "成片时长 ≈ 两段−转场（±1.2s）",
                      f"实得 {实['秒']:.2f}s 期望 {期:.2f}s")
                计.是(实["有音频"], "成片带音轨（缺音轨那段补了静音）")
            except Exception as e:  # noqa: BLE001
                计.是(False, "★ 真合成出 mp4", repr(e))

            # ★ 真合成：硬切走 concat（不重编码）
            出2 = os.path.join(_work目录, "自测_接片_硬切.mp4")
            try:
                果 = 接片(片子们=素材, 转场="硬切", 存到=出2,
                          报=lambda s: P(f"      {s}"))
                计.是(os.path.exists(出2), "★ 硬切也出 mp4", f"{os.path.getsize(出2) / 1e6:.2f} MB")
                计.是("concat" in 果["手法"], "硬切走 concat demuxer（不重编码）", 果["手法"])
                实2 = 探视频(出2)
                计.是(abs(实2["秒"] - (d0["秒"] + d1["秒"])) < 1.2,
                      "硬切成片 ≈ 两段之和（没有融合扣减）",
                      f"实得 {实2['秒']:.2f}s 期望 {d0['秒'] + d1['秒']:.2f}s")
            except Exception as e:  # noqa: BLE001
                计.是(False, "★ 硬切也出 mp4", repr(e))

            # ★ 清单文件路径 + 每行覆盖转场
            清 = os.path.join(_work目录, "自测_接片清单.txt")
            try:
                with open(清, "w", encoding="utf-8") as f:
                    f.write("# 自测清单\n")
                    f.write(素材[0] + "\n")
                    f.write(素材[1] + " | 闪白\n")
                段 = 读接片清单(清)
                计.同(len(段), 2, "清单读到 2 段")
                计.同(段[1]["转场"], "闪白", "清单第二段覆盖了转场名")
                出3 = os.path.join(_work目录, "自测_接片_清单.mp4")
                果 = 接片(清单路=清, 转场="硬切", 每段=0.5, 存到=出3,
                          报=lambda s: P(f"      {s}"))
                计.是(os.path.exists(出3) and os.path.getsize(出3) > 10000,
                      "★ 清单驱动接片出 mp4", f"{os.path.getsize(出3) / 1e6:.2f} MB")
                计.同(果["段们"][1]["转场"], "闪白", "清单覆盖生效（第二段用了闪白）")
            except Exception as e:  # noqa: BLE001
                计.是(False, "★ 清单驱动接片", repr(e))

            # 找不到文件要报错，不许默默少接一段
            try:
                with open(清 + ".坏", "w", encoding="utf-8") as f:
                    f.write(素材[0] + "\n")
                    f.write("D:\\DSHworkspace\\影匠\\_work\\根本没有这段.mp4\n")
                读接片清单(清 + ".坏")
                计.是(False, "清单里片子不存在要报错")
            except RuntimeError:
                计.是(True, "清单里片子不存在要报错")

    # ── 10. 账本 ──
    P("\n[10] 任务账本")
    try:
        号 = f"selftest-{datetime.now():%H%M%S}"
        记任务(号, 状态="running", 模型="minimax-h3-fl2va", 备注="自测")
        条 = [x for x in 列任务() if x["号"] == 号]
        计.是(bool(条) and 条[0]["状态"] == "running", "记一条任务再读回来")
        计.是(os.path.exists(状态文件), "状态文件真落盘了", 状态文件)
        # 清理：自测别把账本撑肥
        数 = 载状态()
        数["任务"].pop(号, None)
        存状态(数)
    except Exception as e:  # noqa: BLE001
        计.是(False, "账本读写", repr(e))

    # ── 11. 真跑（可选） ──
    if 真跑:
        P("\n[11] ★ 真跑：真提交一段视频")
        用图 = 图路
        if not 用图:
            for 候 in (os.path.join(作品目录, "视频"), 作品目录, os.path.join(_根, "素材", "图")):
                if os.path.isdir(候):
                    for f in sorted(os.listdir(候)):
                        if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp"):
                            用图 = os.path.join(候, f)
                            break
                if 用图:
                    break
        if not 用图 or not os.path.exists(用图):
            计.跳("真出一段视频", "找不到一张能当首帧的图（用 图路 参数指定）")
        else:
            P(f"    首帧：{用图}")
            try:
                果 = 图生视频(用图, "镜头缓缓推近，主体自然呼吸", 时长=5, 模型="minimax-h3-fl2va",
                              运镜="推进", 报=lambda s: P(f"      {s}"))
                路 = 果.get("路") or ""
                计.是(bool(路) and os.path.exists(路), "真出了视频", 路)
                if 路:
                    兆 = os.path.getsize(路) / 1048576
                    计.是(兆 > 0.01, "片子不是空文件", f"{兆:.2f} MB")
                    秒 = _mp4秒数(路)
                    计.是(秒 == 0 or 秒 >= 3, "片长合理", f"{秒}s")
                    P(f"    → {路}  {兆:.2f} MB  {秒}s  耗时 {果.get('耗时')}s")
            except Exception as e:  # noqa: BLE001
                计.是(False, "真出一段视频", repr(e))
    else:
        计.跳("真出一段视频", "没给 --真跑（H3 是 24B int8 + 32B 文本编码器，很吃显存/时间）")

    # ── 汇总 ──
    果 = 计.汇总()
    P("")
    P("=" * 78)
    P(f"通过 {果['通过']}　失败 {果['失败']}　没测 {果['没测']}")
    if 果["问题们"]:
        P("失败清单：")
        for x in 果["问题们"]:
            P("  · " + x)
    P("=" * 78)
    if json出:
        P(json.dumps(果, ensure_ascii=False))
    return 果


# ============================================================
# 十一、命令行
# ============================================================

命令们 = {
    "模型": "列飞彩的模型能力表 + 本机 H3 在不在",
    "模式": "列飞彩的 4 个创作模式",
    "运镜": "列 6 个运镜字面量 + 提示词短句",
    "转场": "列转场词表（--列 只看，不出片）",
    "规格": "只算规格（时长/比例/尺寸/帧数），不碰 ComfyUI",
    "文生视频": "一句话出片",
    "图生视频": "一张图 + 一句话出片",
    "首尾帧": "首帧 + 尾帧 + 一句话出片（飞彩有、影匠原来没有）",
    "全能参考": "多张参考图 + 一句话出片",
    "视频参考": "参考视频 + 一句话出片",
    "超分": "拿原图当参考图 + 超分提示词喂图像模型（**不是** RealESRGAN）",
    "取末帧": "从 mp4 抠一帧（走 ComfyUI）",
    "接龙": "取上镜末帧当下镜首帧，串成连续镜头（提示词层，不出 mp4）",
    "接片": "★ 剪辑层：用 ffmpeg 真转场把 N 段 mp4 接成一个（**不占卡**）",
    "状态": "看留档的任务账本（飞彩 feicai-video-states 的影匠版）",
    "自测": "自测；--真跑 才真提交一段视频",
}
别名 = {"列模型": "模型", "能力": "模型", "列运镜": "运镜", "列转场": "转场",
        "首尾帧视频": "首尾帧", "图生": "图生视频", "文生": "文生视频",
        "放大": "超分", "upscale": "超分", "自查": "自测", "selftest": "自测",
        "末帧": "取末帧", "续接": "接龙",
        "剪辑转场": "转场", "接片转场": "转场", "拼片": "接片", "合成": "接片",
        "concat": "接片", "join": "接片"}


def 用法():
    print(__doc__)
    print("\n各命令干什么：")
    for k, v in 命令们.items():
        print(f"  {k:<8} {v}")
    print("\n开关：--空跑 只演一遍不碰 ComfyUI　--json 机器可读　--真跑 自测里真提交")
    print("常用参数：--时长 5  --比例 16:9  --宽 1344 --高 768  --档 720P/1080P/4K/2K")
    print("          --运镜 推/拉/摇/移/跟/升降/环绕/固定  --景别 特写/近景/中景/全景/远景")
    print("  提示词层转场（喂给模型） --转场 叠化/淡入黑场/白闪/匹配剪辑/直接切")
    print("  剪辑层转场（ffmpeg 真合成） python 视频.py 接片 清单.txt --转场 交叉溶解 --每段 0.5")
    print("          可用的剪辑转场：见 `python 视频.py 转场 --剪辑`")
    print("          --节奏 一镜到底/起承转合/快切多段/渐入渐出  --模型 h3/ref2va/wan")
    print("          --存到 <路径.mp4>  --上限秒 N  --图 <首帧.png>  --无音轨  --留中间")


def _参(参数, 名, 默认=None):
    for i, x in enumerate(参数):
        if x in (f"--{名}", f"-{名}") and i + 1 < len(参数):
            return 参数[i + 1]
    return 默认


def _有(参数, 名):
    return f"--{名}" in 参数 or f"-{名}" in 参数


def main(argv) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    if len(argv) < 2 or argv[1] in ("-h", "--help", "帮", "用法"):
        用法()
        return 0
    命令 = 别名.get(argv[1], argv[1])
    if 命令 not in 命令们:
        print(f"不认识这个命令：{argv[1]}")
        用法()
        return 2
    参数 = argv[2:]
    空跑 = _有(参数, "空跑")
    json出 = _有(参数, "json")
    真跑 = _有(参数, "真跑")

    if 命令 == "模型":
        print(f"{'模型':<22}{'本机':<6}{'模式':<34}{'分辨率':<16}时长")
        print("-" * 100)
        for k, v in 模型能力表.items():
            print(f"{k:<22}{'✓' if v.get('本机') else '（飞彩云）':<6}"
                  f"{'/'.join(v.get('modes') or []):<34}"
                  f"{'/'.join(v.get('resolutions') or []):<16}"
                  f"{(v.get('durations') or [])[:8]}…")
        print()
        print("影匠本机能真跑的：")
        for k, v in 模型能力表.items():
            if v.get("本机"):
                print(f"  {k:<20} {v.get('模型')}")
                print(f"  {'':<20} LoRA {v.get('LoRA')}   {v.get('备注','')}")
        if _引擎 is not None:
            在 = _引擎.在线()
            print(f"\nComfyUI：{json.dumps(在, ensure_ascii=False)}")
            if 在.get("在线"):
                有 = []
                for k, v in 模型能力表.items():
                    if not v.get("本机"):
                        continue
                    for 名 in (v.get("模型"), v.get("LoRA")):
                        if 名 and not _引擎.有模型(名):
                            有.append(f"{k} 缺 {名}")
                print("模板/模型缺什么：", 有 or "齐的")
        return 0

    if 命令 == "模式":
        for m in 创作模式:
            print(f"  {m['值']:<12}{m['名']}")
        print(f"\n批量：{创作模式_带批量[-1]['值']}（{创作模式_带批量[-1]['名']}），并发上限 {批量并发上限}")
        return 0

    if 命令 == "运镜":
        for x in 列运镜():
            print(f"  {x['词']:<6}{x['中文']}")
            print(f"        {x['提示词']}")
        print("\n别名：推→推进　拉→拉远　摇/移→横移　跟/升降→升降　环绕　固定")
        return 0

    if 命令 == "转场":
        if _有(参数, "剪辑") or _有(参数, "ffmpeg"):
            print(f"== 剪辑层转场（ffmpeg xfade，**影匠自建**；飞彩零本地转场实现）==")
            print(f"   ffmpeg：{FFMPEG or '（没找到！）'}")
            for x in 列剪辑转场():
                print(f"  {x['词']:<8}{x['名']:<14}{x['说明']}")
            print(f"\n用法：python 视频.py 接片 <清单.txt> --转场 交叉溶解 --每段 0.5 --存到 <出.mp4>")
            print(f"      清单一行一段，可写 `路径 | 转场名` 覆盖该段入点；# 开头是注释。")
            print(f"      清单里出现任意软转场 → 走 ffmpeg；全是硬切 → concat demuxer 不重编码。")
            return 0
        for x in 列转场():
            print(f"  {x['词']:<8}{x['名']:<12}{x['手法']}")
            if x["文案"]:
                print(f"        提示词：{x['文案']}")
        print(f"\n节奏时序档（飞彩逐字）：{' / '.join(节奏表)}")
        print(f"转场镜头提示词：{转场镜头提示}")
        print(f"\n★ 上面这些是**提示词层**的转场（喂给视频模型，飞彩的做法）。")
        print(f"  要看**剪辑层**的真融合（ffmpeg 合成 mp4）：python 视频.py 转场 --剪辑")
        return 0

    if 命令 == "规格":
        try:
            果 = 规格(时长=_参(参数, "时长", 5), 比例=_参(参数, "比例", 比例_默认),
                      模型=_参(参数, "模型", "minimax-h3-fl2va"),
                      分辨率=_参(参数, "分辨率", _参(参数, "档", "")),
                      宽=int(_参(参数, "宽", 0) or 0), 高=int(_参(参数, "高", 0) or 0))
        except Exception as e:  # noqa: BLE001
            print(f"规格算不出来：{e}")
            return 2
        if json出:
            print(json.dumps(果, ensure_ascii=False, indent=1))
        else:
            print(f"模型　　{果['模型']}")
            print(f"宽高比　{果['比例']}　→　{果['宽']}×{果['高']}（{果['分辨率']}）")
            print(f"帧　　　{果['帧数']} 帧 @ {果['帧率']} fps ≈ {果['秒']:.2f} 秒"
                  + (f"（你要 {果['要的秒']} 秒）" if 果["钳过"] else ""))
            for x in 果["提示们"]:
                print(f"　· {x}")
            for x in 果["警告们"]:
                print(f"　⚠ {x}")
        return 0

    if 命令 == "自测":
        图 = _参(参数, "图")
        果 = 自测(真跑=真跑, 图路=图 or "", json出=json出)
        return 0 if 果["失败"] == 0 else 1

    if 命令 == "状态":
        行 = 列任务()
        if not 行:
            print(f"账本空的：{状态文件}")
            return 0
        for x in 行[:40]:
            print(f"  {x.get('建','')}  {x.get('状态','?'):<13}{x['号']}  "
                  f"{x.get('模型','')}  {x.get('备注','')}")
        print(f"\n共 {len(行)} 条，只未完成 {len(列任务(只未完成=True))} 条。账本：{状态文件}")
        return 0

    # ── 出片类 ──
    位 = [x for x in 参数 if not x.startswith("-")]
    # 把开关后面的值也当位置参数会串味，这里只挑「不像开关值」的
    单值开关 = {"时长", "比例", "宽", "高", "档", "分辨率", "模型", "运镜", "景别", "转场",
                "节奏", "时代", "种子", "步数", "存到", "上限秒", "档位", "通道", "图", "强度",
                "关键词", "增强关键词",
                "每段", "质量", "帧率", "第几帧"}
    跳过 = set()
    for i, x in enumerate(参数):
        if x.startswith("-"):
            跳过.add(i)
            if x.lstrip("-") in 单值开关 and i + 1 < len(参数):
                跳过.add(i + 1)
    位 = [x for i, x in enumerate(参数) if i not in 跳过]

    公共 = dict(
        时长=_参(参数, "时长", 5), 比例=_参(参数, "比例", 比例_默认),
        宽=int(_参(参数, "宽", 0) or 0), 高=int(_参(参数, "高", 0) or 0),
        档=_参(参数, "档", ""), 分辨率=_参(参数, "分辨率", ""),
        运镜=_参(参数, "运镜", "") or "", 景别=_参(参数, "景别", "") or "",
        转场=_参(参数, "转场", "") or "", 节奏=_参(参数, "节奏", "") or "",
        时代=_参(参数, "时代", "") or "",
        种子=int(_参(参数, "种子", 0) or 0) or None,
        存到=_参(参数, "存到", "") or "", 空跑=空跑,
        上限秒=int(_参(参数, "上限秒", 3600) or 3600),
        报=(lambda _: None) if json出 else (lambda s: print("   ", s)),
    )
    模型 = _参(参数, "模型", "")

    try:
        if 命令 == "文生视频":
            if not 位:
                print("文生视频要一句提示词")
                return 2
            果 = 文生视频(位[0], 模型=模型 or "minimax-h3-fl2va", **公共)
        elif 命令 == "图生视频":
            if len(位) < 1:
                print("图生视频要一张图（本机绝对路径）")
                return 2
            果 = 图生视频(位[0], 位[1] if len(位) > 1 else "", 模型=模型 or "minimax-h3-fl2va", **公共)
        elif 命令 == "首尾帧":
            if len(位) < 2:
                print("首尾帧要两张图：首帧 尾帧 [动作描述]")
                return 2
            果 = 首尾帧(位[0], 位[1], 位[2] if len(位) > 2 else "",
                        模型=模型 or "minimax-h3-fl2va", **公共)
        elif 命令 == "全能参考":
            if not 位:
                print("全能参考要至少一张参考图")
                return 2
            果 = 全能参考(位, 模型=模型 or "minimax-h3-ref2va", **公共)
        elif 命令 == "视频参考":
            if not 位:
                print("视频参考要至少一段参考视频")
                return 2
            果 = 视频参考(位, 模型=模型 or "minimax-h3-ref2va", **公共)
        elif 命令 == "超分":
            if not 位:
                print("超分要一张图")
                return 2
            果 = 超分(位[0], 档=_参(参数, "档", _参(参数, "档位", "4K")),
                      通道=_参(参数, "通道", "英文"), 比例=公共["比例"], 时代=公共["时代"],
                      增强关键词=_参(参数, "增强关键词", _参(参数, "关键词", "")),
                      强度=(float(_参(参数, "强度")) if _参(参数, "强度") else None),
                      种子=公共["种子"], 存到=_参(参数, "存到", ""),
                      允许降级=(_有(参数, "允许降级") or _有(参数, "接受重画")),
                      空跑=空跑,
                      报=(lambda _: None) if json出 else (lambda s: print("   ", s)))
        elif 命令 == "取末帧":
            if not 位:
                print("取末帧要一段 mp4")
                return 2
            路 = 取末帧(位[0], 存到=_参(参数, "存到", ""), 第几帧=int(_参(参数, "第几帧", -1) or -1),
                        空跑=空跑, 报=(lambda _: None) if json出 else (lambda s: print("   ", s)))
            果 = {"末帧": 路}
        elif 命令 == "接片":
            if not 位:
                print("接片要一个清单文件，或者一串 mp4 路径")
                print("  python 视频.py 接片 清单.txt --转场 交叉溶解 --每段 0.5 --存到 出.mp4")
                return 2
            清单 = 位[0] if (len(位) == 1 and os.path.isfile(位[0])) else ""
            try:
                果 = 接片(清单路=清单, 片子们=(None if 清单 else 位),
                          转场=_参(参数, "转场", "硬切"),
                          每段=float(_参(参数, "每段", 0.5) or 0.5),
                          存到=_参(参数, "存到", ""),
                          宽=int(_参(参数, "宽", 0) or 0), 高=int(_参(参数, "高", 0) or 0),
                          帧率=float(_参(参数, "帧率", 0) or 0),
                          质量=int(_参(参数, "质量", 18) or 18),
                          无音轨=_有(参数, "无音轨"), 留中间=_有(参数, "留中间"),
                          空跑=空跑, 上限秒=int(_参(参数, "上限秒", 7200) or 7200),
                          报=(lambda _: None) if json出 else (lambda s: print("   ", s)))
            except Exception as e:  # noqa: BLE001
                print(f"接片失败：{e}")
                return 1
        elif 命令 == "接龙":
            if len(位) < 2:
                print("接龙要至少两段 mp4")
                return 2
            果 = 接龙(位, 转场=_参(参数, "转场", "直接切"), 节奏=公共["节奏"],
                      空跑=空跑, 上限秒=公共["上限秒"],
                      报=(lambda _: None) if json出 else (lambda s: print("   ", s)))
        else:
            print(f"命令 {命令} 还没接上")
            return 2
    except ValueError as e:
        print(f"参数不行：{e}")
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"出片失败：{type(e).__name__}: {e}")
        if _引擎 is not None and hasattr(_引擎, "提交未知") and isinstance(e, _引擎.提交未知):
            print("⚠ 这是「提交未知」不是「失败」—— 提示号已经拿到手了，活可能已经交出去、钱可能已经花了。")
            print("   飞彩的规矩：超时 ≠ 失败。去 ComfyUI 的 /history 上按提示号查，别急着重跑。")
            try:
                记任务(状态="indeterminate", 备注=f"提交未知：{e}"[:300])
            except Exception:  # noqa: BLE001
                pass
            return 1
        return 1

    if json出:
        print(json.dumps(果, ensure_ascii=False, indent=1, default=str))
    elif isinstance(果, dict) and 果.get("路"):
        print(f"成了：{果['路']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
