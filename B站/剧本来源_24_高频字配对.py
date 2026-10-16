# -*- coding: utf-8 -*-
"""
探针 24 —— 把「缺失的高频字」与「异常占位的字符」配对

方法：拿现代汉语 Top-60 高频字，看哪些在解码文本里**排名明显偏低/缺失**；
那些字正是被错映射挤掉的真身（例：『我』不见踪影 → 『格』621 次就是它）。
再打印每个可疑码位的真实上下文，逐条定罪。
"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR, decrypt

from curl_cffi import requests as creq

# 现代汉语高频字排名（前 80，按大致频序）
RANK = ("的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和"
        "要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起"
        "发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所"
        "同日手又行意动方期它头经长儿回位分爱老因很给名法间斯知世什两次")
RANK = list(dict.fromkeys(RANK))

SUSPECT = [0xE521, 0xE52A, 0xE51E, 0xE547, 0xE534, 0xE54C, 0xE50D, 0xE559,
           0xE559, 0xE4F2, 0xE4D1, 0xE535, 0xE52D, 0xE52F, 0xE52B,
           0xE45D, 0xE45E, 0xE506, 0xE507, 0xE528, 0xE525, 0xE526, 0xE527,
           0xE423, 0xE442, 0xE46E, 0xE4C6, 0xE4C7, 0xE52C, 0xE555, 0xE557,
           0xE54A, 0xE533, 0xE53A, 0xE520, 0xE52E, 0xE530, 0xE549, 0xE51F]

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
        import time as _t; _t.sleep(0.5)

raw = "\n".join(raws)
print(f"语料 {len(raw)} 字（{len(raws)} 章，{len(BOOKS)} 本不同类型）\n")
PUA_RUN = re.compile(r"[\ue000-\uf8ff]+")


def show(cp, n=8):
    g = PUA2CHAR.get(cp, "?")
    hits = list(re.finditer(r".{6}(%s).{6}" % re.escape(chr(cp)), raw))
    print(f"--- U+{cp:04X}  当前={g}  出现 {len(hits)} 次")
    for m in hits[:n]:
        t = PUA_RUN.sub(lambda mm: "〇" * len(mm.group(0)), m.group(0))
        i = m.group(0).find(chr(cp))
        print("    " + t[:i] + f"〖{g}〗" + t[i + 1:])
    if not hits:
        print("    （未出现）")
    print()


for cp in dict.fromkeys(SUSPECT):
    show(cp)
