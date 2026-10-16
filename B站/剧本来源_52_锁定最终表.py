# -*- coding: utf-8 -*-
"""探针 52 —— 把最终映射表锁死到已验证的 map_shift 基线，并做成品验收"""
import html as _h
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)
from curl_cffi import requests as creq

FP = r"D:\DSHworkspace\B站\情报\_font_probe"
BASE = {int(k, 0): v
        for k, v in json.load(open(os.path.join(FP, "map_shift.json"),
                                   encoding="utf-8"))["map"].items()}
json.dump({str(k): v for k, v in sorted(BASE.items())},
          open(os.path.join(FP, "pua_map_final.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"锁定最终表：{len(BASE)} 项 -> pua_map_final.json")

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209",
            "7137980469551104526", "7138408581975507491"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H,
              timeout=25, verify=CAB)
    raws.append(_h.unescape(re.sub(r"<[^>]+>", "",
                 "".join(re.findall(r"<p>(.*?)</p>", r.text, re.S)))))
raw = "\n".join(raws)
dec = "".join(BASE.get(ord(c), c) for c in raw)

PHRASES = ["什么", "怎么", "已经", "不是", "一个", "我们", "自己", "因为",
           "所以", "但是", "可以", "没有", "知道", "觉得", "时候", "出来",
           "起来", "男人", "女人", "看着", "说道", "眼睛", "心里", "身体",
           "有些", "一点", "一样", "这样", "真的", "看见", "声音", "地方",
           "突然", "开始", "最后", "表情", "眼神", "身上"]
print(f"语料 {len(raw)} 字，短语命中 {sum(dec.count(p) for p in PHRASES)}/38")
print(f"残留 PUA {sum(1 for c in dec if 0xE000 <= ord(c) <= 0xF8FF)} 个")
cjk = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
print("最高频 20 字：", "".join(ch for ch, _ in cjk.most_common(20)))
print("\n=== 成品 ===")
print(dec[:400])
