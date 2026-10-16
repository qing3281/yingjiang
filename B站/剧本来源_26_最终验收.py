# -*- coding: utf-8 -*-
"""
探针 26 —— 最终验收：在 10 本不同类型的书上解码，逐段肉眼可读性检查

验收标准：
 1. 未映射码位占比 < 0.1%
 2. 解出的段落是通顺中文（无「囧句」）
 3. 把残余的可疑字符列出来
"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR, decrypt, CORRECTIONS_APPLIED

from curl_cffi import requests as creq

print(f"校正条目已应用：{CORRECTIONS_APPLIED} 条；映射表共 {len(PUA2CHAR)} 个码位\n")

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
         "6883748331202284558", "7101803652683140111", "7075952796322761739",
         "7556979595459710014"]

tot_pua = tot_left = 0
left_counter = Counter()
for BK in BOOKS:
    try:
        page = get(f"https://fanqienovel.com/page/{BK}")
    except Exception as e:
        print(f"[{BK}] 详情页失败 {e}"); continue
    t = re.search(r"<title>(.*?)</title>", page, re.S)
    title = _html.unescape(t.group(1)).split("完整版")[0].strip() if t else "?"
    cids, seen = [], set()
    for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
        if m.group(1) not in seen:
            seen.add(m.group(1)); cids.append(m.group(1))
    for cid in cids[1:3]:
        try:
            tt = get(f"https://fanqienovel.com/reader/{cid}")
        except Exception:
            continue
        paras = re.findall(r"<p>(.*?)</p>", tt, re.S)
        raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
        if len(raw) < 300:
            continue
        txt = decrypt(raw)
        pua = sum(1 for ch in raw if "\ue000" <= ch <= "\uf8ff")
        lp = Counter(ch for ch in txt if "\ue000" <= ch <= "\uf8ff")
        tot_pua += pua; tot_left += sum(lp.values()); left_counter.update(lp)
        print(f"{'='*72}\n《{title}》 第 {cid[-6:]} 章")
        print(f"  原始 {len(raw)} 字 / PUA {pua} 个 / 解码后残留 {sum(lp.values())} 个"
              f" ({sum(lp.values())/max(pua,1)*100:.3f}%)")
        print("  解码正文（前 400 字）：")
        print("  " + txt[:400].replace("\n", "\n  "))
        print()
        import time as _t; _t.sleep(0.4)

print("=" * 72)
print(f"总计：PUA {tot_pua} 个，解码后残留未映射 {tot_left} 个 "
      f"({tot_left/max(tot_pua,1)*100:.3f}%)")
for ch, n in left_counter.most_common(20):
    print(f"   未映射 U+{ord(ch):04X} x{n}")
