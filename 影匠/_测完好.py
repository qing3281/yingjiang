"""验 引擎.模型完好()：真模型该过、截断的必须抓到。"""
import sys, os, json

sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 引擎

真 = [
    "qwen_image_2512_fp8_e4m3fn.safetensors",
    "z_image_turbo_int8_convrot.safetensors",
    "qwen_2.5_vl_7b_fp8_scaled.safetensors",
    "qwen_image_vae.safetensors",
    "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors",
]
print("--- 真模型的头部自校验（应全 True，数字要对得上目录里看到的大小）---")
坏 = 0
for m in 真:
    好, 说明 = 引擎.模型完好(m)
    if not 好:
        坏 += 1
    print(("  OK  " if 好 else "  错! ") + m + "   ->   " + 说明)

print("--- 造数据段截断（写了 100 字节，头部声明该有 4000）---")
假1 = r"D:\Comfy-Desktop\ComfyUI-Shared\models\loras\_截断测试.safetensors"
表 = {"a": {"dtype": "F32", "shape": [1000], "data_offsets": [0, 4000]}}
h = json.dumps(表).encode()
with open(假1, "wb") as f:
    f.write(len(h).to_bytes(8, "little"))
    f.write(h)
    f.write(b"\0" * 100)
好, 说明 = 引擎.模型完好("_截断测试.safetensors")
print(("  OK  " if not 好 else "  漏! ") + "_截断测试.safetensors   ->   " + 说明)
if 好:
    坏 += 1

print("--- 造头部就残（正是那个 0.38G 废文件的形状）---")
假2 = r"D:\Comfy-Desktop\ComfyUI-Shared\models\loras\_残头测试.safetensors"
with open(假2, "wb") as f:
    f.write(bytes.fromhex("6869060000000000") + b'{"__meta')
好, 说明 = 引擎.模型完好("_残头测试.safetensors")
print(("  OK  " if not 好 else "  漏! ") + "_残头测试.safetensors   ->   " + 说明)
if 好:
    坏 += 1

print("--- 造一个完整的小 safetensors（应 True）---")
假3 = r"D:\Comfy-Desktop\ComfyUI-Shared\models\loras\_完整测试.safetensors"
with open(假3, "wb") as f:
    f.write(len(h).to_bytes(8, "little"))
    f.write(h)
    f.write(b"\0" * 4000)
好, 说明 = 引擎.模型完好("_完整测试.safetensors")
print(("  OK  " if 好 else "  错! ") + "_完整测试.safetensors   ->   " + 说明)
if not 好:
    坏 += 1

for x in (假1, 假2, 假3):
    if os.path.exists(x):
        os.remove(x)
print("--- 临时文件已清 ---")
print("结论：", "全部符合预期" if 坏 == 0 else f"有 {坏} 条不符合预期")
sys.exit(0 if 坏 == 0 else 1)
