# -*- coding: utf-8 -*-
r"""把几格的「第一帧」和「最后一帧」并排拼出来 —— 看它到底冻没冻。

─ 为什么要这一步 ─────────────────────────────────────────────
`影匠\_量运动.py` 的说明里自己写着：

    这个数**只说明「像素变了多少」，不说明「变的是不是有意义」** …
    所以它只能用来**筛出冻住的格子**，不能反过来当「动得好」的证据。

2026-10-15 07:58 数出来《雪线》的「极远景」中位只有 0.216，看着像冻住了。
**但 160px 宽的雪原上一颗小黑点在走，像素本来就变不了几个** ——
数低有两种可能：①真冻了 ②场面太大、主体太小，这把尺量不出来。
**光看数字分不开这两样。所以去看画面。**

用法：python _看首尾帧.py 雪线 13,14,15,26,35,36
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace\影匠"
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")

戏 = (sys.argv[1] if len(sys.argv) > 1 else "雪线").strip()
格号 = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else []

段 = os.path.join(根, "作品", 戏, "段")
出图目录 = os.path.join(根, "作品", 戏, "_首尾帧")
os.makedirs(出图目录, exist_ok=True)


def 时长(路):
    # ★ `_bin` 里只有 ffmpeg.exe、没有 ffprobe.exe —— 别去 import ffprobe。
    #   时长从 `ffmpeg -i` 打到 stderr 的 "Duration: 00:00:04.10" 里抠。
    r = subprocess.run([FFMPEG, "-i", 路], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


小块 = []
for 号 in 格号:
    路 = os.path.join(段, f"格{号:02d}.mp4")
    if not os.path.isfile(路):
        候选 = [p for p in os.listdir(段) if p.startswith(f"格{号}_") or p == f"格{号}.mp4"]
        if not 候选:
            print(f"  ✗ 格{号} 找不到片子")
            continue
        路 = os.path.join(段, 候选[0])

    d = 时长(路)
    首 = os.path.join(出图目录, f"格{号:02d}_首.png")
    尾 = os.path.join(出图目录, f"格{号:02d}_尾.png")
    for 目标, 时刻 in ((首, 0.02), (尾, max(0.02, d - 0.12))):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{时刻:.3f}",
                        "-i", 路, "-frames:v", "1", 目标], capture_output=True)

    if not (os.path.exists(首) and os.path.exists(尾)):
        print(f"  ✗ 格{号} 抽帧失败")
        continue

    # 首尾并排 → 「第几格」三个字烧进像素里（不许有需要推断的东西）
    条 = os.path.join(出图目录, f"条_格{号:02d}.png")
    subprocess.run([
        FFMPEG, "-y", "-v", "error",
        "-i", 首, "-i", 尾,
        "-filter_complex",
        f"[0:v]scale=440:-2,pad=iw:ih+34:0:34:color=0x14161a,"
        f"drawtext=text='格{号}  FIRST':fontcolor=0x8ad4a0:fontsize=22:x=6:y=6[a];"
        f"[1:v]scale=440:-2,pad=iw:ih+34:0:34:color=0x14161a,"
        f"drawtext=text='格{号}  LAST  ({d:.1f}s)':fontcolor=0xe8b45a:fontsize=22:x=6:y=6[b];"
        f"[a][b]hstack=inputs=2",
        "-frames:v", "1", 条], capture_output=True)

    if os.path.exists(条):
        小块.append(条)
        print(f"  ✓ 格{号:<3} 时长 {d:>4.1f}s")

# 竖着摞成一张
# ★ 不能用 concat 解复用器 —— 各条高度不完全一样时它只出第一条就静默停了
#   （2026-10-15 08:02 实测：6 条只出来 1 条）。用 vstack 显式吃全部输入。
# ★★ `vstack=inputs=1` 会直接报错、**一个字节都不写**，而旧文件还在原地 ——
#   于是「跑成功了」和「文件是上一次的」长得一模一样。所以这里两件事都要做：
#   ① 只有 1 条时直接拷，不走 vstack；② 写完必须比 mtime，证明是这次写的。
if 小块:
    总 = os.path.join(根, "作品", 戏, f"_首尾帧对比.png")
    前 = os.path.getmtime(总) if os.path.exists(总) else 0.0
    if len(小块) == 1:
        shutil.copy2(小块[0], 总)
    else:
        入 = []
        for p in 小块:
            入 += ["-i", p]
        滤 = "".join(f"[{i}:v]" for i in range(len(小块))) + f"vstack=inputs={len(小块)}"
        r = subprocess.run([FFMPEG, "-y", "-v", "error", *入,
                            "-filter_complex", 滤, "-frames:v", "1", 总],
                           capture_output=True, text=True, errors="replace")
        if r.returncode != 0:
            print(f"\n  ✗ 拼图失败（{len(小块)} 条）：{(r.stderr or '').strip()[:200]}")
    后 = os.path.getmtime(总) if os.path.exists(总) else 0.0
    if 后 > 前:
        print(f"\n  ✓ {总}　{os.path.getsize(总):,} B　{len(小块)} 行　（这次写的）")
    else:
        print(f"\n  ✗ {总} 的时间戳没动 —— 这是上一次留下的旧图，别看它")
