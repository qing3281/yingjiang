# -*- coding: utf-8 -*-
"""_寄官方片.py —— 把官方路线那条成片压一份手机版，寄到 2821719816@qq.com。

配方照抄 `影匠\\作品\\楚子航\\_守成片2.py:78-118` 的 `发信()`（能用就用、能抄就抄，不重写）：
  超过邮箱上限（48 MB）就 `ffmpeg -vf scale=960:-2 -crf 26 -preset medium -c:a aac -b:a 96k` 压一份手机版，
  再调 `B站\\制作\\寄邮件.py --主题 ... --正文 ... --大附件 ...`。

用法：python _寄官方片.py           真的寄
      python _寄官方片.py --干跑      只压手机版，不寄
"""
import os
import sys
import json
import time
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

片目 = r"D:\DSHworkspace\影匠\作品\楚子航\片_官方"
成片 = os.path.join(片目, "楚子航_官方_成片_字幕.mp4")
手机版 = os.path.join(片目, "楚子航_官方_成片_字幕_手机版.mp4")
已寄 = os.path.join(片目, "_已寄.json")
FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
寄信 = r"D:\DSHworkspace\B站\制作\寄邮件.py"
收件 = "2821719816@qq.com"
上限 = 48 * 1024 * 1024

if not os.path.isfile(成片):
    print("✗ 成片不在：%s" % 成片)
    sys.exit(1)

print("成片 %s　%.1f MB" % (成片, os.path.getsize(成片) / 1048576))
附 = 成片
if os.path.getsize(成片) > 上限 - 8 * 1024 * 1024:
    print("· 超邮箱上限，压一份手机版（长边 960 / crf 26 / 96k）")
    r = subprocess.run([FF, "-y", "-v", "error", "-i", 成片,
                        "-vf", "scale=960:-2", "-c:v", "libx264", "-crf", "26",
                        "-preset", "medium", "-c:a", "aac", "-b:a", "96k", 手机版],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.isfile(手机版):
        print("✗ 压手机版失败：" + (r.stderr or "")[-500:])
        sys.exit(1)
    print("· 手机版 %.1f MB　%s" % (os.path.getsize(手机版) / 1048576, 手机版))
    附 = 手机版

if "--干跑" in sys.argv:
    print("（干跑，不寄）")
    sys.exit(0)

正文 = [
    "《楚子航》—— 换成 MiniMax 官方长片做法的那一版，见附件。",
    "",
    "和你之前看到的那一版最大的区别：不再是我把 128 个小片段拼起来，",
    "而是用插件自带的「长视频内循环 + Prompt Relay」：一次排队、71 个渲染窗",
    "在同一个输出节点里严格串行跑完，段与段之间传的是真实的上下文帧（不是拼文件）。",
    "",
    "四个数（都能量）：",
    "① 298.67 秒 = 32 格 × 9.3333 秒，一帧不差（7168 帧 @ 24fps）",
    "② 全片只有 1 处硬切（137.7 秒，一次换镜头）—— 上一版是每 2.33 秒一刀、共 127 刀",
    "③ 有语音：32 句人声混在 H3 自己的环境音上。验法是做减法：",
    "   Σ人声 ≈（混音 − 0.55×源片）/1.9，在 32 句的窗口里比别处响 14.2 倍",
    "④ 字幕 32/32 句，硬烧在画面里",
    "",
    "已知的不足：这一版画面是 736×416（官方示例的尺寸）。你说「清晰度不够之后再超分就行」——",
    "按上次实测折算（1 秒 720p ≈ 43 秒超分），这条 298.67 秒大概要 60 分钟上下，",
    "要跑我就跑。",
    "",
    "桌面「楚子航·官方版」双击直接看。",
]
r = subprocess.run([PY, "-X", "utf8", 寄信, "--主题", "《楚子航》官方长片做法版（4分59秒·有语音·硬字幕）",
                    "--正文", "\n".join(正文), "--大附件", 附],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
for x in (r.stdout or "").strip().splitlines()[-14:]:
    print("   " + x)
if r.returncode != 0:
    print("✗ 发信退出码 %d：%s" % (r.returncode, (r.stderr or "")[-500:]))
    sys.exit(1)
with open(已寄, "w", encoding="utf-8") as f:
    json.dump({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "附件": 附,
               "字节": os.path.getsize(附)}, f, ensure_ascii=False)
print("✓ 已寄出 → %s（附件 %s，%.1f MB）" % (收件, os.path.basename(附), os.path.getsize(附) / 1048576))
