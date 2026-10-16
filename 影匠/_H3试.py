# -*- coding: utf-8 -*-
"""MiniMax-H3 原生出片（图 + 同步声音 + 运动质量）—— 本机能不能跑、多快。

为什么试它：用户说「动作还是不连贯」「一镜里还是像看图片」。
现在用的 wan2.2_ti2v_5B 是 5B 的小模型，只会把首帧往前推一点点，
所以看着像静帧。MiniMax-H3 是原生 AV 模型：一次出视频**和**声音，
而且有专门的运动质量节点。

用法：
    python _H3试.py --图 作品/磨刀/01_格31.png --帧 49
    python _H3试.py --图 ... --帧 124 --宽 736 --高 416
"""
import argparse
import json
import os
import sys
import time
import urllib.request

服务 = "http://127.0.0.1:8188"


def 传图(路):
    """把图片传到 ComfyUI 的 input 目录（走 HTTP，不问本地文件系统）。"""
    import uuid
    边 = uuid.uuid4().hex
    名 = f"h3test_{边}.png"
    体 = open(路, "rb").read()
    界 = "----h3test" + 边
    段 = (f"--{界}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{名}\"\r\n"
          f"Content-Type: image/png\r\n\r\n").encode() + 体 + f"\r\n--{界}--\r\n".encode()
    r = urllib.request.Request(f"{服务}/upload/image", data=段,
                               headers={"Content-Type": f"multipart/form-data; boundary={界}"})
    d = json.load(urllib.request.urlopen(r, timeout=120))
    return d.get("name", 名)


def 建图(图名, 帧, 宽, 高, 词, 种子, 步数, 尾):
    return {
        "1": {"inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}, "class_type": "VAELoader"},
        "2": {"inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}, "class_type": "VAELoader"},
        "3": {"inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                         "type": "minimax", "device": "default"}, "class_type": "CLIPLoader"},
        "4": {"inputs": {"unet_name": "minimax_h3_fl2va_int8_convrot.safetensors",
                         "weight_dtype": "default"}, "class_type": "UNETLoader"},
        # int8_convrot 是量化模型，turbo LoRA 按官方注释要「bypass」
        "5": {"inputs": {"lora_name": "minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors",
                         "strength_model": 1.0, "model": ["4", 0]},
              "class_type": "LoraLoaderBypassModelOnly"},
        "6": {"inputs": {"image": 图名}, "class_type": "LoadImage"},
        "7": {"inputs": {"prompt": 词, "width": 宽, "height": 高, "length": 帧,
                         "task_type": "I2VA", "audio_mode": "native",
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
        "9": {"inputs": {"noise_seed": 种子}, "class_type": "RandomNoise"},
        "10": {"inputs": {"model": ["8", 0], "conditioning": ["7", 0]}, "class_type": "BasicGuider"},
        "11": {"inputs": {"noise": ["9", 0], "guider": ["10", 0], "sampler": ["8", 1],
                          "sigmas": ["14", 0], "latent_image": ["7", 1]},
               "class_type": "SamplerCustomAdvanced"},
        "12": {"inputs": {"av_latent": ["11", 0], "video_vae": ["1", 0], "audio_vae": ["2", 0]},
               "class_type": "MiniMaxH3AVDecodeT8"},
        "13": {"inputs": {"frame_rate": 24, "loop_count": 0, "filename_prefix": 尾,
                          "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 19,
                          "save_metadata": True, "trim_to_audio": False, "pingpong": False,
                          "save_output": True, "images": ["12", 0], "audio": ["12", 1]},
               "class_type": "VHS_VideoCombine"},
        "14": {"inputs": {"sigmas": ["8", 2], "mode": "report_only", "start_progress": 0.5,
                          "tail_power": 1.6, "shift_video": 12.0, "shift_audio": 3.0,
                          "profile": "turbo_standard8", "sampling_route": "dual_clock_euler",
                          "accept_turbo_schedule_ood": False},
               "class_type": "MiniMaxH3AVSigmaSameNFERedistributionT8Advanced"},
        "15": {"inputs": {"frames": ["12", 0], "fps": 24.0, "roi_mode": "full_frame",
                          "roi_x": 0.25, "roi_y": 0.05, "roi_width": 0.5, "roi_height": 0.5,
                          "sharpness_ratio_floor": 0.55, "temporal_instability_multiplier": 2.5,
                          "high_motion_delta_floor": 0.03, "freeze_delta_ceiling": 0.002,
                          "repair_context_frames": 12},
               "class_type": "MiniMaxH3MotionQualityAuditT8Advanced"},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--图", required=True)
    ap.add_argument("--帧", type=int, default=49)
    ap.add_argument("--宽", type=int, default=736)
    ap.add_argument("--高", type=int, default=416)
    ap.add_argument("--步数", type=int, default=8)
    ap.add_argument("--种子", type=int, default=1735946766)
    ap.add_argument("--尾", default="H3test")
    ap.add_argument("--词", default="")
    参 = ap.parse_args()

    路 = os.path.abspath(参.图)
    词 = 参.词 or ("A continuous cinematic shot of the same person in a rainy ancient Chinese alley. "
                 "He turns his head slowly, rain falls, lanterns sway gently in the wind. "
                 "Preserve facial identity and natural skin texture. "
                 "Ambient rain and distant water sounds; no dialogue.")
    print(f"图 {路}")
    名 = 传图(路)
    print(f"  传上去叫 {名}")
    图 = 建图(名, 参.帧, 参.宽, 参.高, 词, 参.种子, 参.步数, 参.尾)
    t = time.time()
    r = urllib.request.Request(f"{服务}/prompt",
                               data=json.dumps({"prompt": 图}).encode(),
                               headers={"Content-Type": "application/json"})
    try:
        d = json.load(urllib.request.urlopen(r, timeout=180))
    except urllib.error.HTTPError as e:
        体 = e.read().decode("utf-8", "replace")
        print(f"✗ 提交被拒 {e.code}\n{体[:3000]}")
        return 1
    号 = d.get("prompt_id")
    print(f"  提交成功 prompt_id={号}")
    print(f"  节点错误 {json.dumps(d.get('node_errors'), ensure_ascii=False)[:800]}")

    上 = ""
    for i in range(720):
        time.sleep(5)
        try:
            h = json.load(urllib.request.urlopen(f"{服务}/history/{号}", timeout=20))
        except Exception:
            continue
        if 号 in h:
            e = h[号]
            st = e.get("status", {})
            print(f"\n★ 用了 {time.time() - t:.1f} 秒　status={st.get('status_str')}　completed={st.get('completed')}")
            for m in st.get("messages", [])[-8:]:
                print("   ", json.dumps(m, ensure_ascii=False)[:300])
            出 = e.get("outputs", {})
            for n, o in 出.items():
                for k in ("gifs", "videos", "images", "audio"):
                    for f in o.get(k, []) or []:
                        print(f"   产物 {f.get('subfolder')}/{f.get('filename')}  {f.get('type')}")
            return 0
        try:
            q = json.load(urllib.request.urlopen(f"{服务}/queue", timeout=10))
            跑 = q.get("queue_running") or []
            剩 = q.get("queue_pending") or []
            新 = f"跑{len(跑)} 等{len(剩)}"
            if 新 != 上:
                print(f"  {time.time() - t:6.1f}s  {新}")
                上 = 新
        except Exception:
            pass
        if i % 12 == 11:
            print(f"  {time.time() - t:6.1f}s 还在跑…")
    print("✗ 一小时没出")
    return 1


if __name__ == "__main__":
    sys.exit(main())
