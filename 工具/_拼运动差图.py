# -*- coding: utf-8 -*-
"""把「相邻帧差」拉亮画出来 —— 一格里到底动没动，一眼看得出来。

做法：ffmpeg 缩到 420 宽 → `tblend=all_mode=difference` 出相邻帧差 →
`curves=all='0/0 0.02/1'` **把 0–5 灰度级硬拉到 0–255**。
（普通 `eq=contrast` 拉不动这种量级 —— 帧差本身才 0.5–2 个灰度级，
  不把 0.02 映射到 1.0，出来的图全黑，看着像「都没动」。这是踩过的坑。）

**画面全黑 = 这一格基本冻住；有轮廓 = 有人在动。**
第三列是这一格改之后的真实画面，用来认出这是哪一格。

用法：python _拼运动差图.py
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

FFMPEG = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
戏 = r"D:\DSHworkspace\影匠\作品\觉醒"
备 = os.path.join(戏, "_起手式前_20261015-034530", "段")
新 = os.path.join(戏, "段")
临时 = os.path.join(戏, "_差图临时")
os.makedirs(临时, exist_ok=True)

对子 = [
    (2, 0.59, 0.70, os.path.join(新, "格2_本机.mp4"), os.path.join(新, "格2_远端.mp4")),
    (5, 0.62, 0.71, os.path.join(新, "格5_本机.mp4"), os.path.join(新, "格5_远端.mp4")),
    (6, 0.60, 0.59, os.path.join(新, "格6_本机.mp4"), os.path.join(新, "格6_远端.mp4")),
    (17, 0.61, 0.70, os.path.join(新, "格17_本机.mp4"), os.path.join(新, "格17_远端.mp4")),
    (49, 0.58, 1.86, os.path.join(备, "格49_远端.mp4"), os.path.join(新, "格49_远端.mp4")),
]

拉亮 = "scale=420:-2,format=gray,tblend=all_mode=difference,curves=all='0/0 0.02/1'"


def 取字(号, 粗=False):
    for 路 in ((r"C:\Windows\Fonts\msyhbd.ttc" if 粗 else r"C:\Windows\Fonts\msyh.ttc"),
               r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if os.path.isfile(路):
            try:
                return ImageFont.truetype(路, 号)
            except Exception:
                pass
    return ImageFont.load_default()


def 抽(片, 出, vf, t="2.2"):
    subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", t, "-i", 片,
                    "-frames:v", "1", "-vf", vf, 出],
                   capture_output=True, text=True, errors="replace")
    return os.path.isfile(出)


f = 取字(17)
fb = 取字(22, True)
宽, 高, 头, 边 = 420, 232, 68, 14
画 = Image.new("RGB", (宽 * 3 + 边 * 4, 108 + (高 + 头) * len(对子) + 边), (15, 17, 21))
d = ImageDraw.Draw(画)
d.text((边, 14), "《觉醒》「一格到底动没动」—— 相邻帧差拉亮图", font=fb, fill=(230, 232, 238))
d.text((边, 44), "全黑＝冻住　有轮廓＝在动　│　左：改之前　中：改之后　右：改之后的真实画面　│　取第 2.2 秒", font=f, fill=(124, 135, 152))

y = 94
for 号, 旧量, 新量, 旧路, 新路 in 对子:
    d.text((边, y), f"格{号}　改之前　运动量 {旧量:.2f}", font=f, fill=(245, 197, 66))
    d.text((边 * 2 + 宽, y), f"格{号}　改之后　运动量 {新量:.2f}（{新量 / 旧量:.2f}×）", font=f, fill=(61, 220, 132))
    d.text((边 * 3 + 宽 * 2, y), f"格{号}　改之后的画面", font=f, fill=(124, 135, 152))
    o = os.path.join(临时, f"d{号}_old.png")
    if 抽(旧路, o, 拉亮):
        图 = Image.open(o).convert("RGB")
        画.paste(图, (边, y + 26))
    o2 = os.path.join(临时, f"d{号}_new.png")
    if 抽(新路, o2, 拉亮):
        图 = Image.open(o2).convert("RGB")
        画.paste(图, (边 * 2 + 宽, y + 26))
    o3 = os.path.join(临时, f"d{号}_pic.png")
    if 抽(新路, o3, "scale=420:-2", "0.2"):
        图 = Image.open(o3).convert("RGB")
        画.paste(图, (边 * 3 + 宽 * 2, y + 26))
    y += 高 + 头

出 = os.path.join(戏, "_起手式运动差.png")
画.save(出)
print(f"  ✓ {出}　{画.width}x{画.height}　{os.path.getsize(出):,} B")
