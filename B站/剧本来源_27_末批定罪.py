# -*- coding: utf-8 -*-
"""探针 27 —— 最后一批高频可疑字定罪 + 与原始字频比对。"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR, decrypt

from curl_cffi import requests as creq

SUSPECT = [0xE423, 0xE3F3, 0xE41F, 0xE53C, 0xE446, 0xE40C, 0xE403, 0xE3F1,
           0xE54F, 0xE550, 0xE551, 0xE552, 0xE553, 0xE554, 0xE556, 0xE55B,
           0xE549, 0xE555, 0xE557, 0xE520, 0xE52E, 0xE51F, 0xE54D, 0xE54B,
           0xE42D, 0xE3F4, 0xE408, 0xE413, 0xE540, 0xE536, 0xE538, 0xE53F]

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
         "6883748331202284558", "7101803652683140111", "7556979595459710014"]
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
    for cid in cids[1:5]:
        try:
            t = get(f"https://fanqienovel.com/reader/{cid}")
        except Exception:
            continue
        paras = re.findall(r"<p>(.*?)</p>", t, re.S)
        raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
        if len(raw) > 400:
            raws.append(raw)
        import time as _t; _t.sleep(0.35)

raw = "\n".join(raws)
print(f"语料 {len(raw)} 字\n")
PUA_RUN = re.compile(r"[\ue000-\uf8ff]+")


def show(cp, n=6):
    g = PUA2CHAR.get(cp, "?")
    hits = list(re.finditer(r".{6}(%s).{6}" % re.escape(chr(cp)), raw))
    print(f"--- U+{cp:04X} 当前={g} x{len(hits)}")
    if not hits:
        print("    （未出现）\n"); return
    for m in hits[:n]:
        t = PUA_RUN.sub(lambda mm: "〇" * len(mm.group(0)), m.group(0))
        i = m.group(0).find(chr(cp))
        print("    " + t[:i] + f"〖{g}〗" + t[i + 1:])
    print()


for cp in SUSPECT:
    show(cp)

# 对照：真实汉字（非 PUA）在语料里的高频榜，用来识别「本该高频却没出现」的字
plain = Counter(ch for ch in raw if "\u4e00" <= ch <= "\u9fff")
tot = sum(plain.values())
print("== 原文自带汉字高频榜（前 40，说明番茄并未混淆这些字）==")
for ch, n in plain.most_common(40):
    print(f"   {ch} {n:6d} {n/tot*100:5.2f}%")
