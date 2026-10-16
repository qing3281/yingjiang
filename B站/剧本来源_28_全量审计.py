# -*- coding: utf-8 -*-
"""
探针 28 —— 对最终映射表做一次全量「高频字合理性」审计

对解码文本里的每个汉字，输出：
   字  解码出现次数  占比  绑定的 PUA 码位
凡是占比 > 0.25% 的字都列出来，人眼扫一遍即可确认没有离谱的错映射。
同时输出「现代汉语超高频字里在解码文本中缺席的」——那些字必然被错映射挤掉了。
"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR, decrypt

from curl_cffi import requests as creq

# 现代汉语最常用的 60 个字（任何中文小说里都必然高频出现）
MUST = "的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所"

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
decs = []
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
            decs.append(decrypt(raw))
        import time as _t; _t.sleep(0.35)

dec = "\n".join(decs)
cjk = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
tot = sum(cjk.values())
rev = {}
for cp, c in PUA2CHAR.items():
    rev.setdefault(c, []).append(cp)

print(f"解码语料 {len(dec)} 字（{len(decs)} 章 / 10 本）\n")
print("== 解码文本中出现占比 >= 0.25% 的字 ==")
for ch, n in cjk.most_common(90):
    share = n / tot * 100
    if share < 0.25:
        break
    cps = ",".join(f"{c:04X}" for c in rev.get(ch, []))
    src = f"PUA:{cps}" if cps else "原文自带"
    print(f"   {ch}  {n:6d}  {share:5.2f}%   {src}")

print("\n== 现代汉语最常用 60 字中，在解码文本里『缺席或异常低』的 ==")
low = []
for ch in dict.fromkeys(MUST):
    n = cjk.get(ch, 0)
    share = n / tot * 100
    if share < 0.05:
        low.append((ch, n, share))
print("   " + ("（无 —— 全部高频出现）" if not low else ""))
for ch, n, share in low:
    cps = rev.get(ch)
    print(f"   {ch}  出现 {n} 次 ({share:.3f}%)  {'← 绑在 ' + ','.join(f'{c:04X}' for c in cps) if cps else '← 未被映射！'}")

print("\n== 映射表里绑了但语料中 0 次出现的码位（保留初版转录，未校验）==")
absent = sorted(c for c in PUA2CHAR if chr(c) not in dec)
print(f"   共 {len(absent)} 个：" + " ".join(f"{PUA2CHAR[c]}@{c:04X}" for c in absent))
