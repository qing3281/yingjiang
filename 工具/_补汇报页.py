# -*- coding: utf-8 -*-
"""_补汇报页.py —— 给 `_怎么做出来的.html` 补一节「2 倍清晰版」，并更新页脚时间。

只插一次：已经有这一节就什么都不做。
"""
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

页 = r"D:\DSHworkspace\影匠\作品\楚子航\_怎么做出来的.html"
标 = "<h2>★ 2 倍清晰版做出来了"

节 = """<h2>★ 2 倍清晰版做出来了（2026-10-16 17:00）</h2>
<p>你 10-16 说过「<b>清晰度不够，之后再超分就行</b>」。这是那句话的落地：把官方那条 736×416
过一遍 SeedVR2 3B，做 2× 超分，其它一律不动。</p>
<table>
  <tr><th>量什么</th><th>数</th><th>怎么算的</th></tr>
  <tr><td>分辨率</td><td><b>736×416 → 1472×832</b>（正好 2.000×）</td><td>读帧尺寸</td></tr>
  <tr><td>帧数 / 时长</td><td>7168 帧 / 298.67 秒 / 24.000 fps（<b>一帧不差</b>）</td><td>数帧</td></tr>
  <tr><td>真的变清楚了吗</td><td><b>1.85×</b></td><td>把超分帧<b>缩回原尺寸</b>再比拉普拉斯方差</td></tr>
  <tr><td>分段有没有留下新刀</td><td><b>最狠 3.68×</b>（段内正常波动 = 1×）</td><td>14 条段缝逐个比</td></tr>
  <tr><td>人声还在不在</td><td><b>6.3×</b></td><td>做减法 Σ人声 ≈（混音 − 0.55×源片）/1.9</td></tr>
  <tr><td>硬字幕</td><td>底下多出 <b>1227</b> 个纯白像素 / 顶上 <b>6</b> 个</td><td>32 句台词中点各抽一帧</td></tr>
  <tr><td>成本</td><td>15 段合计 <b>109 分钟</b>；20 秒小样 = 485 秒 → 24.25 秒/1 秒素材</td><td>实测</td></tr>
  <tr><td>成品</td><td><b>267.9 MB</b>（1472×832）</td><td>字节数</td></tr>
</table>
<p><b>为什么必须分段</b>：整条一次跑挂在
<code>Unable to allocate 14.0 MiB for an array with shape (832, 1472, 3)</code>。
算一下就明白 —— 那个节点把所有帧留在内存，而且同时吃两份（<code>images</code> 与
<code>original_resized_images</code>）：<b>7168 × 2 × 14.7 MB ≈ 210 GB</b>，远端只有 47.2 GB。
切成 15 段（每段 20 秒）就全过了。</p>
<p><b>这一趟自己逮到并修掉的一个错</b>：字幕第一版按「宽/736」把字号从 22 抬到 44
（我以为 2× 画面要 2× 字号），结果最长那句<b>直接冲出画面左右两边</b>。
根因是 <b>libass 本来就按画面高度缩放字号</b>，再乘一次就是净放大两倍。
量完定稿 <b>FontSize=30 / MarginV=48 / Outline=4</b> —— 32 句全部不贴边、不折行，
最长句占画面 86.1%。</p>
<p>量版式的脚本：<code>check_字幕宽度.py</code>（在纯黑底上逐句烧一遍量包围盒）；
验整条成片：<code>_验超分片.py</code>（七条判据）。
<b>注意</b>：拿「超分过的成片 − 源片」做差去量字在哪是<b>错</b>的 —— 超分本身就把像素改动
远超阈值，会把「再见。」三个字报成占画面 99.9%。那一版脚本已作废，留下壳说明理由。</p>

"""

if not os.path.isfile(页):
    print("✗ 找不到 %s" % 页)
    sys.exit(1)

s = open(页, encoding="utf-8").read()
原 = len(s.encode("utf-8"))

if 标 in s:
    print("· 已经有这一节，不动")
    sys.exit(0)

i = s.rfind("<div", 0, s.rfind("</body>"))
if i < 0:
    i = s.rfind("</body>")
s = s[:i] + 节 + s[i:]

# 页脚时间
s = re.sub(r"生成时间：2026-10-16 10:55（14:45 补了官方那条的实测数字）",
           "生成时间：2026-10-16 10:55（14:45 补官方那条的实测数字，17:00 补 2 倍清晰版）", s)

with open(页, "w", encoding="utf-8") as f:
    f.write(s)

新 = len(s.encode("utf-8"))
print("✓ %s  %d → %d 字节（+%d）" % (页, 原, 新, 新 - 原))
