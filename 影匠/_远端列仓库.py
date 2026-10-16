# -*- coding: utf-8 -*-
import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from huggingface_hub import HfApi
api = HfApi(endpoint="https://hf-mirror.com")
文件 = api.list_repo_files("Comfy-Org/MiniMax-H3")
print("  共 %d 个文件" % len(文件))
for f in sorted(文件):
    if f.endswith((".safetensors", ".sft", ".gguf")):
        print("    %s" % f)

print("\n=== 远端 loras 目录现状 ===")
p = r"E:\影匠AI\ComfyUI-Shared\models\loras"
print("  %s 存在=%s" % (p, os.path.isdir(p)))
if os.path.isdir(p):
    for f in sorted(os.listdir(p))[:30]:
        q = os.path.join(p, f)
        g = os.path.getsize(q) / 1e9 if os.path.isfile(q) else 0
        print("    %-70s %6.2f GB" % (f, g))
