# -*- coding: utf-8 -*-
"""把网盘里「工作流要、本机没有」的模型硬链进 ComfyUI 的模型目录。

为什么是硬链不是复制：同一个 D 盘卷，硬链**不占额外空间**，
ComfyUI 照常按文件名加载，网盘那份也照旧在。

为什么值得做：这几个模型（76.51 GiB）是 WF 系列工作流点名要的，
而 WF 的 H3 工作流恰好有「运动质量」「长视频 22 帧」「人脸精修」
「原生出声（4V4A）」—— 正好对着用户抱怨的「单镜像看图片」「动作不连贯」。
"""
import os
import sys

盘 = r"D:\DSHworkspace\素材\网盘"
目标根 = r"D:\Comfy-Desktop\ComfyUI-Shared\models"

# 工作流引用了、本机没有、网盘里有的（>1 GiB 的那几个）
要的 = [
    ("minimax_h3_fl2va_int8_convrot.safetensors", "diffusion_models"),
    ("qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "text_encoders"),
    ("minimax_h3_fl2va_pruned_int8_convrot.safetensors", "diffusion_models"),
    ("minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors", "diffusion_models"),
    ("qwen_image_2.1_int8_convrot.safetensors", "diffusion_models"),
    ("qwen3vl_8b_bf16.safetensors", "text_encoders"),
    ("qwen3.5_qwen_image_2.1_pe_t2i.int8_convrot.safetensors", "text_encoders"),
    ("qwen3.5_qwen_image_2.1_pe_i2i.int8_convrot.safetensors", "text_encoders"),
    ("ema_model.safetensors", "diffusion_models"),
    ("minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors", "loras"),
    ("h3_upscaler_sharpness_2000steps_v0.1_fp32.safetensors", "upscale_models"),
    ("dinov2_vitl14.safetensors", "clip_vision"),
]

干 = "--干跑" not in sys.argv

# 先在网盘里把这些文件名找出来（同名多份时挑第一份）
索引 = {}
for dp, dn, fn in os.walk(盘):
    for f in fn:
        索引.setdefault(f, []).append(os.path.join(dp, f))

print(f"网盘里找到 {len(索引)} 种文件名\n")
省 = 0
成 = 0
跳 = 0
for 名, 子目录 in 要的:
    src = 索引.get(名)
    if not src:
        print(f"  – 网盘里没有：{名}")
        continue
    src = src[0]
    dst_dir = os.path.join(目标根, 子目录)
    dst = os.path.join(dst_dir, 名)
    sz = os.path.getsize(src)
    if os.path.exists(dst):
        a, b = os.stat(src), os.stat(dst)
        if (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino):
            print(f"  – 已经是同一块：{名}")
            跳 += 1
        else:
            print(f"  ! 目标已存在但不是硬链（不同文件）：{名}")
            跳 += 1
        continue
    print(f"  {sz / 2**30:8.2f} GiB  {子目录}/{名}")
    print(f"          ← {os.path.relpath(src, 盘)}")
    if not 干:
        os.makedirs(dst_dir, exist_ok=True)
        try:
            os.link(src, dst)
        except OSError as e:
            print(f"          ✗ 硬链失败：{e}")
            continue
        a, b = os.stat(src), os.stat(dst)
        同 = (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)
        print(f"          复验：同一块 {同}　nlink {b.st_nlink}")
        if 同:
            省 += sz
            成 += 1

print(f"\n★ 链上 {成} 个，跳过 {跳} 个，不占额外空间地多了 {省 / 2**30:.2f} GiB 可用模型")
