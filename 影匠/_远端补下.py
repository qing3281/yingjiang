# -*- coding: utf-8 -*-
import os
import time

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
DEST = r"E:\影匠AI\ComfyUI-Shared\models"
REPO = "Comfy-Org/MiniMax-H3"
名字 = "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
目标 = os.path.join(DEST, "text_encoders", 名字)

if os.path.exists(目标) and os.path.getsize(目标) > 1e10:
    print("  已有 %.2f GB" % (os.path.getsize(目标) / 1e9))
else:
    from huggingface_hub import hf_hub_download
    t0 = time.time()
    p = hf_hub_download(repo_id=REPO, filename="text_encoders/" + 名字, local_dir=DEST)
    dt = max(0.001, time.time() - t0)
    g = os.path.getsize(p) / 1e9
    print("  完成 %.2f GB  %.1f 分  %.1f MB/s" % (g, dt / 60, g * 1000 / dt))
