# -*- coding: utf-8 -*-
"""
剧本来源探针 05 —— 用本机 NotoSansSC-VF 反查番茄 PUA 字体映射

原理：番茄字体 name 表自称 "subset font of SourceHanSansSC-Normal"，
     而 Source Han Sans SC 与 Noto Sans SC 是 Adobe/Google 同源同一套字形设计。
     所以 PUA 码位的字形轮廓 == NotoSansSC 里某个汉字的轮廓。

改进的指纹：对轮廓点做「包围盒归一化 + 栅格化」，对坐标变换不敏感。
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.varLib.instancer import instantiateVariableFont

FONT_DIR = r"D:\DSHworkspace\B站\情报\_font_probe"
FQ_PATH = os.path.join(FONT_DIR, "ch1_dc027189e0ba4cd.woff2")
NOTO = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def sig(glyphset, gname, grid=10):
    """包围盒归一化 + 栅格化指纹；同时返回点数与长宽比用于消歧。"""
    pen = RecordingPen()
    try:
        glyphset[gname].draw(pen)
    except Exception:
        return None
    pts = []
    for op, args in pen.value:
        for a in args:
            if isinstance(a, tuple) and len(a) == 2 and all(isinstance(v, (int, float)) for v in a):
                pts.append(a)
    if len(pts) < 4:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w, h = maxx - minx, maxy - miny
    if w < 30 or h < 30:
        return None
    cells = frozenset(
        (min(grid - 1, int((x - minx) / w * grid)), min(grid - 1, int((y - miny) / h * grid))) for x, y in pts
    )
    return (len(pts), cells, round(w / h, 1))


print("=== 1. 加载番茄字体 ===")
fq = TTFont(FQ_PATH)
fq_cmap = fq.getBestCmap()
fq_gs = fq.getGlyphSet()
pua = [cp for cp in sorted(fq_cmap) if 0xE000 <= cp <= 0xF8FF]
print(f"   PUA 码位 {len(pua)} 个, unitsPerEm={fq['head'].unitsPerEm}")

print("\n=== 2. 加载 NotoSansSC-VF 并实例化到 Regular(400) ===")
vtt = TTFont(NOTO)
print("   fvar 轴:", [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in vtt["fvar"].axes])
stat = vtt.getBestCmap()
print("   汉字数:", sum(1 for cp in stat if CJK.match(chr(cp))))

# 尝试几个重量，命中率最高的那个就是番茄用的
results = {}
for wght in [400, 300, 350, 500]:
    try:
        inst = instantiateVariableFont(TTFont(NOTO), {"wght": wght}, inplace=False, updateFontNames=False)
    except Exception as e:
        print(f"   [wght={wght}] 实例化失败: {e}")
        continue
    rgs = inst.getGlyphSet()
    rcmap = inst.getBestCmap()
    table = {}
    n = 0
    for cp, gname in rcmap.items():
        if not CJK.match(chr(cp)):
            continue
        s = sig(rgs, gname)
        if s is None:
            continue
        table.setdefault(s, []).append(chr(cp))
        n += 1
    hit, mapping, miss = 0, {}, []
    for cp in pua:
        s = sig(fq_gs, fq_cmap[cp])
        if s is None:
            miss.append(cp)
            continue
        cands = table.get(s)
        if cands:
            hit += 1
            mapping[cp] = cands[0]
        else:
            miss.append(cp)
    rate = 100 * hit / len(pua)
    print(f"   [wght={wght}] 参照汉字 {n}  命中 {hit}/{len(pua)} = {rate:.1f}%")
    results[wght] = (hit, mapping, miss)

best_w = max(results, key=lambda k: results[k][0])
hit, mapping, miss = results[best_w]
print(f"\n>>> 最佳重量 wght={best_w}  命中 {hit}/{len(pua)} = {100*hit/len(pua):.1f}%")

out_json = os.path.join(FONT_DIR, "解码映射表.json")
json.dump(
    {
        "font_self_id": "SourceHanSansSC-Normal (subset)",
        "ref_font": f"NotoSansSC-VF wght={best_w}",
        "pua_total": len(pua),
        "hit": hit,
        "miss": [f"{c:04X}" for c in miss],
        "mapping": {f"{c:04X}": v for c, v in mapping.items()},
    },
    open(out_json, "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)
print("   映射表 ->", out_json)

# ---- 闭环验证：拿第1章真实 PUA 正文解密 ----
print("\n=== 3. 闭环验证：解密真实章节正文 ===")
import re as _re

PROBE = os.path.join(FONT_DIR, "chapter_sample.json")
if os.path.exists(PROBE):
    d = json.load(open(PROBE, encoding="utf-8"))
    raw = d.get("content", "")
    plain = _re.sub(r"<[^>]+>", "", raw)
    mp = mapping
    dec = "".join(mp.get(ord(c), c) if 0xE000 <= ord(c) <= 0xF8FF else c for c in plain)
    left = len(_re.findall(r"[\ue000-\uf8ff]", dec))
    print(f"   原文字符 {len(plain)}  解密后残留 PUA {left}")
    print(f"   原文(密) 前120: {plain[:120]}")
    print(f"   解密后   前120: {dec[:120]}")
else:
    print("   (没有 chapter_sample.json，跳过；先用字体自身的 PUA 序列做冒烟测试)")
    s = "".join(chr(c) for c in pua[:60])
    print("   冒烟:", "".join(mapping.get(ord(c), "?") for c in s))

# ---- HTML 对照表（人工核验）----
rows = [(cp, mapping.get(cp, "?")) for cp in pua]
h = [
    "<meta charset='utf-8'><style>body{font-family:sans-serif}",
    "table{border-collapse:collapse;font-size:12px}",
    "td{border:1px solid #ddd;padding:2px 5px;text-align:center}",
    ".fq{font-size:24px;color:#c00}.ok{font-size:24px;color:#080}</style>",
    f"<h3>番茄 PUA 字形 → NotoSansSC 反查  命中 {hit}/{len(pua)} ({100*hit/len(pua):.1f}%)</h3>",
    "<p>红色=番茄字体渲染的密文字形；绿色=反查出的真汉字。两者视觉一致即解密正确。</p>",
    "<table>",
]
for i in range(0, len(rows), 6):
    h.append("<tr>")
    for cp, ch in rows[i : i + 6]:
        h.append(f"<td>U+{cp:04X}</td><td class='fq'>&#x{cp:04X};</td><td class='ok'>{ch}</td>")
    h.append("</tr>")
h.append("</table>")
hp = os.path.join(FONT_DIR, "对照表.html")
open(hp, "w", encoding="utf-8").write("\n".join(h))
print("   HTML 对照表 ->", hp)
