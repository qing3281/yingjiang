# -*- coding: utf-8 -*-
"""
探针 47 —— 频率合理性验收（判断映射表好坏最客观的尺子）

中文小说里，字频排名非常稳定：
   的 > 一 > 了 > 是 > 不 > 我 > 你 > 在 > 他 > 人 > 有 > 这 > 个 > 她 > 着 > 上 > ...
做法：拿 6000 字真实语料，统计解出每个汉字的次数，按次数降序排，
     与期望字频排名对比。错映射会立刻表现为「高频码位解出罕见字」。
"""
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)

sys.path.insert(0, r"D:\DSHworkspace\B站")
import json
import fanqie_novel as F
from curl_cffi import requests as creq

TABLES = {
    "A 权威字形表(fanqie_novel.py)": dict(F.PUA2CHAR),
    "B map_shift(旧)": {int(k, 0): v for k, v in json.load(
        open(r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json",
             encoding="utf-8"))["map"].items()},
}

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526",
            "7138408581975507491"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25, verify=CAB)
    raws.append(F.clean_chapter_text(r.text))
raw = "\n".join(raws)
print(f"语料 {len(raw)} 字\n")

# 中文小说字频期望顺序（前 24）
EXPECT = "的一了是我不你在他人有着个这她上就都而及与说们来到时大地为子中"
print(f"期望高频顺序: {EXPECT}\n")

for name, tab in TABLES.items():
    dec = "".join(tab.get(ord(c), c) for c in raw)
    cjk = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
    top = [ch for ch, _ in cjk.most_common(24)]
    # 打分：前 24 高频道出的字有多少落在期望集里
    inexp = sum(1 for ch in top if ch in EXPECT)
    # 位置吻合度：top[i] 在 EXPECT 中的序位与 i 的偏差
    dev = 0
    for i, ch in enumerate(top):
        j = EXPECT.find(ch)
        dev += abs(i - j) if j >= 0 else 24
    print(f"=== {name} ===")
    print(f"  前24高频字: {''.join(top)}")
    print(f"  落在期望集: {inexp}/24    序位总偏差: {dev} (越小越好)")
    print(f"  样本: {dec[:120]}".replace("\n", " "))
    print()
