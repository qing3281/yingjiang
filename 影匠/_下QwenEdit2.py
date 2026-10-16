"""用 huggingface_hub 的 hf_hub_download 下 Qwen-Image-Edit-2511（单文件版）。

为什么不用 _并行下.py：实测那台服务器会在 256 MB 边界掐断连接
（curl: (18) end of response with 268435456 bytes missing），
自写的分段拼装在掐断 + 文件占用时会拼出半个文件。
hf_hub_download 用的就是「大量小 range 请求 + 断点续传 + 自动重试」，
这正是它设计来解决的场景。
"""
import os
import shutil
import sys
import time

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "30"

from huggingface_hub import hf_hub_download  # noqa: E402

仓 = "Comfy-Org/Qwen-Image-Edit_ComfyUI"
仓内路径 = "split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors"
应大 = 20499083824
目标 = r"D:\Comfy-Desktop\ComfyUI-Shared\models\diffusion_models\qwen_image_edit_2511_int8_convrot.safetensors"
暂存 = r"D:\Comfy-Desktop\ComfyUI-Shared\models\diffusion_models\.cache\hf_edit"


def 大小(路):
    return os.path.getsize(路) if os.path.exists(路) else 0


def 主():
    os.makedirs(暂存, exist_ok=True)
    # 清掉上次的残骸：0 字节的 .lock / .incomplete 会让 hf_hub 误以为在下
    for 根, _, 们 in os.walk(暂存):
        for f in 们:
            p = os.path.join(根, f)
            if f.endswith((".lock", ".incomplete")) and 大小(p) == 0:
                try:
                    os.remove(p)
                    print(f"  清残骸 {f}")
                except OSError:
                    pass

    上次 = 0
    回合 = 0
    while True:
        回合 += 1
        if 回合 > 200:
            print("✗ 200 回合还没下完，放弃")
            return 2
        try:
            路 = hf_hub_download(
                repo_id=仓,
                filename=仓内路径,
                local_dir=暂存,
                force_download=False,
            )
        except Exception as e:
            print(f"  [{回合}] 异常（{type(e).__name__}）{str(e)[:160]}")
            time.sleep(4)
            continue

        大 = 大小(路)
        进 = 大 - 上次
        上次 = 大
        剩 = 应大 - 大
        print(f"  [{回合}] {大 / 1073741824:.2f} / {应大 / 1073741824:.2f} GB"
              f"  ({大 / 应大 * 100:.1f}%)  本轮 +{进 / 1048576:.0f} MB"
              f"  剩 {剩 / 1073741824:.2f} GB", flush=True)

        if 大 == 应大:
            break
        if 进 == 0:
            # 这一轮一点没动，等一会儿再来
            time.sleep(6)

    print("  下完，搬到正式位置…")
    if os.path.exists(目标):
        os.remove(目标)
    shutil.move(路, 目标)
    print(f"✓ {目标}  {大小(目标)} B")
    return 0


if __name__ == "__main__":
    sys.exit(主())
