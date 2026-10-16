# -*- coding: utf-8 -*-
"""探针 20 —— 解决 6 组反向重复冲突：把冲突码位在语料里的上下文并排打印。"""
import html as _html
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR

CONFLICT = [0xE423, 0xE442, 0xE45E, 0xE506, 0xE46E, 0xE50B,
            0xE4C6, 0xE4C7, 0xE507, 0xE525, 0xE52A, 0xE52C,
            0xE528, 0xE527, 0xE526, 0xE52D, 0xE52F, 0xE52E, 0xE52B]

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
            last = f"{type(e).__name__}"
        import time as _t; _t.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{u} -> {last}")


texts = []
page = get("https://fanqienovel.com/page/7069948840148732967")
cids, seen = [], set()
for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
    if m.group(1) not in seen:
        seen.add(m.group(1)); cids.append(m.group(1))
for cid in cids[1:13]:
    t = get(f"https://fanqienovel.com/reader/{cid}")
    paras = re.findall(r"<p>(.*?)</p>", t, re.S)
    texts.append(_html.unescape(re.sub(r"<[^>]+>", "", "".join(paras))))
    import time as _t; _t.sleep(0.7)

full = "\n".join(texts)
print(f"语料 {len(full)} 字\n")
PUA_RUN = re.compile(r"[\ue000-\uf8ff]+")


def show(cp, n=12):
    g = PUA2CHAR.get(cp, "?")
    hits = [m for m in re.finditer(r".{6}(%s).{6}" % re.escape(chr(cp)), full)]
    print(f"--- U+{cp:04X} 当前={g}  出现 {len(hits)} 次")
    for m in hits[:n]:
        t = PUA_RUN.sub(lambda mm: "〇" * len(mm.group(0)), m.group(0))
        i = m.group(0).find(chr(cp))
        print("    " + t[:i] + f"【{g}】" + t[i + 1:])
    if not hits:
        print("    （本语料未出现）")
    print()


for cp in CONFLICT:
    show(cp)
