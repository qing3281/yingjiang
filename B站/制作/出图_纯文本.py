# -*- coding: utf-8 -*-
"""纯文本出图（Qwen-Image 2512，不带参考图）。

为什么需要这个：
  Qwen-Image-Edit 有个治不好的毛病 —— 它总把「参考图」和「生成结果」并排画在一张画布上，
  中间那格是原图翻版，结果是画面被切成几条、还互相叠着。之前出的人设图全是这个毛病。

  但我的角色设计锁现在已经写得足够细（发色渐变、耳朵位置、围裙图案、尾巴形状逐条列死），
  所以可以直接**纯文本出图**，让模型从零画，就不存在拼贴了。

画风锁跟出3D定妆.py 一致（3D 卡通渲染 / 高明度）。
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
输出根 = r"D:\DSHworkspace\B站\成片\不烧心\参考驱动"

# 跟出镜_Qwen参考.py 用同一套模型，保证画风一致
unet = "qwen_image_2512_fp8_e4m3fn.safetensors"
clip = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
vae = "qwen_image_vae.safetensors"

步数 = 40
CFG = 4.0
SHIFT = 3.1


def 取(p, 超时=60):
    with urllib.request.urlopen(COMFY + p, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 发(p, 数据, 超时=120):
    req = urllib.request.Request(
        COMFY + p, data=json.dumps(数据).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 造(提示词: str, 种子: int, 宽: int, 高: int, 负面: str = "") -> dict:
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": clip, "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": 提示词}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": 负面}},
        "6": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": 宽, "height": 高, "batch_size": 1}},
        "7": {"class_type": "ModelSamplingAuraFlow",
              "inputs": {"model": ["1", 0], "shift": SHIFT}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["7", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["6", 0], "seed": 种子, "steps": 步数,
                         "cfg": CFG, "sampler_name": "euler", "scheduler": "simple",
                         "denoise": 1.0}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": "DSH_纯文本"}},
    }


def 跑(提示词: str, 种子=5001, 宽=1152, 高=1536, 负面="", 静默=False) -> str | None:
    os.makedirs(输出根, exist_ok=True)
    wf = 造(提示词, 种子, 宽, 高, 负面)
    pid = 发("/api/prompt", {"prompt": wf})["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(3)
        h = 取(f"/api/history/{pid}")
        if pid in h:
            e = h[pid]
            if e.get("outputs"):
                图 = None
                for _, o in e["outputs"].items():
                    if o.get("images"):
                        图 = o["images"][0]
                if 图:
                    目 = os.path.join(输出根, 图["filename"])
                    if not os.path.isfile(目):
                        import shutil

                        src = os.path.join(
                            r"D:\Comfy-Desktop\ComfyUI-Shared\output",
                            str(图.get("subfolder") or ""), 图["filename"])
                        shutil.copyfile(src, 目)
                    if not 静默:
                        print(f"✅ {time.time()-t0:.0f} 秒 → {目}  ({宽}, {高})")
                    return 目
            if e.get("status", {}).get("status_str") == "error":
                print("❌ 出错：", json.dumps(e.get("status"), ensure_ascii=False)[:600])
                return None
        if time.time() - t0 > 3600:
            print("❌ 超时")
            return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--词", required=True)
    ap.add_argument("--负", default="")
    ap.add_argument("--种子", type=int, default=5001)
    ap.add_argument("--宽", type=int, default=1152)
    ap.add_argument("--高", type=int, default=1536)
    a = ap.parse_args()
    return 0 if 跑(a.词, a.种子, a.宽, a.高, a.负) else 1


if __name__ == "__main__":
    raise SystemExit(main())
