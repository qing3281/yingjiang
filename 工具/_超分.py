# -*- coding: utf-8 -*-
"""
_超分.py —— 用远端 RTX 5080 跑 SeedVR2 超分。

## 为什么这么做

官方给的工作流 `utility_seedvr2_3b_int8_upscale_video.json` 是 **UI 格式**，
而且核心逻辑藏在一个 **subgraph** 里，`/prompt` 接口不认。所以这个脚本按
`/object_info` 拿到的真实签名，**手搭一份 API 格式**（顶层键是 "1".."N"，
每节 `{"class_type":…, "inputs":{…}}`）—— 跟 `影匠\\引擎.py:151` 的
`_请求("/prompt", {"prompt": 工作流})` 是同一个格式，零转换。

搭的时候的对应关系（来自 subgraph `Upscale Video (SeedVR2 3B Int8)`）：
    LoadVideo → Video Slice（本脚本省掉，片源自己先切好）
      → GetVideoComponents.images
      → ResizeImageMaskNode（scale by multiplier 2 / lanczos）
      → SeedVR2Preprocess
      → VAEEncodeTiled → SeedVR2TemporalChunk → SeedVR2Conditioning(model, 分块后的latent)
      → KSampler（steps=1 cfg=1 euler simple denoise=1）
      → SeedVR2TemporalMerge → VAEDecodeTiled
      → SeedVR2PostProcessing（images + original_resized_images）
      → CreateVideo → SaveVideo

## 官方排错（docs.comfy.org/tutorials/utility/seedvr2）
    INT8 可能全黑 → ①关 FlashAttention（3090 上验证有效）②换 FP16/FP8
                    ③确认两个文件都完整（截断下载同样全黑）④关实时预览

用法：
    python _超分.py --试              只提交，把服务端的报错原样打出来
    python _超分.py --跑              提交并一直等到出片
    python _超分.py --看              看远端队列和最近产出
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根
远端 = "http://100.127.224.106:8188"
本机 = "http://127.0.0.1:8188"

# ★ 这两个名字是从远端 `/object_info` 的 COMBO 列表里读出来的，别猜
模型_3B = "seedvr2_3b_int8_convrot.safetensors"
模型_7B = "seedvr2_7b_int8_convrot.safetensors"
VAE = "seedvr2_ema_vae_fp16.safetensors"


def 建工作流(文件, 倍数=2, 模型=模型_3B, vae名=VAE,
             前缀="Upscaled_seedVR2", 色彩="none", 块模式="manual",
             帧每块=21, 瓦片=512, 瓦叠=128, 时块=64, 时叠=8, 种子=42):
    """搭 API 格式。倍数 = 先 lanczos 放大几倍，再让 SeedVR2 还原细节。"""
    return {
        # ① 读片
        "1": {"class_type": "LoadVideo",
              "inputs": {"file": 文件}},
        # ② 拆成帧 + 拿到原帧率（音频后面用不上，H3 出的片没音轨）
        "2": {"class_type": "GetVideoComponents",
              "inputs": {"video": ["1", 0]}},
        # ③ 先放大 —— SeedVR2 是「还原」不是「拉伸」，得先给它一张大图
        #    ★ 动态下拉的附加字段名是 `resize_type.multiplier`（服务端报错里给的原文），
        #      不是 `multiplier`。第一次写成 `multiplier` 被 400 拒了。
        "3": {"class_type": "ResizeImageMaskNode",
              "inputs": {"input": ["2", 0],
                         "resize_type": "scale by multiplier",
                         "resize_type.multiplier": float(倍数),
                         "scale_method": "lanczos"}},
        # ④ 预处理
        "4": {"class_type": "SeedVR2Preprocess",
              "inputs": {"resized_images": ["3", 0]}},
        # ⑤ 模型
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": vae名}},
        "6": {"class_type": "UNETLoader",
              "inputs": {"unet_name": 模型, "weight_dtype": "default"}},
        # ⑥ 编码 → 条件
        #    ★★ 这里是整个工作流最容易接错的一根线（我接错过一次）：
        #       `SeedVR2Conditioning` 吃的必须是**分块之后**的 latent，
        #       不是分块之前那份。接错的表现是采样时报：
        #       `SeedVR2 conditioning shape must match latent batch/temporal/spatial
        #        dimensions; got latent (1,16,1,192,336) and conditioning (1,17,21,192,336)`
        #       —— 左边是「一块」，右边是「整段」，两个 T 不一样。
        #    所以顺序是：VAEEncodeTiled → SeedVR2TemporalChunk → SeedVR2Conditioning
        #    → KSampler。TemporalChunk 吐的是**一串**块，ComfyUI 会自动逐块迭代，
        #    conditioning 跟着一起迭代，merge 再把它们收回来。
        "7": {"class_type": "VAEEncodeTiled",
              "inputs": {"pixels": ["4", 0], "vae": ["5", 0],
                         "tile_size": 瓦片, "overlap": 瓦叠,
                         "temporal_size": 时块, "temporal_overlap": 时叠}},
        # ⑦ 分块（在条件之前！）
        #    ★ `frames_per_chunk` 的单位是**像素帧**，必须是 4n+1（1,5,9,13,21…）
        #    另：chunking_mode 是 DYNAMICCOMBO，附加字段名要带前缀
        #       `chunking_mode.frames_per_chunk`，跟 `resize_type.multiplier` 一个规矩
        "9": {"class_type": "SeedVR2TemporalChunk",
              "inputs": ({"latent": ["7", 0], "temporal_overlap": 0,
                          "chunking_mode": 块模式}
                         if 块模式 == "auto" else
                         {"latent": ["7", 0], "temporal_overlap": 0,
                          "chunking_mode": 块模式,
                          "chunking_mode.frames_per_chunk": int(帧每块)})},
        "8": {"class_type": "SeedVR2Conditioning",
              "inputs": {"model": ["6", 0], "vae_conditioning": ["9", 0]}},
        # ⑧ 一步采样（denoise=1、steps=1、cfg=1，SeedVR2 是单步扩散）
        "10": {"class_type": "KSampler",
               "inputs": {"model": ["6", 0], "seed": 种子, "steps": 1, "cfg": 1.0,
                          "sampler_name": "euler", "scheduler": "simple",
                          "positive": ["8", 0], "negative": ["8", 1],
                          "latent_image": ["9", 0], "denoise": 1.0}},
        "11": {"class_type": "SeedVR2TemporalMerge",
               "inputs": {"latents": ["10", 0], "temporal_overlap": ["9", 1]}},
        # ⑧ 解码 → 校色 → 存
        "12": {"class_type": "VAEDecodeTiled",
               "inputs": {"samples": ["11", 0], "vae": ["5", 0],
                          "tile_size": 瓦片, "overlap": 瓦叠,
                          "temporal_size": 时块, "temporal_overlap": 时叠}},
        "13": {"class_type": "SeedVR2PostProcessing",
               "inputs": {"images": ["12", 0], "original_resized_images": ["4", 0],
                          "color_correction_method": 色彩}},
        "14": {"class_type": "CreateVideo",
               "inputs": {"images": ["13", 0], "fps": ["2", 2]}},
        "15": {"class_type": "SaveVideo",
               "inputs": {"video": ["14", 0], "filename_prefix": 前缀,
                          "format": "auto", "codec": "auto"}},
    }


def 建工作流GAN(文件, 放大模型="4x_foolhardy_Remacri.pth", 缩放回=0,
                前缀="Upscaled_GAN"):
    """GAN 放大（快路）—— 照官方 `utility-gan_upscaler.json` 搭。

    ★ 和 SeedVR2 那条路的区别，是「还原」和「拉伸」的区别：
      · SeedVR2 是**扩散还原** —— 会按提示重新长出细节，慢，但糊的地方能救回来
      · GAN（Remacri / RealESRGAN / NMKD）是**卷积放大** —— 不生成新细节，只把现有的边缘做锐，
        **快得多**（一条 5 秒的片几秒就完），而且不需要远端
      → 所以两条路都要留着：**片子本来就清楚就用 GAN，糊得厉害再上 SeedVR2。**

    ★ 官方模板上的原话：「Model determines output size — 2x models upscale 2x,
      4x models upscale 4x」+「Tip: Upscale 4x first, then use a resize node to bring
      it down to your target resolution」。所以本机那三个都是 **4x**，
      想要 2x 就先 4x 再缩回来（`缩放回` 就是干这个的）。
    """
    流 = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": 文件}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "UpscaleModelLoader",
              "inputs": {"model_name": 放大模型}},
        "4": {"class_type": "ImageUpscaleWithModel",
              "inputs": {"upscale_model": ["3", 0], "image": ["2", 0]}},
    }
    if 缩放回:
        # 缩回指定倍数的办法：按目标宽算。宽度取不到就退回按倍数缩。
        # 用 ComfyUI 自带的 ImageScaleBy（按倍数，比 ImageScale 少一次算宽）
        流["5"] = {"class_type": "ImageScaleBy",
                   "inputs": {"image": ["4", 0], "upscale_method": "lanczos",
                              "scale_by": float(缩放回)}}
        末 = ["5", 0]
    else:
        末 = ["4", 0]
    # ★ `CreateVideo` 的 `audio` 是**可选**口，不接就把音轨丢了 ——
    #   实测第一版放完 832×480 → 1664×960 很漂亮，但**声音没了**（原片是有立体声的）。
    #   `GetVideoComponents` 的 [1] 就是拆出来的那条音轨，直接接上。
    流["14"] = {"class_type": "CreateVideo",
                "inputs": {"images": 末, "fps": ["2", 2], "audio": ["2", 1]}}
    流["15"] = {"class_type": "SaveVideo",
                "inputs": {"video": ["14", 0], "filename_prefix": 前缀,
                           "format": "auto", "codec": "auto"}}
    return 流


def 请求(路, 数据=None, 主机=远端, 超时=120):
    u = 主机 + 路
    头 = {"Content-Type": "application/json"}
    body = json.dumps(数据).encode("utf-8") if 数据 is not None else None
    r = urllib.request.Request(u, data=body, headers=头,
                               method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(r, timeout=超时) as f:
            t = f.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # ★ 400 的正文里才有「哪个节点哪个字段不对」，直接 raise 会把它吞掉
        t = e.read().decode("utf-8", "replace")
        try:
            return json.loads(t)
        except Exception:
            return {"_原文": t, "_HTTP": e.code}
    try:
        return json.loads(t)
    except Exception:
        return {"_原文": t}


def 提交(工作流, 主机=远端):
    return 请求("/prompt", {"prompt": 工作流, "client_id": "dsh-chaofen"}, 主机)


def 队列(主机=远端):
    return 请求("/queue", None, 主机)


def 历史(主机=远端):
    return 请求("/history", None, 主机, 超时=180)


def 说错(错):
    """把 ComfyUI 的校验错误说成人话。"""
    if isinstance(错, dict):
        e = 错.get("error") or {}
        print(f"    error.type    = {e.get('type')}")
        print(f"    error.message = {e.get('message')}")
        for 细 in (e.get("details") or "").split("\n")[:25]:
            print(f"      {细}")
        for k, v in (错.get("node_errors") or {}).items():
            print(f"    节点 {k}：")
            print(f"      {json.dumps(v, ensure_ascii=False)[:600]}")
    else:
        print(f"    {json.dumps(错, ensure_ascii=False)[:1500]}")


远输入 = "E:/影匠AI/ComfyUI/input"
ssh别名 = "776bjta"


def 远端有这个(名, 大小):
    """远端 input/ 里有没有同名同大小的文件。

    ★ 这句 python 只输出 ASCII —— 中文经 PowerShell→ssh→cmd→python 这条链会被吃成乱码，
      这个坑我踩过不止一次（见 `记忆\\经验\\流程与脚本.md`）。
    """
    code = (f"import os;p=r'{远输入}/{名}';"
            f"print(os.path.getsize(p) if os.path.isfile(p) else -1)")
    try:
        r = subprocess.run(["ssh", ssh别名, 'python -c "%s"' % code],
                           capture_output=True, timeout=40)
        t = (r.stdout or b"").decode("ascii", "replace").strip()
        return t.lstrip("-").isdigit() and int(t) == 大小
    except Exception:
        return False


def 送过去(本地路):
    """把本机文件送到远端 input/，返回远端认的那个文件名。

    已经有同名同大小的就不重传 —— 这条路是 2 MB/s（实测），能省就省。
    """
    本地路 = os.path.abspath(本地路)
    if not os.path.isfile(本地路):
        raise SystemExit("本地没这个文件：%s" % 本地路)
    名 = os.path.basename(本地路)
    大小 = os.path.getsize(本地路)
    if 远端有这个(名, 大小):
        print("  远端已有 %s（%d 字节），不重传" % (名, 大小))
        return 名
    print("  传到远端 input/：%s（%.1f MB，按 2 MB/s 约 %.0f 秒）"
          % (名, 大小 / 1048576, 大小 / 1048576 / 2))
    r = subprocess.run(["scp", "-q", 本地路, "%s:%s/%s" % (ssh别名, 远输入, 名)],
                       capture_output=True, timeout=7200)
    if r.returncode != 0:
        raise SystemExit("scp 失败：" +
                         (r.stderr or b"").decode("utf-8", "replace")[:400])
    # ★ 传完回读验证大小。但别在带宽刚跑满时立刻查 —— 那时 ssh 会超时给出假失败。
    for _ in range(4):
        if 远端有这个(名, 大小):
            print("  ✓ 远端大小对上了")
            return 名
        time.sleep(4)
    raise SystemExit("传完了但远端大小对不上：%s" % 名)


本输入 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\input"   # 实测这条路才对（ComfyUI-master\input 不存在）


def _塞进本机(名, 本地路):
    """把本机文件放进本机 ComfyUI 的 input/ —— `/prompt` 里的 `file` 只认 input/ 下的文件名。

    ★ 同名同大小就不重放；放完**回读大小**，别只看 copy 没报错。
    """
    本地路 = os.path.abspath(本地路)
    if not os.path.isfile(本地路):
        raise SystemExit("本地没这个文件：%s" % 本地路)
    # ★ `/prompt` 的 LoadVideo.file 只认**input/ 下的文件名**，不认完整路径。
    #   第一版我把传进来的整条路径当文件名用了，ComfyUI 报
    #   `Invalid video file: D:\DSHworkspace\...\04_锚1格1.mp4` —— 它去 input/ 下找这个名字。
    名 = os.path.basename(本地路)
    if not os.path.isdir(本输入):
        raise SystemExit("本机 ComfyUI 的 input 目录不在：%s" % 本输入)
    去 = os.path.join(本输入, 名)
    if os.path.isfile(去) and os.path.getsize(去) == os.path.getsize(本地路):
        print("  本机 input 里已有 %s（%d 字节），不重放" % (名, os.path.getsize(去)))
        return 名
    shutil.copy2(本地路, 去)
    好 = os.path.getsize(去) if os.path.isfile(去) else -1
    if 好 != os.path.getsize(本地路):
        raise SystemExit("放进 input 之后大小对不上：%d vs %d"
                         % (好, os.path.getsize(本地路)))
    print("  ✓ 放进本机 input/：%s（%d 字节）" % (名, 好))
    return 名


def 主():
    参 = argparse.ArgumentParser()
    参.add_argument("--试", action="store_true", help="只提交，把报错原样打出来")
    参.add_argument("--跑", action="store_true", help="提交并等到出片")
    参.add_argument("--看", action="store_true", help="看队列和历史")
    参.add_argument("--文件", default="磨刀_原片_5s.mp4",
                    help="远端 input/ 里的文件名；给本机路径则自动传过去")
    参.add_argument("--倍数", type=float, default=2)
    参.add_argument("--模型", default=模型_3B)
    参.add_argument("--色彩", default="none")
    参.add_argument("--块模式", default="manual", choices=["auto", "manual"])
    参.add_argument("--帧每块", type=int, default=21, help="像素帧，必须 4n+1")
    参.add_argument("--前缀", default="Upscaled_seedVR2")
    参.add_argument("--主机", default=远端)
    参.add_argument("--放大模型", default="",
                    help="★ 给了就走 GAN 快路（Remacri / RealESRGAN_x4plus.pth / "
                         "4x_NMKD-Siax_200k.pth），默认跑本机，几秒就完")
    参.add_argument("--缩放回", type=float, default=0,
                    help="GAN 那三个模型都是 4x；想要 2x 就先 4x 再按这个倍数缩回来")
    a = 参.parse_args()

    if a.看:
        q = 队列(a.主机)
        print(f"队列：跑 {len(q.get('queue_running') or [])} 个，等 "
              f"{len(q.get('queue_pending') or [])} 个")
        for it in (q.get("queue_running") or []) + (q.get("queue_pending") or []):
            print(f"   prompt_id={it[1]}  {str(it[3])[:80] if len(it)>3 else ''}")
        h = 历史(a.主机)
        print(f"\n历史 {len(h)} 条，最近 8 条：")
        for pid in list(h)[-8:]:
            e = h[pid]
            st = (e.get("status") or {})
            print(f"   {pid}  {st.get('status_str')}  {st.get('completed')}")
            for m in (st.get("messages") or []):
                if m[0] in ("execution_error", "execution_interrupted"):
                    print(f"      ★ {m[0]}: {json.dumps(m[1], ensure_ascii=False)[:400]}")
        return 0

    文件名 = a.文件
    GAN = bool(a.放大模型)
    # ★ GAN 那三个放大模型本机就有，不用走 2 MB/s 那条线 —— 不指定主机时按模式选
    主机 = a.主机 if a.主机 != 远端 or not GAN else 本机
    if os.path.isfile(a.文件) or os.path.sep in a.文件:
        文件名 = 送过去(a.文件) if 主机 == 远端 else _塞进本机(文件名, a.文件)

    if GAN:
        流 = 建工作流GAN(文件名, a.放大模型, a.缩放回, a.前缀 or "Upscaled_GAN")
        print(f"提交到 {主机}　【GAN 快路】")
        print(f"  文件 {文件名}   放大模型 {a.放大模型}   缩放回 {a.缩放回 or '不缩'}")
    else:
        流 = 建工作流(文件名, a.倍数, a.模型, VAE, a.前缀, a.色彩,
                    a.块模式, a.帧每块)
        print(f"提交到 {主机}　【SeedVR2 还原路】")
        print(f"  文件 {文件名}   倍数 {a.倍数}   模型 {a.模型}   色彩 {a.色彩}")
    if a.试:
        print(f"  工作流 {len(流)} 个节点：" + " ".join(流))
    r = 提交(流, 主机)
    if "prompt_id" in r:
        pid = r["prompt_id"]
        print(f"  ✓ 收下了，prompt_id = {pid}")
        print(f"    节点数报回 {r.get('number')}，node_errors = "
              f"{json.dumps(r.get('node_errors') or {}, ensure_ascii=False)[:400]}")
        if not a.跑:
            return 0
    else:
        print("  ✗ 被拒了：")
        说错(r)
        return 1

    # 等
    # ★★ 这里必须是**算出来的 `主机`**，不能是 `a.主机`。
    #    `--主机` 的默认值是远端，而 GAN 那条路会把 `主机` 改成本机（模型在本机）。
    #    写成 `a.主机` 就会：**提交到本机、却去轮询远端的 history** ——
    #    远端永远不会有这个 prompt_id，于是干等到一小时超时才退出，
    #    而产物其实早就落在本机 output/ 里了（实测 13:31:24 就出片了，脚本还在等）。
    t0 = time.time()
    while True:
        time.sleep(5)
        e = 历史(主机).get(pid)
        if e:
            st = (e.get("status") or {})
            print(f"  [{time.time()-t0:6.0f}s] {st.get('status_str')} "
                  f"completed={st.get('completed')}")
            for m in (st.get("messages") or []):
                if m[0] in ("execution_error", "execution_interrupted"):
                    print(f"  ★ {m[0]}：")
                    说错(m[1])
                    return 1
            if st.get("completed"):
                print("  ✓ 跑完了。产出：")
                for nid, o in (e.get("outputs") or {}).items():
                    for k, v in o.items():
                        print(f"     节点{nid} {k} = {json.dumps(v, ensure_ascii=False)[:300]}")
                return 0
        if time.time() - t0 > 14400:
            print("  ✗ 等了 4 小时还没完，停手")
            return 1


if __name__ == "__main__":
    sys.exit(主())
