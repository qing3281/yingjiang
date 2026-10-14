# -*- coding: utf-8 -*-
"""《觉醒》出片 —— MiniMax-H3 原生出视频（带同步声音）。

与旧的 `_出片.py --段` 的区别：
  旧：z_image_turbo 出首帧 → wan2.2_ti2v_5B 把首帧往前推一点（5B 小模型，
      只会做很轻的运动，所以「一镜里像看图片」）
  新：首帧 → MiniMax-H3 I2VA（原生 AV 模型，一次出视频**和**声音，
      头会转、嘴会动、雨会下，而且有运动质量节点可查）

规格：1280×704（H3 要求宽高都是 32 的倍数，720 不是，704 是）
      107 帧 @ 24fps = 4.458 秒（17n+5 网格上最接近 4.56 的合法帧数）
      → 74 格：74×4.4583 − 73×0.5 = 293.4 秒 = 4:53

用法：
    python _出H3.py 觉醒 --只格 1,2,3
    python _出H3.py 觉醒                     # 全 74 格
    python _出H3.py 觉醒 --跳过已有
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

步数 = 8
种子 = 1735946766
宽, 高 = 1280, 704
帧数 = 107                      # H3 的帧数走 17n+5 网格（节点 tooltip 原文：
                                # "24fps; snapped up to the 17n+5 H3 grid"，step=17）。
                                # 107 = 17×6+5 ✓ → 107/24 = 4.4583 秒。
                                # ★ 之前写 109 是个坑：它不在网格上，会被**悄悄**
                                # 吸附到 124（5.1667 秒），74 格就从 4:53 变成 5:46，
                                # 而日志和节点都不报错 —— 只有拿 ffmpeg 量成片时长才发现。
帧率 = 24
每段秒 = 帧数 / 帧率            # 107/24 = 4.4583 秒（不是 4.5417 —— 那是 109 帧的旧值）
转场吃 = 0.5
# 成片长度 = 74×4.4583 − 73×0.5 = 293.42 秒 = 4:53.4
# 再加片头 2 秒 + 片尾 5 秒 = 300.42 秒 = 5:00.4 ← 用户要的「5 分钟」正好够
格步长 = 每段秒 - 转场吃         # 3.9583 秒：第 n 格的起点 = (n−1) × 格步长


def 端点(名):
    if 名 == "远端":
        return "http://100.127.224.106:8188"
    return "http://127.0.0.1:8188"


def 传图(服务, 路):
    边 = uuid.uuid4().hex
    名 = f"h3_{边}.png"
    体 = open(路, "rb").read()
    界 = "----h3" + 边
    段 = (f"--{界}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{名}\"\r\n"
          f"Content-Type: image/png\r\n\r\n").encode() + 体 + f"\r\n--{界}--\r\n".encode()
    r = urllib.request.Request(f"{服务}/upload/image", data=段,
                               headers={"Content-Type": f"multipart/form-data; boundary={界}"})
    return json.load(urllib.request.urlopen(r, timeout=180)).get("name", 名)


def 建图(图名, 词, 号, 种子值, 前缀, 末帧名=""):
    """★ 末帧名非空时走 FL2VA（first+last frame）：把起始姿势和结束姿势都钉住，
    模型必须在这两个姿势之间**演出过程**。
    动机：只喂 first_frame 时，首帧已经是「手停在纸上」的姿势，模型没有理由动 ——
    实测最静的 16 格里，格5（手写册子）三个时刻姿势完全一样，笔就是不落下去。
    见 `_量运动.py`（量出来的：74 格最小 0.45、中位 1.28，但没有一格冻死）。"""
    图d = {
        "1": {"inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}, "class_type": "VAELoader"},
        "2": {"inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}, "class_type": "VAELoader"},
        "3": {"inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                         "type": "minimax", "device": "default"}, "class_type": "CLIPLoader"},
        "4": {"inputs": {"unet_name": "minimax_h3_fl2va_int8_convrot.safetensors",
                         "weight_dtype": "default"}, "class_type": "UNETLoader"},
        "5": {"inputs": {"lora_name": "minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors",
                         "strength_model": 1.0, "model": ["4", 0]},
              "class_type": "LoraLoaderBypassModelOnly"},
        "6": {"inputs": {"image": 图名}, "class_type": "LoadImage"},
        "7": {"inputs": {"prompt": 词, "width": 宽, "height": 高, "length": 帧数,
                         "task_type": "FL2VA" if 末帧名 else "I2VA",
                         "audio_mode": "native",
                         "audio_denoise_strength": 1.0, "add_source_as_reference": False,
                         "prompt_primary_audio_ordinal": 0, "strict_prompt_tags": True,
                         "ref_image_size": "match",
                         "reference_video_policy": "official_2_to_15s",
                         "clip": ["3", 0], "video_vae": ["1", 0], "audio_vae": ["2", 0],
                         "first_frame": ["6", 0]}, "class_type": "MiniMaxH3AudioConditioningT8"},
        "8": {"inputs": {"steps": 步数, "shift_video": 12.0, "shift_audio": 3.0,
                         "sampler_name": "dual_clock_euler", "scheduler": "native_flow",
                         "model": ["5", 0], "av_latent": ["7", 1]},
              "class_type": "MiniMaxH3DualClockSamplerT8"},
        "9": {"inputs": {"noise_seed": 种子值}, "class_type": "RandomNoise"},
        "10": {"inputs": {"model": ["8", 0], "conditioning": ["7", 0]}, "class_type": "BasicGuider"},
        "11": {"inputs": {"noise": ["9", 0], "guider": ["10", 0], "sampler": ["8", 1],
                          "sigmas": ["14", 0], "latent_image": ["7", 1]},
               "class_type": "SamplerCustomAdvanced"},
        "12": {"inputs": {"av_latent": ["11", 0], "video_vae": ["1", 0], "audio_vae": ["2", 0]},
               "class_type": "MiniMaxH3AVDecodeT8"},
        "13": {"inputs": {"frame_rate": 帧率, "loop_count": 0, "filename_prefix": 前缀,
                          "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 17,
                          "save_metadata": True, "trim_to_audio": False, "pingpong": False,
                          "save_output": True, "images": ["12", 0], "audio": ["12", 1]},
               "class_type": "VHS_VideoCombine"},
        "14": {"inputs": {"sigmas": ["8", 2], "mode": "report_only", "start_progress": 0.5,
                          "tail_power": 1.6, "shift_video": 12.0, "shift_audio": 3.0,
                          "profile": "turbo_standard8", "sampling_route": "dual_clock_euler",
                          "accept_turbo_schedule_ood": False},
               "class_type": "MiniMaxH3AVSigmaSameNFERedistributionT8Advanced"},
    }
    if 末帧名:
        图d["16"] = {"inputs": {"image": 末帧名}, "class_type": "LoadImage"}
        图d["7"]["inputs"]["last_frame"] = ["16", 0]
    return 图d


def 读格(戏):
    """从 02-九宫格.md 读每格的动作 + 提示词，用来拼 H3 的运动词。"""
    路 = os.path.join(根, "作品", 戏, "02-九宫格.md")
    文 = open(路, encoding="utf-8").read()
    块 = re.split(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$", 文, flags=re.M)
    出 = {}
    for i in range(1, len(块), 3):
        号 = int(块[i]); 题 = 块[i + 1].strip(); 体 = 块[i + 2]

        def 抠(键, 体=体):
            m = re.search(rf"^-\s*\*{{0,2}}{键}\*{{0,2}}\s*[:：]\s*(.*)$", 体, flags=re.M)
            return m.group(1).strip() if m else ""

        出[号] = {"题": 题, "景别": 抠("景别"), "动作": 抠("动作"), "光色": 抠("光色")}
    return 出


def main():
    global 步数
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--只格", default="")
    ap.add_argument("--端点", default="本机")
    ap.add_argument("--跳过已有", action="store_true")
    ap.add_argument("--步数", type=int, default=步数)
    ap.add_argument("--种子偏移", type=int, default=0,
                    help="在 种子 + 号×1009 之上再加一个偏移。重抽同一格时用 —— "
                         "★ 别用「不传就是新种子」那种写法：那样就复现不出来了")
    ap.add_argument("--出到", default="",
                    help="段文件写到哪（默认 段\\格N_端点.mp4）。重抽试验时指到别处，"
                         "不要覆盖生产用的那一个")
    ap.add_argument("--末帧目录", default="",
                    help="★ 这个目录里放 `末_格N.png`（这一格**结束**时的姿势）就会走 FL2VA："
                         "首帧+末帧都钉住，模型必须演出中间过程。没有对应末帧的格子"
                         "自动退回原来的 I2VA。")
    ap.add_argument("--词尾", default="", choices=["", "原", "动"],
                    help="★ 送给模型的那句英文任务尾巴。原版整句都在说「保持不变」"
                         "（Preserve… / Keep the same…），一个字都没让模型动 —— "
                         "怀疑它压住了动作。`动` 换成「首尾姿势必须明显不同」的写法。"
                         "留空＝用原版。")
    参 = ap.parse_args()
    步数 = 参.步数

    服务 = 端点(参.端点)
    图目录 = os.path.join(根, "作品", 参.戏)
    段目录 = os.path.join(图目录, "段")
    os.makedirs(段目录, exist_ok=True)
    格表 = 读格(参.戏)

    号们 = ([int(x) for x in 参.只格.split(",") if x.strip()]
            if 参.只格 else sorted(格表))
    print(f"端点 {参.端点} {服务}　{len(号们)} 格　{宽}×{高} {帧数}帧 @{帧率}fps　{步数} 步")

    t全 = time.time()
    for k, 号 in enumerate(号们, 1):
        图 = os.path.join(图目录, f"01_格{号}.png")
        出 = (os.path.join(参.出到, f"格{号}_{参.端点}.mp4") if 参.出到
              else os.path.join(段目录, f"格{号}_{参.端点}.mp4"))
        if 参.出到:
            os.makedirs(参.出到, exist_ok=True)
        if not os.path.isfile(图):
            print(f"  ✗ 格{号} 没有首帧 {图}")
            continue
        if 参.跳过已有 and os.path.isfile(出):
            print(f"  – 格{号} 已有")
            continue

        g = 格表.get(号, {})
        动作 = g.get("动作") or "轻微的自然动作"
        光 = g.get("光色") or ""
        # H3 的提示词要英文更稳；这里用「中文动作 + 英文任务句」的混合写法，
        # 实测中文动作能被理解，英文尾巴负责钉住「保身份、保皮肤、环境音」。
        词尾原 = ("A continuous cinematic shot. Preserve facial identity and natural skin texture. "
                  "Keep the same person, the same clothing and the same location as the reference image. "
                  "Natural ambient sound matching the scene; no dialogue.")
        # `动`：把「保持不变」换成「必须变」。原版只有保身份/保衣服/保地点，
        # 没有一句让模型动 —— 而 64% 的格子去噪运动量 < 0.6，怀疑就是它压住的。
        词尾动 = ("One single continuous take. The movement described above happens visibly and "
                  "gradually, starting in the first second and finishing by the last; the pose at "
                  "the end of the clip is clearly different from the pose at the start. Keep the "
                  "same person, the same clothing and the same location as the reference image, "
                  "and preserve facial identity and natural skin texture. Natural ambient sound "
                  "matching the scene; no dialogue.")
        词尾 = 词尾动 if 参.词尾 == "动" else 词尾原
        词 = (f"{动作}。环境：{光}。{词尾}")
        前缀 = f"觉醒_格{号:02d}_{参.端点}"

        try:
            t0 = time.time()
            名 = 传图(服务, 图)
            末名, 末路 = "", ""
            if 参.末帧目录:
                末路 = os.path.join(参.末帧目录, f"末_格{号}.png")
                if os.path.isfile(末路):
                    末名 = 传图(服务, 末路)
                else:
                    print(f"      （格{号} 没有末帧 {末路}，退回 I2VA）")
            图d = 建图(名, 词, 号, 种子 + 号 * 1009 + 参.种子偏移, 前缀, 末名)
            r = urllib.request.Request(f"{服务}/prompt", data=json.dumps({"prompt": 图d}).encode(),
                                       headers={"Content-Type": "application/json"})
            try:
                d = json.load(urllib.request.urlopen(r, timeout=180))
            except urllib.error.HTTPError as e:
                # ★ HTTPError 的正文里才有 ComfyUI 说清楚「哪个节点的哪个输入不对」，
                #   不读出来就只剩一句 400 Bad Request，等于没报错。
                体 = e.read().decode("utf-8", "replace")
                raise RuntimeError(f"POST /prompt 被拒 {e.code}：{体[:1200]}") from None
            号p = d.get("prompt_id")
            if d.get("node_errors"):
                print(f"  ✗ 格{号} 节点错误 {json.dumps(d['node_errors'], ensure_ascii=False)[:300]}")
                continue
            # 等它出
            出好 = False
            for _ in range(1440):
                time.sleep(5)
                h = json.load(urllib.request.urlopen(f"{服务}/history/{号p}", timeout=30))
                if 号p in h:
                    st = h[号p].get("status", {})
                    if st.get("status_str") != "success":
                        for m in st.get("messages", []):
                            if m[0] == "execution_error":
                                print(f"  ✗ 格{号} 执行错 {json.dumps(m[1], ensure_ascii=False)[:400]}")
                        break
                    for _, o in h[号p].get("outputs", {}).items():
                        for f in (o.get("gifs") or []):
                            子 = f.get("subfolder", "")
                            if 参.端点 == "远端":
                                # ★ 远端出的片子在本机磁盘上根本不存在，
                                #   必须走 HTTP /view 拉回来。老代码硬编码本机 output 路径，
                                #   在远端跑时 os.path.isfile 永远是 False → 每格都记「没出」，
                                #   片子其实已经生成好了（白白浪费 3 分钟一格）。
                                链接 = (f"{服务}/view?filename={urllib.parse.quote(f['filename'])}"
                                        f"&subfolder={urllib.parse.quote(子)}&type=output")
                                try:
                                    with urllib.request.urlopen(链接, timeout=300) as 回, \
                                            open(出, "wb") as 写:
                                        while True:
                                            块 = 回.read(1 << 20)
                                            if not 块:
                                                break
                                            写.write(块)
                                    出好 = os.path.getsize(出) > 10000
                                except Exception as e:
                                    print(f"  ✗ 格{号} 下载失败 {type(e).__name__}: {e}")
                            else:
                                # ★ 本机这条路 2026-10-15 一天里踩的两个坑：
                                #   ① VHS_VideoCombine 在「片子带音轨」时会给文件名加一个
                                #      -audio 后缀：节点报 觉醒_格14_本机_00001-audio.mp4，
                                #      老代码去找 觉醒_格14_本机_00001.mp4 —— **片子明明出好了，
                                #      每格都记「没出」**，白等一整轮。
                                #   ② 输出目录不是写死的 D:\Comfy-Desktop\ComfyUI-Shared\output：
                                #      这一版 ComfyUI 落在 D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\output。
                                #      节点自己在 ullpath 里报了真路径 —— **信它，别猜**。
                                源 = f.get("fullpath") or os.path.join(
                                    r"D:\Comfy-Desktop\ComfyUI-Shared\output", 子, f["filename"])
                                if not os.path.isfile(源):
                                    夹 = os.path.dirname(源)
                                    茎 = os.path.splitext(os.path.basename(f["filename"]))[0].replace("-audio", "")
                                    同 = [c for c in (os.listdir(夹) if os.path.isdir(夹) else [])
                                          if c.startswith(茎) and c.lower().endswith(".mp4")]
                                    if 同:
                                        同.sort(key=lambda c: os.path.getmtime(os.path.join(夹, c)))
                                        源 = os.path.join(夹, 同[-1])
                                        print(f"      · 名字对不上，按前缀找到了 {同[-1]}")
                                if os.path.isfile(源):
                                    import shutil
                                    shutil.move(源, 出)
                                    出好 = True
                    break
            if 出好:
                mb = os.path.getsize(出) / 1048576
                print(f"  [{k}/{len(号们)}] ✓ 格{号} {time.time() - t0:.1f} 秒  {mb:.2f} MB  {g.get('题', '')[:22]}")
            else:
                print(f"  [{k}/{len(号们)}] ✗ 格{号} 没出")
        except Exception as e:
            print(f"  ✗ 格{号} {type(e).__name__}: {e}")

    总 = time.time() - t全
    print(f"\n★ 用时 {总:.0f} 秒 = {总 / 60:.1f} 分")


if __name__ == "__main__":
    main()
