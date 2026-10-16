# -*- coding: utf-8 -*-
"""
影匠 · IndexTTS-2.5 缺口模型补齐
==================================
为什么单独写这个：`_下模型.py` 的 indextts 清单里漏了几条，而且有两个文件
压根不在 IndexTeam/IndexTTS-2.5 仓里 —— HEAD 返回 15 字节（"Entry not found"）：

    bigvgan/bigvgan_generator.pt   ← 真身在 nvidia/bigvgan_v2_22khz_80band_256x
    bigvgan/config.json            ← 同上
    w2v-bert-2.0/*                 ← 真身在 facebook/w2v-bert-2.0

所以这里显式写全「仓 + 路径」，一条都不靠猜。

实测的远程真实大小（用 _并行下.问大小 问出来的，不是抄文档的）：
    gpt.pth                      3,259,599,833   (3.04 GB)   ← 已在下，不碰
    s2mel.pth                      414,908,601   (395.7 MB)
    wav2vec2bert_stats.pt                9,343
    bigvgan_generator.pt           449,228,171   (428.4 MB)
    bigvgan/config.json                  1,405
    w2v-bert-2.0/model.safetensors 2,322,063,736 (2.16 GB)
    w2v-bert-2.0/config.json             1,874
    w2v-bert-2.0/preprocessor_config.json  275
    qwen0.6bemo4-merge/model.safetensors 1,192,135,096 (1.11 GB)
    campplus_cn_common.bin          28,036,335   (26.7 MB)

用法：
    python _下音色模型.py           # 只下缺的
    python _下音色模型.py --列表    # 只看状态
"""
import os
import sys

import _并行下 as 并行下

镜像 = "https://hf-mirror.com"
落地根 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\IndexTTS-2.5"

# (仓, 仓内路径, 落地相对路径, 说明)
# 落地相对路径一律写全，不压平 —— qwen 和 w2v 都有 model.safetensors，压平会互相覆盖
# ⚠ 顺序 = 关键路径优先。清单是顺序跑的，所以要先把「小文件 + 基座 validate()
#    点名要的那几个」拿到，跑通了再补 Qwen 情感模型（1.11 GB，只有 Emotion
#    Text 节点用得上，不进基座关键路径）。
清单 = [
    # ── 小文件，秒下，先清掉 ──
    ("IndexTeam/IndexTTS-2.5", "wav2vec2bert_stats.pt",
     "wav2vec2bert_stats.pt", "w2v-bert 归一化统计量（9 KB）"),
    ("nvidia/bigvgan_v2_22khz_80band_256x", "config.json",
     "bigvgan/config.json", "BigVGAN 配置（1.4 KB）"),
    ("facebook/w2v-bert-2.0", "config.json",
     "w2v-bert-2.0/config.json", "w2v 配置（1.9 KB）"),
    ("facebook/w2v-bert-2.0", "preprocessor_config.json",
     "w2v-bert-2.0/preprocessor_config.json", "w2v 前处理配置（275 B）"),
    ("funasr/campplus", "campplus_cn_common.bin",
     "campplus_cn_common.bin", "CampPlus 说话人嵌入（26.7 MB）"),

    # ── 基座 validate() 点名要的中间件 ──
    ("IndexTeam/IndexTTS-2.5", "s2mel.pth",
     "s2mel.pth", "s2mel 声学模型（395.7 MB）"),
    ("nvidia/bigvgan_v2_22khz_80band_256x", "bigvgan_generator.pt",
     "bigvgan/bigvgan_generator.pt", "BigVGAN 声码器（428.4 MB）"),
    ("facebook/w2v-bert-2.0", "model.safetensors",
     "w2v-bert-2.0/model.safetensors", "Wav2Vec2Bert 特征提取主干（2.16 GB）"),

    # ── 最后补情感文本模型（只有 Emotion Text 节点要）──
    ("IndexTeam/IndexTTS-2.5", "qwen0.6bemo4-merge/config.json",
     "qwen0.6bemo4-merge/config.json", "Qwen 情感模型配置"),
    ("IndexTeam/IndexTTS-2.5", "qwen0.6bemo4-merge/generation_config.json",
     "qwen0.6bemo4-merge/generation_config.json", "Qwen 生成配置"),
    ("IndexTeam/IndexTTS-2.5", "qwen0.6bemo4-merge/model.safetensors",
     "qwen0.6bemo4-merge/model.safetensors", "Qwen 情感分析小模型（1.11 GB）"),
]


def 址(仓, 路径):
    return f"{镜像}/{仓}/resolve/main/{路径}"


def 找本地(这里, 仓, 路径):
    """兼容两种落法：写全的相对路径，或旧脚本压平后的文件名。"""
    备 = [这里.get((仓, 路径)), os.path.join(落地根, os.path.basename(路径))]
    for 候选 in 备:
        if 候选 and os.path.exists(候选):
            return 候选
    return None


def 查状态():
    """(仓, 路径) -> (状态字, 现字节, 预期字节, 落地名)"""
    out = {}
    if not os.path.exists(落地根):
        return out
    索引 = {}
    for r, d, fs in os.walk(落地根):
        for f in fs:
            索引.setdefault(f, []).append(os.path.join(r, f))

    这里 = {}
    for 仓, 路径, 落, 说明 in 清单:
        这里[(仓, 路径)] = os.path.join(落地根, 落.replace("/", os.sep))

    for 仓, 路径, 落, 说明 in 清单:
        目标 = 这里[(仓, 路径)]
        现 = os.path.getsize(目标) if os.path.exists(目标) else 0
        半 = 目标 + ".parts"
        if not 现 and os.path.isdir(半):
            现 = sum(os.path.getsize(os.path.join(半, f)) for f in os.listdir(半)
                     if os.path.isfile(os.path.join(半, f)))
        out[(仓, 路径)] = (现, 目标)
    return out


def 报列表():
    状 = 查状态()
    print(f"落地根：{落地根}\n")
    总缺 = 0
    for 仓, 路径, 落, 说明 in 清单:
        现, 目标 = 状[(仓, 路径)]
        名 = os.path.basename(落)
        同名 = [p for p in (目标,) if os.path.exists(p)]
        if 现:
            print(f"  ◐ {并行下.人类(现):>12}  {落}   {说明}")
        else:
            print(f"  ✗ {'没有':>12}  {落}   {说明}")
            总缺 += 1
    print(f"\n缺 {总缺} / {len(清单)} 条")


def 跑():
    os.makedirs(落地根, exist_ok=True)
    成 = 败 = 跳 = 0
    for i, (仓, 路径, 落, 说明) in enumerate(清单, 1):
        目标 = os.path.join(落地根, 落.replace("/", os.sep))
        u = 址(仓, 路径)
        print(f"\n[{i}/{len(清单)}] {说明}", flush=True)
        print(f"    {仓} / {路径}", flush=True)

        # 已经完整了？（用真实远程大小判断，不用文档）
        预期 = 并行下.问大小(u)
        现 = os.path.getsize(目标) if os.path.exists(目标) else 0
        if 预期 and 现 >= 预期:
            print(f"    ✓ 已经完整 {并行下.人类(现)}，跳过", flush=True)
            跳 += 1
            continue
        if 预期:
            print(f"    远程 {并行下.人类(预期)}，本地 {并行下.人类(现)}", flush=True)

        os.makedirs(os.path.dirname(目标), exist_ok=True)
        # ⚠ 小文件必须单连接。分片下载的「每段一条 curl」对小于份数的文件会每段
        #   都拿回整份内容（实测 config.json 1.37 KB 被 4 路各拿全量 → 拼出
        #   5.49 KB，是预期的 4 倍）。大文件才值得并发。
        if not 预期 or 预期 <= 8 * 1048576:
            份 = 1
        elif 预期 > 500 * 1048576:
            份 = 8
        else:
            份 = 4
        if 并行下.拉(u, 目标, 份数=份, 预期=预期):
            print(f"    ✓ 完整 {并行下.人类(os.path.getsize(目标))}", flush=True)
            成 += 1
        else:
            print("    ✗ 失败", flush=True)
            败 += 1

    print(f"\n{'=' * 72}")
    print(f"结束：完整 {成} / 跳过 {跳} / 失败 {败}")
    return 败 == 0


if __name__ == "__main__":
    if "--列表" in sys.argv:
        报列表()
        sys.exit(0)
    sys.exit(0 if 跑() else 1)
