# -*- coding: utf-8 -*-
"""《楚子航》长片：一次生成跑完整条 —— 插件自带的「长视频内循环 + Prompt Relay」。

为什么要换掉「128 小段各自生成再 ffmpeg 拼」：
  插件自己的文档写得很清楚（examples/workflows/14-prompt-relay/README.md 第 27 行）：
  「全局人物、环境、风格、**镜头连续性**和整体声音写到 global_prompt」，
  再由局部事件按时间段生效 —— 连贯性是在**一次生成**里靠全局提示词 + 注意力补丁保证的。
  04-long-video/README.md：`In_Node_Long_Video_Loop_*` 一次排队、在同一个输出节点内
  严格串行跑完整条，段与段之间传**真实的上下文帧**（不是拼文件），原子落盘、断了能续。
  ★ 我原来那套 = 用剪贴板解决一个本该「一次生成」解决的问题。

节点入参名与顺序是从 /object_info 拉的（`_查长视频节点.py`），不是猜的。

用法：
  python _出连片.py --试            # 20 秒小样（4 段），先量时间和显存
  python _出连片.py --总秒 300      # 全片
  python _出连片.py --看图          # 只打印要发的图，不提交（免费）
"""
import os, re, sys, json, time, uuid, shutil, argparse, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")

import _出H3 as H

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
出 = r"D:\DSHworkspace\_出连片"

# ── 模型（沿用生产里跑通 32 格的那套）────────────────────────────
UNET = "minimax_h3_fl2va_int8_convrot.safetensors"
LORA = "minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors"
CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VVAE = "minimax_h3_video_vae_fp16.safetensors"
AVAE = "minimax_h3_audio_vae_fp32.safetensors"

步数 = 8              # Turbo LoRA 的步数
帧率 = 24
宽, 高 = 736, 416    # ★ 官方示例的分辨率。上次写 1344,768 是 3.4 倍像素 → 实测 20 秒小样 40 分钟没跑完
渲染窗 = 124          # 节点下限就是 124
上下文帧 = 22         # 只接受 5 / 22 / 39
种子 = 1735946766


def 网格上(帧):
    """H3 的 17n+5 网格。不在网格上会被**悄悄**上吸附，所以自己先对齐。"""
    帧 = max(5, int(帧))
    return 帧 + ((5 - 帧) % 17)


# ── 全局提示词（按 14-prompt-relay 的写法：人物/环境/风格/镜头连续性/声音）──
全局词 = (
    "A single continuous cinematic take inside an abandoned Beijing subway station at night. "
    "Two people throughout: a tall young man in a long black leather coat with dark blue hair "
    "carrying a sword, and a girl in a navy sailor school uniform with a brown plaid skirt and "
    "long black hair. Keep the same faces, the same clothing and the same underground concrete "
    "platform, tiled walls, rails and rubble from the first frame to the last. "
    "The only light comes from handheld torches, a lighter, sparks and the faint glow at the "
    "tunnel mouth; every built-in ceiling lamp stays dead. "
    "The camera keeps a steady cinematic handheld feel, the same colour grade and the same "
    "realistic photographic style throughout. "
    "Ambience: dripping water, distant tunnel wind, footsteps on concrete, cloth movement and "
    "low rumble; no music."
)


def 各格词():
    """32 条局部事件词。

    ★ 只写「这一格发生什么」，**不重复环境**。
    环境/人物/风格/镜头连续性已经写在 `全局词` 里了 —— 这正是 14-prompt-relay
    的做法：全局词管不变的东西，局部词只管这一段发生了什么。
    原来把 02-九宫格.md 里那段三百多字的「场景光」原样贴 32 遍，
    既是 `_总检查.py` 一直在报的「公共段落塞进不该有的东西」，也白烧 token。
    """
    动 = H.读动态("楚子航")
    格 = H.读格("楚子航")
    词们 = []
    for 号 in range(1, 33):
        动作 = (动.get(号) or 格.get(号, {}).get("动作") or "轻微的自然动作").strip()
        动作 = re.sub(r"\s+", "", 动作)
        词们.append(动作 if 动作.endswith("。") else 动作 + "。")
    return 词们


# ── 建图（API 格式）─────────────────────────────────────────────
def 建图(首图名, 本秒, 词们, 链号, 前缀):
    总帧 = 网格上(本秒 * 帧率)
    起止 = []
    每 = 总帧 // len(词们)
    左 = 0
    for i in range(len(词们)):
        右 = 总帧 - 1 if i == len(词们) - 1 else 左 + 每 - 1
        起止.append(f"{左}-{右}")
        左 = 右 + 1

    图 = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": CLIP, "type": "minimax", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VVAE}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": AVAE}},
        "5": {"class_type": "LoraLoaderBypassModelOnly",
              "inputs": {"model": ["1", 0], "lora_name": LORA, "strength_model": 1.0}},
        # 一条覆盖整条视频的全局时间线（NOTE 1：Plan 只建一次）
        "6": {"class_type": "MiniMaxH3PromptRelayPlanT8Advanced",
              "inputs": {"global_prompt": 全局词,
                         "local_prompts": "\n".join(词们),
                         "length": 总帧,
                         "timing_mode": "auto_equal",
                         "time_ranges": "\n".join(起止),
                         "math_profile": "paper_v1",
                         "epsilon": 0.1,
                         "allow_gaps": False,
                         "allow_overlaps": False}},
        "7": {"class_type": "LoadImage", "inputs": {"image": 首图名, "upload": "image"}},
        "8": {"class_type": "MiniMaxH3LongVideoInNodeLoopEffectsT8Advanced",
              "inputs": {
                  "model": ["5", 0], "clip": ["2", 0],
                  "video_vae": ["3", 0], "audio_vae": ["4", 0],
                  "prompt_relay_plan": ["6", 0],
                  "first_frame": ["7", 0],
                  "persistent_identity_image": ["7", 0],
                  "chain_id": 链号,
                  "total_duration_seconds": float(本秒),
                  "width": 宽, "height": 高,
                  "render_window_frames": 渲染窗,
                  "context_frames": 上下文帧,
                  "global_prompt": "",            # 用了 Relay 就留空（NOTE 1）
                  "segment_prompts_json": "",
                  "prompt_relay_mode": "apply_exp",
                  "query_chunk_rows": 256,
                  "eav_mode": "disabled",
                  "eav_tau": 4.0, "eav_start_video_progress": 0.15,
                  "eav_end_video_progress": 0.9, "eav_max_workspace_mib": 32,
                  "eav_g_hard_limit": 1.5,
                  "minimum_free_vram_mib": 512,
                  "base_seed": 种子, "seed_policy": "increment",
                  "steps": 步数,
                  "shift_video": 12.0, "shift_audio": 3.0,
                  "sampler_name": "dual_clock_euler", "scheduler": "native_flow",
                  "task_type": "auto", "context_audio": "video_and_audio",
                  "audio_mode": "native", "audio_denoise_strength": 0.35,
                  "add_source_as_reference": True,
                  "prompt_primary_audio_ordinal": 0,
                  "strict_prompt_tags": True,
                  "ref_image_size": "match",
                  "reference_video_policy": "official_2_to_15s",
                  "first_frame_reuse": "segment0_only",
                  "persistent_identity_strategy": "single_reference",
                  "persistent_identity_interval": 1,
                  "resume_existing": True,
                  "filename_prefix": 前缀,
                  "audio_seam_policy": "cosine_bridge",
                  "bridge_ms": 5.0,
                  "bit_depth": 8, "crf": 18,
                  "model_id": "minimax_h3_fl2va_int8_convrot+turbo4",
              }},
    }
    return 图, 总帧


def 提交(服务, 图):
    r = urllib.request.Request(
        f"{服务}/prompt",
        data=json.dumps({"prompt": 图, "client_id": "chulianpian"}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(r, timeout=180))
    except urllib.error.HTTPError as e:
        体 = e.read().decode("utf-8", "replace")
        print("✗ 提交被拒 HTTP %s" % e.code)
        print(体[:8000])
        raise


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--试", action="store_true", help="20 秒小样（4 段）")
    ap.add_argument("--秒", type=float, default=None, help="总时长秒")
    ap.add_argument("--端点", default="远端")
    ap.add_argument("--看图", action="store_true", help="只打印要发的图，不提交")
    a = ap.parse_args()

    本秒 = a.秒 if a.秒 else (20.0 if a.试 else 300.0)
    词们 = 各格词()
    if 本秒 < 300:
        段数 = max(2, int(round(本秒 / (300.0 / 32))))
        词们 = 词们[:段数]

    服务 = H.端点(a.端点)
    首路 = os.path.join(目, "01_格1.png")
    if not os.path.isfile(首路):
        print("✗ 找不到首帧 %s" % 首路)
        return 1
    os.makedirs(出, exist_ok=True)

    链号 = "chuzihang_%s" % time.strftime("%Y%m%d_%H%M%S")
    前缀 = "H3_连片_%s" % time.strftime("%m%d_%H%M")

    print("=" * 66)
    print("端点      %s  %s" % (a.端点, 服务))
    print("总时长    %.1f 秒" % 本秒)
    print("局部事件  %d 段" % len(词们))
    print("首帧      %s" % 首路)
    print("链号      %s" % 链号)

    if a.看图:
        for i, w in enumerate(词们, 1):
            print("  %2d. %s" % (i, w))
        return 0

    名 = H.传图(服务, 首路)
    图, 总帧 = 建图(名, 本秒, 词们, 链号, 前缀)
    print("总帧      %d（17n+5 网格上）" % 总帧)
    print("渲染窗    %d 帧 / 上下文 %d 帧 → 约 %d 段"
          % (渲染窗, 上下文帧, max(1, (总帧 + 渲染窗 - 上下文帧 - 1) // (渲染窗 - 上下文帧))))
    print("=" * 66)

    起 = time.time()
    回 = 提交(服务, 图)
    号 = 回.get("prompt_id")
    if not 号:
        print("✗ 没拿到 prompt_id：%s" % 回)
        return 1
    print("✓ 已排队　prompt_id=%s" % 号)

    # ? 内循环节点自己跑完整条才返回，所以这里就是等
    for i in range(2880):          # 最长 8 小时
        time.sleep(10)
        try:
            with urllib.request.urlopen(f"{服务}/history/{号}", timeout=60) as r:
                史 = json.load(r)
        except Exception:
            continue
        if 号 not in 史:
            if i % 6 == 0:
                print("  …跑了 %.0f 分" % ((time.time() - 起) / 60))
            continue
        条 = 史[号]
        态 = 条.get("status", {})
        if 态.get("status_str") == "error" or not 态.get("completed", True):
            for m in 态.get("messages", []):
                if m and m[0] in ("execution_error", "execution_interrupted"):
                    print("✗ 执行出错：%s" % json.dumps(m[1], ensure_ascii=False)[:3000])
            return 1
        出们 = 条.get("outputs", {})
        print("✓ 跑完，用时 %.1f 分" % ((time.time() - 起) / 60))
        for 节点号, 内容 in 出们.items():
            for k, v in 内容.items():
                print("  节点%s.%s = %s" % (节点号, k, json.dumps(v, ensure_ascii=False)[:600]))
        return 0
    print("✗ 超时（8 小时）")
    return 1


if __name__ == "__main__":
    sys.exit(主())
