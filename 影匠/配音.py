# -*- coding: utf-8 -*-
"""
配音.py —— 影匠 TTS 配音（IndexTTS-2.5 / ComfyUI）

按名字从「音色库」找参考音频 → 丢给 ComfyUI 的 IndexTTS 节点 → 出 wav。
模型没下完 / 节点没加载 / ComfyUI 没开 —— **都给一句人话，不抛 traceback 崩掉**。

═══════════════════════════════════════════════════════════════════════════════
【原创声明 / 授权边界】
═══════════════════════════════════════════════════════════════════════════════
  本文件是影匠原创实现。飞彩工作台（FEICAI Studio）包里可考的只有「它调了什么
  服务、用了哪些节点、参数是什么」这一类**设计事实**（证据见
  `知识\\视频与音频系统.md`），**没有抄一行代码**。
  授权 / 许可证 / 设备指纹 / 签名 / 计费逻辑：**完全未涉及，也未分析**。

  飞彩的做法（挖到的，供参考）：短剧 TTS 走 RunningHub 的 `webapp` 工作流，
  按「角色/旁白」分组批量跑；后配音（重配音）走**本地 IndexTTS-2 兼容服务**。
  影匠直接走**本机 ComfyUI + ComfyUI-Index-TTS 节点**，等价但自主可控。

═══════════════════════════════════════════════════════════════════════════════
【本机实测环境（2026-10-14 实测，非猜测）】
═══════════════════════════════════════════════════════════════════════════════
  · ComfyUI       : 在线，`http://127.0.0.1:8188`，版本 0.39.2
  · 自定义节点    : `custom_nodes\\ComfyUI-Index-TTS\\` **源码在**，
                    但 `/object_info` 里 **Index / TTS 命中 0 个** → **节点没被加载**
  · 模型目录      : `<ComfyUI>\\models\\IndexTTS-2.5\\`
      ✓ config.yaml / feat1.pt / feat2.pt / codec.pth / multilingual_zh_ja_yue_char_del.tiktoken
      ✗ gpt.pth                    （只剩 `gpt.pth.lock`，下载没完成）
      ✗ s2mel.pth
      ✗ wav2vec2bert_stats.pt
      ✗ bigvgan\\bigvgan_generator.pt + bigvgan\\config.json
      ✗ campplus_cn_common.bin
      ✗ w2v-bert-2.0\\             （整个目录没有）
      ✗ qwen0.6bemo4-merge\\model.safetensors（只有 tokenizer 几个 json，下载中断）

  → 结论：**现在跑不通真合成**。`体检()` 会把上面这些一条条列给人看，
    `合成()` 会直接抛一句人话 RuntimeError，而不是让 ComfyUI 报一堆堆栈。

  官方下载脚本就在节点目录里：
      `custom_nodes\\ComfyUI-Index-TTS\\TTS2_5_download.py`
  模型根目录由 `<ComfyUI>/custom_nodes/ComfyUI-Index-TTS/indextts2_5/model_loader.py`
  的 `DEFAULT_DIRNAME = "IndexTTS-2.5"` 决定，即 `<ComfyUI>/models/IndexTTS-2.5`。

═══════════════════════════════════════════════════════════════════════════════
【IndexTTS-2.5 节点接口（从节点源码逐字抄下来的，不是猜的）】
═══════════════════════════════════════════════════════════════════════════════
  文件：`custom_nodes\\ComfyUI-Index-TTS\\index_tts2_5_nodes.py`

  class IndexTTS25BaseNode            CATEGORY = "audio"
    required: text(STRING 多行) / reference_audio(AUDIO) / lang(枚举) /
              duration_factor(FLOAT 0.5–2.0, step 0.05, 默认 1.0)
    optional: do_sample_mode["off","on"] 默认 "on" / temperature 0.8(0.1–2.0) /
              top_p 0.8(0–1) / top_k 30(0–100) / num_beams 3(1–10) /
              repetition_penalty 10.0(1–10) / length_penalty 0.0(–2–2) /
              max_mel_tokens 1500(50–1815) / max_tokens_per_sentence 120(0–600) /
              interval_silence_ms 200(0–2000) / text_normalization True /
              seed 0(0–2³²–1) / cache_control(DICT, 默认 None)
    RETURN_TYPES = ("AUDIO","INT","STRING")
    RETURN_NAMES = ("audio","seed","subtitle")
    lang 枚举 LANG_CHOICES = ["ZH","EN","JA","ES","AR","ZH/EN"]
    duration_factor：**>1 变慢，<1 变快**（所以语速 1.2 倍 → duration_factor≈0.833）
    发音标注直接写在 text 里：`<行|XING2>` / `<minute|M AY0 . N UW1 T>` / `<上手|じょうず>`

  另外三个「情感节点」是 Base 的**平替**（同样 required + 各自加料）：
    IndexTTS25EmotionVectorNode  → 8 个滑条（0–1, step 0.05，默认全 0）：
        Happy / Angry / Sad / Fear / Hate / Low / Surprise / Neutral
        （顺序 = 官方的 高兴/愤怒/悲伤/恐惧/反感/低落/惊讶/平静）
    IndexTTS25EmotionAudioNode   → emo_ref_audio(AUDIO) + emotion_weight(0–1, 默认 1.0)
    IndexTTS25EmotionTextNode    → emotion_description(STRING 多行)，留空则自动分析主文本
                                   ★ 需加载 Qwen 情感模型（本机没下 → 会失败）

  缓存控制节点 IndexTTS25CacheControlNode → DICT，键 `keep_cached`(BOOLEAN)。
    传进 Base 节点的 `cache_control`；`keep_cached=True` 时生成完**不卸载模型**。
    批量配音时非常值得开，否则每句都要重新 load 一遍几十 GB。

  ★ 注意：`subtitle` 是节点的第 3 个 RETURN，ComfyUI 的 /history 里拿不到普通
    RETURN（只有 `ui` 段会回传）。所以本文件默认**自己按文本切句生成 SRT**；
    如果运行时发现有 `PreviewAny` 之类的文本预览节点，会自动接上去取真字幕
    （见 `_找文本预览节点()`）。

═══════════════════════════════════════════════════════════════════════════════
【音色库】
═══════════════════════════════════════════════════════════════════════════════
  文件：`音色\\音色库.json`，由 `音色库.py 编目()` 生成（**只读，本文件不改它**）。
  结构：`{"版本","生成时间","根目录","统计":{…},"音频":[…]}`，`音频[]` 每条有：
    名字 / 路径(绝对) / 相对 / 文件名 / 大类 / 子类 / 字节 / MB / 格式 /
    秒 / 采样率 / 声道 / 指纹 / 性别[] / 年龄[] / 气质[] / 用途[] / 语言[]
  实测统计：1408 条，717.9 MB，243.0 分钟，平均 10.4 秒，最长 192.89 秒，最短 0.56 秒。

  IndexTTS 是**零样本克隆**：参考音频 3–15 秒、干净、单人、无背景乐效果最好。
  本文件在 `参考音频()` 里会对时长做体检并给提示（太长/太短都不拦，只提醒）。

═══════════════════════════════════════════════════════════════════════════════
【用法】
═══════════════════════════════════════════════════════════════════════════════
    import 配音

    配音.体检()                              # 先看能不能跑（人话报告）
    配音.找音色("温柔 女")                    # 按标签/名字找音色
    配音.合成("你好，我是影匠。", 音色="xxx", 存到="作品/配音/开场.wav")
    配音.批量([{"序号":1,"台词":"…","音色":"…"}, …])   # 出 wav + srt

    python 配音.py 体检
    python 配音.py 查 温柔
    python 配音.py 试 "你好，我是影匠。" --音色 xxx
    python 配音.py 自查        # 不需要模型，跑通全流程（会跳过真合成）
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

这里 = Path(__file__).resolve().parent

# ─────────────────────────── 配置 ───────────────────────────

COMFY = os.environ.get("影匠_COMFY", "http://127.0.0.1:8188")           # 与 引擎.py 同一约定
COMFY根 = Path(os.environ.get("影匠_COMFY根", r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"))

音色库路 = 这里 / "音色" / "音色库.json"
配音输出 = 这里 / "作品" / "配音"

基础节点 = "IndexTTS25BaseNode"
向量节点 = "IndexTTS25EmotionVectorNode"
音频情感节点 = "IndexTTS25EmotionAudioNode"
文本情感节点 = "IndexTTS25EmotionTextNode"

加载音频节点 = "LoadAudio"
保存音频节点 = "SaveAudio"

语言表 = ["ZH", "EN", "JA", "ES", "AR", "ZH/EN"]

# IndexTTS 的 duration_factor：>1 变慢
语速下限, 语速上限 = 0.5, 2.0

# 8 维情感滑块（英文键，顺序固定 = 官方的 高兴/愤怒/悲伤/恐惧/反感/低落/惊讶/平静）
情感维 = ["Happy", "Angry", "Sad", "Fear", "Hate", "Low", "Surprise", "Neutral"]
情感中文 = {
    "高兴": "Happy", "愤怒": "Angry", "悲伤": "Sad", "恐惧": "Fear",
    "反感": "Hate", "低落": "Low", "惊讶": "Surprise", "平静": "Neutral", "自然": "Neutral",
    "happy": "Happy", "angry": "Angry", "sad": "Sad", "fear": "Fear",
    "hate": "Hate", "low": "Low", "surprise": "Surprise", "neutral": "Neutral",
}

# ── 第 1 层：`indextts2_5/model_loader.py` 的 `validate()` 逐字点名的 8 件 ──
#    缺任一件 → 加载器直接抛 FileNotFoundError，信息清楚。
必需文件 = [
    "config.yaml", "feat1.pt", "feat2.pt", "gpt.pth",
    "codec.pth", "s2mel.pth", "wav2vec2bert_stats.pt",
    "multilingual_zh_ja_yue_char_del.tiktoken",
]

# ── 第 2 层：★ `validate()` **不查**、但 `infer_v2_5.py` 初始化时**真读**的 3 件 ──
#    这是最容易骗过自己的一层：`validate()` 会报「齐了」，然后跑到第 80% 才炸，
#    而且报错信息里不会告诉你就差哪个文件。实测证据见 知识\配音.md §〇 与 §4.6.-3。
#      ① w2v-bert-2.0\model.safetensors  → infer_v2_5.py:179 Wav2Vec2BertModel.from_pretrained
#      ② bigvgan\bigvgan_generator.pt    → infer_v2_5.py:243 BigVGAN.from_pretrained
#      ③ campplus_cn_common.bin          → infer_v2_5.py:218-228 CAMPPlus.load_state_dict
#    额外更阴的一点：infer_v2_5.py:169-177 **只看 w2v-bert-2.0\ 目录在不在**，
#    目录一存在就 local_files_only=True，把 ensure_models_available() 的联网兜底整个绕过
#    —— 所以「目录在但内容不全」比「目录不在」更难修。
深层必需 = [
    ("w2v-bert-2.0/model.safetensors", "语义特征主干（validate 不查，但 infer 真要）"),
    ("w2v-bert-2.0/config.json", "语义编码器配置（SeamlessM4TFeatureExtractor 要读）"),
    ("w2v-bert-2.0/preprocessor_config.json", "语义编码器前处理配置"),
    ("bigvgan/bigvgan_generator.pt", "声码器权重（不出声多半是它没下）"),
    ("bigvgan/config.json", "声码器配置"),
    ("campplus_cn_common.bin", "说话人/音色向量 CAM++（取参考音频风格那一步）"),
]

# 可选但常用的（缺了不影响主链路，或干脆用不到）
可选文件 = [
    ("qwen0.6bemo4-merge/model.safetensors", "Qwen 情感模型（只有 Emotion Text 节点要）"),
    ("qwen0.6bemo4-merge/config.json", "Qwen 情感模型配置"),
    # ★ 实测证实**用不到**（省 2.17 GB）：Wav2Vec2BertConfig.position_embedding_type 实测为 None，
    #   即不使用 shaw 相对位置编码，而这份权重正是 shaw 那份。仍留在清单里是为了
    #   「哪天 from_pretrained 报缺文件，第一个来查这里」——见 知识\配音.md §六 第 9 条。
    ("conformer_shaw.pt", "w2v 的 shaw 权重 —— 实测判为用不到，默认不下"),
]


# ─────────────────────────── 角色 → 音色（G5）───────────────────────────
# 为什么音色挂在【角色】上：照抄飞彩（character.voiceId，见 知识\配音.md §一）。
# 挂在台词上的坏处是同一个角色十句台词要在十个地方写音色，改一次要改十处，且必然漏一处。
映射路 = 这里 / "音色" / "角色映射.json"

# 旁白识别：与飞彩的两套清单合并成一套（它一套含「旁白」一套不含，是历史遗留）。
旁白词 = {"旁白", "旁", "旁述", "narrator", "n", "画外音", "内心独白"}


def _归一(名: str) -> str:
    """角色名/音色名/相对路径统一归一化。

    路径那层不能省：音色库.json 里 `相对` 存的是**正斜杠**，人手写映射表习惯用**反斜杠**，
    不归一就会「明明是同一个文件却判不存在」。
    """
    s = (名 or "").strip().lower().replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    return s


def 是旁白(名: str) -> bool:
    return _归一(名) in 旁白词


def 载映射() -> dict:
    """读 音色\\角色映射.json（只读）。没有就当空表 —— 这是可降级的功能，不该让整条链路起不来。"""
    if not 映射路.is_file():
        return {"角色": {}}
    try:
        return json.loads(映射路.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ 角色映射.json 读不了（{e}），这次当空表用。")
        return {"角色": {}}


def 找角色(名: str, 映射: dict | None = None) -> dict | None:
    """按角色名找映射条目。三级：角色名精确 → 归一化精确 → 比别名。

    ★ 为什么必须归一层：剧本写「凌霜」、分镜写「凌霜 」、音色表写「凌霜」——
      不归一就是三个角色。飞彩专门写了个 `ew()` 干这件事，说明它也踩过。
    """
    映射 = 映射 if 映射 is not None else 载映射()
    低 = _归一(名)
    if not 低:
        return None
    for 键, v in (映射.get("角色") or {}).items():
        if 键 == 名 or _归一(键) == 低:
            return v
    for v in (映射.get("角色") or {}).values():
        for a in (v.get("别名") or []):
            if _归一(a) == 低:
                return v
    return None


def 角色定音色(名字或角色: str, 映射: dict | None = None) -> tuple[str, str]:
    """把一个词解析成音色。返回 (要用的音色词, 怎么来的)。

    先当【角色名】查映射表，命中就用该角色的音色；否则原样当音色名/路径用。
    ★ 顺序不能反：角色名和音色名可能撞（比如某角色就叫「御姐」），
      而映射表是**人明确指定过的**，比模糊匹配可信。
    """
    v = 找角色(名字或角色, 映射)
    if v and (v.get("音色") or "").strip():
        return v["音色"].strip(), ("旁白" if 是旁白(名字或角色) else "映射")
    return 名字或角色, ""


# ─────────────────────────── 音色库 ───────────────────────────


def 载音色库() -> dict:
    """读 音色\\音色库.json（只读）。文件不在就给一句人话。"""
    if not 音色库路.is_file():
        raise FileNotFoundError(
            f"没找到音色库：{音色库路}\n"
            f"解决：cd \"{这里}\" 然后跑  python 音色库.py   （会重新编目并写 音色库.json）"
        )
    return json.loads(音色库路.read_text(encoding="utf-8"))


def _干草(条目: dict) -> str:
    """把一条音色拍成一个大字符串，供模糊匹配用。"""
    块 = [
        str(条目.get("名字", "")), str(条目.get("文件名", "")),
        str(条目.get("相对", "")), str(条目.get("大类", "")), str(条目.get("子类", "")),
    ]
    for 键 in ("性别", "年龄", "气质", "用途", "语言"):
        值 = 条目.get(键)
        if isinstance(值, list):
            块.extend(str(x) for x in 值)
        elif 值:
            块.append(str(值))
    return " ".join(块)


def 找音色(词: str = "", 限: int = 10, 大类: str = "") -> list[dict]:
    """
    按名字 / 标签找音色。返回按「匹配优先 → 时长降序」排好的候选列表。

    匹配策略（和 音色库.py 的 `查()` 思路一致，但这里是本模块自己实现的）：
      1. 名字**完全等于** 词      → 最优先
      2. 名字 / 文件名**包含** 词  → 次优先
      3. 干草串包含 词             → 再次
      4. 词的每个字都出现过        → 兜底
    """
    库 = 载音色库()
    全部 = 库.get("音频", [])
    if 大类:
        全部 = [x for x in 全部 if x.get("大类") == 大类]

    词 = (词 or "").strip()
    if not 词:
        return 全部[:限]

    甲, 乙, 丙, 丁 = [], [], [], []
    for 条 in 全部:
        名 = str(条.get("名字", ""))
        文 = str(条.get("文件名", ""))
        干 = _干草(条)
        低名, 低文, 低干 = 名.lower(), 文.lower(), 干.lower()
        if 名 == 词:
            甲.append(条)
        elif 词 in 名 or 词 in 文:
            乙.append(条)
        elif 词.lower() in 低干:
            丙.append(条)
        elif all(字.lower() in 低干 for 字 in 词):
            丁.append(条)

    def 排(组):
        return sorted(组, key=lambda x: -(x.get("秒") or 0))

    return (排(甲) + 排(乙) + 排(丙) + 排(丁))[:限]


def 按路找音色(相对: str) -> dict | None:
    """
    按**相对路径**精确取一条音色（如 `男女——情绪分类\\女-常规-清冷无情-2-1.wav`）。

    为什么需要这个：模糊匹配再好也只是「比较像」。剧本 → 角色 → 音色 这条链路上
    必须能**指名道姓**地点一条音色，否则「A 组第 1 个」这种引用会随库更新而漂移。
    路径在库内唯一（`指纹` 就是它的 md5），所以这是最稳的钥匙。
    """
    要 = str(相对).replace("/", "\\").strip()
    for 条 in 载音色库().get("音频", []):
        if str(条.get("相对", "")).replace("/", "\\") == 要:
            return 条
        if str(条.get("路径", "")).replace("/", "\\") == 要:
            return 条
    return None


def 参考音频(名字: str) -> dict:
    """
    按名字取一条音色的参考音频信息。

    返回 {"名字","路径","秒","采样率","声道","大类","子类","标签","提示"}
    —— `提示` 里是 IndexTTS 克隆效果的建议（不拦人，只提醒）。
    查不到就抛 KeyError，附上最接近的候选，让人能立刻改对。
    """
    直 = 按路找音色(名字)
    if 直 is not None:
        候选 = [直] + [x for x in 找音色(名字, 限=6) if x.get("指纹") != 直.get("指纹")]
    else:
        候选 = 找音色(名字, 限=6)
    if not 候选:
        raise KeyError(
            f"音色库里找不到「{名字}」相关的音色。\n"
            f"换个词试试（比如「温柔」「男声」「旁白」），或者跑："
            f"python \"{这里/'音色库.py'}\" --查 温柔"
        )

    条 = 候选[0]
    路 = Path(str(条.get("路径", "")))
    提示 = []

    if not 路.is_file():
        提示.append(f"⚠ 参考音频文件不存在（音色库可能过期了）：{路}  跑 python 音色库.py 重新编目")

    秒 = 条.get("秒")
    if 秒 is not None:
        if 秒 < 2:
            提示.append(f"⚠ 参考音频只有 {秒:.2f} 秒，太短，克隆音色会不稳（建议 3–15 秒）")
        elif 秒 > 20:
            提示.append(f"⚠ 参考音频 {秒:.2f} 秒偏长，建议先剪到 3–15 秒干净人声，速度更快效果更好")

    格式 = str(条.get("格式", "")).lower()
    if 格式 and 格式 not in (".wav", ".flac"):
        提示.append(f"· 参考音频是 {格式}，IndexTTS 内部会重采样；wav/flac 更稳")

    return {
        "名字": 条.get("名字", ""),
        "路径": str(路),
        "秒": 秒,
        "采样率": 条.get("采样率"),
        "声道": 条.get("声道"),
        "大类": 条.get("大类", ""),
        "子类": 条.get("子类", ""),
        "标签": {k: 条.get(k) for k in ("性别", "年龄", "气质", "用途", "语言") if 条.get(k)},
        "提示": 提示,
        "候选": [c.get("名字") for c in 候选],
    }


def 音色清单() -> list[str]:
    return [x.get("名字", "") for x in 载音色库().get("音频", [])]


# ─────────────────────────── ComfyUI 通信 ───────────────────────────


def _请求(路: str, 数据=None, 超时: int = 60, 原始: bool = False):
    """极简 HTTP 客户端（和 引擎.py 一个路子，但本文件自带，不依赖它）。"""
    网 = COMFY.rstrip("/") + 路
    if 数据 is None:
        请 = urllib.request.Request(网, method="GET")
    else:
        请 = urllib.request.Request(
            网, method="POST",
            data=json.dumps(数据).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
    try:
        with urllib.request.urlopen(请, timeout=超时) as 应:
            身 = 应.read()
    except urllib.error.HTTPError as e:
        详 = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"ComfyUI 返回 {e.code}：{详[:800]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"连不上 ComfyUI（{COMFY}）：{e.reason}\n"
            f"解决：先启动 ComfyUI Desktop，或者设环境变量 影匠_COMFY 指向真正的地址。"
        ) from None
    if 原始:
        return 身
    try:
        return json.loads(身.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return 身.decode("utf-8", "replace")


def 在线() -> dict:
    try:
        信 = _请求("/system_stats", 超时=8)
        return {"在线": True, "版本": 信.get("system", {}).get("comfyui_version", "?")}
    except Exception as e:  # noqa: BLE001
        return {"在线": False, "错": str(e)}


_规格缓存: dict[str, dict | None] = {}


def 节点规格(节点名: str) -> dict | None:
    """GET /object_info/<节点名>。节点没装就返回 None（不是抛异常）。"""
    if 节点名 in _规格缓存:
        return _规格缓存[节点名]
    try:
        信 = _请求(f"/object_info/{节点名}", 超时=30)
        果 = 信.get(节点名) if isinstance(信, dict) else None
    except Exception:  # noqa: BLE001
        果 = None
    _规格缓存[节点名] = 果
    return 果


def _规格说明(节点名: str) -> str:
    """把一个节点的 required / optional 参数名和枚举列出来，给人看。"""
    规 = 节点规格(节点名)
    if not 规:
        return f"（{节点名} 未加载，拿不到规格）"
    输 = 规.get("input", {})
    块 = []
    for 组 in ("required", "optional"):
        项 = 输.get(组) or {}
        小 = []
        for 名, 定义 in 项.items():
            类 = 定义[0] if isinstance(定义, list) and 定义 else "?"
            if isinstance(类, list):
                类 = "枚举[" + "|".join(str(x) for x in 类[:8]) + ("…]" if len(类) > 8 else "]")
            elif isinstance(类, str) and 类 == "DICT":
                类 = "DICT"
            小.append(f"{名}:{类}")
        块.append(f"  {组}  " + "  ".join(小))
    return "\n".join(块)


def 模型清单() -> list[dict]:
    """列 IndexTTS-2.5 模型目录下的必需/深层必需/可选文件状态。

    三层分开报，因为它们的**失败方式不一样**：
      必需     —— validate() 会拦，报错清楚
      深层必需 —— validate() **不拦**，跑到一半才炸，报错还说不清（最容易骗人的一层）
      可选     —— 不影响主链路
    """
    夹 = COMFY根 / "models" / "IndexTTS-2.5"
    出 = [{"文件": "（模型目录）", "状态": "在" if 夹.is_dir() else "缺", "字节": 0,
           "说明": str(夹)}]
    for 名 in 必需文件:
        p = 夹 / 名
        出.append({
            "文件": 名, "状态": "在" if p.is_file() else "缺",
            "字节": p.stat().st_size if p.is_file() else 0, "说明": "必需",
        })
    for 名, 说 in 深层必需:
        p = 夹 / 名
        出.append({
            "文件": 名, "状态": "在" if p.is_file() else "缺",
            "字节": p.stat().st_size if p.is_file() else 0, "说明": "深层必需 · " + 说,
        })
    for 名, 说 in 可选文件:
        p = 夹 / 名
        出.append({
            "文件": 名, "状态": "在" if p.is_file() else "缺",
            "字节": p.stat().st_size if p.is_file() else 0, "说明": "可选 · " + 说,
        })
    return 出


def _半截下载(夹: Path | None = None) -> list[str]:
    """找 huggingface 缓存里的 .incomplete / .lock —— 它们是「下到一半」的铁证。"""
    夹 = 夹 or (COMFY根 / "models" / "IndexTTS-2.5")
    出 = []
    if not 夹.is_dir():
        return 出
    for 根, _, 文们 in os.walk(夹):
        for 文 in 文们:
            if 文.endswith(".incomplete") or 文.endswith(".lock"):
                出.append(str(Path(根) / 文))
    return 出


def 体检(细: bool = False) -> dict:
    """
    一句话体检：现在到底能不能配音。返回 {"能跑": bool, "报告": [行…], "摘要": str}

    **只读，不改任何东西。**
    """
    行 = []
    能跑 = True

    # 1. ComfyUI
    状 = 在线()
    if 状["在线"]:
        行.append(f"✓ ComfyUI 在线（{COMFY}，版本 {状['版本']}）")
    else:
        能跑 = False
        行.append(f"✗ ComfyUI 不在线：{COMFY}")
        行.append("   解决：启动 ComfyUI Desktop（或者 python main.py），再跑一次。")

    # 2. 节点
    if 状["在线"]:
        规 = 节点规格(基础节点)
        if 规:
            行.append(f"✓ 节点 {基础节点} 已加载")
            if 细:
                行.append(_规格说明(基础节点))
            缺的 = [n for n in (向量节点, 音频情感节点, 文本情感节点) if not 节点规格(n)]
            if 缺的:
                行.append(f"· 这些情感节点没加载（不影响基础配音）：{', '.join(缺的)}")
        else:
            能跑 = False
            行.append(f"✗ 节点 {基础节点} **没被 ComfyUI 加载**（/object_info 里查不到）")
            行.append("   这是当前卡住的地方。常见原因，按可能性排：")
            行.append("   ⓪ ★ 装了依赖但**没重启 ComfyUI** —— custom_nodes 的 import 只在启动时做一次，")
            行.append("      依赖是后装的就必须重启进程，**光刷新页面没用**。最先查这条。")
            行.append(f"   ① 依赖没装全：{COMFY根}\\custom_nodes\\ComfyUI-Index-TTS\\requirements.txt")
            行.append("      → 在该 ComfyUI 的 python 环境里  pip install -r requirements.txt")
            行.append("   ② 模型没下完（见下面第 3 条）—— 有些实现会在 import 期就校验模型")
            行.append("   ③ 节点源码 import 报错：去看 ComfyUI 控制台/日志里的 Traceback，")
            行.append("      搜 'ComfyUI-Index-TTS' 那几行。")
            行.append("   ④ 装了但没重启 ComfyUI：加完 custom_nodes 必须重启。")

    # 3. 模型
    #    ★ 分两层判：`必需` 是 validate() 会拦的；`深层必需` 是它**不拦**的。
    #      第二层缺了照样「能跑=False」—— 因为实际后果就是跑到一半炸，
    #      体检的意义正是在这里提前拦住，而不是等 ComfyUI 抛一个看不懂的错。
    清 = 模型清单()
    必缺 = [x for x in 清 if x["状态"] == "缺" and x["说明"].startswith("必需")]
    深缺 = [x for x in 清 if x["状态"] == "缺" and x["说明"].startswith("深层必需")]
    可缺 = [x for x in 清 if x["状态"] == "缺" and x["说明"].startswith("可选")]
    在数 = len([x for x in 清 if x["状态"] == "在"]) - 1
    行.append(f"· 模型目录 {COMFY根}\\models\\IndexTTS-2.5 ：{在数} 个文件在，"
              f"{len(必缺)} 个必需缺，{len(深缺)} 个深层必需缺，{len(可缺)} 个可选缺")
    for x in 必缺:
        行.append(f"   ✗ [必需] {x['文件']}")
    for x in 深缺:
        行.append(f"   ✗ [深层必需] {x['文件']}   —— {x['说明'].split('· ', 1)[-1]}")
    for x in 可缺:
        行.append(f"   ✗ [可选] {x['文件']}   —— {x['说明'].split('· ', 1)[-1]}")
    if 深缺:
        行.append("   ★ 注意：这几个 `validate()` **不查**，所以模型加载器会说「齐了」，")
        行.append("      然后一路跑到一半才炸，报错还不会点名缺的是哪个 —— 必须先补上再跑。")
        行.append("      见 知识\\配音.md §〇（「8 vs 11」）。")
    if 必缺 or 深缺:
        能跑 = False
        行.append("   解决（别用节点自带的 TTS2_5_download.py，它会把 bigvgan/w2v-bert 指错仓）：")
        行.append(f"     cd D:\\DSHworkspace\\影匠 ; python 补模型.py 状态   # 先看缺什么")
        行.append("     python 补模型.py                                # 再补齐")

    半截 = _半截下载()
    if 半截:
        行.append(f"· 发现 {len(半截)} 个「下到一半」的缓存文件（.incomplete / .lock）—— 说明之前下载中断过")
        for p in 半截[:4]:
            行.append(f"   · {p}")
        if len(半截) > 4:
            行.append(f"   … 还有 {len(半截)-4} 个")

    # 4. 音色库
    try:
        库 = 载音色库()
        统 = 库.get("统计", {})
        行.append(f"✓ 音色库：{统.get('总数','?')} 条，{统.get('总MB','?')} MB，"
                  f"{统.get('总时长_分','?')} 分钟（生成于 {库.get('生成时间','?')}）")
    except Exception as e:  # noqa: BLE001
        能跑 = False
        行.append(f"✗ 音色库读不了：{e}")

    摘要 = "可以配音" if 能跑 else "现在配不了音（看上面 ✗ 那几行）"
    return {"能跑": 能跑, "报告": 行, "摘要": 摘要}


# ─────────────────────────── 上传参考音频 ───────────────────────────


def _上传(路: Path) -> str:
    """
    把参考音频塞进 ComfyUI 的 input 目录，返回 LoadAudio 要填的文件名。

    中文文件名在 HTTP 头里会炸，所以统一重命名成 `yj_<md5前12位><后缀>`。
    先试 HTTP 上传（走 ComfyUI 自己的 /upload/image，它对任意文件都收）；
    不行就直接拷进 <ComfyUI>\\input\\（本机路径已知，是个可靠兜底）。
    """
    import hashlib
    import mimetypes

    后缀 = 路.suffix.lower()
    名 = "yj_" + hashlib.md5(str(路).encode("utf-8")).hexdigest()[:12] + 后缀
    输入夹 = COMFY根 / "input"     # 只在 HTTP 上传失败时当兜底用，见下面注释

    # ★ 这里原来有一条捷径：「已经在 COMFY根\input 里就不用传了」。
    # 它是错的，而且错得很安静 —— ComfyUI 完全可以用 --input-directory 指向
    # 别的目录（本机跑的这条就是 `D:\Comfy-Desktop\ComfyUI-Shared\input`，
    # 而 COMFY根 是程序目录）。于是：COMFY根\input 里躺着旧文件 → 直接 return
    # → 服务端那份根本不存在 → `LoadAudio` 报
    # `Invalid audio file: yj_xxx.wav`，而报错完全没提「你以为传过了」。
    # 判据必须问**服务端**，不能问本地文件系统 —— 本地有文件不等于服务端看得见。
    # 上传只有几百 KB，省这点时间不值得拿一个静默失败去换。

    try:
        边 = uuid.uuid4().hex
        类 = mimetypes.guess_type(名)[0] or "application/octet-stream"
        身 = (
            f"--{边}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{名}"\r\n'
            f"Content-Type: {类}\r\n\r\n"
        ).encode("utf-8") + 路.read_bytes() + f"\r\n--{边}--\r\n".encode("utf-8")
        请 = urllib.request.Request(
            COMFY.rstrip("/") + "/upload/image", method="POST", data=身,
            headers={"Content-Type": f"multipart/form-data; boundary={边}"},
        )
        with urllib.request.urlopen(请, timeout=180) as 应:
            信 = json.loads(应.read().decode("utf-8"))
        回 = 信.get("name") or 名
        if 信.get("subfolder"):
            回 = f"{信['subfolder']}/{回}"
        return 回
    except Exception as e:  # noqa: BLE001
        上传错 = e

    if 输入夹.is_dir():
        import shutil

        shutil.copy2(路, 输入夹 / 名)
        return 名

    raise RuntimeError(
        f"参考音频传不进 ComfyUI。\n"
        f"  HTTP 上传失败：{上传错}\n"
        f"  而且 {输入夹} 也不存在（或者 COMFY根 猜错了）。\n"
        f"解决：手动把 {路} 拷到 <ComfyUI>\\input\\ 目录里，"
        f"或者设环境变量 影匠_COMFY根 指向真正的 ComfyUI 根目录。"
    )


# ─────────────────────────── 出图 / 取音频 ───────────────────────────


# ── ★ 「后缀名是声明，不是事实」 ──────────────────────────────────────
# 实测踩坑（2026-10-14）：ComfyUI 的 `SaveAudio` 节点**只输出 FLAC**。
#   comfy_extras\nodes_audio.py:159-185
#       class SaveAudio(IO.ComfyNode):
#           display_name="Save Audio (FLAC) (DEPRECATED)"
#           def execute(cls, audio, filename_prefix="ComfyUI", format="flac")
#   而 `SaveAudioAdvanced` 的 format 选项只有 flac / mp3 / opus
#   （comfy_api\latest\_ui.py:259  `_FORMATS = {"flac", "mp3", "opus"}`）——
#   **这个 ComfyUI 根本存不出真 WAV**。
# 于是我这边写死的 `.wav` 后缀在骗人：文件名叫 .wav，字节流是 FLAC。
#   后果：`wave.open()` 直接报 `wave.Error: file does not start with RIFF id`；
#   一切按后缀分支的代码都会分叉（剪映、ffmpeg 包装、别人的脚本）。
# 判据：**读魔数**，不信文件名。

_音频魔数 = (
    (b"RIFF", ".wav", "WAV"),
    (b"fLaC", ".flac", "FLAC"),
    (b"OggS", ".ogg", "OGG"),
    (b"ID3", ".mp3", "MP3"),
    (b"\xff\xfb", ".mp3", "MP3"),
    (b"\xff\xf3", ".mp3", "MP3"),
    (b"\xff\xf2", ".mp3", "MP3"),
    (b"ftyp", ".m4a", "M4A"),
    (b"\x30\x26\xb2\x75", ".wma", "WMA"),
)


def 认音频(身: bytes) -> tuple[str, str]:
    """
    看字节流的头，返回 (真实后缀, 格式名)。**不看文件名。**
    m4a 的 `ftyp` 在第 4 字节起，单独判。
    """
    if len(身) >= 12 and 身[4:8] == b"ftyp":
        return ".m4a", "M4A"
    for 头, 后, 名 in _音频魔数:
        if 身.startswith(头):
            return 后, 名
    return "", f"认不出来（头 16 字节 {身[:16].hex(' ')}）"


def 转真WAV(路: Path) -> tuple[bool, str]:
    """
    把「其实是 FLAC/MP3 的 .wav」转成**真 WAV（PCM_16）**。

    为什么必须转而不是只改后缀：下游（剪映草稿、ffmpeg、别人的 wave.open）
    要的是 RIFF 字节流，不是「文件名带 .wav」。只改后缀 = 换个方式骗人。
    返回 (是否真成了 WAV, 说明)。失败不抛异常 —— 由调用方决定要不要容忍。
    """
    路 = Path(路)
    try:
        真后, 格式 = 认音频(路.read_bytes()[:64])
    except Exception as e:  # noqa: BLE001
        return False, f"读不出来：{type(e).__name__}: {e}"
    if 真后 == ".wav":
        return True, "本来就是 WAV"
    if not 真后:
        return False, 格式

    try:
        import soundfile as sf

        数据, 采样率 = sf.read(str(路), always_2d=True)
        临时 = 路.with_name(路.stem + ".__转wav临时__")
        sf.write(str(临时), 数据, 采样率, subtype="PCM_16", format="WAV")
        # 先写临时文件再换名：中途炸了不会把原文件毁掉
        临时.replace(路)
        return True, f"{格式} → WAV（{采样率} Hz · {数据.shape[1]} 声道 · {len(数据) / 采样率:.3f} 秒）"
    except Exception as e:  # noqa: BLE001
        return False, f"{格式} 转 WAV 失败：{type(e).__name__}: {str(e)[:120]}"


def _取音频(文件名: str, 子目录: str = "", 类型: str = "output", 存到: Path | None = None,
           要真WAV: bool = True) -> Path:
    """
    把 ComfyUI 的输出取回来落盘。

    ★ 行为与第一版不同（2026-10-14 改）：**按魔数定后缀，必要时转真 WAV**。
      第一版直接 `存到.write_bytes(身)`，于是 FLAC 顶着 `.wav` 的名字进了磁盘。
    `要真WAV=True`（默认）：落到 `.wav` 就保证是 RIFF；原始格式不是 wav 就先落原格式、
      转完再改成 `.wav`。转换失败就把原格式留着（后缀也是真的），并打一行字说明。
    """
    参 = urllib.parse.urlencode({"filename": 文件名, "subfolder": 子目录, "type": 类型})
    身 = _请求(f"/view?{参}", 超时=600, 原始=True)
    真后, 格式 = 认音频(身)

    if 存到 is None:
        配音输出.mkdir(parents=True, exist_ok=True)
        基 = Path(文件名)
        存到 = 配音输出 / ((基.stem + 真后) if 真后 else 基.name)
    存到 = Path(存到)
    # ★ 拦一道：调用方给的落盘路径如果**指向一个已存在的目录**，说明那里本来
    #   应该是个文件名（实测踩过：音色词带 `\` 被净化成空，落点变成 `001_\`）。
    #   直接报出来，别让它 write_bytes 出一个叫 `001_` 的**目录**。
    if 存到.is_dir() or (存到.exists() and not 存到.is_file()):
        raise RuntimeError(
            f"落盘路径指向一个已存在的目录，不是文件：{存到}\n"
            f"  ——多半是调用方把「音色名/相对路径」直接拿去拼文件名了。"
            f"用 配音.净名(音色) 净化一下再拼。"
        )
    存到.parent.mkdir(parents=True, exist_ok=True)

    if 真后 == ".wav" or not 真后:
        存到.write_bytes(身)            # 已经是 WAV，或者认不出来（原样落，别乱改）
        if not 真后:
            print(f"  ⚠ 取回的音频{格式} —— 原样落盘成 {存到.name}，没敢改后缀")
        return 存到

    # 原始格式不是 WAV：先落原格式（名字与内容一致），再决定要不要转
    原路 = 存到.with_suffix(真后)
    原路.write_bytes(身)
    if not 要真WAV:
        return 原路

    if 存到.suffix.lower() != ".wav":
        # 调用方没点名要 wav（比如自己给了 .flac），那就把真格式给他，别多事
        return 原路

    ok, 说 = 转真WAV(原路)
    if ok:
        原路.replace(存到)
        return 存到
    print(f"  ⚠ 取回的是 {格式}，转真 WAV 没成功（{说}）—— 保留 {原路.name}，后缀是真的")
    return 原路


def _派工音频(工作流: dict, 上限秒: int = 1800, 报=None) -> dict:
    """
    提交工作流并等它跑完，**收集 audio 类输出**（引擎.派工 只收 images/gifs，
    收不到音频，所以这里自己来）。返回 {"音频":[{文件名,子目录,类型}], "耗时", "字幕"}。
    """
    编号 = uuid.uuid4().hex
    应 = _请求("/prompt", {"prompt": 工作流, "client_id": 编号}, 超时=60)
    提示号 = 应.get("prompt_id")
    if not 提示号:
        节点错 = 应.get("node_errors") or 应.get("error") or 应
        raise RuntimeError(f"ComfyUI 拒绝了这张工作流：{json.dumps(节点错, ensure_ascii=False)[:900]}")

    起 = time.time()
    上次 = 0
    while True:
        历 = _请求(f"/history/{提示号}", 超时=30)
        条 = 历.get(提示号)
        if 条:
            状 = 条.get("status", {}) or {}
            if 状.get("status_str") == "error":
                for 信, 详 in 状.get("messages", []):
                    if 信 == "execution_error":
                        raise RuntimeError(
                            "IndexTTS 执行失败："
                            + json.dumps(详, ensure_ascii=False)[:900]
                            + "\n常见原因：模型文件缺/坏（跑 python 配音.py 体检）、显存不够、"
                              "参考音频格式怪。"
                        )
                raise RuntimeError(f"工作流跑挂了：{json.dumps(状, ensure_ascii=False)[:900]}")

            出 = 条.get("outputs", {}) or {}
            音 = []
            字 = ""
            for _, 节 in 出.items():
                for 键 in ("audio", "audios", "gifs"):
                    for x in 节.get(键, []) or []:
                        if isinstance(x, dict) and x.get("filename"):
                            音.append({
                                "文件名": x["filename"],
                                "子目录": x.get("subfolder", ""),
                                "类型": x.get("type", "output"),
                            })
                if isinstance(节.get("text"), list) and 节["text"]:
                    字 = str(节["text"][0])
            if 音 or 状.get("completed"):
                if not 音:
                    raise RuntimeError(
                        "跑完了但没有音频输出。检查工作流末尾接的是不是 SaveAudio"
                        "（或者换一个保存音频的节点）。"
                    )
                return {"音频": 音, "耗时": round(time.time() - 起, 2), "字幕": 字}

        过 = time.time() - 起
        if 过 > 上限秒:
            raise RuntimeError(f"等了 {上限秒} 秒还没跑完（提示号 {提示号[:8]}）。第一句往往最慢（要加载模型）。")
        if 报 and time.time() - 上次 > 5:
            上次 = time.time()
            try:
                队 = _请求("/queue", 超时=10)
                报(f"… 已等 {过:.0f}s（排队 {len(队.get('queue_pending', []))}，运行中 {len(队.get('queue_running', []))}）")
            except Exception:  # noqa: BLE001
                pass
        time.sleep(2)


# ─────────────────────────── 工作流拼装 ───────────────────────────


def _找文本预览节点() -> str | None:
    """
    找一个「能把 STRING 显示出来」的节点，用它把 IndexTTS 的 subtitle 输出带回来。
    /history 只回传 ui 段，普通 RETURN 拿不到，所以必须借道一个预览节点。
    找不到就返回 None（那就自己切句生成 SRT）。
    """
    for 名 in ("PreviewAny", "ShowText|pysssss", "ShowText", "DisplayText"):
        if 节点规格(名):
            return 名
    return None


def _语速转因子(语速: float) -> float:
    """影匠的「语速」（>1 更快）转 IndexTTS 的 duration_factor（>1 更慢）。"""
    语速 = max(0.1, float(语速))
    因 = 1.0 / 语速
    if 因 < 语速下限 or 因 > 语速上限:
        raise ValueError(f"语速 {语速} 超出 IndexTTS 支持范围（duration_factor 只能是 "
                         f"{语速下限}–{语速上限}，对应语速 {1/语速上限:.2f}–{1/语速下限:.2f}）")
    return round(因, 4)


def 净名(词: str, 上限: int = 24) -> str:
    """
    把任意一串东西（音色名/相对路径/角色名）变成**一个安全的文件名主干**。

    ★ 为什么必须有这个函数（实测 bug，2026-10-14）：
      lead 传的音色是 `男女——情绪分类\\女-常规-清冷无情-2-1.wav`（带子目录的相对路径）。
      原来的代码是 `re.sub(r'[^\\w\\u4e00-\\u9fa5]', '', str(音))[:12]`：
      反斜杠被删掉、中文字符也被删掉（Python 的 `re` 里 `\\u4e00` 在**字符类**里
      会被当字面反斜杠+u+4+e+0+0，不是「汉字区间」），于是名字只剩 `21wa`。
      再拼上 `夹 / f"{序:03d}_{名字}.wav"` —— **一个字符都没有，只剩目录前缀**，
      结果 `001_` 变成**目录**，真正的音频落进 `001_\\21wa.wav`。
      人眼看到的是「四个空目录」，不是报错。这就是「静默错误」的又一次发作。
    这里改为：先把路径分隔符换成 `_`，**字母数字汉字以外的字符全部去掉**（用真的
    Unicode 汉字区间），长度截断，空的话给个兜底名。
    """
    s = str(词 or "").strip()
    s = s.replace("\\", "_").replace("/", "_")          # 路径分隔符先变可见字符
    s = Path(s).stem if ("." in s.rsplit("_", 1)[-1]) else s   # 去掉扩展名（如 _2-1.wav）
    s = re.sub(r"[^\w\u4e00-\u9fff]", "", s, flags=re.UNICODE)
    s = s.strip("_") or "音色"
    return s[:上限]


def _独前缀() -> str:
    """
    给 ComfyUI 的 SaveAudio 生成**每次都不一样**的 filename_prefix。

    ★ 为什么（实测）：默认前缀写死 `影匠配音/配音`，ComfyUI 遇到重名会自己加序号
      （于是服务器上堆出 `配音_00001.flac`…`配音_00008.flac`）。
      文件名不重复是对的，但它带来的副作用是：我这边**没法事先知道**服务器会叫哪个名字，
      只能跑完去 `/history` 里问。问回来的名字是对的（不会取错文件），
      但同一前缀跨批次复用，出问题时排查很痛苦 —— 分不清哪个文件属于哪次调用。
      这里带 6 位随机后缀，让「服务器上的文件」与「这一次调用」一一对应。
    """
    import uuid as _uuid

    return f"影匠配音/配音_{_uuid.uuid4().hex[:6]}"


def 拼工作流(文本: str, 参考名: str, 语言: str = "ZH", 语速: float = 1.0,
            情感=None, 情感权重: float = 1.0, 种子: int | None = None,
            前缀: str | None = None, 保留显存: bool = True,
            参数: dict | None = None) -> dict:
    """
    拼一张 IndexTTS-2.5 工作流。**不改任何文件**，只返回 dict。

    结构：
        LoadAudio(参考音频) ──┐
                              ├─→ IndexTTS25*Node ─→ SaveAudio
        [可选] 情感来源 ──────┘

    情感 可以是：
        None                       → 基础节点
        "她很生气地说"  (字符串)    → 情感文本节点（★需 Qwen 情感模型）
        {"高兴":0.7,"悲伤":0.2}     → 情感向量节点（8 滑条）
        {"音频": "路径", "权重":0.8} → 情感参考音频节点

    `前缀=None`（默认）会生成**唯一**前缀（见 `_独前缀()`）。
    """
    if 语言 not in 语言表:
        raise ValueError(f"语言只能是 {'/'.join(语言表)}，给的是「{语言}」")
    if not (文本 or "").strip():
        raise ValueError("文本是空的")

    参 = 参考音频(参考名)
    文件名 = _上传(Path(参["路径"]))
    因子 = _语速转因子(语速)

    公共 = {
        "text": 文本,
        "reference_audio": ["1", 0],
        "lang": 语言,
        "duration_factor": 因子,
        "do_sample_mode": "on",
        "temperature": 0.8,
        "top_p": 0.8,
        "top_k": 30,
        "num_beams": 3,
        "repetition_penalty": 10.0,
        "length_penalty": 0.0,
        "max_mel_tokens": 1500,
        "max_tokens_per_sentence": 120,
        "interval_silence_ms": 200,
        "text_normalization": True,
        "seed": 0 if 种子 is None else int(种子),
    }
    if 参数:
        公共.update(参数)

    节 = {
        "1": {"class_type": 加载音频节点, "inputs": {"audio": 文件名}},
    }

    感情节 = None
    if 情感 is None:
        类名 = 基础节点
    elif isinstance(情感, str):
        类名 = 文本情感节点
        公共["emotion_description"] = 情感
    elif isinstance(情感, dict) and "音频" in 情感:
        类名 = 音频情感节点
        公共["emotion_weight"] = float(情感.get("权重", 情感权重))
        公共["emo_ref_audio"] = ["1b", 0]
        感情节 = {"1b": {"class_type": 加载音频节点,
                        "inputs": {"audio": _上传(Path(str(情感["音频"])))}}}
    elif isinstance(情感, dict):
        类名 = 向量节点
        for k, v in 情感.items():
            真 = 情感中文.get(str(k))
            if 真 is None:
                raise ValueError(f"不认识的情感维度「{k}」。可用：{'/'.join(情感维)}，或中文 "
                                 f"{'/'.join(情感中文.keys())}")
            公共[真] = max(0.0, min(1.0, float(v)))
        for 维 in 情感维:
            公共.setdefault(维, 0.0)
    else:
        raise ValueError(f"情感参数看不懂：{情感!r}")

    if 保留显存:
        公共["cache_control"] = {"keep_cached": True}

    if 感情节:
        节.update(感情节)

    节["2"] = {"class_type": 类名, "inputs": 公共}
    节["3"] = {"class_type": 保存音频节点,
              "inputs": {"audio": ["2", 0], "filename_prefix": 前缀}}

    预览 = _找文本预览节点()
    if 预览:
        节["4"] = {"class_type": 预览, "inputs": {"value": ["2", 2]}}

    return 节


# ─────────────────────────── 合成 ───────────────────────────


def 合成(文本: str, 音色: str, 语言: str = "ZH", 语速: float = 1.0,
        情感=None, 种子: int | None = None, 存到: str | os.PathLike | None = None,
        保留显存: bool = True, 上限秒: int = 1800, 要真WAV: bool = True, 报=None) -> dict:
    """
    合一句词 → 一个音频文件。

    ★ 产物格式（2026-10-14 改）：**默认保证真 WAV（RIFF / PCM_16）**。
      ComfyUI 的 SaveAudio 只存 FLAC，所以这里落盘后会自动转一次；
      转不了就保留原格式并把后缀改对（`.flac`），绝不留下「名叫 .wav 的 FLAC」。
      要原样拿 FLAC（省一次转码）就传 `要真WAV=False`。

    返回 {"路","文件名","秒","音色","参考","种子","耗时","字幕","文本","提示"}
    跑不通就抛 RuntimeError，但**一定是人话**（先做体检，缺什么直接说）。
    """
    # 先体检，缺什么直接说，别等 ComfyUI 报一串堆栈
    检 = 体检()
    if not 检["能跑"]:
        raise RuntimeError("现在配不了音：\n  " + "\n  ".join(检["报告"]))

    参 = 参考音频(音色)
    工作流 = 拼工作流(文本, 音色, 语言=语言, 语速=语速, 情感=情感,
                     种子=种子, 保留显存=保留显存)

    try:
        果 = _派工音频(工作流, 上限秒=上限秒, 报=报)
    except RuntimeError as e:
        if "cache_control" in str(e):
            # 有些 ComfyUI 版本不接受裸 DICT，去掉重试一次
            if 报:
                报("cache_control 被拒，去掉参数重试…")
            工作流 = 拼工作流(文本, 音色, 语言=语言, 语速=语速, 情感=情感,
                             种子=种子, 保留显存=False)
            果 = _派工音频(工作流, 上限秒=上限秒, 报=报)
        else:
            raise

    出 = 果["音频"][0]
    目标 = Path(存到) if 存到 else None
    路 = _取音频(出["文件名"], 出["子目录"], 出["类型"], 目标, 要真WAV=要真WAV)

    秒 = _探秒(路)
    提示 = list(参["提示"])
    if 秒 and 文本:
        字每 = len(_净字(文本)) / 秒
        if 语速 == 1.0 and 字每 > 8:
            提示.append(f"· 语速偏快（{字每:.1f} 字/秒）——IndexTTS 念快时容易吞字，可以调低语速")
        elif 语速 == 1.0 and 字每 < 2.5:
            提示.append(f"· 语速偏慢（{字每:.1f} 字/秒）——可以调高语速，或者检查 duration_factor")

    return {
        "路": str(路),
        "文件名": 路.name,
        "秒": 秒,
        "音色": 参["名字"],
        "参考": 参["路径"],
        "种子": 种子,
        "耗时": 果["耗时"],
        "字幕": 果["字幕"],
        "文本": 文本,
        "提示": 提示,
    }


def _探秒(路: Path) -> float | None:
    """读音频时长。soundfile → av → mutagen，都拿不到就 None，绝不瞎编。"""
    try:
        import soundfile as sf

        return round(float(sf.info(str(路)).duration), 3)
    except Exception:  # noqa: BLE001
        pass
    try:
        import av

        with av.open(str(路)) as 罐:
            if 罐.duration:
                return round(罐.duration / av.time_base, 3)
    except Exception:  # noqa: BLE001
        pass
    try:
        import mutagen

        信 = mutagen.File(str(路))
        if 信 is not None and 信.info:
            return round(float(信.info.length), 3)
    except Exception:  # noqa: BLE001
        pass
    return None


# ─────────────────────────── 批量 / 字幕 ───────────────────────────


_标点 = set(" \t\r\n，。！？、；：“”‘’（）《》〈〉…—－·,.!?;:()[]{}<>\"'`~@#$%^&*_+=|\\/-")


def _净字(文本: str) -> str:
    """去掉空白和标点，只留实字。用来估时长、算语速。"""
    return "".join(c for c in (文本 or "") if c not in _标点)


def 估时长(文本: str, 语速: float = 1.0) -> float:
    """
    没跑合成之前，先毛估一句台词的时长（秒）。
    IndexTTS 中文常见 3.5–5 字/秒；这里按 4 字/秒 + 0.4 秒气口。
    只用来排时间轴，**不是**实测值 —— 真有 wav 了就用 _探秒()。
    """
    字 = len(_净字(文本))
    return round(max(1.2, 字 / 4.0 / max(0.1, 语速) + 0.4), 2)


def _切句(文本: str) -> list[str]:
    部 = re.split(r"(?<=[。！？!?…；;])", (文本 or "").strip())
    出 = [x.strip() for x in 部 if x.strip()]
    if 出:
        return 出
    return [文本.strip()] if (文本 or "").strip() else []


def 写SRT(段们: list[dict], 路: str | os.PathLike) -> Path:
    """
    写一个 srt。

    段们 = [{"文本": "…", "起": 0.0, "时长": 2.3}, …]
    如果某段有 "字幕"（IndexTTS 真返回的），优先用它。
    没有精确时间的话，按字符数在 "时长" 里等比分配。
    """
    def 时刻(秒: float) -> str:
        秒 = max(0.0, float(秒))
        时 = int(秒 // 3600)
        分 = int(秒 % 3600 // 60)
        剩 = 秒 % 60
        return f"{时:02d}:{分:02d}:{int(剩):02d},{int(round((剩 - int(剩)) * 1000)):03d}"

    行 = []
    for i, 段 in enumerate(段们, 1):
        文 = (段.get("字幕") or 段.get("文本") or "").strip()
        if not 文:
            continue
        起 = float(段.get("起", 0.0))
        长 = float(段.get("时长") or 估时长(文))
        句们 = _切句(文)
        总字 = sum(len(s) for s in 句们) or 1
        游 = 起
        for 句 in 句们:
            份 = 长 * (len(句) / 总字)
            if len(句们) == 1:
                行.append(f"{i}\n{时刻(起)} --> {时刻(起 + 长)}\n{句}\n")
            else:
                行.append(f"{i}\n{时刻(游)} --> {时刻(游 + 份)}\n{句}\n")
                游 += 份
    路 = Path(路)
    路.parent.mkdir(parents=True, exist_ok=True)
    路.write_text("\n".join(行), encoding="utf-8")
    return 路


def 批量(台词表: list[dict], 输出目录: str | os.PathLike | None = None,
        保留显存: bool = True, 写字幕: bool = True, 要真WAV: bool = True, 报=None) -> dict:
    """
    一次配一整场。

    台词表 = [{"序号":1, "台词":"…", "音色":"…", "语言":"ZH", "语速":1.0, "情感":None}, …]

    ★「音色」那一格也可以填【角色名】—— 会先查 音色\\角色映射.json（G5）。
      填角色名的好处：音色由映射表统一决定，换音色只改一处；
      而且没有映射时**降级成原来的行为**（当音色名做模糊匹配），不会把整批弄崩。

    返回 {"配音":[{序号, 文本, 路, 秒, 音色, 错}], "srt", "总时长"}
    —— 某一句炸了**不中断整批**，错误记在那一句的 "错" 里，最后一起报。
    `秒` 可以直接喂给 剪映.py 的镜头["时长"]，实现音画对齐。
    """
    夹 = Path(输出目录).expanduser() if 输出目录 else (配音输出 / time.strftime("批次%Y%m%d_%H%M%S"))
    夹.mkdir(parents=True, exist_ok=True)

    映射 = 载映射()
    出 = []
    游 = 0.0
    前一句 = None

    for i, 台 in enumerate(台词表, 1):
        序 = 台.get("序号", i)
        文 = (台.get("台词") or 台.get("文本") or "").strip()
        # G5：先把「角色」解析成音色（命中映射表就用映射的），没给角色就沿用原来的音色词
        原词 = 台.get("音色") or (台.get("角色") if 台.get("角色") else None) or 前一句
        音, 怎么来 = 角色定音色(原词, 映射) if 原词 else (None, "")
        # 如果映射没命中，但这一句明确给了「角色」而没给「音色」，把角色名也当音色词试一次
        #   —— 这样「凌霜」这种既在映射表里、又可能正好是个音色名的词，两头都不会漏
        if not 怎么来 and 台.get("角色") and not 台.get("音色"):
            音, 怎么来 = 台["角色"], "角色名当音色词"
        if not 文:
            出.append({"序号": 序, "文本": "", "路": None, "秒": 0.0, "音色": 音, "错": "空台词"})
            continue
        if not 音:
            出.append({"序号": 序, "文本": 文, "路": None, "秒": 估时长(文), "音色": None,
                        "错": "没给音色，而且前面也没有可以参考的音色"})
            游 += 估时长(文)
            continue

        前一句 = 音
        # ★ 用 净名() 净化：音色词可能是带子目录的相对路径（如 `男女——情绪分类\女-…wav`），
        #   原来的正则会把中文和路径分隔符都删光，只剩 `21wa` —— 甚至拼出空目录名。
        #   详见 净名() 的注释（那次实测 bug）。
        目标 = 夹 / f"{int(序):03d}_{净名(音, 上限=16)}.wav"
        if 报:
            标 = f"（角色「{台.get('角色')}」）" if 怎么来 == "映射" else ""
            报(f"[{i}/{len(台词表)}] {音}{标} ← {文[:24]}{'…' if len(文) > 24 else ''}")
        try:
            果 = 合成(文, 音, 语言=台.get("语言", "ZH"), 语速=台.get("语速", 1.0),
                     情感=台.get("情感"), 种子=台.get("种子"), 存到=目标,
                     保留显存=保留显存, 要真WAV=要真WAV, 报=报)
            秒 = 果["秒"] or 估时长(文)
            出.append({"序号": 序, "文本": 文, "路": 果["路"], "秒": 秒,
                        "音色": 果["音色"], "字幕": 果["字幕"], "错": None, "提示": 果["提示"],
                        "角色": 台.get("角色"), "音色来源": 怎么来 or "直接给音色"})
        except Exception as e:  # noqa: BLE001
            秒 = 估时长(文)
            出.append({"序号": 序, "文本": 文, "路": None, "秒": 秒, "音色": 音, "错": str(e),
                        "角色": 台.get("角色"), "音色来源": 怎么来 or "直接给音色"})
        游 += 秒

    果 = {"配音": 出, "总时长": round(游, 2), "目录": str(夹), "srt": None}
    # 角色解析小账：一眼看出哪几句的音色是映射给的、哪几句是角色名直接当音色词用的、
    # 哪几句压根没解析出来（后者最危险 —— 它会走模糊匹配，可能配错人）。
    没解析 = [(x["序号"], x.get("角色"), x.get("音色")) for x in 出
              if x.get("角色") and x.get("音色来源") in ("角色名当音色词", "")]
    果["角色解析"] = {
        "映射命中": sum(1 for x in 出 if x.get("音色来源") == "映射"),
        "角色名当音色词": sum(1 for x in 出 if x.get("音色来源") == "角色名当音色词"),
        "直接给音色": sum(1 for x in 出 if x.get("音色来源") == "直接给音色"),
        "没解析出来": 没解析,
        "映射表": str(映射路) if 映射.get("角色") else None,
    }
    if 没解析:
        print(f"  ⚠ 有 {len(没解析)} 句的角色没在映射表里命中，已当音色名做模糊匹配："
              f"{'、'.join(str(x[1]) for x in 没解析[:6])}")
        print(f"     要么把角色加进 {映射路}，要么在那句里直接写音色名。")
    if 写字幕:
        行 = []
        起 = 0.0
        for 条 in 出:
            if 条["文本"]:
                行.append({"文本": 条["文本"], "字幕": 条.get("字幕"), "起": 起, "时长": 条["秒"]})
            起 += 条["秒"]
        果["srt"] = str(写SRT(行, 夹 / "台词.srt"))
    return 果


# ─────────────────────────── 自测 ───────────────────────────


def _打印体检(细: bool = False) -> bool:
    检 = 体检(细=细)
    print("=" * 70)
    print("配音.py 环境体检")
    print("=" * 70)
    for 行 in 检["报告"]:
        print("  " + 行)
    print("-" * 70)
    print("  结论：" + 检["摘要"])
    print("=" * 70)
    return 检["能跑"]


def 自查() -> int:
    """
    全流程自查。**不需要模型下完**：模型不在就验证「人话报错」这条路走通没有。
    返回 0 = 通过。
    """
    print("=" * 70)
    print("配音.py 自查")
    print("=" * 70)
    问题 = []

    # 1. 音色库
    print("\n[1/6] 音色库")
    try:
        库 = 载音色库()
        统 = 库.get("统计", {})
        print(f"    总数 {统.get('总数')}  总时长 {统.get('总时长_分')} 分钟  平均 {统.get('平均时长_秒')} 秒")
        print(f"    根目录 {库.get('根目录')}")
    except Exception as e:  # noqa: BLE001
        问题.append(f"音色库读不了：{e}")
        print(f"    ✗ {e}")
        return 1

    # 2. 找音色
    print("\n[2/6] 找音色")
    for 词 in ("温柔", "旁白", "男"):
        候 = 找音色(词, 限=3)
        if 候:
            print(f"    「{词}」→ {', '.join(str(c.get('名字')) for c in 候)}")
        else:
            print(f"    「{词}」→ 无候选（不算错，词太偏）")

    全部 = 库.get("音频", [])
    样本 = None
    for 条 in 全部:
        if 条.get("秒") and 2 <= 条["秒"] <= 15:
            样本 = 条
            break
    if 样本 is None:
        问题.append("音色库里找不到 2–15 秒的样本用于测试")
    else:
        try:
            参 = 参考音频(str(样本.get("名字")))
            print(f"    参考音频：{参['名字']}  {参['秒']}s  {参['路径'][:78]}")
            for t in 参["提示"]:
                print(f"      {t}")
        except Exception as e:  # noqa: BLE001
            问题.append(f"参考音频() 失败：{e}")
            print(f"    ✗ {e}")

    # 3. 体检
    print("\n[3/6] ComfyUI / 节点 / 模型 体检")
    能跑 = _打印体检()
    print(f"    （能跑={能跑}；这一项**不算自查失败** —— 自查要验的是「编排对不对」，"
          f"不是「模型下没下完」）")

    # 4. 拼工作流（不提交）
    print("\n[4/6] 拼工作流（只拼不提交）")
    if 样本 is not None:
        try:
            流 = 拼工作流("你好，我是影匠。", str(样本.get("名字")), 语速=1.0,
                        情感={"高兴": 0.6, "平静": 0.3})
            节点们 = [(k, v["class_type"]) for k, v in sorted(流.items())]
            print(f"    {len(流)} 个节点：{节点们}")
            主 = 流["2"]["inputs"]
            print(f"    text={主['text']!r}  lang={主['lang']}  duration_factor={主['duration_factor']}")
            print(f"    8 维情感：{ {k: 主[k] for k in 情感维} }")
            assert 主["duration_factor"] == 1.0
            assert 流["3"]["inputs"]["audio"] == ["2", 0]
            print("    ✓ 结构自洽（SaveAudio 接在节点 2 的第 0 个输出上）")
        except Exception as e:  # noqa: BLE001
            问题.append(f"拼工作流失败：{e}")
            print(f"    ✗ {e}")
    else:
        print("    （没有样本音色，跳过）")

    # 5. 语速换算 + 估时长 + 切句 + SRT
    print("\n[5/6] 语速换算 / 估时长 / SRT")
    print(f"    语速 1.0 → duration_factor {_语速转因子(1.0)}")
    print(f"    语速 1.25 → duration_factor {_语速转因子(1.25)}（>1 变快 = 因子 <1）")
    print(f"    语速 0.8 → duration_factor {_语速转因子(0.8)}")
    try:
        _语速转因子(9.0)
        问题.append("语速 9.0 本该报错却没报")
    except ValueError as e:
        print(f"    ✓ 语速 9.0 被正确拦下：{str(e)[:60]}…")

    台词 = "她缓缓转过头来。窗外，雪落了一整夜。"
    print(f"    估时长：「{台词}」→ {估时长(台词)} 秒；切句 → {_切句(台词)}")

    import tempfile

    临时 = Path(tempfile.mkdtemp(prefix="yj_dubbing_"))
    srt = 写SRT([
        {"文本": "她缓缓转过头来。", "起": 0.0, "时长": 2.4},
        {"文本": "窗外，雪落了一整夜。", "起": 2.4, "时长": 3.0},
    ], 临时 / "台词.srt")
    正 = srt.read_text(encoding="utf-8")
    print(f"    写了 SRT：{srt}（{len(正)} 字符）")
    print("    ---")
    for 行 in 正.strip().split("\n")[:8]:
        print("    " + 行)
    print("    ---")
    if "-->" not in 正:
        问题.append("SRT 里没有 --> 时间轴")

    # 6. 假数据跑一遍批量（模型在就跑真合成，不在就验证「人话报错 + 不中断」）
    print("\n[6/6] 批量（假数据）")
    假 = [
        {"序号": 1, "台词": "她缓缓转过头来。", "音色": str(样本.get("名字")) if 样本 else "缺"},
        {"序号": 2, "台词": "窗外，雪落了一整夜。", "音色": str(样本.get("名字")) if 样本 else "缺"},
        {"序号": 3, "台词": ""},
    ]
    try:
        果 = 批量(假, 输出目录=临时 / "配音", 写字幕=True, 报=lambda m: print("      " + m))
        print(f"    目录：{果['目录']}")
        print(f"    总时长（含估算）：{果['总时长']} 秒    srt：{果['srt']}")
        # ★ 第 3 句是**故意留空**的测试夹具（验「空台词被隔离、不占时间轴」）——
        #   它报错是设计要的，不是问题。只有「有词儿却失败」才叫真问题。
        有词失败 = [条 for 条 in 果["配音"] if 条.get("错") and (条.get("文本") or "").strip()]
        空句报错 = [条 for 条 in 果["配音"] if 条.get("错") and not (条.get("文本") or "").strip()]
        for 条 in 果["配音"]:
            if 条.get("错"):
                if not (条.get("文本") or "").strip():
                    因 = "预期（这句是故意留空的夹具）"
                elif not 能跑:
                    因 = "预期（环境还没齐，见上面体检）"
                else:
                    因 = "★ 环境是齐的、这句有词儿，不该失败 —— 真问题"
                print(f"    · 第{条['序号']} 句 → 失败[{因}]：{str(条['错']).splitlines()[0][:70]}")
            else:
                print(f"    · 第{条['序号']} 句 → {条['路']}  {条['秒']}s")
        if not any(条.get("错") for 条 in 果["配音"]) and not 能跑:
            问题.append("环境不齐却全部成功，不合常理")
        if 能跑 and 有词失败:
            问题.append(f"环境齐了，但有 {len(有词失败)} 句有词儿的台词失败了 —— 自查本该全通")
        if not 空句报错:
            问题.append("故意留空的那句没有按预期被隔离（空台词应当报错并跳过）")
    except Exception as e:  # noqa: BLE001
        import traceback

        问题.append(f"批量() 崩了（应该被内部吃掉才对）：{e}")
        traceback.print_exc()

    print("\n" + "=" * 70)
    if 问题:
        print(f"自查发现问题 {len(问题)} 个：")
        for x in 问题:
            print("  ✗ " + x)
        return 1
    print("自查通过。")
    if not 能跑:
        print("提示：真合成还跑不了 —— 按上面体检报告把缺失的模型下完、把节点加载起来。")
    print(f"临时产物：{临时}")
    return 0


# ─────────────────────────── 命令行 ───────────────────────────


def _主() -> int:
    参 = sys.argv[1:]
    if not 参:
        print(__doc__)
        return 0
    令 = 参[0]

    if 令 in ("体检", "check"):
        _打印体检(细="-v" in 参)
        return 0 if 体检()["能跑"] else 3

    if 令 in ("查", "找"):
        if len(参) < 2:
            print("用法：python 配音.py 查 <词>")
            return 1
        for c in 找音色(参[1], 限=15):
            print(f"  {c.get('名字','')[:28]:30s} {str(c.get('秒')):>7}s  "
                  f"{c.get('大类',''):6s} {c.get('路径','')}")
        return 0

    if 令 in ("试", "跑"):
        if len(参) < 2:
            print("用法：python 配音.py 试 \"台词\" --音色 名字 [--语言 ZH] [--语速 1.0]")
            return 1
        文 = 参[1]
        音 = None
        语 = "ZH"
        速 = 1.0
        i = 2
        while i < len(参):
            if 参[i] == "--音色" and i + 1 < len(参):
                音 = 参[i + 1]; i += 2
            elif 参[i] == "--语言" and i + 1 < len(参):
                语 = 参[i + 1]; i += 2
            elif 参[i] == "--语速" and i + 1 < len(参):
                速 = float(参[i + 1]); i += 2
            else:
                i += 1
        if not 音:
            print("必须给 --音色（先用 python 配音.py 查 <词> 找）")
            return 1
        try:
            果 = 合成(文, 音, 语言=语, 语速=速, 报=lambda m: print("  " + m))
        except Exception as e:  # noqa: BLE001
            print("\n配不了：")
            print(str(e))
            return 3
        print(f"\n出好了：{果['路']}  {果['秒']} 秒  用了 {果['耗时']}s")
        for t in 果["提示"]:
            print("  " + t)
        return 0

    if 令 in ("自查", "自测", "selftest"):
        return 自查()

    if 令 in ("音色", "列表"):
        for n in 音色清单()[:40]:
            print("  " + n)
        print(f"  … 共 {len(音色清单())} 条")
        return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(_主())
