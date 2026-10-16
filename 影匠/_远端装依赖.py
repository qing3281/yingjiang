# -*- coding: utf-8 -*-
import os
import subprocess
import sys

基础 = r"E:\影匠AI\ComfyUI"

候选 = [
    os.path.join(基础, "python_embeded", "python.exe"),
    os.path.join(基础, ".venv", "Scripts", "python.exe"),
    os.path.join(基础, "venv", "Scripts", "python.exe"),
]
Py = None
for c in 候选:
    if os.path.exists(c):
        Py = c
        break

print("=== ComfyUI 目录 ===")
print("  %s  存在=%s" % (基础, os.path.isdir(基础)))
if os.path.isdir(基础):
    for d in sorted(os.listdir(基础))[:25]:
        print("    %s" % d)

print("\n=== Python ===")
print("  找到：%s" % Py)
if not Py:
    sys.exit(1)

r = subprocess.run([Py, "-c", "import sys;print(sys.version)"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("  " + (r.stdout or r.stderr).strip())

包 = ["opencv-python", "imageio-ffmpeg", "diffusers", "deepdiff", "py-cpuinfo",
      "piexif", "colour-science", "scikit-image", "timm", "transparent-background",
      "ultralytics", "einops", "safetensors", "accelerate", "matplotlib",
      "scipy", "av", "soundfile", "kornia", "spandrel"]

print("\n=== pip 装依赖（%d 个）===" % len(包))
r = subprocess.run([Py, "-m", "pip", "install", "-q", "-i",
                    "https://pypi.tuna.tsinghua.edu.cn/simple"] + 包,
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=3600)
print("  退出码 %d" % r.returncode)
尾 = ((r.stderr or "") + (r.stdout or "")).strip()
print("  " + (尾[-1200:].replace("\n", "\n  ") if 尾 else "（无输出）"))

print("\n=== 复查关键包 ===")
for m in ["cv2", "diffusers", "skimage", "timm", "einops", "soundfile", "av", "torch"]:
    r = subprocess.run([Py, "-c", "import %s;print(getattr(%s,'__version__','?'))" % (m, m)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    v = (r.stdout or r.stderr).strip().splitlines()
    print("  %-12s %s" % (m, v[-1] if v else "?"))
