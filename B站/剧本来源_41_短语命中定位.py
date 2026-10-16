# -*- coding: utf-8 -*-
"""
探针 41 —— 用「固定短语命中数」客观定位错位区间

思路：不靠肉眼。中文小说里必然大量出现固定的二字/三字词。
对每一项都试「把映射在某个区间内平移 k 格」，选命中数最高的方案。
"""
import html as _html
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
import fanqie_font

BASE = {}
for k, v in fanqie_font.PUA2CHAR.items():
    if isinstance(k, int):
        BASE[k] = v
    else:
        try:
            BASE[int(k, 0)] = v
        except (ValueError, TypeError):
            pass

from curl_cffi import requests as creq
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526",
            "7138408581975507491"]:
    t = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25).text
    raws.append(_html.unescape(re.sub(r"<[^>]+>", "", "".join(re.findall(r"<p>(.*?)</p>", t, re.S)))))
raw = "\n".join(raws)
codes = sorted(BASE)
print(f"语料 {len(raw)} 字，映射 {len(codes)} 条\n")

PHRASES = ["什么", "怎么", "这里", "那里", "已经", "不是", "一个", "我们", "你们",
           "他们", "自己", "因为", "所以", "但是", "如果", "可以", "没有", "知道",
           "觉得", "时候", "出来", "进去", "起来", "下来", "过来", "男人", "女人",
           "看着", "说道", "一声", "眼睛", "心里", "身体", "有些", "一点", "一样",
           "这样", "那样", "真的", "还是", "看见", "听到", "抬头", "低头", "起来"]


def hits(dec):
    return sum(dec.count(p) for p in PHRASES)


# 基线
base_dec = "".join(BASE.get(ord(c), c) for c in raw)
print(f"基线（现有映射）短语命中 {hits(base_dec)}\n")

print("== 尝试：把映射表在【所有码位】上整体平移 k ==")
for k in range(-4, 5):
    m = {cp: BASE.get(cp + k, BASE[cp]) for cp in codes}
    dec = "".join(m.get(ord(c), c) for c in raw)
    print(f"  k={k:+d}  命中 {hits(dec):4d}   {dec[60:130]}")

print("\n== 尝试：只在给定区间内平移 k（其余不动）==")
best = None
for lo, hi in [(0xE3E8, 0xE55B), (0xE3F8, 0xE55B), (0xE400, 0xE55B),
               (0xE440, 0xE55B), (0xE480, 0xE55B), (0xE3E8, 0xE4A0),
               (0xE3E8, 0xE440), (0xE3E8, 0xE500), (0xE400, 0xE4C0)]:
    codes_in = [c for c in codes if lo <= c <= hi]
    for k in (-2, -1, 1, 2):
        m = dict(BASE)
        for cp in codes_in:
            tgt = cp + k
            m[cp] = BASE.get(tgt, BASE[cp])
        dec = "".join(m.get(ord(c), c) for c in raw)
        h = hits(dec)
        tag = f"[{lo:04X},{hi:04X}] k={k:+d}"
        if best is None or h > best[0]:
            best = (h, tag, dec)
        if h > hits(base_dec):
            print(f"  {tag}  命中 {h:4d} ★   {dec[60:150]}")

print(f"\n最佳：{best[1]}  命中 {best[0]}")
print(f"\n=== 最佳方案解码样本 ===\n{best[2][:500]}")
