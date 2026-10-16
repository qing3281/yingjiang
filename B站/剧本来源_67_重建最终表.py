# -*- coding: utf-8 -*-
"""
探针 67 —— 用公开权威表重建最终映射表，然后端到端验收

关键发现（探针 66）：
  公开表 ying-ck/fanqienovel-downloader 的 src/charset.json 子表0 是按
  「U+E3E8 + index」硬对齐的，但字体 cmap 在区间内有 10 个空洞
  (U+E3F6/E3FE/E3FF/E419/E45B/E4B6/E4D4/E4D8/E51A/E51F)，
  公开表在这 10 处没留空位，导致 U+E51C 之后**整体错位一格**。
  所以正确修正 = 把这些空洞插回去。

本脚本：
  1. 下载公开表
  2. 按真实 cmap 顺序重排（把 10 个空洞的位置算进去）
  3. 与现有 map_shift 互补，生成 pua_map_v2.json
  4. 抓真章解密，与旧表做短语命中/高频字对比
"""
import base64
import html as _h
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
import certifi
import urllib.request as u
from fontTools.ttLib import TTFont

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)
from curl_cffi import requests as creq

FP = r"D:\DSHworkspace\B站\情报\_font_probe"
UA = {"User-Agent": "probe", "Accept": "application/vnd.github+json"}

# ---- 1. 取公开表 ----
r = u.Request("https://api.github.com/repos/ying-ck/fanqienovel-downloader/"
              "contents/src/charset.json", headers=UA)
pub = json.loads(base64.b64decode(
    json.loads(u.urlopen(r, timeout=25).read())["content"]
).decode("utf-8"))[0]
print(f"公开表 {len(pub)} 项")

# ---- 2. 按真实 cmap 顺序重排（插入 10 个空洞）----
f = TTFont(os.path.join(FP, "fq_subset.ttf"))
ordered = sorted(c for c in f.getBestCmap() if 0xE000 <= c <= 0xF8FF)
gaps = set(range(0xE3E8, 0xE55C)) - set(ordered)
print(f"字体 cmap {len(ordered)} 个，区间空洞 {len(gaps)} 个："
      + " ".join(f"U+{g:04X}" for g in sorted(gaps)))

V2 = {}
j = 0
for cp in range(0xE3E8, 0xE55C):
    if cp in gaps:
        continue                      # 空洞不占公开表的位
    if j < len(pub):
        ch = pub[j]
        if ch and ch != "?":
            V2[cp] = ch
    j += 1
print(f"重排得 {len(V2)} 项")

OLD = {int(k, 0): v for k, v in json.load(open(
    os.path.join(FP, "map_shift.json"), encoding="utf-8"))["map"].items()}
print(f"旧表 {len(OLD)} 项；两者都有 {len(set(V2) & set(OLD))}，"
      f"新表补齐旧表缺的 {len(set(V2) - set(OLD))}，"
      f"旧表独有 {len(set(OLD) - set(V2))}")

# ---- 3. 合并：公开表优先，缺的用旧表兜 ----
MERGED = dict(OLD)
MERGED.update(V2)
json.dump({str(k): v for k, v in sorted(MERGED.items())},
          open(os.path.join(FP, "pua_map_v2.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"合并 -> pua_map_v2.json：{len(MERGED)} 项")

# ---- 4. 端到端验收 ----
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209",
            "7137980469551104526", "7138408581975507491"]:
    rr = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H,
               timeout=25, verify=CAB)
    raws.append(_h.unescape(re.sub(r"<[^>]+>", "",
                 "".join(re.findall(r"<p>(.*?)</p>", rr.text, re.S)))))
raw = "\n".join(raws)
print(f"\n语料 {len(raw)} 字")

PH = ["什么", "怎么", "已经", "不是", "一个", "我们", "自己", "因为", "所以",
      "但是", "可以", "没有", "知道", "觉得", "时候", "出来", "起来", "男人",
      "女人", "看着", "说道", "眼睛", "心里", "身体", "有些", "一点", "一样",
      "这样", "真的", "看见", "声音", "地方", "突然", "开始", "最后", "表情",
      "眼神", "身上", "那个", "这个", "下来", "上来", "轻轻", "微微", "忽然"]
EXP = "的一了是我不你在他人有着个这她上就都而及与说们来到时大地为子中"


def ev(tab, name):
    dec = "".join(tab.get(ord(c), c) for c in raw)
    ph = sum(dec.count(p) for p in PH)
    cjk = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
    top = [ch for ch, _ in cjk.most_common(24)]
    hit = sum(1 for ch in top if ch in EXP)
    print(f"  {name:12s} 短语命中 {ph:4d}   前24高频命中 {hit}/24")
    print(f"               前24：{' '.join(top)}")
    return dec


print("\n对比：")
ev(OLD, "旧表 map_shift")
dec2 = ev(MERGED, "新表 pua_map_v2")
print(f"\n=== 新表成品 ===\n{dec2[:400]}")
