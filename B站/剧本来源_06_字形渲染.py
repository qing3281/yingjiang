# -*- coding: utf-8 -*-
"""
剧本来源探针 06 —— 字体坐标诊断 + 渲染成图（视觉解码路线）

问题：轮廓指纹反查命中率仅 1.9%，怀疑是 unitsPerEm 缩放不一致而非字形不同。
诊断：把同一个字的番茄字形 与 NotoSans 字形 都导出成 SVG path，比较坐标量级。

并且给出「一定可行」的路子：用 PIL 把番茄字体的每个 PUA 字形渲染成 PNG 拼图，
交给任何 OCR / 视觉模型识别 —— 因为这些字形本来就是标准黑体汉字。
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen

FONT_DIR = r"D:\DSHworkspace\B站\情报\_font_probe"
FQ = os.path.join(FONT_DIR, "ch1_dc027189e0ba4cd.woff2")
NOTO = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"

fq = TTFont(FQ)
fqcmap = fq.getBestCmap()
fqgs = fq.getGlyphSet()

print("=== 诊断 1：番茄字体的 hhea / head 指标 ===")
h = fq["head"]
print("  unitsPerEm:", h.unitsPerEm, " xMin/yMin/xMax/yMax:", h.xMin, h.yMin, h.xMax, h.yMax)
hh = fq["hhea"]
print("  hhea ascender/descender/lineGap:", hh.ascender, hh.descender, hh.lineGap)
os2 = fq["OS/2"]
print("  OS/2 winAscent/winDescent:", os2.usWinAscent, os2.usWinDescent)
print("  OS/2 sTypoAscender/Descender:", os2.sTypoAscender, os2.sTypoDescender)
print("  OS/2 usWeightClass:", os2.usWeightClass, " fsSelection:", bin(os2.fsSelection))

print("\n=== 诊断 2：番茄字形 vs Noto 字形 的 scale/bounds 对比 ===")
# 取番茄字体里若干 PUA，输出其 bounds
from fontTools.pens.boundsPen import BoundsPen

fqpua = [cp for cp in sorted(fqcmap) if 0xE000 <= cp <= 0xF8FF]
print(f"{'PUA':>8} {'fq_bounds':>28}  {'fq_scale':>9}")
samples = []
for cp in fqpua[:12]:
    gname = fqcmap[cp]
    bp = BoundsPen(fqgs)
    fqgs[gname].draw(bp)
    w = (bp.bounds[2] - bp.bounds[0]) if bp.bounds else None
    hgt = (bp.bounds[3] - bp.bounds[1]) if bp.bounds else None
    sc = round(max(w, hgt) / fq["head"].unitsPerEm, 4) if bp.bounds else None
    print(f"  U+{cp:04X} {str(bp.bounds):>28}  {sc}")
    samples.append(cp)

print("\n=== 诊断 3：番茄字体是否有 hmtx 宽度异常（值越大越可能是缩放问题）===")
hm = fq["hmtx"]
widths = [hm[fqcmap[cp]][0] for cp in fqpua[:40]]
print("  前 40 个 PUA 的 advance width:", sorted(set(widths))[:15], "...")

print("\n=== 诊断 4：PIL 渲染 PUA 字形 -> PNG 拼图（视觉解码路线）===")
try:
    from PIL import Image, ImageDraw, ImageFont

    print("  Pillow 可用")
    # PIL 能直接读 woff2 吗？通常不能，需要转成 ttf
    ttf_path = os.path.join(FONT_DIR, "fq_subset.ttf")
    if not os.path.exists(ttf_path):
        fq.flavor = None
        fq.save(ttf_path)
        print("  已把 woff2 转存为 ttf:", ttf_path, os.path.getsize(ttf_path))
    font = ImageFont.truetype(ttf_path, 48)
    cols, cell = 14, 64
    n = len(fqpua)
    rows = (n + cols - 1) // cols
    img = Image.new("RGB", (cols * cell, rows * (cell + 18)), "white")
    dr = ImageDraw.Draw(img)
    try:
        lbl = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 11)
    except Exception:
        lbl = None
    for i, cp in enumerate(fqpua):
        cx = (i % cols) * cell
        cy = (i // cols) * (cell + 18)
        try:
            dr.text((cx + 6, cy + 4), chr(cp), font=font, fill="black")
        except Exception:
            pass
        dr.text((cx + 3, cy + cell), f"{cp:04X}", font=lbl, fill=(150, 0, 0))
    png = os.path.join(FONT_DIR, "PUA字形总表.png")
    img.save(png)
    print("  ✔ 生成字形总表:", png, img.size)

    # 小样图：前 70 个，放大，方便人眼/OCR 识别
    n2, cols2, cell2 = min(70, n), 10, 96
    rows2 = (n2 + cols2 - 1) // cols2
    img2 = Image.new("RGB", (cols2 * cell2, rows2 * (cell2 + 20)), "white")
    d2 = ImageDraw.Draw(img2)
    f2 = ImageFont.truetype(ttf_path, 72)
    for i in range(n2):
        cp = fqpua[i]
        cx = (i % cols2) * cell2
        cy = (i // cols2) * (cell2 + 20)
        d2.text((cx + 8, cy + 6), chr(cp), font=f2, fill="black")
        d2.text((cx + 8, cy + cell2), f"U+{cp:04X}", font=lbl, fill=(150, 0, 0))
    png2 = os.path.join(FONT_DIR, "PUA小样70.png")
    img2.save(png2)
    print("  ✔ 生成小样图:", png2, img2.size)

    # ---- 关键：能否用「同字体渲染真汉字」做自校验？----
    # 思路：番茄字体里 PUA 是密文；但正文里混有少量未被替换的汉字。
    #       若能在同一字体里找到「某个 PUA 字形 == 某个已知汉字字形」，
    #       就说明番茄字体内部同时含明文与密文字形。测一下：
    known = {}
    from fontTools.pens.recordingPen import RecordingPen as RP

    def sig(gs, gn):
        pen = RP()
        try:
            gs[gn].draw(pen)
        except Exception:
            return None
        pts = []
        for op, args in pen.value:
            for a in args:
                if isinstance(a, tuple) and len(a) == 2 and all(isinstance(v, (int, float)) for v in a):
                    pts.append(a)
        if len(pts) < 4:
            return None
        return tuple(sorted((round(x, 1), round(y, 1)) for x, y in pts))

    han_sigs = {}
    for cp, gn in fqcmap.items():
        if 0x4E00 <= cp <= 0x9FFF:
            s = sig(fqgs, gn)
            if s:
                han_sigs.setdefault(s, []).append(chr(cp))
    internal = 0
    for cp in fqpua:
        s = sig(fqgs, fqcmap[cp])
        if s in han_sigs:
            internal += 1
    print(f"\n  番qie 字体内部：明文汉字 {len(han_sigs)} 个不同的字形")
    print(f"  PUA 字形与「字体自带的明文汉字字形」重合数: {internal} / {n}")
    print("  => 若 >0，说明字体里同时有明文和密文，可直接自解；若 =0，必须外部参照/OCR")

except ImportError as e:
    print("  [SKIP] Pillow 未安装:", e)
