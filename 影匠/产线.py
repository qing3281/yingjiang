# -*- coding: utf-8 -*-
"""产线库 —— 把 ComfyUI 官方那 614 个现成工作流，变成影匠能用的「产线」。

★ 这是用户 2026-10-15 亲自纠正的方向：
     「想要的是这种，而不是一步步慢慢迁移扩充，最后自己做出来个 comfyui」
     「调用后能生成规范工作流，但也能在 comfyui 里面进一步优化」

★ 所以这个文件干三件事，一件都不多：
     1. 扫        读官方模板目录，认出每个是干什么的（分类 + 中文名）
     2. 拿        把一个产线读出来，改掉里面的参数（提示词 / 图 / 帧数 / 模型）
     3. 交        写成 ComfyUI 认的 UI 格式，**塞进 ComfyUI 自己的工作流列表**
                  （POST /api/userdata/workflows%2F<名>.json，实测 HTTP 200）

★ 为什么必须是 UI 格式（顶层 nodes/links/groups）而不是 API 格式（{节点号: {...}}）：
     官方那 614 个全是 UI 格式 —— 拖进 ComfyUI 能打开、能改、能另存。
     影匠以前手抄的那几个是 API 格式 —— **拖进 ComfyUI 打不开**。
     用户要的「在 ComfyUI 里进一步优化」这一步，以前根本提供不了。
     所以：**影匠不再自己存模板**，模板永远是官方的，官方更新影匠跟着更新。

只读调用，不改 ComfyUI 那边任何文件（写工作流列表是他自己点的，属于我们要交的东西）。
"""

from __future__ import annotations

import glob
import json
import os
import re
import urllib.parse
import urllib.request

# ───────────────────────── 官方模板库在哪 ─────────────────────────

def _找模板库() -> str:
    """返回官方模板目录。找不到返回空串。

    ★ 为什么要找而不是写死：ComfyUI 有桌面版、便携版、venv 版，
      路径三种都不一样，写死一个就会在换机器时静默失效（不报错，只是永远扫出 0 个）。
    """
    候选 = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "_ComfyUI模板库"),
    ]
    try:
        import comfyui_workflow_templates_json as 包   # noqa: F401
        for p in list(getattr(包, "__path__", [])):
            候选.append(os.path.join(p, "templates"))
    except Exception:
        pass
    # 兜底：按已知的几处 site-packages 扫一遍
    for 根 in (r"D:\Comfy-Desktop", r"D:\ComfyUI", r"C:\ComfyUI", r"E:\ComfyUI"):
        if os.path.isdir(根):
            候选 += glob.glob(os.path.join(根, "**", "comfyui_workflow_templates_json",
                                           "templates"), recursive=True)
    for c in 候选:
        if c and os.path.isdir(c) and glob.glob(os.path.join(c, "*.json")):
            return c
    return ""


模板库 = _找模板库()


# ───────────────────────── 分类 ─────────────────────────
# ★ 判据是「用户拿它干什么」，不是「文件名前缀」。
#   前缀是给机器分的（video_/image_/api_/utility_），用户看不懂。

分类表 = [
    # (类名, 顺序, 命中规则：文件名里含任意一个词就归这类)
    ("出片 · 图生视频", 10, ["i2v", "image_to_video"]),
    ("出片 · 文生视频", 11, ["t2v", "text_to_video"]),
    ("出片 · 首尾帧", 12, ["flf2v", "first_last"]),
    ("出片 · 续写", 13, ["continuation", "extend"]),
    ("★ 视频重画（拿现成视频改）", 20, ["v2v", "vid2vid", "video_to_video", "vace_14b_v2v"]),
    # ★ 动作迁移的判据必须够窄：一开始写了 "ati"，结果把 "infl-ati-on"、"estim-ati-on"
    #   全吸进来了（marigold 的 depth/albedo estimation 跑到了动作迁移里）。
    #   教训：短的英文子串当关键词，一定会误伤 —— 要么加边界，要么用全词。
    ("★ 动作迁移", 21, ["animate2", "wan_ati", "_ati_", "wan_dancer", "wanmove",
                        "motion_control", "_motion", "sdpose", "pose_map",
                        "video_to_pose", "dance"]),
    ("★ 换人 / 换脸", 22, ["swap", "character_replacement", "faceswap", "face_swap",
                          "faceid", "instantid", "photomaker"]),
    ("★ 对口型 / 说话", 23, ["talk", "lipsync", "lip_sync", "s2v", "speech"]),
    ("★ 参考图锁形象", 24, ["r2v", "ref2v", "reference", "multiframe"]),
    ("控制（姿势/深度/边缘）", 30, ["control", "controlnet", "depth", "canny", "union"]),
    ("视频修补 / 扩画布", 31, ["inpaint", "outpaint", "patch"]),
    ("超分 / 放大", 40, ["upscal", "seedvr", "topaz", "esrgan", "gan"]),
    ("补帧 / 变顺", 41, ["interpolation", "frame_interp"]),
    ("出图 · 文生图", 50, ["t2i", "text_to_image", "z_image", "flux", "qwen_image", "sd3", "sdxl"]),
    ("出图 · 改图 / 局部重画", 51, ["image_edit", "edit", "recompos", "relight"]),
    ("配乐 / 声音", 60, ["audio", "music", "ace_step", "tts", "voice", "yue2"]),
    ("3D 模型", 70, ["3d", "hunyuan3d", "model2uv", "retopo"]),
    ("文字 / 大模型", 80, ["llm", "text"]),
]

看不懂的类 = ("其它（官方杂项）", 900)


def 归类(名: str) -> tuple[str, int]:
    """按「用户拿它干什么」归类。

    ★ 关键词一律按**词边界**匹配，不做子串匹配。
      踩过两次（都是静默的，只是分错类，不报错）：
        · "ati"   → 把 "infl-ati-on" / "estim-ati-on" 全吸进「动作迁移」
        · "dance" → 把 "see-dance"（Seedance 模型名）也吸进去
        · "face"  → 把 "sur-face"（marigold 法线估计）吸进去
      教训：短的英文子串当关键词，一定会误伤。要么加边界，要么用带前缀的全词。
    """
    n = 名.lower()
    for 类, 序, 词表 in 分类表:
        for w in 词表:
            if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", n):
                return 类, 序
    return 看不懂的类


# ───────────────────────── 扫 ─────────────────────────

def 全部(重新扫: bool = False) -> list[dict]:
    """列出所有产线。每条形如：
       {键, 名, 类, 序, 路, 大小, 节点数, 要什么图, 要什么模型, 从这儿来的}

    「要什么图」是从工作流里数出来的（LoadImage / VHS_LoadVideo 这些节点的个数），
    不是猜的 —— 猜的话用户按了才发现少张图。
    """
    if not 模板库:
        return []
    out = []
    # ★ 权威的「云端节点」名单来自 ComfyUI 自己（`/object_info` 的 `api_node`）。
    #   拿不到就退回前缀表 —— 但**要显式说一句**，不能静默降级成猜的。
    try:
        表 = 节点表()
    except Exception as e:                                     # noqa: BLE001
        表 = None
        print("  ⚠ 拿不到 /object_info（%s）—— 云端与否只能用前缀表猜，可能判错" % e)
    for p in sorted(glob.glob(os.path.join(模板库, "*.json"))):
        键 = os.path.splitext(os.path.basename(p))[0]
        类, 序 = 归类(键)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        节 = d.get("nodes") if isinstance(d, dict) else None
        if not isinstance(节, list):
            # ★ 不是工作流就**跳过**，不要放一条空壳进列表。
            #   实测官方库里有 13 个 `index*.json`（是模板目录的清单，一个 list，
            #   里面装的是分类和模板名），放进来会变成「点开什么都没有」的假产线。
            continue
        类名 = [str(x.get("type", "")) for x in 节 if isinstance(x, dict)]
        # ★★ 2026-10-15 补：**子图里面的节点也要数**。
        #   实测漏过两条：`template contact sheet-step 3.` 和 `templates graphic design recom`
        #   —— 顶层看着全是本机节点，云端那个（Kling / Nano Banana）**藏在 `definitions.subgraphs`
        #   的子图里**，只扫顶层就漏了，交过去报 `seed, kling-v3, invalid literal for int()`。
        for _sg in ((d.get("definitions") or {}).get("subgraphs") or []):
            if isinstance(_sg, dict):
                类名 += [str(x.get("type", "")) for x in (_sg.get("nodes") or [])
                        if isinstance(x, dict)]
        要图 = sum(1 for t in 类名 if t in ("LoadImage", "LoadImageMask", "LoadImageOutput"))
        要视频 = sum(1 for t in 类名 if "LoadVideo" in t or t in ("VHS_LoadVideo", "LoadVideoPath"))
        # ★ 要填几个提示词框：从工作流里数**文本编码节点**，不是猜的。
        #   用户按了才发现少一个框，跟少一张图是一回事。
        要字 = sum(1 for t in 类名 if "TextEncode" in t
                   or t in ("StringLiteral", "Text Multiline", "PrimitiveStringMultiline"))
        模型 = sorted({t for t in 类名 if t.endswith("Loader") or "Checkpoint" in t or "UNET" in t
                       or t in ("LoraLoaderModelOnly", "VAELoader", "CLIPLoader")})
        # ★ api_ 开头的是「调云端接口」，本机跑不了（要 API key、要花钱）。
        #   以前它们跟本地产线混在一个列表里，用户点进去才发现跑不动 —— 必须分开标出来。
        #
        # ★★ 2026-10-15 补：**光看文件名会漏**。实测 `template_contact_sheet-step_1.app`
        #   和 `template product placement` 这两个名字里一个 api 都没有，里面装的却是
        #   `GeminiImage2Node`（要 Google 的 key，要花钱）。把它们当本地产线交过去，
        #   报的是 `seed, Nano Banana 2 (Gemini 3.1 Flash Image), invalid literal for int()`
        #   —— 看着像我的转换器坏了，其实是「这条本来就不是本机能跑的」。
        #   判据改成：**文件名 或 里面任意一个节点类型** 命中云端厂商名单，就算云端。
        #   名单是拿 664 种节点类型数出来的（不是拍脑袋列的）。
        要云端 = 键.startswith("api_") or any(_是云端节点(t, 表) for t in 类名)
        out.append({
            "键": 键, "名": _中文名(键), "类": 类, "序": 序, "路": p,
            "大小": os.path.getsize(p), "节点数": len(节),
            "要图": 要图, "要视频": 要视频, "要字": 要字,
            "要模型": 模型, "要云端": 要云端,
            "从这儿来的": "ComfyUI 官方模板库",
        })
    # ★ 排序：先按类；同一类里**本机能跑的排前面**，云端 API 沉底。
    #   不然点开一列全是 api_grok / api_kling，一个都跑不了。
    out.sort(key=lambda x: (x["序"], x["要云端"], x["键"]))
    return out


def 本机能跑(条: list[dict] | None = None) -> list[dict]:
    """只留不需要云端 API key 的。"""
    return [x for x in (条 if 条 is not None else 全部()) if not x["要云端"]]


# ★ 云端厂商的节点类名前缀 —— **这只是一个「拿不到权威名单时」的兜底**。
#   权威判据是 ComfyUI 自己给的：`GET /object_info` 里每个节点有 `api_node: true/false`，
#   本机实测 **286 个**节点是 true（ClaudeNode / FluxProUltraImageNode / Bria* / Gemini* /
#   Kling* / Recraft* / Luma* / Grok* / MinimaxHailuo* …），本机的 `MiniMaxH3ImageToVideo`
#   是 **false** —— 这就是我们要的那条线。
#   ★ 前缀表踩过的坑：`MiniMaxH3*`（本机）和 `MinimaxHailuo*`（云端海螺）差几个字母；
#     而且 Bria / kling / seedream / Nano Banana 这些**光看名字想不全**，
#     实测漏了 4 条。所以能用 `api_node` 就一定用 `api_node`。
_云端前缀 = (
    "Gemini", "Grok", "Recraft", "Luma", "Kling", "MinimaxHailuo", "Runway",
    "Ideogram", "Seedance", "Veo", "Sora", "Pika", "FluxAPI", "NanoBanana",
    "OpenAIGPT", "DallE", "StabilityAPI", "WanAPI", "QwenAPI", "Bria", "Flux",
    "Claude", "Beeble",
)


def _是云端节点(类名: str, 表: dict | None = None) -> bool:
    """这个节点类型是不是「调别人家接口、要 key、要花钱」。

    ★ 优先问 ComfyUI 自己（`api_node`），问不到才退回前缀表。
    """
    if not 类名:
        return False
    if 表:
        d = 表.get(类名)
        if isinstance(d, dict) and d.get("api_node") is not None:
            return bool(d.get("api_node"))
    return 类名.startswith(_云端前缀)



_已知中文 = {
    "video_minimax_h3_i2v": "MiniMax-H3 图生视频（自带声音）",
    "video_minimax_h3_t2v": "MiniMax-H3 文生视频（自带声音）",
    "video_minimax_h3_r2v": "MiniMax-H3 参考图锁形象",
    "video_minimax_h3_flf2v": "MiniMax-H3 首尾帧",
    "video_minimax_h3_i2v_continuation": "MiniMax-H3 接着上一段往下续",
    "video_minimax_h3_multiframe_reference": "MiniMax-H3 多帧参考",
    "video_minimax_h3_fun_controlnet_union": "MiniMax-H3 控制网（姿势/深度/边缘）",
    "video_wan_vace_14B_v2v": "拿现成视频直接重画（Wan VACE 14B）",
    "video_wan_vace_14B_ref2v": "参考图转视频（Wan VACE）",
    "video_wan_vace_flf2v": "首尾帧（Wan VACE）",
    "video_wan_vace_inpainting": "视频局部重画（去杂物）",
    "video_wan_vace_outpainting": "视频扩画布",
    "video_wan_animate2": "动作迁移：一段动作套到你的角色身上",
    "video_wan_animate2_distilled": "动作迁移（加速版）",
    "video_wan_ati": "动作迁移（ATI）",
    "video_wan_dancer": "跳舞",
    "video_wanmove_480p": "动作控制（WanMove 480p）",
    "video_wan21_scail2_character_replacement": "换人：把视频里的人换成你的角色",
    "video_wan21_scail2_character_replacement_int8": "换人（int8 省显存）",
    "video_wan2_1_infinitetalk": "对口型（InfiniteTalk）",
    "video_wan2_2_14B_s2v": "声音驱动视频（S2V）",
    "video_wan2_2_14B_flf2v": "首尾帧（Wan 2.2 14B）",
    "video_wan2_2_14B_i2v": "图生视频（Wan 2.2 14B）",
    "video_wan2_2_14B_t2v": "文生视频（Wan 2.2 14B）",
    "video_wan2_2_14B_fun_control": "控制网（Wan 2.2 14B）",
    "video_wan2_2_14B_fun_inpaint": "视频局部重画（Wan 2.2 14B）",
    "video_wan2_2_14B_fun_camera": "运镜控制（Wan 2.2 14B）",
    "utility_sdpose_ood_video_to_pose_map": "从视频里把骨架抽出来",
    "utility_video_frame_interpolation": "补帧（卡顿变顺）",
    "utility_seedvr2_3b_int8_upscale_video": "视频超分（SeedVR2 3B）",
    "utility_seedvr2_7b_int8_upscale_video": "视频超分（SeedVR2 7B，更好也更慢）",
    "utility-gan_upscaler": "图片放大（GAN，快）",
    "audio_minimax_music_3": "配乐（MiniMax Music 3）",
}


def _中文名(键: str) -> str:
    if 键 in _已知中文:
        return _已知中文[键]
    # 没见过就按前缀翻一个能看懂的
    n = 键
    for 前, 中 in (("video_", "出片 · "), ("image_", "出图 · "), ("audio_", "声音 · "),
                   ("utility_", "工具 · "), ("3d_", "3D · "), ("api_", "云端 API · "),
                   ("llm_", "文字 · "), ("basic_", "基础 · ")):
        if n.startswith(前):
            return 中 + n[len(前):].replace("_", " ")
    return n.replace("_", " ")


def 按类(条: list[dict] | None = None) -> dict[str, list[dict]]:
    组: dict[str, list[dict]] = {}
    for x in (条 if 条 is not None else 全部()):
        组.setdefault(x["类"], []).append(x)
    return dict(sorted(组.items(), key=lambda kv: (kv[1][0]["序"] if kv[1] else 999)))


# ───────────────────────── 拿 / 改 / 交 ─────────────────────────

def 拿(键: str) -> dict:
    """按产线键读出原始工作流（UI 格式，原样，不改）。"""
    for x in 全部():
        if x["键"] == 键:
            return json.load(open(x["路"], encoding="utf-8"))
    raise KeyError(f"没有这条产线：{键}")


def 找输入(工作流: dict) -> dict:
    """数出这个工作流要用户给什么：几张图 / 几段视频 / 哪些提示词框。

    ★ 为什么要「找」而不是写死：每个官方工作流的节点号都不一样，
      写死就会在换工作流时把图塞进错的地方（塞错不报错，只是出来是垃圾）。
    """
    图, 视频, 文 = [], [], []
    for n in 工作流.get("nodes", []) or []:
        if not isinstance(n, dict):
            continue
        t = str(n.get("type", ""))
        if t in ("LoadImage", "LoadImageMask", "LoadImageOutput"):
            图.append({"节点": n.get("id"), "现在": (n.get("widgets_values") or [None])[0]})
        elif "LoadVideo" in t:
            视频.append({"节点": n.get("id"), "现在": (n.get("widgets_values") or [None])[0]})
        elif t in ("CLIPTextEncode", "TextEncodeQwenImageEdit", "String Literal",
                   "PrimitiveStringMultiline", "Text Multiline"):
            v = n.get("widgets_values") or [""]
            文.append({"节点": n.get("id"), "现在": str(v[0])[:80] if v else ""})
    return {"图": 图, "视频": 视频, "文字": 文}


def 改成(工作流: dict, 改: dict) -> dict:
    """把参数写进工作流。改 形如 {节点号: 新值} 或 {"提示词": "...", "图": "路径"}。

    ★ 只动 widgets_values —— 不碰 nodes/links 的结构。
      结构一动，ComfyUI 打开时连线就断了（而且是静默断，打开才看得见）。
    """
    for n in 工作流.get("nodes", []) or []:
        if not isinstance(n, dict):
            continue
        号 = n.get("id")
        if 号 in 改:
            w = list(n.get("widgets_values") or [])
            while len(w) < 1:
                w.append(None)
            w[0] = 改[号]
            n["widgets_values"] = w
    if isinstance(改.get("提示词"), str):
        t = str(改["提示词"])
        for n in 工作流.get("nodes", []) or []:
            if isinstance(n, dict) and str(n.get("type")) in ("CLIPTextEncode",):
                n["widgets_values"] = [t]
                break
    return 工作流


def 交给ComfyUI(工作流: dict, 名: str, 机: str = "本机",
               ComfyUI地址: str | None = None) -> dict:
    """把工作流写进 **ComfyUI 自己的工作流列表**。

    用户打开 ComfyUI → 左边侧栏的工作流清单 → 它就在那儿，点开能跑、能改、能另存。

    ★ 实测：`POST /api/userdata/workflows%2F<名>.json` → HTTP 200
      （见 记忆\\经验\\流程与脚本.md）
    """
    基 = ComfyUI地址 or ("http://127.0.0.1:8188" if 机 == "本机"
                        else "http://100.127.224.106:8188")
    路 = "/api/userdata/workflows%2F" + urllib.parse.quote(_安全名(名) + ".json")
    体 = json.dumps(工作流, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(基 + 路, data=体, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return {"ok": r.status in (200, 201, 204), "码": r.status, "名": _安全名(名) + ".json"}


def ComfyUI工作流列表(ComfyUI地址: str = "http://127.0.0.1:8188") -> list[str]:
    """看 ComfyUI 自己的工作流列表里现在有什么。"""
    u = ComfyUI地址 + "/api/userdata?dir=workflows"
    with urllib.request.urlopen(u, timeout=20) as r:
        d = json.loads(r.read().decode("utf-8"))
    return [x if isinstance(x, str) else x.get("path", "") for x in (d or [])]


# ───────────── UI 格式 → API 格式（转得过来才 POST /prompt 得动） ─────────────

_节点表缓存: dict = {}


def 节点表(机: str = "本机", ComfyUI地址: str | None = None) -> dict:
    """拿 ComfyUI 的 `/object_info` —— 每个节点类「有哪些输入、按什么顺序」。

    ★ 为什么必须拉它：UI 格式的 `widgets_values` 是**按位置**存的，
      要把它对回输入名，只能靠节点自己声明的输入表。写死顺序一定错。
    """
    基 = ComfyUI地址 or ("http://127.0.0.1:8188" if 机 == "本机"
                        else "http://100.127.224.106:8188")
    if 基 not in _节点表缓存:
        with urllib.request.urlopen(基 + "/object_info", timeout=60) as r:
            _节点表缓存[基] = json.loads(r.read().decode("utf-8"))
    return _节点表缓存[基]


_可填类型 = ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO")


def 是控件(声明) -> bool:
    """这个输入能不能「填值」（而不是必须接一条线）。

    ★★ 判据不能只看 `forceInput` —— 那是**踩过的坑**：
      很多连线型输入的声明长这样：`"images": ["IMAGE", {"tooltip": "..."}]`，
      没有 `forceInput`，光看它会被当成控件。于是 `SaveImage` 会把
      `widgets_values[0]`（"z-image-turbo"）填给 **images**，
      而真正的 `filename_prefix` 一个值都没拿到 →
      ComfyUI 报 `required_input_missing: filename_prefix`。
      `WanFirstLastFrameToVideo` 更惨：`clip_vision_start_image` 被填成 640、
      `height` 变成 1（整套 width/height/length/batch_size 集体错位）。

    真正的规矩是：**只有 INT / FLOAT / STRING / BOOLEAN 和下拉（COMBO，声明是个 list）能填值**，
    IMAGE / LATENT / MODEL / CONDITIONING 这些一律只能接线。

    ★ 还有一类特例：**`socketless: true`** —— 它连插口都没有，只能是个值。
      实测 `ImageCompare.compare_view` 声明成 `["IMAGECOMPARE", {"socketless": true}]`，
      它还是 `required` 的；不认这一类就会报 `required_input_missing: compare_view`。

    ★★ 2026-10-15 又补一类：**`COMFY_DYNAMICCOMBO_V3`** —— 新版的「动态下拉」，
      类型名是个**字符串**（不是候选 list），候选藏在 `cfg["options"]` 里，
      而且每个候选是 `{"key": "auto", "inputs": {...}}` 这种**对象**，不是裸字符串。
      实测 `SaveVideo.format` 就是这个：本机明明把整条 20 个节点全跑完了，
      最后一步报 `SaveVideo.execute() missing 1 required positional argument: 'format'`
      —— 因为它被当成「必须接线的口」，一个字都没填。
      `CreateVideo` 的 `codec` / `color_space` / `bit_depth` 是同一类。
    """
    类型 = 声明[0] if isinstance(声明, (list, tuple)) and 声明 else 声明
    cfg = (声明[1] if isinstance(声明, (list, tuple)) and len(声明) > 1
           and isinstance(声明[1], dict) else {})
    if cfg.get("forceInput"):
        return False
    if cfg.get("socketless"):
        return True                     # 没插口，只可能是值
    if isinstance(类型, list):
        return True                     # COMBO：一批候选值，是个下拉
    if str(类型) in _动态下拉:
        return True                     # 动态下拉：候选在 cfg["options"] 里
    return str(类型) in _可填类型


_动态下拉 = ("COMFY_DYNAMICCOMBO_V3",)


def _下拉候选(声明) -> list:
    """把一个下拉的候选值列出来（**要的是能填进去的那个值，不是给人看的标签**）。

    ★ 实测两处不一样：
      - 普通 COMBO：声明就是 `[["a","b"], {...}]` —— 候选就是裸字符串；
      - `COMFY_DYNAMICCOMBO_V3`：`[["COMFY_DYNAMICCOMBO_V3", {...}]]` —— 候选在
        `cfg["options"]` 里，每项是 `{"key": "auto", ...}`，**要取 `key`**。
    """
    类型 = 声明[0] if isinstance(声明, (list, tuple)) and 声明 else 声明
    cfg = (声明[1] if isinstance(声明, (list, tuple)) and len(声明) > 1
           and isinstance(声明[1], dict) else {})
    if isinstance(类型, list):
        return [x for x in 类型 if isinstance(x, (str, int, float))]
    if str(类型) in _动态下拉:
        出 = []
        for o in (cfg.get("options") or []):
            if isinstance(o, dict) and "key" in o:
                出.append(o["key"])
            elif isinstance(o, (str, int, float)):
                出.append(o)
        return 出
    return []


def _下拉默认(声明):
    """下拉没写默认值时填什么：取第一个候选（ComfyUI 界面就是这么干的）。"""
    cfg = (声明[1] if isinstance(声明, (list, tuple)) and len(声明) > 1
           and isinstance(声明[1], dict) else {})
    if "default" in cfg:
        return cfg["default"]
    候 = _下拉候选(声明)
    return 候[0] if 候 else None


_控件占位 = "__ctl__"        # 「生成后控制」那一格在 widgets_values 里占位，但它不是一个输入


def _输入名表(声明) -> list:
    """按声明顺序列出这个节点能填值的输入名。

    ★★ 必须给 `control_after_generate` 留一个占位 —— 这是**踩过的坑**：
      `KSampler` 在 `/object_info` 里声明的是
        model / seed / steps / cfg / sampler_name / scheduler / positive / negative / latent_image / denoise
      而界面上 `seed` 后面**多一格下拉**（randomize / fixed / increment），
      实测 widgets_values = `[173805153958730, "randomize", 4, 1, "euler", "simple", 1]`。
      不留占位就会整体错位一格：`steps` 收到字符串 "randomize"、
      `sampler_name` 收到数字 1 —— ComfyUI 直接报
      `Failed to convert an input value to a INT value: steps ... 'randomize'`。
      实测 2264 个节点类里有 **165 个**带这一格，不处理等于大面积错。
    """
    名 = []
    for k, v in 声明.items():
        if not 是控件(v):
            continue
        名.append(k)
        cfg = v[1] if isinstance(v, (list, tuple)) and len(v) > 1 and isinstance(v[1], dict) else {}
        if cfg.get("control_after_generate"):
            名.append(_控件占位)
    return 名


_注释类 = ("Note", "MarkdownNote", "NotePlus", "Note Plus (mtb)",
          "PreviewAny", "ShowText|pysssss", "PreviewText")
# 只活在界面里、API 格式里没有、已经被「原地化掉」的节点 —— 不算丢
_已化掉 = ("Reroute", "PrimitiveNode")


def 是注释(n: dict) -> bool:
    """这个 UI 节点是不是「便签/说明」—— 它不参与执行，丢了不算丢。

    ★ 为什么单独判：官方模板里几乎每条都夹着 `MarkdownNote` 写使用说明。
      把它们算进「没认出的节点」，就会把**本来能跑**的产线判成不能跑。
    """
    t = str((n or {}).get("type", ""))
    if t in _注释类:
        return True
    # 没输入也没输出的孤立节点，一律当注释
    return not (n.get("inputs") or n.get("outputs"))


def 展开子图(工作流: dict, 最多轮: int = 6) -> dict:
    """把 `definitions.subgraphs` 里的子图**摊平**进主图（原地改）。

    ★ 为什么非做不可：官方模板库里拿子图打包是常态 ——
      实测本机能跑的 308 条里，**183 条除了「有个子图」以外没有任何问题**。
      子图是「界面上的一个盒子」，API 格式里没有这种东西，不摊平就一条都跑不了。

    形状（实测 `templates ohneis i2v`）：
      - 主图节点里有个 `type == 子图id` 的**实例**，父图的链连到它的输入/输出槽位；
      - 子图自己带 `nodes` / `links`，另有 `inputNode`(id **-10**) / `outputNode`(id **-20**)；
      - 子图 `inputs[i].linkIds` 里的链，源都是 -10、槽位 i（= 第 i 个入参）；
      - 子图 `outputs[j].linkIds` 里的链，目标都是 -20、槽位 j（= 第 j 个出参）。

    做法就是**接线**：把「父图 → 实例槽位」接到「子图内部真正的消费点」上，
    再把「父图 ← 实例出参」接到「子图内部真正的产出点」上，然后把内部节点改名搬进来。
    """
    for _ in range(最多轮):
        子图们 = {str(s.get("id")): s for s in
                  ((工作流.get("definitions") or {}).get("subgraphs") or []) if isinstance(s, dict)}
        节点们 = [n for n in (工作流.get("nodes") or []) if isinstance(n, dict)]
        实例们 = [n for n in 节点们 if str(n.get("type", "")) in 子图们]
        if not 实例们:
            return 工作流

        最大号 = max([int(n["id"]) for n in 节点们
                      if str(n.get("id", "")).lstrip("-").isdigit()] or [0])
        父链 = [list(l) for l in (工作流.get("links") or [])
                if isinstance(l, (list, tuple)) and len(l) >= 5]
        链号 = max([int(l[0]) for l in 父链 if str(l[0]).lstrip("-").isdigit()] or [0])

        新节点 = [n for n in 节点们 if n not in 实例们]
        新链 = []
        换源 = {}            # (实例号, 出参槽位) → [内部节点号, 槽位]

        for 实例 in 实例们:
            实 = str(实例.get("id"))
            S = 子图们[str(实例.get("type"))]
            内链 = {l["id"]: l for l in (S.get("links") or []) if isinstance(l, dict)}

            # ① 父图喂给这个实例第 i 个入参的是什么
            入源 = {l[4]: [str(l[1]), l[2]] for l in 父链 if str(l[3]) == 实}

            # ★★ 2026-10-15 修：**外层槽位号 ≠ 子图入参序号**，必须按名字对。
            #   实测 `video_minimax_h3_i2v`：子图 inputs 顺序是
            #   `first_frame / last_frame / prompt / width / height`，
            #   而实例节点自己 `inputs[]` 的顺序不一样（没接线的那几个被挪了位置）。
            #   我原来写 `入源.get(i)`（i = 子图 inputs 的序号），于是
            #   **`prompt` 拿到了喂给 `width` 的那条链**。
            #   判据：认名字，绝不退回按序号。

            # ② 子图里被 -10 喂的消费点，换成①里的外部来源
            #   ★★ 2026-10-15 修（这个坑查了很久，机制写在下面）：
            #      子图入参分两种，**只有一部分在实例节点身上有「口」**。
            #      实测 `video_minimax_h3_i2v`：子图声明 15 个入参，实例 105 身上只有 9 个口
            #      —— `prompt(STRING)` / `noise_seed` / `unet_name` / `clip_name` /
            #      `vae_name` / `lora_name` 这 6 个**根本没有口**，它们的值在
            #      **实例自己的 `widgets_values` 里**，按「缺的那几个」的顺序排。
            #      我原来对不上的时候退回按序号 `.get(i)` —— 于是 `prompt`（子图第 2 个）
            #      撞上了外层第 2 号口，那正好是喂给 `width` 的 `ResolutionSelector`（INT），
            #      ComfyUI 报 `prompt, received_type(INT) mismatch input_type(STRING)`。
            #      **接线是通的，只是接错了口**，所以「能不能跑」的检查一直报「能跑」。
            实例口名 = {}
            for _t, _s in enumerate(实例.get("inputs") or []):
                if isinstance(_s, dict) and _s.get("name"):
                    实例口名[str(_s["name"])] = _t
            口名集 = set(实例口名)

            # 缺的那些（没有口的）按子图顺序排队，值从实例的 widgets_values 里按同序取
            #
            # ★★ 2026-10-15 第二次修（第一次修完还是错，这次找到了真规矩）：
            #   实例的 `widgets_values` **不是只装「没口的」那些** —— 它装的是
            #   **子图里所有「控件型」入参**，按子图声明顺序，**有口的也占一格**。
            #   实测 `video_minimax_h3_t2v`：子图 15 个入参，13 个控件型，实例的
            #   `widgets_values` 正好 13 格：
            #     [0]prompt [1]width=1344 [2]height=768 [3]value_1=5 [4]noise_seed=757358688076805
            #     [5]unet_name [6]clip_name [7]vae_name [8]vae_name_1 [9]value=False
            #     [10]lora_name [11]strength_model_1=1 [12]value_2=8
            #   —— `width`/`height`/`value_1`/`vae_name_1`/`value`/`strength_model_1`/`value_2`
            #   这 7 个在实例身上**明明有口**（被外面的线喂着），但**照样占着格子**。
            #   我第一版只数「没口的」6 个 → 下标整体错位，
            #   表现是 `unet_name` 收到 768（那是 height）、`vae_name` 收到一个种子号。
            #   判据：**按下标 `控件型入参[k] ← widgets_values[k]`**，有口的照样占格。
            _控件型 = ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO")
            控件型名 = [str(p.get("name") or "") for p in (S.get("inputs") or [])
                      if str(p.get("type") or "").upper() in _控件型]
            缺值 = {}
            _w = list(实例.get("widgets_values") or [])
            for _k, _nm in enumerate(控件型名):
                if _k < len(_w):
                    缺值[_nm] = _w[_k]

            替 = {}
            替值 = {}                       # (内部节点号, 槽位) → 字面值（不接线，直接填）
            for i, 参 in enumerate(S.get("inputs") or []):
                参名 = str(参.get("name") or "")
                外槽 = 实例口名.get(参名)
                for lid in (参.get("linkIds") or []):
                    l = 内链.get(lid)
                    if not (l and str(l.get("origin_id")) == "-10"):
                        continue
                    键 = (str(l["target_id"]), l["target_slot"])
                    if 外槽 is None:
                        # 没有口 → 值型，直接填字面量（绝不退回按序号找链！）
                        if 参名 in 缺值:
                            替值[键] = 缺值[参名]
                    else:
                        替[键] = 入源.get(外槽)

            # ④ 内部节点改名搬进来（-10 / -20 是接线柱，不搬）
            #    ★ 必须先算改名、再算③的出参来源 —— 反过来的话③里存的是**内部旧号**，
            #      而那些号已经被改掉了，⑥拿它去接线就查不到节点，
            #      表现是下游 `link` 有号、`溯源` 却回 None → 输入凭空消失 →
            #      ComfyUI 报 `required_input_missing: video`。
            改名 = {}
            for n in (S.get("nodes") or []):
                if not isinstance(n, dict) or str(n.get("id")) in ("-10", "-20"):
                    continue
                最大号 += 1
                改名[str(n.get("id"))] = str(最大号)
                nn = json.loads(json.dumps(n, ensure_ascii=False))
                nn["id"] = 最大号
                新节点.append(nn)

            # ③ 子图第 j 个出参是谁产出的（用改名后的新号）
            #    ★ 同一个坑的另一半：⑥ 拿 `l[2]`（外层链的 origin_slot）来查这里，
            #      而 origin_slot 数的是**实例节点自己的 `outputs[]`**，
            #      跟子图 `outputs[]` 的序号同样不一定对得上 —— 也得按名字。
            实出槽 = {}
            for _j, _s in enumerate(实例.get("outputs") or []):
                if isinstance(_s, dict) and _s.get("name"):
                    实出槽[str(_s["name"])] = _j
            for j, 参 in enumerate(S.get("outputs") or []):
                参名 = str(参.get("name") or "")
                外槽 = 实出槽.get(参名, j)          # ★ 按名字找外层出参槽位
                for lid in (参.get("linkIds") or []):
                    l = 内链.get(lid)
                    if l and str(l.get("target_id")) == "-20":
                        旧 = str(l["origin_id"])
                        换源[(实, 外槽)] = [改名.get(旧, 旧), l["origin_slot"]]

            # ⑤ 内部链搬进来，两头都按改名换掉
            for l in (S.get("links") or []):
                if not isinstance(l, dict):
                    continue
                源, 靶 = str(l.get("origin_id")), str(l.get("target_id"))
                if 靶 == "-20":                       # 出参：由③负责，不搬
                    continue
                if 源 == "-10":                       # 入参：接外部来源，或者直接填个值
                    槽 = l.get("target_slot")
                    外 = 替.get((靶, 槽))
                    if 外:
                        新链.append([链号 + 1, 外[0], 外[1], 改名.get(靶, 靶),
                                    槽, l.get("type")])
                    elif (靶, 槽) in 替值:
                        # ★ 值型入参：实例身上没有这个口，值就写在 `widgets_values` 里。
                        #   不接线，直接**填字面量**给消费节点。
                        #   消费节点在第 4 个槽位的输入名，从它自己的 `inputs[]` 里取。
                        新号 = 改名.get(靶, 靶)
                        名 = None
                        for _n in (S.get("nodes") or []):
                            if str(_n.get("id")) == 靶:
                                for _i, _s in enumerate(_n.get("inputs") or []):
                                    if _i == 槽 and isinstance(_s, dict):
                                        名 = _s.get("name")
                                break
                        if 名:
                            for _nn in 新节点:
                                if str(_nn.get("id")) == 新号:
                                    _nn.setdefault("_注入", {})[名] = 替值[(靶, 槽)]
                                    break
                else:
                    if 源 not in 改名 or 靶 not in 改名:
                        continue
                    新链.append([链号 + 1, 改名[源], l.get("origin_slot"),
                                 改名[靶], l.get("target_slot"), l.get("type")])
                链号 += 1

        # ⑥ 父图里所有「从实例的出参取东西」的链，改接到真正的产出点
        #    ★ 取的是 `l[2]`（**origin_slot**），不是 `l[3]`（那是 target_id）。
        #      写错过一次：键取成 target_id，`换源` 永远查不到 → 直接 continue，
        #      表现是下游节点的 `link` 变成 null、ComfyUI 报 `required_input_missing: video`。
        实例号们 = {str(x.get("id")) for x in 实例们}
        for l in 父链:
            if str(l[1]) in 实例号们:
                真 = 换源.get((str(l[1]), l[2]))
                if not 真:
                    continue                  # 出参没接到东西 → 这条链作废
                新链.append([链号 + 1, 真[0], 真[1], str(l[3]), l[4], l[5]])
            elif str(l[3]) in 实例号们:
                continue                      # 喂给实例入参的链，已由⑤接手
            else:
                新链.append(list(l))
            链号 += 1

        # ⑦ 重算每个节点的 inputs[].link —— 摊平后老的链路号全失效了
        图 = {(str(l[3]), l[4]): l[0] for l in 新链}
        for n in 新节点:
            for i, s in enumerate(n.get("inputs") or []):
                if isinstance(s, dict):
                    s["link"] = 图.get((str(n.get("id")), i))
        工作流["nodes"] = 新节点
        工作流["links"] = 新链
    return 工作流

def 转API(工作流: dict, 表: dict | None = None) -> dict:
    """UI 格式（`nodes` + `links`）→ API 格式（`{节点号: {class_type, inputs}}`）。

    ★ 不转就没法 `POST /prompt` —— 官方模板库 614 条给的全是 UI 格式。
    ★ 认不出的节点**整条丢掉**，不硬塞一个空壳进去：塞进去 ComfyUI 只会报一个
      跟真实原因无关的错，比直接报「这个节点我不认识」难查十倍。
    """
    表 = 表 if 表 is not None else 节点表()
    工作流 = 展开子图(json.loads(json.dumps(工作流, ensure_ascii=False)))
    出, 丢, 注 = {}, [], 0

    # 线：[链路id, 源节点号, 源槽位, 目标节点号, 目标槽位, 类型]
    连 = {}
    for l in (工作流.get("links") or []):
        if isinstance(l, (list, tuple)) and len(l) >= 5:
            连[(str(l[3]), int(l[4]))] = [str(l[1]), int(l[2])]
    原节点 = {str(n.get("id")): n for n in (工作流.get("nodes") or []) if isinstance(n, dict)}

    def 溯源(号: str, 槽: int, 深: int = 0):
        """顺着线往回找「真正的来源」。

        ★ 两种节点只活在界面里，API 格式里没有它们，必须原地化掉：
          - `Reroute`（改线点）：一根直通的管子，跳过它继续往上找；
          - `PrimitiveNode`（原语）：它身上带着一个**值**（不是节点），
            把它喂给谁，就等于给那个人填了个数。
        不处理这两种，官方模板里 37 条本来能跑的会被判成不能跑。
        """
        if 深 > 24:
            return None
        n = 原节点.get(号)
        if n is None:
            return None
        t = str(n.get("type", ""))
        if t == "Reroute":
            上 = 连.get((号, 槽)) or 连.get((号, 0))
            return 溯源(上[0], 上[1], 深 + 1) if 上 else None
        if t == "PrimitiveNode":
            值 = list(n.get("widgets_values") or [None])
            return 值[0] if 值 else None
        return [号, 槽]

    for n in (工作流.get("nodes") or []):
        if not isinstance(n, dict):
            continue
        if n.get("mode") in (2, 4):          # 静音 / 绕过 —— 不跑它
            continue
        ct = str(n.get("type", ""))
        声 = (表.get(ct) or {}).get("input") or {}
        声明 = dict(声.get("required") or {})
        for k, v in (声.get("optional") or {}).items():
            声明.setdefault(k, v)
        if not 声明:
            if 是注释(n) or str(n.get("type", "")) in _已化掉:
                注 += 1
            else:
                丢.append((n.get("id"), ct))
            continue
        控件们 = _输入名表(声明)
        值们 = list(n.get("widgets_values") or [])
        号 = str(n.get("id"))
        输入, 用掉 = {}, 0

        def _收(名):
            """把 widgets_values[用掉] 塞给 `名`，占位格只前进不赋值。"""
            nonlocal 用掉
            if 用掉 >= len(值们):
                return
            v = 值们[用掉]
            用掉 += 1
            if 名 and 名 != _控件占位 and (isinstance(v, (str, int, float, bool)) or v is None):
                输入[名] = v

        for i, s in enumerate(n.get("inputs") or []):
            if not isinstance(s, dict):
                continue
            # 控件型输入的名字以 `widget.name` 为准 —— 实测有节点两处名字不一致
            名 = ((s.get("widget") or {}).get("name") if isinstance(s.get("widget"), dict)
                  else None) or s.get("name") or (控件们[用掉] if 用掉 < len(控件们) else None)
            if s.get("link") is None:
                continue
            源 = 连.get((号, i))
            if 源 and 名:
                真 = 溯源(源[0], 源[1])
                if 真 is not None:
                    输入[名] = 真

        # ★★ 值们（widgets_values）必须**按下标**对齐「声明顺序里的控件们」。
        #    不能顺着消费（那是踩过的坑）：一个控件如果既接着线、又有值，
        #    它的值**仍然占着 widgets_values 里的那一格**。
        #    顺着消费会整体错位一格，实测表现是
        #      `BasicScheduler` 收到 `scheduler` 缺失 + `denoise=4`（那是 steps 的值）；
        #      `ResolutionSelector` 收到 `megapixels="1:1 (Square)"`（那是 aspect_ratio 的值）
        #      `multiple=0.4`（那是 megapixels 的值）。
        #    正确做法：`控件们[k] ← 值们[k]`，接走线的那些**跳过赋值但仍占格**。
        for k, 名 in enumerate(控件们):
            if k >= len(值们) or 名 == _控件占位 or 名 in 输入:
                continue
            v = 值们[k]
            if isinstance(v, (str, int, float, bool)) or v is None:
                输入[名] = v

        # ★ 兜底：**必填 + 能填值 + 还没值** 的，用声明里的 `default` 补上。
        #   ComfyUI 自己的界面就是这么干的（工作流没写就取控件默认值）。
        #   不补的话会遇到 `required_input_missing`，而那些参数在界面上
        #   本来就有一个默认值，等于白白判死。
        for 名, 声 in 声明.items():
            if 名 in 输入 or not 是控件(声):
                continue
            cfg = (声[1] if isinstance(声, (list, tuple)) and len(声) > 1
                   and isinstance(声[1], dict) else {})
            if "default" in cfg:
                输入[名] = cfg["default"]
            elif isinstance(声[0], list) or str(声[0]) in _动态下拉:
                默认 = _下拉默认(声)
                if 默认 is not None:
                    输入[名] = 默认          # 没默认值的下拉：取第一个候选

        # ★ 子图摊平时攒下的「值型入参」—— 那些在实例节点身上没有口、
        #   值写在 `widgets_values` 里的（`prompt` / `noise_seed` / `unet_name`…）。
        #   摊平的时候它们接不了线，只能记成 `_注入` 挂到搬进来的内部节点上，
        #   到这儿才真正填进去。**优先于上面所有来源** —— 它就是用户在这个框里填的字。
        for 名, v in (n.get("_注入") or {}).items():
            if 名 in 声明:
                输入[名] = v
        出[号] = {"class_type": ct, "inputs": 输入}
    return {"prompt": 出, "丢": 丢, "注": 注, "认出": len(出),
            "总数": len([x for x in (工作流.get("nodes") or []) if isinstance(x, dict)])}


def 转得干不干净(工作流: dict, 表: dict | None = None) -> dict:
    """转一遍，报「认出了几个 / 丢了几个 / 丢的是谁」。

    ★ 判据：**丢 0 个**才算这条产线能跑。丢一个，ComfyUI 那边的行为就是未知的。
      （便签/说明不算丢 —— 它们本来就不执行。）
    """
    r = 转API(工作流, 表)
    return {"能跑": len(r["丢"]) == 0, "认出": r["认出"], "总数": r["总数"],
            "注": r["注"], "丢": r["丢"], "api": r["prompt"]}


def 跑(api: dict, 机: str = "本机", ComfyUI地址: str | None = None) -> dict:
    """把 API 格式的工作流 `POST /prompt` 交上去。"""
    基 = ComfyUI地址 or ("http://127.0.0.1:8188" if 机 == "本机"
                        else "http://100.127.224.106:8188")
    体 = json.dumps({"prompt": api}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(基 + "/prompt", data=体, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        return {"ok": True, "任务": d.get("prompt_id"), "码": r.status}
    except urllib.error.HTTPError as e:
        原 = (e.read() or b"").decode("utf-8", "replace")
        try:
            d = json.loads(原)
        except Exception:
             d = {}
        return {"ok": False, "码": e.code, "错": d.get("error") or 原[:400],
                "详情": d.get("node_errors") or {}}


def 要填什么(键: str, 机: str = "本机", ComfyUI地址: str | None = None) -> dict:
    """这条产线交过去之前，**得你填的有哪些**。

    ★ 判据：只列「**值型**输入里、还真缺东西的」——
      接管线的（`["123", 0]` 这种）不用填，有值且不像是占位符的也不用填。
      不然一条 30 个节点的产线会列出 60 个框，用户一个都不想看。

    返回 `{"ok", "能跑", "丢", "要": [{节点, 类, 名, 类型, 现值, 候选, 说什么}]}`
    """
    表 = 节点表(机, ComfyUI地址)
    w = 拿(键)
    r = 转得干不干净(json.loads(json.dumps(w, ensure_ascii=False)), 表)
    api = r["api"]
    要 = []
    # 节点顺序按 UI 里的原序，别按字典序 —— 用户要按顺序填
    序 = [str(n.get("id")) for n in (w.get("nodes") or []) if isinstance(n, dict)]
    for 号 in sorted(api.keys(), key=lambda x: 序.index(x) if x in 序 else 9999):
        节 = api[号]
        ct = 节.get("class_type")
        声 = (表.get(ct) or {}).get("input") or {}
        合 = dict(声.get("required") or {})
        for k, v in (声.get("optional") or {}).items():
            合.setdefault(k, v)
        for 名, 值 in (节.get("inputs") or {}).items():
            if isinstance(值, list):
                continue                      # 接着线的，不用填
            声 = 合.get(名)
            t = 声[0] if isinstance(声, (list, tuple)) and 声 else "?"
            if t not in _可填类型:
                continue
            cfg = (声[1] if isinstance(声, (list, tuple)) and len(声) > 1
                   and isinstance(声[1], dict) else {})
            候选 = list(t[0]) if isinstance(t, list) else None
            if 候选 is None and isinstance(声, (list, tuple)) and 声 and isinstance(声[0], list):
                候选 = list(声[0])
            说什么 = ""
            if 名 in ("text", "prompt", "positive", "string", "value"):
                说什么 = "要写的话"
            elif "image" in 名.lower():
                说什么 = "图片文件名（要放在 ComfyUI 的 input 目录里）"
            elif "video" in 名.lower():
                说什么 = "视频文件名（要放在 ComfyUI 的 input 目录里）"
            elif 名 in ("seed", "noise_seed"):
                说什么 = "种子，改一个数就换一版"
            elif 名 in ("width", "height", "length", "batch_size", "steps", "cfg"):
                说什么 = "数字"
            要.append({"节点": 号, "类": ct, "名": 名, "类型": (t if isinstance(t, str) else "COMBO"),
                       "现值": 值, "候选": (候选[:60] if 候选 else None), "说什么": 说什么})
    # 长文本排前面（那是一定要改的），数字/下拉沉底
    要.sort(key=lambda x: (0 if x["说什么"] == "要写的话" else 1,))
    return {"ok": True, "能跑": r["能跑"], "丢": r["丢"], "认出": r["认出"], "要": 要, "条": len(要)}


def 填了就跑(键: str, 改: dict, 机: str = "本机", ComfyUI地址: str | None = None) -> dict:
    """按「节点号.输入名 → 新值」改一遍，然后真交上去。

    `改` 的形状：`{"133.prompt": "写什么", "133.width": 832}`
    ★ 类型要转回来：从界面来的数都是字符串，`INT` 得转成 int，
      不然 ComfyUI 报 `invalid literal for int()`（这个错我已经踩过一次了）。
    """
    表 = 节点表(机, ComfyUI地址)
    w = 拿(键)
    r = 转得干不干净(json.loads(json.dumps(w, ensure_ascii=False)), 表)
    if not r["能跑"]:
        return {"ok": False, "错": "这条转换器还没吃透（丢了 %d 个节点：%s）"
                % (len(r["丢"]), r["丢"][:3])}
    api = r["api"]
    改了几处, 错 = 0, []
    for 路, 新 in (改 or {}).items():
        if "." not in str(路):
            continue
        号, 名 = str(路).split(".", 1)
        节 = api.get(号)
        if not 节 or 名 not in (节.get("inputs") or {}):
            错.append("没有 %s" % 路)
            continue
        ct = 节["class_type"]
        声 = (表.get(ct) or {}).get("input") or {}
        合 = dict(声.get("required") or {})
        for k, v in (声.get("optional") or {}).items():
            合.setdefault(k, v)
        s = 合.get(名)
        t = s[0] if isinstance(s, (list, tuple)) and s else None
        t = t if isinstance(t, str) else "COMBO"
        try:
            if t in ("INT",):
                新 = int(float(新))
            elif t in ("FLOAT",):
                新 = float(新)
            elif t == "BOOLEAN":
                新 = (str(新).strip().lower() in ("1", "true", "yes", "是", "on"))
        except (TypeError, ValueError) as e:
            错.append("%s 要是%s，给的是 %r（%s）" % (路, t, 新, e))
            continue
        节["inputs"][名] = 新
        改了几处 += 1
    果 = 跑(api, 机, ComfyUI地址)
    果.update({"改了几处": 改了几处, "小错": 错})
    return 果


def 存成模板(键: str, 名: str = "", 机: str = "本机",
             ComfyUI地址: str | None = None) -> dict:
    """★ 把官方库里的一条产线，**存成影匠自己的模板**。

    这是「两边一起用」缺的那一环：官方 614 条是 UI 格式、只能在 ComfyUI 里手点，
    影匠的 `引擎.图生视频(模板=…)` 吃的是 API 格式的 `影匠\\模板\\*.json`。
    以前换一条产线要人肉把 30 个节点抄一遍 —— 现在一句话搬过来。

    搬完**不用改一个字**就能跑，因为 `引擎.图生视频` 是按 `class_type` 认节点的
    （CLIPTextEncode 认正负向、LoadImage 领图、KSampler/KSamplerAdvanced 换种子、
    WanImageToVideo 系改宽高帧数、CreateVideo 改帧率、SaveVideo 改前缀），
    不依赖节点号 —— 节点号是官方库里长什么样就什么样。

    返回 `{"ok", "路", "节点数", "图槽", "丢"}`。
    """
    表 = 节点表(机, ComfyUI地址)
    w = 拿(键)
    r = 转得干不干净(json.loads(json.dumps(w, ensure_ascii=False)), 表)
    if not r["能跑"]:
        return {"ok": False, "错": "这条转换器还没吃透（丢了 %d 个节点：%s）"
                % (len(r["丢"]), r["丢"][:3]), "丢": r["丢"]}
    api = r["api"]

    # 图槽：按节点号从小到大 —— 跟 引擎.图生视频 里那个 _图槽 的排法**必须一致**，
    # 不一致就会出现「模板说第 1 槽是首帧、引擎填到了第 2 槽」这种静默错位。
    槽 = sorted((号 for 号, 节 in api.items() if 节.get("class_type") == "LoadImage"),
               key=lambda x: (len(str(x)), str(x)))

    出 = {"_说明": "从 ComfyUI 官方库搬来的产线：%s（键 %s）。"
                  "节点由 引擎.图生视频 按 class_type 自动接管，别手改节点号。"
                  % (w.get("_名") or 键, 键),
          "_规格": {"图槽": ["首帧", "尾帧"][:max(1, len(槽))] if 槽 else []}}
    出.update(api)

    名 = 名 or 键
    路 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "模板", _安全名(名) + ".json")
    os.makedirs(os.path.dirname(路), exist_ok=True)
    with open(路, "w", encoding="utf-8", newline="\n") as f:
        json.dump(出, f, ensure_ascii=False, indent=2)
    return {"ok": True, "路": 路, "名": _安全名(名), "节点数": len(api),
            "图槽": 槽, "丢": r["丢"], "认不出": r["认不出"] if "认不出" in r else []}


def _安全名(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(s)).strip() or "未命名"


# ───────────────────────── 自测 ─────────────────────────

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    # `python 产线.py 存模板 <键> [影匠里的名字]` —— 把官方产线搬成影匠模板
    if a and a[0] in ("存模板", "存", "搬"):
        if len(a) < 2:
            print("用法：python 产线.py 存模板 <键> [名字]")
            raise SystemExit(2)
        果 = 存成模板(a[1], a[2] if len(a) > 2 else "")
        if not 果["ok"]:
            print("✗ " + 果["错"])
            raise SystemExit(1)
        print(f"✓ 存成 {果['路']}")
        print(f"  {果['节点数']} 个节点，图槽 {果['图槽']}")
        print(f"  用：引擎.图生视频(图路, 提示词, 模板=\"{果['名']}\")")
        raise SystemExit(0)
    条 = 全部()
    print(f"产线库：{模板库 or '（没找到模板库！）'}")
    print(f"共 {len(条)} 条产线\n")
    for 类, 组 in 按类(条).items():
        print(f"── {类}  （{len(组)} 条）")
        for x in 组[:6]:
            要 = []
            if x["要图"]:
                要.append(f"{x['要图']} 张图")
            if x["要视频"]:
                要.append(f"{x['要视频']} 段视频")
            print(f"     {x['名']}")
            print(f"       {x['键']}   {x['节点数']} 节点"
                  + (f"　要 {'+'.join(要)}" if 要 else ""))
        if len(组) > 6:
            print(f"     … 还有 {len(组)-6} 条")
