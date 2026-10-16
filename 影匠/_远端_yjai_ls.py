# -*- coding: utf-8 -*-
"""远端模型清点：把 ComfyUI-Shared\\models 下的大文件列成 JSON，供本机比对。

为什么要走 Python 而不是 cmd 的 dir：
    cmd 的输出编码取决于代码页，中文路径过来就是乱码。
    Python 固定 UTF-8 写文件，本机再 scp 回去读，中间不经过任何代码页转换。
"""
import json
import os

根 = r"E:\影匠AI\ComfyUI-Shared\models"
出 = r"C:\yjai_models.json"
子目录 = ["diffusion_models", "vae", "text_encoders", "loras", "checkpoints",
        "upscale_models", "model_patches", "clip_vision", "audio_encoders"]

表 = {}
for 子 in 子目录:
    d = os.path.join(根, 子)
    if not os.path.isdir(d):
        continue
    for 名 in sorted(os.listdir(d)):
        p = os.path.join(d, 名)
        if os.path.isfile(p):
            表[f"{子}/{名}"] = os.path.getsize(p)

# 顺带把 venv / 节点 / 版本也记上，方便两边核对环境
import platform
import sys

环 = {
    "python": sys.version.split()[0],
    "机器": platform.node(),
}
try:
    import torch

    环["torch"] = torch.__version__
    环["cuda"] = torch.cuda.is_available()
    环["显卡"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
except Exception as e:
    环["torch"] = f"导入失败 {e}"

with open(出, "w", encoding="utf-8") as f:
    json.dump({"模型": 表, "环境": 环}, f, ensure_ascii=False, indent=1)
print(f"写了 {len(表)} 个模型 -> {出}")
