# -*- coding: utf-8 -*-
"""IndexTTS-2.5 模型下载（hf-mirror + 禁用 xet 后端 + 逐文件断点续传）"""
import os, sys, time
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_XET"] = "1"          # ← 关键：1.30 的 xet 后端在镜像后会卡死
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"

目标 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\IndexTTS-2.5"
os.makedirs(目标, exist_ok=True)

from huggingface_hub import hf_hub_download, HfApi

def 报(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

仓 = "IndexTeam/IndexTTS-2.5"
报("拉文件清单 …")
info = HfApi().model_info(仓, files_metadata=True)
文件 = [(s.rfilename, s.size or 0) for s in info.siblings]
文件.sort(key=lambda x: x[1])          # 小的先下，快出成果
报(f"共 {len(文件)} 个文件 / {sum(s for _,s in 文件)/1073741824:.2f} GB")

# 只下需要扩展名的，跳过 .gitattributes 之类
要 = [f for f in 文件 if not f[0].startswith('.')]
好的 = 坏的 = 0
总字节 = 0
for i, (名, 大) in enumerate(要, 1):
    报(f"[{i}/{len(要)}] {名}  {大/1048576:.1f} MB")
    t = time.time()
    try:
        p = hf_hub_download(repo_id=仓, filename=名, local_dir=目标,
                            force_download=False, resume_download=True)
        dt = time.time() - t
        总字节 += os.path.getsize(p)
        好的 += 1
        if 大 > 5*1048576:
            报(f"    OK  {dt:.1f} 秒  {大/1048576/dt:.2f} MB/s")
    except Exception as e:
        坏的 += 1
        报(f"    X {type(e).__name__}: {str(e)[:160]}")

报("")
报("=========== 落盘清单 ===========")
for r, d, fs in os.walk(目标):
    for f in fs:
        fp = os.path.join(r, f)
        s = os.path.getsize(fp)
        if s > 5*1048576:
            print(f"  {s/1048576:9.1f} MB  {os.path.relpath(fp, 目标)}", flush=True)
报(f"成功 {好的} / 失败 {坏的}")