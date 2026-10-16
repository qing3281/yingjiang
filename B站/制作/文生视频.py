# -*- coding: utf-8 -*-
"""MiniMax-H3 文生视频（带声音）—— 复用图生视频.py 的骨架，换一套节点。

跟「图生视频.py」的区别：
  · MiniMax-H3 是**视频+音频联合生成**，出的 mp4 自带音轨（对白/环境音），
    这是目前唯一能给片子配上「人声」的本地模型
  · 它是蒸馏模型（4 步、无 cfg、无负面），节点里没有 KSampler，走 SamplerCustomAdvanced
  · `MiniMaxH3ImageToVideo` 这个名字有误导——它不吃起始图，只吃提示词+宽高+帧数，
    实际是 t2v(a) 节点：输出 [0]=conditioning  [1]=空 latent

用法：
    python 文生视频.py --提示词 "..."                      # 默认 1344x768 / 362 帧 = 15.08 秒
    python 文生视频.py --提示词 "..." --帧 121 --输出 短.mp4
    python 文生视频.py --提示词 "..." --只校验
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

本目录 = os.path.dirname(os.path.abspath(__file__))
仓库根 = os.path.dirname(os.path.dirname(本目录))  # D:\DSHworkspace
WF目录 = os.path.join(仓库根, "本地AI", "workflows")
默认工作流 = os.path.join(WF目录, "MinimaxH3_t2va_api.json")
默认输出目录 = r"D:\Comfy-Desktop\ComfyUI-Shared\output\MiniMax出片"

# 官方模板的默认值
默认宽 = 1344
默认高 = 768
默认帧 = 362          # 362 帧 @24fps = 15.08 秒
默认fps = 24
默认步数 = 4          # turbo 4 步 LoRA


def 服务在跑(地址):
    try:
        urllib.request.urlopen(地址 + "/api/queue", timeout=8).read()
        return True
    except Exception:
        return False


def 显存状态():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        )
        a, b = r.stdout.strip().split(",")
        return int(a), int(b)
    except Exception:
        return None, None


def 卸本地模型():
    """把 LM Studio 的模型卸掉，腾显存给扩散模型。"""
    lms = os.path.join(os.path.expanduser("~"), ".lmstudio", "bin", "lms.exe")
    if not os.path.isfile(lms):
        return
    try:
        r = subprocess.run([lms, "ps"], capture_output=True, text=True, timeout=25)
        if "IDLE" in r.stdout or "LOADED" in r.stdout:
            subprocess.run([lms, "unload", "--all"], capture_output=True, text=True, timeout=60)
            print("   已卸载 LM Studio 模型")
    except Exception:
        pass


def 卸常驻模型(地址):
    """让 ComfyUI 把缓存的模型吐出来。"""
    try:
        req = urllib.request.Request(
            地址 + "/api/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=25).read()
    except Exception:
        pass


def 释放显存(地址, 卸LLM=True):
    if 卸LLM:
        卸本地模型()
    卸常驻模型(地址)
    time.sleep(2)
    用, 总 = 显存状态()
    if 用 is not None:
        print(f"   显存 {用} / {总} MiB（空闲 {总-用}）")


def 建工作流(提示词, 宽, 高, 帧, 种子, 前缀, 步数=默认步数, 工作流=None):
    wf = json.load(open(工作流 or 默认工作流, encoding="utf-8"))
    # 提示词在 MiniMaxH3ImageToVideo 节点上
    节点 = None
    for nid, n in wf.items():
        if n.get("class_type") == "MiniMaxH3ImageToVideo":
            节点 = nid
            break
    if 节点 is None:
        raise RuntimeError("工作流里找不到 MiniMaxH3ImageToVideo 节点")
    wf[节点]["inputs"]["prompt"] = 提示词
    wf[节点]["inputs"]["width"] = 宽
    wf[节点]["inputs"]["height"] = 高
    wf[节点]["inputs"]["length"] = 帧
    for nid, n in wf.items():
        ct = n.get("class_type")
        if ct == "RandomNoise":
            n["inputs"]["noise_seed"] = 种子
        elif ct == "SaveVideo":
            n["inputs"]["filename_prefix"] = 前缀
        elif ct == "BasicScheduler":
            n["inputs"]["steps"] = 步数
    return wf


def 提交(地址, wf):
    body = json.dumps({"prompt": wf, "client_id": "wensheng"}).encode()
    req = urllib.request.Request(地址 + "/api/prompt", body, {"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=60).read())
    if "prompt_id" not in d:
        raise RuntimeError("提交被拒：\n" + json.dumps(d, ensure_ascii=False, indent=2)[:2500])
    return d["prompt_id"]


def 等完成(地址, pid, 超时分钟):
    t0 = time.time()
    上限 = 超时分钟 * 60
    while time.time() - t0 < 上限:
        time.sleep(8)
        h = json.loads(urllib.request.urlopen(f"{地址}/api/history/{pid}", timeout=30).read())
        if pid in h:
            rec = h[pid]
            st = rec.get("status", {})
            if st.get("status_str") == "error" or not st.get("completed", True):
                msgs = st.get("messages", [])
                raise RuntimeError("执行出错：\n" + json.dumps(msgs[-3:], ensure_ascii=False, indent=2)[:2500])
            return rec, time.time() - t0
        q = json.loads(urllib.request.urlopen(f"{地址}/api/queue", timeout=20).read())
        n = len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
        print(f"   [{time.time()-t0:5.0f}s] 队列 {n}", flush=True)
    raise TimeoutError(f"超过 {超时分钟} 分钟还没出结果")


def 取文件(rec):
    """SaveVideo 把 mp4 放在 images 键里并标 animated。"""
    for nid, o in rec.get("outputs", {}).items():
        for k in ("videos", "gifs", "images", "audio"):
            for it in o.get(k) or []:
                if isinstance(it, dict) and it.get("filename"):
                    yield it["filename"], it.get("subfolder", ""), it.get("type", "output")


def 下载(地址, 文件名, 子目录, 类型, 目标):
    import urllib.parse
    q = urllib.parse.urlencode({"filename": 文件名, "subfolder": 子目录, "type": 类型})
    data = urllib.request.urlopen(f"{地址}/api/view?{q}", timeout=180).read()
    os.makedirs(os.path.dirname(目标), exist_ok=True)
    with open(目标, "wb") as f:
        f.write(data)
    return len(data)


def 耗时描述(秒):
    if 秒 < 60:
        return f"{秒:.1f} 秒"
    return f"{秒/60:.1f} 分（{秒:.0f} 秒）"


def main():
    p = argparse.ArgumentParser(description="MiniMax-H3 文生视频（带声音）")
    p.add_argument("--提示词", required=True, help="要生成什么（英文效果更稳）")
    p.add_argument("--宽", type=int, default=默认宽)
    p.add_argument("--高", type=int, default=默认高)
    p.add_argument("--帧", type=int, default=默认帧, help=f"总帧数，默认 {默认帧}（@24fps = 15 秒）")
    p.add_argument("--fps", type=int, default=默认fps)
    p.add_argument("--种子", type=int, default=11)
    p.add_argument("--步数", type=int, default=默认步数)
    p.add_argument("--前缀", default="MiniMax出片")
    p.add_argument("--输出", default=None, help="目标 mp4 路径")
    p.add_argument("--服务地址", default="http://127.0.0.1:8188")
    p.add_argument("--工作流", default=None)
    p.add_argument("--超时分钟", type=int, default=45)
    p.add_argument("--不释放显存", action="store_true")
    p.add_argument("--只校验", action="store_true")
    a = p.parse_args()

    地址 = a.服务地址.rstrip("/")
    帧 = a.帧

    print("=" * 60)
    print("MiniMax-H3 文生视频（视频 + 音频联合生成）")
    print("=" * 60)
    print(f"  画面   {a.宽}x{a.高}   {帧} 帧 @{a.fps}fps = {帧/a.fps:.2f} 秒")
    print(f"  步数   {a.步数}（turbo 蒸馏）")
    print(f"  提示词 {a.提示词[:90]}{'…' if len(a.提示词) > 90 else ''}")

    if not 服务在跑(地址):
        print(f"\n❌ ComfyUI 没在 {地址} 上跑")
        return 1

    wf = 建工作流(a.提示词, a.宽, a.高, 帧, a.种子, a.前缀, a.步数, a.工作流)
    if a.只校验:
        print("\n✅ 工作流构造成功（--只校验，未提交）")
        return 0

    if not a.不释放显存:
        print("\n[1/4] 腾显存")
        释放显存(地址)

    print("\n[2/4] 提交任务")
    pid = 提交(地址, wf)
    print(f"   prompt_id = {pid}")

    print("\n[3/4] 等生成")
    rec, 秒 = 等完成(地址, pid, a.超时分钟)
    每秒钟视频 = 秒 / (帧 / a.fps)
    print(f"   ✅ 完成，耗时 {耗时描述(秒)}（{每秒钟视频:.1f} 秒 / 秒视频）")

    print("\n[4/4] 取回文件")
    产物 = list(取文件(rec))
    if not 产物:
        print("   ❌ 没找到输出文件，原始 outputs：")
        print(json.dumps(rec.get("outputs", {}), ensure_ascii=False, indent=2)[:2000])
        return 1

    mp4 = None
    音频 = None
    for fn, sub, ty in 产物:
        if fn.lower().endswith((".mp4", ".webm", ".mkv")):
            mp4 = (fn, sub, ty)
        elif fn.lower().endswith((".flac", ".wav", ".mp3")):
            音频 = (fn, sub, ty)

    if not mp4:
        print("   ❌ 没找到视频文件")
        return 1

    目标 = a.输出 or os.path.join(默认输出目录, os.path.basename(mp4[0]))
    大小 = 下载(地址, *mp4, 目标)
    print(f"   ✅ {目标}")
    print(f"      {大小/1048576:.2f} MB")

    if 音频:
        目标音频 = os.path.splitext(目标)[0] + ".wav"
        try:
            大小2 = 下载(地址, *音频, 目标音频)
            print(f"   ✅ 单独音轨 {目标音频}  ({大小2/1048576:.2f} MB)")
        except Exception as e:
            print(f"   （单独音轨取回失败：{e}）")

    # 确认 mp4 里真的有音轨
    try:
        import av
        c = av.open(目标)
        na = len(c.streams.audio)
        nv = len(c.streams.video)
        dur = float(c.duration or 0) / 1e6
        c.close()
        print(f"\n   检查：{nv} 条视频轨 / {na} 条音频轨 / 时长 {dur:.2f} 秒")
        if na == 0:
            print("   ⚠ mp4 里没有音轨")
    except Exception as e:
        print(f"   （无法检查轨道：{e}）")

    print(f"\n✅ 出片：{目标}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
