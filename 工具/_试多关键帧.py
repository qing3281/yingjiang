# -*- coding: utf-8 -*-
"""试「多关键帧 + 原生对白」—— 花小钱验两条我没走过的路。

不碰 `_出H3.py`。import 它、读它的表，自己搭一张图：
    首帧 + 3 张中间帧 + 尾帧   → MiniMaxH3MultiKeyframeConditioningT8Advanced
和旧路的区别只有一处：旧路 node7 是 `MiniMaxH3AudioConditioningT8`（只吃首尾帧），
新路 node7 是 `MiniMaxH3MultiKeyframeConditioningT8Advanced`（多吃 keyframe_plan 链）。

用法（中文一律不往命令行塞，写死在这里）：
    python _试多关键帧.py             # 格2，226 帧，本机
    python _试多关键帧.py --帧数 107   # 先拿 107 帧对一遍，确认图能跑
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import _出H3 as H  # noqa: E402

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
出 = r"D:\DSHworkspace\_试多关键帧"

宽, 高 = 1344, 768
帧率 = 24
步数 = 8
种子 = 1735946766
格号 = 2
帧数 = 226
端点名 = "本机"
模式 = "整格"          # 整格 = 首→(中1,中2,中3)→末；半A = 首→(中1)→中2；半B = 中2→(中3)→末
位们 = [25.0, 50.0, 75.0]   # 中间锚点落在这一段的百分之几处

词尾 = (
    "One single continuous take. The movement described above happens visibly and gradually, "
    "starting in the first second and finishing by the last. Keep the same person, the same "
    "clothing and the same location as the reference image, and preserve facial identity and "
    "natural skin texture. Natural location ambience with a clear human voice."
)


def 解析命令行():
    global 帧数, 格号, 端点名, 模式, 位们
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == "--帧数" and i + 1 < len(a):
            帧数 = int(a[i + 1])
        elif x == "--格" and i + 1 < len(a):
            格号 = int(a[i + 1])
        elif x == "--端点" and i + 1 < len(a):
            端点名 = a[i + 1]
        elif x == "--模式" and i + 1 < len(a):
            模式 = a[i + 1]
            if 模式 in ("半A", "半B"):
                位们 = [50.0]


def 建图多(首名, 中名们, 末名, 词, 种子值, 前缀):
    """抄 H.建图()，只把 node7 换成多关键帧版，并让 sampler 吃 node7 的 model 输出。"""
    图 = {
        "1": {"inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"},
              "class_type": "VAELoader"},
        "2": {"inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"},
              "class_type": "VAELoader"},
        "3": {"inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                         "type": "minimax", "device": "default"},
              "class_type": "CLIPLoader"},
        "4": {"inputs": {"unet_name": "minimax_h3_fl2va_int8_convrot.safetensors",
                         "weight_dtype": "default"},
              "class_type": "UNETLoader"},
        "5": {"inputs": {"lora_name": "minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors",
                         "strength_model": 1.0, "model": ["4", 0]},
              "class_type": "LoraLoaderBypassModelOnly"},
        "6": {"inputs": {"image": 首名}, "class_type": "LoadImage"},
        "7": {"inputs": {
                "prompt": 词, "width": 宽, "height": 高, "length": 帧数,
                "task_type": "FL2VA",
                "audio_mode": "native",
                "audio_denoise_strength": 1.0,
                "add_source_as_reference": False,
                "prompt_primary_audio_ordinal": 0,
                "strict_prompt_tags": True,
                "ref_image_size": "match",
                "reference_video_policy": "official_2_to_15s",
                "first_frame_noise_aug": 0.999,
                "last_frame_noise_aug": 0.999,
                "reference_visual_noise_aug": 0.999,
                "model": ["5", 0], "clip": ["3", 0],
                "video_vae": ["1", 0], "audio_vae": ["2", 0],
                "first_frame": ["6", 0], "last_frame": ["16", 0],
                "keyframe_plan": [str(20 + len(中名们) - 1), 0],
              }, "class_type": "MiniMaxH3MultiKeyframeConditioningT8Advanced"},
        "8": {"inputs": {"steps": 步数, "shift_video": 12.0, "shift_audio": 3.0,
                         "sampler_name": "dual_clock_euler", "scheduler": "native_flow",
                         "model": ["7", 0], "av_latent": ["7", 2]},
              "class_type": "MiniMaxH3DualClockSamplerT8"},
        "9": {"inputs": {"noise_seed": 种子值}, "class_type": "RandomNoise"},
        "10": {"inputs": {"model": ["8", 0], "conditioning": ["7", 1]},
               "class_type": "BasicGuider"},
        "11": {"inputs": {"noise": ["9", 0], "guider": ["10", 0], "sampler": ["8", 1],
                          "sigmas": ["14", 0], "latent_image": ["7", 2]},
               "class_type": "SamplerCustomAdvanced"},
        "12": {"inputs": {"av_latent": ["11", 0], "video_vae": ["1", 0], "audio_vae": ["2", 0]},
               "class_type": "MiniMaxH3AVDecodeT8"},
        "13": {"inputs": {"frame_rate": 帧率, "loop_count": 0, "filename_prefix": 前缀,
                          "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 17,
                          "save_metadata": True, "trim_to_audio": False, "pingpong": False,
                          "save_output": True, "images": ["12", 0], "audio": ["12", 1]},
               "class_type": "VHS_VideoCombine"},
        "14": {"inputs": {"sigmas": ["8", 2], "mode": "report_only", "start_progress": 0.5,
                          "tail_power": 1.6, "shift_video": 12.0, "shift_audio": 3.0,
                          "profile": "turbo_standard8", "sampling_route": "dual_clock_euler",
                          "accept_turbo_schedule_ood": False},
               "class_type": "MiniMaxH3AVSigmaSameNFERedistributionT8Advanced"},
        "16": {"inputs": {"image": 末名}, "class_type": "LoadImage"},
    }
    # 3 张中间帧各自的 LoadImage（17/18/19）与计划节点（20/21/22，链式接起来）
    位 = 位们
    for k, 名 in enumerate(中名们):
        图[str(17 + k)] = {"inputs": {"image": 名}, "class_type": "LoadImage"}
        节 = {"inputs": {"image": [str(17 + k), 0],
                         "position_mode": "percent", "position": 位[k],
                         "visual_noise_aug": 0.999, "resize_mode": "center_crop",
                         "enabled": True},
              "class_type": "MiniMaxH3KeyframePlanT8Advanced"}
        if k > 0:
            节["inputs"]["previous_plan"] = [str(20 + k - 1), 0]
        图[str(20 + k)] = 节
    return 图


def 提交(服务, 图):
    r = urllib.request.Request(
        f"{服务}/prompt",
        data=json.dumps({"prompt": 图, "client_id": "shiduoguankezhen"}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(r, timeout=120))
    except urllib.error.HTTPError as e:
        # ★ 2026-10-16 加：ComfyUI 的 400 里带着 node_errors，不读出来等于什么都没量
        体 = e.read().decode("utf-8", "replace")
        print("✗ 提交被拒 HTTP %s" % e.code)
        print(体[:6000])
        raise


def 取历史(服务, pid):
    with urllib.request.urlopen(f"{服务}/history/{pid}", timeout=120) as r:
        return json.load(r)


def 主():
    解析命令行()
    服务 = H.端点(端点名)
    os.makedirs(出, exist_ok=True)

    首 = os.path.join(目, "01_格%d.png" % 格号)
    末 = os.path.join(目, "末帧", "末_格%d.png" % 格号)
    中 = [os.path.join(目, "02_中%d_%d.png" % (格号, k)) for k in (1, 2, 3)]
    if 模式 == "半A":
        首, 末, 中 = 首, 中[1], [中[0]]
    elif 模式 == "半B":
        首, 末, 中 = 中[1], 末, [中[2]]
    料 = [首, 末] + 中
    print("═" * 66)
    print("试多关键帧　格%d　%s　%d 帧（%.3f 秒）　%s　锚点位 %s"
          % (格号, 模式, 帧数, 帧数 / 24.0, 端点名, 位们[:len(中)]))
    print("═" * 66)
    for p in 料:
        if not os.path.isfile(p):
            print("✗ 缺素材：%s" % p)
            return 1
        print("  ✓ %9d B  %s" % (os.path.getsize(p), os.path.basename(p)))

    动 = H.读动态("楚子航")
    格 = H.读格("楚子航")

    def _取(d, k, 键):
        v = d.get(k)
        if v is None:
            return ""
        if isinstance(v, dict):
            return v.get(键, "") or ""
        return str(v)

    动作 = _取(动, 格号, "动作") or _取(动, 格号, "") or _取(格, 格号, "动作")
    光 = _取(格, 格号, "光色") or _取(格, 格号, "光")
    if not 动作:
        print("✗ 没取到格%d 的动作（读动态/读格 的结构不是我猜的那样）" % 格号)
        return 1

    台词 = "楚子航开口说中文：「站台尽头有东西。」能清楚听见他说这句话。"
    词 = "%s。环境：%s。%s。%s" % (动作, 光, 台词, 词尾)
    print()
    print("── 词（%d 字）──" % len(词))
    print("  " + 词[:400] + ("…" if len(词) > 400 else ""))

    print()
    print("── 传 %d 张图 ──" % (2 + len(中)))
    名 = {}
    要传 = [("首", 首), ("末", 末)] + [("中%d" % (k + 1), p) for k, p in enumerate(中)]
    for 键, p in 要传:
        名[键] = H.传图(服务, p)
        print("  ✓ %s %s → %s" % (键, os.path.basename(p), 名[键]))

    中名 = [名["中%d" % (k + 1)] for k in range(len(中))]
    图 = 建图多(名["首"], 中名, 名["末"], 词, 种子, "shiduo")
    print()
    print("── 图里有 %d 个节点：%s" % (len(图), ", ".join(sorted(图, key=int))))

    起 = time.time()
    回 = 提交(服务, 图)
    if "prompt_id" not in 回:
        print("✗ 提交被拒：%s" % json.dumps(回, ensure_ascii=False)[:3000])
        return 1
    pid = 回["prompt_id"]
    print("  ✓ 已提交 prompt_id=%s" % pid)

    上次 = 0
    while True:
        time.sleep(10)
        过 = time.time() - 起
        if 过 - 上次 >= 60:
            上次 = 过
            try:
                with urllib.request.urlopen(f"{服务}/queue", timeout=30) as r:
                    队 = json.load(r)
                print("  … %5.1f 分　跑 %d 排 %d" % (过 / 60.0, len(队.get("queue_running", [])),
                                                    len(队.get("queue_pending", []))))
            except Exception:
                print("  … %5.1f 分" % (过 / 60.0))
        h = 取历史(服务, pid)
        if pid in h:
            break
        if 过 > 3600:
            print("✗ 超 60 分钟还没出")
            return 1

    耗时 = time.time() - 起
    e = h[pid]
    状 = e.get("status", {})
    print()
    print("── 完了　%.1f 秒 = %.1f 分" % (耗时, 耗时 / 60.0))
    print("   status: %s" % json.dumps(状, ensure_ascii=False)[:800])
    if 状.get("status_str") == "error" or not 状.get("completed", True):
        for m in 状.get("messages", [])[-6:]:
             print("   ! %s" % json.dumps(m, ensure_ascii=False)[:600])
        return 1

    件 = []
    for _, v in (e.get("outputs") or {}).items():
        for g in v.get("gifs", []) + v.get("videos", []):
            件.append(g)
    print("   产物 %d 个" % len(件))
    for g in 件:
        print("     %s" % json.dumps(g, ensure_ascii=False)[:400])
        q = ("%s/view?filename=%s&subfolder=%s&type=%s"
             % (服务, urllib.parse.quote(g["filename"]),
                urllib.parse.quote(g.get("subfolder", "")), g.get("type", "output")))
        with urllib.request.urlopen(q, timeout=600) as r:
            体 = r.read()
        落 = os.path.join(出, "格%d_%s_%d帧.mp4" % (格号, 模式, 帧数))
        open(落, "wb").write(体)
        print("  ✓ 落盘 %s　%d B" % (落, len(体)))
    return 0


if __name__ == "__main__":
    sys.exit(主())
