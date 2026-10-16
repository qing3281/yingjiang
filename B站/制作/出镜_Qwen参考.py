# -*- coding: utf-8 -*-
"""用 Qwen-Image-Edit-2512 把「网上的原图」直接变成分镜画面。

核心诉求（用户 m02916）：「能不能用网上的形象，别重画」

所以这里的路线是**参考图驱动**，不是文字描述驱动：
  把 `B站\情报\AI娘参考图\` 里的官方角色图直接喂给模型（最多 3 张），
  模型保留原图的脸/发色/服装设计，只换场景和构图。

用法：
    python 出镜_Qwen参考.py --试                # 跑一张测试图
    python 出镜_Qwen参考.py --图 A.png --词 "..." --出 out.png

工作流（Qwen-Image-Edit-2512 + Lightning 4 步 LoRA）：
    UNETLoader(qwen_image_2512_fp8_e4m3fn)
      → LoraLoaderModelOnly(Qwen-Image-2512-Lightning-4steps-V1.0-fp32, 1.0)
      → ModelSamplingAuraFlow(shift=3.1)
    CLIPLoader(qwen_2.5_vl_7b_fp8_scaled, type=qwen_image)
    VAELoader(qwen_image_vae)
    LoadImage(参考图) ×1~3
      → TextEncodeQwenImageEditPlus(clip, prompt, vae, image1..3)
      → ReferenceLatent
      → KSampler(steps=4, cfg=1.0) → VAEDecode → SaveImage
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
参考根 = r"D:\DSHworkspace\B站\情报\AI娘参考图"
输出根 = r"D:\DSHworkspace\B站\成片\不烧心\参考驱动"

UNET = "qwen_image_2512_fp8_e4m3fn.safetensors"
CLIP = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
VAE = "qwen_image_vae.safetensors"
LORA = "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors"

W, H = 1536, 864          # 横屏分镜
步数 = 4
CFG = 1.0
SHIFT = 3.1

# 高质量档：不挂 Lightning 蒸馏 LoRA，走原模型的完整采样
#
# 这两个数不是拍的 —— 是 ComfyUI 自带官方模板里写死的：
#   image_qwen_Image_2512.json      → KSampler(50 步, CFG 4.0)，Lightning LoRA 只是"加速档"
#   image_qwen_image_edit_2511.json → KSampler(40 步, CFG 3) + CFGNorm + FluxKontext* 两个节点
#   image_qwen_image_edit_2511.json 的 MarkdownNote 原话：
#       「You can test and find the best setting by yourself. The following table is for reference.
#         | Steps | Qwen 40 | Comfy 20 |     | CFG | 4.0 | 4.0 |」
# 我一开始用 4 步 / CFG 1.0 是蒸馏加速档 —— 细节和参考还原度必然崩，这就是"效果糟糕"的根因。
步数高质量 = 40
CFG高质量 = 4.0


def 取(p, 超时=60):
    with urllib.request.urlopen(COMFY + p, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 发(p, 数据, 超时=120):
    req = urllib.request.Request(
        COMFY + p, data=json.dumps(数据).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 传图(路: str) -> str:
    """multipart 上传，返回 ComfyUI 侧的文件名。"""
    with open(路, "rb") as f:
        数据 = f.read()
    名 = f"ref_{uuid.uuid4().hex[:8]}_{os.path.basename(路)}"
    边界 = "----DSH" + uuid.uuid4().hex
    体 = b""
    体 += f"--{边界}\r\n".encode()
    体 += f'Content-Disposition: form-data; name="image"; filename="{名}"\r\n'.encode()
    体 += b"Content-Type: application/octet-stream\r\n\r\n"
    体 += 数据 + b"\r\n"
    体 += f"--{边界}\r\n".encode()
    体 += b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
    体 += f"--{边界}--\r\n".encode()
    req = urllib.request.Request(
        COMFY + "/api/upload/image", data=体,
        headers={"Content-Type": f"multipart/form-data; boundary={边界}"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        j = json.loads(r.read().decode("utf-8"))
    return j.get("name") or 名


def 造工作流(参考文件名们: list[str], 提示词: str, 种子: int, 宽=W, 高=H,
            起始图: str | None = None, 降噪=1.0, 高质量=False) -> dict:
    """Qwen-Image-Edit 工作流。

    起始图=None → 空潜变量 + ReferenceLatent（纯参考驱动，构图自由）
    起始图=名   → VAEEncode(起始图) 当起始潜变量（改图模式，构图跟着起始图）

    高质量=True → 不挂 Lightning 4 步蒸馏 LoRA，用原模型 + 高 CFG + 多步。
                  慢 5~8 倍，但参考还原度和细节会好非常多。
    """
    g = {}
    节点 = 1

    def 加(类型, 输入, 标题=None):
        nonlocal 节点
        g[str(节点)] = {"class_type": 类型, "inputs": 输入}
        if 标题:
            g[str(节点)]["_meta"] = {"title": 标题}
        n = 节点
        节点 += 1
        return str(n)

    m = 加("UNETLoader", {"unet_name": UNET, "weight_dtype": "default"}, "① 主模型")
    if 高质量:
        步数_用, cfg_用 = 步数高质量, CFG高质量
    else:
        m = 加("LoraLoaderModelOnly", {"model": [m, 0], "lora_name": LORA,
                                    "strength_model": 1.0}, "② Lightning 4步")
        步数_用, cfg_用 = 步数, CFG
    m = 加("ModelSamplingAuraFlow", {"model": [m, 0], "shift": SHIFT}, "③ shift")

    c = 加("CLIPLoader", {"clip_name": CLIP, "type": "qwen_image"}, "④ CLIP")
    v = 加("VAELoader", {"vae_name": VAE}, "⑤ VAE")

    参 = {}
    for i, 名 in enumerate(参考文件名们[:3], 1):
        参[f"image{i}"] = [加("LoadImage", {"image": 名, "upload": "image"},
                             f"⑥ 参考图{i}"), 0]

    if 起始图:
        起 = 加("VAEEncode", {"pixels": [加("LoadImage",
                       {"image": 起始图, "upload": "image"}, "⑦ 起始图"), 0],
                       "vae": [v, 0]}, "⑦b 起始潜变量")
        cond = 加("TextEncodeQwenImageEditPlus",
                 {"clip": [c, 0], "prompt": 提示词, "vae": [v, 0], **参}, "⑧ 编码")
        cond = 加("ReferenceLatent", {"conditioning": [cond, 0], "latent": [起, 0]},
                 "⑨ 参考潜变量")
        neg = 加("TextEncodeQwenImageEditPlus",
                {"clip": [c, 0], "prompt": "", "vae": [v, 0], "image1": 参["image1"]},
                "⑩ 负向")
        潜 = 起
    else:
        cond = 加("TextEncodeQwenImageEditPlus",
                 {"clip": [c, 0], "prompt": 提示词, "vae": [v, 0], **参}, "⑧ 编码")
        cond = 加("ReferenceLatent", {"conditioning": [cond, 0]}, "⑨ 参考潜变量")
        neg = 加("TextEncodeQwenImageEditPlus",
                {"clip": [c, 0], "prompt": "", "vae": [v, 0], "image1": 参["image1"]},
                "⑩ 负向")
        潜 = 加("EmptySD3LatentImage", {"width": 宽, "height": 高, "batch_size": 1},
               "⑦b 空潜变量")

    samp = 加("KSampler", {"model": [m, 0], "positive": [cond, 0], "negative": [neg, 0],
                          "latent_image": [潜, 0], "seed": 种子, "steps": 步数_用,
                          "cfg": cfg_用, "sampler_name": "euler", "scheduler": "simple",
                          "denoise": 降噪}, "⑪ 采样")
    dec = 加("VAEDecode", {"samples": [samp, 0], "vae": [v, 0]}, "⑫ 解码")
    加("SaveImage", {"images": [dec, 0], "filename_prefix": "DSH_ref"}, "⑬ 存图")
    return g


def 贴到画布(参考图路: str, 宽: int, 高: int, 底: str | None = None, 缩放=0.98) -> str:
    """把参考图等比放进 宽×高 画布（白底或指定底图），返回临时文件路径。

    Qwen-Image-Edit 的输出尺寸跟着起始潜变量走，所以先把参考图贴成目标画幅。
    """
    from PIL import Image
    画 = Image.new("RGB", (宽, 高), (245, 245, 245))
    if 底 and os.path.isfile(底):
        背 = Image.open(底).convert("RGB").resize((宽, 高), Image.LANCZOS)
        画.paste(背, (0, 0))
    参 = Image.open(参考图路).convert("RGB")
    参.thumbnail((int(宽 * 缩放), int(高 * 缩放)), Image.LANCZOS)
    画.paste(参, ((宽 - 参.width) // 2, (高 - 参.height) // 2))
    临 = os.path.join(输出根, "_画布.png")
    os.makedirs(输出根, exist_ok=True)
    画.save(临)
    return 临


def 拆三联(图路: str, 每联宽: int | None = None) -> list[str]:
    """Qwen-Image-Edit 有个顽固习惯：把「参考图」和「生成结果」并排画成三联画。
    中间那联是原图的翻版（发白/发光），左右两联才是真正生成的画面。

    这里自动找出白色分隔带，把每一联切出来，返回（左联, 右联）。
    """
    import numpy as np
    from PIL import Image
    im = Image.open(图路).convert("RGB")
    W, H = im.size
    a = np.array(im).astype(int)
    colmean = a.mean(axis=(0, 2))

    # 找连续的高亮竖带（分隔缝）
    缝 = []
    起 = None
    for x, v in enumerate(colmean > 232):
        if v and 起 is None:
            起 = x
        elif not v and 起 is not None:
            if x - 起 >= 6:
                缝.append((起, x - 1))
            起 = None
    if 起 is not None and W - 起 >= 6:
        缝.append((起, W - 1))

    if not 缝:
        return [图路]

    # 用缝把画面切成若干联
    边 = [0]
    for a_, b_ in 缝:
        边 += [a_, b_ + 1]
    边.append(W)
    段 = [(边[i], 边[i + 1]) for i in range(0, len(边) - 1, 2)]
    段 = [(a_, b_) for a_, b_ in 段 if b_ - a_ > W * 0.08]
    if len(段) < 2:
        return [图路]

    # 中间那联 = 原图翻版；取最宽的一联当"原图"，其余都是生成结果
    宽 = [b_ - a_ for a_, b_ in 段]
    中最宽 = 宽.index(max(宽))
    出 = []
    os.makedirs(输出根, exist_ok=True)
    for i, (a_, b_) in enumerate(段):
        if i == 中最宽:
            continue
        p = os.path.join(输出根, f"_联{len(出)+1}_{os.path.basename(图路)}")
        im.crop((a_, 0, b_, H)).save(p)
        出.append(p)
    return 出 or [图路]


def 跑(参考图路们: list[str], 提示词: str, 种子=777, 宽=W, 高=H, 静默=False,
      底: str | None = None, 改图=False, 降噪=0.55, 拆联=False,
      高质量=False) -> str | None:
    os.makedirs(输出根, exist_ok=True)
    文件名们 = [传图(p) for p in 参考图路们[:3]]
    起始 = None
    if 改图:
        起始 = 传图(贴到画布(参考图路们[0], 宽, 高, 底))
    wf = 造工作流(文件名们, 提示词, 种子, 宽, 高, 起始图=起始,
                 降噪=降噪 if 改图 else 1.0, 高质量=高质量)
    pid = 发("/api/prompt", {"prompt": wf})["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(3)
        h = 取(f"/api/history/{pid}")
        if pid in h:
            e = h[pid]
            if e.get("outputs"):
                图 = None
                for _, o in e["outputs"].items():
                    if o.get("images"):
                        图 = o["images"][0]
                if 图:
                    源 = os.path.join(r"D:\Comfy-Desktop\ComfyUI-Shared\output",
                                     图.get("subfolder", ""), 图["filename"])
                    目的 = os.path.join(输出根, f"ref_{种子}_{int(time.time())}.png")
                    with open(源, "rb") as a, open(目的, "wb") as b:
                        b.write(a.read())
                    if not 静默:
                        from PIL import Image as _I
                        print(f"✅ {time.time()-t0:.0f} 秒 → {目的}  {_I.open(目的).size}")
                    if 拆联:
                        联 = 拆三联(目的)
                        if not 静默:
                            from PIL import Image as _I
                            for q in 联:
                                print(f"   ✂ 拆出 {os.path.basename(q)}  {_I.open(q).size}")
                        return 联[0] if 联 else 目的
                    return 目的
                return None
            if e.get("status", {}).get("status_str") == "error":
                print("❌ ComfyUI 报错：")
                for m_ in e.get("status", {}).get("messages", [])[-4:]:
                    print("   ", str(m_)[:400])
                return None
        if time.time() - t0 > 1800:
            print("❌ 超时 30 分钟")
            return None


试词 = (
    "把参考图里的角色原样放进新的场景：黄昏的中国老街道边，"
    "她站在一家小店门口，中景，仰角略低，"
    "电影感打光，浅景深，35mm 胶片质感，画面里只有她一个人"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--试", action="store_true")
    ap.add_argument("--图", nargs="+", default=[])
    ap.add_argument("--词", default=试词)
    ap.add_argument("--出", default=None)
    ap.add_argument("--种子", type=int, default=777)
    ap.add_argument("--宽", type=int, default=W)
    ap.add_argument("--高", type=int, default=H)
    ap.add_argument("--拆联", action="store_true", help="自动切掉中间的参考图翻版")
    ap.add_argument("--高质量", action="store_true", help="不挂 Lightning LoRA，30 步 cfg3.5，慢但准")
    a = ap.parse_args()

    if a.试 or not a.图:
        图们 = [os.path.join(参考根, "DS_女仆鲸鱼娘_官方设定图.png")]
    else:
        图们 = [p if os.path.isabs(p) else os.path.join(参考根, p) for p in a.图]

    for p in 图们:
        if not os.path.isfile(p):
            print(f"❌ 找不到参考图 {p}")
            return 1
    print(f"参考图 {len(图们)} 张：")
    for p in 图们:
        print("   ", os.path.basename(p))
    print(f"提示词：{a.词}")
    出 = 跑(图们, a.词, a.种子, a.宽, a.高, 拆联=a.拆联, 高质量=a.高质量)
    if 出 and a.出:
        import shutil
        shutil.copy(出, a.出)
        print("   →", a.出)
    return 0 if 出 else 1


if __name__ == "__main__":
    sys.exit(main())
