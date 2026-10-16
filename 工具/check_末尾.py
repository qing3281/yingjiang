# -*- coding: utf-8 -*-
"""check_末尾.py —— 成片最后 20 秒到底黑不黑、闪不闪。

起因：格32（龙的死亡）的 `04-动态提示词.md` 动作里本来就写着「画面慢慢变暗、最后只剩那串脚印」，
      所以「变暗」是对的；要盯的是**中途黑到 0 再猛地亮回来**（那才是 bug）。
      主线版格32_4 当时量到 8.63 → 8.18；质量闸又用 种子偏移 777 重摇过一次 —— 得看落进片里的到底是哪一版。

判据：最后 20 秒逐帧亮度里，**相邻帧亮度差 > 25 的跳变不许出现**（渐变每帧差个位数）。
"""
import os
import sys
import subprocess
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
片 = r"D:\DSHworkspace\影匠\作品\楚子航\片\楚子航_成片_字幕.mp4"
出 = r"D:\DSHworkspace\_验末尾"
os.makedirs(出, exist_ok=True)

import cv2

c = cv2.VideoCapture(片)
n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
fps = float(c.get(cv2.CAP_PROP_FPS)) or 24.0
c.release()
总秒 = n / fps
print(f"成片 {n} 帧　{fps:.3f} fps　{总秒:.2f} 秒")

起 = max(0.0, 总秒 - 20.0)
亮 = []
for i in range(int((总秒 - 起) * fps)):
    t = 起 + i / fps
    png = os.path.join(出, "_t.png")
    subprocess.run([FF, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", 片,
                    "-frames:v", "1", png], check=True)
    a = cv2.imdecode(np.fromfile(png, np.uint8), cv2.IMREAD_COLOR)
    亮.append(float(a.mean()))

亮 = np.array(亮)
差 = np.abs(np.diff(亮))
print(f"最后 {len(亮)} 帧（{起:.1f}–{总秒:.1f} 秒）")
print(f"  亮度：起 {亮[0]:.2f}　中位 {np.median(亮):.2f}　末 {亮[-1]:.2f}　最小 {亮.min():.2f}　最大 {亮.max():.2f}")
print(f"  逐帧亮度差：中位 {np.median(差):.2f}　最大 {差.max():.2f}")
暗 = np.where(亮 < 10)[0]
if len(暗):
    print(f"  · 亮度 <10 的帧：{len(暗)} 帧 = {len(暗)/fps:.2f} 秒"
          f"　从 {起 + 暗[0]/fps:.2f} 秒 起　到片尾")
else:
    print("  · 没有 <10 的帧")
坏 = np.where(差 > 25)[0]
if len(坏):
    print(f"  ★ 有 {len(坏)} 处跳变 >25：")
    for i in 坏[:6]:
        print(f"      {起 + i / fps:6.2f} 秒　{亮[i]:.2f} → {亮[i+1]:.2f}　差 {差[i]:.1f}")
else:
    print("  ✓ 没有 >25 的亮度跳变 —— 末尾是渐变，不是闪")

# 抽 6 帧拼条
挑 = [int(x) for x in np.linspace(0, len(亮) - 2, 6)]      # ★ 不能取到最后一帧：那个时刻 ffmpeg 抽不出来
ims = []
for i in 挑:
    t = 起 + i / fps
    png = os.path.join(出, "_s%d.png" % i)
    subprocess.run([FF, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", 片,
                    "-frames:v", "1", "-vf", "scale=460:-1", png], check=True)
    ims.append(cv2.imdecode(np.fromfile(png, np.uint8), cv2.IMREAD_COLOR))
    cv2.putText(ims[-1], "%.1fs  y=%.1f" % (t, 亮[i]), (8, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
条 = np.hstack(ims)
拼 = os.path.join(出, "_末尾条.jpg")
cv2.imencode(".jpg", 条, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tofile(拼)
print(f"\n拼图 {拼}")
sys.exit(1 if len(坏) else 0)
