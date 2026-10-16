# -*- coding: utf-8 -*-
"""
探针 25 —— 第二梯队可疑码位定罪（8.8 万字、8 本书语料）

第一梯队（E521/e52A/e51E/e547/e534/e54C/e50D/e559/e4F2/e535/e4D1/e52D/e52F）
已由探针24 定罪。本探针覆盖剩下所有「映射字占比异常」的码位。
"""
import html as _html
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR

from curl_cffi import requests as creq

SUSPECT = [0xE555, 0xE557, 0xE54A, 0xE533, 0xE53A, 0xE520, 0xE52E, 0xE530,
           0xE549, 0xE51F, 0xE525, 0xE526, 0xE506, 0xE45D, 0xE45E, 0xE4C6,
           0xE46E, 0xE423, 0xE442, 0xE446, 0xE430, 0xE44D, 0xE449, 0xE444,
           0xE477, 0xE4FA, 0xE480, 0xE4C2, 0xE436, 0xE4DE, 0xE4F3, 0xE41E,
           0xE459, 0xE40E, 0xE428, 0xE404, 0xE4EC, 0xE508, 0xE4C5, 0xE41F,
           0xE4FC, 0xE4E4, 0xE4FF, 0xE50B, 0xE4FE, 0xE545, 0xE3EE, 0xE4E7,
           0xE4A8, 0xE438, 0xE4F5, 0xE411, 0xE43A, 0xE41A, 0xE489, 0xE3F3,
           0xE4E0, 0xE4E1, 0xE4E2, 0xE4E3, 0xE4E5, 0xE4E6, 0xE4E8, 0xE4E9,
           0xE4EA, 0xE4EB, 0xE4ED, 0xE4EE, 0xE4EF, 0xE4F0, 0xE4F4, 0xE4F6]

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
         "6883748331202284558", "7101803652683140111"]
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
        if len(raw) > 500:
            raws.append(raw)
        import time as _t; _t.sleep(0.4)

raw = "\n".join(raws)
print(f"语料 {len(raw)} 字（{len(raws)} 章 / {len(BOOKS)} 本）\n")
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
