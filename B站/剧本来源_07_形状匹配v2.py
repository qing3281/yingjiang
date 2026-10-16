# -*- coding: utf-8 -*-
"""
剧本来源探针 07 —— v2 形状匹配（栅格化 + 汉明距离）

v1 用「精确轮廓坐标指纹」命中率只有 1.9%，说明番茄字体（SourceHanSansSC v2.002 / makeotf）
与 本机 NotoSansSC-VF 存在微小坐标扰动。
v2 改为：把字形轮廓栅格化成归一化 N×N 位图，用位图做匹配 —— 对微小扰动免疫。

同时用 hmtx advance width 做预筛，把候选集从 27000 压到几百，速度提升 10 倍以上。
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.varLib.instancer import instantiateVariableFont

FONT_DIR = r"D:\DSHworkspace\B站\情报\_font_probe"
FQ = os.path.join(FONT_DIR, "ch1_dc027189e0ba4cd.woff2")
NOTO = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
N = 24  # 位图边长


def outline_polys(glyphset, gname):
    """返回 [(contour_pts, closed)]，contour 为 (x,y) 列表"""
    pen = RecordingPen()
    try:
        glyphset[gname].draw(pen)
    except Exception:
        return None, None
    polys, cur, start = [], [], None
    for op, args in pen.value:
        if op == "moveTo":
            if cur:
                polys.append(cur)
            cur = [args[0]]
            start = args[0]
        elif op == "lineTo":
            cur.append(args[0])
        elif op == "curveTo":
            # 用折线近似（6 段足够 24x24 栅格）
            p0 = cur[-1]
            c1, c2, p3 = args[-3], args[-2], args[-1]
            for i in range(1, 7):
                t = i / 6
                mt = 1 - t
                x = mt**3 * p0[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * p3[0]
                y = mt**3 * p0[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * p3[1]
                cur.append((x, y))
        elif op in ("closePath", "endPath"):
            if cur:
                polys.append(cur)
                cur = []
    if cur:
        polys.append(cur)
    if not polys:
        return None, None
    xs = [p[0] for pl in polys for p in pl]
    ys = [p[1] for pl in polys for p in pl]
    return polys, (min(xs), min(ys), max(xs), max(ys))


def to_bitmap(glyphset, gname, n=N):
    polys, bbox = outline_polys(glyphset, gname)
    if not polys or not bbox:
        return None
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    if w < 30 or h < 30:
        return None
    bits = 0
    for gy in range(n):
        cy = y0 + (gy + 0.5) / n * h
        for gx in range(n):
            cx = x0 + (gx + 0.5) / n * w
            inside = False
            for pl in polys:
                m = len(pl)
                for i in range(m):
                    ax, ay = pl[i]
                    bx, by = pl[(i + 1) % m]
                    if (ay > cy) != (by > cy):
                        xint = ax + (cy - ay) / (by - ay) * (bx - ax)
                        if xint > cx:
                            inside = not inside
            if inside:
                bits |= 1 << (gy * n + gx)
    return bits


def popcount(x):
    return bin(x).count("1")


print("=== 加载番茄字体 ===")
fq = TTFont(FQ)
fqcmap = fq.getBestCmap()
fqgs = fq.getGlyphSet()
fqhm = fq["hmtx"]
pua = [cp for cp in sorted(fqcmap) if 0xE000 <= cp <= 0xF8FF]
fqbits = {}
fqw = {}
t0 = time.time()
for cp in pua:
    b = to_bitmap(fqgs, fqcmap[cp])
    if b is not None:
        fqbits[cp] = b
        fqw[cp] = fqhm[fqcmap[cp]][0]
print(f"   {len(fqbits)}/{len(pua)} 个 PUA 位图化成功，耗时 {time.time()-t0:.1f}s")

# 收集番茄字体的 advance width 集合，用于预筛容差
ref_widths = sorted(set(fqw.values()))
print("   PUA advance width 取值:", ref_widths[:20])

for WGHT in [400, 500]:
    print(f"\n=== 参照字体 NotoSansSC-VF @ wght={WGHT} ===")
    vtt = TTFont(NOTO)
    inst = instantiateVariableFont(vtt, {"wght": WGHT}, inplace=False, updateFontNames=False)
    rgs = inst.getGlyphSet()
    rcmap = inst.getBestCmap()
    rhm = inst["hmtx"]

    # 按 advance width 分桶预筛（容差 ±2）
    t0 = time.time()
    ref = {}
    for cp, gname in rcmap.items():
        if not (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF):
            continue
        ref.setdefault(rhm[gname][0], []).append((chr(cp), gname))
    print(f"   参照汉字 {sum(len(v) for v in ref.values())} 个，按宽度分 {len(ref)} 桶，耗时 {time.time()-t0:.1f}s")

    # 只对「宽度在 ref 桶里存在」的 PUA 做匹配
    wset = set(ref.keys())
    # 为了宽容，允许 ±3 的宽度差
    cache = {}
    hit, mapping, miss = 0, {}, []
    for cp in pua:
        if cp not in fqbits:
            continue
        w = fqw[cp]
        cands = []
        for dw in range(-3, 4):
            cands.extend(ref.get(w + dw, []))
        if not cands:
            miss.append(cp)
            continue
        fb = fqbits[cp]
        best, bestd = None, 10**9
        for ch, gname in cands:
            key = gname
            if key not in cache:
                cache[key] = to_bitmap(rgs, gname)
            rb = cache[key]
            if rb is None:
                continue
            d = popcount(fb ^ rb)
            if d < bestd:
                bestd, best = d, ch
                if d == 0:
                    break
        # 接受阈值：错位像素 < 6% 面积
        if best is not None and bestd <= int(0.06 * N * N):
            hit += 1
            mapping[cp] = (best, bestd)
        else:
            miss.append(cp)
    rate = 100 * hit / len(pua)
    print(f"   ✔ 命中 {hit}/{len(pua)} = {rate:.1f}%   (最佳距离分布见下)")
    ds = sorted(v[1] for v in mapping.values())
    if ds:
        print(f"     匹配距离: min={ds[0]} p50={ds[len(ds)//2]} max={ds[-1]}  (阈值 {int(0.06*N*N)})")
    print(f"     样例: " + ", ".join(f"U+{c:04X}→{v[0]}(d={v[1]})" for c, v in list(mapping.items())[:16]))

    out = os.path.join(FONT_DIR, f"解码映射表_wght{WGHT}.json")
    json.dump(
        {
            "ref": f"NotoSansSC-VF wght={WGHT}",
            "hit": hit,
            "total": len(pua),
            "mapping": {f"{c:04X}": v[0] for c, v in mapping.items()},
            "dist": {f"{c:04X}": v[1] for c, v in mapping.items()},
        },
        open(out, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    print("     映射表 ->", out)

    if rate > 60:
        # 生成人工核验对照表
        rows = [(c, mapping.get(c)) for c in pua]
        h = [
            "<meta charset='utf-8'><style>body{font-family:sans-serif;font-size:12px}",
            "table{border-collapse:collapse}td{border:1px solid #ddd;padding:2px 5px;text-align:center}",
            ".fq{font-size:26px;color:#c00}.ok{font-size:26px;color:#080}</style>",
            f"<h3>番茄 PUA 字形(红) vs NotoSansSC@{WGHT} 反查结果(绿) — 命中 {hit}/{len(pua)}</h3>",
            "<table>",
        ]
        for i in range(0, len(rows), 6):
            h.append("<tr>")
            for c, r in rows[i : i + 6]:
                ch = r[0] if r else "?"
                h.append(f"<td>U+{c:04X}</td><td class='fq'>&#x{c:04X};</td><td class='ok'>{ch}</td>")
            h.append("</tr>")
        h.append("</table>")
        hp = os.path.join(FONT_DIR, f"对照表_wght{WGHT}.html")
        open(hp, "w", encoding="utf-8").write("\n".join(h))
        print("     对照表 ->", hp)
