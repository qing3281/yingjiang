# -*- coding: utf-8 -*-
"""
剪映.py —— 影匠 → 剪映草稿工程导出

把「一组镜头（图片 / 视频 / 配音 / 台词）」写成一个剪映专业版能直接打开的草稿目录。

═══════════════════════════════════════════════════════════════════════════════
【格式可信度声明】—— 请先读完这一段再看代码
═══════════════════════════════════════════════════════════════════════════════

▌结论：飞彩的剪映草稿格式 —— **未挖到**。

  在 `D:\\DSHworkspace\\网盘\\_飞彩解包\\Win\\` 全域（含 `.next\\` 全部 409 个 js
  以及解包根所有文本文件）搜索：

      draft_content    → 0 命中
      draft_meta_info  → 0 命中
      剪映             → 1 个文件 8 处（只在设置页，见下）
      JianyingPro      → 1 个文件 6 处（同上）
      lveditor         → 1 个文件 4 处（同上）

  飞彩**确实有**「导出剪映草稿」这个功能，但草稿文件本身的 JSON 结构在本包里
  一处都没有。写草稿的实现不在 `.next\\`（本包没有 `.next\\server\\`），
  应在未解包的 `server.pack` 或服务端。

▌唯一挖到的真证据（可以直接用，已写进本文件）：

  文件：`Win\\.next\\static\\chunks\\app\\settings\\page-e1d73e3724aa9bbb.js`
  搜词：`剪映` / `jianying-draft` / `JianyingPro`

  1) 设置页有一个区块：`data-settings-ui-section="jianying-draft"`
     标题「剪映草稿目录」，副标题「（导出剪映草稿时直接写入）」
     按钮「保存」→ `localStorage.setItem(键, 路径.trim())`
     失败文案「保存失败（localStorage 不可用）」

  2) 它按 `navigator.userAgent` 推断的默认目录（逐字）：
       Mac     : ~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft
       Windows : C:\\Users\\<你的用户名>\\AppData\\Local\\JianyingPro\\User Data\\
                 Projects\\com.lveditor.draft
     → 本文件的 `默认草稿目录()` 就是这么来的。

▌那下面这套 JSON 结构是哪来的？

  **公开通用知识**（剪映 / CapCut 草稿是社区长期逆向出来的互通格式），
  **不是**飞彩解包证据，**也未经本机剪映实测**（本机未确认安装剪映专业版）。

  所以本文件做了三件事，让「格式可能不准」这件事**不会悄悄毁掉你的工程**：

  A. 所有格式细节集中在 `_字段()` 与 `_构造_draft_content()` / `_构造_draft_meta_info()`
     里，**改格式 = 改数据，不用改逻辑**。
  B. `校验(草稿目录)` 会检查生成物的内部一致性（时长自洽、material_id 都有对应素材、
     时间轴无重叠无空洞），并把「无法自证」的部分列出来。
  C. 文件末尾有 `校准指南()`，告诉你**怎么用剪映自己生成的草稿反推真实字段**。

  ★ 如果你手上有剪映，**先做一次校准**再用（见 `校准指南()`）。不要盲信。

▌关于铁律

  本文件是**影匠原创实现**。飞彩包里没有剪映相关代码可抄（0 命中），
  一行都没有复制。授权 / 许可证 / 设备指纹 / 签名 / 计费相关逻辑：**完全未涉及**。

═══════════════════════════════════════════════════════════════════════════════
【数据结构】
═══════════════════════════════════════════════════════════════════════════════

镜头 = {
    "序号":   int,                     # 可选，缺省按列表顺序
    "素材":   str,                     # 必填，图片或视频的绝对路径
    "类型":   "图片" | "视频",          # 可选，缺省按后缀猜
    "时长":   float,                    # 秒。图片必填；视频可省（用探测值）
    "台词":   str,                      # 可选 → 生成一条字幕片段
    "配音":   str,                      # 可选 → 生成一条音频片段（绝对路径）
    "转场":   str,                      # 可选，"叠化" / "黑场" / 无
    "宽":     int,                      # 可选，跳过探测时用
    "高":     int,
}

分镜列表 = [镜头, 镜头, ...]

输出：<输出目录>/<戏名>/
        draft_content.json      ← 主时间轴
        draft_meta_info.json    ← 素材索引
        （可选）materials/      ← 收集模式下的素材副本

用法：
    import 剪映
    剪映.导出("第一集", 分镜列表)
    剪映.导出("第一集", 分镜列表, 输出目录=r"D:\\剪映草稿")

    python 剪映.py 自查        # 自检（造 3 个镜头跑一遍）
    python 剪映.py 默认目录    # 打印本机剪映草稿目录
    python 剪映.py 校准        # 打印校准指南
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

这里 = Path(__file__).resolve().parent

# ─────────────────────────── 格式来源标记 ───────────────────────────

格式来源 = "公开通用知识（非飞彩解包证据，未经剪映实测）"
飞彩证据 = "未挖到：.next 全域搜 draft_content / draft_meta_info 均 0 命中"
格式代号 = "JY-DRAFT-PUBLIC-v1"

# 剪映草稿的时间单位是**微秒**
微秒 = 1_000_000

图片后缀 = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic"}
视频后缀 = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".wmv"}

转场表 = {
    "叠化": "transition_dissolve",
    "黑场": "transition_fade_black",
    "白场": "transition_fade_white",
    "左滑": "transition_slide_left",
    "右滑": "transition_slide_right",
}


# ─────────────────────────── 平台默认目录 ───────────────────────────


def 默认草稿目录() -> Path:
    """
    按飞彩设置页的逻辑推断本机剪映草稿根目录。

    证据（逐字，`Win\\.next\\static\\chunks\\app\\settings\\page-e1d73e3724aa9bbb.js`）：
        Mac     : ~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft
        Windows : C:\\Users\\<你的用户名>\\AppData\\Local\\JianyingPro\\User Data\\Projects\\com.lveditor.draft
    """
    if os.name == "nt":
        户 = os.environ.get("USERPROFILE") or str(Path.home())
        return Path(户) / "AppData" / "Local" / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
    return Path.home() / "Movies" / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"


def 找草稿目录() -> Path:
    """返回一个真实存在的草稿目录；默认目录不存在就退回 影匠\\作品\\剪映草稿。"""
    默 = 默认草稿目录()
    if 默.is_dir():
        return 默
    return 这里 / "作品" / "剪映草稿"


# ─────────────────────────── 媒体探测 ───────────────────────────


def 探媒体(路: str | os.PathLike) -> dict:
    """
    探测一个媒体文件的时长 / 尺寸 / 有无音轨。

    图片走 PIL，音视频走 PyAV（本机没有 ffmpeg 在 PATH，所以只能用 av）。
    探测不到就填 None —— **绝不瞎编**。
    """
    路 = Path(路)
    果 = {"存在": 路.is_file(), "时长": None, "宽": None, "高": None,
          "有音轨": None, "类别": None, "错": ""}
    if not 果["存在"]:
        果["错"] = f"文件不存在：{路}"
        return 果

    后 = 路.suffix.lower()

    if 后 in 图片后缀:
        果["类别"] = "图片"
        try:
            from PIL import Image

            with Image.open(路) as 图:
                果["宽"], 果["高"] = int(图.width), int(图.height)
        except Exception as e:  # noqa: BLE001
            果["错"] = f"PIL 读图失败：{e}"
        return 果

    if 后 in 视频后缀:
        果["类别"] = "视频"
        try:
            import av

            with av.open(str(路)) as 罐:
                if 罐.duration is not None:
                    果["时长"] = 罐.duration / av.time_base
                for 流 in 罐.streams:
                    if 流.type == "video" and 果["宽"] is None:
                        果["宽"] = int(流.codec_context.width)
                        果["高"] = int(流.codec_context.height)
                        if 果["时长"] is None and 流.duration is not None and 流.time_base is not None:
                            果["时长"] = float(流.duration * 流.time_base)
                    if 流.type == "audio":
                        果["有音轨"] = True
                if 果["有音轨"] is None:
                    果["有音轨"] = False
        except Exception as e:  # noqa: BLE001
            果["错"] = f"PyAV 读视频失败：{e}"
        return 果

    if 后 in {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma"}:
        果["类别"] = "音频"
        try:
            import soundfile as sf

            信息 = sf.info(str(路))
            果["时长"] = float(信息.frames) / float(信息.samplerate)
        except Exception:
            try:
                import av

                with av.open(str(路)) as 罐:
                    if 罐.duration is not None:
                        果["时长"] = 罐.duration / av.time_base
            except Exception as e:  # noqa: BLE001
                果["错"] = f"读音频失败：{e}"
        return 果

    果["类别"] = "未知"
    果["错"] = f"不认识的后缀：{后}"
    return 果


# ─────────────────────────── 基础构件 ───────────────────────────


def _ID() -> str:
    """剪映的 id 是大写带横线的 UUID。"""
    return str(uuid.uuid4()).upper()


def _秒(v: float) -> int:
    return int(round(float(v) * 微秒))


def _猜类型(路: str | os.PathLike, 声明: str | None = None) -> str:
    if 声明 in ("图片", "视频"):
        return 声明
    后 = Path(路).suffix.lower()
    if 后 in 图片后缀:
        return "图片"
    if 后 in 视频后缀:
        return "视频"
    raise ValueError(f"分不清这是图片还是视频，请在镜头里写死「类型」：{路}")


# ─────────────────────────── 素材构造 ───────────────────────────
#
# ↓↓↓ 这一整段是「格式适配层」：格式不对，只改这里，不用动别的 ↓↓↓


def _素材_视频(路: str, 时长: float, 宽: int, 高: int, 有音轨: bool = False) -> dict:
    return {
        "id": _ID(),
        "type": "video",
        "path": str(路),
        "material_name": Path(路).name,
        "duration": _秒(时长),
        "width": int(宽),
        "height": int(高),
        "category_name": "local",
        "extra_type_option": 0,
        "has_audio": bool(有音轨),
        "use_audio": bool(有音轨),
        "audio_fade": None,
        "crop": {
            "lower_left_x": 0.0, "lower_left_y": 0.0,
            "lower_right_x": 1.0, "lower_right_y": 0.0,
            "upper_left_x": 0.0, "upper_left_y": 1.0,
            "upper_right_x": 1.0, "upper_right_y": 1.0,
        },
        "crop_ratio": "free",
        "crop_scale": 1.0,
        "beauty_body_preset_id": "",
        "beauty_face_preset_id": "",
        "smart_motion": None,
        "stable": None,
        "matting": None,
        "source_platform": 0,
        "video_algorithm": {
            "algorithms": [],
            "complement_frame_config": None,
            "deflicker": None,
            "gameplay_configs": [],
            "motion_blur_config": None,
            "noise_reduction": None,
            "path": "",
            "quality_enhan": None,
            "smart_complement_frame": None,
            "super_resolution": None,
            "time_range": None,
        },
        "aigc_type": "none",
        "is_ai_generate_content": False,
        "picture_from": "none",
        "picture_set_category_id": "",
        "picture_set_category_name": "",
        "origin_material_id": "",
        "external_material_id": "",
    }


def _素材_图片(路: str, 时长: float, 宽: int, 高: int) -> dict:
    """剪映内部把静图也当 video 素材，只是 type 记成 photo。"""
    素 = _素材_视频(路, 时长, 宽, 高, 有音轨=False)
    素["type"] = "photo"
    素["has_audio"] = False
    素["use_audio"] = False
    return 素


def _素材_音频(路: str, 时长: float, 名: str = "") -> dict:
    return {
        "id": _ID(),
        "type": "audio",
        "path": str(路),
        "name": 名 or Path(路).name,
        "duration": _秒(时长),
        "app_id": 0,
        "category_id": "",
        "category_name": "local",
        "extra_type_option": 0,
        "formula_id": "",
        "intensifies_path": "",
        "music_id": "",
        "query": "",
        "request_id": "",
        "resource_id": "",
        "source_platform": 0,
        "team_id": "",
        "text_id": "",
        "tone_category_id": "",
        "tone_category_name": "",
        "tone_effect_id": "",
        "tone_effect_name": "",
        "tone_platform": "",
        "tone_second_category_id": "",
        "tone_second_category_name": "",
        "tone_speaker": "",
        "tone_type": "",
        "video_id": "",
        "wave_points": [],
    }


def _素材_文本(文本: str, 字号: float = 8.0) -> dict:
    """
    文本素材。剪映 5.x 起 `content` 是一段 **JSON 字符串**（富文本描述），
    不是早期版本的 `<font>…</font>` 片段。

    ★ 这一处是本文件里**最可能随版本漂移**的地方，校准指南第 3 条专门讲它。
    """
    富文本 = {
        "text": 文本,
        "styles": [
            {
                "fill": {"content": {"solid": {"color": [1.0, 1.0, 1.0]}}},
                "range": [0, len(文本)],
                "size": 字号,
                "font": {"id": "", "path": ""},
                "strokes": [
                    {"content": {"solid": {"color": [0.0, 0.0, 0.0]}},
                     "width": 0.08}
                ],
            }
        ],
    }
    return {
        "id": _ID(),
        "type": "text",
        "content": json.dumps(富文本, ensure_ascii=False),
        "text_color": "#FFFFFF",
        "font_size": 字号,
        "alignment": 1,
        "letter_spacing": 0.0,
        "line_spacing": 0.02,
        "words": {"text": [], "start_time": [], "end_time": []},
        "typesetting": 0,
        "check_flag": 7,
        "fixed_width": -1.0,
        "fixed_height": -1.0,
        "background_color": "",
        "background_style": 0,
        "background_alpha": 1.0,
        "has_shadow": False,
        "shadow_color": "",
        "shadow_alpha": 0.9,
        "shadow_angle": -45.0,
        "shadow_distance": 5.0,
        "shadow_smoothing": 0.45,
        "border_color": "",
        "border_width": 0.08,
        "border_alpha": 1.0,
        "base_content": "",
        "recognize_type": 0,
        "global_alpha": 1.0,
        "group_id": "",
        "is_rich_text": True,
    }


def _素材_转场(名: str, 时长: float = 0.5) -> dict:
    return {
        "id": _ID(),
        "type": "transition",
        "name": 名,
        "duration": _秒(时长),
        "is_overlap": False,
        "category_id": "",
        "category_name": "",
        "effect_id": 转场表.get(名, "transition_dissolve"),
        "resource_id": "",
        "platform": "all",
        "source_platform": 0,
        "path": "",
    }


def _片段(素材号: str, 起: float, 时长: float, 源起: float = 0.0,
          渲染序: int = 0, 音量: float = 1.0, 附加素材: list[str] | None = None) -> dict:
    return {
        "id": _ID(),
        "material_id": 素材号,
        "target_timerange": {"start": _秒(起), "duration": _秒(时长)},
        "source_timerange": {"start": _秒(源起), "duration": _秒(时长)},
        "extra_material_refs": list(附加素材 or []),
        "render_index": int(渲染序),
        "keyframe_refs": [],
        "visible": True,
        "volume": float(音量),
        "speed": 1.0,
        "reverse": False,
        "is_placeholder": False,
        "is_tone_modify": False,
        "intensifies_audio": False,
        "cartoon": False,
        "enable_adjust": True,
        "enable_color_correct_adjust": False,
        "enable_color_curves": True,
        "enable_color_match_adjust": False,
        "enable_color_wheels": True,
        "enable_lut": True,
        "enable_smart_color_adjust": False,
        "last_nonzero_volume": float(音量),
        "template_id": "",
        "template_scene": "default",
        "track_attribute": 0,
        "track_render_index": int(渲染序),
        "uniform_scale": {"on": True, "value": 1.0},
        "group_id": "",
        "clip": {
            "alpha": 1.0,
            "flip": {"horizontal": False, "vertical": False},
            "rotation": 0.0,
            "scale": {"x": 1.0, "y": 1.0},
            "transform": {"x": 0.0, "y": 0.0},
        },
        "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
        "caption_info": None,
    }


def _空轨(类型: str) -> dict:
    return {
        "id": _ID(),
        "type": 类型,          # video / audio / text / sticker / effect / filter
        "segments": [],
        "flag": 0,
        "attribute": 0,
        "is_default_name": True,
        "name": "",
    }


def _空素材柜() -> dict:
    return {
        "audios": [], "videos": [], "texts": [], "stickers": [],
        "canvases": [], "speeds": [], "placeholders": [],
        "sound_channel_mappings": [], "beats": [], "common_keyframes": [],
        "effects": [], "filters": [], "handwrites": [], "transitions": [],
        "audio_effects": [], "audio_fades": [], "material_animations": [],
        "video_effects": [], "video_trackings": [],
    }


# ↑↑↑ 格式适配层结束 ↑↑↑


# ─────────────────────────── 主构造 ───────────────────────────


def _构造草稿(戏名: str, 分镜列表: list[dict], 画布: tuple[int, int],
              帧率: float) -> tuple[dict, dict, list[str]]:
    """
    返回 (draft_content, draft_meta_info, 警告们)。

    轨道规划：
        视频轨（主）  ← 每个镜头的图片 / 视频，按 时长 顺序首尾相接
        配音轨        ← 有「配音」的镜头生成一条音频片段，起点 = 该镜头起点
        字幕轨        ← 有「台词」的镜头生成一条文本片段，时长 = 镜头时长
    """
    警告: list[str] = []
    素材柜 = _空素材柜()
    视轨 = _空轨("video")
    音轨 = _空轨("audio")
    字幕轨 = _空轨("text")

    总时长 = 0.0
    上镜头有转场 = False

    for i, 镜 in enumerate(分镜列表):
        序号 = 镜.get("序号", i + 1)
        素材路 = 镜.get("素材") or 镜.get("路径") or 镜.get("图")
        if not 素材路:
            警告.append(f"第 {序号} 个镜头没有「素材」，跳过")
            continue
        素材路 = str(Path(素材路).expanduser())

        查 = 探媒体(素材路)
        if not 查["存在"]:
            警告.append(f"第 {序号} 个镜头素材不存在，仍写进草稿（剪映会显示离线）：{素材路}")

        类型 = _猜类型(素材路, 镜.get("类型"))
        宽 = 镜.get("宽") or 查["宽"] or 画布[0]
        高 = 镜.get("高") or 查["高"] or 画布[1]

        时长 = 镜.get("时长")
        if 时长 is None:
            时长 = 查["时长"]
        if 时长 is None:
            时长 = 3.0
            警告.append(f"第 {序号} 个镜头没给「时长」也探测不到，按 3.0 秒算：{Path(素材路).name}")
        时长 = float(时长)
        if 时长 <= 0:
            警告.append(f"第 {序号} 个镜头时长 {时长} 不合理，改成 1.0 秒")
            时长 = 1.0

        附件: list[str] = []

        if 类型 == "图片":
            素 = _素材_图片(素材路, 时长, 宽, 高)
        else:
            素 = _素材_视频(素材路, 时长, 宽, 高, bool(查["有音轨"]))
            源 = 查["时长"]
            if 源 is not None and 源 + 0.02 < 时长:
                警告.append(
                    f"第 {序号} 个镜头要 {时长:.2f} 秒，但视频只有 {源:.2f} 秒 —— "
                    f"剪映里这一段会黑尾。建议缩短时长或加慢放。"
                )
        素材柜["videos"].append(素)

        # 转场挂在片段上（放在 source 段末尾，剪映习惯）
        转 = 镜.get("转场")
        if 转 and 转 in 转场表:
            转素 = _素材_转场(转)
            素材柜["transitions"].append(转素)
            附件.append(转素["id"])
            上镜头有转场 = True
        elif 转:
            警告.append(f"第 {序号} 个镜头写了不认识的转场「{转}」，忽略")

        片 = _片段(素["id"], 总时长, 时长, 渲染序=len(视轨["segments"]), 附加素材=附件)
        视轨["segments"].append(片)

        # 配音
        配 = 镜.get("配音")
        if 配:
            配 = str(Path(配).expanduser())
            配查 = 探媒体(配)
            if 配查["时长"] is None:
                警告.append(f"第 {序号} 个镜头配音探测不到时长，按镜头时长 {时长:.2f} 秒算：{配}")
            音响 = 配查["时长"] if 配查["时长"] else 时长
            if 配查["时长"] and 配查["时长"] > 时长 + 0.05:
                警告.append(
                    f"第 {序号} 个镜头配音 {配查['时长']:.2f} 秒 > 镜头 {时长:.2f} 秒 —— "
                    f"声音会被切断。台词建议按 max(1.5, 0.25×字数) 秒估时长。"
                )
            音素 = _素材_音频(配, 音响, 名=f"{序号:02d}_{Path(配).name}")
            素材柜["audios"].append(音素)
            音轨["segments"].append(
                _片段(音素["id"], 总时长, min(音响, 时长) if 配查["时长"] else 时长,
                      渲染序=len(音轨["segments"]))
            )

        # 台词 → 字幕
        台词 = (镜.get("台词") or "").strip()
        if 台词:
            字素 = _素材_文本(台词)
            素材柜["texts"].append(字素)
            字幕轨["segments"].append(
                _片段(字素["id"], 总时长, 时长, 渲染序=len(字幕轨["segments"]))
            )

        总时长 += 时长

    if 上镜头有转场:
        警告.append("转场需要相邻两个片段有重叠才看得出效果；当前是首尾相接，剪映里可能要手动拖一下。")

    轨们 = [视轨]
    if 字幕轨["segments"]:
        轨们.append(字幕轨)
    if 音轨["segments"]:
        轨们.append(音轨)

    草稿号 = _ID()
    内容 = {
        "id": 草稿号,
        "name": 戏名,
        "duration": _秒(总时长),
        "fps": float(帧率),
        "canvas_config": {
            "width": int(画布[0]),
            "height": int(画布[1]),
            "ratio": "original",
        },
        "tracks": 轨们,
        "materials": 素材柜,
        "keyframes": {
            "adjusts": [], "audios": [], "effects": [], "filters": [],
            "handwrites": [], "stickers": [], "texts": [], "videos": [],
        },
        "keyframe_graph_list": [],
        "relationships": [],
        "platform": {
            "app_id": 0,
            "app_source": "lv",
            "app_version": "5.9.0",
            "device_id": "",
            "hardware_name": "",
            "os": "windows" if os.name == "nt" else "mac",
            "os_version": "",
        },
        "last_modified_platform": {
            "app_id": 0,
            "app_source": "lv",
            "app_version": "5.9.0",
            "device_id": "",
            "hardware_name": "",
            "os": "windows" if os.name == "nt" else "mac",
            "os_version": "",
        },
        "color_space": 0,
        "config": {
            "adjusts": [], "audio_effects": [], "audio_fades": [],
            "audio_pannings": [], "audio_pitch_shifts": [], "audio_trackings": [],
            "audios": [], "beats": [], "canvases": [], "chromas": [],
            "color_curves": [], "common_keyframes": [], "drafts": [],
            "effects": [], "filters": [], "green_screens": [], "handwrites": [],
            "hsl": [], "images": [], "log_color_wheels": [], "loudnesses": [],
            "manual_deformations": [], "masks": [], "material_animations": [],
            "material_colors": [], "multi_language_refs": [], "placeholders": [],
            "plugin_effects": [], "primary_color_wheels": [], "realtime_denoises": [],
            "shapes": [], "smart_crops": [], "smart_relights": [], "sound_channel_mappings": [],
            "speeds": [], "stickers": [], "tail_leaders": [], "text_templates": [],
            "texts": [], "time_marks": [], "transitions": [], "video_effects": [],
            "video_trackings": [], "videos": [], "vocal_beautifys": [],
            "vocal_separations": [],
        },
        "extra_info": None,
        "free_render_index_mode_on": False,
        "mutable_config": None,
        "new_version": "110.0.0",
        "render_index_track_mode_on": False,
        "source": "default",
        "version": 360000,
        "cover": None,
        "create_time": int(time.time()),
        "update_time": int(time.time()),
    }

    素录 = []
    for v in 素材柜["videos"]:
        素录.append({
            "id": v["id"],
            "type": v["type"],
            "path": v["path"],
            "duration": v["duration"],
            "width": v.get("width", 0),
            "height": v.get("height", 0),
            "create_time": int(time.time()),
            "import_time": int(time.time()),
            "extra_info": Path(v["path"]).name,
            "file_Path": v["path"],
            "metetype": "photo" if v["type"] == "photo" else "video",
            "roughcut_time_range": {"start": 0, "duration": v["duration"]},
            "sub_time_range": {"start": -1, "duration": -1},
        })
    for a in 素材柜["audios"]:
        素录.append({
            "id": a["id"],
            "type": "audio",
            "path": a["path"],
            "duration": a["duration"],
            "name": a.get("name", ""),
            "create_time": int(time.time()),
            "import_time": int(time.time()),
            "extra_info": Path(a["path"]).name,
            "file_Path": a["path"],
            "metetype": "music",
            "roughcut_time_range": {"start": 0, "duration": a["duration"]},
            "sub_time_range": {"start": -1, "duration": -1},
        })
    for t in 素材柜["texts"]:
        素录.append({
            "id": t["id"],
            "type": "text",
            "duration": 0,
            "create_time": int(time.time()),
            "import_time": int(time.time()),
            "extra_info": (t.get("content") or "")[:64],
            "metetype": "text",
            "roughcut_time_range": {"start": 0, "duration": 0},
            "sub_time_range": {"start": -1, "duration": -1},
        })

    元信息 = {
        "draft_id": 草稿号,
        "draft_name": 戏名,
        "draft_fold_path": "",
        "draft_root_path": "",
        "draft_cloud_capcut_purchase_info": "",
        "draft_removable_storage_device": "",
        "draft_cover": "",
        "draft_enterprise_info": {"draft_enterprise_extra": "", "draft_enterprise_id": "",
                                  "draft_enterprise_name": "", "enterprise_draft": {}},
        "draft_id_md5": "",
        "draft_type": "",
        "draft_timeline_materials_size_": 0,
        "draft_materials_copied_info": [],
        "draft_materials": [{"type": 0, "value": 素录}],
        "draft_segment_extra_info": [],
        "draft_deeplink_url": "",
        "draft_is_ae_produce": False,
        "draft_is_ai_packaging_used": False,
        "draft_is_ai_shorts": False,
        "draft_is_ai_translate": False,
        "draft_is_article_video_draft": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_from_deeplink": "false",
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_need_rename_folder": False,
        "draft_platform": {"app_id": 0, "app_source": "lv", "app_version": "5.9.0",
                           "device_id": "", "hardware_name": "",
                           "os": "windows" if os.name == "nt" else "mac", "os_version": ""},
        "draft_removable_storage_device_list": [],
        "draft_timeline_materials_size": 0,
        "draft_total_duration": _秒(总时长),
        "draft_version": "110.0.0",
    }

    return 内容, 元信息, 警告


# ─────────────────────────── 对外接口 ───────────────────────────


def 导出(戏名: str, 分镜列表: list[dict], 输出目录: str | os.PathLike | None = None,
        画布: tuple[int, int] = (1080, 1920), 帧率: float = 30.0,
        收集素材: bool = False, 覆盖: bool = True) -> dict:
    """
    把一组镜头写成一个剪映草稿工程目录。

    参数
    ----
    戏名      : 草稿工程名，也是目录名
    分镜列表  : [镜头, …]，见文件头「数据结构」
    输出目录  : 草稿**根**目录（里面会建 <戏名>/）；缺省用 找草稿目录()
    画布      : (宽, 高) 像素，默认竖屏 1080×1920
    帧率      : 默认 30.0
    收集素材  : True 时把媒体复制进 <草稿>/materials/，工程可整体搬走
    覆盖      : 同名草稿已存在时是否覆盖

    返回
    ----
    {"草稿目录", "draft_content", "draft_meta_info", "镜头数", "总时长",
     "警告":[…], "格式来源", "飞彩证据"}
    """
    if not 分镜列表:
        raise ValueError("分镜列表是空的，没什么可导的")

    根 = Path(输出目录).expanduser() if 输出目录 else 找草稿目录()
    草稿夹 = 根 / 戏名

    if 草稿夹.exists():
        if not 覆盖:
            raise FileExistsError(f"草稿已存在：{草稿夹}（要覆盖就把 覆盖=True）")
        shutil.rmtree(草稿夹)
    草稿夹.mkdir(parents=True, exist_ok=True)

    片段表 = [dict(镜) for 镜 in 分镜列表]

    if 收集素材:
        素夹 = 草稿夹 / "materials"
        素夹.mkdir(exist_ok=True)
        for 镜 in 片段表:
            for 键 in ("素材", "配音"):
                路 = 镜.get(键)
                if not 路:
                    continue
                源 = Path(str(路)).expanduser()
                if 源.is_file():
                    目标 = 素夹 / 源.name
                    if not 目标.exists():
                        shutil.copy2(源, 目标)
                    镜[键] = str(目标)

    内容, 元信息, 警告 = _构造草稿(戏名, 片段表, 画布, 帧率)

    文路 = 草稿夹 / "draft_content.json"
    元路 = 草稿夹 / "draft_meta_info.json"
    文路.write_text(json.dumps(内容, ensure_ascii=False, indent=4), encoding="utf-8")
    元路.write_text(json.dumps(元信息, ensure_ascii=False, indent=4), encoding="utf-8")

    return {
        "草稿目录": str(草稿夹),
        "draft_content": str(文路),
        "draft_meta_info": str(元路),
        "镜头数": len(内容["tracks"][0]["segments"]) if 内容["tracks"] else 0,
        "总时长": 内容["duration"] / 微秒,
        "警告": 警告,
        "格式来源": 格式来源,
        "飞彩证据": 飞彩证据,
    }


def 校验(草稿目录: str | os.PathLike) -> dict:
    """
    自检生成的草稿：能证实的证实，证实不了的**明说证实不了**。

    能查的（纯 JSON 内部一致性）：
      · 两个文件都在、都能解析
      · 每个 tracks[].segments[].material_id 都能在 materials 里找到
      · 每个 extra_material_refs 都能找到
      · 时间轴首尾相接、无重叠、无空洞
      · draft_content.duration == 最后一段的 end
      · draft_meta_info.draft_materials 的 id 与 materials 对得上

    查不了的（必须在剪映里开一次才知道）：
      · 剪映这个版本认不认这些字段名
      · 文本素材 content 的富文本格式
      · 转场 effect_id 对不对
    """
    夹 = Path(草稿目录)
    报 = {"通过": [], "问题": [], "无法自证": []}

    def 过(话): 报["通过"].append(话)
    def 错(话): 报["问题"].append(话)

    文路 = 夹 / "draft_content.json"
    元路 = 夹 / "draft_meta_info.json"
    if not 文路.is_file():
        错(f"缺 draft_content.json：{文路}")
        return 报
    if not 元路.is_file():
        错(f"缺 draft_meta_info.json（剪映可能仍能开，但素材库会是空的）：{元路}")

    try:
        内容 = json.loads(文路.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        错(f"draft_content.json 不是合法 JSON：{e}")
        return 报
    过("draft_content.json 是合法 JSON")

    素材柜 = 内容.get("materials", {})
    全部素材号 = set()
    for 类, 列 in 素材柜.items():
        for 素 in 列 or []:
            if isinstance(素, dict) and 素.get("id"):
                全部素材号.add(素["id"])

    轨们 = 内容.get("tracks", [])
    if not 轨们:
        错("没有任何轨道")
        return 报
    过(f"有 {len(轨们)} 条轨道：{', '.join(t.get('type','?') for t in 轨们)}")

    错数 = 0
    for ti, 轨 in enumerate(轨们):
        for 片 in 轨.get("segments", []):
            mid = 片.get("material_id")
            if mid not in 全部素材号:
                错(f"轨道{ti} 的片段 material_id={mid} 在 materials 里找不到")
                错数 += 1
            for r in 片.get("extra_material_refs", []):
                if r not in 全部素材号:
                    错(f"轨道{ti} 的 extra_material_refs 里 {r} 找不到")
                    错数 += 1
    if 错数 == 0:
        过("所有片段的 material_id / extra_material_refs 都有对应素材")

    视轨 = next((t for t in 轨们 if t.get("type") == "video"), None)
    if 视轨 is None:
        错("没有 video 轨，剪映打开会是空的")
    else:
        段 = 视轨.get("segments", [])
        游标 = 0
        空洞 = []
        for 片 in 段:
            tr = 片.get("target_timerange", {})
            起 = tr.get("start", 0)
            if 起 != 游标:
                空洞.append((游标 / 微秒, 起 / 微秒))
            游标 = 起 + tr.get("duration", 0)
        if 空洞:
            错(f"主视频轨有 {len(空洞)} 处缝隙/重叠：{空洞[:4]}")
        else:
            过(f"主视频轨首尾相接，共 {len(段)} 段")
        总 = 内容.get("duration", 0)
        if abs(总 - 游标) > 1000:
            错(f"draft_content.duration={总/微秒:.3f}s 与轨道末尾 {游标/微秒:.3f}s 对不上")
        else:
            过(f"总时长自洽：{总/微秒:.3f} 秒")

    if 元路.is_file():
        try:
            元 = json.loads(元路.read_text(encoding="utf-8"))
            号 = set()
            for 组 in 元.get("draft_materials", []):
                for 素 in 组.get("value", []):
                    if 素.get("id"):
                        号.add(素["id"])
            漏 = 号 - 全部素材号
            if 漏:
                错(f"draft_meta_info 里有 {len(漏)} 个素材在 draft_content 里没有")
            else:
                过(f"draft_meta_info 的 {len(号)} 个素材都在 draft_content 里")
        except Exception as e:  # noqa: BLE001
            错(f"draft_meta_info.json 解析失败：{e}")

    报["无法自证"] = [
        "这些字段名是不是你这个剪映版本认的（本文件格式来自公开通用知识，非解包证据）",
        "文本素材 materials.texts[].content 的富文本 JSON 格式",
        "转场的 effect_id 命名",
        "剪映能否接受 version=360000 / new_version=110.0.0",
    ]
    return 报


def 列草稿(目录: str | os.PathLike | None = None) -> list[dict]:
    """列出一个草稿根目录下的所有草稿。"""
    根 = Path(目录).expanduser() if 目录 else 找草稿目录()
    出 = []
    if not 根.is_dir():
        return 出
    for 子 in sorted(根.iterdir()):
        if not 子.is_dir():
            continue
        文 = 子 / "draft_content.json"
        if not 文.is_file():
            continue
        时长 = None
        try:
            时长 = json.loads(文.read_text(encoding="utf-8")).get("duration", 0) / 微秒
        except Exception:  # noqa: BLE001
            pass
        出.append({"名": 子.name, "路": str(子), "总时长": 时长})
    return 出


def 清草稿(戏名: str, 输出目录: str | os.PathLike | None = None) -> bool:
    根 = Path(输出目录).expanduser() if 输出目录 else 找草稿目录()
    夹 = 根 / 戏名
    if 夹.is_dir():
        shutil.rmtree(夹)
        return True
    return False


def 校准指南() -> str:
    return f"""
════════════════════════════════════════════════════════════════════════
剪映草稿格式校准指南
════════════════════════════════════════════════════════════════════════

本文件用的格式：{格式代号}
来源：{格式来源}
飞彩证据：{飞彩证据}

也就是说：**这套字段名是社区互通格式，我没有在飞彩包里找到、也没在你机器上的
剪映里验证过。** 剪映版本之间字段会漂。用之前花 5 分钟校准一次，比导出十个
打不开的工程划算。

校准步骤
────────
1. 打开剪映专业版，手工做一个最简单的工程：
       · 1 张图（3 秒）
       · 1 段配音
       · 1 行字幕
       · 1 个叠化转场
   保存。然后在剪映草稿目录里找到它：
       {默认草稿目录()}

2. 把它的 draft_content.json 和本文件生成的对比。重点看这 6 处：

   ① tracks[].type 的取值            （是 "video"/"audio"/"text" 吗？有没有 "main"？）
   ② materials.videos[].type         （静图是 "photo" 还是 "video"？）
   ③ materials.texts[].content       （是 JSON 字符串，还是 "<font>…</font>"？）
   ④ target_timerange 的单位         （微秒 1e6？还是毫秒 1e3？）
   ⑤ version / new_version            （顶层那两个版本号是多少）
   ⑥ segments[] 里缺哪些字段会打不开 （逐字段删一遍试，记下哪个是必需的）

3. 改哪里：
       · 字段名/默认值  → 本文件 `_素材_*` / `_片段` / `_空轨` / `_构造草稿`
       · 时间单位       → 本文件顶部常量 `微秒`
       · 版本号         → `_构造草稿()` 里的 "version" / "new_version"

   改完跑 `python 剪映.py 自查`，再在剪映里开一次。

4. 校准完把差异写回本文件的注释里 —— 下次就不用再校准了。

如果你**暂时没有剪映**：可以先只用本文件的「轨道规划」逻辑（镜头顺序、时长、
音画对齐、台词时长估算），把 JSON 输出当成一份中间清单用，等有剪映了再对接。
════════════════════════════════════════════════════════════════════════
"""


# ─────────────────────────── 自测 ───────────────────────────


def _造假素材(夹: Path) -> list[dict]:
    """造 3 个镜头：2 张图 + 1 段假视频 + 2 段配音。"""
    夹.mkdir(parents=True, exist_ok=True)

    from PIL import Image, ImageDraw

    图路 = []
    for i, (宽, 高) in enumerate([(1080, 1920), (1080, 1920), (1920, 1080)], 1):
        图 = Image.new("RGB", (宽, 高), (20 + i * 30, 18, 40))
        笔 = ImageDraw.Draw(图)
        笔.rectangle([40, 40, 宽 - 40, 高 - 40], outline=(200, 170, 90), width=8)
        笔.text((60, 60), f"影匠 selftest shot {i}", fill=(240, 235, 220))
        p = 夹 / f"镜头{i}.png"
        图.save(p)
        图路.append(str(p))

    # 假视频：用 av 编 1 秒 30 帧
    视路 = ""
    try:
        import av
        import numpy as np

        p = 夹 / "镜头3.mp4"
        with av.open(str(p), mode="w") as 罐:
            流 = 罐.add_stream("mpeg4", rate=30)
            流.width, 流.height, 流.pix_fmt = 640, 360, "yuv420p"
            for n in range(30):
                阵 = np.full((360, 640, 3), (n * 8) % 255, dtype=np.uint8)
                帧 = av.VideoFrame.from_ndarray(阵, format="rgb24")
                罐.mux(流.encode(帧))
            for 包 in 流.encode():
                罐.mux(包)
        视路 = str(p)
    except Exception as e:  # noqa: BLE001
        print(f"  （造视频失败，改用图片顶替：{e}）")
        视路 = 图路[2]

    # 假配音：1 秒 440Hz 正弦，用 stdlib wave 写
    import array
    import math
    import wave

    音路 = []
    for i, 秒 in enumerate([1.4, 2.2], 1):
        p = 夹 / f"配音{i}.wav"
        率 = 24000
        with wave.open(str(p), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(率)
            样 = array.array("h", (
                int(9000 * math.sin(2 * math.pi * 440 * t / 率))
                for t in range(int(率 * 秒))
            ))
            w.writeframes(样.tobytes())
        音路.append(str(p))

    return [
        {"序号": 1, "素材": 图路[0], "类型": "图片", "时长": 3.0,
         "台词": "她缓缓转过头来。", "配音": 音路[0]},
        {"序号": 2, "素材": 图路[1], "类型": "图片", "时长": 4.0,
         "台词": "窗外，雪落了一整夜。", "转场": "叠化"},
        {"序号": 3, "素材": 视路, "时长": 3.0},
        {"序号": 4, "素材": 图路[2], "类型": "图片", "时长": 2.0,
         "台词": "（旁白）故事，从这里开始。", "配音": 音路[1]},
    ]


def 自查(输出目录: str | os.PathLike | None = None) -> int:
    """造一套假数据，跑一遍导出 + 校验。返回 0 表示通过。"""
    import tempfile

    print("=" * 68)
    print("剪映.py 自查")
    print("=" * 68)
    print(f"格式来源：{格式来源}")
    print(f"飞彩证据：{飞彩证据}")
    print()

    临时 = Path(tempfile.mkdtemp(prefix="yj_jianying_"))
    try:
        素 = _造假素材(临时 / "素材")
        print(f"造了 {len(素)} 个假镜头 → {临时/'素材'}")

        # 1. 探测
        print("\n[1/4] 媒体探测")
        for 镜 in 素:
            for 键 in ("素材", "配音"):
                if 镜.get(键):
                    查 = 探媒体(镜[键])
                    print(f"    {Path(镜[键]).name:20s} 类别={查['类别']} "
                          f"时长={查['时长'] and round(查['时长'],3)} "
                          f"尺寸={查['宽']}x{查['高']} 错={查['错'] or '无'}")

        # 2. 导出
        print("\n[2/4] 导出草稿")
        果 = 导出("影匠自查戏", 素, 输出目录=临时 / "草稿", 收集素材=False)
        print(f"    草稿目录：{果['草稿目录']}")
        print(f"    镜头数  ：{果['镜头数']}   总时长：{果['总时长']} 秒")
        for w in 果["警告"]:
            print(f"    ⚠ {w}")
        if not 果["警告"]:
            print("    无警告")

        # 3. 校验
        print("\n[3/4] 校验")
        报 = 校验(果["草稿目录"])
        for x in 报["通过"]:
            print(f"    ✓ {x}")
        for x in 报["问题"]:
            print(f"    ✗ {x}")
        print("    （以下必须由剪映本体确认，本文件无法自证）")
        for x in 报["无法自证"]:
            print(f"    ? {x}")

        # 4. 文件
        print("\n[4/4] 落盘文件")
        for 名 in ("draft_content.json", "draft_meta_info.json"):
            p = Path(果["草稿目录"]) / 名
            print(f"    {名:24s} {p.stat().st_size if p.is_file() else 0} 字节")
        print(f"\n    列草稿：{列草稿(临时/'草稿')}")

        print("\n" + "=" * 68)
        if 报["问题"]:
            print(f"自查不通过：{len(报['问题'])} 个问题")
            return 1
        print("自查通过（内部一致性 OK；剪映能不能打开仍需实机确认）")
        print(f"临时产物留在：{临时}")
        print("=" * 68)
        return 0
    except Exception as e:  # noqa: BLE001
        import traceback

        print(f"\n自查崩了：{e}")
        traceback.print_exc()
        return 2


def _主() -> int:
    参 = sys.argv[1:]
    if not 参:
        print(__doc__)
        return 0
    令 = 参[0]
    if 令 in ("自查", "自测", "selftest"):
        return 自查()
    if 令 in ("默认目录", "目录"):
        print(f"平台默认：{默认草稿目录()}")
        print(f"实际使用：{找草稿目录()}")
        return 0
    if 令 in ("列", "列表"):
        for 条 in 列草稿(参[1] if len(参) > 1 else None):
            print(f"  {条['名']}  {条['总时长']}s  {条['路']}")
        return 0
    if 令 == "校准":
        print(校准指南())
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(_主())
