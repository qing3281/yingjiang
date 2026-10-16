# -*- coding: utf-8 -*-
"""双线保证 —— 让远端【只出算力】，出什么样【本机说了算】。

用户的要求（原话）：
    「让那边只是提供一个视频生成的算力，但决定各种效果的、生成视频是什么样的，
      还得由这边来」（m13440）

这句话落到代码上就是三条【可以当场证伪】的检查，而不是一句承诺：

    L1 模型一致   同一份模板要的那几个模型文件，两台机器【字节数逐个相等】。
                  不等 = 同样的种子会出不同的画面，直接拒绝，不派工。
    L2 工作流一致 本机拼好图 → 提交 → 从对端 /history 把【它实际执行的那张图】读回来，
                  规范化后算哈希，和本机发出去的比。相同 = 对端一个字段都没改。
                  ★ 这条最硬：它证明的是「对端执行的正是本机写的那张图」，
                    而不是「本机以为自己发了什么」。
    L3 成片一致   出来的文件尺寸/帧数/帧率 = 本机要求的。对端不能偷偷改画幅。

跑法：
    python 双线.py 查               # 查 L1：把当前所有模板要的模型两边比一遍
    python 双线.py 查 wan22_i2v     # 只查一个模板
    python 双线.py 快照             # 重新抓远端模型清单（慢，走 ssh）
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 引擎  # noqa: E402

这里 = os.path.dirname(os.path.abspath(__file__))
远端快照 = os.path.join(这里, "_远端模型.json")
远端登录 = os.environ.get("影匠_远端SSH", "776bjta")
远端模型根 = os.environ.get("影匠_远端模型根", r"E:\影匠AI\ComfyUI-Shared\models")
远端系统py = os.environ.get(
    "影匠_远端系统py",
    r"C:\Users\Seele\AppData\Local\Programs\Python\Python312\python.exe",
)

# 本机模型根（和 ComfyUI 的 extra_model_paths.yaml 对得上）
本机模型根 = os.environ.get("影匠_本机模型根", r"D:\Comfy-Desktop\ComfyUI-Shared\models")

# 模板里哪些字段是「模型文件名」，各自属于哪个子目录
字段子目录 = {
    "unet_name": "diffusion_models",
    "ckpt_name": "checkpoints",
    "vae_name": "vae",
    "clip_name": "text_encoders",
    "clip_name1": "text_encoders",
    "clip_name2": "text_encoders",
    "clip_name3": "text_encoders",
    "lora_name": "loras",
    "model_name": "upscale_models",
    "clip_vision_name": "clip_vision",
    "audio_vae_name": "vae",
}


# ───────────────────── L1：模型一致 ─────────────────────


def 本机清单() -> dict:
    """扫本机模型根，返回 {'子目录/文件名': 字节数}。"""
    表 = {}
    for 子 in set(字段子目录.values()):
        d = os.path.join(本机模型根, 子)
        if not os.path.isdir(d):
            continue
        for 名 in os.listdir(d):
            p = os.path.join(d, 名)
            if os.path.isfile(p):
                表[f"{子}/{名}"] = os.path.getsize(p)
    return 表


def 抓远端清单(报=print) -> dict:
    """走 ssh 让远端把自己的模型列成 JSON，再 scp 回来。全程不经过 cmd 的代码页。

    为什么不用 `ssh ... dir`：cmd 的输出按 OEM 代码页编码，中文路径过来是乱码，
    没法解析。让远端用 Python 写 UTF-8 的 JSON 文件再传回来，才可靠。
    """
    本地脚本 = os.path.join(这里, "_远端_yjai_ls.py")
    if not os.path.exists(本地脚本):
        raise RuntimeError(f"缺远端清点脚本：{本地脚本}")
    报("  传清点脚本…")
    subprocess.run(["scp", "-o", "ConnectTimeout=10", 本地脚本, f"{远端登录}:C:/yjai_ls.py"],
                   check=True, capture_output=True)
    报("  远端执行…")
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", 远端登录, f"{远端系统py} C:\\yjai_ls.py"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"远端清点失败：{r.stderr[:400]}")
    报("  " + (r.stdout or "").strip())
    subprocess.run(["scp", "-o", "ConnectTimeout=10", f"{远端登录}:C:/yjai_models.json", 远端快照],
                   check=True, capture_output=True)
    with open(远端快照, "r", encoding="utf-8") as f:
        return json.load(f)


def 读远端快照(要新的=False) -> dict:
    if 要新的 or not os.path.exists(远端快照):
        return 抓远端清单()
    with open(远端快照, "r", encoding="utf-8") as f:
        return json.load(f)


def 模板要的模型(模板名: str) -> list[tuple[str, str]]:
    """从模板 JSON 里挑出所有模型引用，返回 [(子目录/文件名, 出处节点)]。"""
    wf = 引擎.读模板(模板名)
    要 = []
    for 号, 节 in wf.items():
        if not isinstance(节, dict):
            continue
        for 键, 值 in (节.get("inputs") or {}).items():
            if 键 in 字段子目录 and isinstance(值, str) and 值:
                要.append((f"{字段子目录[键]}/{值}", f"节点{号}({节.get('class_type','?')})"))
    return 要


def 比模型(模板们: list[str] | None = None, 报=print) -> dict:
    """L1 检查。返回 {通过, 行:[...], 缺, 不一致}。"""
    模板们 = 模板们 or [t for t in 引擎.列模板() if not t.startswith("_")]
    本 = 本机清单()
    远 = 读远端快照()["模型"]
    远环 = 读远端快照().get("环境", {})

    行, 缺, 不一致, 全过 = [], [], [], True
    报(f"本机模型根 {本机模型根}")
    报(f"远端模型根 {远端模型根}   （远端 {len(远)} 个模型）")
    报(f"远端环境 {远环.get('机器','?')} / Python {远环.get('python','?')}")
    报("")

    见过 = set()
    for t in 模板们:
        try:
            要 = 模板要的模型(t)
        except Exception as e:
            报(f"  [{t}] 读不了：{e}")
            continue
        if not 要:
            continue
        报(f"  [{t}]")
        for 键, 出处 in 要:
            if (t, 键) in 见过:
                continue
            见过.add((t, 键))
            a, b = 本.get(键), 远.get(键)
            if a is None:
                状态, 全过 = "✗ 本机没有", False
                缺.append((t, 键, 出处))
            elif b is None:
                状态, 全过 = "✗ 远端没有", False
                缺.append((t, 键, 出处))
            elif a != b:
                状态, 全过 = f"✗ 字节数不同 本机{a:,} vs 远端{b:,}", False
                不一致.append((t, 键, a, b))
            else:
                状态 = f"✓ {a:,} B"
            行.append((t, 键, 出处, 状态))
            报(f"     {状态:<38} {键}")

    报("")
    if 全过:
        报("★ L1 通过 —— 这些模型两边字节数逐个相等，同种子同参数必然出同一结果。")
    else:
        报(f"★ L1 没过 —— 缺 {len(缺)} 项 / 不一致 {len(不一致)} 项，别派工到远端。")
    return {"通过": 全过, "行": 行, "缺": 缺, "不一致": 不一致}


# ───────────────────── L2：工作流一致 ─────────────────────


def _归一值(v):
    """把值折算成「同一个意思的同一个写法」。

    ★ 这一层是必需的，不是洁癖：ComfyUI 收到图之后会按节点自己的输入声明
    **做一次类型折算**，于是本机发 `"fps": 16`（int），/history 里存回来是
    `"fps": 16.0`（float）。逐字符比就永远差这一处，L2 永远红 —— 而它红的
    理由跟「对端改了我的图」毫无关系。**判据太严会跟判据太松一样没用**：
    太松放过真改动，太严天天误报，人就学会无视它。

    归一的是【承载意图的写法】，不是意图本身：数值统一成 float 的规范写法、
    字符串去首尾空白。名字、连接、参数值一律不动。
    """
    if isinstance(v, bool):
        return v                      # bool 是 int 的子类，必须先拦
    if isinstance(v, (int, float)):
        f = float(v)
        return int(f) if f.is_integer() else f
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        return [_归一值(x) for x in v]
    if isinstance(v, dict):
        return {k: _归一值(x) for k, x in v.items()}
    return v


def 规范化(图: dict) -> str:
    """把一张 ComfyUI 工作流图规范化成可比对的字符串。

    规则：只留 class_type / inputs；键排序；数值按 _归一值 折算
    （ComfyUI 的 /history 会按节点声明折算类型，也会补默认值、去掉 _meta，
      所以两边都用同一套规则过一遍，差异才是【真的差异】）。
    """
    出 = {}
    for 号, 节 in (图 or {}).items():
        if not isinstance(节, dict):
            continue
        if "class_type" not in 节:
            continue   # _说明 / _规格 这类注释键，提交前本来就剔掉了
        条 = {"class_type": 节.get("class_type"), "inputs": _归一值(节.get("inputs") or {})}
        出[str(号)] = 条
    return json.dumps(出, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def 图指纹(图: dict) -> str:
    return hashlib.sha256(规范化(图).encode("utf-8")).hexdigest()[:16]


def 取回执(提示号: str) -> dict | None:
    """从对端 /history 读回【它实际执行的那张图】。

    ComfyUI 的 /history/<号> 里，条["prompt"] 有时是裸图，
    有时是 [号, 图, 额外信息, 客户端号] 的四元组。两种都认。
    """
    if not 提示号:
        return None
    try:
        史 = 引擎._请求(f"/history/{提示号}", 超时=20)
    except Exception:
        史 = None
    条 = (史 or {}).get(提示号)
    if not 条:
        # /history/<号> 只认完整 UUID！给半截（前 8 位）它会当成没这条。
        # 所以取不到时退回列表接口，按前缀找一条 —— 这个坑踩过一次：
        # 拿 "2a1b4784" 去查，静默返回 None，看起来像"历史滚掉了"。
        try:
            全 = 引擎._请求("/history?max_items=50", 超时=20) or {}
        except Exception:
            return None
        中 = [k for k in 全 if k == 提示号 or k.startswith(提示号)]
        if not 中:
            return None
        提示号 = sorted(中)[-1] if len(中) > 1 else 中[0]
        条 = 全.get(提示号)
        if not 条:
            return None
    图 = 条.get("prompt")
    if isinstance(图, list):
        for x in 图:
            if isinstance(x, dict) and any(
                isinstance(v, dict) and "class_type" in v for v in x.values()
            ):
                return x
        return None
    return 图 if isinstance(图, dict) else None


def 验回执(提示号: str, 我方图: dict, 报=print) -> dict:
    """L2 检查：对端执行的图 == 本机发的图？"""
    回 = 取回执(提示号)
    if 回 is None:
        报("  ⚠ 从对端取不回执（历史可能已经滚掉了）—— L2 这次没验成，不能说通过")
        return {"通过": None, "原因": "取不回执"}
    # /history 的 prompt 有时是 [号, 图, 额外] 的三元组
    if isinstance(回, list) and len(回) >= 2 and isinstance(回[1], dict):
        回 = 回[1]
    a, b = 图指纹(我方图), 图指纹(回)
    同 = a == b
    报(f"  本机发出指纹 {a}")
    报(f"  对端执行指纹 {b}")
    if 同:
        报("  ✓ L2 通过 —— 对端跑的正是本机写的这张图，一个字段没改。")
    else:
        报("  ✗ L2 没过 —— 对端执行的图跟本机发的不一样！")
        报(_图差异(我方图, 回))
    return {"通过": 同, "我方": a, "对端": b}


def _图差异(a: dict, b: dict) -> str:
    """把两张图的字段级差异打出来，便于定位。"""
    出 = []
    for 号 in sorted(set(map(str, a)) | set(map(str, b)), key=lambda x: (len(x), x)):
        x, y = a.get(号), b.get(号)
        if x is None:
            出.append(f"    只在对端有：节点 {号} {y.get('class_type')}")
            continue
        if y is None:
            出.append(f"    只在本机有：节点 {号} {x.get('class_type')}")
            continue
        if x.get("class_type") != y.get("class_type"):
            出.append(f"    节点 {号} 类型不同：{x.get('class_type')} vs {y.get('class_type')}")
            continue
        xi, yi = x.get("inputs") or {}, y.get("inputs") or {}
        for k in sorted(set(xi) | set(yi)):
            if xi.get(k) != yi.get(k):
                出.append(f"    节点 {号}({x.get('class_type')}).{k}: {xi.get(k)!r} vs {yi.get(k)!r}")
    return "\n".join(出) if 出 else "    （没看出字段差异，可能是键序/默认值补全导致，需人工看）"


# ───────────────────── L3：成片一致 ─────────────────────


def 验片(路: str, 宽: int = 0, 高: int = 0, 帧数: int = 0, 帧率: int = 0, 报=print) -> dict:
    """L3 检查：出来的文件的画幅/帧数/帧率是不是本机要求的。

    这台机器上没有独立的 ffprobe，用的是项目自带的 `_bin\\ffmpeg.exe -i`（把它的
    版本信息从 stderr 里读出来）—— 和 _出成片.py / _双线成片.py 用的是同一个。
    """
    if not os.path.exists(路):
        报(f"  ✗ 文件不存在：{路}")
        return {"通过": False}
    ff = os.path.join(这里, "_bin", "ffmpeg.exe")
    if not os.path.exists(ff):
        报(f"  ⚠ 找不到 {ff}，跳过 L3")
        return {"通过": None}
    r = subprocess.run([ff, "-i", 路], capture_output=True, text=True, errors="replace")
    文 = (r.stderr or "") + (r.stdout or "")

    import re

    # 不能用 `[^,]+,\s*[^,]+,\s*WxH` —— 像素格式那一格里【自己带逗号】：
    #   Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709/bt709/iec61966-2-1, progressive), 832x480
    #                                        ↑ 这里  ↑ 和这里           ↑ 还有这里
    # 匹配"逗号分隔的第 N 段"必然漏。改成：Video: 之后、第一个独立的 WxH。
    m = re.search(r"Video:\s.*?,\s*(\d{2,5})x(\d{2,5})(?=[\s,\[])", 文)
    W, H = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    m2 = re.search(r"(\d+(?:\.\d+)?)\s*fps", 文)
    fps = float(m2.group(1)) if m2 else 0.0
    m3 = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", 文)
    秒 = (int(m3.group(1)) * 3600 + int(m3.group(2)) * 60 + float(m3.group(3))) if m3 else 0.0
    帧 = round(秒 * fps) if (秒 and fps) else 0

    好 = True
    if 宽 and W != 宽:
        报(f"  ✗ 宽不对：要 {宽}，实际 {W}")
        好 = False
    if 高 and H != 高:
        报(f"  ✗ 高不对：要 {高}，实际 {H}")
        好 = False
    if 帧率 and abs(fps - 帧率) > 0.01:
        报(f"  ⚠ 帧率：要 {帧率}，实际 {fps}")
    if 帧数 and 帧 and 帧 != 帧数:
        报(f"  ⚠ 帧数：要 {帧数}，实际约 {帧}")
    if 好:
        报(f"  ✓ L3 通过 —— {W}×{H}  {fps}fps  {秒:.2f} 秒（约 {帧} 帧）  {os.path.getsize(路):,} B")
    return {"通过": 好, "宽": W, "高": H, "帧率": fps, "秒": 秒, "帧数": 帧}


# ───────────────────── 命令行 ─────────────────────


def main():
    甲 = sys.argv[1:] or ["查"]
    令 = 甲[0]

    if 令 == "快照":
        d = 抓远端清单()
        print(f"远端 {len(d['模型'])} 个模型 -> {远端快照}")
        return 0

    if 令 == "查":
        模板们 = 甲[1:] or None
        r = 比模型(模板们)
        return 0 if r["通过"] else 2

    if 令 == "本机":
        表 = 本机清单()
        print(f"本机 {len(表)} 个模型：")
        for k, v in sorted(表.items()):
            print(f"  {k:<58} {v:,} B")
        return 0

    if 令 == "远端":
        d = 读远端快照()
        print(f"远端 {len(d['模型'])} 个模型（快照）：")
        for k, v in sorted(d["模型"].items()):
            print(f"  {k:<58} {v:,} B")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
