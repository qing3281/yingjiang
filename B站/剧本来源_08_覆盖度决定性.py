# -*- coding: utf-8 -*-
"""
剧本来源探针 08 —— 决定性验证：正文到底能拿到多少？

问题：前面观察到「第351章 字数=2701 但 content 只有 200 字符」，
      而「第1章 字数=4223 且 content=5077 字符」。
      到底是 (a) 只有锁章被截断，还是 (b) 只有部分章节完整？

设计：取同一本书的首章、中间章、尾章各 1 个，用**全新无 cookie 会话**拉取，
      记录 字数 / content 长度 / isChapterLock / 首次字符。

另外验证：换一本书，字体 hash 是否还是 dc027189e0ba4cd（=> 全站固定字体）。
"""
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as rq

OUT = r"D:\DSHworkspace\B站\情报\_font_probe"
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def new_session():
    s = rq.Session(impersonate="chrome131")
    s.headers.update({
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "User-Agent": UA,
        "Referer": "https://fanqienovel.com/",
    })
    return s


def parse_state(html):
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*)", html, re.S)
    if not m:
        return None
    raw, depth, ins, esc = m.group(1), 0, False, False
    for i, ch in enumerate(raw):
        if ins:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                ins = False
            continue
        if ch == '"':
            ins = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[: i + 1])
                except Exception:
                    return None
    return None


def font_hash(html):
    hs = sorted(set(re.findall(r"bytetos\.com/obj/awesome-font/c/([0-9a-f]+)\.woff2", html)))
    return hs[0] if hs else None


def chapter_list(s, book):
    r = s.get(f"https://fanqienovel.com/page/{book}", timeout=30)
    ids, seen = [], set()
    for m in re.finditer(r"/reader/(\d+)", r.text):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids, r.text


print("=" * 78)
print("实验 1：同一本书 首/中/尾 三章，全新无 cookie 会话，看 content 长度")
print("=" * 78)
BOOK = "7069948840148732967"  # 部族荣光
s1 = new_session()
ids, page_html = chapter_list(s1, BOOK)
print(f"书 {BOOK}  目录 {len(ids)} 章   详情页字体 hash = {font_hash(page_html)}")

pick = {"首章": ids[0], "中间章": ids[len(ids) // 2], "尾章": ids[-1]}
samples = {}
for label, item in pick.items():
    time.sleep(2.0)
    r = s1.get(f"https://fanqienovel.com/reader/{item}", timeout=30)
    st = parse_state(r.text)
    cd = (st or {}).get("reader", {}).get("chapterData", {}) if st else {}
    html_content = cd.get("content", "") or ""
    plain = re.sub(r"<[^>]+>", "", html_content)
    pua = len(re.findall(r"[\ue000-\uf8ff]", plain))
    han = len(re.findall(r"[\u4e00-\u9fff]", plain))
    stmt_words = cd.get("chapterWordNumber")
    print(f"\n[{label}] itemId={item}")
    print(f"   title        = {cd.get('title')!r}")
    print(f"   平台标称字数   = {stmt_words}")
    print(f"   content 字符数 = {len(html_content)}  (去标签后 {len(plain)})")
    print(f"   汉字 {han} / PUA {pua}")
    print(f"   isChapterLock = {cd.get('isChapterLock')}  needPay={cd.get('needPay')}  status={cd.get('status')}  serialCount={cd.get('serialCount')}")
    print(f"   order/real    = {cd.get('order')} / {cd.get('realChapterOrder')}")
    print(f"   覆盖度        = {100*len(plain)/max(1,int(stmt_words or 1)):.1f}%")
    print(f"   开头 60 字(密文) = {plain[:60]}")
    samples[label] = {"item": item, "cd": {k: v for k, v in cd.items() if k != "content"}, "plain_len": len(plain),
                      "stmt": stmt_words, "lock": cd.get("isChapterLock"), "content": html_content}

json.dump(samples, open(os.path.join(OUT, "章节覆盖度样本.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("\n" + "=" * 78)
print("实验 2：逐章扫前 12 章 + 随机 6 章，看截断规律")
print("=" * 78)
import random
random.seed(42)
scan = ids[:12] + random.sample(ids[12:], 6)
rows = []
for item in scan:
    time.sleep(1.4)
    r = s1.get(f"https://fanqienovel.com/reader/{item}", timeout=30)
    st = parse_state(r.text)
    cd = (st or {}).get("reader", {}).get("chapterData", {}) if st else {}
    plain = re.sub(r"<[^>]+>", "", cd.get("content", "") or "")
    rows.append((cd.get("order"), cd.get("title", "")[:18], int(cd.get("chapterWordNumber") or 0),
                 len(plain), cd.get("isChapterLock"), cd.get("needPay")))
print(f"{'章':>4} {'标题':<20} {'标称':>6} {'实得':>6} {'覆盖':>7} {'锁':>6} {'付费':>5}")
for o, t, w, got, lk, np_ in rows:
    cov = f"{100*got/max(1,w):.0f}%"
    print(f"{str(o):>4} {t:<20} {w:>6} {got:>6} {cov:>7} {str(lk):>6} {str(np_):>5}")

print("\n" + "=" * 78)
print("实验 3：换 3 本书，字体 hash 是否全站相同")
print("=" * 78)
OTHER_BOOKS = []
s2 = new_session()
r = s2.get("https://fanqienovel.com/", timeout=30)
allbooks = sorted(set(re.findall(r"/page/(\d+)", r.text)))[:6]
print("首页拿到的 bookId:", allbooks)
for bid in allbooks[:4]:
    time.sleep(1.6)
    rp = s2.get(f"https://fanqienovel.com/page/{bid}", timeout=30)
    bids, _ = chapter_list(s2, bid)
    fh_page = font_hash(rp.text)
    if not bids:
        print(f"  book {bid}: 无章节, page font={fh_page}")
        continue
    time.sleep(1.6)
    rr = s2.get(f"https://fanqienovel.com/reader/{bids[0]}", timeout=30)
    st = parse_state(rr.text)
    cd = (st or {}).get("reader", {}).get("chapterData", {}) if st else {}
    plain = re.sub(r"<[^>]+>", "", cd.get("content", "") or "")
    fam = (re.findall(r"@font-face[^}]*?font-family:\s*([A-Za-z0-9]+)", rr.text, re.S) or [None])[0]
    print(f"  book {bid}  {cd.get('bookName')!r:<14} 首章实得 {len(plain):>5} 字  "
          f"font-family={fam}  font-hash={font_hash(rr.text)}")
print("\n(若 font-hash 全部相同 => 全站共用一张固定映射表，解密一次永久有效)")
