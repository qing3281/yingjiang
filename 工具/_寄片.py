# -*- coding: utf-8 -*-
"""_寄片.py —— 把一条成片压一份手机版，寄到 2821719816@qq.com。**通用版**。

`_寄官方片.py` 是写死目标的那一版（成片路径、主题、正文全焊在里面）；
这一版全部走参数，免得每换一条片子就复制一份脚本。

配方照抄 `影匠\\作品\\楚子航\\_守成片2.py:78-118` 的 `发信()`（能用就用、能抄就抄）：
  超过邮箱上限（48 MB）就 `ffmpeg -vf scale=960:-2 -crf 26 -preset medium -c:a aac -b:a 96k`
  压一份手机版，再调 `B站\\制作\\寄邮件.py --主题 ... --正文 ... --大附件 ...`。

用法：
    python _寄片.py --片 <成片绝对路径> --主题 "<主题>" [--正文 <正文.md 或 .txt>]
                    [--手机版 <输出路径>] [--已寄 <记账 json>] [--干跑]

`--正文` 给一个文件路径时按 UTF-8 读进来当正文；不给就只发一句话。
`--干跑` 只压手机版、不寄。
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
寄信 = r"D:\DSHworkspace\B站\制作\寄邮件.py"
收件 = "2821719816@qq.com"
上限 = 48 * 1024 * 1024
留白 = 8 * 1024 * 1024


def 主():
    参 = argparse.ArgumentParser()
    参.add_argument("--片", required=True)
    参.add_argument("--主题", required=True)
    参.add_argument("--正文", default="")
    参.add_argument("--手机版", default="")
    参.add_argument("--已寄", default="")
    参.add_argument("--干跑", action="store_true")
    a = 参.parse_args()

    if not os.path.isfile(a.片):
        print("✗ 成片不在：%s" % a.片)
        return 1
    字节 = os.path.getsize(a.片)
    print("成片 %s　%.1f MB" % (a.片, 字节 / 1048576))

    附 = a.片
    if 字节 > 上限 - 留白:
        手 = a.手机版 or os.path.splitext(a.片)[0] + "_手机版.mp4"
        # ★ 目录可能还不存在 —— ffmpeg **不会**自己建，会报
        #   `Error opening output ...: No such file or directory`。（干跑时逮到的）
        if os.path.dirname(手):
            os.makedirs(os.path.dirname(手), exist_ok=True)
        print("· 超邮箱上限，压一份手机版（长边 960 / crf 26 / 96k）→ %s" % 手)
        r = subprocess.run([FF, "-y", "-v", "error", "-i", a.片,
                            "-vf", "scale=960:-2", "-c:v", "libx264", "-crf", "26",
                            "-preset", "medium", "-c:a", "aac", "-b:a", "96k", 手],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not os.path.isfile(手):
            print("✗ 压手机版失败：" + (r.stderr or "")[-500:])
            return 1
        print("· 手机版 %.1f MB" % (os.path.getsize(手) / 1048576))
        附 = 手
    else:
        print("· 没超上限，原件直接寄")

    if a.正文:
        if os.path.isfile(a.正文):
            正文 = open(a.正文, encoding="utf-8").read()
        else:
            正文 = a.正文
    else:
        正文 = "见附件。"

    if a.干跑:
        print("（干跑，不寄）")
        print("---- 主题 ----")
        print(a.主题)
        print("---- 正文（前 1200 字）----")
        print(正文[:1200])
        return 0

    r = subprocess.run([PY, "-X", "utf8", 寄信, "--主题", a.主题,
                        "--正文", 正文, "--大附件", 附],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for x in (r.stdout or "").strip().splitlines()[-16:]:
        print("   " + x)
    if r.returncode != 0:
        print("✗ 发信退出码 %d：%s" % (r.returncode, (r.stderr or "")[-500:]))
        return 1
    账 = a.已寄 or os.path.join(os.path.dirname(a.片), "_已寄.json")
    with open(账, "w", encoding="utf-8") as f:
        json.dump({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "片": a.片,
                   "附件": 附, "字节": os.path.getsize(附), "主题": a.主题},
                  f, ensure_ascii=False, indent=1)
    print("✓ 已寄出 → %s（附件 %s，%.1f MB）" % (收件, os.path.basename(附),
                                                os.path.getsize(附) / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(主())
