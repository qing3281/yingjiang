# -*- coding: utf-8 -*-
"""影匠 —— 引擎：把活派给本机 ComfyUI，把片子收回来。

零依赖：只用 Python 标准库 + 本机已有 requests。
    import 引擎
    路 = 引擎.文生图("一个穿红裙的女子站在雨中的霓虹街口", 种子=1)
    片 = 引擎.图生视频(路, "她缓缓抬头，雨水顺着发梢滑落")

设计原则
--------
1. **一份模板，处处改**：工作流不写死，从这里 `模板` 目录读 json，
   只替换提示词/种子/尺寸/步数。换模型 = 换一个 json，不动代码。
2. **看得见进度**：排队、跑、取图，每一步都往 callback 里报。
3. **失败要说人话**：ComfyUI 的报错原样带回来，不吞。
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request

这里 = os.path.dirname(os.path.abspath(__file__))
模板目录 = os.path.join(这里, "模板")
作品目录 = os.path.join(这里, "作品")
os.makedirs(模板目录, exist_ok=True)
os.makedirs(作品目录, exist_ok=True)

COMFY = os.environ.get("影匠_COMFY", "http://127.0.0.1:8188")

# ───────────────────────────── HTTP ─────────────────────────────


def _请求(路: str, 数据=None, 超时: int = 60, 原始: bool = False):
    """访问 ComfyUI。原始=True 时返回 bytes。"""
    网址 = COMFY + 路
    try:
        if 数据 is None:
            with urllib.request.urlopen(网址, timeout=超时) as r:
                b = r.read()
        else:
            体 = json.dumps(数据).encode("utf-8")
            req = urllib.request.Request(
                网址, data=体, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=超时) as r:
                b = r.read()
    except urllib.error.HTTPError as e:
        详情 = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"ComfyUI 返回 {e.code}：{详情[:600]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"连不上 ComfyUI（{COMFY}）：{e.reason}") from None
    if 原始:
        return b
    return json.loads(b.decode("utf-8"))


def 在线() -> dict:
    """探活。返回 {在线, 版本, 显卡, 显存GB}。"""
    try:
        s = _请求("/system_stats", 超时=8)
        d = (s.get("devices") or [{}])[0]
        return {
            "在线": True,
            "版本": s.get("system", {}).get("comfyui_version", "?"),
            "显卡": d.get("name", "?"),
            "显存GB": round(d.get("vram_total", 0) / 1024**3, 1),
            "显存空闲GB": round(d.get("vram_free", 0) / 1024**3, 1),
        }
    except Exception as e:
        return {"在线": False, "错": str(e)}


# ───────────────────────────── 模板 ─────────────────────────────


def 读模板(名: str) -> dict:
    路 = os.path.join(模板目录, 名 if 名.endswith(".json") else 名 + ".json")
    if not os.path.exists(路):
        raise RuntimeError(f"没有模板 {名}（该有：{路}）")
    with open(路, "r", encoding="utf-8") as f:
        return json.load(f)


def 列模板() -> list[str]:
    return sorted(
        f[:-5] for f in os.listdir(模板目录) if f.endswith(".json")
    )


# ───────────────────────────── 派工 ─────────────────────────────


def 派工(工作流: dict, 报=None, 等: bool = True, 上限秒: int = 1800) -> dict:
    """提交工作流，等它跑完，返回 {提示号, 图们:[{文件名,子目录,类型}], 耗时}。"""
    报 = 报 or (lambda _: None)
    r = _请求("/prompt", {"prompt": 工作流}, 超时=60)
    if "error" in r:
        raise RuntimeError(f"ComfyUI 拒绝了这个工作流：{json.dumps(r, ensure_ascii=False)[:800]}")
    号 = r["prompt_id"]
    报(f"已排队 {号[:8]}")
    if not 等:
        return {"提示号": 号}

    起 = time.time()
    上次 = 0.0
    while True:
        if time.time() - 起 > 上限秒:
            raise RuntimeError(f"等了 {上限秒} 秒还没跑完（提示号 {号[:8]}）")
        史 = _请求(f"/history/{号}", 超时=20)
        if 号 in 史:
            条 = 史[号]
            状 = 条.get("status", {})
            if 状.get("status_str") == "error" or not 状.get("completed", True):
                信 = 状.get("messages") or []
                raise RuntimeError(f"工作流跑挂了：{json.dumps(信, ensure_ascii=False)[:800]}")
            图们 = []
            出 = 条.get("outputs", {})
            for 节点号, 出项 in 出.items():
                for 图 in 出项.get("images", []) or []:
                    图们.append(图)
                for 视 in 出项.get("gifs", []) or []:
                    图们.append(视)
            if not 图们:
                raise RuntimeError("跑完了但没有输出（检查 SaveImage/保存节点接对了没）")
            return {
                "提示号": 号,
                "图们": 图们,
                "耗时": round(time.time() - 起, 1),
            }
        # 进度
        now = time.time()
        if now - 上次 > 3:
            上次 = now
            try:
                队 = _请求("/queue", 超时=10)
                跑 = len(队.get("queue_running", []))
                排 = len(队.get("queue_pending", []))
                报(f"等待中… 跑 {跑} 排 {排}  已等 {int(now-起)} 秒")
            except Exception:
                pass
        time.sleep(1.2)


def 取图(图: dict, 存到: str | None = None) -> str:
    """把一张输出图/视频下载到本地。返回本地路径。"""
    from urllib.parse import urlencode

    参 = urlencode(
        {
            "filename": 图["filename"],
            "subfolder": 图.get("subfolder", ""),
            "type": 图.get("type", "output"),
        }
    )
    b = _请求(f"/view?{参}", 超时=300, 原始=True)
    if 存到 is None:
        存到 = os.path.join(作品目录, 图["filename"])
    os.makedirs(os.path.dirname(存到), exist_ok=True)
    with open(存到, "wb") as f:
        f.write(b)
    return 存到


# ───────────────────────────── 文生图 ─────────────────────────────


def 文生图(
    提示词: str,
    负面: str = "",
    种子: int | None = None,
    宽: int = 1024,
    高: int = 1024,
    步数: int = 8,
    模板: str = "zimage_turbo",
    前缀: str = "影匠",
    报=None,
    存到: str | None = None,
) -> dict:
    """按模板出一张图。返回 {路, 种子, 耗时}。

    zimage_turbo 是 8 步 Turbo，cfg 固定 1.0，不需要负面词（会自动零化）。
    """
    报 = 报 or (lambda _: None)
    种 = 种子 if 种子 is not None else random.randint(1, 2**31)

    wf = 读模板(模板)
    改 = 0
    for 号, 节 in wf.items():
        类 = 节.get("class_type", "")
        ins = 节.setdefault("inputs", {})
        if 类 in ("CLIPTextEncode", "T5TextEncode", "TextEncodeQwenImageEdit"):
            # 正向=第一个遇到的；其余（负面）走负面词或零化
            if 改 == 0:
                ins["text"] = 提示词
                改 = 1
            elif 负面 and not 节.get("_零化"):
                ins["text"] = 负面
        elif 类 == "EmptySD3LatentImage" or 类 == "EmptyLatentImage":
            ins["width"] = 宽
            ins["height"] = 高
        elif 类 in ("KSampler", "KSamplerAdvanced"):
            if "seed" in ins:
                ins["seed"] = 种
            if "noise_seed" in ins:
                ins["noise_seed"] = 种
            if ins.get("sampler_name") not in ("", None):
                ins["steps"] = 步数
        elif 类 in ("SaveImage", "SaveAnimatedWEBP", "SaveVideo", "VHS_VideoCombine"):
            if "filename_prefix" in ins:
                ins["filename_prefix"] = 前缀

    if 改 == 0:
        raise RuntimeError(f"模板 {模板} 里找不到文本编码节点，改不了提示词")

    报(f"提交：{提示词[:40]}…  种子 {种}")
    果 = 派工(wf, 报=报)
    图 = 果["图们"][0]
    路 = 取图(图, 存到)
    报(f"出图：{os.path.basename(路)}")
    return {"路": 路, "种子": 种, "耗时": 果["耗时"], "原始": 图}


# ───────────────────────────── 图生视频 ─────────────────────────────


def 图生视频(
    图路: str,
    提示词: str,
    负面: str = "",
    种子: int | None = None,
    帧数: int = 49,
    帧率: int = 16,
    宽: int = 0,
    高: int = 0,
    模板: str = "wan22_i2v",
    前缀: str = "影匠片",
    报=None,
    存到: str | None = None,
) -> dict:
    """拿一张图 + 一句话，出一段视频。

    先把图上传进 ComfyUI，再按模板派工。
    """
    报 = 报 or (lambda _: None)
    种 = 种子 if 种子 is not None else random.randint(1, 2**31)
    if not os.path.exists(图路):
        raise RuntimeError(f"找不到图：{图路}")

    上 = 上传图(图路)
    报(f"上传 {os.path.basename(图路)} → {上['name']}")

    wf = 读模板(模板)
    # 模板里允许有 "_说明" 这类注释键，值不是 dict，先剔掉
    wf = {号: 节 for 号, 节 in wf.items() if isinstance(节, dict) and "class_type" in 节}

    def _认():
        """顺着采样器的连线倒推：哪个是正向词节点、哪个是负向词节点。"""
        正号 = 负号 = 潜号 = 采号 = None
        for 号, 节 in wf.items():
            if 节.get("class_type") in ("KSampler", "KSamplerAdvanced"):
                采号 = 号
                ins = 节.get("inputs", {})
                if isinstance(ins.get("positive"), list):
                    正号 = ins["positive"][0]
                if isinstance(ins.get("negative"), list):
                    负号 = ins["negative"][0]
                if isinstance(ins.get("latent_image"), list):
                    潜号 = ins["latent_image"][0]
        return 正号, 负号, 潜号, 采号

    正号, 负号, 潜号, 采号 = _认()

    for 号, 节 in wf.items():
        类 = 节.get("class_type", "")
        ins = 节.setdefault("inputs", {})

        if 类 in ("CLIPTextEncode", "T5TextEncode"):
            if 号 == 正号:
                ins["text"] = 提示词
            elif 号 == 负号:
                ins["text"] = 负面 or "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"

        elif 类 == "LoadImage":
            ins["image"] = 上["name"]

        elif 类 in ("KSampler", "KSamplerAdvanced"):
            if "seed" in ins:
                ins["seed"] = 种
            if "noise_seed" in ins:
                ins["noise_seed"] = 种

        elif 类 in ("WanImageToVideo", "Wan22ImageToVideoLatent", "WanFirstLastFrameToVideo"):
            if "length" in ins:
                ins["length"] = 帧数
            if 宽 > 0 and "width" in ins:
                ins["width"] = 宽
            if 高 > 0 and "height" in ins:
                ins["height"] = 高

        elif 类 == "CreateVideo":
            ins["fps"] = 帧率

        elif 类 in ("SaveVideo", "VHS_VideoCombine", "SaveAnimatedWEBP"):
            if "frame_rate" in ins:
                ins["frame_rate"] = 帧率
            if "fps" in ins:
                ins["fps"] = 帧率
            if "filename_prefix" in ins:
                ins["filename_prefix"] = 前缀

    if 正号 is None:
        raise RuntimeError(f"模板 {模板} 里找不到正向文本节点（采样器没接 CLIPTextEncode）")
    if not any(节.get("class_type") == "LoadImage" for 节 in wf.values()):
        raise RuntimeError(f"模板 {模板} 里没有 LoadImage 节点，接不上图")

    报(f"提交视频：{提示词[:40]}…  种子 {种}  {帧数}帧 @{帧率}fps")
    果 = 派工(wf, 报=报, 上限秒=3600)
    出 = 果["图们"][0]
    路 = 取图(出, 存到)
    报(f"出片：{os.path.basename(路)}")
    return {"路": 路, "种子": 种, "耗时": 果["耗时"], "原始": 出}


# ───────────────────────────── 上传 ─────────────────────────────


def 上传图(图路: str) -> dict:
    """
    把本地图塞进 ComfyUI 的 input 目录。返回 {name, subfolder, type}。

    注意：HTTP 头只能是 latin-1，**中文文件名塞不进去**（会 UnicodeEncodeError）。
    所以这里统一把文件重命名成 `yj_<内容哈希>.<后缀>` 再传 —— 顺便自带去重，
    同一张图传两次只会留一份。
    """
    import hashlib
    import mimetypes
    import uuid

    with open(图路, "rb") as f:
        内容 = f.read()

    原后缀 = os.path.splitext(图路)[1].lower() or ".png"
    指纹 = hashlib.md5(内容).hexdigest()[:12]
    名 = f"yj_{指纹}{原后缀}"
    类 = mimetypes.guess_type(名)[0] or "image/png"

    界 = "----yj" + uuid.uuid4().hex
    体 = b"".join(
        [
            f"--{界}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{名}"\r\n'.encode("ascii"),
            f"Content-Type: {类}\r\n\r\n".encode("ascii"),
            内容,
            f"\r\n--{界}--\r\n".encode(),
        ]
    )
    req = urllib.request.Request(
        COMFY + "/upload/image",
        data=体,
        headers={"Content-Type": f"multipart/form-data; boundary={界}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            果 = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"上传失败 {e.code}：{e.read().decode('utf-8','replace')[:400]}") from None
    果.setdefault("name", 名)
    return 果


# ───────────────────────────── 清单 ─────────────────────────────


def 列模型() -> dict:
    """这台机器上有什么能用的。"""
    出 = {"文生图": [], "视频": [], "CLIP": [], "VAE": [], "LoRA": []}
    对 = {
        "CheckpointLoaderSimple": ("文生图", "ckpt_name"),
        "UNETLoader": ("视频", "unet_name"),  # 后面再分
        "CLIPLoader": ("CLIP", "clip_name"),
        "VAELoader": ("VAE", "vae_name"),
        "LoraLoader": ("LoRA", "lora_name"),
    }
    图模型 = ("flux", "sd_xl", "sdxl", "qwen_image", "z_image", "zimage", "sd3", "pony", "illustrious")
    视模型 = ("wan", "minimax", "h3", "ltx", "cogvideo", "hunyuan")
    for 节点, (桶, 键) in 对.items():
        try:
            o = _请求(f"/object_info/{节点}", 超时=15)
            值 = o[节点]["input"]["required"][键][0]
            if not isinstance(值, list):
                continue
            for v in 值:
                b = 桶
                if 节点 == "UNETLoader":
                    低 = v.lower()
                    b = "文生图" if any(k in 低 for k in 图模型) else ("视频" if any(k in 低 for k in 视模型) else "视频")
                出[b].append(v)
        except Exception:
            pass
    return 出


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "体检":
        print(json.dumps(在线(), ensure_ascii=False, indent=2))
        print("模板：", 列模板())
        m = 列模型()
        for k, v in m.items():
            print(f"\n{k}（{len(v)}）")
            for x in v[:40]:
                print("   ", x)
    elif len(sys.argv) > 1 and sys.argv[1] == "试":
        词 = sys.argv[2] if len(sys.argv) > 2 else "a lone swordsman standing on a snowy ridge at dawn, back view, wide shot, cinematic"
        r = 文生图(词, 报=lambda s: print("  ", s))
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("用法：python 引擎.py 体检 | python 引擎.py 试 \"提示词\"")
