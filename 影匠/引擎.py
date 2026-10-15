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
4. **说不清就不许当失败**：提交之后才跟丢的（等超时 / 轮询断链）抛 `提交未知`，
   带着提示号一起交出去 —— 上层拿它记账本里的「未知」态，交人工核对，
   绝不自动重跑（钱可能已经花过一次了）。跑挂了/没输出这种明确失败仍是 RuntimeError。
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request

这里 = os.path.dirname(os.path.abspath(__file__))
默认负面 = ("blurry, low quality, watermark, text, subtitles, extra fingers, deformed hands, "
            "cartoon, 3d render, oversaturated")

模板目录 = os.path.join(这里, "模板")
作品目录 = os.path.join(这里, "作品")
os.makedirs(模板目录, exist_ok=True)
os.makedirs(作品目录, exist_ok=True)

COMFY = os.environ.get("影匠_COMFY", "http://127.0.0.1:8188")

# ───────────────────────────── 端点 ─────────────────────────────
# 两条线同时生产：同一份 剧组.py，换个端点就把活派给另一台机器。
#     引擎.换端点("远端")
#     引擎.换端点()                 # 不传 = 报当前端点
# 命令行也行：影匠_COMFY=http://100.127.224.106:8188 python 剧组.py 出图 试镜
# 备注：ComfyUI 默认只听 127.0.0.1，远端那份启动时要 --listen 0.0.0.0（或 --listen 100.127.224.106）。
端点表 = {
    "本机": os.environ.get("影匠_COMFY", "http://127.0.0.1:8188"),
    "远端": os.environ.get("影匠_COMFY_远端", "http://100.127.224.106:8188"),
}
端点名 = "本机"


def 是本机() -> bool:
    """当前端点是不是这台机器。

    为什么需要它：`模型完好()` 是拿**本机磁盘上的文件**去校验模型的。
    端点在远端时那个校验毫无意义 —— 它只会说「本机找不到文件」，
    然后被当成「信 ComfyUI」放行，看起来通过了、其实根本没查。
    """
    return any(x in COMFY for x in ("127.0.0.1", "localhost", "::1"))


def 换端点(名或址: str | None = None) -> dict:
    """切 ComfyUI 端点，或只查当前端点（不传参）。

    可给 '本机' / '远端' / 一个 http:// 地址。返回 {端点, 名, 是本机}。
    切完清缓存 —— 两台机器的模型库不是同一份，留旧缓存会误判。
    """
    global COMFY, 端点名
    if 名或址 is not None:
        原 = str(名或址).strip()
        if 原 in 端点表:
            COMFY, 端点名 = 端点表[原], 原
        elif 原.startswith("http"):
            COMFY, 端点名 = 原.rstrip("/"), "自定义"
        else:
            raise RuntimeError(
                f"不认识端点「{名或址}」—— 可用：{'、'.join(端点表)}，或一个 http:// 地址")
        _模型缓存["时间"] = 0.0
        _模型缓存["表"] = None
        _完好缓存.clear()
    return {"端点": COMFY, "名": 端点名, "是本机": 是本机()}


# ─────────────────────── 「交出去了，然后跟丢了」───────────────────────


class 提交未知(RuntimeError):
    """★ 钱可能已经花出去的现场。

    只有在**工作流已经提交、提示号已经拿到**之后才会抛它：
    请求出去了，对端可能正在跑、可能已经跑完、也可能压根没收到。
    所以它代表「说不清」，不是「失败」—— 上层不许拿它当失败去自动重跑。

    它自带账本要的那两个属性（账本.py 的 分类异常() 认属性、不认字）：
        .可能已计费   = True      ← 可能已经花过钱了
        .供应商任务号 = 提示号     ← 拿这个号去 ComfyUI 的 history 查最快

    一行接进账本：
        try:
            r = 引擎.派工(wf)
        except 引擎.提交未知 as e:
            账本.未知因为(任务id, e)          # ← 提示号/可能已计费 自动带进账

    仍继承 RuntimeError：老代码里 except RuntimeError 照样接得住，不会漏。
    """

    def __init__(self, 提示号: str = "", 已等秒: float = 0.0, 详情: str = ""):
        self.提示号 = str(提示号 or "")
        self.已等秒 = float(已等秒 or 0.0)
        self.可能已计费 = True
        self.供应商任务号 = self.提示号
        self.供应商 = "ComfyUI"
        self.详情 = str(详情 or "")
        行 = [f"等了 {self.已等秒:g} 秒还没跑完（提示号 {self.提示号[:8]}）"]
        if self.详情:
            行.append(f"  {self.详情}")
        行 += [
            "★ 这一条**别当「失败」**：工作流已经交给 ComfyUI 了（提示号都拿到了），",
            "  它可能正在跑、可能已经跑完 —— 结果和计费都说不清，按「未知」处理。",
            f"【去哪查】{COMFY}/history/{self.提示号}　和　{COMFY}/queue",
            "【查什么】这个提示号还在不在跑、history 里有没有它的 outputs",
            "【怎么办】跑出来了 → python 账本.py 对账 <id> --结果 成了 --产物 <路径>",
            "           真没跑成 → python 账本.py 对账 <id> --结果 没成",
        ]
        super().__init__("\n".join(行))

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
            "端点": COMFY,
            "端点名": 端点名,
            "本机": 是本机(),
            "版本": s.get("system", {}).get("comfyui_version", "?"),
            "显卡": d.get("name", "?"),
            "显存GB": round(d.get("vram_total", 0) / 1024**3, 1),
            "显存空闲GB": round(d.get("vram_free", 0) / 1024**3, 1),
        }
    except Exception as e:
        return {"在线": False, "端点": COMFY, "端点名": 端点名, "错": str(e)}


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
    """提交工作流，等它跑完，返回 {提示号, 图们:[{文件名,子目录,类型}], 耗时}。

    ★ 提交**之后**出岔子 → 一律抛 提交未知（提示号已经拿到手了，那属于「说不清」）；
      真失败（跑挂了 / 跑完了但没输出）→ 还是 RuntimeError（对端给了明确答复）。
      这条界线是钱的分界线：前者可能已经计费，后者确定没成。
    """
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
            raise 提交未知(号, time.time() - 起)
        try:
            史 = _请求(f"/history/{号}", 超时=20)
        except Exception as e:
            # 拿到提示号之后才断的 —— 这跟「服务没起」是两回事：
            # 活已经交出去了，钱可能已经花了，所以是「未知」不是「失败」。
            raise 提交未知(号, time.time() - 起, f"等结果的时候跟对端断了：{e}") from e
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
    参考图: list | None = None,
    参考模板: str = "qwen_edit",
    配置: dict | None = None,
) -> dict:
    """按模板出一张图。返回 {路, 种子, 耗时, 参考图}。

    zimage_turbo 是 8 步 Turbo，cfg 固定 1.0，不需要负面词（会自动零化）。

    参考图  给了就自动改走 `参考模板`（默认 qwen_edit）——那是 Qwen-Image-Edit
            的图，靠 image1/image2/image3 三个槽吃参考图，最多 3 张。
            ⚠ 这是飞彩那套「角色/场景/道具」一致性的底座：光把参考图算出来没用，
              必须真的喂进模型，否则脸和衣服每格都在变。
            路径必须是本机绝对路径；会自动传进 ComfyUI 的 input 目录。
    配置    直接覆盖模板里的节点字段，形如 {"40": {"steps": 30, "cfg": 4.5}}。
            用来在不新建模板的前提下微调采样参数。
    """
    报 = 报 or (lambda _: None)
    参考图 = [p for p in (参考图 or []) if p]

    if 参考图 and 模板 == "zimage_turbo":
        模板 = 参考模板
        if 步数 == 8:           # 8 是 Turbo 的默认值，换成 Edit 模板要跟着换
            步数 = 20
    if 模板 == 参考模板 and 参考图 and 步数 == 8:
        步数 = 20

    # ── 保险：编辑模板要的模型没下全，就别硬上 ──
    # 实测教训：拿纯文生图模型（qwen_image_2512）配 TextEncodeQwenImageEditPlus
    # 喂参考图，会出一张满屏棋盘格伪影的废图 —— 模型没训练过参考图隐变量。
    # 宁可退回文生图（脸会飘）也不能交废图。
    if 参考图:
        缺 = 模板缺什么(模板)
        if 缺:
            报(f"⚠ 参考图通道不可用 —— 模板 {模板} 缺模型：")
            for x in 缺:
                报(f"    · {x}")
            报("  退回纯文生图（这一镜的脸不锁，属于降级出图）")
            参考图 = []
            模板 = "zimage_turbo"
            步数 = 8

    种 = 种子 if 种子 is not None else random.randint(1, 2**31)

    wf = 读模板(模板)
    # 模板里允许带 "_规格" / "_说明" 这类注释键，值不是节点，提交前必须剔掉，
    # 不然 ComfyUI 会拿它当节点号校验，直接 400。
    wf = {号: 节 for 号, 节 in wf.items() if isinstance(节, dict) and "class_type" in 节}

    # 可缺节点（如加速 LoRA）的模型没下完，就摘掉它而不是整个模板失败
    for x in _摘可缺(wf, 模板):
        报(f"摘掉可缺节点：{x}")

    # ── 先把参考图挂进 LoadImage，并删掉用不到的槽 ──
    挂了几张 = 0
    if 参考图:
        槽们 = sorted(
            (号 for 号, 节 in wf.items() if 节.get("class_type") == "LoadImage"),
            key=lambda x: (len(str(x)), str(x)),
        )
        if len(参考图) > len(槽们):
            raise RuntimeError(
                f"模板 {模板} 只有 {len(槽们)} 个参考图槽，给了 {len(参考图)} 张。"
                f"飞彩的做法是「角色→场景→道具→风格」按序占槽，多的用拼图合成一张再喂。"
            )
        用了的槽 = 槽们[: len(参考图)]
        for 槽号, 图路 in zip(用了的槽, 参考图):
            if not os.path.isabs(图路):
                raise RuntimeError(f"参考图必须是本机绝对路径，收到：{图路}")
            if not os.path.exists(图路):
                raise RuntimeError(f"参考图不存在：{图路}")
            上传 = 上传图(图路)
            名 = 上传.get("name") or ""
            if 上传.get("subfolder"):
                名 = f"{上传['subfolder']}/{名}"
            wf[槽号]["inputs"]["image"] = 名
            挂了几张 += 1
            报(f"参考图{挂了几张}：{os.path.basename(图路)} → {名}")

        # 没用的槽：删节点 + 删上游引用
        没用的槽 = 槽们[len(参考图):]
        for 槽号 in 没用的槽:
            wf.pop(槽号, None)
        for 节 in wf.values():
            for 键 in list(节.get("inputs", {}).keys()):
                值 = 节["inputs"][键]
                if isinstance(值, list) and len(值) == 2 and str(值[0]) in {str(x) for x in 没用的槽}:
                    del 节["inputs"][键]

    wf0 = wf  # 保留原始引用，便于出错时排查
    改 = 0
    for 号, 节 in wf.items():
        类 = 节.get("class_type", "")
        ins = 节.setdefault("inputs", {})
        if 类 == "TextEncodeQwenImage21":
            # ★ Qwen-Image 2.1 专用节点：**一个节点同时吐正向(0)和负面(1)**，
            #   所以它不走下面那套「第一个是正向、第二个是负面」的轮转。
            #   实测教训：拿普通 CLIPTextEncode 接 2.1 的 int8_convrot 权重，
            #   出的是满屏彩色噪点废图（作品/_超分试验/对比_出图模型.png 右半）。
            ins["prompt"] = 提示词
            if 负面 and "negative_prompt" in ins:
                ins["negative_prompt"] = 负面
            elif "negative_prompt" in ins and not ins.get("negative_prompt"):
                ins["negative_prompt"] = 默认负面
            改 = 1
        elif 类 in ("CLIPTextEncode", "T5TextEncode", "TextEncodeQwenImageEdit",
                    "TextEncodeQwenImageEditPlus", "TextEncodeZImageOmni"):
            # 正向=第一个遇到的；其余（负面）走负面词或零化
            if 类.startswith("TextEncodeQwen") or 类 == "TextEncodeZImageOmni":
                # 这类节点的 prompt 就是提示词本体，参考图已经挂在 imageN 上
                ins["prompt"] = 提示词
                改 = 1
            elif 改 == 0:
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

    # ── 直接覆盖节点字段（留给调用方微调采样参数）──
    for 号, 覆盖 in (配置 or {}).items():
        号 = str(号)
        if 号 not in wf:
            报(f"警告：配置里的节点 {号} 不在模板 {模板} 里，跳过")
            continue
        wf[号].setdefault("inputs", {}).update(覆盖)

    报(f"提交：{提示词[:40]}…  种子 {种}" + (f"  参考图 {挂了几张} 张" if 挂了几张 else ""))
    果 = 派工(wf, 报=报)
    图 = 果["图们"][0]
    路 = 取图(图, 存到)
    报(f"出图：{os.path.basename(路)}")
    return {"路": 路, "种子": 种, "耗时": 果["耗时"], "原始": 图,
            "模板": 模板, "参考图": list(参考图), "挂了几张": 挂了几张}


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
    尾图: str | None = None,
    参考图: list | None = None,
    角色LoRA: str = "",
    LoRA强度: float = 1.0,
) -> dict:
    """拿一张图（或首帧+尾帧）+ 一句话，出一段视频。

    先把图上传进 ComfyUI，再按模板派工。

    角色LoRA  ★ 锁角色用。H3 模板里本来就挂着一个「加速 LoRA」（turbo 4/8 步），
              这个是在它**后面再接一个**，两个串着走：
                  UNETLoader → 加速 LoRA → 角色 LoRA → 引导器
              本机能用的：`h3-realism-people-t2v-i2v-r2v.safetensors`（真人质感，
              t2v/i2v/r2v 都能挂）、`h3_character_swap_pro4500_1000.safetensors`（换人）。
              ★ 实测：模板里原本那个 LoRA 的输出被谁吃，就把它接到谁身上 ——
                不能写死节点号，每个模板的编号都不一样。

    尾图  给了就**自动改走首尾帧模板**（默认 minimax_h3_flf2v）——两帧之间的中间过程
          由模型补。这是让相邻两格真正缝上的做法：这一格结束的那一帧就是下一格开始的那一帧，
          而不是各出各的再靠交叉溶解糊过去。
    """
    报 = 报 or (lambda _: None)
    种 = 种子 if 种子 is not None else random.randint(1, 2**31)
    if not os.path.exists(图路):
        raise RuntimeError(f"找不到图：{图路}")

    上 = 上传图(图路)
    报(f"上传 {os.path.basename(图路)} → {上['name']}")

    # ★ 给几张图 → 自动改走对应的模板（除非调用方自己点名了别的）
    #   给了参考图 → r2v（锁形象）；给了尾图 → flf2v（首尾帧）；都没有 → 单图 i2v
    尾上 = None
    参上 = []
    if 参考图:
        if 模板 in ("", "wan22_i2v", "minimax_h3_i2v", "minimax_h3_flf2v"):
            模板 = "minimax_h3_r2v"
        for i, q in enumerate([x for x in 参考图 if x][:3]):
            if not os.path.exists(q):
                raise RuntimeError(f"找不到参考图：{q}")
            u = 上传图(q)
            参上.append(u)
            报(f"上传参考图{i + 1} {os.path.basename(q)} → {u['name']}")
    elif 尾图:
        if not os.path.exists(尾图):
            raise RuntimeError(f"找不到尾图：{尾图}")
        if 模板 in ("", "wan22_i2v", "minimax_h3_i2v"):
            模板 = "minimax_h3_flf2v"
        尾上 = 上传图(尾图)
        报(f"上传尾帧 {os.path.basename(尾图)} → {尾上['name']}")

    wf = 读模板(模板)
    # 模板里允许有 "_说明" 这类注释键，值不是 dict，先剔掉
    wf = {号: 节 for 号, 节 in wf.items() if isinstance(节, dict) and "class_type" in 节}

    # ── ★ 角色 LoRA：接在模板里那个「加速 LoRA」**后面**，两个串着走 ──
    #    判据不是节点号，是「谁的输出被非 LoRA 的节点吃了」—— 那就是这条链的末端 LoRA。
    #    写死节点号会在换模板时悄悄挂错地方（挂错不报错，只是不生效，最难发现）。
    if 角色LoRA:
        若 = _挂角色LoRA(wf, 角色LoRA, LoRA强度)
        if 若:
            # ★ 挂之前先看一眼「配不配」：H3 的 LoRA 挂到 Wan 的主模型上不会报错，
            #   只会出一段垃圾（LoRA 的键名对不上就被静默忽略，或者更糟）。
            主模型 = " ".join(str(节.get("inputs", {}).get("unet_name", ""))
                            for 节 in wf.values()
                            if isinstance(节, dict) and 节.get("class_type") == "UNETLoader")
            小名 = 角色LoRA.lower()
            if "h3" in 小名 and "wan" in 主模型.lower():
                报(f"⚠ 角色 LoRA「{角色LoRA}」看着是给 MiniMax-H3 配的，"
                   f"而这个模板的主模型是 Wan（{主模型}）—— 多半不生效，甚至会出垃圾")
            报(f"挂上角色 LoRA：{角色LoRA}（强度 {LoRA强度}，接在 {若} 后面）")
        else:
            报(f"⚠ 这个模板里既没有 LoRA 节点、也没有 UNETLoader，角色 LoRA {角色LoRA} 没挂上")

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

    # ★ 模板声明自己吃几张图（_规格.图槽），引擎按节点号从小到大一张张填。
    #   没声明就按老规矩：第 1 槽 = 首帧，第 2 槽 = 尾帧。
    _槽名 = (wf.get("_规格") or {}).get("图槽") or ["首帧", "尾帧"]
    _图槽 = sorted((号 for 号, 节 in wf.items() if 节.get("class_type") == "LoadImage"),
                  key=lambda x: (len(str(x)), str(x)))
    _槽图 = {}
    if 参上:
        for i, u in enumerate(参上):
            if i < len(_图槽):
                _槽图[_图槽[i]] = u
    else:
        if _图槽:
            _槽图[_图槽[0]] = 上
        if 尾上 is not None and len(_图槽) >= 2:
            _槽图[_图槽[1]] = 尾上
    _尾槽 = None

    for 号, 节 in wf.items():
        类 = 节.get("class_type", "")
        ins = 节.setdefault("inputs", {})

        if 类 in ("CLIPTextEncode", "T5TextEncode"):
            if 号 == 正号:
                ins["text"] = 提示词
            elif 号 == 负号:
                ins["text"] = 负面 or "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"

        elif "prompt" in ins and 正号 is None:
            # ★ 有些模板（MiniMax-H3 的 r2v）**没有 CLIPTextEncode** ——
            #   提示词是直接挂在 MiniMaxH3ReferenceToVideo 的 prompt 输入上的。
            #   找不到正向词节点时，就把提示词写进带 prompt 槽的那个节点。
            ins["prompt"] = 提示词

        elif 类 == "LoadImage":
            # ★ 每个 LoadImage 槽按节点号顺序领一张图（_槽图 是上面算好的）。
            #   没领到图的槽留着不动 —— ComfyUI 会报「没给图」，那正是我们要的错。
            u = _槽图.get(号)
            if u is not None:
                ins["image"] = u["name"]

        elif 类 in ("KSampler", "KSamplerAdvanced", "RandomNoise"):
            # ★ RandomNoise 是 SamplerCustomAdvanced 那条链上的种子节点 ——
            #   MiniMax-H3 的官方骨架走的就是它，不在这里换，模板里的 __SEED__ 会原样送进
            #   ComfyUI，报 `invalid literal for int() with base 10: '__SEED__'`。
            if "seed" in ins:
                ins["seed"] = 种
            if "noise_seed" in ins:
                ins["noise_seed"] = 种

        elif 类 in ("WanImageToVideo", "Wan22ImageToVideoLatent", "WanFirstLastFrameToVideo",
                    "MiniMaxH3ImageToVideo"):
            # ★ MiniMax-H3 和 wan 的骨架不一样：它的提示词**不在 CLIPTextEncode 里**，
            #   而是这个节点自己的 `prompt` 字段；条件也从它这里吐出来（[0]=条件 [1]=隐变量）。
            #   所以提示词要在这儿塞，不能等下面那圈 CLIPTextEncode。
            if 类 == "MiniMaxH3ImageToVideo":
                if "prompt" in ins:
                    ins["prompt"] = 提示词
                正号 = 号          # 让下面「找不到正向节点」那道检查放行
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

    if 正号 is None and not any("prompt" in (节.get("inputs") or {}) for 节 in wf.values()):
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


def _挂角色LoRA(wf: dict, 名: str, 强度: float = 1.0) -> str:
    """在模板的模型链末端再接一个 LoRA，返回被接的那个节点号（没接成返回 ""）。

    ★ 为什么不能写死节点号：`wan22_i2v` / `minimax_h3_i2v` / `_flf2v` / `_r2v`
      四个模板的 LoRA 编号分别是 145 / 121 / …，而且以后照官方模板再抄一份又会变。
    ★ 怎么认出「末端 LoRA」：模型链是**线性**的（A→B→C），末端那个 LoRA 的输出
      会被一个**不是 LoRA** 的节点消费（引导器 / 采样器 / guider）。
      中间那个 LoRA 的输出只会被另一个 LoRA 消费。
    ★ 挂错不报错 —— 只是不生效。所以这里认不出来就明说，不要硬塞一个节点进去。
    """
    loras = {号: 节 for 号, 节 in wf.items()
             if 节.get("class_type") == "LoraLoaderModelOnly"}
    if not loras:
        # ★ 模板里一个 LoRA 都没有（`wan22_i2v` 就是这样）——
        #   那就直接接在**主模型**（UNETLoader）后面。别因为「没有现成的 LoRA 可接」
        #   就放弃：那等于告诉他「这个模板不支持角色 LoRA」，而其实是支持的。
        主 = [号 for 号, 节 in wf.items()
              if 节.get("class_type") in ("UNETLoader", "CheckpointLoaderSimple")]
        if not 主:
            return ""
        源0 = sorted(主, key=lambda x: (len(str(x)), str(x)))[0]
    else:
        源0 = None

    if 源0 is None:
        # 谁吃了谁：把「模型口」的引用记下来
        被吃 = set()
        for 号, 节 in wf.items():
            for k, v in (节.get("inputs") or {}).items():
                if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                    if v[0] in loras and v[0] != 号:
                        被吃.add(v[0])

        末端 = [号 for 号 in loras if 号 not in 被吃]
        if not 末端:
            # 环形（理论上不会有）—— 退而求其次，取号最大的那个
            末端 = [sorted(loras, key=lambda x: (len(str(x)), str(x)))[-1]]
        源 = 末端[0]
    else:
        源 = 源0

    # 新节点号：不跟现有号撞
    新号 = "角色LoRA"
    while 新号 in wf:
        新号 += "_"

    wf[新号] = {"class_type": "LoraLoaderModelOnly",
                "inputs": {"model": [源, 0], "lora_name": 名,
                           "strength_model": float(强度)}}

    # 把所有「原来吃 源 的地方」改成吃新节点
    改了几处 = 0
    for 号, 节 in wf.items():
        if 号 == 新号:
            continue
        for k, v in (节.get("inputs") or {}).items():
            if isinstance(v, list) and len(v) == 2 and v[0] == 源:
                # 只改「模型口」——同一节点也可能吐别的东西，但 LoRA 只吐 MODEL
                节["inputs"][k] = [新号, v[1]]
                改了几处 += 1
    if 改了几处 == 0:
        wf.pop(新号, None)
        return ""
    return 源


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


_模型缓存 = {"时间": 0.0, "表": None}


def _摘可缺(wf: dict, 模板: str) -> list:
    """把「模型不在本机」的可缺节点从图里拆掉，并把它下游重新接回它上游。

    典型场景：模板里挂了 Lightning 加速 LoRA，但 LoRA 还没下完。
    这时候不该整个模板跑不了 —— 摘掉 LoRA 照样能出图，只是慢。
    """
    try:
        规格 = (读模板(模板).get("_规格") or {})
    except Exception:
        return []
    可缺 = set(规格.get("可缺") or [])
    if not 可缺:
        return []

    摘了 = []
    for 号 in list(wf.keys()):
        节 = wf[号]
        if 节.get("class_type") not in 可缺:
            continue
        字段 = _节点字段.get(节["class_type"])
        if not 字段:
            continue
        名 = (节.get("inputs") or {}).get(字段)
        if 名 and 有模型(名):
            continue  # 模型在，留着

        # 找它自己的上游：inputs 里除模型名外，那个 [节点号, 槽位] 形状的值
        上游 = None
        for k, v in (节.get("inputs") or {}).items():
            if k != 字段 and isinstance(v, list) and len(v) == 2:
                上游 = v
                break
        if 上游 is None:
            continue

        # 把所有指向它的线，改指到它的上游
        接线 = 0
        for 别节 in wf.values():
            for k, v in list((别节.get("inputs") or {}).items()):
                if isinstance(v, list) and len(v) == 2 and str(v[0]) == str(号):
                    别节["inputs"][k] = 上游
                    接线 += 1
        del wf[号]
        摘了.append(f"{节['class_type']}（{名}）→ 重新接了 {接线} 条线")
    return 摘了


_模型根 = [
    r"D:\Comfy-Desktop\ComfyUI-Shared\models",
    r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models",
]
_模型子目录 = (
    "diffusion_models", "unet", "checkpoints", "loras", "lora", "vae",
    "text_encoders", "clip", "clip_vision", "model_patches", "upscale_models",
)
_完好缓存 = {}


def _找模型文件(名: str) -> str:
    """在两个模型根 + 常见子目录里找这个文件。找不到返回空串。"""
    基 = os.path.basename(str(名).replace("\\", "/"))
    for 根 in _模型根:
        if not os.path.isdir(根):
            continue
        直 = os.path.join(根, str(名).replace("/", os.sep))
        if os.path.isfile(直):
            return 直
        for 子 in _模型子目录:
            候 = os.path.join(根, 子, 基)
            if os.path.isfile(候):
                return 候
    return ""


def 模型完好(名: str) -> tuple:
    """这文件在不在、**全不全**。返回 (好坏, 说明)。

    为什么不能只看「在不在」：实测踩过 —— 一个 19 GB 的模型下到 1.97%，
    就带着正确的最终文件名躺在模型目录里，ComfyUI 照列不误，
    到出图才炸，而且炸出来的是一张满屏伪影的废图（看起来像模型不对，
    其实像下了一半）。safetensors 是自描述的（8 字节头长 + JSON 张量表
    + 数据段），所以能 O(1) 算出它「本该多大」，差一个字节都抓得出来。

    找不到文件时返回 True —— 本机模型可能放在我没枚举到的第三个根，
    这种时候信 ComfyUI（它自己列得出来就说明它加载得了）。
    只有「找到了、并且能证明它残缺」才判死。
    """
    if not 是本机():
        # 端点在别的机器上，本机磁盘上的文件跟对面没关系 —— 别假装查过了。
        return (True, f"端点在 {COMFY}，跳过本机文件校验（信对面 ComfyUI）")
    if 名 in _完好缓存:
        return _完好缓存[名]
    路 = _找模型文件(名)
    if not 路:
        果 = (True, "本机找不到文件，信 ComfyUI")
        _完好缓存[名] = 果
        return 果
    大 = os.path.getsize(路)
    if not 路.lower().endswith(".safetensors"):
        果 = (大 > 1048576, f"{大 / 1048576:.1f} MB（非 safetensors，只看体积）")
        _完好缓存[名] = 果
        return 果
    try:
        with open(路, "rb") as f:
            头 = f.read(8)
            if len(头) < 8:
                raise ValueError("连 8 字节头都读不到")
            长 = int.from_bytes(头, "little")
            if 长 <= 0 or 长 > 64 * 1048576:
                raise ValueError(f"头长 {长} 不合理")
            表 = json.loads(f.read(长).decode("utf-8", "replace"))
        应 = 8 + 长
        for k, v in 表.items():
            if k == "__metadata__" or not isinstance(v, dict):
                continue
            偏 = v.get("data_offsets") or [0, 0]
            应 = max(应, 8 + 长 + int(偏[1]))
    except Exception as e:
        果 = (False, f"张量表读不出来（{e}）—— 多半是下了一半")
        _完好缓存[名] = 果
        return 果
    if 大 == 应:
        果 = (True, f"{大 / 1073741824:.2f} GB 完整")
    else:
        果 = (False,
              f"**不完整**：实际 {大 / 1073741824:.2f} GB，头部算出来该有 "
              f"{应 / 1073741824:.2f} GB（只有 {大 / 应 * 100:.1f}%）")
    _完好缓存[名] = 果
    return 果


def 有模型(名: str) -> bool:
    """ComfyUI 认不认这个名字的模型。

    为什么要问 ComfyUI 而不是看文件在不在：ComfyUI 只列它自己能加载的，
    文件在但没被认到（路径不对 / 名字拼错 / 没重启）照样会失败。

    结果缓存 60 秒 —— 一次出图会问好几遍，别每遍都打 ComfyUI。
    """
    import time as _t

    if _t.time() - _模型缓存["时间"] > 60 or _模型缓存["表"] is None:
        try:
            info = _请求("/object_info", 超时=120)
        except Exception:
            return False  # 问不到就说没有，宁可退回文生图也别交一张废图
        表 = set()
        对 = {
            "unet": ("UNETLoader", "unet_name"),
            "ckpt": ("CheckpointLoaderSimple", "ckpt_name"),
            "clip": ("CLIPLoader", "clip_name"),
            "vae": ("VAELoader", "vae_name"),
            "lora": ("LoraLoader", "lora_name"),
        }
        for 节点, 字段 in 对.values():
            try:
                枚 = info[节点]["input"]["required"][字段][0]
            except Exception:
                continue
            表.update(枚)
        _模型缓存["表"] = 表
        _模型缓存["时间"] = _t.time()

    if not _模型缓存["表"]:
        return False
    # 允许只写文件名不带子目录
    基 = os.path.basename(str(名).replace("\\", "/"))
    认 = 名 in _模型缓存["表"] or any(
        os.path.basename(x) == 基 for x in _模型缓存["表"])
    if not 认:
        return False
    # ComfyUI 只认名字、不认完整性 —— 残缺文件它照样列出来。
    # 所以这里再拿 safetensors 的头部自校验一遍。
    好, _ = 模型完好(名)
    return 好


_节点字段 = {
    "UNETLoader": "unet_name",
    "CheckpointLoaderSimple": "ckpt_name",
    "CLIPLoader": "clip_name",
    "VAELoader": "vae_name",
    "LoraLoader": "lora_name",
    "LoraLoaderModelOnly": "lora_name",
}


def 模板缺什么(模板: str, 含软: bool = False) -> list:
    """这个模板跑不起来，是因为缺什么。空列表 = 能跑。

    查两件事：
      1. 模型文件在不在（问 ComfyUI，不是问文件系统）
      2. 模型**对不对**（模板 `_规格.要求` 里写死的名字约束）

    第 2 条是血换来的：qwen_edit 模板的 UNETLoader 一度指向 qwen_image_2512
    （纯文生图）。文件在、ComfyUI 也认，但拿去配 TextEncodeQwenImageEditPlus
    会出一张满屏棋盘格伪影的废图 —— 只查「在不在」根本拦不住。

    `含软=True` 时把可选的（`_规格.可缺`，比如加速 LoRA）也列出来，前缀「(可选)」。
    """
    try:
        wf = 读模板(模板)
    except Exception as e:
        return [f"读不到模板：{e}"]

    规格 = wf.get("_规格") or {}
    可缺 = set(规格.get("可缺") or [])

    缺 = []
    看过 = set()
    for 号, 节 in wf.items():
        if not isinstance(节, dict):
            continue
        类 = 节.get("class_type", "")
        字段 = _节点字段.get(类)
        if not 字段:
            continue
        名 = (节.get("inputs") or {}).get(字段)
        if not 名 or 名 in 看过:
            continue
        看过.add(名)
        if not 有模型(名):
            软 = 类 in 可缺
            if 软 and not 含软:
                continue
            缺.append(f"{'(可选) ' if 软 else ''}{类} 要 {名} —— 本机没有")

    # ── 语义要求：名字必须含某些词 ──
    for 条 in 规格.get("要求") or []:
        类 = 条.get("节点")
        字段 = _节点字段.get(类 or "")
        if not 字段:
            continue
        名 = None
        for 节 in wf.values():
            if isinstance(节, dict) and 节.get("class_type") == 类:
                名 = (节.get("inputs") or {}).get(字段)
                break
        if not 名:
            continue
        须含 = 条.get("名字须含") or []
        低 = 名.lower()
        if 须含 and not any(x.lower() in 低 for x in 须含):
            缺.append(
                f"{类} 装的是 {名}，但本模板要求名字含 "
                f"{'/'.join(须含)} —— {条.get('为什么', '模型类型不对')}"
            )
    return 缺


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
