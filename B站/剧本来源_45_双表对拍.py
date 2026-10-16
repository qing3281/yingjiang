# -*- coding: utf-8 -*-
"""
探针 45 —— 三张候选映射表 A/B 对拍，用「真实语料可读性」定胜负

候选：
  B = 情报/_font_probe/map_shift.json （旧表，来源于最初 11 列网格转录）
  A = fanqie_novel.py 里的权威字形表转录（12 列网格）

裁决标准（客观）：
  1. 出现次数最高的 24 个码位，其「字体渲染字形」是否等于该表声称的字
     （左半靠字形图对账 / 右半靠上下文短语命中）
  2. 中文短语命中数（什么/自己/眼睛/看着/因为/…）
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import certifi

_CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(_CAB):
    import shutil
    shutil.copy(certifi.where(), _CAB)

sys.path.insert(0, r"D:\DSHworkspace\B站")
import fanqie_novel as F
import json

B = {int(k, 0): v for k, v in json.load(
    open(r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json", encoding="utf-8"))["map"].items()}
A = dict(F.PUA2CHAR)

from curl_cffi import requests as creq
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526",
            "7138408581975507491"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25, verify=_CAB)
    raws.append(F.clean_chapter_text(r.text))
raw = "\n".join(raws)
print(f"语料 {len(raw)} 字\n")

PHRASES = ["什么", "怎么", "这里", "那里", "已经", "不是", "一个", "我们", "你们",
           "他们", "自己", "因为", "所以", "但是", "如果", "可以", "没有", "知道",
           "觉得", "时候", "出来", "进去", "起来", "下来", "过来", "男人", "女人",
           "看着", "说道", "一声", "眼睛", "心里", "身体", "有些", "一点", "一样",
           "这样", "那样", "真的", "还是", "看见", "听到", "抬头", "低头", "手指",
           "声音", "地方", "突然", "已经", "开始", "最后", "表情", "眼神", "身上"]


def dec(m):
    return "".join(m.get(ord(c), c) for c in raw)


def hits(d):
    return sum(d.count(p) for p in PHRASES)


for name, m in (("B(map_shift 旧表)", B), ("A(fanqie_novel 新表)", A)):
    d = dec(m)
    print(f"=== {name}：短语命中 {hits(d)} ===")
    print("   " + d[:260].replace("\n", " / "))
    print()

# 逐码位对账：高频码位下 A 与 B 的差异
from collections import Counter
cnt = Counter(c for c in raw if "\ue000" <= c <= "\uf8ff")
print("== 高频码位上 A 与 B 的分歧（看哪个更像上下文里的字）==")
shown = 0
for c, n in cnt.most_common(80):
    cp = ord(c)
    a, b = A.get(cp, "?"), B.get(cp, "?")

    def ctx(mm):
        d = dec(mm)
        i = d.find(mm.get(cp, "\uffff"))
        return d[max(0, i - 5):i + 6].replace("\n", "/") if i >= 0 else ""
    if a != b:
        shown += 1
        print(f"  U+{cp:04X} x{n:3d}  A={a}  B={b}    B上下文: {ctx(B)}")
        if shown >= 40:
            break
print(f"\n共列出 {shown} 处分歧")
