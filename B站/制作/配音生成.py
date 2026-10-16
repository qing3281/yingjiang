# -*- coding: utf-8 -*-
"""批量把中文台词生成旁白 wav —— 3 分钟短剧的出旁白环节。

## 为什么单独写成脚本（而不是每次手敲 python -c）

IndexTTS-2 的模型加载要 **13 秒 + 6.2 GB 显存**，而合成一句 10 来个字只要 3 秒。
一集短剧几十句台词，如果每句都重启一次进程，光加载就浪费十分钟。所以这里
**加载一次、循环合成全部台词**，并且把每句的路径 / 时长 / 耗时写成一份
`旁白清单.json`，交给 `配音.py` 直接用。

## 为什么路径要过一道 `转ascii`

这台机器上 kaldifst / sentencepiece 这类 C++ 扩展**打不开含中文的路径**
（详见 `B站\\情报\\配音方案调研.md` 的坑 E/F）。而工作区恰好叫 `B站`。
解决办法是在 `D:\\tts` 建了个纯 ASCII 的目录联接指向 `D:\\DSHworkspace\\B站\\配音环境`，
脚本内部一律走 `D:\\tts\\...`。这里再自动转一道，免得使用者写中文路径踩坑。

## 用法

    $V = "D:\\tts\\venv\\Scripts\\python.exe"     # 注意：必须用 junction 这条路径
    & $V "D:\\DSHworkspace\\B站\\制作\\配音生成.py" `
        --脚本 "D:\\DSHworkspace\\B站\\制作\\它记得_台词.txt" `
        --参考 "D:\\tts\\_ref\\ref_a.wav" `
        --输出目录 "D:\\DSHworkspace\\B站\\配音\\它记得"

`--脚本` 支持两种格式，按扩展名自动认：

* **.txt**：一行一句，`#` 开头和空行跳过。
* **.json**：`[{"文本": "...", "参考": "ref_b.wav", "文件": "03.wav", "情绪": "..."}]`，
  后三项都可省。`情绪` 只在 `--情绪模式` 打开时生效。

## 显存

加载后峰值 6.18 GB，跑的时候涨到 6.5 GB 上下。跑之前记得腾显存：

    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8188/api/free" `
      -Body '{"unload_models":true,"free_memory":true}' -ContentType "application/json"
"""
import argparse
import json
import os
import sys
import time

# --- 路径兜底：把中文前缀换成 ASCII 的 junction，C++ 扩展才肯开文件 ---------
中文前缀 = r"D:\DSHworkspace\B站\配音环境"
ASCII前缀 = r"D:\tts"


def 转ascii(路径: str) -> str:
    if 路径 and 路径.lower().startswith(中文前缀.lower()):
        return ASCII前缀 + 路径[len(中文前缀):]
    return 路径


默认环境 = 转ascii(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "配音环境"))
默认环境 = os.path.normpath(默认环境)
默认模型 = os.path.join(默认环境, "models", "IndexTTS-2")
默认源码 = os.path.join(默认环境, "index-tts-src")
默认参考目录 = os.path.join(默认环境, "_ref")

sys.path.insert(0, 默认源码)
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "配音环境")))

# 必须在 indextts 之前：把 torchaudio.save（2.9+ 要 torchcodec，本机没有 ffmpeg）换成 PyAV
import _indextts_patch  # noqa: E402,F401


def 读脚本(路径: str):
    """读台词本，返回 [(文本, 参考名, 输出文件名, 情绪), ...]。"""
    根, 扩展 = os.path.splitext(路径)
    扩展 = 扩展.lower()
    条目 = []
    if 扩展 == ".json":
        with open(路径, "r", encoding="utf-8") as f:
            原始 = json.load(f)
        if isinstance(原始, dict):
            原始 = 原始.get("台词") or 原始.get("lines") or []
        for 序号, 项 in enumerate(原始, 1):
            if isinstance(项, str):
                项 = {"文本": 项}
            条目.append(
                (
                    项["文本"],
                    项.get("参考"),
                    项.get("文件") or f"{序号:03d}.wav",
                    项.get("情绪"),
                )
            )
    else:
        with open(路径, "r", encoding="utf-8") as f:
            行们 = f.read().splitlines()
        序号 = 0
        for 行 in 行们:
            行 = 行.strip()
            if not 行 or 行.startswith("#"):
                continue
            序号 += 1
            条目.append((行, None, f"{序号:03d}.wav", None))
    if not 条目:
        raise SystemExit(f"台词本里没有可用台词：{路径}")
    return 条目


def main():
    ap = argparse.ArgumentParser(
        description="IndexTTS-2 批量生成中文旁白（加载一次，循环合成）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--脚本", required=True, help="台词本：.txt（一行一句）或 .json")
    ap.add_argument("--输出目录", required=True, help="wav 输出目录，不存在会自动建")
    ap.add_argument("--参考", default=os.path.join(默认参考目录, "ref_a.wav"),
                    help="默认参考音色 wav（台词本里没单独指定时用它）")
    ap.add_argument("--参考目录", default=默认参考目录, help="台词本里写相对参考名时去哪找")
    ap.add_argument("--模型", default=默认模型, help="IndexTTS-2 模型目录")
    ap.add_argument("--源码", default=默认源码, help="index-tts 源码目录")
    ap.add_argument("--清单", default=None, help="旁白清单 json 的输出路径，默认写在输出目录里")
    ap.add_argument("--情绪模式", action="store_true", help="打开 Qwen 情绪理解（更慢，默认关）")
    ap.add_argument("--无fp16", action="store_true", help="关掉 fp16（默认开）")
    ap.add_argument("--限制", type=int, default=0, help="只跑前 N 句，0 = 全跑（调试用）")
    args = ap.parse_args()

    模型 = 转ascii(os.path.abspath(args.模型))
    源码 = 转ascii(os.path.abspath(args.源码))
    参考目录 = 转ascii(os.path.abspath(args.参考目录))
    参考 = 转ascii(os.path.abspath(args.参考))
    输出目录 = os.path.abspath(args.输出目录)  # 输出让 PyAV 写，中文路径没问题
    os.makedirs(输出目录, exist_ok=True)

    # 源码可能不在默认位置，重新挂一下
    if 源码 not in sys.path:
        sys.path.insert(0, 源码)

    条目 = 读脚本(args.脚本)
    if args.限制:
        条目 = 条目[: args.限制]

    import torch
    from indextts.infer_v2 import IndexTTS2

    自由, 总共 = torch.cuda.mem_get_info()
    print("=" * 66)
    print(f"GPU {torch.cuda.get_device_name(0)}  空闲 {自由/1024**3:.2f}/{总共/1024**3:.2f} GB")
    print(f"台词 {len(条目)} 句   模型 {模型}")
    print("=" * 66, flush=True)

    起 = time.time()
    tts = IndexTTS2(
        cfg_path=os.path.join(模型, "config.yaml"),
        model_dir=模型,
        use_fp16=not args.无fp16,
        use_qwen_emo=bool(args.情绪模式),
    )
    print(f"[加载完成] {time.time()-起:.1f}s  "
          f"显存 {torch.cuda.max_memory_allocated()/1024**3:.2f} GB\n", flush=True)

    清单 = []
    总起 = time.time()
    for 序号, (文本, 参考名, 文件名, 情绪) in enumerate(条目, 1):
        if 参考名:
            该参考 = 参考名 if os.path.isabs(参考名) else os.path.join(参考目录, 参考名)
            该参考 = 转ascii(该参考)
        else:
            该参考 = 参考
        if not os.path.isfile(该参考):
            print(f"  [跳过] 参考音频不存在：{该参考}", flush=True)
            continue

        出 = os.path.join(输出目录, 文件名 if 文件名.lower().endswith(".wav") else 文件名 + ".wav")
        t0 = time.time()
        额外 = {}
        if 情绪 and args.情绪模式:
            额外["emo_text"] = 情绪
            tts.infer(spk_audio_prompt=该参考, text=文本, output_path=出,
                      verbose=False, use_emo_text=True, **额外)
        else:
            tts.infer(spk_audio_prompt=该参考, text=文本, output_path=出, verbose=False)
        耗 = time.time() - t0

        # 量一下真实时长（PlayRes 排布要用）
        时长 = 0.0
        try:
            import av

            with av.open(出) as c:
                s = c.streams.audio[0]
                时长 = float(s.duration * s.time_base) if s.duration else 0.0
                if 时长 <= 0:
                    时长 = sum(f.samples for f in c.decode(s)) / s.rate
        except Exception:
            pass

        清单.append({"序号": 序号, "文本": 文本, "文件": 出, "时长": round(时长, 3),
                     "耗时": round(耗, 2), "参考": os.path.basename(该参考)})
        print(f"  [{序号:>3}/{len(条目)}] {耗:5.2f}s  {时长:5.2f}s  {len(文本):>3}字  {os.path.basename(出)}",
              flush=True)

    清单路径 = args.清单 or os.path.join(输出目录, "旁白清单.json")
    总时长 = sum(条["时长"] for 条 in 清单)
    with open(清单路径, "w", encoding="utf-8") as f:
        json.dump({"台词本": os.path.abspath(args.脚本), "参考": 参考, "句数": len(清单),
                   "总时长": round(总时长, 3), "清单": 清单}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(清单)} 句   音频共 {总时长:.2f}s   合成总耗时 {time.time()-总起:.1f}s "
          f"（均 {(time.time()-总起)/max(1,len(清单)):.2f}s/句）")
    print(f"   显存峰值 {torch.cuda.max_memory_allocated()/1024**3:.2f} GB")
    print(f"   清单 {清单路径}")
    print(f"   下一步：& \"D:\\Comfy-Desktop\\...\\python.exe\" "
          f"\"D:\\DSHworkspace\\B站\\制作\\配音.py\" --视频 成片.mp4 --bgm BGM.mp3 "
          f"--旁白 " + " ".join(条["文件"] for 条 in 清单))


if __name__ == "__main__":
    main()
