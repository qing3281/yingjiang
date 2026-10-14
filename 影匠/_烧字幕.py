# -*- coding: utf-8 -*-
"""把 SRT 烧进画面（硬字幕）。

为什么要烧进画面，而不是挂软字幕轨：用户要的是「发出去别人直接能看」，
软字幕轨在微信/QQ/手机相册里默认不显示，等于没有。

用法：
    python _烧字幕.py 片.mp4                   # 同名 _字幕.mp4，自动找同目录的 _台词.srt
    python _烧字幕.py 片.mp4 --srt 台词.srt
    python _烧字幕.py 片.mp4 --字号 26 --边距 34 --字体 "微软雅黑"
    python _烧字幕.py 片.mp4 --只数字幕             # 只输出 srt，不烧

踩过的坑（写在这里省得再踩）：
1. **filter 里 Windows 路径要把冒号转义成 `\\:`，反斜杠要换成 `/`。**
   直接写 `subtitles=D:\\a\\b.srt` 会被 ffmpeg 的 filter 语法当成参数分隔，
   报 `No option name near ...`，而且报错完全看不出是路径问题。
2. **`force_style` 里的颜色是 `&HAABBGGRR`（BGR 顺序，不是 RGB）**，
   写反了白字会变蓝。`&H00FFFFFF` 是白，`&H00000000` 是黑。
3. **字号是相对视频高度的**（脚本高度 = 视频高度），
   1344×768 用 22–26 合适；同一套参数换到 720p 会显小。
4. **中文字体名必须是系统里真有的**。写不存在的字体名 ffmpeg 不报错，
   直接回落成默认字体，中文可能变方框。这里默认「微软雅黑」。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))


def 找ffmpeg():
    """优先用项目里的 _bin\\ffmpeg.exe，没有再退回 PATH。"""
    本 = os.path.join(根, "_bin", "ffmpeg.exe")
    if os.path.exists(本):
        return 本
    return shutil.which("ffmpeg") or "ffmpeg"


def 转滤镜路径(路):
    """ffmpeg filter 里的路径：反斜杠→正斜杠，冒号→\\:，单引号→\\'。"""
    p = os.path.abspath(路).replace("\\", "/")
    p = p.replace(":", "\\:").replace("'", "\\'")
    return p


def 探时长(ff, 路):
    """读时长。

    ★ 这里原来是调 ffprobe 的，`ff.replace("ffmpeg","ffprobe")` —— 而 `_bin\\` 下
    **只有 ffmpeg.exe，没有 ffprobe.exe**。于是 subprocess 抛异常被吞掉，函数
    返回 0.0，两个 0.0 相减等于 0，**那个「时长差 > 0.5 秒就报错」的检查
    就变成了一个永远说 OK 的检查**。第一次跑就撞上了：打印 `0.00 秒 → 0.00 秒`，
    看着像通过，其实什么都没量。
    改成直接问 ffmpeg（`-i` 会把 Duration 打到 stderr），不依赖 ffprobe。
    """
    try:
        r = subprocess.run([ff, "-i", 路, "-hide_banner"],
                           capture_output=True, text=True, errors="replace")
        m = re.search(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d{1,3})", r.stderr or "")
        if not m:
            return 0.0
        h, mi, s, ms = m.groups()
        return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
    except Exception:  # noqa: BLE001
        return 0.0


def 数条目(srt路):
    """数 srt 里有多少条字幕（按「行号 + 时间行」的成对结构数）。"""
    文 = open(srt路, encoding="utf-8-sig", errors="replace").read()
    return len(re.findall(r"^\s*\d+\s*\n\s*\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->", 文, flags=re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("片")
    ap.add_argument("--srt", default="")
    ap.add_argument("--出", default="")
    ap.add_argument("--字体", default="微软雅黑")
    ap.add_argument("--字号", type=int, default=24)
    ap.add_argument("--边距", type=int, default=30, help="距底部像素")
    ap.add_argument("--描边", type=int, default=2)
    ap.add_argument("--只数字幕", action="store_true")
    参 = ap.parse_args()

    片 = os.path.abspath(参.片)
    if not os.path.exists(片):
        print(f"✗ 找不到片子：{片}")
        return 1

    srt = 参.srt
    if not srt:
        候选 = [os.path.join(os.path.dirname(片), "_台词.srt"),
                os.path.splitext(片)[0] + ".srt"]
        srt = next((c for c in 候选 if os.path.exists(c)), "")
        if not srt:
            # 往下找一层（配音目录里）
            基 = os.path.dirname(片)
            for 子 in ("配音", "片"):
                p = os.path.join(基, 子, "_台词.srt")
                if os.path.exists(p):
                    srt = p
                    break
    if not srt or not os.path.exists(srt):
        print("✗ 没找到 srt（用 --srt 指定）")
        return 1
    srt = os.path.abspath(srt)

    n = 数条目(srt)
    print(f"字幕：{srt}")
    print(f"  {n} 条　{os.path.getsize(srt):,} B")
    if n == 0:
        print("✗ srt 里一条都没解析出来，先看格式对不对")
        return 1
    if 参.只数字幕:
        return 0

    ff = 找ffmpeg()
    出 = 参.出 or os.path.join(
        os.path.dirname(片),
        os.path.splitext(os.path.basename(片))[0] + "_字幕.mp4")

    样式 = (f"FontName={参.字体},FontSize={参.字号},"
            f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            f"BorderStyle=1,Outline={参.描边},Shadow=0,"
            f"Alignment=2,MarginV={参.边距}")
    vf = f"subtitles='{转滤镜路径(srt)}':force_style='{样式}'"

    命令 = [ff, "-y", "-i", 片, "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", 出]
    print(f"\n烧字幕 → {os.path.basename(出)}")
    r = subprocess.run(命令, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(f"✗ ffmpeg 退出码 {r.returncode}")
        # 只打最后几行，前面全是无用的版本信息
        for 行 in (r.stderr or "").strip().splitlines()[-8:]:
            print("   ", 行)
        return 1

    if not os.path.exists(出):
        print("✗ ffmpeg 说成功但文件不在，别信")
        return 1

    原秒, 新秒 = 探时长(ff, 片), 探时长(ff, 出)
    print(f"  ✓ {os.path.getsize(出)/1048576:.2f} MB　"
          f"{原秒:.2f} 秒 → {新秒:.2f} 秒")
    if abs(原秒 - 新秒) > 0.5:
        print(f"  ⚠ 时长差了 {abs(原秒-新秒):.2f} 秒 —— 正常应该只差一帧以内，查一下")
        return 1
    print(f"\n✓ 硬字幕成片：{出}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
