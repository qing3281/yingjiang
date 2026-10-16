"""一次性排查：ComfyUI 认到的模型落在磁盘哪儿、模板该指谁。用完可删。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 引擎

根 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
info = 引擎._请求("/object_info", 超时=120)

print("=== ComfyUI 认到的 unet ===")
for x in info["UNETLoader"]["input"]["required"]["unet_name"][0]:
    找到 = None
    for 子 in ("unet", "diffusion_models", os.path.join("models", "unet")):
        q = os.path.join(根, "models", 子, x)
        if os.path.exists(q):
            找到 = q
            break
    if 找到:
        print(f"  {os.path.getsize(找到)/2**30:7.2f} GB  {x}")
        print(f"               {找到}")
    else:
        print(f"  {'未知大小':>9s}  {x}   <-- 磁盘上没找到")

print()
print("=== extra_model_paths ===")
for f in ("extra_model_paths.yaml", "extra_model_paths.yaml.example"):
    q = os.path.join(根, f)
    if os.path.exists(q):
        print(f"--- {f} ---")
        print(open(q, encoding="utf-8", errors="replace").read()[:1500])
    else:
        print(f"--- {f} 不存在 ---")

print()
print("=== 用户目录里的 ComfyUI 配置 ===")
for q in (
    r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\unet",
    r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\diffusion_models",
):
    print(f"--- {q} ---")
    if os.path.isdir(q):
        for f in sorted(os.listdir(q)):
            p = os.path.join(q, f)
            if os.path.isfile(p):
                print(f"  {os.path.getsize(p)/2**30:7.2f} GB  {f}")
            else:
                print(f"  [目录]      {f}")
    else:
        print("  （不存在）")

print()
print("=== 影匠模板目录 ===")
模 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "模板")
for f in sorted(os.listdir(模)):
    print(f"  {os.path.getsize(os.path.join(模, f)):>6d} B  {f}")
