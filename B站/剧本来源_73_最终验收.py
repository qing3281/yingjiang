# -*- coding: utf-8 -*-
"""探针 73 —— 最终验收：用锁定表跑真实章节 + 统计还原准确率"""
import html as _h
import json
import os
import re
import sys
import time
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)
from curl_cffi import requests as creq

FP = r"D:\DSHworkspace\B站\情报\_font_probe"
T = {int(k, 0): v for k, v in json.load(open(
    os.path.join(FP, "map_shift.json"), encoding="utf-8"))["map"].items()}
json.dump({str(k): v for k, v in sorted(T.items())},
          open(os.path.join(FP, "pua_map_final.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"最终映射表 pua_map_final.json：{len(T)} 项（= map_shift，已逐轮验过）")

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209",
            "7137980469551104526", "7138408581975507491"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H,
              timeout=30, verify=CAB)
    raws.append(_h.unescape(re.sub(r"<[^>]+>", "",
                 "".join(re.findall(r"<p>(.*?)</p>", r.text, re.S)))))
    time.sleep(1.5)
raw = "\n".join(raws)
dec = "".join(T.get(ord(c), c) for c in raw)

PH = ["什么", "怎么", "已经", "不是", "一个", "我们", "你们", "他们", "自己",
      "因为", "所以", "但是", "可以", "没有", "知道", "觉得", "时候", "出来",
      "起来", "下来", "男人", "女人", "看着", "说道", "眼睛", "心里", "身体",
      "有些", "一点", "一样", "这样", "真的", "看见", "听到", "声音", "地方",
      "突然", "开始", "最后", "表情", "眼神", "身上", "那个", "这个", "轻轻",
      "微微", "忽然", "其实", "要是", "不过", "而且", "或者", "然后", "接着"]
hits = {p: dec.count(p) for p in PH if dec.count(p) > 0}
print(f"\n语料 {len(raw)} 字；常见词命中 {len(hits)}/{len(PH)} 种，"
      f"总计 {sum(hits.values())} 次")
print("  命中词：", " ".join(f"{k}×{v}" for k, v in
                             sorted(hits.items(), key=lambda x: -x[1])[:18]))
cjk = Counter(c for c in dec if "\u4e00" <= c <= "\u9fff")
print(f"\n  最高频 20 字：{' '.join(c for c, _ in cjk.most_common(20))}")
print(f"  残留 PUA：{sum(1 for c in dec if 0xE000 <= ord(c) <= 0xF8FF)} 个")
print(f"\n=== 最终成品（前 500 字）===\n{dec[:500]}")
