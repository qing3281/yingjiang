# -*- coding: utf-8 -*-
r"""逐格量「画面下缘有多少**纯白**像素」—— 专抓模型自己画上去的假字幕。

为什么这么量：这条片子的调子是冷灰、暗部居多，画面里**本来不该有大片纯白**。
模型犯「假字幕」这个病的时候，是在画面下缘居中写一行白字、带黑描边 ——
那一片像素的三通道都会顶到 240 以上，跟场景的亮度分布完全不是一回事。

判据不是「有没有白」，是「白得**成片**」：单格量出来的白色像素占比
跟全片中位数比，高出十几倍的就是嫌疑格。

用法：python _查假字幕.py            （量 + 拼图）
      python _查假字幕.py --只量      （只打印表）
产出：D:\DSHworkspace\影匠\作品\觉醒\_查假字幕.png
"""
import os
import statistics
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

FFMPEG = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
戏 = r"D:\DSHworkspace\影匠\作品\觉醒"
段 = os.path.join(戏, "段")
临时 = os.path.join(戏, "_假字幕临时")
os.makedirs(临时, exist_ok=True)

# 段用的是哪一条 —— 跟 `_拼长片.py` 一样的规矩：两条线都出了就挑文件大的
找到 = {}
for f in sorted(os.listdir(段)):
    if not f.endswith(".mp4") or not f.startswith("格"):
        continue
    try:
        号 = int(f.split("_")[0].replace("格", ""))
    except ValueError:
        continue
    路 = os.path.join(段, f)
    if 号 not in 找到 or os.path.getsize(路) > os.path.getsize(找到[号]):
        找到[号] = 路
号们 = sorted(找到)

裁 = "crop=1280:200:0:504"       # 下缘 200 像素 —— 字幕就落在这里
纯白 = 235                        # 三通道都 ≥ 这个数才算「纯白」


def 量一格(号, t="2.0"):
    o = os.path.join(临时, f"w{号}.png")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", t, "-i", 找到[号],
                    "-frames:v", "1", "-vf", 裁, o],
                   capture_output=True, text=True, errors="replace")
    if not os.path.isfile(o):
        return None
    图 = Image.open(o).convert("RGB")
    px = list(图.getdata())
    n = len(px)
    白 = sum(1 for r, g, b in px if r >= 纯白 and g >= 纯白 and b >= 纯白)
    return 白 / n


数 = {}
for 号 in 号们:
    v = 量一格(号)
    if v is not None:
        数[号] = v

中位 = statistics.median(数.values())
print(f"  全片 {len(数)} 格，下缘纯白占比：中位 {中位 * 100:.3f}%　最大 {max(数.values()) * 100:.3f}%")
嫌疑 = sorted([k for k, v in 数.items() if v > max(中位 * 8, 0.004)], key=lambda k: -数[k])
print(f"  ★ 嫌疑格 {len(嫌疑)} 个：")
for k in 嫌疑:
    print(f"      格{k:<3} 纯白 {数[k] * 100:.3f}%　（是中位的 {数[k] / max(中位, 1e-9):.0f} 倍）")

if "--只量" in sys.argv:
    sys.exit(0)

窄, 高 = 384, 84
每行 = 4
行数 = (len(号们) + 每行 - 1) // 每行
画 = Image.new("RGB", (窄 * 每行 + 8 * (每行 + 1), 66 + (高 + 22) * 行数 + 8), (15, 17, 21))
d = ImageDraw.Draw(画)


def 字(n, 粗=False):
    for p in ((r"C:\Windows\Fonts\msyhbd.ttc" if 粗 else r"C:\Windows\Fonts\msyh.ttc"),
              r"C:\Windows\Fonts\msyh.ttc"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, n)
            except Exception:
                pass
    return ImageFont.load_default()


f, fb = 字(14), 字(24, True)
d.text((10, 12), "《觉醒》全片 74 格 —— 下缘纯白像素量（专抓模型画上去的假字幕）", font=fb, fill=(230, 232, 238))
d.text((10, 42), f"绿=正常　红框=纯白占比是中位的 8 倍以上（{len(嫌疑)} 格）　每格取第 2.0 秒", font=f, fill=(124, 135, 152))

出 = os.path.join(戏, "_查假字幕.png")
for i, 号 in enumerate(号们):
    x = 8 + (i % 每行) * (窄 + 8)
    y = 66 + (i // 每行) * (高 + 22)
    坏 = 号 in 嫌疑
    d.text((x, y), f"格{号}　{数[号] * 100:.2f}%", font=f, fill=(255, 91, 91) if 坏 else (61, 220, 132))
    o = os.path.join(临时, f"w{号}.png")
    if os.path.isfile(o):
        图 = Image.open(o).convert("RGB").resize((窄, 高))
        画.paste(图, (x, y + 18))
        if 坏:
            d.rectangle([x - 2, y + 16, x + 窄 + 1, y + 18 + 高 + 1], outline=(255, 91, 91), width=2)

画.save(出)
print(f"  ✓ {出}　{画.width}x{画.height}　{os.path.getsize(出):,} B")
