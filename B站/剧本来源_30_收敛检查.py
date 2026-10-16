# -*- coding: utf-8 -*-
"""
探针 30 —— 用「必用高频字缺席检查」做最终收敛

思路：现代汉语最常用的 60 个字，在任何中文小说里都必然高频出现。
解码后如果某个字**彻底缺席或异常低**，说明它的码位被错映射成了别的字。
反复迭代：找出缺席字 → 找出对应的高频异常码位 → 用上下文定罪 → 修正 → 再检查。
"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
import fanqie_font
from fanqie_font import PUA2CHAR, decrypt

# 本探针要验证的新一轮修正（由 29/30 的上下文推导）
NEW = {
    0xE423: "大",   # 449次：棠〖大〗/小〖大〗/〖大〗概率/〖大〗步 —— 并非『姐』
    0xE41F: "年",   # 〖年〗轻/十〖年〗/〖年〗纪 —— 并非『十』
    0xE531: "下",   # 俯〖下〗身/眉〖下〗/〖下〗颚线 —— 并非『重』
    0xE533: "重",   # 〖重〗演/〖重〗蹈覆辙/〖重〗巴 —— 并非『老』
    0xE532: "己",   # 自〖己〗
    0xE52E: "信",   # 相信/信心
    0xE549: "方",   # 方法/方面
    0xE555: "样",   # 怎么〖样〗/这〖样〗
    0xE3F3: "只",   # 〖只〗抿着唇角/〖只〗静静
}
PUA2CHAR.update(NEW)

from curl_cffi import requests as creq

MUST = "的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所"
MUST = list(dict.fromkeys(MUST))

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
         "7075952796322761739", "7096667097870109733"]
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
dec = decrypt(raw)
cjk = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
tot = sum(cjk.values())
print(f"解码语料 {len(dec)} 字 / {len(raws)} 章\n")

print("== 必用高频字缺席检查 ==")
missing = []
for ch in MUST:
    n = cjk.get(ch, 0)
    share = n / tot * 100
    if share < 0.06:
        missing.append((ch, n, share))
if missing:
    for ch, n, share in missing:
        print(f"   ★ {ch}  {n:5d}  {share:.3f}%   ← 缺席/异常低，说明它的码位被错映射了")
else:
    print("   （全部合格 —— 60 个必用高频字都在正常频率区间）")

# 反查：原始文本里每个码位的次数 + 当前映射，供人工复核
cnt = Counter(ch for ch in raw if "\ue000" <= ch <= "\uf8ff")
rev = {}
for cp, c in PUA2CHAR.items():
    rev.setdefault(c, []).append(cp)
print("\n== 解码文本里占比 >= 0.35% 的字（逐个核对是否为合理映射）==")
for ch, n in cjk.most_common(60):
    share = n / tot * 100
    if share < 0.35:
        break
    cps = ",".join(f"{c:04X}" for c in rev.get(ch, []))
    print(f"   {ch} {n:6d} {share:5.2f}%  {'PUA:'+cps if cps else '原文自带'}")
