# -*- coding: utf-8 -*-
"""
影匠 · 一致性系统（原创实现）

维护一个跨分镜复用的「素材库」：角色(character) / 场景(scene) / 道具(prop) / 服装(costume)。
每个素材有 名字、描述、参考图、标签；落盘为 JSON。

    D:\\DSHworkspace\\影匠\\素材\\素材库.json
    D:\\DSHworkspace\\影匠\\素材\\图\\<id>.png        ← 绑定进来的参考图副本

核心接口
    绑定(素材名, 图片路径)            把本机图片绑成该素材的参考图（复制入库，原图不动）
    列出(类别="")                     清单
    查(名字)                          单条
    注入(提示词, 素材名列表, **选项)   ★核心：把素材翻译成英文提示词并拼成完整生图提示词
    参考块(素材名列表, **选项)        只取参考图编号块
    图数组(素材名列表)                按编号顺序返回参考图路径（喂给图像模型的图片顺序）
    服装推荐(场景名或文本, 角色名="") 按标签给服装打分排序
    自测()                            造一批素材跑通全链路

设计要点（照飞彩规格，见 知识\\一致性系统.md）
  1. 参考图**不是**被 VLM 描述成文字再拼进提示词；参考图本体作为图片一起发给图像模型，
     提示词里只用 @1 @2 @3 这种**位置编号**引用它们。
  2. 编号 = 参考图连线顺序，系统自动排布（错位会导致 AI 认错角色）。
  3. 图片顺序：垫图/尾帧 → 角色 → 场景 → 道具 → 服装 → 其他 → 风格参考图。
  4. 注入文本结构（本模块的实现，含四段）：
         参考图序号对应：参考图1是【角色：X，用于保持画面连续性】；参考图2是【场景：Y】…
         [2 REFERENCE IMAGES ATTACHED：… 每张图前有文字标签（参考图1、参考图2…），严格照它对应。]
         Use the reference images as the primary subject. …
         零文字铁律：…
         <原始提示词正文>
  5. 中文描述走 `角色库.py` 的 96 词对照词典翻成英文（只读复用，不改它）。

依赖：仅标准库 + Pillow（影匠既有环境已装）。不联网、不调用任何模型 API。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import datetime

# 影匠既有模块导入：脚本目录可能不在 sys.path，先补上。
_根 = os.path.dirname(os.path.abspath(__file__))
if _根 not in sys.path:
    sys.path.insert(0, _根)


def _装模块(文件名, 别名):
    """
    载入影匠既有模块（只读，绝不改它们）。
    中文文件名在部分环境直接 import 会失败，所以先试 import，再退回按路径载入。
    """
    try:
        return __import__(别名), ""
    except Exception as e1:
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
    except Exception as e2:
        return None, f"import 失败({e1!r})；按路径载入失败({e2!r})"


_角色库, _角色库错 = _装模块("角色库.py", "角色库")
_风格库, _风格库错 = _装模块("风格库.py", "风格库")


__all__ = [
    "素材根", "图目录", "库文件", "类别表", "类别中文",
    "载入", "保存", "清空", "建", "删", "改",
    "绑定", "绑定目录", "解绑", "解绑为孤儿", "列出", "查", "查找", "统计",
    "译", "译描述", "译描述细", "加译补", "译补", "标签串", "排序", "编号",
    "注入", "参考块", "图数组", "编号表", "写md",
    "服装推荐", "服装建", "场景标签",
    "风格提示词", "自测",
]

# ============================================================
# 路径与常量
# ============================================================
素材根 = os.path.join(_根, "素材")
图目录 = os.path.join(素材根, "图")
库文件 = os.path.join(素材根, "素材库.json")

# 四类素材。键用英文（跟提示词/图片标记一致），值给中文名与编号前缀。
类别表 = {
    "character": {"中文": "角色", "前缀": "char", "图标记": "CHARACTER"},
    "scene":     {"中文": "场景", "前缀": "scene", "图标记": "SCENE"},
    "prop":      {"中文": "道具", "前缀": "prop", "图标记": "PROP"},
    "costume":   {"中文": "服装", "前缀": "cost", "图标记": "COSTUME"},
}
类别中文 = {v["中文"]: k for k, v in 类别表.items()}
# 中文别名 → 英文键（方便手写）
for _a in ("角色", "人物", "char", "chars", "characters"):
    类别中文.setdefault(_a, "character")
for _a in ("场景", "环境", "地点", "scene", "scenes", "location"):
    类别中文.setdefault(_a, "scene")
for _a in ("道具", "物件", "prop", "props", "item"):
    类别中文.setdefault(_a, "prop")
for _a in ("服装", "服装造型", "戏服", "穿搭", "costume", "costumes", "outfit", "wardrobe"):
    类别中文.setdefault(_a, "costume")

# 图片顺序：垫图/尾帧 → 角色 → 场景 → 道具 → 服装 → 其他 → 风格
顺序权重 = {"base": 0, "character": 1, "scene": 2, "prop": 3, "costume": 4, "other": 5, "style": 6}

# 每类素材给图像模型的英文标签（说明该图该怎么用）
图标签 = {
    "character": "CHARACTER reference sheet — keep this character's face, hairstyle, outfit and body "
                 "proportions EXACTLY identical wherever they appear",
    "scene":     "SCENE reference — match this location's environment, layout, materials and lighting",
    "prop":      "PROP reference — reproduce this object's exact design, proportions and material",
    "costume":   "COSTUME reference — dress the character EXACTLY in this outfit, keep every garment "
                 "detail and colour identical",
    "style":     "STYLE reference — take ONLY the art style / rendering technique / palette from this "
                 "image; do NOT copy its subject matter, characters or layout",
    "other":     "ADDITIONAL reference — adjacent storyboard frame kept for visual continuity",
}

# 参考图语义前缀（中文，进「参考图序号对应」那一行）
语义前缀 = {
    "character": "角色",
    "scene":     "场景",
    "prop":      "道具",
    "costume":   "服装",
    "style":     "🎨 风格参考图",
    "base":      "底图",
    "other":     "其他参考",
}

# 影匠统一的注入文本块（原创措辞）
抬头 = (
    "参考图序号对应：{对应表}"
)
外部表头 = (
    "[{张数} REFERENCE IMAGES ATTACHED: {摘要}。"
    "每张图前面带一行文字标签（参考图1、参考图2…），严格按标签对应使用，不得张冠李戴。]"
)
主指令 = (
    "Use the reference images as the primary subject. Pay attention to the spatial layout of the "
    "environment and the relative positions of characters and objects in the space. Generate coherent "
    "frames from different angles that follow the plot progression. Maintain strict consistency with "
    "the art style of the reference images."
)
零文字铁律 = (
    "零文字铁律：成图里不得出现任何文字 —— 台词、对话气泡、字幕、时间码、镜号、水印、角色名、拟声词，"
    "一个都不许有。分镜描述里引号内的台词只作表演提示（表情、手势、情绪），绝不允许画成可见文字。"
)
环境带入 = (
    "时代/世界观：{设定}。所有视觉元素（服装、建筑、道具、载具、科技水平、武器、光线审美）都必须严格贴合该设定，"
    "不得把现代物件混进古代/奇幻，也不得反过来。"
)
风格兜底 = "统一画风与色调，电影级光影，画面干净锐利。"

_默认库 = {"版本": 1, "更新": "", "说明": "影匠 · 一致性素材库（角色/场景/道具/服装）", "素材": {}}

_库 = None
_已载 = False


# ============================================================
# 落盘
# ============================================================
def _确保目录():
    os.makedirs(图目录, exist_ok=True)


def 载入(重载=False):
    """读素材库；返回整个 dict。文件不存在则返回空库（不写盘）。"""
    global _库, _已载
    if _已载 and not 重载 and _库 is not None:
        return _库
    if os.path.exists(库文件):
        try:
            with open(库文件, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception as e:
            raise RuntimeError(f"素材库 JSON 解析失败：{库文件} → {e}") from e
        if not isinstance(d, dict) or not isinstance(d.get("素材"), dict):
            raise RuntimeError(f"素材库结构不对（缺 素材 字典）：{库文件}")
    else:
        d = json.loads(json.dumps(_默认库, ensure_ascii=False))
    _库 = d
    _已载 = True
    return _库


def 保存():
    """写盘（原子替换）。"""
    d = 载入()
    _确保目录()
    d["更新"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    d["数量"] = {k: sum(1 for v in d["素材"].values() if v.get("类别") == k) for k in 类别表}
    tmp = 库文件 + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, 库文件)
    return 库文件


def 清空(真删图片=False):
    """清空素材库（默认保留 图\\ 下的文件）。"""
    global _库, _已载
    d = json.loads(json.dumps(_默认库, ensure_ascii=False))
    d["更新"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    d["数量"] = {k: 0 for k in 类别表}
    _库 = d
    _已载 = True
    if 真删图片 and os.path.isdir(图目录):
        shutil.rmtree(图目录, ignore_errors=True)
    # 刻意不走 保存()：保存() 内部会 载入()，一旦 _已载 失效就会把磁盘上的旧库读回来，
    # 表现为「清空后旧数据复活」。这里直接写盘，顺带修正可能写坏的键。
    _确保目录()
    tmp = 库文件 + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, 库文件)
    _已载 = True
    return d


# ============================================================
# 小工具
# ============================================================
def _规范类别(类别):
    if not 类别:
        return ""
    k = str(类别).strip().lower()
    if k in 类别表:
        return k
    return 类别中文.get(str(类别).strip(), "")


def _slug(名):
    """素材名 → 文件名安全串（保留中文，去掉路径与空白）。"""
    s = str(名).strip().replace("\\", "_").replace("/", "_")
    s = re.sub(r'[<>:"|?*\x00-\x1f]', "_", s)
    s = re.sub(r"\s+", "_", s)
    return s[:60] or "未命名"


def _新id(类别, 名):
    d = 载入()
    基 = f"{类别表[类别]['前缀']}_{_slug(名)}"
    n, i = 基, 2
    while n in d["素材"]:
        n, i = f"{基}_{i}", i + 1
    return n


def _现在():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _归一(标签):
    if 标签 is None:
        return []
    if isinstance(标签, str):
        标签 = re.split(r"[,，、;；\s]+", 标签)
    out = []
    for t in 标签:
        t = str(t).strip()
        if t and t not in out:
            out.append(t)
    return out


# ============================================================
# 增删改查
# ============================================================
def 建(名, 类别="character", 描述="", 标签=None, 别名=None, 关联角色="", 参考图="",
      英文名="", 英文描述="", **额外):
    """
    新建一条素材，返回 id。

    名        素材名（唯一键，重复会报错）
    类别      character / scene / prop / costume（可写中文「角色/场景/道具/服装」）
              别名：char / chars / location / outfit / wardrobe / 人物 / 环境 / 戏服 …
    描述      中文描述（注入时由 角色库.py 的词典翻成英文）
    标签      列表或逗号分隔串；服装的标签推荐写场景名，供 服装推荐() 打分
    别名      同一实体的其它叫法，查找时都能命中
    关联角色  服装专用：这条服装属于哪个角色（注入时标注「worn by X」）
    参考图    可选的图片路径，等价于建完再调 绑定()
    英文名    注入时给模型看的英文名（不给就自动查词典，人名通常翻不动会保留中文）
    英文描述  直接写死的英文描述；给了就不再走词典，注入时优先用它
    额外      任意其它字段，直接存进条目（例如 备注 / 出处 / 集数）
    """
    k = _规范类别(类别)
    if not k:
        raise ValueError(f"不认识的类别：{类别!r}；可用 {list(类别表)} 或 {list(类别中文)}")
    名 = str(名).strip()
    if not 名:
        raise ValueError("素材名不能为空")
    d = 载入()
    for v in d["素材"].values():
        if v.get("名") == 名:
            raise ValueError(f"素材名已存在：{名}（id={v.get('id')}）")

    i = _新id(k, 名)
    条 = {
        "id": i,
        "名": 名,
        "英文名": str(英文名 or "").strip(),
        "类别": k,
        "描述": str(描述 or "").strip(),
        "英文描述": str(英文描述 or "").strip(),
        "标签": _归一(标签),
        "别名": _归一(别名),
        "参考图": "",
        "图源": "",
        "绑定时间": "",
        "关联角色": str(关联角色 or "").strip(),
        "启用": True,
        "建时间": _现在(),
        "改时间": _现在(),
    }
    for kk, vv in 额外.items():
        if kk not in 条:
            条[kk] = vv
    d["素材"][i] = 条
    if 参考图:
        绑定(名, 参考图)
    else:
        保存()
    return i


def 改(名, **字段):
    """改任意字段。改「描述」会清掉缓存的英文描述。"""
    v = _要求(名)
    for k, val in 字段.items():
        if k == "标签" or k == "别名":
            v[k] = _归一(val)
        elif k == "类别":
            kk = _规范类别(val)
            if not kk:
                raise ValueError(f"不认识的类别：{val!r}")
            v["类别"] = kk
        elif k in ("名", "id"):
            raise ValueError(f"{k} 不允许直接改（id/名 是键）")
        else:
            v[k] = val
    if "描述" in 字段:
        v["英文描述"] = ""
    v["改时间"] = _现在()
    保存()
    return v


def 删(名, 连图=True):
    """删条目；连图=True 时把库内图片副本也删掉（原图不动）。"""
    v = _要求(名)
    d = 载入()
    p = v.get("参考图", "")
    d["素材"].pop(v["id"], None)
    if 连图 and p and os.path.isfile(p) and os.path.abspath(p).startswith(os.path.abspath(图目录)):
        try:
            os.remove(p)
        except OSError:
            pass
    保存()
    return v


def 查(名字):
    """按 id / 名 / 别名 精确查；先 id，再名，再别名（不区分大小写）。找不到返回 None。"""
    d = 载入()
    s = str(名字).strip()
    if s in d["素材"]:
        return d["素材"][s]
    for v in d["素材"].values():
        if v.get("名") == s:
            return v
    low = s.lower()
    for v in d["素材"].values():
        if str(v.get("名", "")).lower() == low:
            return v
        for a in v.get("别名", []) or []:
            if str(a).lower() == low:
                return v
    return None


def _要求(名字):
    v = 查(名字)
    if v is None:
        raise KeyError(f"素材库里没有：{名字}")
    return v


def 查找(关键词="", 类别="", 只带有图=False, 启用中=True):
    """模糊查：关键词同时匹配 名 / id / 别名 / 描述 / 标签。返回列表。"""
    d = 载入()
    k = _规范类别(类别) if 类别 else ""
    kw = str(关键词 or "").strip().lower()
    out = []
    for v in d["素材"].values():
        if 启用中 and not v.get("启用", True):
            continue
        if k and v.get("类别") != k:
            continue
        if 只带有图 and not (v.get("参考图") and os.path.isfile(v["参考图"])):
            continue
        if kw:
            池 = " ".join([
                str(v.get("名", "")), str(v.get("id", "")), str(v.get("描述", "")),
                " ".join(map(str, v.get("别名", []) or [])),
                " ".join(map(str, v.get("标签", []) or [])),
                str(v.get("关联角色", "")),
            ]).lower()
            if kw not in 池:
                continue
        out.append(v)
    return 排序(out)


def 列出(类别="", 详细=False):
    """
    清单。详细=False 返回 [(名, 类别中文, 有无图)]；详细=True 返回 [dict]。
    """
    d = 载入()
    k = _规范类别(类别) if 类别 else ""
    vs = [v for v in d["素材"].values() if (not k or v.get("类别") == k)]
    vs = 排序(vs)
    if 详细:
        return vs
    return [(v["名"], 类别表[v["类别"]]["中文"], "有图" if v.get("参考图") else "无图") for v in vs]


def 统计():
    d = 载入()
    r = {类别表[k]["中文"]: 0 for k in 类别表}
    有图 = 0
    for v in d["素材"].values():
        r[类别表.get(v.get("类别"), {"中文": "其他"})["中文"]] = r.get(
            类别表.get(v.get("类别"), {"中文": "其他"})["中文"], 0) + 1
        if v.get("参考图"):
            有图 += 1
    r["合计"] = len(d["素材"])
    r["有参考图"] = 有图
    r["库文件"] = 库文件
    r["更新"] = d.get("更新", "")
    return r


def 排序(素材们):
    """按 类别顺序 → 名 排序。"""
    return sorted(
        素材们,
        key=lambda v: (顺序权重.get(v.get("类别"), 5), str(v.get("名", ""))),
    )


# ============================================================
# 参考图绑定
# ============================================================
def 绑定(素材名, 图片路径, 复制=True):
    """
    把一张本机图片绑成该素材的参考图。

    复制=True  把图片复制进 素材\\图\\<id>.<ext>（影匠素材自持，原图不动）
    复制=False 只登记原路径（图片被挪走就失效）

    注意：同一次生成里，一个素材只能贡献一张参考图；重复绑定是**替换**。
    返回新的参考图路径。
    """
    v = _要求(素材名)
    源 = os.path.abspath(os.path.expanduser(str(图片路径).strip().strip('"')))
    if not os.path.isfile(源):
        raise FileNotFoundError(f"图片不存在：{源}")
    _确保目录()
    if 复制:
        ext = os.path.splitext(源)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".avif"):
            ext = ".png"
        目标 = os.path.join(图目录, f"{v['id']}{ext}")
        if os.path.abspath(源) != os.path.abspath(目标):
            shutil.copy2(源, 目标)
        # 换过扩展名时清掉旧副本
        for 旧 in os.listdir(图目录):
            if 旧.startswith(v["id"] + ".") and os.path.join(图目录, 旧) != 目标:
                try:
                    os.remove(os.path.join(图目录, 旧))
                except OSError:
                    pass
        v["参考图"] = 目标
    else:
        v["参考图"] = 源
    v["图源"] = 源
    v["绑定时间"] = _现在()
    v["改时间"] = _现在()
    保存()
    return v["参考图"]


def 绑定目录(目录路径, 类别="", 覆盖=False, 复制=True):
    """
    批量绑定：把目录里的图片按**文件名（不含扩展名）**匹配素材名。

    返回 {"绑定": [(素材名, 路径)], "未匹配": [文件名], "跳过": [素材名]}
    """
    根目录 = os.path.abspath(str(目录路径))
    if not os.path.isdir(根目录):
        raise NotADirectoryError(f"目录不存在：{根目录}")
    好, 未匹配, 跳过 = [], [], []
    exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".avif")
    for f in sorted(os.listdir(根目录)):
        stem, ext = os.path.splitext(f)
        if ext.lower() not in exts:
            continue
        v = 查(stem)
        if v is None or (类别 and v.get("类别") != _规范类别(类别)):
            未匹配.append(f)
            continue
        if v.get("参考图") and not 覆盖:
            跳过.append(v["名"])
            continue
        绑定(v["名"], os.path.join(根目录, f), 复制=复制)
        好.append((v["名"], v["参考图"]))
    return {"绑定": 好, "未匹配": 未匹配, "跳过": 跳过}


def 解绑(素材名):
    """清空某素材的参考图（库内副本一并删除）。"""
    v = _要求(素材名)
    p = v.get("参考图", "")
    if p and os.path.isfile(p) and os.path.abspath(p).startswith(os.path.abspath(图目录)):
        try:
            os.remove(p)
        except OSError:
            pass
    v["参考图"] = ""
    v["改时间"] = _现在()
    保存()
    return v


def 解绑为孤儿(类别="character"):
    """列出没有参考图的素材名（照飞彩「该实体还没有参考图，暂时不能选入绑定」的口径）。"""
    return [v["名"] for v in 查找(类别=类别, 只带有图=False) if not v.get("参考图")]


# ============================================================
# 中→英：复用 角色库.py 的词典机制（只读）
# ============================================================
def _角色词典():
    if _角色库 is None:
        return {}, {}
    正 = getattr(_角色库, "_词典", {}) or {}
    反 = {}
    for k, v in 正.items():
        for 段 in str(v).split(","):
            段 = 段.strip().lower()
            if 段 and 段 not in 反:
                反[段] = k
    # 性别也当词收进来（男/女 → male/female）
    for k, v in (getattr(_角色库, "_性别", {}) or {}).items():
        正.setdefault(k, v)
        反.setdefault(str(v).strip().lower(), k)
    return 正, 反


def _英文占比(s):
    s = str(s or "")
    字母 = sum(1 for c in s if ("a" <= c <= "z") or ("A" <= c <= "Z"))
    汉字 = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    if 汉字 == 0:
        return 1.0
    return 字母 / max(1, 字母 + 汉字 * 2)


def 译(词):
    """
    单条中文词 → 英文。命中 角色库.py 的 96 词对照词典就用它（正查 + 反查）；
    已经基本是英文的原样返回；查不到的原样保留（让上层看得见，不静默丢词）。
    返回 (英文, 是否命中)
    """
    词 = str(词 or "").strip()
    if not 词:
        return "", False
    词典, 反 = _角色词典()
    if 词 in 词典:
        return 词典[词], True
    if 词 in 反:
        return 词, True          # 本身就是词典里的英文
    if _英文占比(词) >= 0.7 and not re.search(r"[\u4e00-\u9fff]", 词):
        return 词, True
    # 「黑发红眸」这类多字串：按词典做「最长词优先」切分再拼
    命中, i, n, 全中 = [], 0, len(词), True
    键 = sorted(词典, key=len, reverse=True)
    while i < n:
        for c in 键:
            if 词.startswith(c, i):
                命中.append(词典[c])
                i += len(c)
                break
        else:
            命中.append(词[i])
            全中 = False
            i += 1
    if 全中:
        return " ".join(x for x in 命中 if x.strip()), True
    return 词, False


# ------------------------------------------------------------
# 补译表：角色库.py 的 96 词词典只覆盖身体/发型/五官/衣着大类，
# 场景、道具、年龄、武器、朝代服制这些它一律翻不出来（_译 会直接丢掉并报警）。
# 这里给影匠自己补一层短语表，**不动 角色库.py**（只读）。
# 顺序无所谓，替换时按词长倒序，保证「银白长发披肩」优先于「长发」。
# ------------------------------------------------------------
译补 = {
    # 年龄 / 气质
    "青年": "young man", "少年": "youthful", "少女": "young girl", "孩童": "child",
    "中年": "middle-aged", "老年": "elderly", "二十出头": "in his early twenties",
    "十八九岁": "late teens", "面容清冷": "cold and aloof expression",
    "紫罗兰色杏眼": "violet almond-shaped eyes", "紫色杏眼": "purple almond-shaped eyes",
    "紫罗兰色": "violet", "紫色": "purple", "杏眼": "almond-shaped eyes", "冷白皮": "fair cool-toned skin",
    # 服制 / 服装
    "红衣": "red robe", "白色长裙": "white long dress", "长裙": "long dress",
    "玄色紧身劲装": "black tight-fitting martial outfit", "黑色劲装": "black martial outfit",
    "劲装": "martial outfit", "束腰": "cinched waist", "夜行装": "night-raid outfit",
    "常服": "everyday clothes", "披风": "cape", "斗篷": "cloak",
    "腰间缠着黑布": "black cloth wrapped around the waist", "缠黑布": "wrapped in black cloth",
    # 武器 / 道具
    "长剑": "longsword", "青铜剑": "bronze sword", "三尺青铜古剑": "three-chi ancient bronze sword",
    "剑身有暗红纹路": "dark red vein patterns on the blade", "剑柄缠黑布": "black cloth-wrapped hilt",
    "玉牌": "jade tablet", "铜灯": "bronze lamp",
    # 场景
    "荒废古庙": "abandoned ancient temple", "古庙": "ancient temple", "破庙": "ruined temple",
    "断壁残垣": "crumbling walls and broken beams", "月光从破洞洒下": "moonlight falling through a hole in the roof",
    "尘埃漂浮": "floating dust motes", "客栈": "inn", "街道": "street",
}


def 加译补(表):
    """往补译表里加词（{'中文': 'english'}）。返回新增条数。"""
    n = 0
    for k, v in dict(表 or {}).items():
        k, v = str(k).strip(), str(v).strip()
        if k and v and 译补.get(k) != v:
            译补[k] = v
            n += 1
    return n


_译补键缓存 = []


def _补译(s, 命中=None):
    """
    在**中文原文**上做短语替换（这正是 角色库._译 做不到的那一步）：
    把 译补 里命中的中文短语换成英文，避免它们被 _译 当缺词丢掉。
    返回 (替换后的串, 本次命中的中文键列表)。
    """
    global _译补键缓存
    s = str(s or "")
    if not s:
        return s, []
    if not _译补键缓存 or len(_译补键缓存) != len(译补):
        _译补键缓存 = sorted(译补, key=len, reverse=True)
    命中 = []
    for k in _译补键缓存:
        if k and k in s:
            # 两侧垫空格：中文短语之间没有分隔符（「紫色杏眼」）时，
            # 直接换成英文会黏成 "purplealmond-shaped"，垫空格再归一化即可分开。
            s = s.replace(k, " " + 译补[k] + " ")
            命中.append(k)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\s+([,，、;；])", r"\1", s)
    return s, 命中


def 译描述细(描述, 分隔=", ", 补词=""):
    """
    和 译描述 同一套逻辑，但额外把「被 译补 表救回来的词」也报出来。
    返回 (英文串, 未命中列表, 补译命中列表)
    """
    s = str(描述 or "").strip()
    if not s:
        return (补词 or "").strip(), [], []
    补前, 补中 = _补译(s)
    果 = 译描述(补前, 分隔=分隔, 补词=补词)
    # 补译后原本被判缺词的短语已经变成英文，把它们从「未命中」里剔除
    未中 = [w for w in 果[1] if w not in 补中]
    return 果[0], 未中, 补中


def 译描述(描述, 分隔=", ", 补词=""):
    """
    中文描述 → 英文短语。优先直接复用 角色库.py 的 `_译()`（它的分词最懂自己的词典，
    包括「银白长发披肩」这种整词优先命中）；拿不到就退回本模块自己的最长词匹配。

    角色库._译 的脾气是**翻不出来的中文直接丢掉并报警** —— 这里把它的报警接住，
    改成本函数返回的「未命中」列表，绝不静默丢词。
    返回 (英文串, 未命中列表)
    """
    s = str(描述 or "").strip()
    if not s:
        return (补词 or "").strip(), []

    if _角色库 is not None and hasattr(_角色库, "_译"):
        讯 = []
        try:
            果 = _角色库._译(s, 讯.append)
        except Exception:
            果, 讯 = None, []
        if isinstance(果, str):
            未中 = []
            for m in 讯:
                报 = m.split("\u3000→")[0].strip()          # 砍掉「→ 补词：…」尾巴
                if "没译出：" not in 报:
                    continue
                体 = 报.split("没译出：", 1)[1]
                for 段 in 体.split("；"):
                    段 = 段.strip()
                    if not 段:
                        continue
                    没译 = ""
                    if "（" in 段 and 段.endswith("）"):
                        原 = 段.split("（", 1)[0].strip()
                        没译 = 段.split("（", 1)[1][:-1].replace("没译出：", "").strip()
                        没译 = 没译 or 原
                    else:
                        没译 = 段
                    if 没译:
                        未中.append(没译.strip("）) 　"))
            if 补词:
                果 = 分隔.join(x for x in (果, str(补词).strip()) if x)
            return 果, 未中

    # 兜底：本模块自己的分词
    段们 = [x.strip() for x in re.split(r"[,，、;；。\n]+", s) if x.strip()]
    出, 未中 = [], []
    for 段 in 段们:
        e, 中 = 译(段)
        if not 中:
            未中.append(段)
        出.append(e)
    if 补词:
        出.append(str(补词).strip())
    return 分隔.join(x for x in 出 if x), 未中


def 标签串(素材, 语言="英文"):
    """素材的标签拼成串（英文用 角色库 词典翻，翻不动就留原样）。"""
    ts = 素材.get("标签", []) or []
    if not ts:
        return ""
    if 语言 == "中文":
        return "、".join(map(str, ts))
    return " ".join(译(str(t))[0] for t in ts)


def 风格提示词(风格键="", 兜底=风格兜底):
    """从 风格库.py 取风格段（只读）。取不到就用兜底串。"""
    if 风格键 and _风格库 is not None:
        try:
            s = _风格库.取(风格键)
        except Exception:
            s = None
        if s:
            段 = [s.get("风格", ""), s.get("画质", ""), s.get("镜头", ""), s.get("光线", "")]
            t = ", ".join(x for x in 段 if x)
            if t:
                return t
    return 兜底


# ============================================================
# ★核心：参考图编号 + 注入
# ============================================================
def _条目字段(v):
    """把一条素材摊平成注入要用的字段。"""
    类 = v.get("类别", "other")
    中 = 类别表.get(类, {"中文": "其他"})["中文"]
    # 素材名也过一遍词典：角色名通常翻不动（人名），但「夜行装」这类能翻出来
    英名 = str(v.get("英文名", "") or "").strip()
    if not 英名:
        英名 = 译(v.get("名", ""))[0]
    if v.get("英文描述"):
        英 = v["英文描述"]
        未中, 补中 = [], []
    else:
        # 走「细」版：它会先用本模块的 译补 短语表捞一遍 角色库 词典漏掉的中文
        英, 未中, 补中 = 译描述细(v.get("描述", ""))
    if 类 == "costume" and v.get("关联角色"):
        母 = str(v["关联角色"]).strip()
        母英 = 译(母)[0] or 母
        英 = (f"worn by {母英}" + (f" ({英})" if 英 else "")).strip()
        # 「母角色」能给服装当一致性锚点时，就标注出来（照飞彩「服装以母角色定妆图为锚」的思路）
        try:
            if hasattr(_角色库, "定妆照路径"):
                p = _角色库.定妆照路径(母)
                if p and os.path.isfile(p):
                    英 += f" [anchor: {母英} character sheet]"
        except Exception:
            pass
    return {
        "id": v.get("id"),
        "名": v.get("名", ""),
        "英文名": 英名,
        "类别": 类,
        "类别中文": 中,
        "英文": 英,
        "未命中": 未中,
        "补译命中": 补中,
        "有图": bool(v.get("参考图")) and os.path.isfile(v["参考图"]) if v.get("参考图") else False,
        "原图": v.get("参考图", ""),
        "参考图": v.get("参考图", ""),
    }


def 编号(素材名列表, 严格=False):
    """
    ★把素材名列表摊成带 @编号 的参考图序列。

    排序：角色 → 场景 → 道具 → 服装 → 其他（同类别内按传入顺序，稳定去重）。
    返回 [{"n":1,"at":"@1","名":…,"类别":…,"类别中文":…,"英文":…,"有图":bool,"参考图":路径,"未命中":[…], "标签行":英文标签}]
    严格=True 时，没参考图的素材直接报错（照飞彩 "ENTITY_UNAVAILABLE" 的口径）。
    """
    d = 载入()
    vs = []
    for 名 in (素材名列表 or []):
        if 名 is None or str(名).strip() == "":
            continue
        v = 查(名)
        if v is None:
            raise KeyError(f"素材库里没有：{名}")
        if v.get("启用", True) is False:
            continue
        if any(x["id"] == v["id"] for x in vs):
            continue          # 稳定去重
        vs.append(v)
    vs = sorted(vs, key=lambda v: 顺序权重.get(v.get("类别"), 5))   # 稳定排序，保内部次序

    出, n = [], 0
    for v in vs:
        it = _条目字段(v)
        if not it["有图"]:
            if 严格:
                raise ValueError(f"该实体还没有参考图，不能选入绑定：{it['名']}（id={it['id']}）")
            continue
        n += 1
        it["n"] = n
        it["at"] = f"@{n}"
        it["标签行"] = f"参考图{n} {图标签.get(it['类别'], 图标签['other'])}"
        出.append(it)
    return 出


def 编号表(素材名列表, 严格=False):
    """只要 {名字: '@n'} 的映射。"""
    return {it["名"]: it["at"] for it in 编号(素材名列表, 严格=严格)}


def 图数组(素材名列表, 严格=False):
    """
    按编号顺序返回参考图路径列表 —— 这就是喂给图像模型的图片顺序。
    zip(图数组(...), wait, 提示词里的 @1 @2 …) 必须一一对应，错位会导致 AI 认错角色。
    """
    return [it["参考图"] for it in 编号(素材名列表, 严格=严格)]


def 参考块(素材名列表, 底图="", 底图说明="", 风格参考图="", 严格=False):
    """
    组装参考图编号块（不含提示词正文）。返回 dict：
        {
          "块": "参考图序号对应：…\\n[2 REFERENCE IMAGES ATTACHED: …]",
          "对应表": "参考图1是【角色：X，用于保持画面连续性】；参考图2是【场景：Y】",
          "编号": [ ...编号()... ],
          "图数组": [路径…],
          "摘要": "Characters: X | Scenes: Y",
          "张数": int,
          "未命中": {素材名: [没翻出来的中文词…]},
          "警告": [ ... ]
        }
    """
    警告 = []
    序 = []
    if 底图:
        if not os.path.isfile(底图):
            raise FileNotFoundError(f"底图不存在：{底图}")
        序.append({"参考图": os.path.abspath(底图), "类别": "base", "名": "底图",
                   "别称": 底图说明 or "底图"})
    本体 = 编号(素材名列表, 严格=严格)
    序.extend(本体)
    if 风格参考图:
        if not os.path.isfile(风格参考图):
            raise FileNotFoundError(f"风格参考图不存在：{风格参考图}")
        序.append({"参考图": os.path.abspath(风格参考图), "类别": "style", "名": "风格参考图",
                   "别称": "风格参考图"})

    对应, 摘要, 未命中 = [], [], {}
    for i, it in enumerate(序, 1):
        类 = it["类别"]
        名 = it.get("名", "")
        if 类 == "style":
            对应.append(f"参考图{i}是【🎨 风格参考图】")
            continue
        if 类 == "base":
            对应.append(f"参考图{i}是【{it.get('别称') or '底图'}】")
            continue
        中文 = it["类别中文"]
        if it.get("未命中"):
            未命中[名] = it["未命中"]
        尾 = "，用于保持画面连续性" if 类 == "character" else ""
        显示 = it.get("英文名") or 名
        if 显示 != 名:
            显示 = f"{名}（{显示}）"
        对应.append(f"参考图{i}是【{中文}：{显示}{尾}】")
        摘要.append((类, it.get("英文名") or 名))

    def _汇总(类, 英文名):
        们 = [n for c, n in 摘要 if c == 类]
        return f"{英文名}: {', '.join(们)}" if 们 else ""

    摘要串 = " | ".join(x for x in [
        (f"Base frame ×1 ({底图说明})" if 底图 else ""),
        _汇总("character", "Characters"),
        _汇总("scene", "Scenes"),
        _汇总("prop", "Props"),
        _汇总("costume", "Costumes"),
        ("Style reference ×1 (🎨 art style)" if 风格参考图 else ""),
    ] if x)

    if not 序:
        return {"块": "", "对应表": "", "编号": [], "图数组": [], "摘要": "", "张数": 0,
                "未命中": {}, "警告": ["没有参考图，将不带参考继续生成"]}

    块 = "\n".join([
        抬头.format(对应表="；".join(对应)),
        外部表头.format(张数=len(序), 摘要=摘要串 or "见下"),
    ])
    return {
        "块": 块,
        "对应表": "；".join(对应),
        "编号": 本体,
        "图数组": [x["参考图"] for x in 序],
        "摘要": 摘要串,
        "张数": len(序),
        "未命中": 未命中,
        "警告": 警告,
    }


def 注入(提示词, 素材名列表, *, 底图="", 底图说明="", 风格参考图="", 风格键="",
       时代设定="", 严格=False, 带主指令=True, 零文字=True, 风格兜底串=None, 只回文本=True):
    """
    ★核心：把素材注入提示词，产出可以直接喂给图像模型的完整生图提示词。

    提示词      原始分镜提示词正文（中文/英文都行；里面可以用 @1 @2 自己引用参考图）
    素材名列表  这格要挂哪些素材（名字 / id / 别名都认）
    底图        垫图 / 尾帧（会占据 @1，其余参考图顺延）
    底图说明    例如 "尾帧" / "首帧" / "上一格画面"
    风格参考图  风格参考图路径（排在最后一张）
    风格键      影匠 风格库.py 里的风格键；给了就抽它的风格/画质/镜头/光线段
    时代设定    例如 "盛唐长安" —— 会插一段世界观一致性约束
    严格        True 时，没有参考图的素材直接报错，不再静默跳过
    带主指令    是否插入 "Use the reference images as the primary subject…"
    零文字      是否追加零文字铁律
    风格兜底串  覆盖默认兜底风格词（None 用 风格兜底）

    返回 (完整提示词, 参考块dict)。只回文本串请用 注入文本()。
    """
    块 = 参考块(素材名列表, 底图=底图, 底图说明=底图说明, 风格参考图=风格参考图, 严格=严格)
    正文 = str(提示词 or "").strip()
    段 = []

    if 块["张数"]:
        段.append(块["块"])
    else:
        段.append("参考图序号对应：无（本次不带参考图）")

    if 带主指令:
        段.append(主指令)
    if 时代设定:
        段.append(环境带入.format(设定=str(时代设定).strip()))
    if 零文字:
        段.append(零文字铁律)

    风 = 风格提示词(风格键, 兜底=(风格兜底串 if 风格兜底串 is not None else 风格兜底))
    段.append(f"风格: {风}")

    if 正文:
        段.append(正文)

    全文 = "\n\n".join(x for x in 段 if x)
    if 只回文本:
        return 全文, 块
    return {"提示词": 全文, "参考块": 块, "图数组": 块["图数组"], "编号": 块["编号"],
            "未命中": 块["未命中"], "张数": 块["张数"]}


def 注入文本(提示词, 素材名列表, **kw):
    """只要完整提示词字符串。"""
    kw["只回文本"] = True
    return 注入(提示词, 素材名列表, **kw)[0]


def 写md(路径, 素材名列表, **kw):
    """把一次注入的结果写成可读的 md（方便人工核对编号与图片顺序）。"""
    完整, 块 = 注入(素材名列表=素材名列表, 提示词=kw.pop("提示词", ""), 只回文本=True, **kw)
    行 = ["# 参考图编号对照", "", f"- 生成时间：{_现在()}", f"- 参考图张数：{块['张数']}",
          f"- 摘要：{块['摘要'] or '（无）'}", ""]
    if 块["未命中"]:
        行 += ["## 未翻出的中文词", ""]
        for k, v in 块["未命中"].items():
            行.append(f"- {k}：{'、'.join(v)}")
        行.append("")
    行 += ["## 编号 ↔ 图片", "", "| @ | 类别 | 名字 | 图片 |", "| --- | --- | --- | --- |"]
    for i, p in enumerate(块["图数组"], 1):
        it = next((x for x in 块["编号"] if x["n"] == i), None)
        行.append(f"| @{i} | {it['类别中文'] if it else '底图/风格'} | {it['名'] if it else ''} | `{p}` |")
    行 += ["", "## 完整提示词", "", "```", 完整, "```", ""]
    with open(路径, "w", encoding="utf-8") as f:
        f.write("\n".join(行))
    return 路径


# ============================================================
# 服装 / 场景匹配（标签打分，不调模型）
# ============================================================
def 场景标签(文本):
    """
    从一段文本（场景描述 / 分镜提示词）里抽出可当标签的词。
    规则：中文按 2~4 字切 + 顿号/逗号分段；英文按单词。够用即可。
    """
    t = str(文本 or "")
    出 = []
    for 段 in re.split(r"[,，、;；。\s/|]+", t):
        段 = 段.strip()
        if not 段:
            continue
        if re.search(r"[\u4e00-\u9fff]", 段):
            if len(段) <= 6:
                出.append(段)
            else:
                for L in (4, 3, 2):
                    for i in range(len(段) - L + 1):
                        出.append(段[i:i + L])
        else:
            if len(段) > 1:
                出.append(段.lower())
    seen = []
    for x in 出:
        if x not in seen:
            seen.append(x)
    return seen


def 服装推荐(场景, 角色名="", 上限=3):
    """
    服装/场景匹配的打分排序（不调模型，纯标签重叠）。

    场景    场景名 或 一段场景描述文本 或 素材名（会自动找场景素材的描述/标签一起打分）
    角色名  给了就优先该角色的服装
    返回 [{"名","id","分","命中","来源"}] 按分倒序
    """
    词 = set()
    for x in 场景标签(场景):
        词.add(x.lower())
    sv = 查(场景)
    if sv is not None:
        for x in 场景标签(sv.get("描述", "")) + [str(t) for t in sv.get("标签", []) or []]:
            词.add(x.lower())
    词.discard("")

    出 = []
    for v in 查找(类别="costume"):
        if 角色名 and str(v.get("关联角色", "")).strip() not in ("", str(角色名).strip()):
            continue
        池 = [str(t) for t in v.get("标签", []) or []]
        池 += 场景标签(v.get("名", "")) + 场景标签(v.get("描述", ""))
        池l = {x.lower() for x in 池 if x}
        命中 = sorted(词 & 池l)
        分 = 0.0
        分 += 2.0 * len(命中)
        if 角色名 and str(v.get("关联角色", "")).strip() == str(角色名).strip():
            分 += 3.0
        if v.get("参考图"):
            分 += 1.0
        出.append({"名": v["名"], "id": v["id"], "分": round(分, 2), "命中": 命中,
                   "来源": "标签重叠" if 命中 else "无重叠", "关联角色": v.get("关联角色", "")})
    出.sort(key=lambda d: (-d["分"], d["名"]))
    return 出[:上限] if 上限 else 出


def 服装建(角色名, 造型名, 描述="", 标签=None, 参考图=""):
    """
    给某角色加一套服装造型。名 = 「角色 · 造型」。
    标签里建议写上适用场景名（服装推荐 会用）。
    """
    名 = f"{str(角色名).strip()} · {str(造型名).strip()}"
    return 建(名, 类别="costume", 描述=描述, 标签=标签, 关联角色=str(角色名).strip(),
              参考图=参考图)


# ============================================================
# 自测
# ============================================================
def 自测(重置=True, 图目录源=None):
    """
    造一批素材 → 绑定 → 注入 → 打印。默认重建一个干净的测试库。
    图目录源：可选，指向一个装着现成 png 的目录，用真图测试；不给就现造纯色 png。
    """
    印 = print
    印("=" * 78)
    印(f"角色库.py 可用={_角色库 is not None} {_角色库错}")
    印(f"风格库.py 可用={_风格库 is not None} {_风格库错}")
    印(f"角色库 词典词数={len(_角色词典()[0])}")
    if 重置:
        清空(真删图片=True)
        # 自检：清空后磁盘必须真的是空库，否则后面的 建() 会报「素材名已存在」
        try:
            with open(库文件, "r", encoding="utf-8") as _f:
                _n = len(json.load(_f).get("素材") or {})
        except Exception as _e:
            _n = f"读盘失败 {_e}"
        if _n != 0:
            印(f"⚠ 清空后磁盘仍是 {_n} 条 —— 测试库不干净，先手工删除 {库文件} 再跑")

    def 造图(名, 色):
        from PIL import Image
        _确保目录()
        if 图目录源 and os.path.isdir(图目录源):
            for f in sorted(os.listdir(图目录源)):
                if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp"):
                    return os.path.join(图目录源, f)
        p = os.path.join(图目录, f"_自测_{_slug(名)}.png")
        Image.new("RGB", (256, 256), 色).save(p)
        return p

    印("=" * 78)
    印("【1】建素材")
    建("叶云", "character", "男，青年，黑长直，红衣，长剑",
       英文名="Ye Yun", 标签=["男主", "剑客"])
    建("苏晚", "character", "女，少年，银白长发披肩，紫色杏眼，冷白皮，白色长裙",
       英文名="Su Wan", 标签=["女主", "药师"])
    建("破庙", "scene", "荒废古庙，断壁残垣，月光从破洞洒下，尘埃漂浮",
       英文名="Ruined Temple", 标签=["夜", "室外"])
    建("青铜剑", "prop", "三尺青铜古剑，剑身有暗红纹路，剑柄缠黑布",
       英文名="Bronze Sword", 标签=["兵器"])
    服装建("叶云", "夜行装", "黑色劲装，束腰，披风", 标签=["破庙", "夜", "潜行"])
    服装建("叶云", "常服", "素白长衫，青色腰带", 标签=["客栈", "白天"])
    for n, c in (("叶云", (200, 40, 40)), ("苏晚", (240, 240, 240)),
                 ("破庙", (30, 40, 60)), ("青铜剑", (140, 120, 60)),
                 ("叶云 · 夜行装", (25, 25, 25))):
        try:
            绑定(n, 造图(n, c))
        except Exception as e:
            印(f"  !! 绑定失败 {n}: {e}")
    印(f"  统计: {统计()}")
    for r in 列出():
        印(f"  {r}")

    印("")
    印("【2】编号（排序 + 去重 + 无图跳过）")
    for it in 编号(["青铜剑", "叶云", "破庙", "叶云", "叶云 · 夜行装"]):
        印(f"  {it['at']:<3} {it['类别中文']}  {it['名']:<12} 图={os.path.basename(it['参考图'])}")
    印(f"  编号表: {编号表(['叶云', '破庙', '青铜剑'])}")
    印(f"  图数组: {[os.path.basename(p) for p in 图数组(['叶云', '破庙'])]}")

    印("")
    印("【3】译描述（角色库.py 99 词词典 + 本模块 译补 短语表）")
    for 名 in ("叶云", "苏晚", "破庙", "青铜剑"):
        v = 查(名)
        e, 未, 补 = 译描述细(v["描述"])
        印(f"  {名:<6} → {e}")
        if 补:
            印(f"         译补救回: {补}")
        if 未:
            印(f"         仍缺词（未进提示词，可用 加译补() 补）: {未}")

    印("")
    印("【4】★注入")
    完整, 块 = 注入(
        "破庙内，叶云握紧青铜剑，缓步走向神像，月光打在侧脸，冷色调，中景，镜头缓慢推近",
        ["破庙", "叶云", "青铜剑", "叶云 · 夜行装"],
        时代设定="架空军武·架空王朝",
    )
    印(完整)
    印("")
    印(f"  张数={块['张数']}  图数组={[os.path.basename(p) for p in 块['图数组']]}")
    印(f"  未命中={块['未命中']}")

    印("")
    印("【5】无参考图 → 严格模式应报错")
    try:
        编号(["幽灵角色"], 严格=True)
    except KeyError as e:
        印(f"  按预期报错: {e}")

    印("")
    印("【6】服装推荐")
    for 场景 in ("破庙", "客栈白天"):
        印(f"  {场景} →")
        for r in 服装推荐(场景, 角色名="叶云"):
            印(f"      {r['分']:>5}  {r['名']}  命中={r['命中']}")

    印("")
    印("【7】落盘检查")
    印(f"  库文件: {库文件}  存在={os.path.exists(库文件)}  大小={os.path.getsize(库文件) if os.path.exists(库文件) else 0}B")
    印(f"  图目录: {图目录}  文件数={len(os.listdir(图目录)) if os.path.isdir(图目录) else 0}")
    印(f"  角色库.py 可用={_角色库 is not None} {_角色库错}")
    印(f"  风格库.py 可用={_风格库 is not None} {_风格库错}")
    印("=" * 78)
    return 统计()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    自测()
