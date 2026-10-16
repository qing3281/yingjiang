# -*- coding: utf-8 -*-
"""
图生视频 —— Wan 2.2 本地出片

用法：
  python 图生视频.py --图 起始图.png --提示词 "镜头缓慢推近，风吹动头发" [选项]

  --宽 832 --高 480        分辨率（32 的倍数，5B 建议 832x480 起步）
  --帧 49 --fps 16         帧数（4n+1）与帧率；49 帧 @16fps ≈ 3.0 秒
  --线 5b|14b              5b = ti2v 冒烟线；14b = i2v + LightX2V 4步（质量线）
  --步数 N                 覆盖默认步数（5b 默认 20，14b 默认 4）
  --种子 N
  --等 分钟                超时（默认 40）

设计要点：
  · 5B 与 14B 是**两套不通用**的 VAE/latent 组合，见各 workflow json 顶部注释
  · 提交后按自己的 prompt_id 轮询 history —— /history 会带回旧任务，不筛会提前判完
"""
import argparse
import json
import mimetypes
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
本目录 = os.path.dirname(os.path.abspath(__file__))          # …\B站\制作
仓库根 = os.path.dirname(os.path.dirname(本目录))             # …\DSHworkspace
WF目录 = os.path.join(仓库根, "本地AI", "workflows")

工作流 = {
    "5b": "Wan22_5B_ti2v_api.json",
    "14b": "Wan22_14B_i2v_4step_api.json",
}
默认参数 = {
    "5b": {"步数": 20, "负向": "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
                              "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
                              "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
                              "杂乱的背景，三条腿，背景人很多，倒着走"},
    "14b": {"步数": 4, "负向": "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
                              "最差质量，低质量，模糊，扭曲，变形"},
}


def 取(p, 超时=30):
    with urllib.request.urlopen(COMFY + p, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 发(p, 数据, 超时=90):
    req = urllib.request.Request(COMFY + p, data=json.dumps(数据).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 传图(路径):
    """上传到 ComfyUI 的 input 目录，返回服务端文件名"""
    with open(路径, "rb") as f:
        数据 = f.read()
    边界 = "----dsh" + uuid.uuid4().hex
    名 = os.path.basename(路径)
    类型 = mimetypes.guess_type(名)[0] or "image/png"
    体 = b""
    体 += f"--{边界}\r\n".encode()
    体 += f'Content-Disposition: form-data; name="image"; filename="{名}"\r\n'.encode()
    体 += f"Content-Type: {类型}\r\n\r\n".encode()
    体 += 数据 + b"\r\n"
    体 += f"--{边界}\r\n".encode()
    体 += b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
    体 += f"--{边界}--\r\n".encode()
    req = urllib.request.Request(
        COMFY + "/upload/image", data=体,
        headers={"Content-Type": f"multipart/form-data; boundary={边界}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        j = json.loads(r.read().decode("utf-8"))
    子 = j.get("subfolder") or ""
    return (子 + "/" + j["name"]) if 子 else j["name"], j["name"]


def 填(模板, 映射):
    def 走(o):
        if isinstance(o, dict):
            return {k: 走(v) for k, v in o.items()}
        if isinstance(o, list):
            return [走(v) for v in o]
        if isinstance(o, str) and o.startswith("{{") and o.endswith("}}"):
            键 = o[2:-2]
            if 键 in 映射:
                return 映射[键]
        return o
    return {k: 走(v) for k, v in 模板.items() if not k.startswith("_")}


def 卸本地模型():
    """视频生成吃满显存，先把 LM Studio 的模型卸掉整块让路"""
    lms = os.path.expanduser(r"~\.lmstudio\bin\lms.exe")
    if not os.path.exists(lms):
        return None
    try:
        子 = subprocess.run([lms, "unload", "--all"], capture_output=True,
                            text=True, timeout=120, encoding="utf-8", errors="replace")
        行 = [x for x in (子.stdout or "").strip().splitlines() if x.strip()]
        return 行[-1] if 行 else "(已卸载)"
    except Exception as e:
        return f"(失败 {e})"


def 释放显存():
    r = 卸本地模型()
    if r:
        print(f"      本地 LLM：{r[:70]}")
    try:
        发("/free", {"unload_models": True, "free_memory": True})
        time.sleep(1.5)
    except Exception:
        pass


def 状态():
    s = 取("/system_stats", 8)
    d = s["devices"][0]
    return d["vram_free"] / 2 ** 30, d["vram_total"] / 2 ** 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--图", required=True, help="起始图（本机绝对路径）")
    ap.add_argument("--提示词", required=True)
    ap.add_argument("--宽", type=int, default=832)
    ap.add_argument("--高", type=int, default=480)
    ap.add_argument("--帧", type=int, default=49, help="4n+1")
    ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--线", choices=["5b", "14b"], default="5b")
    ap.add_argument("--步数", type=int, default=None)
    ap.add_argument("--种子", type=int, default=None)
    ap.add_argument("--输出", default=None)
    ap.add_argument("--等", type=int, default=40, help="超时分钟")
    ap.add_argument("--不释放显存", action="store_true")
    ap.add_argument("--只校验", action="store_true", help="只提交不等待，用于验证工作流结构")
    args = ap.parse_args()

    if not os.path.isabs(args.图) or not os.path.exists(args.图):
        sys.exit(f"❌ 图不存在或不是绝对路径：{args.图}")
    if (args.帧 - 1) % 4 != 0:
        sys.exit(f"❌ 帧数必须是 4n+1，收到 {args.帧}")
    if args.宽 % 32 or args.高 % 32:
        sys.exit(f"❌ 宽高必须是 32 的倍数，收到 {args.宽}x{args.高}")

    线 = args.线
    参 = dict(默认参数[线])
    步数 = args.步数 if args.步数 is not None else 参["步数"]
    种子 = args.种子 if args.种子 is not None else random.randint(0, 2 ** 31 - 1)

    print("=" * 66)
    print(f"Wan 2.2 {线.upper()}  |  {args.宽}x{args.高}  {args.帧} 帧 @{args.fps}fps = {args.帧 / args.fps:.2f} 秒")
    print(f"起点  {args.图}")
    print(f"提示  {args.提示词[:80]}")

    if not args.不释放显存:
        空闲, 总 = 状态()
        print(f"显存  空闲 {空闲:.1f}/{总:.1f} GB → 卸载 ComfyUI 常驻模型")
        释放显存()
        空闲, 总 = 状态()
        print(f"      空闲 {空闲:.1f}/{总:.1f} GB")

    服务端名, _ = 传图(args.图)
    print(f"已上传 → {服务端名}")

    模板 = json.load(open(os.path.join(WF目录, 工作流[线]), encoding="utf-8"))
    图 = 填(模板, {
        "PROMPT": args.提示词, "NEGATIVE": 参["负向"], "SEED": 种子,
        "IMAGE": 服务端名, "W": args.宽, "H": args.高,
        "LEN": args.帧, "FPS": args.fps,
        "PREFIX": "Wan出片/" + os.path.splitext(os.path.basename(args.图))[0],
    })
    if 步数 != 参["步数"]:
        for k, v in 图.items():
            if v.get("class_type") in ("KSampler", "KSamplerAdvanced"):
                v["inputs"]["steps"] = 步数

    try:
        r = 发("/prompt", {"prompt": 图})
    except urllib.error.HTTPError as e:
        d = json.loads(e.read().decode("utf-8", "replace"))
        print("❌ 校验失败：", d.get("error", {}).get("message"))
        for nid, ne in (d.get("node_errors") or {}).items():
            for err in ne.get("errors", []):
                print(f"   #{nid} {ne.get('class_type')}  {err.get('type')}  "
                      f"{err.get('message')} {str(err.get('extra_info', {}))[:160]}")
        sys.exit(1)

    pid = r["prompt_id"]
    print(f"已入队 {pid}   种子 {种子}")
    if args.只校验:
        print("（--只校验：不等待）")
        return

    起 = time.time()
    上次 = 0
    while time.time() - 起 < args.等 * 60:
        time.sleep(3)
        try:
            h = 取(f"/history/{pid}", 15)
        except Exception:
            continue
        if pid not in h:
            # 进度：从 /queue 里看还剩几个
            try:
                q = 取("/queue", 8)
                跑 = len(q.get("queue_running", []))
                if 跑 and time.time() - 上次 > 30:
                    print(f"   ... 运行中 {time.time() - 起:.0f}s")
                    上次 = time.time()
            except Exception:
                pass
            continue
        rec = h[pid]
        状 = rec.get("status", {})
        if 状.get("status_str") == "error":
            print("❌ ComfyUI 执行报错：")
            for m in 状.get("messages", []):
                print("   ", json.dumps(m, ensure_ascii=False)[:300])
            sys.exit(1)
        耗 = time.time() - 起
        出 = rec.get("outputs", {})
        for nid, o in 出.items():
            # SaveVideo 把 mp4 放在 images 键里并标 animated=true；老节点用 videos/gifs
            候选 = (o.get("videos") or o.get("gifs")
                    or [x for x in (o.get("images") or []) if x.get("filename", "").lower().endswith((".mp4", ".webm", ".mkv"))])
            for v in 候选:
                名 = v.get("filename")
                if not 名:
                    continue
                存 = args.输出 or os.path.join(os.path.dirname(args.图), 名)
                import urllib.parse
                q2 = urllib.parse.urlencode({"filename": 名, "subfolder": v.get("subfolder", ""),
                                             "type": v.get("type", "output")})
                with urllib.request.urlopen(f"{COMFY}/view?{q2}", timeout=300) as rr:
                    数据 = rr.read()
                os.makedirs(os.path.dirname(存), exist_ok=True)
                with open(存, "wb") as f:
                    f.write(数据)
                print("=" * 66)
                print(f"✅ 出片 {存}")
                print(f"   {len(数据) / 1024 / 1024:.2f} MB   {args.帧 / args.fps:.2f} 秒视频")
                print(f"   ⏱ 总耗时 {耗:.1f} 秒   →  {耗 / (args.帧 / args.fps):.1f} 秒/秒视频")
                return
        print("任务结束但没拿到视频：", json.dumps(出, ensure_ascii=False)[:400])
        sys.exit(1)
    sys.exit(f"❌ 超时（{args.等} 分钟）")


if __name__ == "__main__":
    main()
