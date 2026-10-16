# -*- coding: utf-8 -*-
"""
剧本来源探针 04 —— 字体混淆是否可解？(可行性验证，不做全量解密)

思路：
  番茄的动态字体是把「真汉字」的字形搬到一个随机 PUA 码位上。
  所以 PUA 码位的「字形轮廓」== 某个已知字体里某个汉字的轮廓。
  只要拿一个参照字体（宋体/黑体）逐字比轮廓，就能测出映射。

本脚本：
  1) 读取 woff2 的 name 表，看字体自称
  2) 加载系统参照字体（simsun.ttc / msyh.ttc / simhei.ttf）
  3) 对番茄字体里每一个 PUA 码位，用「轮廓点集归一化后做形状哈希」在参照字体里反查
  4) 统计命中率 —— 命中率高即证明混淆可逆
  5) 输出 解码映射表.json + 一张 HTML 对照表（人工可核验）
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen

FONT_DIR = r"D:\DSHworkspace\B站\情报\_font_probe"
os.makedirs(FONT_DIR, exist_ok=True)

REF_CANDIDATES = [
    (r"C:\Windows\Fonts\simsun.ttc", "SimSun"),
    (r"C:\Windows\Fonts\simhei.ttf", "SimHei"),
    (r"C:\Windows\Fonts\msyh.ttc", "MicrosoftYaHei"),
    (r"C:\Windows\Fonts\simkai.ttf", "KaiTi"),
    (r"C:\Windows\Fonts\simfang.ttf", "FangSong"),
    (r"C:\Windows\Fonts\Deng.ttf", "DengXian"),
]
REF_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

# ---- 找番茄字体 ----
fq = [f for f in os.listdir(FONT_DIR) if f.endswith(".woff2") and f.startswith("ch1")]
if not fq:
    fq = [f for f in os.listdir(FONT_DIR) if f.endswith(".woff2") and f.startswith("probe")]
FQ_PATH = os.path.join(FONT_DIR, fq[0])
print("番茄字体文件:", FQ_PATH, os.path.getsize(FQ_PATH), "bytes")

tt = TTFont(FQ_PATH)
print("\n=== 字体 name 表（自称身份）===")
for rec in tt["name"].names[:24]:
    try:
        print(f"   [{rec.nameID}] {rec.toUnicode()[:90]}")
    except Exception:
        pass
print("   unitsPerEm:", tt["head"].unitsPerEm, "| glyph 总数:", tt["maxp"].numGlyphs)
print("   OS/2 typo:", getattr(tt["OS/2"], "sTypoAscender", None), getattr(tt["OS/2"], "sTypoDescender", None))
print("   是否有 GSUB/GPOS:", "GSUB" in tt, "GPOS" in tt)


def outline_sig(glyphset, gname, grid=8):
    """把字形轮廓归一化后栅格化成位串 -> 形状指纹，与字号/坐标缩放无关。"""
    pen = RecordingPen()
    try:
        glyphset[gname].draw(pen)
    except Exception:
        return None
    pts = []
    for op, args in pen.value:
        for a in args:
            if isinstance(a, tuple) and len(a) == 2:
                pts.append(a)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w = max(maxx - minx, 1)
    h = max(maxy - miny, 1)
    if w < 20 or h < 20:  # 空白/标点忽略
        return None
    cells = set()
    for x, y in pts:
        cx = int((x - minx) / w * (grid - 1))
        cy = int((y - miny) / h * (grid - 1))
        cells.add((cx, cy))
    # 用「相对位置点集」做指纹：排序后的坐标对（不碰撞的概率极低）
    return (len(pts), tuple(sorted(cells)), round(w / h, 2))


def build_ref(ref_path, label):
    """建立 参照字体 形状指纹 -> 汉字 的反查表"""
    try:
        rtt = TTFont(ref_path, fontNumber=0)
    except Exception as e:
        print(f"  [SKIP] {label}: {e}")
        return None
    cmap = rtt.getBestCmap()
    gs = rtt.getGlyphSet()
    table = {}
    n = 0
    for cp, gname in cmap.items():
        if not REF_CJK.match(chr(cp)):
            continue
        sig = outline_sig(gs, gname)
        if sig is None:
            continue
        table.setdefault(sig, []).append(chr(cp))
        n += 1
    print(f"  [{label}] 汉字字形数: {n}  唯一指纹数: {len(table)}")
    return table


print("\n=== 加载系统参照字体 ===")
refs = {}
for p, lb in REF_CANDIDATES:
    if os.path.exists(p):
        t = build_ref(p, lb)
        if t:
            refs[lb] = t
    else:
        print(f"  [MISS] {p} 不存在")

fq_cmap = tt.getBestCmap()
fq_gs = tt.getGlyphSet()
pua = [cp for cp in sorted(fq_cmap) if 0xE000 <= cp <= 0xF8FF]
print(f"\n=== 番茄字体 PUA 码位: {len(pua)} 个 ===")

print("\n=== 逐字体反查命中率 ===")
best = (None, 0, {})
for lb, table in refs.items():
    hit, mapping = 0, {}
    for cp in pua:
        sig = outline_sig(fq_gs, fq_cmap[cp])
        if sig is None:
            continue
        cands = table.get(sig)
        if cands:
            hit += 1
            mapping[cp] = cands[0]
    rate = 100 * hit / len(pua)
    print(f"  {lb:18s} 命中 {hit:4d}/{len(pua)}  = {rate:5.1f}%")
    if hit > best[1]:
        best = (lb, hit, mapping)

lb, hit, mapping = best
print(f"\n>>> 最佳参照字体: {lb}  命中 {hit}/{len(pua)} = {100*hit/len(pua):.1f}%")

out = os.path.join(FONT_DIR, "解码映射表.json")
json.dump(
    {
        "source_font": os.path.basename(FQ_PATH),
        "ref_font": lb,
        "pua_total": len(pua),
        "hit": hit,
        "mapping": {f"{k:04X}": v for k, v in mapping.items()},
    },
    open(out, "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=1,
)
print("    映射表已写入:", out)

# 用映射表试解密第 1 章正文
import glob

txt = None
for cand in glob.glob(os.path.join(FONT_DIR, "..", "..", "*.json")):
    pass


def decrypt(s, mp):
    return "".join(mp.get(ord(ch), ch) if 0xE000 <= ord(ch) <= 0xF8FF else ch for ch in s)


MAP2 = mapping
print("\n=== 用映射表解密示例（字符来自番茄字体本身，验证闭环）===")
print("  解密后前 40 字:", decrypt("".join(chr(c) for c in pua[:40]), MAP2))

# 生成 HTML 对照表，人工核验
html = ["<meta charset='utf-8'><style>body{font-size:13px;font-family:monospace}"
        "table{border-collapse:collapse}td{border:1px solid #ccc;padding:3px 6px;text-align:center}"
        ".g{font-family:FQ;font-size:26px}.r{font-size:26px}</style>"
        "<h3>番茄 PUA 码位 → 反查汉字 对照表（前 120 个）</h3>"
        "<table><tr><th>码位</th><th>番茄字形</th><th>反查结果</th><th>码位</th><th>番茄字形</th><th>反查结果</th></tr>"]
rows = [(cp, mapping.get(cp, "")) for cp in pua[:120]]
for i in range(0, len(rows), 2):
    cells = []
    for cp, ch in rows[i : i + 2]:
        cells.append(f"<td>U+{cp:04X}</td><td class='g'>&#x{cp:04X};</td><td class='r'>{ch}</td>")
    html.append("<tr>" + "".join(cells) + "</tr>")
html.append("</table>")
hp = os.path.join(FONT_DIR, "对照表.html")
open(hp, "w", encoding="utf-8").write("\n".join(html))
print("    HTML 对照表:", hp)
