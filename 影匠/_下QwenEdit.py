# -*- coding: utf-8 -*-
"""Qwen-Image-Edit-2511 下载：int8_convrot 本体（本机已验证的量化格式）+ Lightning 4步 LoRA"""
import os, sys, time
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"

根 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models"
from huggingface_hub import hf_hub_download

def 报(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

任务 = [
    # (仓库, 仓内路径, 落到哪个子目录, 简述)
    ("Comfy-Org/Qwen-Image-Edit_ComfyUI",
     "split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors",
     "diffusion_models", "Qwen-Image-Edit-2511 主模型 int8（19.1 GB）"),
    ("lightx2v/Qwen-Image-Edit-2511-Lightning",
     "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
     "loras", "Lightning 4步加速 LoRA（810 MB）"),
]

for 仓, 路径, 子目录, 说明 in 任务:
    目标 = os.path.join(根, 子目录)
    os.makedirs(目标, exist_ok=True)
    报(f"=== {说明} ===")
    t = time.time()
    try:
        p = hf_hub_download(repo_id=仓, filename=路径, local_dir=目标)
        sz = os.path.getsize(p) / 1073741824
        dt = time.time() - t
        报(f"    ✓ {os.path.basename(p)}  {sz:.2f} GB  {dt/60:.1f} 分钟  {sz*1024/dt:.2f} MB/s")
    except Exception as e:
        报(f"    X {type(e).__name__}: {str(e)[:200]}")

报("")
报("=== 落盘确认 ===")
for 子目录 in ("diffusion_models", "loras"):
    d = os.path.join(根, 子目录)
    for f in sorted(os.listdir(d)):
        fp = os.path.join(d, f)
        if os.path.isfile(fp) and os.path.getsize(fp) > 100*1048576:
            print(f"  {os.path.getsize(fp)/1073741824:6.2f} GB  {子目录}/{f}", flush=True)