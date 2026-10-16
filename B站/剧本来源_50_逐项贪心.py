# -*- coding: utf-8 -*-
"""
探针 50 —— 逐项验证：每一条候选修正，加进去对「短语命中和字频合理性」是加分还是减分

只保留净收益为正的修正。避免像探针 49 那样一次性覆盖 102 项、把好项也改坏。
"""
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

P = r"D:\DSHworkspace\B站\情报\_font_probe\pua_map_final.json"
BASE = {int(k, 0): v for k, v in json.load(open(P, encoding="utf-8")).items()}

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526",
            "7138408581975507491"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25, verify=CAB)
    paras = re.findall(r"<p>(.*?)</p>", r.text, re.S)
    raws.append(_h.unescape(re.sub(r"<[^>]+>", "", "".join(paras))))
raw = "\n".join(raws)

PHRASES = ["什么", "怎么", "这里", "那里", "已经", "不是", "一个", "我们", "你们",
           "他们", "自己", "因为", "所以", "但是", "如果", "可以", "没有", "知道",
           "觉得", "时候", "出来", "进去", "起来", "下来", "过来", "男人", "女人",
           "看着", "说道", "一声", "眼睛", "心里", "身体", "有些", "一点", "一样",
           "这样", "那样", "真的", "还是", "看见", "听到", "抬头", "低头", "手指",
           "声音", "地方", "突然", "开始", "最后", "表情", "眼神", "身上"]
EXPECT = "的一了是我不你在他人有着个这她上就都而及与说们来到时大地为子中"
# 明显的错字黑名单：解出这些字说明映射错了
BAD = set("棠梨傅扬稜尊四搭聪洛昆檀喉友笑息无没9稜")


def score(tab):
    dec = "".join(tab.get(ord(c), c) for c in raw)
    h = sum(dec.count(p) for p in PHRASES)
    cjk = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
    top = [ch for ch, _ in cjk.most_common(30)]
    inexp = sum(1 for ch in top if ch in EXPECT)
    bad = sum(1 for ch in top if ch in BAD)
    return h + inexp * 2 - bad * 3, h, inexp, bad


base_score, bh, bi, bb = score(BASE)
print(f"基线：score={base_score}  短语={bh}  高频命中={bi}  错字={bb}\n")

CAND = {
    0xE3E9: "在", 0xE3EC: "家", 0xE3EF: "情", 0xE3F8: "还", 0xE3F9: "在",
    0xE3FB: "看", 0xE40E: "都", 0xE40F: "平", 0xE41C: "些", 0xE41E: "是",
    0xE41F: "十", 0xE420: "张", 0xE423: "大", 0xE424: "爱", 0xE425: "两",
    0xE426: "命", 0xE427: "全", 0xE428: "后", 0xE42C: "被", 0xE42D: "1",
    0xE436: "了", 0xE444: "着", 0xE44B: "少", 0xE44C: "色", 0xE44D: "里",
    0xE45D: "地", 0xE461: "写", 0xE46A: "没", 0xE46B: "书", 0xE46E: "像",
    0xE471: "为", 0xE477: "看", 0xE47D: "上", 0xE47F: "有", 0xE480: "有",
    0xE481: "法", 0xE483: "应", 0xE488: "声", 0xE489: "身", 0xE48A: "国",
    0xE48E: "他", 0xE499: "对", 0xE4A0: "到", 0xE4A8: "点", 0xE4AA: "定",
    0xE4AE: "正", 0xE4B5: "得", 0xE4B7: "告", 0xE4BC: "过", 0xE4BE: "让",
    0xE4C1: "人", 0xE4C2: "人", 0xE4C4: "者", 0xE4C6: "原", 0xE4CC: "如",
    0xE4D7: "部", 0xE4DE: "一", 0xE4DF: "条", 0xE4E2: "光", 0xE4E4: "头",
    0xE4E7: "自", 0xE4F2: "的", 0xE4F3: "的", 0xE4F9: "心", 0xE4FA: "来",
    0xE505: "很", 0xE507: "小", 0xE508: "小", 0xE50B: "代", 0xE50D: "么",
    0xE50E: "分", 0xE510: "口", 0xE514: "西", 0xE51B: "情", 0xE51D: "这",
    0xE51E: "么", 0xE521: "我", 0xE524: "长", 0xE528: "眼", 0xE52A: "不",
    0xE52C: "0", 0xE52E: "信", 0xE52F: "下", 0xE530: "却", 0xE531: "重",
    0xE535: "音", 0xE537: "m", 0xE53A: "之", 0xE53B: "前", 0xE53E: "高",
    0xE540: "太", 0xE541: "眼", 0xE543: "起", 0xE545: "了", 0xE547: "她",
    0xE54C: "子", 0xE54F: "四", 0xE556: "a", 0xE557: "海", 0xE559: "个",
    0xE55A: "个", 0xE530: "却",
}

keep, drop = {}, {}
cur = dict(BASE)
cur_score = base_score
# 贪心：反复扫描所有候选，谁能提分就接受，直到不再提升
for _round in range(6):
    improved = False
    for cp, ch in CAND.items():
        if cur.get(cp) == ch:
            continue
        trial = dict(cur)
        trial[cp] = ch
        sc, _, _, _ = score(trial)
        if sc > cur_score:
            cur = trial
            cur_score = sc
            keep[cp] = ch
            improved = True
    if not improved:
        break

sc, h, i, b = score(cur)
print(f"贪心收敛后：score={sc}（基线 {base_score}）  短语={h}（基线 {bh}）  "
      f"高频命中={i}（基线 {bi}）  错字={b}（基线 {bb}）")
print(f"接受的修正 {len(keep)} 项：")
for cp, ch in sorted(keep.items()):
    print(f"   U+{cp:04X} -> {ch}   （原 {BASE.get(cp)}）")

json.dump({str(k): v for k, v in sorted(cur.items())},
          open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"\n已写回 {P}")

dec = "".join(cur.get(ord(c), c) for c in raw)
print(f"\n=== 最终样本 ===\n{dec[:340]}")
