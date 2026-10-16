# -*- coding: utf-8 -*-
"""MiniMax H3 fl2va 批量动态 —— 首帧图 + 台词 → 5 秒带对白视频。

## 为什么用这个

《今天别开门》走的是 Wan 2.2 14B 双模型串联，一条 5 秒要 4 分钟，**而且没有声音**，
得再跑一遍 IndexTTS 配音、再对齐口型。

MiniMax H3 的 fl2va（first-last to video+audio）**一次出画面 + 对白音频**：
- 5.17 秒（124 帧 @24fps）实测 **141~151 秒**
- 首帧钉得住（输出首帧 vs 输入图逐像素平均差 3.7~4.2 / 255）
- 中文台词经 Whisper 验证完全可懂，口型同步
- 显存峰值 15.4 / 16.3 GB，内存 32.8 / 46.8 GB

## 坑（都踩过）

1. **长度**：5.17 秒是甜点。15 秒（362 帧）实测跑了 30 分钟还没完 4 步（≥450 秒/步，19× 慢），
   token 只涨 2.8 倍但时间爆炸 —— **不要超过 5 秒**，长镜头靠多条拼。
2. **必须先 free 显存**：不 free 的话第一次要 46~151 秒才起跑。
3. **后台任务被中断可能连带弄死 ComfyUI**。所以这里每镜之间查一次 `/system_stats`。
4. 工作流里是 `MiniMaxH3ImageToVideo`（不是 `MiniMaxImageToVideoNode`）。
5. 提示词用**英文描述动作**，台词用**中文引号**原样写进去。

## 用法

```python
from MiniMax动态 import 出动态
r = 出动态(首帧路, 动作词, "今天也别开门。", 出来路, 帧=124, 种子=12345)
```
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

地址 = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
工作流 = r"D:\DSHworkspace\素材\本地AI\workflows\MiniMaxH3_api.json"
Comfy输出 = r"D:\Comfy-Desktop\ComfyUI-Shared\output"

帧每镜 = 124          # 124 帧 @24fps = 5.17 秒 —— 实测的甜点
步数 = 4


# ────────────────────────────── 小工具 ──────────────────────────────

def 显存() -> tuple[int, int]:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=15)
        a, b = r.stdout.strip().split(",")
        return int(a), int(b)
    except Exception:
        return 0, 0


def 内存GB() -> float:
    import ctypes

    class M(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    m = M(); m.dwLength = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return (m.ullTotalPhys - m.ullAvailPhys) / 2**30


def 活着(超时=5) -> bool:
    try:
        urllib.request.urlopen(地址 + "/system_stats", timeout=超时).read()
        return True
    except Exception:
        return False


def 腾地方() -> None:
    """不 free 的话第一次起跑能拖到 150 秒。"""
    try:
        req = urllib.request.Request(
            地址 + "/api/free",
            json.dumps({"unload_models": True, "free_memory": True}).encode(),
            {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=90).read()
        time.sleep(3)
    except Exception as e:
        print(f"    （free 没成功：{e}）")


def 上传图(本地路径: str) -> tuple[str, str]:
    远端名 = f"dsh_{uuid.uuid4().hex[:10]}{os.path.splitext(本地路径)[1].lower() or '.png'}"
    边界 = "----dsh" + uuid.uuid4().hex
    with open(本地路径, "rb") as f:
        数据 = f.read()
    body = b""
    body += f"--{边界}\r\n".encode()
    body += f'Content-Disposition: form-data; name="image"; filename="{远端名}"\r\n'.encode()
    body += b"Content-Type: image/png\r\n\r\n" + 数据 + b"\r\n"
    body += f"--{边界}\r\n".encode()
    body += b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
    body += f"--{边界}--\r\n".encode()
    req = urllib.request.Request(地址 + "/api/upload/image", body,
                                 {"Content-Type": f"multipart/form-data; boundary={边界}"})
    d = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return d.get("name", 远端名), d.get("subfolder", "")


# ────────────────────────────── 主体 ──────────────────────────────

def 出动态(首帧路: str, 动作: str, 台词: str, 出来路: str,
           帧: int = 帧每镜, 种子: int = 12345, 超时秒: int = 3600,
           主体: str = "", 场景锚: str = "", 放行中文: bool = False) -> str | None:
    """跑一条。成功返回 出来路，失败返回 None。

    放行中文=True 时跳过「引号外不许有中文」的硬闸 —— 给《龙族》那种
    整篇中文导演脚本文案用（Work-Fisher 写法）。默认 False，因为中文正文
    会被 H3 当朗读内容念出来，只有确知整篇是给模型看的说明文字时才开。
    """
    if not os.path.isfile(首帧路):
        print(f"    ❌ 首帧不存在：{首帧路}")
        return None
    if os.path.isfile(出来路) and os.path.getsize(出来路) > 10240:
        print(f"    ↷ 已有，跳过")
        return 出来路

    if not 活着():
        print("    ❌ ComfyUI 没响应")
        return None

    腾地方()
    远端, 子目录 = 上传图(首帧路)

    # 提示词：英文写动作 + 中文原样写台词（模型靠这个对口型）
    #
    # ★★ 坑（第二次踩，代价是 30 条重跑）：**提示词总长也要短**。
    #    第一版这里堆了六句英文（"Animate the given first frame exactly." /
    #    "Absolutely do not introduce any new character..." / "The ONLY spoken
    #    audio in the entire clip is..."），遇到台词本来就短的镜头
    #    （镜 04 只有「……涨。」一个字），模型没话可说就拿这些英文去填时间，
    #    Whisper 转写出来是「喂 還是出 只是小姨是個警司長」这种毫不相干的音。
    #    现在压到「动作 + 表情 + 有谁 + 台词 + 一句音频要求」。
    段 = []
    # ★★★ 整篇模式（《龙族》起用）：
    #   当 动作 本身已经是一份完整的 H3 结构化提示词（含
    #   integrated_multimodal_description / overall_soundscape /
    #   non_diegetic_music 三字段），就【原样发出】，一个字都不许再拼。
    #   踩过的坑：以前这里无条件补「主体为空 → 街上完全没人」和
    #   「没台词 → 没有对白」，结果把奥丁、楚子航、所有角色从画面里删掉了。
    整篇 = ("integrated_multimodal_description" in 动作
            and "overall_soundscape" in 动作)
    if 整篇:
        提示词 = 动作.strip()
    else:
        if 动作:
            段.append(f"{动作.strip()}.")
        # ★★ 场景锚（《光明顶》第三次踩坑的修法）：运镜写得越猛，模型对场景的
        #    锚定越弱，甩镜一狠它就退回训练先验——雪原广场会变成中式街市或竹林。
        #    这一句把「场景不许变」明确写成否定清单，比正面描述有效得多。
        if 场景锚:
            段.append(f"The location never changes and stays exactly the same in "
                      f"every frame: {场景锚.strip()}")
        if 主体:
            段.append(f"On screen: {主体.strip()}.")
        elif not 台词:
            # 只有在「既没主体、也没台词」时才敢说画面里没人。
            # 有台词就说明画面上一定有人——这是《龙族》镜 10/11/14 踩出来的。
            段.append("The street is completely empty, no people at all.")
        if 台词:
            段.append(f'She speaks Chinese: "{台词}"')
            段.append("No other dialogue, no narration, no voice-over, no music.")
        elif 主体:
            段.append("No dialogue, no narration, no music, ambient sound only.")
        提示词 = " ".join(段)

    # 硬闸：引号外出现任何中文，直接拦下来，别浪费 2 分钟的 GPU
    引号外 = re.sub(r'"[^"]*"', "", 提示词)
    漏 = re.findall(r"[\u4e00-\u9fff]+", 引号外)
    if 漏 and not 放行中文:
        print(f"    ⛔ 提示词引号外还有中文 {'、'.join(sorted(set(漏))[:8])}"
              f" —— 会被模型念出来，先改干净再跑")
        return None

    g = json.load(open(工作流, encoding="utf-8"))["prompt"]
    g["1"]["inputs"]["image"] = f"{子目录}/{远端}" if 子目录 else 远端

    节点 = next((nid for nid, n in g.items()
                 if n.get("class_type") == "MiniMaxH3ImageToVideo"), None)
    if 节点 is None:
        print("    ❌ 工作流里找不到 MiniMaxH3ImageToVideo")
        return None
    assert "first_frame" in g[节点]["inputs"], "这个节点没有 first_frame 输入"
    g[节点]["inputs"]["prompt"] = 提示词
    g[节点]["inputs"]["length"] = 帧

    for _, n in g.items():
        if n.get("class_type") == "RandomNoise":
            n["inputs"]["noise_seed"] = 种子
        if n.get("class_type") == "BasicScheduler":
            n["inputs"]["steps"] = 步数
        if n.get("class_type") == "SaveVideo":
            n["inputs"]["filename_prefix"] = "video/DSH_不烧心"

    try:
        pid = json.loads(urllib.request.urlopen(
            urllib.request.Request(地址 + "/api/prompt",
                                   json.dumps({"prompt": g, "client_id": "dsh_bsx"}).encode(),
                                   {"Content-Type": "application/json"}),
            timeout=120).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"    ❌ HTTP {e.code}：{body[:900]}")
        return None
    if "prompt_id" not in pid:
        print(f"    ❌ 被拒：{json.dumps(pid, ensure_ascii=False)[:900]}")
        return None
    pid = pid["prompt_id"]

    t0 = time.time()
    峰显 = 峰内 = 0
    while time.time() - t0 < 超时秒:
        time.sleep(8)
        用, _ = 显存()
        峰显 = max(峰显, 用)
        峰内 = max(峰内, 内存GB())
        try:
            h = json.loads(urllib.request.urlopen(f"{地址}/api/history/{pid}", timeout=30).read())
        except Exception:
            continue
        if pid not in h:
            continue
        rec = h[pid]
        st = rec.get("status", {})
        if st.get("status_str") == "error":
            print(f"    ❌ 执行出错：{json.dumps(st.get('messages', [])[-2:], ensure_ascii=False)[:700]}")
            return None
        秒 = time.time() - t0
        路 = _取回(rec, 出来路)
        if 路:
            print(f"    ✅ {秒:.0f} 秒   峰显存 {峰显} MiB   峰内存 {峰内:.1f} GB")
        return 路

    print(f"    ❌ 超时 {超时秒} 秒")
    return None


def _取回(rec: dict, 出来路: str) -> str | None:
    for _, o in rec.get("outputs", {}).items():
        for k in ("videos", "gifs", "images"):
            for it in o.get(k) or []:
                if not isinstance(it, dict) or not it.get("filename"):
                    continue
                fn = it["filename"]
                if not fn.lower().endswith((".mp4", ".webm", ".mkv")):
                    continue
                q = urllib.parse.urlencode({"filename": fn,
                                            "subfolder": it.get("subfolder", ""),
                                            "type": it.get("type", "output")})
                try:
                    数据 = urllib.request.urlopen(f"{地址}/api/view?{q}", timeout=600).read()
                except Exception:
                    src = os.path.join(Comfy输出, str(it.get("subfolder") or ""), fn)
                    if not os.path.isfile(src):
                        continue
                    数据 = open(src, "rb").read()
                os.makedirs(os.path.dirname(出来路), exist_ok=True)
                with open(出来路, "wb") as f:
                    f.write(数据)
                return 出来路
    print("    ❌ 没拿到 mp4")
    return None


def 读时长(路: str) -> tuple[float, int, int]:
    import av
    with av.open(路) as c:
        n = float(c.duration or 0) / 1e6
        return n, len(c.streams.video), len(c.streams.audio)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("用法：python MiniMax动态.py 首帧.png '动作' '台词' 出来.mp4 [帧] [种子]")
        raise SystemExit(1)
    帧数 = int(sys.argv[5]) if len(sys.argv) > 5 else 帧每镜
    种 = int(sys.argv[6]) if len(sys.argv) > 6 else 12345
    r = 出动态(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], 帧数, 种)
    if r:
        d, nv, na = 读时长(r)
        print(f"✓ {r}  {d:.2f} 秒  {nv} 视频轨 / {na} 音频轨")
