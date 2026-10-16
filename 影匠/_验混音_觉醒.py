# -*- coding: utf-8 -*-
"""单独验「原声留下 + 人声压过原声」这条新混音链 —— 不跑 IndexTTS，不占 GPU。

为什么单独验：`_配片.py` 整条跑一遍要先合成 74 句台词（十来分钟 GPU），
而这里要验的只是 **ffmpeg 的滤镜图对不对**。拿已经出好的 H3 段片（它自带音轨）
配上已经合成好的那三个 wav，就够验了。

★ 采样点要躲开片头卡：前 2 秒是黑场静音，在那儿量只会得到「静音」这个假结论
（第一版就是这么踩的：`片自带音轨有效值 0.0000`）。
所以人声故意排到 8s / 16s / 26s，空出 5s 和 20s 两个「没人说话」的窗口来对比。
"""
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")

片 = os.path.join(根, "作品", "觉醒", "片", "_试接6格_带头尾.mp4")
人声 = [os.path.join(根, "作品", "觉醒", "配音", x)
        for x in ("01_旁白.wav", "02_陈老根.wav", "03_系统.wav")]
人声 = [p for p in 人声 if os.path.exists(p)]
出 = os.path.join(根, "作品", "觉醒", "片", "_混音试.mp4")
旧 = os.path.join(根, "作品", "觉醒", "片", "_混音试_旧.mp4")
起们 = [6.0, 13.0, 20.0][:len(人声)]


def 探秒(路):
    r = subprocess.run([FFMPEG, "-i", 路, "-hide_banner"],
                       capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d{1,3})", r.stderr or "")
    if not m:
        return 0.0
    h, mi, s, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def 量(路, 时, 窗=0.5):
    r = subprocess.run([FFMPEG, "-ss", f"{时:.2f}", "-t", f"{窗}", "-i", 路,
                        "-af", "volumedetect", "-f", "null", os.devnull],
                       capture_output=True, text=True, errors="replace")
    m = re.search(r"mean_volume:\s*(-?[\d.]+)", r.stderr or "")
    return float(m.group(1)) if m else None


def 量全片(路):
    """在片体里取四个点，躲开片头片尾卡。"""
    总 = 探秒(路)
    点 = [总 * b for b in (0.15, 0.35, 0.55, 0.75)]
    值 = [量(路, p) for p in 点]
    值 = [v for v in 值 if v is not None]
    return (max(值) if 值 else None), 点, 值


print(f"片子 {os.path.basename(片)}　{探秒(片):.2f} 秒")
机, 点, 值 = 量全片(片)
print(f"  片子自带的音轨（片体四点 {[round(p,1) for p in 点]}）：{值} dB → 最大 {机} dB")
print(f"  人声 {len(人声)} 条，起于 {起们} 秒："
      + "、".join(os.path.basename(p) for p in 人声))

# ══ 新链（复刻 `_配片.py`）══
输入 = [FFMPEG, "-y", "-i", 片]
链, idx = [], 1
for i, p in enumerate(人声):
    输入 += ["-i", p]
    毫 = int(起们[i] * 1000)
    链.append(f"[{idx}:a]adelay={毫}|{毫},volume=1.0[v{i}]")
    idx += 1
滤人 = (";".join(链)
       + f";{''.join(f'[v{i}]' for i in range(len(人声)))}"
         f"amix=inputs={len(人声)}:duration=longest:normalize=0[人声]")

总 = 探秒(片)
# ⚠ 人声是有限长的，而 sidechaincompress / amix 都「谁短跟谁」——
#   不把两条人声分支 apad 到全片长，整条音轨会在最后一句台词结束处被砍断。
新滤 = (滤人
       + ";[0:a]aresample=48000,volume=1.0[原声];"
         "[人声]asplit=2[人声出0][人声键0];"
         f"[人声出0]apad=whole_dur={总:.3f}[人声出];"
         f"[人声键0]apad=whole_dur={总:.3f}[人声键];"
         "[原声][人声键]sidechaincompress="
         "threshold=0.04:ratio=12:attack=15:release=450:makeup=1[原声压]"
       + f";anoisesrc=color=brown:amplitude=0.35:duration={总 + 5:.1f}[噪];"
         "[噪]highpass=f=180,lowpass=f=1400,volume=0.030[风]"
       + ";[原声压][人声出][风]amix=inputs=3:duration=first:normalize=0[混]"
       + ";[混]alimiter=limit=0.95,apad[aout]")

旧滤 = (滤人
       + f";anoisesrc=color=brown:amplitude=0.35:duration={总 + 5:.1f}[噪];"
         "[噪]highpass=f=180,lowpass=f=1400,volume=0.055[风]"
       + ";[风][人声]amix=inputs=2:duration=first:normalize=0[混]"
       + ";[混]alimiter=limit=0.95,apad[aout]")

出图 = {}
for 名, 滤, 目 in (("新链", 新滤, 出), ("旧链", 旧滤, 旧)):
    r = subprocess.run(输入 + ["-filter_complex", 滤, "-map", "0:v", "-map", "[aout]",
                               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                               "-t", f"{总}", 目],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0 and os.path.exists(目)
    出图[名] = ok
    if not ok:
        print(f"\n✗ {名} 滤镜图挂了：\n{(r.stderr or '')[-1200:]}")
    else:
        print(f"\n✓ {名} → {os.path.basename(目)}　"
              f"{探秒(目):.2f} 秒　{os.path.getsize(目)/1048576:.2f} MB")

if not all(出图.values()):
    sys.exit(1)

print("\n══ 关键对比：同一条片子，两套链，同样三个窗口 ══")
print(f"{'窗口':<26}{'旧链(丢原声)':>16}{'新链(留原声)':>16}")
表 = [(4.0, "4.0s　没人说话"), (6.6, "6.6s　人声在说"),
      (10.5, "10.5s 没人说话"), (13.6, "13.6s 人声在说"),
      (18.0, "18.0s 没人说话"), (23.5, "23.5s 没人说话")]
明细 = []
for 时, 说 in 表:
    a, b = 量(旧, 时), 量(出, 时)
    明细.append((说, a, b))
    print(f"{说:<24}{('%+.1f dB' % a) if a is not None else '?':>16}"
          f"{('%+.1f dB' % b) if b is not None else '?':>16}")

print("\n══ 判据 ══")
空窗 = [(说, a, b) for 说, a, b in 明细 if "没人说话" in 说]
人窗 = [(说, a, b) for 说, a, b in 明细 if "人声在说" in 说]
判 = []
if 空窗:
    d = [b - a for _, a, b in 空窗 if a is not None and b is not None]
    好 = all(x >= 2.0 for x in d)
    判.append((好, f"没人说话的窗口，新链比旧链响 {['%+.1f' % x for x in d]} dB"
                   f"（环境音真的留下了）"))
if 人窗 and 空窗:
    新空 = [b for _, _, b in 空窗 if b is not None]
    新人 = [b for _, _, b in 人窗 if b is not None]
    if 新空 and 新人:
        好 = max(新人) > max(新空)
        判.append((好, f"新链里人声窗口 {max(新人):+.1f} dB > 空窗 {max(新空):+.1f} dB"
                       f"（差 {max(新人)-max(新空):+.1f} dB，台词盖得住环境）"))
for 好, 话 in 判:
    print(f"  {'✓' if 好 else '✗'} {话}")
sys.exit(0 if all(好 for 好, _ in 判) else 1)
