# -*- coding: utf-8 -*-
"""
探针 35 —— 用未被拦截的指纹，验证两件事：
 (1) 字体是否「每本书一份」（对比 3 本书的 woff2 md5）
 (2) 实际解密一篇 → 明文占比、可读性抽样
 (3) 番茄的免费书单入口在哪（首页/榜单能否拿到大批 bookId）
"""
import hashlib
import html as _html
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import decrypt

from curl_cffi import requests as creq

IMP = "chrome124"          # chrome131 被番茄针对性拦截（实测）
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
s = creq.Session(impersonate=IMP)


def get(u, minlen=800, tries=3):
    for i in range(tries):
        try:
            r = s.get(u, headers=H, timeout=25)
            if r.status_code == 200 and len(r.text) >= minlen:
                return r
        except Exception:
            pass
        time.sleep(1.3 * (i + 1))
    raise RuntimeError(u)


BOOKS = ["7137359676424850443", "7069948840148732967", "6823667291557727235"]

print("=" * 70)
print("(1) 字体文件是否每书一份")
print("=" * 70)
md5_map = {}
for BK in BOOKS:
    page = get(f"https://fanqienovel.com/page/{BK}").text
    t = re.search(r"<title>(.*?)</title>", page, re.S)
    title = t.group(1).split("完整版")[0].strip() if t else "?"
    ids, seen = [], set()
    for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
        if m.group(1) not in seen:
            seen.add(m.group(1)); ids.append(m.group(1))
    if not ids:
        print(f"  《{title}》 详情页无章节链接")
        continue
    ch = get(f"https://fanqienovel.com/reader/{ids[1]}").text
    print(f"\n  《{title}》 len={len(ch)}")

    fonts = set(re.findall(r'url\((?:&quot;|\\?["\'])?(https?://[^)"\'&\\]+\.(?:woff2?|ttf|otf))', ch))
    if not fonts:
        fonts = set(re.findall(r'(https?://[^\s"\'<>\\&]+\.(?:woff2?|ttf|otf))', ch))
    # font-family 名
    fams = set(re.findall(r'font-family:\s*([A-Za-z0-9_\-]+)', ch))
    print(f"    font-family: {sorted(fams)[:6]}")
    print(f"    字体 URL 数: {len(fonts)}")
    for u in sorted(fonts)[:4]:
        try:
            fr = s.get(u, headers=H, timeout=25)
            md5 = hashlib.md5(fr.content).hexdigest()
            md5_map.setdefault(md5, []).append(title)
            print(f"      {u[:88]}")
            print(f"        -> {fr.status_code} {len(fr.content)}B md5={md5[:16]}")
        except Exception as e:
            print(f"      {u[:88]} 下载失败 {type(e).__name__}")
    time.sleep(0.6)

print("\n  == md5 去重 ==")
for md5, users in md5_map.items():
    print(f"    {md5[:16]}  {users}")
print(f"  → {'每本书一份字体（%d 份）' % len(md5_map) if len(md5_map) > 1 else '全局共用同一份字体'}")

print()
print("=" * 70)
print("(2) 实测解密一章")
print("=" * 70)
cid = "7137980122702807592"
ch = get(f"https://fanqienovel.com/reader/{cid}").text
paras = re.findall(r"<p>(.*?)</p>", ch, re.S)
raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
dec = decrypt(raw)
pua = sum(1 for c in raw if "\ue000" <= c <= "\uf8ff")
print(f"  原始正文 {len(raw)} 字，其中 PUA {pua} 字（{pua/max(1,len(raw))*100:.1f}%）")
out = re.sub(r"[ \u3000]+", " ", dec).replace(" ", "\n")
lines = [l for l in out.split("\n") if len(l) > 6]
print(f"  解密后可读段落 {len(lines)} 条。前 8 条：")
for l in lines[:8]:
    print(f"    {l[:78]}")

print()
print("=" * 70)
print("(3) 免费书单入口")
print("=" * 70)
home = get("https://fanqienovel.com/").text
ids_home, seen2 = [], set()
for m in re.finditer(r'href="/page/(\d{15,25})"', home):
    if m.group(1) not in seen2:
        seen2.add(m.group(1)); ids_home.append(m.group(1))
print(f"  首页直接给出 {len(ids_home)} 个 bookId")
titles = re.findall(r'<a[^>]+href="/page/(\d{15,25})"[^>]*>(.*?)</a>', home, re.S)
for bid, tt in titles[:10]:
    tt = re.sub(r"<[^>]+>", "", tt).strip()
    print(f"    {bid}  {tt}")
for path in ["/library", "/rank", "/category", "/all", "/free"]:
    try:
        r = s.get(f"https://fanqienovel.com{path}", headers=H, timeout=20, allow_redirects=True)
        n = len(set(re.findall(r'/page/(\d{15,25})', r.text)))
        print(f"  GET {path:10s} -> {r.status_code} len={len(r.text):7d} 唯一 bookId={n}  final={r.url[:70]}")
    except Exception as e:
        print(f"  GET {path:10s} -> 异常 {type(e).__name__}")
    time.sleep(1.0)
