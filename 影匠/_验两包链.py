# -*- coding: utf-8 -*-
"""决定性判据：那两个包之间到底有没有硬链上？"""
import os
import ctypes
from ctypes import wintypes

下载 = r"D:\DSHworkspace\素材\网盘\下载"
甲 = os.path.join(下载, "1.MINIMAX打斗专篇")
乙 = os.path.join(下载, "【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）")
子 = os.path.join(甲, "【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）")

名 = [
    r"Comfyui-WF-2026.8.8.7z",
    r"models（放入comfyui modes文件夹即可，直接替换）\diffusion_models\minimax_h3_fl2va_int8_convrot.safetensors",
    r"models（放入comfyui modes文件夹即可，直接替换）\diffusion_models\minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    r"models（放入comfyui modes文件夹即可，直接替换）\text encoders\qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
    r"models（放入comfyui modes文件夹即可，直接替换）\text encoders\qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    r"models（放入comfyui modes文件夹即可，直接替换）\vae\minimax_h3_audio_vae_fp32.safetensors",
    r"models（放入comfyui modes文件夹即可，直接替换）\vae\minimax_h3_video_vae_fp16.safetensors",
]

print(f"{'文件':<52} {'打斗专篇 nlink':>14} {'子目录 nlink':>13} {'WF 那份 nlink':>14}  同一块？")
总数 = 0
链上 = 0
for n in 名:
    p1 = os.path.join(子, n)
    p2 = os.path.join(乙, n)
    短 = os.path.basename(n)[:50]
    行 = []
    ids = []
    for p in (p1, p2):
        if os.path.isfile(p):
            s = os.stat(p)
            ids.append((s.st_dev, s.st_ino))
            行.append(s.st_nlink)
        else:
            ids.append(None)
            行.append("-")
    if ids[0] and ids[1]:
        总数 += 1
        同 = ids[0] == ids[1]
        if 同:
            链上 += 1
        print(f"{短:<52} {行[0]:>14} {'-':>13} {行[1]:>14}  {'★ 同一块' if 同 else '✗ 两块独立'}")
        if 同:
            print(f"{'':52} ino={ids[0][1]}")
    else:
        print(f"{短:<52} 缺文件  {ids}")

print(f"\n比了 {总数} 个文件，其中 {链上} 个是同一块数据。")
if 链上 < 总数:
    print(f"→ ★ 还有 {(总数 - 链上)} 个文件是两份独立数据，可以硬链省下来。")
