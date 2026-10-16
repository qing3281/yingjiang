# -*- coding: utf-8 -*-
"""
探针 21 —— 换一本书做盲测（真正的验收）

在一本**从未用于校对**的书上跑解码器，检验三件事：
  1. 解密后的正文是否通顺（若映射有错，会立刻出现「囧句」）；
  2. 覆盖率：还有多少 PUA 字符没落在映射表里（会以 〇 显示并有计数）；
  3. 顺带量一下「短篇/短剧素材」的可得性：免费章数、章节字数。
"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR, decrypt

from curl_cffi import requests as creq

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
        import time as _t; _t.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{u} -> {last}")


# 盲测对象：从站点首页抓到的真实书号（与校对用的 7069948840148732967 不同）
BLIND = ["7091150316644600867", "7075952796322761739", "6883748331202284558",
         "7064405896540982309", "7137359676424850443", "7096667097870109733",
         "7101803652683140111", "6823667291557727235", "7556979595459710014",
         "7674861059122924569"]

all_unknown = Counter()
DEAD = {"7279306271253027879", "7143556936453700621"}
for BK in BLIND:
    if BK in DEAD:
        continue
    try:
        page = get(f"https://fanqienovel.com/page/{BK}")
    except Exception as e:
        print(f"[{BK}] 详情页抓取失败：{e}")
        continue
    m = re.search(r"<title>(.*?)</title>", page, re.S)
    title = _html.unescape(m.group(1)).strip() if m else "?"
    cids, seen = [], set()
    for mm in re.finditer(r'["\'/]reader/(\d{15,25})', page):
        if mm.group(1) not in seen:
            seen.add(mm.group(1)); cids.append(mm.group(1))
    print(f"\n{'='*70}\n[{BK}] 《{title}》  页内 reader 链接 {len(cids)} 个")
    free = cids[1:4]
    for cid in free:
        try:
            t = get(f"https://fanqienovel.com/reader/{cid}")
        except Exception as e:
            print("   章节抓取失败:", e); continue
        paras = re.findall(r"<p>(.*?)</p>", t, re.S)
        raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
        txt = decrypt(raw)
        unknown = Counter(ch for ch in txt if "\ue000" <= ch <= "\uf8ff")
        all_unknown.update(unknown)
        pua_raw = sum(1 for ch in raw if "\ue000" <= ch <= "\uf8ff")
        pua_un = sum(unknown.values())
        print(f"   - 章节 {cid}: 原始 {len(raw)} 字, 原文 PUA {pua_raw} 个, "
              f"解码后残留未知 {pua_un} 个 ({pua_un/max(pua_raw,1)*100:.2f}%)")
        print("     样本：" + txt[:120].replace("\n", " "))

print(f"\n{'='*70}\n盲测中所有未映射的 PUA 码位：")
for ch, n in all_unknown.most_common():
    print(f"   U+{ord(ch):04X}  x{n}")
if not all_unknown:
    print("   （无——映射表对这两本书完全覆盖）")
