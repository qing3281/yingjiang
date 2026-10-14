# -*- coding: utf-8 -*-
r"""出一条「超分前 / 超分后」左右并排的对比 mp4（P0③ 要的就是这个）。

左边：原片 1280×704　右边：超分结果 2560×1408
两边都缩到 960×528 再并排（总 1920×528），这样对比是公平的 —— 播放器不会
因为一边像素多就把它渲染得更清楚。音轨用超分那条（原片和超分是同一段声音）。

★ 两个坑：
1. `drawtext` 在 Windows 上不吃字体名，只吃 `fontfile=`，而字体路径里的 `C:` 冒号
   在 filtergraph 里要转义。**绕法：把字体拷到一个目录，把工作目录设成那里，写相对文件名。**
2. 命令行里带中文，别用 pwsh 拼字符串 —— 用 Python 的 subprocess 传列表，一个字节都不动。

用法：python _拼超分对比mp4.py
"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

FFMPEG = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
试 = r"D:\DSHworkspace\影匠\作品\_超分试验"
原 = os.path.join(试, "觉醒_开头12s_原片.mp4")
超 = os.path.join(试, "觉醒开头12s_1440p_有声.mp4")
出 = os.path.join(试, "对比_觉醒开头12s.mp4")

字体夹 = r"D:\DSHworkspace\_字体"
os.makedirs(字体夹, exist_ok=True)
for n in ("msyh.ttc", "msyhbd.ttc"):
    src = os.path.join(r"C:\Windows\Fonts", n)
    if os.path.isfile(src):
        shutil.copy2(src, os.path.join(字体夹, n))

for p in (原, 超):
    if not os.path.isfile(p):
        print(f"  ✗ 缺文件：{p}")
        sys.exit(1)

def 签(字):
    return (
        f"drawtext=fontfile=msyhbd.ttc:text='{字}':x=16:y=14:fontsize=28:"
        f"fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10"
    )

滤 = (
    f"[0:v]scale=960:528:flags=lanczos,setsar=1,{签('超分前  1280x704')}[l];"
    f"[1:v]scale=960:528:flags=lanczos,setsar=1,{签('超分后  2560x1408')}[r];"
    f"[l][r]hstack=inputs=2[v]"
)

命令 = [
    FFMPEG, "-hide_banner", "-v", "error", "-y",
    "-i", 原, "-i", 超,
    "-filter_complex", 滤,
    "-map", "[v]", "-map", "1:a:0",
    "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "160k", "-shortest",
    "-movflags", "+faststart",
    os.path.basename(出),
]

r = subprocess.run(命令, cwd=字体夹, capture_output=True, text=True, errors="replace")
if r.returncode != 0:
    print("  ✗ ffmpeg 失败：")
    print("   ", (r.stderr or "").strip()[:1200])
    sys.exit(1)

# ffmpeg 写在了字体夹里（因为 cwd），搬回来
临时 = os.path.join(字体夹, os.path.basename(出))
if os.path.isfile(临时):
    shutil.move(临时, 出)

print(f"  ✓ {出}")
print(f"    {os.path.getsize(出):,} B　{os.path.getsize(出) / 1024 / 1024:.2f} MB")

探 = subprocess.run(
    [FFMPEG, "-hide_banner", "-i", 出], capture_output=True, text=True, errors="replace")
for 行 in (探.stderr or "").splitlines():
    if "Duration" in 行 or "Stream #" in 行:
        print("   ", 行.strip())
