# -*- coding: utf-8 -*-
"""
出片 —— 从「脚本.json」到成片.mp4 的一条命令流水线

  脚本.json → [出图] → [动态镜头转 Wan I2V] → [混编合成] → 成片.mp4

镜头分两种：
  · 普通镜头——只出静帧，合成时做 Ken Burns 运镜（约 4 秒/张，几乎不花时间）
  · 动态镜头——静帧再喂 Wan 2.2 做图生视频（约 4 分钟/5 秒，质量优先环节）

一条片子里通常只有 2~4 个关键镜头值得跑动态，其余用静帧运镜，
性价比最高。在镜头里加 "动态": 5.0 即表示该镜头出 5 秒视频。

用法：
  python 出片.py 脚本.json                    # 全流程
  python 出片.py 脚本.json --只出图            # 只生成图，不合成
  python 出片.py 脚本.json --只合成            # 图已有，只做视频
  python 出片.py 脚本.json --线 14b            # 动态镜头用 14B（更慢更好）
  python 出片.py 脚本.json --跳过动态          # 动态镜头退化为静帧运镜
  python 出片.py --示例                        # 打印一个示例脚本

脚本格式见 --示例
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request

COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
本目录 = os.path.dirname(os.path.abspath(__file__))
混编器 = os.path.join(本目录, "视频拼接.py")
视频生成器 = os.path.join(本目录, "图生视频.py")
PY = sys.executable

示例脚本 = {
    "标题": "示例",
    "画布": "1920x1080",
    "每张秒": 4.0,
    "转场秒": 0.7,
    "BGM": None,
    "风格前缀": "masterpiece, best quality, highly detailed, cinematic lighting, ",
    "输出目录": "D:/DSHworkspace/B站/成片/示例",
    "镜头": [
        # 动态镜头：静帧再喂 Wan 2.2 做图生视频，5 秒片约 4 分钟（质量优先，整片留 2~4 个）
        {"提示词": "a lone lighthouse on a cliff at dusk, stormy sea below",
         "运镜": "推近", "动态": 5.0},
        # 普通镜头：只出静帧，合成时做 Ken Burns 运镜，几乎不花时间
        {"提示词": "close-up of the lamp room, warm light spilling out", "运镜": "左到右"},
        {"提示词": "the keeper's small room, tea steaming on a wooden table", "运镜": "拉远"},
    ],
}

动态默认 = {
    "线": "5b",        # 5b | 14b
    "宽": 832,
    "高": 480,
    "fps": 16,
    "步数": None,      # None = 按线路取默认
}

有声默认 = {
    "宽": 1344, "高": 768, "fps": 24, "秒": 15.0, "步数": 4,
    "超时分钟": 90,
}


# ----------------------------------------------------------------- ComfyUI
def 取(p, 超时=30):
    with urllib.request.urlopen(COMFY + p, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 发(p, 数据, 超时=60):
    req = urllib.request.Request(
        COMFY + p, data=json.dumps(数据).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 检查服务():
    try:
        s = 取("/system_stats", 8)
    except Exception as e:
        print(f"❌ 连不上 ComfyUI ({COMFY})：{e}")
        print("   请先启动 ComfyUI 桌面端，或设 COMFY_API 环境变量")
        sys.exit(1)
    d = s["devices"][0]
    print(f"ComfyUI {s['system']['comfyui_version']}  "
          f"VRAM 空闲 {d['vram_free']/2**30:.1f}/{d['vram_total']/2**30:.1f} GB")
    return s


def 释放显存():
    try:
        发("/free", {"unload_models": True, "free_memory": True})
        time.sleep(1.5)
    except Exception:
        pass


# Qwen-Image 用的是真负面提示词（cfg>1），不是 Z-Image 那种 ZeroOut
负面词 = ("低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，"
          "过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲")
cfg = 4.0


def 建图(提示词, 宽, 高, 种子, 步数, 模型, 文本编码器, vae, shift):
    """构造 Z-Image-Turbo 的 API 工作流（结构取自官方 int8 模板）"""
    return {
        "28": {"class_type": "UNETLoader",
               "inputs": {"unet_name": 模型, "weight_dtype": "default"}},
        "30": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": 文本编码器, "type": "lumina2", "device": "default"}},
        "29": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "27": {"class_type": "CLIPTextEncode",
               "inputs": {"text": 提示词, "clip": ["30", 0]}},
        # Z-Image-Turbo 是 guidance 蒸馏模型（cfg=1.0），负面词无效，官方模板用 ZeroOut
        "33": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["27", 0]}},
        "11": {"class_type": "ModelSamplingAuraFlow",
               "inputs": {"model": ["28", 0], "shift": shift}},
        "13": {"class_type": "EmptySD3LatentImage",
               "inputs": {"width": 宽, "height": 高, "batch_size": 1}},
        "3": {"class_type": "KSampler",
              "inputs": {"model": ["11", 0], "positive": ["27", 0], "negative": ["33", 0],
                         "latent_image": ["13", 0], "seed": 种子, "steps": 步数,
                         "cfg": 1.0, "sampler_name": "res_multistep",
                         "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["29", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": "出片"}},
    }


def 建Qwen图(提示词, 宽, 高, 种子, 步数, 模型, 文本编码器, vae, lora):
    """构造 Qwen-Image 2512 的 API 工作流（20 步原生，或挂 Lightning LoRA 走 4 步）

    与 Z-Image 的两处关键差别：
      1. 文本编码器是 Qwen2.5-VL（模型自带 visual），不是 CLIP
      2. 用 cfg>1 的真负面提示词（Z-Image 那边是 cfg=1 的 ConditioningZeroOut，负面词无效）
    """
    m = {"1": {"class_type": "UNETLoader",
               "inputs": {"unet_name": 模型, "weight_dtype": "default"}},
         "2": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": 文本编码器, "type": "qwen_image", "device": "default"}},
         "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
         "5": {"class_type": "CLIPTextEncode",
               "inputs": {"text": 提示词, "clip": ["2", 0]}},
         "6": {"class_type": "CLIPTextEncode",
               "inputs": {"text": 负面词, "clip": ["2", 0]}},
         "7": {"class_type": "EmptySD3LatentImage",
               "inputs": {"width": 宽, "height": 高, "batch_size": 1}},
         "8": {"class_type": "KSampler",
               "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0],
                          "latent_image": ["7", 0], "seed": 种子, "steps": 步数,
                          "cfg": cfg, "sampler_name": "euler",
                          "scheduler": "simple", "denoise": 1.0}},
         "9": {"class_type": "VAEDecode",
               "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
         "10": {"class_type": "SaveImage",
                "inputs": {"images": ["9", 0], "filename_prefix": "出片"}}}
    if lora:  # 4 步 Lightning：必须 cfg=1.0，否则过曝
        m["11"] = {"class_type": "LoraLoaderModelOnly",
                   "inputs": {"model": ["1", 0], "lora_name": lora,
                              "strength_model": 1.0}}
        m["4"] = {"class_type": "ModelSamplingAuraFlow",
                  "inputs": {"model": ["11", 0], "shift": 3.1}}
        m["8"]["inputs"]["cfg"] = 1.0
    else:     # 20 步原生
        m["4"] = {"class_type": "ModelSamplingAuraFlow",
                  "inputs": {"model": ["1", 0], "shift": 3.1}}
        m["8"]["inputs"]["cfg"] = 4.0
    return m


def 出图一张(图, 超时秒=600):
    """提交并等到出图，返回 (文件名, 子目录)"""
    r = 发("/prompt", {"prompt": 图})
    pid = r["prompt_id"]
    起 = time.time()
    轮 = 0
    while time.time() - 起 < 超时秒:
        time.sleep(1.2)
        轮 += 1
        try:
            h = 取(f"/history/{pid}", 15)
        except Exception:
            continue
        if pid not in h:
            continue
        rec = h[pid]
        状态 = rec.get("status", {})
        if 状态.get("status_str") == "error" or 状态.get("completed") is False:
            消息 = json.dumps(状态.get("messages", []), ensure_ascii=False)[:400]
            raise RuntimeError(f"ComfyUI 报错: {消息}")
        出 = rec.get("outputs", {})
        for nid, o in 出.items():
            for im in o.get("images", []):
                return im["filename"], im.get("subfolder", ""), time.time() - 起
        if 轮 > 4:
            raise RuntimeError("任务结束但没拿到图片")
    raise RuntimeError(f"等图超时（{超时秒}s）")


def 下载图(文件名, 子目录, 存到):
    import urllib.parse
    q = urllib.parse.urlencode({"filename": 文件名, "subfolder": 子目录, "type": "output"})
    with urllib.request.urlopen(f"{COMFY}/view?{q}", timeout=120) as r:
        数据 = r.read()
    with open(存到, "wb") as f:
        f.write(数据)
    return len(数据)


# ----------------------------------------------------------------- 主流程
def 对齐分辨率(画布):
    """把画布尺寸换算成适合生成的尺寸（16 的倍数、约 1.0~1.4 MP）"""
    w, h = (int(x) for x in 画布.lower().split("x"))
    比 = w / h
    if abs(比 - 16 / 9) < 0.05:
        return 1536, 864
    if abs(比 - 9 / 16) < 0.05:
        return 864, 1536
    if abs(比 - 4 / 3) < 0.05:
        return 1152, 864
    if abs(比 - 1.0) < 0.05:
        return 1024, 1024
    # 通用：以 1.33MP 为预算、16 的倍数
    像素 = 1_327_680
    高 = int(round((像素 / 比) ** 0.5 / 16)) * 16
    宽 = int(round((像素 * 比) ** 0.5 / 16)) * 16
    return 宽, 高


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("脚本", nargs="?", help="脚本 json 路径")
    ap.add_argument("--只出图", action="store_true")
    ap.add_argument("--只合成", action="store_true")
    ap.add_argument("--示例", action="store_true", help="打印示例脚本")
    ap.add_argument("--步数", type=int, default=None,
                    help="默认：Z-Image 8 步 / Qwen 4 步")
    ap.add_argument("--出图线", choices=["zimage", "qwen"], default="zimage",
                    help="出图用哪个模型：zimage（快、动画感）或 qwen（慢一点、CG 写实感）")
    ap.add_argument("--模型", default=None)
    ap.add_argument("--文本编码器", default=None)
    ap.add_argument("--vae", default=None)
    ap.add_argument("--lora", default="Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors",
                    help="Qwen 线挂的加速 LoRA；传空字符串则走 20 步原生")
    ap.add_argument("--shift", type=float, default=None)
    ap.add_argument("--种子", type=int, default=None, help="固定种子（默认随机）")
    ap.add_argument("--不释放显存", action="store_true")
    ap.add_argument("--线", choices=["5b", "14b"], default=None,
                    help="动态镜头走哪条 Wan 线路（默认取脚本里的「动态线」或 5b）")
    ap.add_argument("--跳过动态", action="store_true",
                    help="所有动态镜头退化为静帧运镜（想快速看整体节奏时用）")
    ap.add_argument("--跳过有声", action="store_true",
                    help="所有有声镜头退化为静帧运镜（MiniMax 太慢时先看画面节奏）")
    args = ap.parse_args()

    if args.示例 or not args.脚本:
        print(json.dumps(示例脚本, ensure_ascii=False, indent=2))
        return

    with open(args.脚本, encoding="utf-8") as f:
        脚本 = json.load(f)

    画布 = 脚本.get("画布", "1920x1080")
    每张秒 = float(脚本.get("每张秒", 4.0))
    转场秒 = float(脚本.get("转场秒", 0.7))
    bgm = 脚本.get("BGM")
    风格前缀 = 脚本.get("风格前缀", "")
    # 角色锁：拼在风格前缀之后、每条提示词之前，全句只出现一次。
    # 不能写成「每个镜头都出现的角色…」这类复数语义，模型会照着画一群。
    角色前缀 = 脚本.get("角色", "")

    def 本镜提示词(镜):
        """角色锁默认全片生效，但「空镜」需要它让位：
        镜里写 "角色": "" 或 "无角色": true 就这一镜去掉角色前缀；
        写别的字符串就这一镜换一个角色描述。"""
        r = 角色前缀
        if 镜.get("无角色") or 镜.get("角色") == "":
            r = ""
        elif 镜.get("角色"):
            r = 镜["角色"]
        return 风格前缀 + r + 镜["提示词"]

    镜头表 = 脚本["镜头"]
    输出目录 = 脚本.get("输出目录") or os.path.join(
        os.path.dirname(os.path.abspath(args.脚本)), "成片")
    图目录 = os.path.join(输出目录, "图")
    os.makedirs(图目录, exist_ok=True)

    print(f"《{脚本.get('标题', '(无题)')}》  {len(镜头表)} 个镜头  {画布}")
    print(f"输出: {输出目录}\n")

    # ---------- 阶段1：出图 ----------
    图路径表 = []
    if not args.只合成:
        检查服务()
        if not args.不释放显存:
            print("先释放其他进程占用的显存 ...")
            释放显存()
        生成宽, 生成高 = 对齐分辨率(画布)
        print(f"生成分辨率 {生成宽}x{生成高}（画布 {画布}）")

        # 按出图线补齐默认值
        if args.出图线 == "qwen":
            模型 = args.模型 or "qwen_image_2512_fp8_e4m3fn.safetensors"
            编码器 = args.文本编码器 or "qwen_2.5_vl_7b_fp8_scaled.safetensors"
            vae名 = args.vae or "qwen_image_vae.safetensors"
            步数 = args.步数 if args.步数 is not None else (4 if args.lora else 20)
            print(f"出图线 Qwen-Image 2512 | {步数} 步 | "
                  f"{'LoRA ' + args.lora if args.lora else '原生'}\n")
        else:
            模型 = args.模型 or "z_image_turbo_int8_convrot.safetensors"
            编码器 = args.文本编码器 or "qwen_3_4b_fp8_mixed.safetensors"
            vae名 = args.vae or "ae.safetensors"
            步数 = args.步数 if args.步数 is not None else 8
            print(f"出图线 Z-Image-Turbo | {步数} 步 | shift={args.shift or 3.0}\n")

        for i, 镜 in enumerate(镜头表, 1):
            提示词 = 本镜提示词(镜)
            种子 = args.种子 if args.种子 is not None else random.randint(0, 2**31 - 1)
            存到 = os.path.join(图目录, f"{i:02d}.png")
            print(f"[{i}/{len(镜头表)}] {镜['提示词'][:70]}")
            print(f"        种子 {种子}")
            try:
                if args.出图线 == "qwen":
                    图 = 建Qwen图(提示词, 生成宽, 生成高, 种子, 步数,
                                  模型, 编码器, vae名, args.lora)
                else:
                    图 = 建图(提示词, 生成宽, 生成高, 种子, 步数,
                              模型, 编码器, vae名, args.shift or 3.0)
                文件名, 子目录, 耗时 = 出图一张(图)
                大小 = 下载图(文件名, 子目录, 存到)
                print(f"        ✅ {耗时:.1f}s  {大小/1024:.0f} KB  → {os.path.basename(存到)}")
                图路径表.append(存到)
            except Exception as e:
                print(f"        ❌ {e}")
                if os.path.exists(存到):
                    print("        （沿用上一次的图）")
                    图路径表.append(存到)
    else:
        图路径表 = sorted(
            os.path.join(图目录, f) for f in os.listdir(图目录)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        )
        print(f"复用已有 {len(图路径表)} 张图")

    if not 图路径表:
        print("❌ 没有任何图，无法合成")
        sys.exit(1)

    if args.只出图:
        print(f"\n✅ 出图完成：{len(图路径表)} 张 → {图目录}")
        return

    # ---------- 阶段2：动态镜头 → Wan 图生视频 ----------
    # 只有标了 "动态": 秒数 的镜头才跑，这是全流程唯一的「质量优先」环节
    动目录 = os.path.join(输出目录, "动")
    动态表 = {}          # 镜头序号 → mp4 路径
    if not args.跳过动态:
        待做 = []
        for i, 镜 in enumerate(镜头表):
            d = 镜.get("动态")
            if d and i < len(图路径表):
                待做.append((i, float(d) if not isinstance(d, bool) else 5.0))
        if 待做:
            配置 = dict(动态默认)
            配置.update(脚本.get("动态参数", {}))
            线 = args.线 or 配置["线"]
            配置["线"] = 线
            步数 = 配置.get("步数") or (8 if 线 == "5b" else 4)
            # 竖屏画布对应竖屏视频。
            # 注意：这里必须转成 int 再比 —— 字符串比较 "1280" >= "720" 是 False
            # （逐字符比，'1' < '7'），会把横屏画布判成竖屏。
            布宽, 布高 = (int(x) for x in 画布.lower().split("x"))
            横 = 布宽 >= 布高
            bw, bh = (配置["宽"], 配置["高"]) if 横 else (配置["高"], 配置["宽"])
            os.makedirs(动目录, exist_ok=True)
            print(f"\n动态镜头 {len(待做)}/{len(镜头表)} 个 → Wan 2.2 {线.upper()} "
                  f"{bw}x{bh} {步数}步")
            print("（5B 约 20~40 秒一段；14B 较慢。这是全流程唯一的「质量优先」环节）\n")
            for k, (i, 秒) in enumerate(待做, 1):
                帧 = int(round(秒 * 配置["fps"]))
                帧 = max(5, (帧 - 1) // 4 * 4 + 1)          # 必须 4n+1
                真秒 = 帧 / 配置["fps"]
                存到 = os.path.join(动目录, f"{i+1:02d}.mp4")
                print(f"[动 {k}/{len(待做)}] 镜头{i+1}  {真秒:.1f}s ({帧}帧)")
                if os.path.exists(存到) and os.path.getsize(存到) > 10000:
                    print(f"        （已有，跳过）")
                    动态表[i] = 存到
                    continue
                cmd = [PY, 视频生成器,
                       "--图", 图路径表[i],
                       "--提示词", 本镜提示词(镜头表[i]),
                       "--宽", str(bw), "--高", str(bh),
                       "--帧", str(帧), "--fps", str(配置["fps"]),
                       "--线", 线, "--步数", str(步数),
                       "--输出", 存到]
                if i:
                    cmd.append("--不释放显存")   # 后面还有镜头，别反复卸载
                子 = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
                尾 = [l for l in (子.stdout or "").strip().splitlines() if l.strip()]
                for l in 尾[-3:]:
                    print("        " + l.strip())
                if 子.returncode != 0 or not os.path.exists(存到):
                    print(f"        ❌ 动态失败，该镜头退回静帧运镜")
                    print("        " + (子.stderr or "")[-400:].strip())
                else:
                    动态表[i] = 存到

    # ---------- 阶段2.5：有声镜头 → MiniMax-H3 文生视频（自带音轨） ----------
    # 标了 "有声": {"秒": N, "提示词": "..."} 的镜头走这条线。
    # 只有它能把声音做出来（人声/环境音/音效跟画面一起生成），是全流程最慢的一环。
    声目录 = os.path.join(输出目录, "声")
    有声表 = {}          # 镜头序号 → mp4 路径
    if not args.跳过有声:
        待声 = [(i, 镜["有声"]) for i, 镜 in enumerate(镜头表)
                if isinstance(镜.get("有声"), dict)]
        if 待声:
            os.makedirs(声目录, exist_ok=True)
            声配 = dict(有声默认)
            声配.update(脚本.get("有声参数", {}))
            print(f"\n有声镜头 {len(待声)}/{len(镜头表)} 个 → MiniMax-H3 "
                  f"{声配['宽']}x{声配['高']} {声配['步数']}步 自带音轨")
            print(f"（单支约 {声配['宽']*声配['高']/768/512*15/5*163/60:.0f} 分钟，最慢的一环，耐心等）\n")
            for k, (i, 配) in enumerate(待声, 1):
                秒 = float(配.get("秒", 声配["秒"]))
                帧 = int(round(秒 * 声配["fps"]))
                帧 = max(5, (帧 - 1) // 4 * 4 + 1)
                真秒 = 帧 / 声配["fps"]
                存到 = os.path.join(声目录, f"{i+1:02d}.mp4")
                print(f"[声 {k}/{len(待声)}] 镜头{i+1}  {真秒:.1f}s ({帧}帧)")
                if os.path.exists(存到) and os.path.getsize(存到) > 10000:
                    print("        （已有，跳过）")
                    有声表[i] = 存到
                    continue
                cmd = [PY, 视频生成器,
                       "--提示词", 配.get("提示词") or 本镜提示词(镜头表[i]),
                       "--宽", str(声配["宽"]), "--高", str(声配["高"]),
                       "--帧", str(帧), "--fps", str(声配["fps"]),
                       "--步数", str(声配["步数"]),
                       "--输出", 存到,
                       "--超时分钟", str(声配["超时分钟"])]
                if k < len(待声):
                    cmd.append("--不释放显存")
                子 = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
                for l in [x for x in (子.stdout or "").strip().splitlines() if x.strip()][-3:]:
                    print("        " + l.strip())
                if 子.returncode != 0 or not os.path.exists(存到):
                    print("        ❌ 有声镜头失败，改用它自己的静帧运镜（这一段会没声音）")
                    print("        " + (子.stderr or "")[-400:].strip())
                else:
                    有声表[i] = 存到

    # ---------- 阶段3：混编合成 ----------
    print(f"\n合成中（静帧 {每张秒}s，转场 {转场秒}s，"
          f"动态 {len(动态表)} 段）...")
    出片 = os.path.join(输出目录, f"{脚本.get('标题', '成片')}.mp4")
    清单 = {
        "画布": 画布,
        # 有有声镜头就按 24fps 出片（对白戏要电影帧率）；否则沿用 Wan 的 16fps
        "fps": 有声默认["fps"] if 有声表 else (动态默认["fps"] if 动态表 else 24),
        "转场秒": 转场秒,
        "片段": [],
    }
    if 脚本.get("BGM") and os.path.exists(脚本["BGM"]):
        清单["BGM"] = 脚本["BGM"]
    for i, 镜 in enumerate(镜头表):
        if i >= len(图路径表):
            break
        字 = 镜.get("字幕")
        if i in 有声表:
            段 = {"类型": "视频", "文件": 有声表[i].replace("\\", "/")}
        elif i in 动态表:
            段 = {"类型": "视频", "文件": 动态表[i].replace("\\", "/")}
        else:
            段 = {"类型": "图", "文件": 图路径表[i].replace("\\", "/"),
                  # 镜头可以单独指定停留秒数（短剧按台词长度算），没写就用全局每张秒
                  "秒": float(镜.get("秒", 每张秒)), "运镜": 镜.get("运镜", "推近")}
        if 字:
            段["字幕"] = 字
        清单["片段"].append(段)
    清单路径 = os.path.join(输出目录, "_清单.json")
    with open(清单路径, "w", encoding="utf-8") as f:
        json.dump(清单, f, ensure_ascii=False, indent=2)

    cmd = [PY, 混编器, "--清单", 清单路径, "--out", 出片]
    if bgm:
        cmd += ["--bgm", bgm]
    if 脚本.get("BGM音量") is not None:
        cmd += ["--bgm音量", str(脚本["BGM音量"])]
    子 = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if 子.returncode != 0:
        print("❌ 合成失败：")
        print(子.stdout[-2000:] if 子.stdout else "")
        print(子.stderr[-2000:] if 子.stderr else "")
        sys.exit(1)
    for 行 in (子.stdout or "").strip().splitlines():
        if 行.strip():
            print("   " + 行.strip())

    print(f"\n{'='*60}")
    print(f"✅ 成片 {出片}")
    print(f"   {os.path.getsize(出片)/1024/1024:.1f} MB")

    # ---------- 阶段4：生成投稿信息 ----------
    # 注意：这里只「备好」投稿文案，不投。必须先给人看过、签字，投稿.py 才肯动。
    投稿 = 生成投稿信息(脚本, 输出目录, 出片)
    审核页 = os.path.join(输出目录, "审核.html")
    print(f"\n✅ 投稿信息 {投稿}")
    print(f"   标题 {投稿信息缓存['标题']}")
    print(f"\n下一步是审片，不是投稿：")
    print(f"   python 审片.py \"{输出目录}\"        # 生成审核页（有 Edge 会直接打开）")
    print(f"   看完再签字：--通过  或  --打回 -备注 \"...\"")


投稿信息缓存 = {}


def 生成投稿信息(脚本, 输出目录, 出片):
    """把脚本.json 里的「投稿」块落成投稿信息.json，供 投稿.py 使用。

    「投稿」块可选，缺省时用「标题」当稿件标题、风格前缀当简介占位。
    封面：输出目录里优先找 封面/封面_<标题>_带字.png，其次 封面/*带字*.png，
          再其次 封面/*.png，最后留空（B站自动截帧）。
    """
    global 投稿信息缓存
    投 = 脚本.get("投稿") or {}
    标题 = 投.get("标题") or 脚本.get("标题", "未命名")
    活动 = 投.get("活动", "")
    if 活动 and 活动 not in 标题:
        标题 = f"{活动}｜《{标题}》"
    elif not 活动 and not 标题.startswith("《"):
        标题 = f"《{标题}》"
    副 = 投.get("副标题", "")
    if 副:
        标题 = f"{标题}：{副}"
    if len(标题) > 80:          # B站上限 80 字，超了先砍副标题
        标题 = 标题[:80] if not 副 else f"{标题[:80-len(副)-1]}：{副}"
        if len(标题) > 80:
            标题 = 标题[:80]

    简介 = 投.get("简介", "")
    if not 简介:
        镜头数 = len(脚本.get("镜头", []))
        简介 = f"{脚本.get('标题','')}——{镜头数} 个镜头，全部由本地 AI 生成。"

    # 封面
    封面 = ""
    封面目录 = os.path.join(输出目录, "封面")
    if os.path.isdir(封面目录):
        候选 = sorted(
            (f for f in os.listdir(封面目录) if f.lower().endswith((".png", ".jpg", ".jpeg"))),
            key=lambda f: (0 if "带字" in f else 1, f),
        )
        if 候选:
            封面 = os.path.join(封面目录, 候选[0])

    info = {
        "视频": 出片,
        "标题": 标题,
        "简介": 简介,
        "标签": 投.get("标签", []),
        "分区": 投.get("分区", 27),
        "封面": 封面,
        "AI生成声明": 投.get("AI声明", True),
        "定时发布时间": 投.get("定时发布时间", ""),
    }
    路径 = os.path.join(输出目录, "投稿信息.json")
    with open(路径, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    投稿信息缓存 = info
    return 路径


if __name__ == "__main__":
    main()
