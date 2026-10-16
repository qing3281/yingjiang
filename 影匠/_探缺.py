# -*- coding: utf-8 -*-
"""_探缺.py —— 把「跑一次合成才发现缺一个包」变成「一次问清楚还缺哪些包」。

为什么要它（实测教训，2026-10-14 凌晨）：
    真跑 IndexTTS-2.5 合成时，连着死在
        No module named 'audiotools'
        No module named 'absl'
        No module named 'kaldifst'
        No module named 'contractions'
    每死一次都要等 14~58 秒（ComfyUI 排队 + 加载 9 GB 权重）才知道下一个缺谁。
    更贵的是：`补模型.py 验` 当时报「三关全过、退出码 0、可以合成」，
    **一跑就死** —— 因为那三关只查模型文件，一个字都没查 Python 依赖。

真正的错不是「缺得多」，而是「**判据来得太晚**」：
包缺不缺，在 `import` 那一刻就有答案，不需要真跑一遍合成。

两关（与 `补模型.py 验` 的三关拼成一条链）：
    第 4 关 · 依赖关：读节点自带的 requirements.txt，逐个查**是否已安装**
                      （用 importlib.metadata 查分发名，**不 import**，所以又快又不炸）
    第 5 关 · 冒烟关：把合成链上真正会走的模块**真 import 一遍**
                      （查「装了但装坏了 / 名字对不上 / 子模块缺失」）

用法（python 必须是 ComfyUI 自己那个 .venv 的解释器）：
    python _探缺.py            两关都跑，逐行报 ✓ / ✗
    python _探缺.py --静默      只报 ✗
    python _探缺.py --依赖关    只跑第 4 关（秒级）
退出码：0 = 两关全过；1 = 有缺；3 = requirements.txt 都找不到。
"""
from __future__ import annotations

import contextlib
import importlib
import importlib.metadata as md
import io
import os
import re
import sys
import types

这里 = os.path.dirname(os.path.abspath(__file__))
COMFY根 = os.environ.get(
    "影匠_COMFY根", r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
)
节点名 = "ComfyUI-Index-TTS"
需求文件 = os.path.join(COMFY根, "custom_nodes", 节点名, "requirements.txt")

# 分发名（PyPI）→ 导入名，两边不一致的才要写在这里
分发名到导入名 = {
    "openai-whisper": "whisper",
    "descript-audiotools": "audiotools",
    "pyyaml": "yaml",
    "g2p-en": "g2p_en",
    "docstring-parser": "docstring_parser",
    "absl-py": "absl",
    "flatten-dict": "flatten_dict",
    "unidic-lite": "unidic_lite",
    "soundfile": "soundfile",
    "huggingface-hub": "huggingface_hub",
    "scikit-learn": "sklearn",
}

# ---------------------------------------------------------------------------
# 第 5 关：合成链上真正会走的模块 —— 每条注释写明「谁会 import 它」
# ---------------------------------------------------------------------------
要试 = [
    # --- 环境自身 ---
    ("torch", "推理后端"),
    ("torchaudio", "音频读写"),
    ("numpy", "张量"),
    ("transformers", "GPT2 / w2v-bert 模型定义"),

    # --- s2mel / dac 编解码链（第一、二个断点都在这一串）---
    ("audiotools", "dac 读 AudioSignal / ml.BaseModel"),
    ("audiotools.ml", "dac/__init__.py:8 摸 audiotools.ml.BaseModel.INTERN"),
    ("audiotools.core.util", "dac/utils/encode.py:9 from audiotools.core import util"),
    ("absl", "audiotools → tensorboard → absl"),
    ("tensorboard", "audiotools 的 SummaryWriter 路径"),
    ("flatten_dict", "audiotools/core/util.py:17 from flatten_dict import flatten"),
    ("julius", "audiotools 内部重采样"),
    ("pyloudnorm", "audiotools 响度"),
    ("pystoi", "audiotools 指标"),
    ("randomname", "audiotools 内部命名"),
    ("markdown2", "audiotools 报告"),
    ("argbind", "audiotools 配置绑定"),
    ("einops", "s2mel / bigvgan 张量重排"),

    # --- 文本前端（第三、四个断点：kaldifst、contractions）---
    ("wetext", "中英文本正则化"),
    ("wetext.utils", "wetext/utils.py:21 import contractions ← 第四个断点在这"),
    ("contractions", "wetext 英文缩写展开"),
    ("kaldifst", "wetext 的 FST 后端"),
    ("cn2an", "中文数字归一化"),
    ("jieba", "中文分词"),
    ("tiktoken", "multilingual_zh_ja_yue_char_del.tiktoken 分词表"),
    ("g2p_en", "英语 G2P（CMU 音素）"),
    ("inflect", "英语数词"),
    ("fugashi", "日语分词"),
    ("unidic_lite", "日语词典"),

    # --- 配置 / 权重 / 音频 IO ---
    ("omegaconf", "config.yaml"),
    ("munch", "配置点号访问"),
    ("json5", "config.yaml 的 json5 方言"),
    ("modelscope", "部分权重走 modelscope 仓"),
    ("soundfile", "音频读写（转真 WAV 也靠它）"),
    ("librosa", "重采样"),
    ("scipy", "信号处理"),
    ("safetensors", "权重读取"),
    ("huggingface_hub", "w2v-bert / bigvgan 拉取"),
    ("accelerate", "Qwen 情感模型 device_map"),

    # --- 只有 Emotion Text 节点要的 ---
    ("matplotlib", "BigVGAN utils 画图"),
]

# 只做「找得到吗」，不真 import 的模块。
# 理由逐条（都实测过）：
#   whisper / g2p_en —— import 会触发 nltk 联网下载语料（raw.githubusercontent.com 连不上，
#                       会重试到跑不完：实测 10 分钟没回来）
#   torch / transformers / matplotlib —— import 要几十秒，情报价值只有「在不在」
#   numba —— import 会 JIT 预热
只查在不在 = {"torch", "torchaudio", "torchvision", "transformers", "matplotlib",
              "whisper", "g2p_en", "numba", "nltk", "scipy", "librosa"}


def 桩server() -> None:
    """把 server.PromptServer 桩掉，否则节点包在 import 阶段就炸。

    节点包在**模块级**写了 `@PromptServer.instance.routes.get("/indextts25/voice_files")`
    （indextts2_5_voice_nodes.py:137），而 `instance` 只有 ComfyUI 服务起来才有。
    不桩就报 `AttributeError: type object 'PromptServer' has no attribute 'instance'`
    —— 那是「服务器没起」，不是缺陷。

    ★ 坑：`instance` 挂在**类对象**上，必须 `_PS.instance = _PS()`；
      写成 `PromptServer().instance = ...` 不管用。
    """
    if "server" in sys.modules:
        return

    class _Routes:
        def get(self, *a, **k):
            return lambda f: f

        def post(self, *a, **k):
            return lambda f: f

    class _PS:
        instance = None

        def __init__(self) -> None:
            self.routes = _Routes()

    m = types.ModuleType("server")
    _PS.instance = _PS()
    m.PromptServer = _PS
    sys.modules["server"] = m


def 试导入(名: str) -> tuple[bool, str]:
    """**真 import** 一次 —— 只给「轻、且自己不会联网」的模块用。

    ★ 为什么默认不用它：实测 `import whisper` 会连带触发
      `nltk.download('cmudict')` 去 raw.githubusercontent.com，本机连不上 →
      重试到天荒地老（跑了 10 分钟没回来）。`import g2p_en` 也会打一堆警告。
      所以重模块一律先走 `find_spec`（见 `试找得到`），只在必要时真 import。
    这里仍然把 stdout/stderr 按掉，免得模块自己刷屏。
    """
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            importlib.import_module(名)
    except ModuleNotFoundError as e:
        return False, f"No module named '{e.name}'"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:90]}"
    return True, ""


def 试找得到(名: str) -> tuple[bool, str]:
    """**不执行**模块代码，只问解释器「这个模块找得到吗」。

    这就是第一关「包缺不缺」的正确答案：找得到 = 包在；
    至于它 import 进来会不会炸（缺子模块、版本不合），由 `试导入` 管。
    速度是毫秒级，且**绝不联网**。
    """
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            找到了 = importlib.util.find_spec(名)
    except ModuleNotFoundError as e:
        return False, f"No module named '{e.name}'"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:90]}"
    if 找到了 is None:
        return False, "找不到（find_spec 返回 None）"
    return True, ""


# ---------------------------------------------------------------------------
# 第 4 关：纯查「装了没」，不 import（秒级，且不会因为副作用炸）
# ---------------------------------------------------------------------------

def 读需求(路: str) -> list[tuple[str, str, str]]:
    """读 requirements.txt → [(分发名, 版本要求, 原始行)]，跳过注释/空行/平台不适用行。"""
    if not os.path.isfile(路):
        return []
    出 = []
    with open(路, encoding="utf-8") as f:
        for 行 in f:
            行 = 行.split("#", 1)[0].strip()
            if not 行 or 行.startswith("-"):
                continue
            # 跳过平台标记不命中的（如 pynini==2.1.6; platform_system!="Windows"）
            if ";" in 行:
                包部, 标记 = 行.split(";", 1)
                if "Windows" in 标记 and "!=" in 标记:
                    continue          # platform_system!="Windows" → Windows 上不装
                if "Windows" in 标记 and "==" in 标记 and "!=" not in 标记:
                    pass              # platform_system=="Windows" → 装
                行 = 包部.strip()
            if 行.startswith("git+"):     # git+https://…#egg=xxx
                m = re.search(r"egg=([A-Za-z0-9_.\-]+)", 行)
                if m:
                    出.append((m.group(1), "", 行))
                continue
            名 = re.split(r"[<>=!~\[]", 行, maxsplit=1)[0].strip()
            if not 名:
                continue
            版本 = 行[len(名):].strip()
            出.append((名, 版本, 行))
    # 去重（requirements.txt 里真的有重复行，实测 librosa/soundfile/omegaconf 各两遍）
    见 = set()
    独 = []
    for x in 出:
        if x[0].lower() in 见:
            continue
        见.add(x[0].lower())
        独.append(x)
    return 独


def 装了没(分发名: str) -> tuple[bool, str]:
    try:
        版本 = md.version(分发名)
        return True, 版本
    except md.PackageNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        return False, f"查询出错：{type(e).__name__}"
    # 名字对不上时，用「导入名」再试一次
    导入名 = 分发名到导入名.get(分发名.lower(), 分发名.replace("-", "_"))
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            importlib.import_module(导入名)
        return True, "（按导入名命中）"
    except Exception:  # noqa: BLE001
        return False, ""


def 第4关(静默: bool) -> list[str]:
    print("  ── 第 4 关 · 依赖关：节点 requirements.txt 里的包都装了吗 ──")
    件 = 读需求(需求文件)
    if not 件:
        print(f"  ✗ 读不到 {需求文件}")
        return ["<requirements.txt 不在>"]
    缺 = []
    for 名, 版本, 原 in 件:
        ok, 有 = 装了没(名)
        if ok:
            if not 静默:
                print(f"  ✓ {名:<24} {有}")
        else:
            print(f"  ✗ {名:<24} 没装        ← requirements.txt 要求 {版本 or '(任意)'}")
            缺.append(名)
    print(f"     —— 共 {len(件)} 个包：{len(件) - len(缺)} 装了，{len(缺)} 没装")
    return 缺


def 第5关(静默: bool) -> list[str]:
    print("  ── 第 5 关 · 冒烟关：合成链上的模块都在不在、轻的再真 import 一遍 ──")
    print("     （重模块只做 find_spec「找得到吗」—— 真 import 它们会联网/吃几分钟；")
    print("       标注「只查在不在」的就是这类。轻模块才是真 import。）")
    缺 = []
    for 名, 为什么 in 要试:
        只查 = 名 in 只查在不在
        ok, 错 = 试找得到(名) if 只查 else 试导入(名)
        if ok:
            if not 静默:
                标 = "只查在不在" if 只查 else "真 import ✓"
                print(f"  ✓ {名:<24} {标}")
        else:
            print(f"  ✗ {名:<24} {错:<34} ← {为什么}")
            缺.append(名)
    # 节点包本身（桩完 server 才试）—— 这个必须真 import，否则等于没验
    ok包, 错包 = 试导入(节点名)
    if ok包:
        if not 静默:
            print(f"  ✓ {节点名}（20 个节点整体 import 通过）")
    else:
        print(f"  ✗ {节点名:<24} {错包:<34} ← 节点包本身")
        缺.append(节点名)
    print(f"     —— 共 {len(要试) + 1} 项：{len(要试) + 1 - len(缺)} 通过，{len(缺)} 缺")
    return 缺


def 断网() -> None:
    """把「会自己联网的重试」全部掐掉。

    实测：`import whisper` 会去 raw.githubusercontent.com 下 cmudict，连不上就重试，
    10 分钟不回来 —— 一个本该 3 秒的体检变成跑不完。
    这里不追求真断网，只要求「**连不上就立刻报错，别重试**」：
    给 NLTK 指一个空目录，给 HF 打开离线开关。副作用只在本进程内。
    """
    空 = os.path.join(这里, "_work", "空nltk")
    os.makedirs(空, exist_ok=True)
    os.environ["NLTK_DATA"] = 空
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def main() -> int:
    os.chdir(COMFY根)
    for p in (COMFY根, os.path.join(COMFY根, "custom_nodes")):
        if p not in sys.path:
            sys.path.insert(0, p)
    断网()
    桩server()

    静默 = "--静默" in sys.argv
    print("=" * 100)
    print("  影匠 · 依赖体检（_探缺.py）—— 补模型.py 那三关之后再补这两关")
    print("=" * 100)

    只依赖 = "--依赖关" in sys.argv
    缺4 = 第4关(静默)
    print()
    缺5 = [] if 只依赖 else 第5关(静默)

    缺 = 缺4 + [x for x in 缺5 if x not in 缺4]
    print()
    print("=" * 100)
    if not 缺:
        print("  ✓ 两关全过 —— 依赖齐了。可以跑：python 真实试音.py \"雪落无声，剑亦无声。\"")
        return 0
    print(f"  ✗ 还缺 {len(缺)} 项：{'、'.join(缺)}")
    print("  ★ 补装一律加 --no-deps：这个 venv 里 torch 2.12.1+cu130 / numpy 2.5.2 /")
    print("     transformers 5.16.1 是 ComfyUI 自己在用的版本，绝不能被依赖解析拉低。")
    print("     例：python -m pip install --no-input --no-deps " + " ".join(缺[:6]))
    print("  ★ 装完**要重启 ComfyUI 进程**（custom_nodes 的 import 只在启动时做一次）。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
