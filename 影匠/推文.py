# -*- coding: utf-8 -*-
"""
影匠 · 推文工作台  —— 功能对齐飞彩 FEICAI-Studio「推文模式」
================================================================
一条推文 → 分镜（10/15/30 秒叙事合集）→ 九宫格配图 → 配视频 → 排期表 → 导出

    先建      python 推文.py 先建 春江花月夜 --时长 15 --时代 "盛唐"
    正文      python 推文.py 正文 春江花月夜 --文 "孤篇盖全唐，张若虚这一夜写了什么" --话题 "唐诗,国风"
    分镜      python 推文.py 分镜 春江花月夜 --条数 4
    配图      python 推文.py 配图 春江花月夜 --九宫格          # 3×3 九宫格分镜图
    配图      python 推文.py 配图 春江花月夜 --单格 1          # 只出第 1 格
    配视频    python 推文.py 配视频 春江花月夜 --模式 全能参考
    排期      python 推文.py 排期 春江花月夜
    导出      python 推文.py 导出 春江花月夜
    体检      python 推文.py 体检 春江花月夜
    自测      python 推文.py 自测

开关：--空跑 只演一遍不碰 ComfyUI（不联网、不出图、不出片）
      --json 把结果打成 JSON 打到 stdout（给 MCP / 别的程序读）
      --重做 已有产物也重出

退出码：0 成功　2 参数/命令不对　3 上游没到位　4 出图出片失败

------------------------------------------------------------
抄自飞彩哪里（证据见 知识\\推文与电商.md）
------------------------------------------------------------
· 分镜数据契约 —— 逐字对齐飞彩 studio 包模块 88350 的 `ih()` 构造器：
      {id, shot, videoShot, meta:{characters,scenes,props,dialogues},
       board:{id, n, brief, characters, sceneType, sceneAnchor:{layout,keyProps,
              lightSource,colorKey,styleLock}, durationSeconds, timelineShots:[],
              directing:{cameraMotion,emotionArc,montage,rhythm,hook},
              dialogues:[], videoPrompt, videoPromptStatus, contentStatus}}
      飞彩原文（模块 88350）：`board:{id:i,n:1,brief:"",characters:[],
      sceneType:"narrative",sceneAnchor:{layout:"",keyProps:"",lightSource:"",
      colorKey:"",styleLock:""},durationSeconds:r.creativeSettings?.durationSeconds??15,
      timelineShots:[],directing:{cameraMotion:"",emotionArc:"",montage:"",rhythm:"",
      hook:""},dialogues:[],videoPrompt:a.videoPrompt??"",videoPromptStatus:"draft",
      contentStatus:"draft"}`
· 产出文件名 —— 飞彩 outputs 页模块 17843 的 `B()`/`C()`：
      tuiwen/script.json         "推文分镜"
      tuiwen/script-edited.json  "推文分镜-用户编辑版"
      tuiwen/structure.json      "推文结构化剧本"
      references/*.manifest.json "参考图提取"
      beat-breakdown="节拍拆解" beat-board-prompt="九宫格提示词"
      beat-board="九宫格图集" sequence-board-prompt="四宫格提示词"
      motion-prompt="动态提示词" ai-generation-log="生成日志"
· 分镜条数 —— 飞彩同一模块："10/15 秒档为 XY(10) 条，30 秒档为 XY(30) 条"，
  即 10/15 秒档 10 个时间线镜头、30 秒档 30 个。分镜数另按 `--条数` 给。
· 三档时长 —— 飞彩创意设置里的 durationSeconds ∈ {10, 15, 30}。
· 视频模式 —— 飞彩分镜坞按钮 `E("multiref"|"firstlast"|"single")`：
      文生视频=单图模式、首尾帧=firstlast、全能参考=multiref。
      飞彩原文提示：
      "全能参考：分镜图为主体图，融合本格参考图与支持的角色音频"
      "全能参考：第一张参考图为主体图，按顺序提交全部参考图与支持的角色音频"
· 一键 @ —— 飞彩按钮文案："一键 @参考图+音频" / "一键修复并 @参考图+音频"，
  副文案"补入 N 个引用：已生成分镜图、参考图和音频；不包含参考视频"。
· 批量下载 —— 飞彩 TuiwenTable 的原文案（模块 88350）：
      "请先勾选要下载的分镜" / "已有批量下载正在进行，请等它结束"
      "已有批量任务在进行，请等它结束后再下载"
      "批量下载中断，请查看浏览器下载记录确认已落盘的文件"
      "[TuiwenTable] 批量下载素材异常:" / "一键复制文案"
· 一键复制文案 —— 飞彩原文案："点击「一键复制文案」→ 粘贴到 Flow 输入框 → 生成图片"。
· 导出时间戳 —— 飞彩模块 70308 的导出 md：`i.push(`> 导出时间：${r}`)`。

依赖：引擎.py（文生图/图生视频）、风格库.py（编译风格）、拼图.py（拼九宫格）、
      配音.py（可选，给分镜配音）。全部只读调用，不改它们。
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime

# 中文模块名在部分环境直接 import 会失败，先补 path，再 import，再退按路径载入。
_根 = os.path.dirname(os.path.abspath(__file__))
if _根 not in sys.path:
    sys.path.insert(0, _根)


def _装模块(文件名, 别名):
    """载入影匠既有模块（只读，绝不改它们）。写法照抄 一致性.py:53-77。"""
    e1 = None
    try:
        return __import__(别名), ""
    except Exception as e:
        e1 = e
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
    except Exception as e2:
        return None, f"import 失败({e1!r})；按路径载入失败({e2!r})"


_引擎, _引擎错 = _装模块("引擎.py", "引擎")
_风格库, _风格库错 = _装模块("风格库.py", "风格库")
_拼图, _拼图错 = _装模块("拼图.py", "拼图")
_配音, _配音错 = _装模块("配音.py", "配音")


# ============================================================
# 一、常量
# ============================================================

本文件 = os.path.abspath(__file__)
影匠根 = _根
作品根 = os.path.join(影匠根, "作品")

# 飞彩三档叙事时长。飞彩原话：「最终提示词必须同时兼容飞彩 10 秒、15 秒和 30 秒三档」。
三档 = (10, 15, 30)

# 模式 → 飞彩的 sourceType。飞彩分镜坞按钮：E("single"|"firstlast"|"multiref")。
模式表 = {
    "文生视频": "single",
    "首尾帧": "firstlast",
    "全能参考": "multiref",
}
模式别名 = {
    "single": "文生视频",
    "firstlast": "首尾帧",
    "multiref": "全能参考",
    "文生": "文生视频",
    "首尾": "首尾帧",
}

# 飞彩 outputs 页的产物种类表（模块 17843 的 B()），逐条抄下来当导出清单的说明。
产物说明 = {
    "script.json": "推文分镜（每一行/每一板 = 一个 10/15/30 秒叙事合集 + 一条完整九宫格描述 + 一张完整合图）",
    "script-edited.json": "推文分镜（用户编辑版 · 每一行/每一板各是一套完整九宫格）",
    "structure.json": "推文 10/15/30 秒叙事合集编排（中间产物）",
    "beat-breakdown.md": "节拍拆解",
    "beat-board-prompt.md": "九宫格提示词",
    "motion-prompt.md": "动态提示词",
    "ai-generation-log.json": "生成日志",
}

# 飞彩 timelineShots 条数：10/15 秒档 10 条、30 秒档 30 条。
def 时间线镜头数(时长: int) -> int:
    """飞彩原文：10/15 秒档为 XY(10) 条，30 秒档为 XY(30) 条。"""
    return 10 if int(时长) in (10, 15) else 30


# 飞彩 studio 模块里出现的实体类别（settings_entity_patch_invalid 的 kind 白名单）
实体类别 = ("characters", "scenes", "props")


# ============================================================
# 二、终端输出（照 剧组.py 的风格：头/报/警/错 + 中文标点）
# ============================================================

def 宽(s):
    """中文按 2 格算宽度，用来对齐表头。"""
    n = 0
    for c in str(s):
        n += 2 if ord(c) > 0x2E80 else 1
    return n


def 排(s, n):
    s = str(s)
    return s + " " * max(0, n - 宽(s))


def 头(标题):
    print()
    print("=" * 66)
    print(f"  {标题}")
    print("=" * 66)


def 报(s):
    print(f"  {s}", flush=True)


def 警(s):
    print(f"  ⚠ {s}", flush=True)


def 错(s):
    print(f"  ✗ {s}", file=sys.stderr, flush=True)


def 大小(字节):
    for 单位 in ("B", "KB", "MB", "GB"):
        if 字节 < 1024 or 单位 == "GB":
            return f"{字节:.0f}{单位}" if 单位 == "B" else f"{字节:.1f}{单位}"
        字节 /= 1024.0
    return f"{字节:.1f}GB"


# ============================================================
# 三、工程目录与落盘
# ============================================================

def 安全名(s):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(s)).strip(" .")
    return s[:60] or "推文"


def 项目目录(推文名):
    return os.path.join(作品根, 安全名(推文名))


def 分镜目录(推文名):
    return os.path.join(项目目录(推文名), "tuiwen")


def 图目录(推文名):
    return os.path.join(分镜目录(推文名), "beat-board")


def 片目录(推文名):
    return os.path.join(分镜目录(推文名), "motion")


def 导出目录(推文名):
    return os.path.join(项目目录(推文名), "导出")


def 分镜文件(推文名):
    return os.path.join(分镜目录(推文名), "script.json")


def 正文文件(推文名):
    return os.path.join(分镜目录(推文名), "推文正文.md")


def 项目文件(推文名):
    return os.path.join(项目目录(推文名), "tuiwen.json")


def _确保目录(推文名):
    for d in (项目目录(推文名), 分镜目录(推文名), 图目录(推文名), 片目录(推文名), 导出目录(推文名)):
        os.makedirs(d, exist_ok=True)


def _写json(路径, 数据):
    os.makedirs(os.path.dirname(路径), exist_ok=True)
    with open(路径, "w", encoding="utf-8") as f:
        json.dump(数据, f, ensure_ascii=False, indent=1)
    return 路径


def _读json(路径, 兜底=None):
    if not os.path.isfile(路径):
        return 兜底
    try:
        with open(路径, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return 兜底


def _写文(路径, 文字):
    os.makedirs(os.path.dirname(路径), exist_ok=True)
    with open(路径, "w", encoding="utf-8") as f:
        f.write(文字)
    return 路径


def _现在():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# 四、分镜数据契约（逐字对齐飞彩模块 88350 的 ih() 构造器）
# ============================================================

def 空场景锚点():
    """飞彩原文 sceneAnchor:{layout:"",keyProps:"",lightSource:"",colorKey:"",styleLock:""}"""
    return {"layout": "", "keyProps": "", "lightSource": "", "colorKey": "", "styleLock": ""}


def 空导演设计():
    """飞彩原文 directing:{cameraMotion:"",emotionArc:"",montage:"",rhythm:"",hook:""}

    飞彩对每个字段的说明（模块 88350 原文）：
      镜头运动 —— 镜头运动正文，不含标题。
      情绪曲线 —— 情绪曲线正文，不含标题。
      蒙太奇   —— 蒙太奇正文，不含标题。
      节奏     —— 节奏正文，不含标题。
      钩子     —— 钩子正文，不含标题。
    """
    return {"cameraMotion": "", "emotionArc": "", "montage": "", "rhythm": "", "hook": ""}


def 造分镜(编号: str, 画面: str, 时长: int, 视频提示词: str = ""):
    """造一条 storyboard。

    飞彩 `ih()` 的两个分支：authoringMode==="manual" 走手写（无 board），
    否则走 board 结构。影匠一律走 board 结构（这是飞彩自动化的主路径）。
    飞彩原文：`board:{id:i,n:1,brief:"",characters:[],sceneType:"narrative",...}`
    """
    时长 = int(时长)
    if 时长 not in 三档:
        时长 = 15
    条数 = 时间线镜头数(时长)
    return {
        "id": 编号,
        "shot": 画面,
        "videoShot": 视频提示词,
        "meta": {"characters": [], "scenes": [], "props": [], "dialogues": []},
        "board": {
            "id": 编号,
            "n": 1,                       # 飞彩 n:1 —— 一板一图，不拆九条
            "brief": 画面[:60],
            "characters": [],
            "sceneType": "narrative",
            "sceneAnchor": 空场景锚点(),
            "durationSeconds": 时长,
            "timelineShots": [],          # 由 造时间线镜头() 填，条数受时长约束
            "directing": 空导演设计(),
            "dialogues": [],
            "videoPrompt": 视频提示词,
            "videoPromptStatus": "draft",  # 飞彩原文 videoPromptStatus:"draft"
            "contentStatus": "draft",      # 飞彩原文 contentStatus:"draft"
        },
    }


def 造时间线镜头(画面: str, 时长: int):
    """按飞彩合同把一条画面拆成 timelineShots。

    飞彩合同原文：「每个 storyboard 的 timelineShots 条数必须服从运行时的分镜叙事目标时长：
    10/15 秒档为 XY(10) 条，30 秒档为 XY(30) 条」。
    影匠没有 LLM 时的本地拆法：把画面按标点切成小句，数量不够就整段轮着补，
    绝不空着 —— 因为飞彩的下游（九宫格提示词）是按条数取料的。
    """
    时长 = int(时长) if int(时长) in 三档 else 15
    条数 = 时间线镜头数(时长)
    片段 = [x.strip() for x in re.split(r"[，。；！？、,.;!?\n]+", str(画面)) if x.strip()]
    if not 片段:
        片段 = [str(画面).strip() or "（待补画面描述）"]
    出 = []
    for i in range(条数):
        s = 片段[i % len(片段)]
        if i >= len(片段):
            s = f"{s}（延续）"
        出.append({"n": i + 1, "shot": s, "seconds": round(时长 / 条数, 2)})
    return 出


def 造推文结构(名称: str, 时长: int, 时代: str = "", 条数: int = 3, 正文: str = ""):
    """造一个空的推文工程骨架。"""
    时长 = int(时长) if int(时长) in 三档 else 15
    return {
        "schemaVersion": 1,
        "kind": "tuiwen",
        # 飞彩合同字段：timeSetting / episodes / storyboards / sceneAnchor /
        # timelineShots / directing / dialogues / dialogueSourceIds / entities / durationSeconds
        "name": 名称,
        "timeSetting": 时代 or "",
        "durationSeconds": 时长,
        "episodeCount": 1,
        "storyboardCount": max(1, int(条数)),
        "scriptTitle": 名称,
        "pipeline": {
            "action": "run-full-flow",           # 飞彩消息契约里的 action
            "schemaVersion": 1,
            "confirmNewRun": True,
            "messageKeys": {
                "readyRequest": "feicai-tuiwen-pipeline-ui:v1:ready-request",
                "command": "feicai-tuiwen-pipeline-ui:v1:command",
                "result": "feicai-tuiwen-pipeline-ui:v1:result",
                "cancel": "feicai-tuiwen-pipeline-ui:v1:cancel",
                "runFullFlow": "run-full-flow",
            },
        },
        "createdAt": _现在(),
        "updatedAt": _现在(),
        "episodes": [{"id": "ep1", "n": 1, "title": 名称, "storyboards": []}],
        "storyboards": [],
        "entities": {"characters": [], "scenes": [], "props": []},
        "tuiwenVoiceSlots": [],
        "publish": {"platform": "", "topic": "", "copy": "", "scheduleAt": ""},
        "gallery": [],       # 生成出来的图/片登记（对齐飞彩的 cards 归档）
        "log": [],
    }


# ============================================================
# 五、风格编译（接 风格库.py）
# ============================================================

普通风格 = "cinematic-real"


def 编译风格(风格键="", 额外="", 镜头=None):
    """把风格键编译成 {正向,负向,cfg,风格}。

    风格库.py 的 `编译(键, 额外="", 角色="", 镜头=None, 去掉负向=False)`
    返回的正是这个字典（风格库.py: 编译() 的 return）。风格库没装好就退化成空壳，
    不让它挡住主流程。
    """
    空 = {"正向": 额外 or "", "负向": "", "cfg": None, "风格": ""}
    if _风格库 is None:
        警(f"风格库.py 没载入（{_风格库错}），这一批不带风格前缀")
        return 空
    try:
        键 = 风格键
        if not 键:
            ks = _风格库.全部() or []
            键 = ks[0] if ks else ""
        if not 键:
            return 空
        d = _风格库.编译(键, 额外=额外, 镜头=镜头) or {}
        if d.get("错"):
            警(f"风格库说：{d['错']}（按不带风格前缀继续）")
        return {"正向": d.get("正向") or "", "负向": d.get("负向") or "",
                "cfg": d.get("cfg"), "风格": d.get("风格") or 键}
    except Exception as e:
        警(f"风格库编译失败（{type(e).__name__}: {e}），这一批不带风格前缀")
        return 空


# ============================================================
# 六、命令 · 先建
# ============================================================

def 命令_先建(推文名, 时长=15, 时代="", 条数=3, 空跑=False, json出=False, 重做=False):
    头(f"先建《{推文名}》　时长 {时长} 秒　分镜 {条数} 条" + ("　[空跑]" if 空跑 else ""))
    if 时长 not in 三档:
        警(f"时长 {时长} 不在飞彩三档 {三档} 里，按 15 秒来")
        时长 = 15

    老 = _读json(项目文件(推文名))
    if 老 and not 重做:
        报(f"已经有一部了（建于 {老.get('createdAt','?')}）：{项目文件(推文名)}")
        报("要重来加 --重做（会清掉分镜和产物）")
        return _交(json出, {"ok": True, "已存在": True, "目录": 项目目录(推文名)}, 0)

    if 空跑:
        报(f"[空跑] 会建目录：{项目目录(推文名)}")
        报(f"[空跑] 会写：{项目文件(推文名)}　{分镜文件(推文名)}")
        报(f"[空跑] 时间线镜头数：{时间线镜头数(时长)} 条/分镜（飞彩：10/15 秒档 10 条，30 秒档 30 条）")
        return _交(json出, {"ok": True, "空跑": True, "时长": 时长, "分镜数": 条数,
                            "时间线镜头数": 时间线镜头数(时长)}, 0)

    if 老 and 重做:
        import shutil
        报("--重做：清掉旧工程")
        for d in (分镜目录(推文名),):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)

    工程 = 造推文结构(推文名, 时长, 时代=时代, 条数=条数)
    # 先把骨架按条数铺好，正文/分镜命令再往里填
    工程["episodes"][0]["storyboards"] = [造分镜(f"ep1-s{i+1}", "", 时长) for i in range(int(条数))]
    工程["storyboards"] = 工程["episodes"][0]["storyboards"]
    _确保目录(推文名)
    _写json(项目文件(推文名), 工程)
    _写json(分镜文件(推文名), 工程)   # 飞彩 tuiwen/script.json
    报(f"目录：{项目目录(推文名)}")
    报(f"工程：{项目文件(推文名)}")
    报(f"分镜：{分镜文件(推文名)}（飞彩叫「推文分镜」，路径 tuiwen/script.json）")
    报(f"铺了 {条数} 条 storyboard，每条 timelineShots {时间线镜头数(时长)} 条")
    报("下一步：正文 给推文写发布文案；分镜 把文案拆成叙事合集")
    return _交(json出, {"ok": True, "目录": 项目目录(推文名),
                        "分镜数": 条数, "时长": 时长}, 0)


# ============================================================
# 七、命令 · 正文（推文发布文案）
# ============================================================

# 飞彩的正文落点是 tuiwen/script.json + 一键复制文案。
# 飞彩原文案：「点击「一键复制文案」→ 粘贴到 Flow 输入框 → 生成图片」。
正文模板 = "{标题}\n\n{正文}\n\n{话题}"

# 给外部 LLM 的任务书（飞彩的 LLM 走 /api/llm，影匠不自带 Key，所以把任务书写出来让人/别的工具填）
正文任务书 = """# 推文正文生成任务（影匠 · 推文工作台）

请为下面这条推文写一段可直接发布的中文正文。

## 要求
- 全文简体中文，短句为主，口语化，不要「首先/其次/总之」这类公文腔。
- 开头一句话就要抓人（飞彩叫「钩子」），正文分 2–4 个自然段。
- 结尾带上引导互动的一句（提问 / 邀请），然后另起一行给话题标签。
- 话题标签格式 `#话题1 #话题2`，3–5 个，与内容强相关。
- 不复述提示词，不写「以下是」「好的」这类应答语。
- 总长 80–220 字。

## 输入
标题：{标题}
素材/要点：{要点}
时代/背景：{时代}
时长档：{时长} 秒

## 输出格式（严格）
第一行：标题
空行
正文（2–4 段）
空行
话题标签行
"""


def 命令_正文(推文名, 标题="", 文="", 要点="", 话题="", 空跑=False, json出=False):
    头(f"正文《{推文名}》" + ("　[空跑]" if 空跑 else ""))
    工 = _读json(项目文件(推文名))
    if not 工:
        return _没这部(推文名, json出)

    标题 = 标题 or 工.get("name", 推文名)
    要点 = 要点 or 文
    任务 = 正文任务书.format(标题=标题, 要点=要点 or "（未给，围绕标题发挥）",
                             时代=工.get("timeSetting", "") or "不限",
                             时长=工.get("durationSeconds", 15))
    任务路径 = os.path.join(分镜目录(推文名), "正文提示词.md")

    if 空跑:
        报(f"[空跑] 会写任务书：{任务路径}")
        报(f"[空跑] 会写正文：{正文文件(推文名)}")
        return _交(json出, {"ok": True, "空跑": True, "任务书": 任务路径}, 0)

    _确保目录(推文名)
    _写文(任务路径, 任务)
    报(f"任务书已写：{任务路径}")

    话题行 = " ".join("#" + t.strip().lstrip("#") for t in re.split(r"[,，\s]+", 话题) if t.strip())
    正文段 = 文 or 要点 or "（正文待写：把上面任务书喂给任意 LLM，再把结果贴回来）"
    全文 = 正文模板.format(标题=标题, 正文=正文段, 话题=话题行).strip() + "\n"
    _写文(正文文件(推文名), f"# {推文名} · 推文正文\n\n> 生成时间：{_现在()}\n\n---\n\n{全文}")

    工.setdefault("publish", {})
    工["publish"].update({"copy": 全文, "topic": 话题行, "title": 标题})
    工["updatedAt"] = _现在()
    _写json(项目文件(推文名), 工)
    _写json(分镜文件(推文名), 工)

    报(f"正文（{len(全文)} 字）已写：{正文文件(推文名)}")
    if not (文 or 要点):
        警("正文是占位符 —— 影匠不自带 LLM Key，飞彩走 /api/llm，影匠把任务书写出来了，请填内容")
    报("下一步：分镜 把正文拆成 10/15/30 秒叙事合集")
    return _交(json出, {"ok": True, "正文": 全文, "文件": 正文文件(推文名)}, 0)


# ============================================================
# 八、命令 · 分镜（叙事合集拆解）
# ============================================================

# 飞彩的 Stage 1 提示词键名（from 模块 87793）：
#   tuiwenStoryBreakdownV3 = "★ 10/15/30 秒叙事合集编排师(Stage 1)"
#   tuiwenVisualDirectorV4 = "★ 九宫格画面师(Stage 2)"
# 描述原文：「推文模式 · EP 仅作容器；每个 storyboard 是独立 10/15/30 秒叙事合集，
#            并对应一条连续画面描述、聚合元数据和视频提示词」
分镜任务书 = """# 推文分镜拆解任务（影匠 · 推文工作台 · Stage 1）

[FEICAI_CONTRACT:tuiwen-storyboards-stage1-v5-markdown-row-aligned]

## 铁律（抄自飞彩模块 88350 的固定合同）
1. 两级关系：EP 只作章节/段落容器，episodes[].storyboards[] 才是合集分镜单元；
   每个 storyboard 只对应**一行**标准化数据，**不能把九宫格拆成九条 storyboard**。
2. 固定 Markdown 标题层级，必须按层级出现：
       # 时代背景
       ## EP 1
       ### Storyboard 1
       #### 场景锚点
       #### 时间线镜头 1
       #### 导演设计
       #### 对白 1
   可确定性归一为：timeSetting / episodes / storyboards / sceneAnchor /
   timelineShots / directing / dialogues / dialogueSourceIds / entities / durationSeconds。
   **不得另建第二套 JSON 或 Markdown 架构、改标题名或改变列表/字段关系。**
3. 每个 storyboard 的 timelineShots 条数必须服从叙事目标时长：
   10/15 秒档 = {条数1015} 条，30 秒档 = {条数30} 条。
4. 本任务只负责第一层「合集拆解与标准化数据」，
   **不越权规定第二层「成品视频提示词框架」，不输出最终成品排版**。
5. 不得写死「10 秒」「15 秒」「30 秒」三档字样（飞彩要求同时兼容三档），
   统一表述为「系统固定合同指定的分镜叙事目标时长」。
6. 角色与实体使用**纯名称列表**；输入里的「名称(#内部id)」只输出「名称」。

## 字段（每个 storyboard 一行，顺序固定）
id | shot（一条连续画面描述） | durationSeconds | sceneAnchor.layout | sceneAnchor.keyProps |
sceneAnchor.lightSource | sceneAnchor.colorKey | sceneAnchor.styleLock |
directing.cameraMotion | directing.emotionArc | directing.montage | directing.rhythm |
directing.hook | videoPrompt

## 输入
推文名：{名称}
本文案：{正文}
时代背景：{时代}
目标时长：系统固定合同指定的分镜叙事目标时长（档位 {时长} 秒）
要几条 storyboard：{条数}
"""


def 命令_分镜(推文名, 条数=0, 文="", 空跑=False, json出=False, 重做=False):
    头(f"分镜《{推文名}》" + ("　[空跑]" if 空跑 else ""))
    工 = _读json(项目文件(推文名))
    if not 工:
        return _没这部(推文名, json出)

    时长 = int(工.get("durationSeconds", 15))
    if 时长 not in 三档:
        时长 = 15
    条数 = int(条数) if 条数 else int(工.get("storyboardCount", 3) or 3)
    条数 = max(1, min(24, 条数))

    素材 = (文 or (工.get("publish") or {}).get("copy") or "").strip()
    素材 = re.sub(r"^#.*$", "", 素材, flags=re.M).strip()   # 去掉标题行和话题行
    if not 素材:
        素材 = f"{推文名}。{工.get('timeSetting','')}".strip("。")

    任务 = 分镜任务书.format(名称=推文名, 正文=素材[:1200], 时代=工.get("timeSetting", "") or "不限",
                             时长=时长, 条数=条数, 条数1015=时间线镜头数(10), 条数30=时间线镜头数(30))
    任务路径 = os.path.join(分镜目录(推文名), "beat-breakdown-prompt.md")

    if 空跑:
        报(f"[空跑] 会写 Stage1 任务书：{任务路径}")
        报(f"[空跑] 会拆 {条数} 条 storyboard，每条 timelineShots {时间线镜头数(时长)} 条")
        报("[空跑] 已有分镜不会被覆盖" if not 重做 else "[空跑] --重做：会覆盖已有分镜")
        return _交(json出, {"ok": True, "空跑": True, "任务书": 任务路径,
                            "条数": 条数, "时间线镜头数": 时间线镜头数(时长)}, 0)

    _确保目录(推文名)
    _写文(任务路径, 任务)
    报(f"Stage1 任务书已写：{任务路径}")

    旧 = 工.get("storyboards") or []
    if 旧 and not 重做 and any(x.get("shot") for x in 旧):
        报(f"已有 {len([x for x in 旧 if x.get('shot')])} 条填好的分镜，不覆盖（要重来加 --重做）")

    板们 = []
    句 = [x.strip() for x in re.split(r"[。！？\n]+", 素材) if x.strip()] or [素材]
    for i in range(条数):
        画面 = 句[i % len(句)]
        if i >= len(句):
            画面 = f"{画面}（第 {i+1} 段落延伸）"
        b = 造分镜(f"ep1-s{i+1}", 画面, 时长)
        b["board"]["timelineShots"] = 造时间线镜头(画面, 时长)
        b["board"]["sceneAnchor"] = {
            "layout": "主体居中，三分法构图",
            "keyProps": "",
            "lightSource": "自然侧光",
            "colorKey": "",
            "styleLock": "",
        }
        b["board"]["directing"] = {
            "cameraMotion": "缓推，落幅稳",
            "emotionArc": "由静到动，收在留白",
            "montage": "顺叙，不跳切",
            "rhythm": f"{时长} 秒内 {时间线镜头数(时长)} 个时间线镜头，前 3 秒立钩子",
            "hook": (画面[:24] + "…") if len(画面) > 24 else 画面,
        }
        b["board"]["videoPrompt"] = f"{画面}｜{时长} 秒｜慢慢推进，光影自然流动"
        b["board"]["videoPromptStatus"] = "ready"
        b["board"]["contentStatus"] = "ready"
        b["videoShot"] = b["board"]["videoPrompt"]
        板们.append(b)

    工["episodes"] = [{"id": "ep1", "n": 1, "title": 工.get("scriptTitle", 推文名), "storyboards": 板们}]
    工["storyboards"] = 板们
    工["storyboardCount"] = len(板们)
    工["updatedAt"] = _现在()
    工.setdefault("log", []).append({"at": _现在(), "cmd": "分镜", "条数": len(板们), "时长": 时长})
    _写json(项目文件(推文名), 工)
    _写json(分镜文件(推文名), 工)              # 飞彩 tuiwen/script.json
    _写json(os.path.join(分镜目录(推文名), "structure.json"), {   # 飞彩 tuiwen/structure.json
        "kind": "tuiwen-structure", "durationSeconds": 时长,
        "episodes": [{"id": "ep1", "storyboardIds": [b["id"] for b in 板们]}],
    })
    _写文(os.path.join(分镜目录(推文名), "beat-breakdown.md"), _分镜markdown(工))
    报(f"拆出 {len(板们)} 条 storyboard（每条 {时间线镜头数(时长)} 个时间线镜头）")
    报(f"分镜：{分镜文件(推文名)}")
    报(f"结构化：{os.path.join(分镜目录(推文名), 'structure.json')}")
    报("下一步：配图 --九宫格 出 3×3 分镜图；配视频 出片")
    return _交(json出, {"ok": True, "条数": len(板们), "时长": 时长,
                        "分镜": 分镜文件(推文名)}, 0)


def _分镜markdown(工):
    """写飞彩那套「固定 Markdown 标题层级」。

    飞彩合同原文：
      「时代背景 / EP N / Storyboard N / 场景锚点 / 时间线镜头 N / 导演设计 / 对白 N」
    """
    L = [f"# 时代背景", "", 工.get("timeSetting") or "不限", ""]
    for ep in 工.get("episodes", []):
        L += [f"## EP {ep.get('n', 1)}", "", f"标题：{ep.get('title','')}", ""]
        for j, b in enumerate(ep.get("storyboards", []) or []):
            bd = b.get("board") or {}
            L += [f"### Storyboard {j+1}", "", f"id：{b.get('id','')}", "",
                  f"时长：系统固定合同指定的分镜叙事目标时长（档位 {bd.get('durationSeconds',15)} 秒）", "",
                  f"连续画面描述：{b.get('shot','')}", "",
                  "#### 场景锚点", ""]
            L += [f"- {k}：{v}" for k, v in (bd.get("sceneAnchor") or {}).items()]
            L += ["", "#### 时间线镜头", ""]
            for t in bd.get("timelineShots", []) or []:
                L.append(f"{t.get('n')}. {t.get('shot','')}")
            L += ["", "#### 导演设计", ""]
            L += [f"- {k}：{v}" for k, v in (bd.get("directing") or {}).items()]
            L += ["", "#### 对白 1", "", "（无）", "",
                  f"视频提示词：{bd.get('videoPrompt','')}", "", "---", ""]
    return "\n".join(L)


# ============================================================
# 九、命令 · 配图（九宫格）
# ============================================================

# 9 格的构图槽位。飞彩的 Stage 2 是「九宫格画面师」，默认 3×3 模板：
#   原文："推文模式 · 每个 10/15/30 秒叙事 storyboard 先生成连续中文画面描述和聚合实体元数据；
#          默认 3×3 模板随后写入创作工作台的可编辑生图提示词，不拆九条数据"
九格角度 = [
    "远景定场", "全景交代环境", "中景主体入画",
    "中近景表情", "近景细节", "特写关键物",
    "肩上视角", "俯视构图", "仰视收束",
]


def _格提示词(分镜, 格号, 风格前缀=""):
    一 = 分镜.get("board") or {}
    画面 = 分镜.get("shot") or ""
    角度 = 九格角度[(格号 - 1) % 9]
    锚 = 一.get("sceneAnchor") or {}
    导 = 一.get("directing") or {}
    段 = [
        f"九宫格第 {格号} 格（{角度}）",
        画面,
        f"场景锚点：{锚.get('layout','')} {锚.get('keyProps','')} {锚.get('lightSource','')}".strip(),
        f"镜头：{导.get('cameraMotion','')}　氛围：{导.get('emotionArc','')}".strip(),
    ]
    if 风格前缀:
        段.insert(0, 风格前缀)
    段.append("无任何文字、水印或字幕")
    return "，".join(x for x in 段 if x and x.strip("，"))


def 命令_配图(推文名, 九宫格=False, 单格=None, 序号=None, 风格键=普通风格,
              空跑=False, json出=False, 重做=False):
    头(f"配图《{推文名}》" + ("　[九宫格]" if 九宫格 else "") + ("　[空跑]" if 空跑 else ""))
    工 = _读json(项目文件(推文名))
    if not 工:
        return _没这部(推文名, json出)
    板们 = 工.get("storyboards") or []
    if not 板们:
        return _没分镜(推文名, json出)

    板们 = _挑板(板们, 序号)
    风 = 编译风格(风格键)
    if 风["正向"]:
        报(f"风格：{风['风格']}　前缀 {风['正向'][:56]}…")
    风格前 = 风["正向"]

    要出的 = []   # [(分镜, 格号)]
    if 九宫格:
        for b in 板们:
            for k in range(1, 10):
                要出的.append((b, k))
    else:
        kk = int(单格) if 单格 else 1
        for b in 板们:
            要出的.append((b, kk))

    if 空跑:
        报(f"[空跑] 要出 {len(要出的)} 张图（{len(板们)} 条分镜 × {9 if 九宫格 else 1} 格）")
        for b, k in 要出的[:6]:
            报(f"   {b['id']} 格{k}：{_格提示词(b, k, 风格前)[:70]}…")
        if len(要出的) > 6:
            报(f"   …还有 {len(要出的)-6} 张")
        报(f"[空跑] 会落到：{图目录(推文名)}")
        报(f"[空跑] 会拼合图：{os.path.join(项目目录(推文名), '_看片表.png')}")
        return _交(json出, {"ok": True, "空跑": True, "要出": len(要出的)}, 0)

    if _引擎 is None:
        错(f"引擎.py 载入失败：{_引擎错}")
        return _交(json出, {"ok": False, "错误": "引擎载入失败", "说明": _引擎错}, 4)

    _确保目录(推文名)
    出图 = _目录里的图(图目录(推文名))
    做 = 出图数 = 败 = 0
    for b, k in 要出的:
        目标 = os.path.join(图目录(推文名), f"{b['id']}_格{k}.png")
        if os.path.isfile(目标) and not 重做:
            报(f"跳过（已有）：{os.path.basename(目标)}")
            continue
        提示词 = _格提示词(b, k, 风格前)
        try:
            果 = _引擎.文生图(提示词, 负面=风["负向"], 报=lambda s: None, 存到=目标)
            路 = 果.get("路") if isinstance(果, dict) else None
            if 路 and os.path.isfile(路):
                做 += 1
                _登记(工, 路, "image", 提示词, f"{b['id']} 格{k}")
            else:
                败 += 1
                警(f"{b['id']} 格{k} 没拿到图：{果 if not isinstance(果,dict) else 果.get('错','')}")
        except Exception as e:
            败 += 1
            警(f"{b['id']} 格{k} 出图异常：{type(e).__name__}: {e}")
        出图数 += 1

    if 做 == 0 and 出图数 > 0:
        错("一张图都没出来 —— 检查 ComfyUI 是否在跑（引擎.py 在线）")
        工["updatedAt"] = _现在()
        _写json(项目文件(推文名), 工)
        return _交(json出, {"ok": False, "做成": 0, "失败": 败}, 4)

    合图 = None
    if 九宫格 and _拼图 is not None:
        try:
            合图 = _拼图.拼(图目录(推文名), 每行=3,
                            出=os.path.join(项目目录(推文名), "_看片表.png"))
            报(f"九宫格合图：{合图}")
        except Exception as e:
            警(f"拼图失败（{e}）—— 单格图仍在 {图目录(推文名)}")

    工["updatedAt"] = _现在()
    工.setdefault("log", []).append({"at": _现在(), "cmd": "配图", "成": 做, "败": 败})
    _写json(项目文件(推文名), 工)
    报(f"出图 {做} 张，失败 {败} 张 → {图目录(推文名)}")
    报("下一步：配视频 出片；排期 看表")
    return _交(json出, {"ok": True, "做成": 做, "失败": 败, "合图": 合图,
                        "目录": 图目录(推文名)}, 0 if 败 == 0 else 4)


# ============================================================
# 十、命令 · 配视频
# ============================================================

def 命令_配视频(推文名, 模式="全能参考", 序号=None, 风格键=普通风格,
                空跑=False, json出=False, 重做=False):
    模式中文 = 模式别名.get(模式, 模式)
    if 模式中文 not in 模式表:
        return _交(json出, {"ok": False, "错误": "模式不对",
                            "说明": f"模式只能是 {list(模式表)} 之一，收到 {模式!r}"}, 2)
    源型 = 模式表[模式中文]
    头(f"配视频《{推文名}》　模式 {模式中文}（{源型}）" + ("　[空跑]" if 空跑 else ""))
    报(f"飞彩原文：{_模式说明(模式中文)}")

    工 = _读json(项目文件(推文名))
    if not 工:
        return _没这部(推文名, json出)
    板们 = _挑板(工.get("storyboards") or [], 序号)
    if not 板们:
        return _没分镜(推文名, json出)

    风 = 编译风格(风格键)
    if 风["正向"]:
        报(f"风格：{风['风格']}")
    计划 = []
    for b in 板们:
        图 = _找合图(推文名, b)
        参考 = _找参考图(推文名, b)
        提示词 = (b.get("board") or {}).get("videoPrompt") or b.get("videoPrompt") or ""
        if 源型 == "multiref":
            if 图:
                提示词 = f"全能参考：分镜图为主体图，融合本格参考图与支持的角色音频。{提示词}"
            else:
                提示词 = f"全能参考：第一张参考图为主体图，按顺序提交全部参考图与支持的角色音频。{提示词}"
        elif 源型 == "firstlast":
            提示词 = f"首尾帧：第一张作首帧，第二张作尾帧。{提示词}"
        if 风["正向"]:
            提示词 = f"{风['正向']}，{提示词}"
        计划.append({"id": b["id"], "图": 图, "参考": 参考, "提示词": 提示词,
                     "源型": 源型, "秒": (b.get("board") or {}).get("durationSeconds", 15)})

    if 空跑:
        报(f"[空跑] 要出 {len(计划)} 段片")
        for p in 计划[:6]:
            报(f"   {p['id']}　{os.path.basename(p['图']) if p['图'] else '（没有分镜图，会让模型纯文生）'}"
               f"　参考 {len(p['参考'])} 张　{p['秒']} 秒")
            报(f"      {p['提示词'][:88]}…")
        if len(计划) > 6:
            报(f"   …还有 {len(计划)-6} 段")
        报(f"[空跑] 会落到：{片目录(推文名)}")
        提示 = "请 图 == 9 张再合成一段片" if 源型 == "multiref" else "单段出片"
        报(f"[空跑] {提示}")
        return _交(json出, {"ok": True, "空跑": True, "要出": len(计划)}, 0)

    if _引擎 is None:
        错(f"引擎.py 载入失败：{_引擎错}")
        return _交(json出, {"ok": False, "错误": "引擎载入失败", "说明": _引擎错}, 4)

    _确保目录(推文名)
    做 = 败 = 0
    for p in 计划:
        目标 = os.path.join(片目录(推文名), f"{p['id']}.mp4")
        if os.path.isfile(目标) and not 重做:
            报(f"跳过（已有）：{os.path.basename(目标)}")
            continue
        try:
            # 引擎.py 只有 图生视频(图路, 提示词, ...)，没有纯文生视频。
            # 文生视频档（single）没图时先出一张首帧，再喂给图生视频。
            图路 = p["图"]
            if not 图路:
                首 = os.path.join(图目录(推文名), f"{p['id']}_首帧.png")
                if not (os.path.isfile(首) and not 重做):
                    果0 = _引擎.文生图(p["提示词"], 负面=风["负向"], 报=lambda s: None, 存到=首)
                    首 = (果0 or {}).get("路") or 首
                图路 = 首
                if not os.path.isfile(图路):
                    raise RuntimeError(f"文生视频档要一张首帧，但首帧没出来：{图路}")
            果 = _引擎.图生视频(图路, p["提示词"], 负面=风["负向"],
                              报=lambda s: None, 存到=目标)
            路 = 果.get("路") if isinstance(果, dict) else None
            if 路 and os.path.isfile(路):
                做 += 1
                _登记(工, 路, "video", p["提示词"], p["id"])
            else:
                败 += 1
                警(f"{p['id']} 没拿到片：{果 if not isinstance(果,dict) else 果.get('错','')}")
        except Exception as e:
            败 += 1
            警(f"{p['id']} 出片异常：{type(e).__name__}: {e}")

    if 做 == 0 and 计划:
        错("一段片都没出来 —— 检查 ComfyUI 是否在跑（引擎.py 在线）")
        return _交(json出, {"ok": False, "做成": 0, "失败": 败}, 4)

    工["updatedAt"] = _现在()
    工.setdefault("log", []).append({"at": _现在(), "cmd": "配视频", "模式": 模式中文,
                                    "成": 做, "败": 败})
    _写json(项目文件(推文名), 工)
    报(f"出片 {做} 段，失败 {败} 段 → {片目录(推文名)}")
    报("下一步：排期 看表；导出 打包")
    return _交(json出, {"ok": True, "做成": 做, "失败": 败, "目录": 片目录(推文名)}, 0 if 败 == 0 else 4)


def _模式说明(模式中文):
    # 飞彩分镜坞按钮的 title 原文
    if 模式中文 == "全能参考":
        return "全能参考：分镜图为主体图，融合本格参考图与支持的角色音频"
    if 模式中文 == "首尾帧":
        return "首尾帧：第一张作首帧、第二张作尾帧"
    return "文生视频：提示词直接出片"


def _找合图(推文名, 板):
    p = os.path.join(项目目录(推文名), "_看片表.png")
    return p if os.path.isfile(p) else None


def _找参考图(推文名, 板):
    """按 id 前缀收图目录里的单格图，当参考图用。"""
    出 = []
    d = 图目录(推文名)
    if os.path.isdir(d):
        前缀 = str(板.get("id", "")) + "_"
        for f in sorted(os.listdir(d)):
            if f.startswith(前缀) and f.lower().endswith(".png"):
                出.append(os.path.join(d, f))
    return 出


def _目录里的图(d):
    if not os.path.isdir(d):
        return []
    return [f for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]


def _挑板(板们, 序号):
    if not 序号:
        return 板们
    if isinstance(序号, str):
        序号 = [x for x in re.split(r"[,，\s]+", 序号) if x.strip()]
    要 = set()
    for x in 序号:
        s = str(x).strip()
        if s.startswith("ep") or s.startswith("s"):
            要.add(s)
        elif s.isdigit():
            要.add(f"ep1-s{s}")
    if not 要:
        return 板们
    return [b for b in 板们 if str(b.get("id")) in 要]


def _登记(工, 路, 类型, 提示词, 标题):
    """把产物登进 gallery（对齐飞彩的 cards 归档）。"""
    工.setdefault("gallery", []).append({
        "url": os.path.abspath(路), "type": 类型, "prompt": 提示词[:400],
        "title": 标题, "createdAt": _现在(),
    })


# ============================================================
# 十一、命令 · 排期（TuiwenTable 那样的行表）
# ============================================================

# TuiwenTable 的列。飞彩那一行 = 一个 storyboard：
#   id / 连续画面描述 / 时长 / 时间线镜头数 / 导演设计 / 视频提示词 / 有图没 / 有片没 / 状态
排期列 = ["行", "分镜ID", "时长(秒)", "时间线镜头", "参考图", "连续画面描述",
          "导演·镜头运动", "导演·钩子", "视频提示词", "分镜图", "成片", "状态"]


def _排期行(推文名, 板们):
    出 = []
    for i, b in enumerate(板们, 1):
        bd = b.get("board") or {}
        图 = _找参考图(推文名, b)
        合图 = _找合图(推文名, b)
        片 = os.path.join(片目录(推文名), f"{b.get('id')}.mp4")
        有片 = os.path.isfile(片)
        有图 = bool(图) or bool(合图)
        状态 = "成片✓" if 有片 else ("有图" if 有图 else "待配图")
        if not (b.get("shot") or "").strip():
            状态 = "空行"
        d = bd.get("directing") or {}
        出.append({
            "行": i, "分镜ID": b.get("id", ""), "时长(秒)": bd.get("durationSeconds", 15),
            "时间线镜头": len(bd.get("timelineShots") or []),
            "参考图": len(图), "连续画面描述": b.get("shot", ""),
            "导演·镜头运动": d.get("cameraMotion", ""), "导演·钩子": d.get("hook", ""),
            "视频提示词": bd.get("videoPrompt", "") or b.get("videoShot", ""),
            "分镜图": "有" if 有图 else "无", "成片": "有" if 有片 else "无", "状态": 状态,
        })
    return 出


def 命令_排期(推文名, 空跑=False, json出=False, 写文件=True):
    头(f"排期《{推文名}》")
    工 = _读json(项目文件(推文名))
    if not 工:
        return _没这部(推文名, json出)
    板们 = 工.get("storyboards") or []
    if not 板们:
        return _没分镜(推文名, json出)

    行 = _排期行(推文名, 板们)
    报(f"{' '.join(排(x, 12) for x in ['行', '分镜ID', '时长', '镜头', '参考图', '图', '片', '状态'])}")
    for r in 行:
        print("   " + " ".join(排(r[x], 12) for x in
                              ["行", "分镜ID", "时长(秒)", "时间线镜头", "参考图", "分镜图", "成片", "状态"]))
    报("")
    报(f"共 {len(行)} 行；有图 {sum(1 for r in 行 if r['分镜图']=='有')}　"
       f"有片 {sum(1 for r in 行 if r['成片']=='有')}　待配图 {sum(1 for r in 行 if r['状态']=='待配图')}")

    if 空跑:
        报("[空跑] 不写文件")
        return _交(json出, {"ok": True, "空跑": True, "行数": len(行)}, 0)

    csv路 = os.path.join(导出目录(推文名), "排期表.csv")
    md路 = os.path.join(导出目录(推文名), "排期表.md")
    if 写文件:
        _确保目录(推文名)
        with open(csv路, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=排期列)
            w.writeheader()
            for r in 行:
                w.writerow({k: r.get(k, "") for k in 排期列})
        L = [f"# {推文名} · 推文排期表", "",
             f"> 导出时间：{_现在()}",           # 飞彩模块 70308 的原文格式
             f"> 时长档：{工.get('durationSeconds',15)} 秒　"
             f"分镜：{len(行)} 条　时代：{工.get('timeSetting','') or '不限'}", "",
             "| " + " | ".join(排期列) + " |",
             "|" + "---|" * len(排期列)]
        for r in 行:
            L.append("| " + " | ".join(str(r.get(k, "")).replace("|", "／") for k in 排期列) + " |")
        L += ["", "## 发布信息（一键复制文案）", "",
              f"- 平台：{(工.get('publish') or {}).get('platform','') or '（未填）'}",
              f"- 排期时间：{(工.get('publish') or {}).get('scheduleAt','') or '（未填）'}",
              f"- 话题：{(工.get('publish') or {}).get('topic','') or '（未填）'}",
              "", "```", (工.get("publish") or {}).get("copy", "") or "（未写正文）", "```"]
        _写文(md路, "\n".join(L))
        报(f"排期表：{csv路}")
        报(f"排期表：{md路}")

    报("下一步：导出 打包全部产物")
    return _交(json出, {"ok": True, "行数": len(行), "csv": csv路, "md": md路,
                        "行": 行}, 0)


# ============================================================
# 十二、命令 · 导出
# ============================================================

def 命令_导出(推文名, 空跑=False, json出=False):
    头(f"导出《{推文名}》" + ("　[空跑]" if 空跑 else ""))
    工 = _读json(项目文件(推文名))
    if not 工:
        return _没这部(推文名, json出)

    d = 分镜目录(推文名)
    图 = _目录里的图(图目录(推文名))
    片 = [f for f in os.listdir(片目录(推文名)) if f.lower().endswith(".mp4")] \
        if os.path.isdir(片目录(推文名)) else []

    清单 = [
        ("推文正文.md", 正文文件(推文名), "推文发布文案（一键复制文案）"),
        ("script.json", 分镜文件(推文名), 产物说明["script.json"]),
        ("structure.json", os.path.join(d, "structure.json"), 产物说明["structure.json"]),
        ("beat-breakdown.md", os.path.join(d, "beat-breakdown.md"), 产物说明["beat-breakdown.md"]),
        ("beat-breakdown-prompt.md", os.path.join(d, "beat-breakdown-prompt.md"), "节拍拆解任务书"),
        ("正文提示词.md", os.path.join(d, "正文提示词.md"), "正文生成任务书"),
        ("排期表.csv", os.path.join(导出目录(推文名), "排期表.csv"), "排期表（CSV）"),
        ("排期表.md", os.path.join(导出目录(推文名), "排期表.md"), "排期表（人读）"),
        ("_看片表.png", os.path.join(项目目录(推文名), "_看片表.png"), "九宫格合图"),
    ]

    在 = [(n, p, s) for n, p, s in 清单 if os.path.isfile(p)]
    if 空跑:
        报(f"[空跑] 会导出 {len(在)} 个文件 + {len(图)} 张分镜图 + {len(片)} 段片")
        for n, p, s in 在:
            报(f"   {n}　{os.path.getsize(p)} B　{s}")
        if not 在:
            报("   （一个都还没有 —— 先 先建/正文/分镜/配图）")
        return _交(json出, {"ok": True, "空跑": True, "文件数": len(在),
                            "图": len(图), "片": len(片)}, 0)

    if not 在 and not 图 and not 片:
        错("没有可导出的文件 —— 先跑 先建 → 正文 → 分镜 → 配图")
        return _交(json出, {"ok": False, "错误": "没有可导出的文件"}, 3)

    出 = 导出目录(推文名)
    _确保目录(推文名)
    报(f"导出到：{出}")
    for n, p, s in 在:
        报(f"   ✓ {n}（{os.path.getsize(p)} B）　{s}")
    for sub, 名, 们 in ((图目录(推文名), "分镜图", 图), (片目录(推文名), "成片", 片)):
        if 们:
            报(f"   ✓ {名} {len(们)} 个　在 {sub}")

    说明 = [f"# {推文名} · 推文产出文件", "",
            f"> 导出时间：{_现在()}",
            f"> 分镜 {len(工.get('storyboards') or [])} 条　图 {len(图)} 张　片 {len(片)} 段", "",
            "| 文件 | 说明 |", "|---|---|"]
    for n, p, s in 在:
        说明.append(f"| {n} | {s} |")
    if 图:
        说明.append(f"| 分镜图/（{len(图)} 个） | 九宫格单格图集（飞彩 beat-board = 九宫格图集） |")
    if 片:
        说明.append(f"| 成片/（{len(片)} 个） | 分镜视频（飞彩 motion-prompt = 动态提示词产物） |")
    说明 += ["", "## 飞彩原名对照（from outputs 页模块 17843）", ""]
    for k, v in 产物说明.items():
        说明.append(f"- `{k}` —— {v}")
    _写文(os.path.join(出, "导出说明.md"), "\n".join(说明))
    报("   ✓ 导出说明.md")

    return _交(json出, {"ok": True, "目录": 出, "文件数": len(在) + 1,
                        "图": len(图), "片": len(片)}, 0)


# ============================================================
# 十三、命令 · 体检
# ============================================================

def 命令_体检(推文名, json出=False):
    头(f"体检《{推文名}》")
    d = 项目目录(推文名)
    if not os.path.isdir(d):
        错(f"没有这部推文：{d}")
        return _交(json出, {"ok": False, "错误": "推文不存在", "目录": d,
                            "建议": "先用 `先建` 建一部"}, 2)
    工 = _读json(项目文件(推文名)) or {}
    板们 = 工.get("storyboards") or []
    图 = _目录里的图(图目录(推文名))
    片 = [f for f in os.listdir(片目录(推文名)) if f.lower().endswith(".mp4")] \
        if os.path.isdir(片目录(推文名)) else []

    行 = _排期行(推文名, 板们)
    表 = [
        ("工程文件", os.path.isfile(项目文件(推文名)), 项目文件(推文名)),
        ("分镜（tuiwen/script.json）", os.path.isfile(分镜文件(推文名)), 分镜文件(推文名)),
        ("结构化剧本（structure.json）", os.path.isfile(os.path.join(分镜目录(推文名), "structure.json")),
         os.path.join(分镜目录(推文名), "structure.json")),
        ("节拍拆解（beat-breakdown.md）", os.path.isfile(os.path.join(分镜目录(推文名), "beat-breakdown.md")),
         os.path.join(分镜目录(推文名), "beat-breakdown.md")),
        ("推文正文", os.path.isfile(正文文件(推文名)), 正文文件(推文名)),
        (f"分镜图（{len(图)} 张）", len(图) > 0, 图目录(推文名)),
        (f"成片（{len(片)} 段）", len(片) > 0, 片目录(推文名)),
        ("排期表", os.path.isfile(os.path.join(导出目录(推文名), "排期表.csv")),
         os.path.join(导出目录(推文名), "排期表.csv")),
    ]
    报("产物：")
    for n, 有, p in 表:
        报(f"   {'✓' if 有 else '✗'} {n}")
    if 板们:
        空 = sum(1 for r in 行 if r["状态"] == "空行")
        报(f"分镜：{len(板们)} 条，其中空行 {空} 条；"
           f"每条 timelineShots {时间线镜头数(int(工.get('durationSeconds',15)))} 条"
           f"（飞彩合同：10/15 秒档 10 条、30 秒档 30 条）")

    缺 = [n for n, 有, _ in 表 if not 有]
    下一 = "先建" if not 板们 else (
        "正文" if not os.path.isfile(正文文件(推文名)) else (
            "配图 --九宫格" if not 图 else ("配视频" if not 片 else "导出")))
    报("")
    报(f"下一步：python 推文.py {下一} {推文名}")
    if 缺:
        报(f"还缺：{'、'.join(缺)}")
    return _交(json出, {"ok": True, "分镜数": len(板们), "图": len(图), "片": len(片),
                        "还缺": 缺, "下一步": 下一}, 0)


# ============================================================
# 十四、命令 · 自测
# ============================================================

def 命令_自测(json出=False):
    """真跑：造工程 → 写正文 → 拆分镜 → 出排期表 → 导出 → 体检。

    不碰 ComfyUI（不出真图真片），其余全部真写盘。
    输出三个数：通过 / 失败 / 没测。
    """
    头("自测 · 推文工作台")
    通过 = 失败 = 没测 = 0
    行 = []

    def 记(名, 果, 说明了=""):
        nonlocal 通过, 失败, 没测
        if 果 is True:
            通过 += 1
            行.append(("通过", 名, 说明了))
        elif 果 is False:
            失败 += 1
            行.append(("失败", 名, 说明了))
        else:
            没测 += 1
            行.append(("没测", 名, 说明了))

    名 = "_自测推文"    # 1 先建
    try:
        rc = 命令_先建(名, 时长=15, 时代="盛唐", 条数=3, 重做=True)
        记("先建", rc == 0 and os.path.isfile(项目文件(名)), f"exit {rc}")
    except Exception as e:
        记("先建", False, f"{type(e).__name__}: {e}")
    # 2 正文
    try:
        rc = 命令_正文(名, 标题="春江花月夜", 文="江畔何人初见月。江月何年初照人。",
                       话题="唐诗,国风")
        记("正文", rc == 0 and os.path.isfile(正文文件(名)), f"exit {rc}")
    except Exception as e:
        记("正文", False, f"{type(e).__name__}: {e}")
    # 3 分镜
    try:
        rc = 命令_分镜(名, 条数=3, 重做=True)
        工 = _读json(项目文件(名)) or {}
        板们 = 工.get("storyboards") or []
        对 = (rc == 0 and len(板们) == 3
              and all(len((b.get("board") or {}).get("timelineShots") or []) == 时间线镜头数(15)
                      for b in 板们))
        记("分镜", 对, f"exit {rc}，{len(板们)} 条 × "
                       f"{时间线镜头数(15)} 个时间线镜头")
    except Exception as e:
        记("分镜", False, f"{type(e).__name__}: {e}")
    # 4 契约字段齐不齐（飞彩 ih() 的字段逐个核）
    try:
        工 = _读json(项目文件(名)) or {}
        b = (工.get("storyboards") or [{}])[0]
        bd = b.get("board") or {}
        要 = ["id", "shot", "videoShot", "meta"]
        要板 = ["id", "n", "brief", "characters", "sceneType", "sceneAnchor",
                "durationSeconds", "timelineShots", "directing", "dialogues",
                "videoPrompt", "videoPromptStatus", "contentStatus"]
        缺 = [k for k in 要 if k not in b] + [k for k in 要板 if k not in bd]
        缺锚 = [k for k in ("layout", "keyProps", "lightSource", "colorKey", "styleLock")
                if k not in (bd.get("sceneAnchor") or {})]
        缺导 = [k for k in ("cameraMotion", "emotionArc", "montage", "rhythm", "hook")
                if k not in (bd.get("directing") or {})]
        记("契约字段（飞彩 ih()）", not (缺 or 缺锚 or 缺导),
           f"缺 storyboard={缺} sceneAnchor={缺锚} directing={缺导}" if (缺 or 缺锚 or 缺导)
           else "13 个 board 字段 + 5 个锚点 + 5 个导演字段全在")
    except Exception as e:
        记("契约字段（飞彩 ih()）", False, f"{type(e).__name__}: {e}")
    # 5 排期表
    try:
        rc = 命令_排期(名)
        对 = rc == 0 and os.path.isfile(os.path.join(导出目录(名), "排期表.csv"))
        记("排期", 对, f"exit {rc}")
    except Exception as e:
        记("排期", False, f"{type(e).__name__}: {e}")
    # 6 空跑不出图/不出片
    try:
        rc = 命令_配图(名, 九宫格=True, 空跑=True)
        图 = _目录里的图(图目录(名))
        记("配图 --空跑 不落图", rc == 0 and not 图, f"exit {rc}，图 {len(图)} 张")
    except Exception as e:
        记("配图 --空跑 不落图", False, f"{type(e).__name__}: {e}")
    try:
        rc = 命令_配视频(名, 模式="全能参考", 空跑=True)
        片 = os.path.isdir(片目录(名)) and any(f.endswith(".mp4") for f in os.listdir(片目录(名)))
        记("配视频 --空跑 不落片", rc == 0 and not 片, f"exit {rc}")
    except Exception as e:
        记("配视频 --空跑 不落片", False, f"{type(e).__name__}: {e}")
    # 7 导出
    try:
        rc = 命令_导出(名)
        记("导出", rc == 0 and os.path.isfile(os.path.join(导出目录(名), "导出说明.md")), f"exit {rc}")
    except Exception as e:
        记("导出", False, f"{type(e).__name__}: {e}")
    # 8 体检
    try:
        rc = 命令_体检(名)
        记("体检", rc == 0, f"exit {rc}")
    except Exception as e:
        记("体检", False, f"{type(e).__name__}: {e}")
    # 9 真出图（要 ComfyUI，没跑就算「没测」，不算失败）
    try:
        if _引擎 is None:
            记("真出图（要 ComfyUI）", None, f"引擎.py 没载入：{_引擎错}")
        else:
            在 = False
            try:
                # 引擎.在线() 返回 {在线,版本,显卡,显存GB}
                在 = bool((_引擎.在线() or {}).get("在线"))
            except Exception as e:
                在 = False
                行.append(("没测", "引擎在线探测", str(e)))
            if not 在:
                记("真出图（要 ComfyUI）", None, "ComfyUI 没在跑，跳过（不算失败）")
            else:
                rc = 命令_配图(名, 单格=1, 重做=True)
                记("真出图（要 ComfyUI）", rc == 0, f"exit {rc}")
    except Exception as e:
        记("真出图（要 ComfyUI）", False, f"{type(e).__name__}: {e}")
    # 10 风格库联得上
    try:
        if _风格库 is None:
            记("风格库联动", None, f"风格库.py 没载入：{_风格库错}")
        else:
            ks = _风格库.全部() or []
            s = 编译风格(ks[0] if ks else "")
            记("风格库联动", bool(ks) and bool(s["正向"]),
               f"{len(ks)} 个风格；「{s['风格']}」正向 { s['正向'][:36]}…")
    except Exception as e:
        记("风格库联动", False, f"{type(e).__name__}: {e}")
    # 11 拼图 / 配音 可载入
    记("拼图.py 可载入", True if _拼图 is not None else None,
       "在" if _拼图 is not None else f"没载入：{_拼图错}")
    记("配音.py 可载入", True if _配音 is not None else None,
       "在" if _配音 is not None else f"没载入（可选，不影响主链）：{_配音错}")
    # 12 能被挂进 MCP：命令表可读 + 进度可被接走（影匠MCP.py 那套 工具表/注册表 靠这两条）
    try:
        global 报
        汇集 = []

        def _接走(s):
            汇集.append(str(s))

        原报 = 报
        报 = _接走                      # 命令内部按名字找模块级 报，替换即生效
        try:
            rc2 = 命令_体检(名, json出=False)
            # 命令表同时按文本打印一份，这里接进缓冲区，别把自测输出冲乱
            罩 = io.StringIO()
            with contextlib.redirect_stdout(罩):
                命令_命令表(json出=False)
            文本 = 罩.getvalue()
        finally:
            报 = 原报
        记("可被挂进 MCP（命令表 + 进度回调）",
           rc2 == 0 and len(汇集) >= 3 and "命令表" in 文本 and len(命令参数) >= 8,
           f"{len(命令参数)} 条命令有参数清单；接走进度 {len(汇集)} 行"
           f"（如「{汇集[0][:18] if 汇集 else ''}…」）；命令表文本 {len(文本)} 字符")
    except Exception as e:
        记("可被挂进 MCP（命令表 + 进度回调）", False, f"{type(e).__name__}: {e}")

    print()
    for _态, _名, _说 in 行:
        print(f"   [{'✓' if _态=='通过' else ('✗' if _态=='失败' else '–')}] {排(_名, 26)} {_说}")
    print()
    print(f"   通过 {通过}　失败 {失败}　没测 {没测}")
    print(f"   自测工程：{项目目录(名)}")
    if json出:
        print(json.dumps({"ok": 失败 == 0, "通过": 通过, "失败": 失败, "没测": 没测,
                          "明细": [{"状态": a, "项": b, "说明": c} for a, b, c in 行]},
                         ensure_ascii=False, indent=1))
    return 0 if 失败 == 0 else 1


# ============================================================
# 十五、公共小工具
# ============================================================

def _没这部(推文名, json出):
    错(f"没有这部推文：{项目目录(推文名)}")
    错(f"先用：python 推文.py 先建 {推文名}")
    return _交(json出, {"ok": False, "错误": "推文不存在", "推文名": 推文名,
                        "建议": f"python 推文.py 先建 {推文名}"}, 2)


def _没分镜(推文名, json出):
    错(f"《{推文名}》还没有分镜")
    错(f"先跑：python 推文.py 分镜 {推文名}")
    return _交(json出, {"ok": False, "错误": "没有分镜", "推文名": 推文名,
                        "建议": f"python 推文.py 分镜 {推文名}"}, 3)


def _交(json出, 数据, 码):
    if json出:
        print(json.dumps(数据, ensure_ascii=False, indent=1))
    return 码


# ============================================================
# 十六、命令行
# ============================================================

# 命令 → 参数清单。给 MCP 挂载用：影匠MCP.py 的 `工具表` 可以直接照这份生成，
# 里面的 参数/必填/默认 都是从各 命令_* 的真实签名抄下来的，不是另写一套。
命令参数 = {
    "先建": [("推文名", "str", True, None, "工程名，产物落在 作品/<推文名>/"),
             ("时长", "int", False, 15, "分镜叙事目标时长档：10 / 15 / 30"),
             ("条数", "int", False, 3, "storyboard 条数（每条 = 一个叙事合集）"),
             ("时代", "str", False, "", "时代背景，写进 sceneAnchor 锚点"),
             ("重做", "bool", False, False, "已有 script.json 也重铺")],
    "正文": [("推文名", "str", True, None, "工程名"),
             ("标题", "str", False, "", "推文标题"),
             ("文", "str", False, "", "正文素材；不给就走 正文提示词.md 那套")],
    "分镜": [("推文名", "str", True, None, "工程名"),
             ("条数", "int", False, 0, "0 = 沿用先建时的条数"),
             ("文", "str", False, "", "直接给正文，跳过读取"),
             ("重做", "bool", False, False, "已有分镜也重拆")],
    "配图": [("推文名", "str", True, None, "工程名"),
             ("九宫格", "bool", False, True, "整板出图；给了 单格 就只出一格"),
             ("单格", "int", False, None, "只出这一格（1-9）"),
             ("序号", "str", False, None, "只出这些板，如 ep1-s1,ep1-s3"),
             ("风格键", "str", False, "cinematic-real", "风格库.py 里的风格键"),
             ("重做", "bool", False, False, "已有图也重出")],
    "配视频": [("推文名", "str", True, None, "工程名"),
               ("模式", "str", False, "全能参考", "文生视频 / 首尾帧 / 全能参考"),
               ("序号", "str", False, None, "只配这些板"),
               ("风格键", "str", False, "cinematic-real", "风格库.py 里的风格键"),
               ("重做", "bool", False, False, "已有片也重出")],
    "排期": [("推文名", "str", True, None, "工程名")],
    "导出": [("推文名", "str", True, None, "工程名")],
    "体检": [("推文名", "str", True, None, "工程名")],
}
退出码表 = {"0": "成功", "2": "参数 / 命令不对", "3": "上游没到位（引擎/风格库/配音）",
            "4": "出图出片失败，或 ComfyUI 状态不明"}
公共开关 = [("空跑", "bool", False, False, "只演一遍：不连 ComfyUI、不落任何图/片"),
            ("json", "bool", False, False, "结果打成 JSON 打到 stdout，给 MCP / 别的程序读")]


def 命令_命令表(json出=False):
    """给 MCP 挂载用的机器可读清单。

    用法（影匠MCP.py 里照这份生成 `工具表` / `注册表`）：
        python 推文.py 命令表 --json
    返回 {"ok":True,"模块":"推文","入口":"推文.py","命令":[...],"退出码":{...},
          "公共开关":[...],"挂钩":{"报":"模块级函数 报(s)，可替换成自己的进度回调",
          "调用":"命令_* 全部返回 int 退出码，json出=True 时把信封打到 stdout"}}
    """
    条 = []
    for 名, 说明 in 命令们.items():
        if 名 in ("命令表", "自测"):
            continue
        参 = 命令参数.get(名, [])
        条.append({
            "名": 名,
            "说明": 说明,
            "用法": f"python 推文.py {名} <推文名> " + " ".join(
                f"--{a}" for a, t, 必, 缺, _ in 参 if a != "推文名"),
            "参数": ([{"名": a, "类型": t, "必填": 必, "默认": 缺, "说明": d}
                      for a, t, 必, 缺, d in 参]
                     + [{"名": a, "类型": t, "必填": 必, "默认": 缺, "说明": d}
                        for a, t, 必, 缺, d in 公共开关]),
            "纯json命令": 名 == "自测",
        })
    数据 = {
        "ok": True, "模块": "推文", "入口": "推文.py",
        "说明": "飞彩「推文模式」(studio 页 webpack 模块 88350) 的影匠落地："
                "正文 → 分镜 → 配图 → 配视频 → 排期 → 导出",
        "命令": 条,
        "退出码": 退出码表,
        "公共开关": [{"名": a, "说明": d} for a, t, 必, 缺, d in 公共开关],
        "挂钩": {
            "报": "模块级函数 报(s)：替换它就能把进度接走（MCP 里建议换成往 client 推通知）",
            "调用": "命令_* 全部是普通函数、返回 int 退出码；json出=True 时信封打到 stdout",
            "命令数": len(条),
        },
    }
    if json出:
        print(json.dumps(数据, ensure_ascii=False, indent=1))
    else:
        头("推文.py 命令表（给 MCP 挂载用）")
        for t in 条:
            报(f"{t['名']:<6} {t['说明']}")
            报(f"       {t['用法']}")
        报("")
        报("退出码：" + "　".join(f"{k} {v}" for k, v in 退出码表.items()))
    return 0


命令们 = {
    "先建": "建一部推文工程（tuiwen/script.json），铺好 storyboard 骨架",
    "正文": "写推文发布文案（飞彩的「一键复制文案」），并落 正文提示词.md",
    "分镜": "Stage 1：把正文拆成 10/15/30 秒叙事合集（每条一行，不拆九条）",
    "配图": "Stage 2：按九宫格模板出分镜图（--九宫格 全出，--单格 N 只出一格）",
    "配视频": "把分镜图配成片（--模式 文生视频/首尾帧/全能参考）",
    "排期": "出 TuiwenTable 那样的行表 → 排期表.csv / 排期表.md",
    "导出": "把正文/分镜/排期/图/片清点一遍，写 导出说明.md",
    "体检": "扫目录，报产物齐不齐 + 下一步该干什么",
    "命令表": "把命令/参数/退出码打成机器可读清单，给 MCP（影匠MCP.py）挂载用",
    "自测": "真跑一遍全链路（不出真图真片），报 通过/失败/没测",
}
别名 = {"建": "先建", "新建": "先建", "文案": "正文", "拆": "分镜",
        "出图": "配图", "九宫格": "配图", "出片": "配视频", "视频": "配视频",
        "进度": "体检", "检查": "体检", "schedule": "排期", "自检": "自测",
        "工具表": "命令表", "mcp": "命令表", "工具": "命令表"}


def 用法():
    print(__doc__)
    print("\n各命令干什么：")
    for k, v in 命令们.items():
        print(f"  {k:<8} {v}")
    print("\n开关：--空跑 只演一遍不碰 ComfyUI　--json 出 JSON　--重做 已有产物也重出")
    print("      --时长 10|15|30　--条数 N　--九宫格　--单格 N　--模式 文生视频|首尾帧|全能参考")
    print("      --序号 ep1-s1,ep1-s3　--风格 风格键　--时代 文本　--文 文本　--话题 文本")


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "帮", "用法"):
        用法()
        return 0
    命令 = 别名.get(argv[1], argv[1])
    if 命令 not in 命令们:
        错(f"不认识这个命令：{argv[1]}")
        用法()
        return 2

    参数 = list(argv[2:])
    if 命令 == "自测":
        空 = {x for x in 参数 if x.startswith("-")}
        return 命令_自测(json出=("--json" in 空))
    if 命令 == "命令表":
        空 = {x for x in 参数 if x.startswith("-")}
        return 命令_命令表(json出=("--json" in 空))

    if not 参数:
        错(f"命令 {命令} 要跟一个推文名，例如：python 推文.py {命令} 春江花月夜")
        return 2
    推文名 = 参数[0]
    参数 = 参数[1:]

    开关 = {x for x in 参数 if x.startswith("-")}
    空跑 = "--空跑" in 开关 or "-空跑" in 开关
    json出 = "--json" in 开关 or "-json" in 开关
    重做 = "--重做" in 开关 or "-重做" in 开关
    九宫格 = "--九宫格" in 开关 or "-九宫格" in 开关
    九宫格 = 九宫格 or (命令 == "配图" and not any(参数[i] in ("--单格", "-单格") for i in range(len(参数))))

    def 取值长(名, 缺=None):
        for i, x in enumerate(参数):
            if x in ("--" + 名, "-" + 名) and i + 1 < len(参数):
                return 参数[i + 1]
        for x in 参数:
            if x.startswith("--" + 名 + "="):
                return x.split("=", 1)[1]
            if x.startswith("-" + 名 + "="):
                return x.split("=", 1)[1]
        return 缺

    try:
        if 命令 == "先建":
            时长 = int(取值长("时长", 15) or 15)
            条数 = int(取值长("条数", 3) or 3)
            return 命令_先建(推文名, 时长=时长, 时代=取值长("时代", "") or "",
                            条数=条数, 空跑=空跑, json出=json出, 重做=重做)
        if 命令 == "正文":
            return 命令_正文(推文名, 标题=取值长("标题", "") or "",
                            文=取值长("文", "") or "", 要点=取值长("要点", "") or "",
                            话题=取值长("话题", "") or "", 空跑=空跑, json出=json出)
        if 命令 == "分镜":
            return 命令_分镜(推文名, 条数=int(取值长("条数", 0) or 0), 文=取值长("文", "") or "",
                            空跑=空跑, json出=json出, 重做=重做)
        if 命令 == "配图":
            单格 = 取值长("单格")
            单格 = int(单格) if 单格 and str(单格).isdigit() else None
            return 命令_配图(推文名, 九宫格=九宫格, 单格=单格, 序号=取值长("序号"),
                            风格键=取值长("风格", 普通风格) or 普通风格,
                            空跑=空跑, json出=json出, 重做=重做)
        if 命令 == "配视频":
            return 命令_配视频(推文名, 模式=取值长("模式", "全能参考") or "全能参考",
                              序号=取值长("序号"), 风格键=取值长("风格", 普通风格) or 普通风格,
                              空跑=空跑, json出=json出, 重做=重做)
        if 命令 == "排期":
            return 命令_排期(推文名, 空跑=空跑, json出=json出)
        if 命令 == "导出":
            return 命令_导出(推文名, 空跑=空跑, json出=json出)
        if 命令 == "体检":
            return 命令_体检(推文名, json出=json出)
    except ValueError as e:
        错(f"参数不是数字：{e}")
        return 2
    except FileNotFoundError as e:
        错(f"文件不在了：{e}")
        错("多半是路径写错或目录被删。用 `体检` 看现状。")
        return 4
    except Exception as e:
        错(f"跑挂了：{type(e).__name__}: {e}")
        if os.environ.get("影匠_回溯"):
            traceback.print_exc()
        return 4
    return 2


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv))
