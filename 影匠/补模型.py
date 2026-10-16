"""影匠 · IndexTTS-2.5 模型补全 / 状态检查

用法（在 D:\\DSHworkspace\\影匠 下，用 ComfyUI 的 venv python）：
    python 补模型.py 状态          只看缺什么、有多少到位（零下载）
    python 补模型.py               按下面的顺序把缺的补齐
    python 补模型.py gpt           只下文件名含 "gpt" 的
    python 补模型.py --小件        只下 < 8 MB 的小件（验证通路，几秒钟）

为什么是 python 不是 ps1：
    本机 PowerShell 执行策略禁止运行 .ps1（跑 .ps1 报 PSSecurityException），
    且 PS 5.1 读 UTF-8无BOM 的中文会乱码。python 没这两个问题。

## 上一版为什么全下不动（已定位的真因，别再犯）

1) **`_并行下.py` 的 CLI 是 `<url> <目标文件> [份数]`，不是 `<目标文件> [份数]`。**
   上一版把文件路径当 URL 传进去，于是每次都是
   `curl: (3) URL rejected: Port number was not a decimal number between 0 and 65535`，
   curl 重试 10 次、每次退避 5 秒 —— 表现就是「进程活着、一个字节不进」。
   → 大文件现在直接调 `_并行下.拉(url, 目标, 份数, 预期)`，不拼命令行。

2) **`_下模型.py` 的 indextts 清单把 bigvgan / w2v-bert 指向了主仓，而它们不在主仓。**
   实测对 `IndexTeam/IndexTTS-2.5` 发 HEAD：
       bigvgan/bigvgan_generator.pt   → HTTP 404，Content-Length 15
       bigvgan/config.json            → HTTP 404，Content-Length 15
       w2v-bert-2.0/model.safetensors → HTTP 404，Content-Length 15
       w2v-bert-2.0/config.json       → HTTP 404，Content-Length 15
   而 `_下模型.py` 都不带 `--fail`，curl 会把那 15 字节的 "Entry not found" **当成功存成文件**。
   → 本脚本给每个文件单独记来源仓，不按前缀猜。

3) **`--speed-limit` / `--speed-time` 套在小文件上会假报 404。**
   实测：`bigvgan/config.json` 单独跑是 `HTTP=200 size_download=1405 exit=0`，
   但在 8 路分片抢带宽时被那对速度开关按「太慢」中止，curl 返回 **exit 22**，
   和小文件走错仓时的 404 长得一模一样。→ 小文件不带速度保护，只留宽松 `--max-time`。

4) **本机 PowerShell 执行策略禁止 .ps1**，所以入口只能是 .py。

必须守住的三条（实测踩出来的）：
    1) HF_HUB_DISABLE_XET=1 —— hf-mirror 后面 xet 后端会静默卡死
       （证据：模型目录里留下 hf_cache\\xet\\logs\\xet_20261014T003457025+0800_30740.log，622,113 B）
    2) 小文件（< 8 MB）绝不分片 —— 4 路拉 1,369 B 的 config.json 会拼出 5.49 KB = 4 倍
    3) 续传只认 .parts\\ 里的正式分片大小，绝不按目标文件大小判

## 为什么要加 safetensors **头校验**（Lead 在远端的实测教训）

Lead 用同一套算法扫远端模型库，6 个 `.safetensors` 里 **2 个是残缺的**：
    z_image_turbo_int8_convrot.safetensors      969,932,800 / 6,201,001,296 = 15.6%
    umt5_xxl_fp8_e4m3fn_scaled.safetensors    3,853,414,400 / 6,735,906,897 = 57.2%
这两个文件 `exists()` 为真、大小非零、ComfyUI 照列不误，
但一加载就 `Tensor 'layers.11.attention.out.weight' extends past the end of the file`。

→ **「文件存在」≠「文件对」，而「大小对上」也只是对上了一个我们以为的数。**
   `.safetensors` 是**自描述**的：头里写着每块张量的 `data_offsets`，
   所以「本该多大」可以**算出来**，不必信任何外部清单 —— 这才是真判据。
   比 `exists()` 强，比 `torch.load()` 快得多（只读头，不把 5 GB 读进内存）。

算法（`引擎.py 模型完好()` / `_work\\扫模型.py` 同源）：
    前 8 字节 = 小端 uint64 头长 L → 读 L 字节 JSON 张量表
    应 = max(8 + L + data_offsets[1])   # 跳过 __metadata__
    应 == 实际字节数 才算完好
"""

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

这里 = Path(__file__).resolve().parent

# 落地相对路径 -> (远程真实字节数, 来源仓, 仓内路径, 是否必需, 说明)
#
# ⚠ 为什么落地路径和仓内路径要**分开写**（这是踩出来的）：
#   bigvgan/* 和 w2v-bert-2.0/* 的落地是带目录的（`w2v-bert-2.0/model.safetensors`），
#   但它们在各自真身仓里是**仓根**文件（`model.safetensors`）。
#   早先把落地路径直接拼到 URL 上，拼出了
#       https://hf-mirror.com/facebook/w2v-bert-2.0/resolve/main/w2v-bert-2.0/preprocessor_config.json
#   多了一层目录 → HTTP 404、15 字节 → curl --fail 报 exit 22，
#   看起来像「镜像没有这个文件」，其实是自己拼错的。
#   字节数都是 curl -sIL HEAD 实测（2026-10-14）。
清单: dict[str, tuple[int, str, str, bool, str]] = {
    # ── 必需：主仓 IndexTeam/IndexTTS-2.5（仓内路径 == 落地路径）──
    "gpt.pth": (
        3259599833,
        "IndexTeam/IndexTTS-2.5",
        "gpt.pth",
        True,
        "GPT 自回归主模型，最大头",
    ),
    "s2mel.pth": (
        414908601,
        "IndexTeam/IndexTTS-2.5",
        "s2mel.pth",
        True,
        "s2mel 语义转梅尔",
    ),
    "qwen0.6bemo4-merge/model.safetensors": (
        1192135096,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/model.safetensors",
        True,
        "Qwen 情感文本分析权重（不用 Emotion Text 节点可省）",
    ),
    # ── 必需：★ 不在主仓，且落地要带目录、仓内是仓根文件 ──
    "bigvgan/bigvgan_generator.pt": (
        449228171,
        "nvidia/bigvgan_v2_22khz_80band_256x",
        "bigvgan_generator.pt",
        True,
        "BigVGAN 神经声码器权重",
    ),
    "bigvgan/config.json": (
        1405,
        "nvidia/bigvgan_v2_22khz_80band_256x",
        "config.json",
        True,
        "声码器超参",
    ),
    "w2v-bert-2.0/model.safetensors": (
        2322063736,
        "facebook/w2v-bert-2.0",
        "model.safetensors",
        True,
        "Wav2Vec2Bert 语义特征主干",
    ),
    "w2v-bert-2.0/config.json": (
        1874,
        "facebook/w2v-bert-2.0",
        "config.json",
        True,
        "w2v 配置",
    ),
    "w2v-bert-2.0/preprocessor_config.json": (
        275,
        "facebook/w2v-bert-2.0",
        "preprocessor_config.json",
        True,
        "w2v 前处理配置（SeamlessM4TFeatureExtractor 要读）",
    ),
    "campplus_cn_common.bin": (
        28036335,
        "funasr/campplus",
        "campplus_cn_common.bin",
        True,
        "CAMPPlus 说话人向量",
    ),
    # ── 可选：节点自带的 TTS2_5_download.py 会带它，但 infer_v2_5.py 只用
    #          SeamlessM4TFeatureExtractor + Wav2Vec2BertModel.from_pretrained，
    #          两者读 config/preprocessor_config/model.safetensors 即可，用不到它。
    #          单独列出来是为了「要就下、不要就跳过」有据可依，且省 2.17 GB。
    "w2v-bert-2.0/conformer_shaw.pt": (
        2329131983,
        "facebook/w2v-bert-2.0",
        "conformer_shaw.pt",
        False,
        "w2v 的 shaw 相对位置权重 —— 本节点用不到，默认不下",
    ),
    # ── 已齐（列出只为状态表完整 + 防止将来误删）──
    "codec.pth": (607290935, "IndexTeam/IndexTTS-2.5", "codec.pth", True, "音频 codec"),
    "config.yaml": (2860, "IndexTeam/IndexTTS-2.5", "config.yaml", True, "主配置"),
    "feat1.pt": (57170, "IndexTeam/IndexTTS-2.5", "feat1.pt", True, "特征统计 1"),
    "feat2.pt": (374866, "IndexTeam/IndexTTS-2.5", "feat2.pt", True, "特征统计 2"),
    "wav2vec2bert_stats.pt": (
        9343,
        "IndexTeam/IndexTTS-2.5",
        "wav2vec2bert_stats.pt",
        True,
        "w2v 归一化统计",
    ),
    "multilingual_zh_ja_yue_char_del.tiktoken": (
        907395,
        "IndexTeam/IndexTTS-2.5",
        "multilingual_zh_ja_yue_char_del.tiktoken",
        True,
        "多语 tokenizer",
    ),
    "qwen0.6bemo4-merge/tokenizer.json": (
        11422654,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/tokenizer.json",
        True,
        "",
    ),
    "qwen0.6bemo4-merge/merges.txt": (
        1671853,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/merges.txt",
        True,
        "",
    ),
    "qwen0.6bemo4-merge/vocab.json": (
        2776833,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/vocab.json",
        True,
        "",
    ),
    "qwen0.6bemo4-merge/tokenizer_config.json": (
        5433,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/tokenizer_config.json",
        True,
        "",
    ),
    "qwen0.6bemo4-merge/added_tokens.json": (
        707,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/added_tokens.json",
        True,
        "",
    ),
    "qwen0.6bemo4-merge/special_tokens_map.json": (
        616,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/special_tokens_map.json",
        True,
        "",
    ),
    "qwen0.6bemo4-merge/chat_template.jinja": (
        550,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/chat_template.jinja",
        True,
        "",
    ),
    "qwen0.6bemo4-merge/Modelfile": (
        360,
        "IndexTeam/IndexTTS-2.5",
        "qwen0.6bemo4-merge/Modelfile",
        True,
        "",
    ),
}

模型目录 = Path(
    r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\IndexTTS-2.5"
)
镜像 = "https://hf-mirror.com"
CURL = r"C:\WINDOWS\system32\curl.exe"
小文件界 = 8 * 1024 * 1024


def 址(仓: str, 路径: str) -> str:
    return f"{镜像}/{仓}/resolve/main/{路径}"


def 量(path: Path) -> tuple[int, int]:
    """返回 (目标文件字节, .parts 分片+临时块合计字节)。"""
    单 = path.stat().st_size if path.exists() else 0
    分 = 0
    目 = Path(str(path) + ".parts")
    if 目.is_dir():
        for f in 目.rglob("*"):
            if f.is_file():
                try:
                    分 += f.stat().st_size
                except OSError:
                    pass
    return 单, 分


def 头校验(p: Path) -> tuple[bool, str]:
    """`.safetensors` 自描述头校验：算出「本该多大」，跟实际字节数比。

    返回 (好, 说明)。非 safetensors 或文件不存在都返回 (True, '')——**不管**，
    因为调用方是按扩展名决定要不要调它的。

    为什么需要它（Lead 远端实测，6 个里 2 个残缺）：
        `exists()` 真、大小非零、ComfyUI 照列不误 —— 但一加载就
        `Tensor 'layers.11.attention.out.weight' extends past the end of the file`。
        **「文件存在」≠「文件对」**；而 `.safetensors` 自带「本该多大」的答案，
        算出来比信任何清单都硬。只读头（几 KB），**不把 5 GB 读进内存**。
    """
    if p.suffix.lower() != ".safetensors" or not p.is_file():
        return True, ""
    实际 = p.stat().st_size
    try:
        with p.open("rb") as fh:
            头 = fh.read(8)
            if len(头) < 8:
                return False, f"文件太短，读不出头（{实际:,} 字节）"
            长 = struct.unpack("<Q", 头)[0]
            if 长 <= 0 or 长 > 200_000_000:
                return False, f"头长不合理 {长}（{实际:,} 字节）"
            表 = json.loads(fh.read(长).decode("utf-8"))
        应 = 8 + 长
        for k, v in 表.items():
            if k == "__metadata__" or not isinstance(v, dict):
                continue
            o = v.get("data_offsets")
            if o and len(o) >= 2:
                应 = max(应, 8 + 长 + int(o[1]))
    except Exception as e:  # noqa: BLE001
        return False, f"头读不了：{type(e).__name__}: {str(e)[:80]}"
    if 应 == 实际:
        return True, f"头校验 ✓ {实际:,} 字节"
    return False, f"头校验 ✗ 残缺：实际 {实际:,} / 应 {应:,}（只到 {实际 / 应:.1%}，缺 {应 - 实际:,} 字节）"


def 清单_校验(p: Path) -> str:
    """给状态表用的一列：`✓` / `✗残缺` / 空（非 safetensors）。"""
    if p.suffix.lower() != ".safetensors" or not p.is_file():
        return ""
    好, 说 = 头校验(p)
    return "✓" if 好 else "✗残缺"


def 查状态() -> int:
    print("=" * 108)
    print("IndexTTS-2.5 模型状态：" + str(模型目录))
    print("=" * 108)
    print(f"{'状态':<7}{'校验':<8}{'必需':<5}{'文件':<44}{'到位':>14}{'应有':>14}{'进度':>7}  {'载体':<7}来源")
    print("-" * 108)
    差总 = 0
    硬缺 = 0
    坏件: list[str] = []
    for 名, (要, 仓, 仓内, 必需, 注) in 清单.items():
        p = 模型目录 / 名
        单, 分 = 量(p)
        到位 = max(单, 分)
        完整 = 单 == 要
        # ★ 「大小对上」还不够 —— safetensors 再验一次自描述头
        校 = 清单_校验(p) if 完整 else ""
        if 校 == "✗残缺":
            坏件.append(名)
        if not 完整:
            差总 += max(0, 要 - 到位)
            if 必需:
                硬缺 += 1
        标 = "✓完整" if 完整 else ("◐断点" if 到位 > 0 else "✗没有")
        进度 = f"{100.0 * 到位 / 要:6.1f}%" if 要 else "   n/a"
        载 = "分片" if 分 > 0 else "单文件"
        print(
            f"{标:<7}{校:<8}{'必需' if 必需 else '可选':<5}{名:<44}{到位:>14,}{要:>14,}{进度}  {载:<7}{仓}"
        )
        if 注 and not 完整:
            print(f"       └─ {注}")
        if 校 == "✗残缺":
            好, 说 = 头校验(p)
            print(f"       └─ ★ {说}  ← 大小对上了，**内容还是坏的**，必须重下")
    print("-" * 108)
    print(f"必需件还缺 {硬缺} 个；合计还差 {差总 / 1024**3:.2f} GB")
    if 坏件:
        print(f"★ 头校验不过 {len(坏件)} 个：{'、'.join(坏件)}")
        print("  这些文件 `exists()` 为真、大小也对，但一加载就 "
              "`Tensor '…' extends past the end of the file` —— 删掉重下。")
    print("提示：◐断点 的行有 .parts\\ 分片，续传会接着下，**不要删 .parts\\**。")
    return 硬缺


def 下小件(名: str, 要: int, 仓: str, 仓内: str) -> bool:
    """小文件单连接。分片会把它拉成 N 倍（实测 4 路 1,369 B → 5.49 KB）。

    ⚠ 这里**故意不带 --speed-limit / --speed-time**。
    那两个开关是为「几个 GB 的大文件卡死」设计的：掉到 10 KB/s 以下持续 90 秒就自杀。
    套到 1.4 KB 的 config.json 上就是个陷阱 —— 在 8 路分片抢带宽的时候，
    小文件很容易 90 秒内传不完，curl 直接按「太慢」中止并返回 **exit 22**，
    看起来像 404，其实文件本身 200/1405 字节完全正常（实测：
    同一个 URL 单独跑 `-o NUL` 是 HTTP=200 size_download=1405 exit=0）。
    小文件总耗时本来就是毫秒级，不需要速度保护，只需要给一个宽松的 --max-time 兜底。
    """
    目标 = 模型目录 / 名
    目标.parent.mkdir(parents=True, exist_ok=True)
    # 小文件不支持续传（几 KB 的东西没必要），残留半截先清掉，
    # 免得下一轮把半截当完整、或者 curl 拿到错位的 -C 偏移
    if 目标.exists() and 目标.stat().st_size != 要:
        目标.unlink()
    u = 址(仓, 仓内)
    命令 = [
        CURL,
        "-L",
        "--fail",  # ★ 必须：没它就会把 404 的 15 字节 "Entry not found" 存成文件
        "--no-progress-meter",
        "--retry",
        "10",
        "--retry-delay",
        "3",
        "--retry-all-errors",
        "--connect-timeout",
        "30",
        "--max-time",
        "300",
        "-o",
        str(目标),
        u,
    ]
    r = subprocess.run(命令)
    if r.returncode != 0:
        print(f"    ✗ curl 退出码 {r.returncode}")
        # 半截小文件留着没用，删掉免得被后一轮误认成完整
        if 目标.exists():
            目标.unlink()
        return False
    n = 目标.stat().st_size
    if 要 and n != 要:
        print(f"    ✗ 大小不符：{n:,} ≠ {要:,}，删掉重来")
        目标.unlink()
        return False
    print(f"    ✓ {n:,} 字节")
    return True


def 下大件(名: str, 要: int, 仓: str, 仓内: str, 份数: int = 8) -> bool:
    """大文件走 _并行下.拉（8 路分片 + .parts 续传 + 大小校验后才替换）。"""
    sys.path.insert(0, str(这里))
    import _并行下

    目标 = 模型目录 / 名
    目标.parent.mkdir(parents=True, exist_ok=True)
    p = Path(str(目标))
    单, _ = 量(p)
    # ⚠ 单连接留下的半截跟分片方案对不上，且没有 .parts 就无从续传 —— 清掉重来
    if 单 and not Path(str(目标) + ".parts").is_dir():
        print(f"    清掉单连接留下的半截 {单:,} 字节，改用分片")
        目标.unlink()
    u = 址(仓, 仓内)
    print(f"    {u}")
    return bool(_并行下.拉(u, str(目标), 份数=份数, 预期=要))


def 排序键(名: str, 要: int) -> int:
    """下件顺序（★ 不是「按大小升序」那么简单 —— 见下）。

    为什么不能纯按大小升序排（这是 Lead 批准的改动，理由是实测出来的）：
        `infer_v2_5.py` 初始化要读 **11 件**，而 `validate()` 只查 **8 件**。
        多出来的 3 件里 `w2v-bert-2.0/model.safetensors`(2.32 GB) 若排在最后，
        就会经历「下完 3.26 GB 的 `gpt.pth` → `validate()` 说齐了 → 一跑在第 80% 炸」
        —— 而且报错不会告诉你就差那 2.32 GB。
        所以 **w2v-bert 必须排在 gpt.pth 前面**：让「validate 说齐」的那一刻是真的齐。
        （更糟的是 `infer_v2_5.py:169-177` 只看目录在不在，目录一旦存在就
          `local_files_only=True`，把联网兜底整个绕过 —— 「目录在但内容不全」比
          「目录不在」更难修。详见 知识\\配音.md §4.6.-3。）
        `qwen0.6bemo4-merge/*` 只为 Emotion Text 节点服务，与主链路无关，压到最后。

    分档：
        第 1 档（0）：< 小文件界 的小件 —— 秒级完成，先把通路验通
        第 2 档（1）：w2v-bert-2.0/model.safetensors（2.32 GB）
        第 3 档（2）：gpt.pth（3.26 GB，最大头）
        第 4 档（3）：其余大件（同档内按大小升序）
        第 5 档（4）：qwen0.6bemo4-merge/*
    """
    if 名.startswith("qwen0.6bemo4-merge/"):
        return 4
    if 要 < 小文件界:
        return 0
    if 名 == "w2v-bert-2.0/model.safetensors":
        return 1
    if 名 == "gpt.pth":
        return 2
    return 3


def 下(过滤: str = "", 只小件: bool = False) -> int:
    os.environ["HF_HUB_DISABLE_XET"] = "1"  # ★ 必须
    失败: list[str] = []
    顺序 = sorted(
        清单.items(),
        key=lambda kv: (排序键(kv[0], kv[1][0]), kv[1][0]),
    )
    for 名, (要, 仓, 仓内, 必需, 注) in 顺序:
        if 过滤 and 过滤.lower() not in 名.lower():
            continue
        if 只小件 and 要 >= 小文件界:
            continue
        p = 模型目录 / 名
        单, _ = 量(p)
        if 单 == 要:
            print(f"[跳过] {名} 已完整")
            continue
        print(f"\n=== 下 {名}  ({要 / 1024**2:.2f} MB)  {注} ===")
        print(f"    来源仓 {仓}  /  仓内 {仓内}")
        print("    " + ("单连接（小文件）" if 要 < 小文件界 else "8 路分片（可续传）"))
        ok = 下小件(名, 要, 仓, 仓内) if 要 < 小文件界 else 下大件(名, 要, 仓, 仓内)
        if not ok:
            print(f"    ✗ {名} 没下完")
            失败.append(名)
        else:
            print(f"    ✓ {名} 完成")
            # ★ 下完立刻验一次「内容」—— 别等合成时报一个看不懂的错。
            #   大小对上了也只说明下到了预期长度，说明不了内容是对的。
            好, 说 = 头校验(模型目录 / 名)
            if 说:
                print(f"      {说}")
            if not 好:
                print("      ★ 这个文件必须重下（删掉再跑本脚本）")
                失败.append(名 + "（头校验不过）")
    print("\n=== 结束 ===")
    查状态()
    if 失败:
        print("失败件：" + "、".join(失败))
        return 1
    return 0


# ═══════════════════════════════════════════════════════════════════════════
# 验：三关闸门
#
#   「下完就验、验不过就重下」是**一条闭环**，所以它跟「补」在同一个文件里，
#   不拆成两个 —— 拆了以后一定会有人只跑其中一个。
#
#   为什么是**三关**而不是一个 True：
#       我们这一晚被「一个判据说三种谎」坑了好几轮。
#       `exists()` 说真但内容是坏的；`validate()` 说齐但少查 3 件；
#       大小对上但 `torch.load` 炸。每一种都要**分开报**、**分开给退出码**：
#
#       退出码   含义                        下一步
#       0        三关全过                    可以合成
#       2        还缺件                      跑 `python 补模型.py` 续下（别删 .parts\）
#       3        齐了但加载炸                文件是坏的，删那一个再下
#       4        节点没加载（**没测**）      重启 ComfyUI 进程（刷新页面没用）
#
#   ★ 第 3 关是**唯一不撒谎的判据**，前两关只是前置筛。这句话必须留在输出里，
#     不然下一个人又会拿「11 件齐了」当结论。
# ═══════════════════════════════════════════════════════════════════════════

# 第 3 关要真加载的文件。`gpt.pth` / `s2mel.pth` / `codec.pth` 都是 pickle 打包的
# state_dict，**没有 safetensors 那种自描述头** —— 所以「大小对上」之后仍然可能是坏的，
# 只有真读一次才知道。safetensors 由第 1 关的头校验覆盖，这里不必重复读 3 GB。
真加载件 = (
    "gpt.pth",
    "s2mel.pth",
    "codec.pth",
    "bigvgan/bigvgan_generator.pt",
    "campplus_cn_common.bin",
    "wav2vec2bert_stats.pt",
    "feat1.pt",
    "feat2.pt",
)


def 探一个(p: Path) -> tuple[str, str]:
    """真 `torch.load` 一次（`mmap=True`：只按需映射，不把 3 GB 读进内存）。

    **只读** —— 不写、不删、不替换，所以下载进行中也能安全跑。
    """
    if not p.is_file():
        return "跳过", "文件不在"
    try:
        import torch
    except Exception as e:  # noqa: BLE001
        return "没测", f"没装 torch：{e}"
    try:
        sd = torch.load(str(p), map_location="cpu", mmap=True, weights_only=True)
    except Exception as e:  # noqa: BLE001
        话 = f"{type(e).__name__}: {str(e)[:150]}"
        # pickle 里带自定义类时 weights_only=True 会被拒 —— 那是「读法不对」，
        # 不是「文件坏」，所以放开再试一次，别把可用的文件误判成坏的。
        if ("WeightsUnpickler" in 话) or ("weights_only" in 话) or ("Unsupported global" in 话):
            try:
                sd = torch.load(str(p), map_location="cpu", mmap=True)
            except Exception as e2:  # noqa: BLE001
                return "✗", f"真加载失败（放开 weights_only 也不行）：{type(e2).__name__}: {str(e2)[:150]}"
        else:
            return "✗", f"真加载失败：{话}"
    if isinstance(sd, dict):
        if not sd:
            return "✗", "读出来是空 dict"
        键 = list(sd.keys())
        try:
            形 = tuple(sd[键[0]].shape)
        except Exception:  # noqa: BLE001
            形 = ()
        return "✓", f"{len(键)} 个张量 · 首键 {键[0]} {形}"
    if isinstance(sd, (list, tuple)):
        return "✓", f"{type(sd).__name__}，{len(sd)} 个元素"
    return "✓", f"读出来是 {type(sd).__name__}"


def 节点在不在() -> tuple[bool, str]:
    """问 ComfyUI 的 `/object_info` 有没有 IndexTTS 的节点。

    为什么用 `curl` 而不是 `urllib`：本机 `.venv` 的证书链对 127.0.0.1 的
    自签同样会挑剔，而 `配音.py` 里已经用 curl 走通了同一条路，保持一致。
    """
    try:
        r = subprocess.run(
            [CURL, "-s", "--max-time", "20", "http://127.0.0.1:8188/object_info"],
            capture_output=True, timeout=40,
        )
        if r.returncode != 0:
            return False, f"curl 退出码 {r.returncode}（ComfyUI 没在跑？）"
        文 = r.stdout.decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return False, f"问不到：{type(e).__name__}: {str(e)[:80]}"
    中 = [n for n in ("IndexTTS25BaseNode", "IndexTTS25EmotionAudioNode",
                      "IndexTTS25EmotionVectorNode", "IndexTTS25EmotionTextNode",
                      "IndexTTS25CacheControlNode") if n in 文]
    if not 中:
        return False, "/object_info 里 IndexTTS* 命中 0 个"
    return True, "已加载：" + "、".join(中)


def 第二关(stub: bool = True) -> tuple[str, str]:
    """`model_loader.validate()` 亲口说齐 —— 用桩测，不启服务。

    它只查 8 件、**不查** w2v-bert / bigvgan / campplus 那 3 件（见 知识\\配音.md §〇
    「8 vs 11」）。所以它说「齐」**只是前置筛**，不代表能跑。
    """
    try:
        sys.path.insert(0, str(这里))
    except Exception as e:  # noqa: BLE001
        return "没测", f"准备失败：{e}"
    # 桩：`indextts2_5_voice_nodes.py:137` 在模块级就 @PromptServer.instance.routes.get(...)，
    # 服务器没起时 `PromptServer.instance` 根本不存在 → AttributeError。
    # 关键是 `instance` 挂在**类对象**上（写成 `PromptServer().instance = ...` 不管用）。
    根 = Path(r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI")
    if not (根 / "custom_nodes" / "ComfyUI-Index-TTS").is_dir():
        return "没测", f"节点目录不在：{根}"
    import types
    if "server" not in sys.modules:
        假 = types.ModuleType("server")

        class _Routes:
            def get(self, *_a, **_k):
                return lambda f: f

            def post(self, *_a, **_k):
                return lambda f: f

        class _PS:
            instance = None

        _PS.instance = _PS()
        _PS.routes = _Routes()
        假.PromptServer = _PS
        sys.modules["server"] = 假
    os.chdir(根)
    for p in (str(根), str(根 / "custom_nodes")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from importlib import import_module
        mod = import_module("ComfyUI-Index-TTS.indextts2_5.model_loader")
    except Exception as e:  # noqa: BLE001
        return "没测", f"载不进 model_loader：{type(e).__name__}: {str(e)[:150]}"
    载 = getattr(mod, "IndexTTS25Loader", None)
    if 载 is None:
        return "没测", "model_loader 里没有 IndexTTS25Loader"
    try:
        # ★ 构造参数是 `models_root`（**模型目录的父目录**），不是模型目录本身！
        #   model_loader.py:20-21 逐字：
        #       self._models_root = models_root or self._default_models_root()
        #       self._model_dir = os.path.join(self._models_root, self.DEFAULT_DIRNAME)
        #   传模型目录 → 变成 `…\IndexTTS-2.5\IndexTTS-2.5` → 报缺 8 件的假警报。
        #   ★ 这是同一个坑的第三次发作：第一次是「文件存在≠文件对」（判据太弱），
        #     第二次是 `_并行下.py` 参数顺序（报错指向错地方），
        #     这一次是「**字符串看着对，但它是名字/根目录，不是那个路径**」。
        obj = 载(str(模型目录.parent))
    except Exception as e:  # noqa: BLE001
        return "没测", f"构造 Loader 失败：{type(e).__name__}: {str(e)[:120]}"
    校 = getattr(obj, "validate", None)
    if 校 is None:
        return "没测", "Loader 上没有 validate()"
    try:
        缺 = 校()
    except FileNotFoundError as e:
        return "没过", f"validate() 报缺：{str(e)[:200]}"
    except Exception as e:  # noqa: BLE001
        return "没测", f"validate() 抛了别的：{type(e).__name__}: {str(e)[:150]}"
    if 缺:
        return "没过", f"validate() 说还缺：{缺}"
    return "过", "validate() 说 8 件都在（★ 注意它不查 w2v-bert / bigvgan / campplus）"


def 验() -> int:
    print("=" * 100)
    print("IndexTTS-2.5 三关闸门    " + str(模型目录))
    print("=" * 100)

    # ── 第 1 关：件齐 + 字节对 + safetensors 头过 ──
    print("\n[第 1 关] 件齐 / 字节数 / safetensors 头表   —— 前置筛")
    print("-" * 100)
    缺: list[str] = []
    坏: list[str] = []
    for 名, (要, _仓, _内, 必需, 注) in 清单.items():
        p = 模型目录 / 名
        单 = p.stat().st_size if p.exists() else 0
        标 = "必需" if 必需 else "可选"
        if 单 != 要:
            缺.append(f"{名}（{标}，{单:,}/{要:,} = {单 / 要:.1%}）")
            态 = "✗缺"
        else:
            好, 说 = 头校验(p)
            if 说 and not 好:
                坏.append(名)
                态 = "✗坏"
                print(f"  {态:<5}{标:<5}{名:<44} {说}")
            else:
                态 = "✓"
        if 态 in ("✗缺", "✓"):
            行 = f"  {态:<5}{标:<5}{名:<44} {单:>14,} / {要:>14,}  {单 / 要:6.1%}"
            print(行)
    第1 = "过" if (not 缺 and not 坏) else "没过"
    print(f"\n  → 第 1 关：{第1}" + (f"（缺 {len(缺)} 件，坏 {len(坏)} 件）" if 缺 or 坏 else "（全部到位）"))
    for x in 坏:
        print(f"      ✗ 内容坏：{x}  ← 删掉它再跑 `python 补模型.py`")

    # ── 第 2 关：加载器自己说齐 ──
    print("\n[第 2 关] `model_loader.validate()` 亲口说齐   —— 前置筛（用桩测，不启服务）")
    print("-" * 100)
    if 缺:
        print(f"  没测（第 1 关还缺 {len(缺)} 件，validate() 必然抛错，测了也只是重复一遍）")
        第2 = "没测"
    else:
        第2, 话2 = 第二关()
        print(f"  → 第 2 关：{第2}   {话2}")

    # ── 第 3 关：真加载 ★ ──
    print("\n[第 3 关] 真 `torch.load` 读一遍   ★★★ 这是唯一不撒谎的判据 ★★★")
    print("-" * 100)
    print("  前两关都过了也仍然可能炸。`exists()` 真、大小非零、validate() 说齐，")
    print("  都不能证明「读得进来」—— 只有真读一次能。")
    print()
    if 缺:
        print(f"  没测（还缺 {len(缺)} 件）")
        第3 = "没测"
    else:
        失败: list[str] = []
        for 名 in 真加载件:
            p = 模型目录 / 名
            判定, 话 = 探一个(p)
            mb = p.stat().st_size / 1024 / 1024 if p.is_file() else 0
            print(f"  [{判定:<4}] {名:<44} {mb:>10,.1f} MB  {话}", flush=True)
            if 判定 == "✗":
                失败.append(名)
        第3 = "过" if not 失败 else "没过"
        print(f"\n  → 第 3 关：{第3}" + (f"（{len(失败)} 个读不进来：{失败}）" if 失败 else "（全读进来了）"))

    # ── 附加：节点在不在（这决定「能不能测」，不是「模型对不对」）──
    print("\n[附加] ComfyUI 里节点加载了吗   —— 这决定前面几关的信号有没有意义")
    print("-" * 100)
    在, 话在 = 节点在不在()
    print(f"  {'✓' if 在 else '✗'} {话在}")
    if not 在:
        print("      ★ 装了依赖但**没重启 ComfyUI** 的话，就是这个现象 ——")
        print("        custom_nodes 的 import 只在启动时做一次，**光刷新页面没用**。")

    # ── 裁决 ──
    print("\n" + "=" * 100)
    print(f"第 1 关 {第1}   第 2 关 {第2}   第 3 关 {第3}" + ("" if 在 else "   [节点没加载]"))
    码 = 0
    if 缺 or 坏:
        码 = 2
        print("→ 退出码 2：还缺件。跑 `python 补模型.py` 续下；**别删 .parts\\**（那是续传的本钱）。")
    elif 第3 == "没过":
        码 = 3
        print("→ 退出码 3：件齐了但真加载炸。文件是坏的，删掉上面报 ✗ 的那几个再下。")
    elif 第2 == "没过":
        码 = 3
        print("→ 退出码 3：validate() 不认（比第 3 关更早拦你）。按它的报错查。")
    elif not 在:
        码 = 4
        print("→ 退出码 4：模型没问题，但**节点没加载 → 这一轮算「没测」**。")
        print("   重启 ComfyUI 进程后再跑一次本命令（刷新页面不算）。")
    else:
        print("→ 退出码 0：三关全过，可以合成。")
        print("   下一步：python 真实试音.py \"雪落无声，剑亦无声。\"")
    print("=" * 100)
    return 码


def main() -> int:
    参 = [a for a in sys.argv[1:]]
    if 参 and 参[0] in ("状态", "status", "-s"):
        查状态()
        return 0
    if 参 and 参[0] in ("验", "verify", "-v"):
        return 验()
    只小 = "--小件" in 参
    位置 = [a for a in 参 if not a.startswith("--")]
    return 下(位置[0] if 位置 else "", 只小)


if __name__ == "__main__":
    sys.exit(main())
