# -*- coding: utf-8 -*-
"""探针 76 —— 收尾：打印疑似错位的码位在真实语料里的上下文，做最后定罪"""
import html as _h
import json
import os
import re
import sys
import time

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

SUSPECT = [0xE545, 0xE546, 0xE51B, 0xE51C, 0xE51D, 0xE51E, 0xE520, 0xE522,
           0xE524, 0xE527, 0xE529, 0xE52B, 0xE52D, 0xE52E, 0xE530, 0xE533,
           0xE535, 0xE53A, 0xE541, 0xE54D, 0xE54F, 0xE551, 0xE552, 0xE553,
           0xE557, 0xE558, 0xE559, 0xE55B, 0xE4A7, 0xE502, 0xE50A, 0xE532,
           0xE541, 0xE543, 0xE544]

for cp in SUSPECT:
    ch = chr(cp)
    if ch not in raw:
        continue
    n = raw.count(ch)
    ctxs = []
    for m in re.finditer(re.escape(ch), raw):
        a = max(0, m.start() - 6)
        b = min(len(raw), m.end() + 6)
        seg = raw[a:b]
        # 段内其它 PUA 用 # 占位，只把目标位显示成【当前猜测】
        out = []
        for c in seg:
            if c == ch:
                out.append(f"【{T.get(cp, '?')}】")
            elif 0xE000 <= ord(c) <= 0xF8FF:
                out.append("#")
            else:
                out.append(c)
        ctxs.append("".join(out).replace("\n", " "))
        if len(ctxs) >= 12:
            break
    print(f"\n### U+{cp:04X}  当前={T.get(cp)!r}  出现 {n} 次")
    for c in ctxs:
        print(f"    {c}")
