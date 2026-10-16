# -*- coding: utf-8 -*-
"""
探针 12 —— 用上下文反查法校正映射表

思路：同一个 PUA 码位在一章里会出现多次，每个出现的上下文（前后各 6 字）都是约束。
把候选字逐个代入，只有「正确的那一个」能让所有上下文都通顺。
对于候选集不确定的位置，用高频字表 + 常用搭配做筛选。
"""
import html as _html
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR

BOOK = "7069948840148732967"
s = creq.Session(impersonate="chrome131")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}


def get(url):
    return s.get(url, headers=H, timeout=25)


page = get(f"https://fanqienovel.com/page/{BOOK}").text
cids = []
seen = set()
for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
    if m.group(1) not in seen:
        seen.add(m.group(1))
        cids.append(m.group(1))

# 抓前 2 章（免费章节），正文量大，足够统计
texts = []
for cid in cids[:2]:
    t = get(f"https://fanqienovel.com/reader/{cid}").text
    paras = re.findall(r"<p>(.*?)</p>", t, re.S)
    body = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
    texts.append(body)
    print(f"抓到 {cid}  正文 {len(body)} 字")

full = "\n".join(texts)
print("总语料:", len(full), "字\n")

# 统计每个 PUA 码位的上下文
ctx = defaultdict(list)
for m in re.finditer(r".{6}([\ue000-\uf8ff]).{6}", full):
    ctx[ord(m.group(1))].append(m.group(0))

print("=" * 78)
print("所有出现了 3 次以上的未知/可疑码位的上下文（供人工判定）")
print("=" * 78)
for cp in sorted(ctx):
    n = len(ctx[cp])
    if n < 3:
        continue
    guess = PUA2CHAR.get(cp, "?")
    samples = ctx[cp][:6]
    print(f"\nU+{cp:04X}  我当前猜={guess}  出现 {n} 次")
    for smp in samples:
        print("      " + smp.replace(chr(cp), f"〖{guess}〗"))

# 顺带看单次出现的码位
print("\n" + "=" * 78)
print("仅出现 1~2 次的码位")
print("=" * 78)
for cp in sorted(ctx):
    if len(ctx[cp]) >= 3:
        continue
    guess = PUA2CHAR.get(cp, "?")
    print(f"U+{cp:04X} 猜={guess} x{len(ctx[cp])}: " +
          " | ".join(s.replace(chr(cp), f"〖{guess}〗") for s in ctx[cp][:2]))
