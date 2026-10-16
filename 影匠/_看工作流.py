# -*- coding: utf-8 -*-
"""看一眼 WF 的工作流 json：是 UI 格式还是 API 格式、用了哪些模型、多少节点。

用法：python _看工作流.py <关键词>      例：python _看工作流.py Motion_Quality
"""
import json
import os
import sys

取出 = r"D:\DSHworkspace\影匠\_网盘整理\取出"

模型类 = {
    "UNETLoader": "unet_name", "CheckpointLoaderSimple": "ckpt_name",
    "CLIPLoader": "clip_name", "VAELoader": "vae_name",
    "LoraLoader": "lora_name", "LoraLoaderModelOnly": "lora_name",
    "UpscaleModelLoader": "model_name", "CLIPVisionLoader": "clip_name",
    "LoadImage": "image", "LoadAudio": "audio", "LoadVideo": "video",
}


def 找(词):
    出 = []
    for dp, dn, fn in os.walk(取出):
        for f in fn:
            if f.endswith(".json") and (词.lower() in f.lower()):
                出.append(os.path.join(dp, f))
    return sorted(出)


def 看(路):
    with open(路, encoding="utf-8") as fh:
        d = json.load(fh)
    # API 格式：{"1": {"class_type": ..., "inputs": {...}}, ...}
    # UI 格式：{"nodes": [...], "links": [...]}
    if isinstance(d, dict) and "nodes" in d and isinstance(d["nodes"], list):
        形 = "UI"
        节 = d["nodes"]
    elif isinstance(d, dict) and all(isinstance(v, dict) and "class_type" in v for v in d.values()):
        形 = "API"
        节 = list(d.values())
    else:
        形 = "?"
        节 = []

    类 = {}
    模 = []
    for n in 节:
        ct = n.get("class_type") or n.get("type") or "?"
        类[ct] = 类.get(ct, 0) + 1
        ins = n.get("inputs") or {}
        if isinstance(ins, dict):
            for k, v in 模型类.items():
                if ct == k and isinstance(ins.get(v), str):
                    模.append(f"{k}: {ins[v]}")
    return 形, len(节), 类, 模


词 = sys.argv[1] if len(sys.argv) > 1 else ""
路们 = 找(词)
print(f"匹配 {len(路们)} 个\n")
for 路 in 路们[:12]:
    try:
        形, 数, 类, 模 = 看(路)
    except Exception as e:
        print(f"  ✗ {os.path.basename(路)}  {e}")
        continue
    print(f"── {os.path.basename(路)}")
    print(f"   格式 {形}　节点 {数}　大小 {os.path.getsize(路):,} B")
    if 模:
        for m in dict.fromkeys(模):
            print(f"   模型 {m}")
    # 挑几个关键节点名
    关键 = [k for k in 类 if any(s in k for s in
            ("Sampler", "H3", "MiniMax", "Latent", "Audio", "Speech", "Video", "Keyframe", "Decode"))]
    if 关键:
        print(f"   关键节点 " + "，".join(f"{k}×{类[k]}" for k in sorted(关键)[:14]))
    print()
