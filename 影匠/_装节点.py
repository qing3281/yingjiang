# -*- coding: utf-8 -*-
"""把 WF 整合包里最要紧的几个自定义节点装进本机 ComfyUI。

为什么挑这些：用户的三条抱怨
  ① 「动作还是不连贯」   → comfyui-minimax-h3-audio-T8 的 Motion Quality / DualClockSampler
                          + comfyui-frame-interpolation（补帧，把 16fps 补到 32/48）
  ② 「一镜里还是像看图片」→ 同上补帧 + MiniMax-H3 原生运动（不是把静帧推近拉远）
  ③ 「前后衔接有问题」   → MiniMax-H3 的 flf2v（首尾帧）+ MultiKeyframe
另外 comfyui-videohelpersuite 是所有 WF 工作流都要的（VHS_VideoCombine）。

**不做的事**：不装全部 92 个。装得多不等于跑得动，装的每一个都可能把
现在能跑的 ComfyUI 弄挂。先装这批，重启验完再决定要不要加。
"""
import os
import shutil
import subprocess
import sys

取出 = (r"D:\DSHworkspace\影匠\_网盘整理\取出\02_WF整合包_2026.9.28（不含模型）"
        r"\Comfyui-WF-2026.8.8\ComfyUI\custom_nodes")
目标 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes"
py = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

要的 = [
    # 核心：T8 节点包（运动质量 / 双时钟采样 / AV 解码 / 语音 / 多关键帧）
    "comfyui-minimax-h3-audio-T8",
    "comfyui-minimax-h3-blockcache-T8",
    "ComfyUI-MiniMaxH3-AVCache-CN",
    "ComfyUI-YCNodes-MiniMax-H3",
    # 视频合成（WF 工作流全都要 VHS_VideoCombine）
    "comfyui-videohelpersuite",
    # 补帧 —— 直接对着「像看图片」「动作不连贯」
    "comfyui-frame-interpolation",
    "ComfyUI-GIMM-VFI",
    "ComfyUI-VFI",
    # 常用依赖（工作流里的杂项节点）
    "rgthree-comfy", "ComfyMath", "ComfyUI-EulerDiscreteScheduler",
    "cg-use-everywhere", "comfyui-custom-scripts", "ComfyUI-Crystools",
    "comfyui-kjnodes", "comfyui_essentials", "ComfyUI_StringOps",
    "ComfyUI-Various" if os.path.isdir(os.path.join(取出, "ComfyUI-Various")) else "comfyui-various",
    # 画质
    "comfyui-impact-pack", "comfyui-impact-subpack",
    "comfyui-inpaint-nodes",
]

干 = "--真做" not in sys.argv

装了 = []
for 名 in 要的:
    源 = os.path.join(取出, 名)
    if not os.path.isdir(源):
        print(f"  ✗ 源里没有：{名}")
        continue
    去 = os.path.join(目标, 名)
    if os.path.isdir(去):
        print(f"  – 已装：{名}")
        continue
    n = sum(len(f) for _, _, f in os.walk(源))
    print(f"  {名:44s} {n:6d} 文件")
    if not 干:
        shutil.copytree(源, 去, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
        装了.append(名)

if 干:
    print(f"\n（干跑，没动。加 --真做 才装）要装 {len(要的)} 个")
    sys.exit(0)

print(f"\n装了 {len(装了)} 个，装依赖……")

# 收集 requirements
包 = set()
for 名 in 装了:
    r = os.path.join(目标, 名, "requirements.txt")
    if os.path.isfile(r):
        for 行 in open(r, encoding="utf-8", errors="replace"):
            行 = 行.split("#")[0].strip()
            if 行 and not 行.startswith("-"):
                包.add(行)
# 本机实测缺的
包 |= {"opencv-python", "imageio-ffmpeg", "diffusers", "deepdiff", "py-cpuinfo", "piexif"}
print("  要装的：", " ".join(sorted(包)))
r = subprocess.run([py, "-m", "pip", "install", "-q",
                    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", *sorted(包)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print(f"  pip 退出码 {r.returncode}")
if r.stdout:
    print("  " + r.stdout.strip()[-1500:])
if r.stderr:
    print("  " + r.stderr.strip()[-1500:])
