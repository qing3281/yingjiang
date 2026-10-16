# -*- coding: utf-8 -*-
"""
探针 29 —— 定位「整行错位」的边界并推导补丁

现象：初版目视转录在若干行整体错了一格。表现为两类铁证：
  A) 某个码位高频出现，但它的上下文只有唯一解（例 E521 出现 750 次，
     上下文全是「X叔/棠梨X/让X」，只可能是『我』）。
  B) 现代汉语必用的超高频字在解码文本里彻底缺席（不/大/子/年/下/之/想）。
本探针把 A 类（高频+唯一解）与 B 类（缺席高频字）配对，找出错位区间。
"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR, decrypt

from curl_cffi import requests as creq

# 本探针要定向验证的码位（A 类：高频且上下文唯一）
A_CLASS = [0xE433, 0xE434, 0xE43C, 0xE43F, 0xE424, 0xE425, 0xE426,
           0xE4D1, 0xE4D2, 0xE45F, 0xE460, 0xE461, 0xE462, 0xE463,
           0xE4C8, 0xE4CA, 0xE4CD, 0xE4CE, 0xE469, 0xE4B1, 0xE4B2,
           0xE475, 0xE476, 0xE47F, 0xE4A2, 0xE4A4, 0xE4A5, 0xE4AB,
           0xE4AA, 0xE4AF, 0xE46D, 0xE471, 0xE474, 0xE478, 0xE479,
           0xE47A, 0xE47C, 0xE4B4, 0xE4B5, 0xE4B9, 0xE4BA, 0xE486,
           0xE48B, 0xE48D, 0xE490, 0xE491, 0xE498, 0xE49A, 0xE49B,
           0xE4CD, 0xE4F9, 0xE4FD, 0xE500, 0xE501, 0xE503, 0xE504,
           0xE509, 0xE50E, 0xE510, 0xE511, 0xE513, 0xE514, 0xE517,
           0xE518, 0xE51B, 0xE522, 0xE523, 0xE529, 0xE52E, 0xE536,
           0xE537, 0xE538, 0xE539, 0xE53B, 0xE53D, 0xE53E, 0xE540,
           0xE541, 0xE542, 0xE544, 0xE555, 0xE557, 0xE55A]

s = creq.Session(impersonate="chrome131")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}


def get(u, tries=4):
    last = ""
    for i in range(tries):
        try:
            r = s.get(u, headers=H, timeout=25)
            if r.status_code == 200 and len(r.text) > 5000:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = type(e).__name__
        import time as _t; _t.sleep(1.2 * (i + 1))
    raise RuntimeError(f"{u} -> {last}")


BOOKS = ["7137359676424850443", "6823667291557727235", "7674861059122924569",
         "7091150316644600867", "7096667097870109733", "7064405896540982309",
         "6883748331202284558", "7101803652683140111", "7556979595459710014",
         "7075952796322761739"]
raws = []
for BK in BOOKS:
    try:
        page = get(f"https://fanqienovel.com/page/{BK}")
    except Exception:
        continue
    cids, seen = [], set()
    for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
        if m.group(1) not in seen:
            seen.add(m.group(1)); cids.append(m.group(1))
    for cid in cids[1:6]:
        try:
            t = get(f"https://fanqienovel.com/reader/{cid}")
        except Exception:
            continue
        paras = re.findall(r"<p>(.*?)</p>", t, re.S)
        raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
        if len(raw) > 400:
            raws.append(raw)
        import time as _t; _t.sleep(0.3)

raw = "\n".join(raws)
print(f"语料 {len(raw)} 字\n")

# 关键：统计原始文本里每个 PUA 码位的出现次数，只列出高频的
cnt = Counter(ch for ch in raw if "\ue000" <= ch <= "\uf8ff")
print(f"原始 PUA 字符 {sum(cnt.values())} 个 / {len(cnt)} 个不同码位\n")
print("== 出现次数 Top 60 的码位（这些是真正的高频字，其映射必须准确）==")
PUA_RUN = re.compile(r"[\ue000-\uf8ff]+")
for ch, n in cnt.most_common(60):
    cp = ord(ch)
    g = PUA2CHAR.get(cp, "?")
    hits = list(re.finditer(r".{5}(%s).{5}" % re.escape(ch), raw))
    samples = []
    for m in hits[:2]:
        t = PUA_RUN.sub(lambda mm: "〇" * len(mm.group(0)), m.group(0))
        i = m.group(0).find(ch)
        samples.append(t[:i] + f"〖{g}〗" + t[i + 1:])
    print(f"  U+{cp:04X} x{n:5d} 当前={g}   " + " | ".join(samples))
