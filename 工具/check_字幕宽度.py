# -*- coding: utf-8 -*-
"""check_字幕宽度.py —— 32 句每一句都在**纯黑底**上单独烧一遍，量它的真实包围盒。

为什么不用成片帧去量：成片是 2× 超分过的，「成片 − 源片」的差在顶灯、水花、
火把上本来就会有 >60 的像素，边缘零星几个点就能把包围盒撑到整幅 ——
于是「再见。」三个字也被报成占 99.9%。**量版式要用版式自己的场地（纯黑底），
不要拿一条经过超分的成片当尺子。**

判据：
  ① 左右不贴边（留 ≥2% 余量）
  ② 没有折行（行数 = 1 行；折行说明被 libass 自动换行，和剧本一句一行不一致）
"""
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
工 = r"D:\DSHworkspace\_字幕试\宽"
表 = r"D:\DSHworkspace\影匠\作品\楚子航\配音\_配音表.json"
W, H = 1472, 832
字号, 边距, 描边 = 30, 48, 4

os.makedirs(工, exist_ok=True)
黑 = os.path.join(工, "黑.png")
cv2.imencode(".png", np.zeros((H, W, 3), np.uint8))[1].tofile(黑)

d = json.load(open(表, encoding="utf-8"))
句 = sorted(d["配音"], key=lambda e: -len(e["文本"]))
print("按字数从多到少（FontSize=%d MarginV=%d Outline=%d，画面 %dx%d）：" % (字号, 边距, 描边, W, H))
坏 = []
最宽 = 0.0
最宽句 = None
for e in 句:
    srt = os.path.join(工, "s.srt")
    with open(srt, "w", encoding="utf-8") as f:
        f.write("1\n00:00:00,000 --> 00:00:10,000\n%s\n" % e["文本"])
    o = os.path.join(工, "o.png")
    if os.path.isfile(o):
        os.remove(o)
    样 = ("FontName=Microsoft YaHei,FontSize=%d,PrimaryColour=&H00FFFFFF,"
          "OutlineColour=&H00000000,BorderStyle=1,Outline=%d,Shadow=0,MarginV=%d"
          % (字号, 描边, 边距))
    滤 = "subtitles='%s':force_style='%s'" % (srt.replace("\\", "/").replace(":", "\\:"), 样)
    r = subprocess.run([FF, "-y", "-v", "error", "-i", 黑, "-vf", 滤, "-frames:v", "1", o],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.isfile(o):
        print("  第%2d句　★ 渲染失败：%s" % (e["序号"], (r.stderr or "")[-160:]))
        坏.append(e["序号"])
        continue
    im = cv2.imdecode(np.fromfile(o, dtype=np.uint8), cv2.IMREAD_COLOR)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    行 = g.sum(axis=1) > 0
    列 = g.sum(axis=0) > 0
    有行 = np.nonzero(行)[0]
    有列 = np.nonzero(列)[0]
    if not len(有列):
        print("  第%2d句　★ 没画出字" % e["序号"])
        坏.append(e["序号"])
        continue
    l, r_ = int(有列.min()), int(有列.max())
    宽 = r_ - l + 1
    占 = 100.0 * 宽 / W
    # 折行判断：找行方向上的空白带
    段 = 0
    上 = False
    for v in 行:
        if v and not 上:
            段 += 1
        上 = bool(v)
    贴 = l <= int(W * 0.02) or r_ >= W - int(W * 0.02)
    if 占 > 最宽:
        最宽, 最宽句 = 占, e["序号"]
    记 = "★ 贴边" if 贴 else "ok"
    if 段 > 1:
        记 += "　★ 折成 %d 行" % 段
    print("  第%2d句 %2d字「%s」　宽 %4d px（占 %5.1f%%）　左右 %4d..%4d　%d 行　%s"
          % (e["序号"], len(e["文本"]), e["文本"][:14], 宽, 占, l, r_, 段, 记))
    if 贴 or 段 > 1:
        坏.append(e["序号"])

print("")
print("最宽的一句：第 %s 句，占 %.1f%%" % (最宽句, 最宽))
if 坏:
    print("✗ %d 句有问题：%s" % (len(坏), 坏))
    sys.exit(1)
print("✓ 32 句全部：不贴边、不折行")
