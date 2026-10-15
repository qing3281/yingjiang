# -*- coding: utf-8 -*-
"""safetensors 到底是残的还是完的 —— 直接读文件头的偏移表算。"""
import io, json, os, struct, sys
sys.stdout.reconfigure(encoding="utf-8")
d = r"D:\Comfy-Desktop\ComfyUI-Shared\models\diffusion_models"
for f in ("minimax_h3_ref2va_pruned_w6a8.safetensors",
          "minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors",
          "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
          "minimax_h3_fl2va_pruned_w6a8.safetensors"):
    p = os.path.join(d, f)
    if not os.path.exists(p):
        print(f"  ✗ 不在：{f}"); continue
    实 = os.path.getsize(p)
    with io.open(p, "rb") as fp:
        n = struct.unpack("<Q", fp.read(8))[0]
        try:
            h = json.loads(fp.read(n).decode("utf-8"))
        except Exception as e:
            print(f"  ? {f}　头读不动（{e}）　{实/2**30:.2f} GB"); continue
    末 = 0
    for k, v in h.items():
        if k == "__metadata__" or not isinstance(v, dict): continue
        末 = max(末, v["data_offsets"][1])
    需 = 8 + n + 末
    差 = 需 - 实
    print(f"  {'✓' if 差 <= 0 else '✗'} {f}")
    print(f"        文件 {实/2**30:7.2f} GB　头声明需要 {需/2**30:7.2f} GB　缺 {差/2**30:7.2f} GB")
