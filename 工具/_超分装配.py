# -*- coding: utf-8 -*-
"""_超分装配.py —— 把远端超分出来的无声素材，贴回音轨 + 在高分辨率上烧硬字幕。

**为什么不直接超分「已经烧好字幕的成片」**：
    超分节点把音轨丢了（老毛病），不管超哪一条都要 ffmpeg 贴回去；
    而字幕如果在 736×416 时就烧进像素、再被超分放大，字是「被放大的字」（发虚）；
    在 1472×832 上原生烧，字是真的 1472 宽的字。所以流程是：
        超分【混音版（无字幕）】 → 得到无声 2x → 贴回混音版的音轨 + 原生烧字幕

字幕样式按分辨率缩放：`_接子镜.烧()` 在 736 宽上用 FontSize=22 / MarginV=36 / Outline=3，
这里按 `宽/736` 等比放大，保证画面上字的相对大小、位置、描边粗细和原来一样。

用法：
    python _超分装配.py --超分 <2x无声mp4> --音源 <带人声的mp4> --srt <srt> --出 <输出mp4>
"""
import os
import sys
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
基准宽 = 736


def 尺寸(路):
    r = subprocess.run([FF, "-hide_banner", "-i", 路], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    for l in (r.stderr or "").splitlines():
        if "Video:" in l and "x" in l:
            for t in l.replace(",", " ").split():
                if t.count("x") == 1:
                    a, b = t.split("x")
                    if a.isdigit() and b.isdigit():
                        return int(a), int(b)
    return 0, 0


def 有音轨(路):
    r = subprocess.run([FF, "-hide_banner", "-i", 路], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return any("Stream #" in l and "Audio" in l for l in (r.stderr or "").splitlines())


def main():
    a = sys.argv
    if not all(k in a for k in ("--超分", "--音源", "--出")):
        print(__doc__)
        return 2
    超 = a[a.index("--超分") + 1]
    音 = a[a.index("--音源") + 1]
    出 = a[a.index("--出") + 1]
    srt = a[a.index("--srt") + 1] if "--srt" in a else ""

    for p in (超, 音):
        if not os.path.isfile(p):
            print("✗ 找不到 %s" % p)
            return 1
    w, h = 尺寸(超)
    if not w:
        print("✗ 读不出 %s 的分辨率" % 超)
        return 1
    倍 = w / 基准宽
    字号 = int(round(22 * 倍))
    边距 = int(round(36 * 倍))
    描边 = max(3, int(round(3 * 倍)))
    print("超分素材 %dx%d（%.2f×）→ 字幕 FontSize=%d MarginV=%d Outline=%d"
          % (w, h, 倍, 字号, 边距, 描边))
    print("超分素材有音轨吗：%s" % ("有（会被 --音源 覆盖）" if 有音轨(超) else "没有 → 贴回 --音源 的"))
    print("音源有音轨吗：%s" % ("有" if 有音轨(音) else "★ 没有！混音() 靠它当环境音，贴不上"))
    if not 有音轨(音):
        return 1

    样 = ("FontName=Microsoft YaHei,FontSize=%d,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,BorderStyle=1,Outline=%d,Shadow=1,MarginV=%d"
          % (字号, 描边, 边距))
    cmd = [FF, "-y", "-v", "error", "-i", 超, "-i", 音]
    if srt:
        if not os.path.isfile(srt):
            print("✗ 找不到字幕 %s" % srt)
            return 1
        esc = srt.replace("\\", "/").replace(":", "\\:")
        cmd += ["-vf", "subtitles='%s':force_style='%s'" % (esc, 样)]
    cmd += ["-map", "0:v:0", "-map", "1:a:0", "-shortest",
            "-c:v", "libx264", "-crf", "17", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", 出]
    print("开始装配（这一条是全片重编码，要等）…")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("✗ 装配失败：\n" + (r.stderr or "")[-2000:])
        return 1
    if not os.path.isfile(出):
        print("✗ 命令退 0 但产物不在")
        return 1
    print("✓ %s　%.1f MB" % (出, os.path.getsize(出) / 1048576))
    print("  有音轨：%s" % ("是" if 有音轨(出) else "★ 否"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
