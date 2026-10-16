# -*- coding: utf-8 -*-
"""
影匠 · 大模型下载器（curl 驱动）
================================
为什么不用 huggingface_hub：
  1) 1.30.0 默认走 xet 后端，在 hf-mirror 镜像后面会静默卡死（CPU 不动、盘不长）
     —— 必须 HF_HUB_DISABLE_XET=1 才有救
  2) 连接被对端掐断时整个任务退出（实测 "peer closed connection without sending
     complete message body (received 130969000 bytes, expected 20499083824)"），
     20.5 GB 只收到 131 MB 就死了
  3) 不给人看进度，出事了只能看日志尾巴

curl 的表现（远程机上 10.1 MB/s 实测）：
  -C -            断点续传，断了接着下，不重头来
  --retry-all-errors  把「连接被掐」也算可重试，不像 curl 默认只重试少数几种错
  --speed-limit / --speed-time  真的卡死了自己退出来，不会永远挂着

用法：
  python _下模型.py            下全部
  python _下模型.py qwen       只下 Qwen-Image-Edit
  python _下模型.py indextts   只下 IndexTTS-2.5
  python _下模型.py --列表     只看清单和进度，什么都不下
"""
import os
import subprocess
import sys
import time

import _并行下 as 并行下

CURL = r"C:\WINDOWS\system32\curl.exe"
镜像 = "https://hf-mirror.com"

# ⚠ 两个模型根，别下错地方：
#   共享根 —— ComfyUI 实际加载大模型的地方（30+ 个模型都在这，从 logs 的
#              "Adding extra search path" 抄回来的，见 模型路径.yaml）
#   私有根 —— IndexTTS 那个节点自己找的相对路径，codec.pth 已经躺在这了
共享根 = r"D:\Comfy-Desktop\ComfyUI-Shared\models"
私有根 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models"

# ── 清单 ──────────────────────────────────────────────────────────
# (仓库, 仓内路径, 根, 落地相对路径, 下完预期字节数, 说明)
#   预期字节数写 0 = 下之前用 HEAD 现问
#   ⚠ 落地相对路径必须写全，不能只写文件名：qwen0.6bemo4-merge/model.safetensors
#     和 w2v-bert-2.0/model.safetensors 同名，压平了就互相覆盖
清单 = {
    "qwen": [
        ("Comfy-Org/Qwen-Image-Edit_ComfyUI",
         "split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors",
         共享根, "diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors", 20499083824,
         "Qwen-Image-Edit-2511 主模型 int8_convrot（20.5 GB）"),
        ("lightx2v/Qwen-Image-Edit-2511-Lightning",
         "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
         共享根, "loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", 0,
         "Lightning 4 步加速 LoRA（~810 MB）"),
    ],
    "indextts": [
        ("IndexTeam/IndexTTS-2.5", "gpt.pth",
         私有根, "IndexTTS-2.5/gpt.pth", 0, "GPT 自回归主模型（~3.1 GB）"),
        ("IndexTeam/IndexTTS-2.5", "qwen0.6bemo4-merge/model.safetensors",
         私有根, "IndexTTS-2.5/qwen0.6bemo4-merge/model.safetensors", 0, "情感文本分析小模型（~1.1 GB）"),
        ("IndexTeam/IndexTTS-2.5", "s2mel.pth",
         私有根, "IndexTTS-2.5/s2mel.pth", 0, "s2mel（~395 MB）"),
        ("IndexTeam/IndexTTS-2.5", "wav2vec2bert_stats.pt",
         私有根, "IndexTTS-2.5/wav2vec2bert_stats.pt", 0, "w2v-bert 统计量"),
        ("IndexTeam/IndexTTS-2.5", "bigvgan/bigvgan_generator.pt",
         私有根, "IndexTTS-2.5/bigvgan/bigvgan_generator.pt", 0, "声码器"),
        ("IndexTeam/IndexTTS-2.5", "bigvgan/config.json",
         私有根, "IndexTTS-2.5/bigvgan/config.json", 0, "声码器配置"),
        ("IndexTeam/IndexTTS-2.5", "qwen0.6bemo4-merge/tokenizer.json",
         私有根, "IndexTTS-2.5/qwen0.6bemo4-merge/tokenizer.json", 0, "分词器"),
        ("IndexTeam/IndexTTS-2.5", "qwen0.6bemo4-merge/tokenizer_config.json",
         私有根, "IndexTTS-2.5/qwen0.6bemo4-merge/tokenizer_config.json", 0, "分词器配置"),
        ("IndexTeam/IndexTTS-2.5", "qwen0.6bemo4-merge/vocab.json",
         私有根, "IndexTTS-2.5/qwen0.6bemo4-merge/vocab.json", 0, "词表"),
        ("IndexTeam/IndexTTS-2.5", "qwen0.6bemo4-merge/special_tokens_map.json",
         私有根, "IndexTTS-2.5/qwen0.6bemo4-merge/special_tokens_map.json", 0, "特殊词表映射"),
        ("IndexTeam/IndexTTS-2.5", "w2v-bert-2.0/config.json",
         私有根, "IndexTTS-2.5/w2v-bert-2.0/config.json", 0, "w2v 配置"),
        ("IndexTeam/IndexTTS-2.5", "w2v-bert-2.0/model.safetensors",
         私有根, "IndexTTS-2.5/w2v-bert-2.0/model.safetensors", 0, "w2v 主干"),
        ("IndexTeam/IndexTTS-2.5", "w2v-bert-2.0/conformer_shaw.pt",
         私有根, "IndexTTS-2.5/w2v-bert-2.0/conformer_shaw.pt", 0, "w2v conformer"),
        ("IndexTeam/IndexTTS-2.5", "w2v-bert-2.0/preprocessor_config.json",
         私有根, "IndexTTS-2.5/w2v-bert-2.0/preprocessor_config.json", 0, "w2v 前处理配置"),
    ],
}


def 址(仓, 路径):
    return f"{镜像}/{仓}/resolve/main/{路径}"


def 问大小(u, 超时=90):
    """HEAD 要 Content-Length。跟随跳转，取最后一个（真实的那个）。"""
    try:
        r = subprocess.run([CURL, "-sIL", "--connect-timeout", "30", "--max-time", str(超时), u],
                           capture_output=True, text=True, timeout=超时 + 30)
    except subprocess.TimeoutExpired:
        return 0
    n = 0
    for 行 in r.stdout.splitlines():
        if 行.lower().startswith("content-length:"):
            try:
                n = int(行.split(":", 1)[1].strip())
            except ValueError:
                pass
    return n


def 人类(n):
    for 单位, 除 in (("GB", 1073741824), ("MB", 1048576), ("KB", 1024)):
        if n >= 除:
            return f"{n/除:.2f} {单位}"
    return f"{n} B"


def 下一条(仓, 路径, 根, 落点, 预期, 说明, 最多轮=300, 份数=8):
    u = 址(仓, 路径)
    目标 = os.path.join(根, 落点.replace("/", os.sep))
    os.makedirs(os.path.dirname(目标), exist_ok=True)

    if not 预期:
        预期 = 问大小(u)
    if 预期:
        print(f"    预期 {人类(预期)}", flush=True)

    # ── 大文件走多连接并发 ──
    # 实测：单连接从 hf-mirror 拉 19 GB 只有 3 MB/s（要 1 小时 48 分）；
    # 分片并发每段都能各自跑到 3 MB/s 以上，总时长能压到十几分钟。
    if 预期 and 预期 > 500 * 1048576:
        现 = os.path.getsize(目标) if os.path.exists(目标) else 0
        if 现 >= 预期 - 1048576:
            print(f"    ✓ 已经完整  {人类(现)}", flush=True)
            return True
        # 单连接留下的半截文件跟分片方案对不上，清掉重来（分片自己有 .parts 续传）
        if 现 and not os.path.isdir(目标 + ".parts"):
            print(f"    清掉单连接留下的半截 {人类(现)}，改用分片", flush=True)
            os.remove(目标)
        print(f"    下载 {u}", flush=True)
        if 并行下.拉(u, 目标, 份数=份数, 预期=预期):
            print(f"    ✓ 完整  {人类(os.path.getsize(目标))}", flush=True)
            return True
        print("    ✗ 分片下载失败", flush=True)
        return False

    for 轮 in range(1, 最多轮 + 1):
        现 = os.path.getsize(目标) if os.path.exists(目标) else 0

        # 正好下完（容 1 MB 误差，有些源 Content-Length 不含尾部）
        if 预期 and 现 >= 预期 - 1048576:
            print(f"    ✓ 完整  {人类(现)}", flush=True)
            return True
        # 没预期大小就靠 curl 退出码判断，这里只在重试时提示
        if 现 and not 预期 and 轮 > 1:
            print(f"    ✓ 已拿到 {人类(现)}（无预期大小，按下完处理）", flush=True)
            return True

        if 轮 == 1:
            print(f"    下载 {u}", flush=True)
        else:
            print(f"    [{轮} 轮] 从 {人类(现)} 续传 …", flush=True)

        t0 = time.time()
        try:
            r = subprocess.run(
                [CURL, "-L", "--fail", "--no-progress-meter",
                 "--retry", "10", "--retry-delay", "5", "--retry-all-errors",
                 "--connect-timeout", "30", "--max-time", "0",
                 # 掉到 10 KB/s 以下持续 90 秒 = 真卡死，退出来重连
                 "--speed-limit", "10240", "--speed-time", "90",
                 "-C", "-", "-o", 目标, u],
                timeout=None)
            码 = r.returncode
        except KeyboardInterrupt:
            print("    ! 被中断", flush=True)
            return False
        except Exception as e:
            print(f"    ! {type(e).__name__}: {e}", flush=True)
            码 = -1

        新 = os.path.getsize(目标) if os.path.exists(目标) else 0
        dt = max(time.time() - t0, 0.001)
        增 = 新 - 现
        print(f"        退出码 {码}  现在 {人类(新)}  +{人类(增)}  {dt:.0f} 秒  {增/1048576/dt:.2f} MB/s", flush=True)

        if 预期 and 新 >= 预期 - 1048576:
            print(f"    ✓ 完整  {人类(新)}", flush=True)
            return True
        if 码 == 0 and not 预期:
            return True
        if 增 <= 0 and 轮 >= 5:
            print("    ✗ 连续 5 轮没有进展，放弃这一条", flush=True)
            return False
        time.sleep(3)

    return False


def 跑(组):
    print("=" * 72, flush=True)
    print(f"影匠 · 模型下载 · 组「{组}」", flush=True)
    print("=" * 72, flush=True)
    成 = 败 = 0
    for i, (仓, 路径, 根, 落点, 预期, 说明) in enumerate(清单[组], 1):
        print(f"\n[{i}/{len(清单[组])}] {说明}", flush=True)
        print(f"    {仓} / {路径}", flush=True)
        print(f"    → {根}\\{落点}", flush=True)
        if 下一条(仓, 路径, 根, 落点, 预期, 说明):
            成 += 1
        else:
            败 += 1
    print(f"\n{'=' * 72}", flush=True)
    print(f"组「{组}」结束：成功 {成} / 失败 {败}", flush=True)
    return 败 == 0


def 报列表():
    print(f"共享根：{共享根}")
    print(f"私有根：{私有根}\n")
    for 组, 条 in 清单.items():
        print(f"── 组「{组}」（{len(条)} 条）──")
        for 仓, 路径, 根, 落点, 预期, 说明 in 条:
            目标 = os.path.join(根, 落点.replace("/", os.sep))
            现 = os.path.getsize(目标) if os.path.exists(目标) else 0
            if 预期 and 现 >= 预期 - 1048576:
                状 = "✓ 完整"
            elif 现:
                状 = f"◐ {人类(现)}" + (f" / {人类(预期)}" if 预期 else "")
            else:
                状 = "✗ 没有"
            print(f"   {状:>22}   {落点}")
        print()


if __name__ == "__main__":
    if not os.path.exists(CURL):
        print(f"X 找不到 curl：{CURL}")
        sys.exit(1)

    if "--列表" in sys.argv:
        报列表()
        sys.exit(0)

    要 = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not 要:
        要 = list(清单.keys())
    for 组 in 要:
        if 组 not in 清单:
            print(f"X 不认识的组「{组}」，可选：{', '.join(清单)}")
            sys.exit(1)

    好 = True
    for 组 in 要:
        好 = 跑(组) and 好

    print("\n" + "=" * 72, flush=True)
    print("全部结束，最终清单：", flush=True)
    报列表()
    sys.exit(0 if 好 else 1)
