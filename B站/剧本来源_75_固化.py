# -*- coding: utf-8 -*-
"""探针 75 —— 最终一轮修正 + 完整验收（样例输出用于报告引用）"""
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
    os.path.join(FP, "pua_map_final.json"), encoding="utf-8")).items()}

FIX = {
    0xE524: "修",  # 「身姿修长」——现为 '觉'
    0xE532: "修",  # 备选
    0xE523: "长",  # 「身姿修长」
    0xE522: "神",  # 「眼神」
    0xE51B: "情",  # 「表情」
    0xE51C: "才",  # 「刚才」
    0xE51D: "这",  # 「这样」
    0xE51E: "么",  # 「什么」
    0xE520: "格",  # 备选
    0xE521: "我",  # 「叫我」
    0xE526: "间",  # 「时间」
    0xE527: "年",  # 备选
    0xE528: "眼",  # 「眼睛」
    0xE529: "无",  # 备选
    0xE52B: "亲",  # 备选
    0xE52D: "结",  # 「结实」
    0xE52E: "友",  # 「朋友」
    0xE530: "信",  # 备选
    0xE533: "重",  # 备选
    0xE535: "老",  # 备选
    0xE541: "睛",  # 备选（眼 X）
    0xE54D: "方",  # 「方向」
    0xE54F: "英",  # 备选
    0xE551: "便",
    0xE552: "四",
    0xE553: "数",
    0xE557: "样",
    0xE558: "a",
    0xE559: "海",
    0xE55B: "任",
    0xE546: "起",
    0xE545: "9",
    0xE543: "太",
    0xE542: "目",
    0xE540: "P",
    0xE53F: "高",
    0xE539: "m",
    0xE538: "字",
    0xE53A: "呢",
    0xE53B: "明",
    0xE53C: "之",
}
old = dict(T)
T.update(FIX)
changed = {k: (old.get(k), v) for k, v in FIX.items() if old.get(k) != v}
json.dump({str(k): v for k, v in sorted(T.items())},
          open(os.path.join(FP, "pua_map_final.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"pua_map_final.json 固化：{len(T)} 项，本轮改动 {len(changed)} 项")

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
ids = ["7137980122702807592", "7137980233667314209", "7137980469551104526",
       "7138408581975507491", "7138408581975507492", "7138408581975507493"]
raws = []
for cid in ids:
    try:
        r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H,
                  timeout=30, verify=CAB)
        p = re.findall(r"<p>(.*?)</p>", r.text, re.S)
        if len(p) > 5:
            raws.append(_h.unescape(re.sub(r"<[^>]+>", "", "".join(p))))
    except Exception as e:
        print(f"   {cid} 失败 {str(e)[:40]}")
    time.sleep(1.5)
raw = "\n".join(raws)
dec = "".join(T.get(ord(c), c) for c in raw)

PH = ["什么", "怎么", "已经", "不是", "一个", "我们", "他们", "自己", "因为",
      "所以", "但是", "可以", "没有", "知道", "觉得", "时候", "出来", "起来",
      "下来", "男人", "女人", "看着", "说道", "眼睛", "心里", "身体", "有些",
      "一点", "一样", "这样", "真的", "看见", "听到", "声音", "地方", "突然",
      "开始", "最后", "表情", "眼神", "身上", "那个", "这个", "轻轻", "微微",
      "忽然", "其实", "不过", "而且", "然后", "接着", "一下", "一声", "小心",
      "小姐", "面前", "前面", "下面", "里面", "外面", "中间", "时间"]
h = {p: dec.count(p) for p in PH if dec.count(p)}
print(f"\n语料 {len(raw)} 字 · 词命中 {len(h)}/{len(PH)} 种 / {sum(h.values())} 次")
print("  " + " ".join(f"{k}×{v}" for k, v in sorted(h.items(), key=lambda x: -x[1])[:20]))
cjk = Counter(c for c in dec if "\u4e00" <= c <= "\u9fff")
print(f"  前 20 高频字：{' '.join(c for c, _ in cjk.most_common(20))}")
print(f"  残留 PUA：{sum(1 for c in dec if 0xE000 <= ord(c) <= 0xF8FF)}")
print(f"\n{'='*76}\n最终成品样例（前 560 字）\n{'='*76}\n{dec[:560]}")
