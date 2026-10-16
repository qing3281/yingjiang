# -*- coding: utf-8 -*-
"""给《觉醒》加片头卡和片尾卡 —— 不是为了好看，是为了**时长**和**最后一句不被切掉**。

## 为什么非得加

1. **最后一句会撞到片尾。**
   格74 有两句（旁白「青云山下，这一次有人记得他。」＋陈老根「陈老根。」）。
   按实测语速估，这两句从格74 的 289.66s 起，一路能说到约 294.5s，
   而 74 格的画面**总共只有 293.4 秒** —— 全片的题眼（他第一次说出自己的名字）
   会被切在最后一个字上。加一张片尾卡，这句话就有地方落。

2. **时长差 6.6 秒。**
   107 帧 × 74 格 − 73 × 0.5s 转场 = **293.4 秒 = 4 分 53.4 秒**，
   离用户要的 5 分钟差 6.6 秒。
   片头 2 秒 + 片尾 5 秒 = 300.4 秒 = **5 分 00.4 秒**。

## 卡片长什么样

片头：黑底，一行片名《觉醒》，底下小字「影匠」。
片尾：黑底，一句话 + 「影匠」。
都用 ffmpeg 的 drawtext 直接画，不依赖任何图片素材。
"""
import os
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")
FFPROBE = os.path.join(根, "_bin", "ffprobe.exe")


def 有ffprobe():
    return os.path.isfile(FFPROBE)


def 探秒(路):
    if 有ffprobe():
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", 路],
                           capture_output=True, text=True, errors="replace")
        try:
            return float((r.stdout or "").strip())
        except ValueError:
            pass
    import re
    r = subprocess.run([FFMPEG, "-i", 路, "-hide_banner"],
                       capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d{1,3})", r.stderr or "")
    if m:
        h, mi, s, ms = m.groups()
        return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
    return 0.0


def 找字体():
    """找一款有中文的字体。没有就用 ffmpeg 默认（会画成方块，要报出来）。"""
    候选 = [
        r"C:\Windows\Fonts\msyhbd.ttc",      # 微软雅黑粗体
        r"C:\Windows\Fonts\msyh.ttc",        # 微软雅黑
        r"C:\Windows\Fonts\simhei.ttf",      # 黑体
        r"C:\Windows\Fonts\simsun.ttc",      # 宋体
        r"C:\Windows\Fonts\SourceHanSansSC-Bold.otf",
    ]
    for c in 候选:
        if os.path.isfile(c):
            return c
    return ""


def 画卡(出, 宽, 高, 帧率, 秒, 主文, 副文, 字体):
    """一张黑底卡。主文大、居中偏上；副文小、在主文下面。"""
    字号主 = int(高 * 0.095)
    字号副 = int(高 * 0.032)
    # ffmpeg 的 drawtext 里冒号、反斜杠、单引号都要转义；Windows 路径的 \ 要写 \\
    字 = 字体.replace("\\", "/").replace(":", "\\:")
    主 = 主文.replace(":", "\\:").replace("'", "")
    副 = 副文.replace(":", "\\:").replace("'", "")
    链 = (
        f"drawtext=fontfile='{字}':text='{主}':fontcolor=white:fontsize={字号主}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-{int(高*0.03)},"
        f"drawtext=fontfile='{字}':text='{副}':fontcolor=0xBBBBBB:fontsize={字号副}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2+{int(高*0.075)}"
    )
    # ⚠ `-vf` 是**输出**选项，必须写在两个 `-i` 之后。
    # 写在两个 -i 中间会被当成第二个输入的选项，ffmpeg 直接报
    # 「Option vf cannot be applied to input url anullsrc=...」。
    cmd = [FFMPEG, "-y",
           "-f", "lavfi", "-i", f"color=c=black:s={宽}x{高}:r={帧率}:d={秒}",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=32000",
           "-vf", 链,
           "-map", "0:v", "-map", "1:a",
           "-shortest",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-c:a", "aac", "-b:a", "128k", 出]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0 and os.path.isfile(出) and os.path.getsize(出) > 1000
    if not ok:
        print(f"  ✗ 画卡失败：{(r.stderr or '')[-400:]}")
    return ok


def 接(清单, 出, 帧率):
    """用 concat **滤镜**硬接（卡片和正片之间不需要溶解，黑场接黑场看不出来）。

    ⚠ 为什么不用 `-f concat` 解复用器（2026-10-14 实测）：解复用器只按时间戳
    往下排，三块 tbn 不完全一致时会在拼接点把时长拉长——实测 2+28.25+5=35.25 秒的
    片子，解复用器输出 **45.15 秒**（多了 9.9 秒），而滤镜重编码输出正好 35.25 秒。
    所以这里是滤镜法：每块先 `setpts=PTS-STARTPTS` 把时间轴归零，再 concat。
    """
    参 = []
    for p in 清单:
        参 += ["-i", p]
    v = "".join(f"[{i}:v]fps={帧率},setpts=PTS-STARTPTS[v{i}];" for i in range(len(清单)))
    a = "".join(f"[{i}:a]aresample=32000,asetpts=PTS-STARTPTS[a{i}];" for i in range(len(清单)))
    n = len(清单)
    滤 = (v + a
          + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vo];"
          + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[ao]")
    r = subprocess.run([FFMPEG, "-y", *参, "-filter_complex", 滤,
                        "-map", "[vo]", "-map", "[ao]",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                        "-r", str(帧率),
                        "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", 出],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.isfile(出):
        print(f"  ✗ 接片失败：{(r.stderr or '')[-500:]}")
        return False
    return True


def 主(正片, 出, 片名, 尾句, 头秒, 尾秒, 尾嗓=None):
    字体 = 找字体()
    print(f"字体：{字体 or '⚠ 找不到中文字体，卡片上的字会画成方块'}")
    if not 探秒(正片):
        print(f"✗ 量不出 {正片} 的时长")
        return 1
    总 = 探秒(正片)
    print(f"正片 {总:.2f} 秒 = {int(总//60)} 分 {总%60:.1f} 秒")
    print(f"片头 {头秒}s + 片尾 {尾秒}s → {总+头秒+尾秒:.2f} 秒 = "
          f"{int((总+头秒+尾秒)//60)} 分 {(总+头秒+尾秒)%60:.1f} 秒")

    # 拿正片的实际规格来画卡，免得拼接时分辨率/帧率对不上
    import json as _j
    if 有ffprobe():
        r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,r_frame_rate",
                            "-of", "json", 正片],
                           capture_output=True, text=True, errors="replace")
        try:
            s = _j.loads(r.stdout)["streams"][0]
            宽, 高 = int(s["width"]), int(s["height"])
            帧率 = eval(s["r_frame_rate"]) if "/" in s["r_frame_rate"] else float(s["r_frame_rate"])
        except Exception:  # noqa: BLE001
            宽, 高, 帧率 = 1280, 704, 24.0
    else:
        宽, 高, 帧率 = 1280, 704, 24.0
    print(f"规格 {宽}×{高} @{帧率:g}fps")

    戏目录 = os.path.dirname(os.path.dirname(os.path.abspath(正片)))
    头 = os.path.join(戏目录, "_卡_头.mp4")
    尾 = os.path.join(戏目录, "_卡_尾.mp4")
    if not 画卡(头, 宽, 高, 帧率, 头秒, 片名, "影匠", 字体):
        return 1
    if not 画卡(尾, 宽, 高, 帧率, 尾秒, 尾句, "影匠", 字体):
        return 1
    print(f"  头卡 {探秒(头):.2f}s　尾卡 {探秒(尾):.2f}s")

    if not 接([头, 正片, 尾], 出, 帧率):
        return 1
    新 = 探秒(出)
    应该 = 探秒(头) + 总 + 探秒(尾)
    # 硬闸门：出片时长必须等于三块相加（±0.15 秒）。
    # 2026-10-14 加：concat 解复用器把 35.25 秒的片子接成 45.15 秒，
    # 而脚本照样打 ✓ —— 这正是「假判据族」里「说 OK 但什么都没量」那一种。
    if abs(新 - 应该) > 0.15:
        print(f"\n✗ 接出来的时长不对：{新:.2f} 秒，应该是 {应该:.2f} 秒"
              f"（差 {新-应该:+.2f} 秒）")
        return 1
    print(f"\n✓ {出}")
    print(f"  {新:.2f} 秒 = {int(新//60)} 分 {新%60:.1f} 秒　{os.path.getsize(出)/1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("正片")
    ap.add_argument("--出", default="")
    ap.add_argument("--片名", default="觉醒")
    ap.add_argument("--尾句", default="陈老根。")
    ap.add_argument("--头秒", type=float, default=2.0)
    ap.add_argument("--尾秒", type=float, default=5.0)
    参 = ap.parse_args()
    出 = 参.出 or os.path.join(os.path.dirname(os.path.abspath(参.正片)),
                               f"《{参.片名}》成片_带头尾.mp4")
    sys.exit(主(参.正片, 出, f"《{参.片名}》", 参.尾句, 参.头秒, 参.尾秒))
