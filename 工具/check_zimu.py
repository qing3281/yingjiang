# -*- coding: utf-8 -*-
"""验「硬字幕到底有没有烧进像素」—— 在**台词窗口的中间**抽帧，不是在随机时刻抽。

起因：`_验成片2.py` 的 ⑤ 只抽了 5 帧（随机时刻），那 5 帧正好都在没台词的缝里，
      于是「字幕是像素」这句话等于没验。随机抽帧验不了只在特定时刻出现的东西。
判据：台词窗口中点抽出来的帧上，画面下三分之一应该有一行亮像素（字）。
"""
import os, sys, subprocess, json
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"      # 和 _接子镜.py:42 用的同一个，不靠 PATH
片 = os.path.join(目, "片", "楚子航_成片_字幕.mp4")
表 = os.path.join(目, "配音", "_配音表.json")
出 = r"D:\DSHworkspace\_验字幕"
os.makedirs(出, exist_ok=True)

一格秒 = 298.67 / 32

with open(表, encoding="utf-8") as f:
    d = json.load(f)
句 = d["配音"]          # 表的结构：{配音:[{序号,文本,路,秒,音色,字幕,角色}], 总时长, 目录, srt, 角色解析}
print(f"  配音表 {len(句)} 句，总时长字段 {d['总时长']}")

print(f"成片: {片}")
print(f"  存在={os.path.exists(片)}  字节={os.path.getsize(片):,}")

# 取 6 句，均匀撒在全片
挑 = [1, 8, 16, 24, 29, 32]
条 = []
print(f"\n{'句':>3} {'说话人':<8} {'抽帧秒':>8}   字")
for 号 in 挑:
    r = next(x for x in 句 if x["序号"] == 号)
    起 = (号 - 1) * 一格秒 + 0.35
    长 = float(r.get("秒") or 1.5)
    中 = 起 + max(0.3, 长 * 0.5)
    png = os.path.join(出, f"句{号:02d}.png")
    subprocess.run([FF, "-y", "-v", "error", "-ss", f"{中:.3f}", "-i", 片,
                    "-frames:v", "1", png], check=True)
    im = np.asarray(Image.open(png).convert("L"))
    h, w = im.shape
    # 字幕一般在下方 20% 之内，但烧字的坐标是 _接子镜.py 定的 —— 这里扫下三分之一
    band = im[int(h * 0.66):, :]
    # 字是纯白/亮黄，阈值取 200
    亮 = int((band > 200).sum())
    # 对照：同一帧的上三分之一（天花板/墙）里的亮像素
    top = int((im[:int(h * 0.33), :] > 200).sum())
    条.append((号, r.get("角色", "?"), 中, 亮, top))
    print(f"{号:>3} {r.get('角色','?'):<8} {中:>8.2f}   {亮:>7}  (上三分之一 {top})")

# 拼一条对照图
ims = [Image.open(os.path.join(出, f"句{号:02d}.png")) for 号 in 挑]
W = 320
ims = [im.resize((W, int(im.height * W / im.width))) for im in ims]
H = max(im.height for im in ims)
图 = Image.new("RGB", (W * len(ims), H))
for i, im in enumerate(ims):
    图.paste(im, (i * W, 0))
拼 = os.path.join(出, "_验字幕条.jpg")
图.save(拼, quality=88)

m = np.median([x[3] for x in 条])
print(f"\n下三分之一亮像素中位 {m:.0f}；上三分之一中位 {np.median([x[4] for x in 条]):.0f}")
print(f"拼图 {拼}")
print("\n结论：" + ("✓ 台词窗口的帧上确实有亮像素（字烧在画面上）" if m > 500 else
                "✗ 台词窗口的帧上看不到字 —— 硬字幕这一步没生效"))
sys.exit(0 if m > 500 else 1)
