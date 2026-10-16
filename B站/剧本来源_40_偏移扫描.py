# -*- coding: utf-8 -*-
"""
探针 40 —— 偏移量扫描

假设：初版映射表 OLD 与真值之间存在**固定的码位偏移 k**，即真值[cp] = OLD[cp+k]。
对 k = -4..+4 各解一遍同一段密文，用「可读性打分」挑出正确的 k。

打分依据（不依赖主观判断）：
  - 常见字覆盖率：解码文本中前 60 个常用汉字所占比例
  - 双字词命中：常见二字词（的、了、在、是…组成的固定搭配）出现次数
  - 非法搭配惩罚：如『手手』『的的』等连续重复
"""
import html as _html
import json
import re
import sys
from collections import Counter

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
print(f"基础映射 {len(BASE)} 条")

from curl_cffi import requests as creq
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526"]:
    t = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25).text
    raws.append(_html.unescape(re.sub(r"<[^>]+>", "", "".join(re.findall(r"<p>(.*?)</p>", t, re.S)))))
raw = "\n".join(raws)
print(f"语料 {len(raw)} 字\n")

COMMON = "的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所同"
COMMON = set(COMMON)
WORDS = ["什么", "怎么", "这里", "那里", "已经", "不是", "一个", "我们", "你们", "他们",
         "自己", "因为", "所以", "但是", "如果", "可以", "没有", "知道", "觉得", "时候",
         "出来", "进去", "起来", "下来", "过来", "男人", "女人", "看着", "说道", "一声",
         "眼睛", "心里", "身体", "有些", "一点", "一样", "这样", "那样", "真的", "还是"]


def score(dec):
    n = len(dec)
    if not n:
        return 0
    cjk = [c for c in dec if "\u4e00" <= c <= "\u9fff"]
    if not cjk:
        return 0
    cov = sum(1 for c in cjk if c in COMMON) / len(cjk)
    w = sum(dec.count(x) * len(x) for x in WORDS)
    rep = sum(1 for i in range(len(dec) - 1) if dec[i] == dec[i + 1] and "\u4e00" <= dec[i] <= "\u9fff")
    return cov * 100 + w / n * 300 - rep / n * 200


results = []
for k in range(-6, 7):
    m = {}
    for cp, ch in BASE.items():
        tgt = cp + k
        m[cp] = BASE.get(tgt, ch)          # 越界的保留原值
    dec = "".join(m.get(ord(c), c) for c in raw)
    sc = score(dec)
    results.append((sc, k, dec))

results.sort(reverse=True)
print("== 偏移扫描结果（分数越高越像正常中文）==")
for sc, k, dec in results:
    sample = dec[:66].replace("\n", "/")
    print(f"  k={k:+d}  score={sc:7.2f}   {sample}")

best_sc, best_k, best_dec = results[0]
print(f"\n最佳偏移 k = {best_k:+d}  (score={best_sc:.2f})")
print(f"\n=== k={best_k:+d} 解码样本 600 字 ===")
print(best_dec[:600])

# 写出该偏移下的完整映射，供人工复核
out = {str(cp): BASE.get(cp + best_k, ch) for cp, ch in BASE.items()}
p = r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json"
json.dump({"k": best_k, "map": out}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\n已写出 {p}")
