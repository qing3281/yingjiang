# -*- coding: utf-8 -*-
"""
探针 32 —— 字体是否「每本书一份」？(v2，用正确的章节 id)

拿到多本书各自的章节 id → 分别抓章节页 → 找 @font-face 的 woff2 →
下载并比 md5。若各书 md5 不同，则字体是按书下发的子集（但码位集合可能相同）。
"""
import hashlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

s = creq.Session(impersonate="chrome131")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}


def get(u, tries=4, minlen=800):
    last = ""
    for i in range(tries):
        try:
            r = s.get(u, headers=H, timeout=25)
            if r.status_code == 200 and len(r.text) >= minlen:
                return r
            last = f"HTTP {r.status_code} len={len(r.text)}"
        except Exception as e:
            last = type(e).__name__
        import time as _t; _t.sleep(1.3 * (i + 1))
    raise RuntimeError(f"{u} -> {last}")


BOOKS = ["7137359676424850443", "6823667291557727235", "7674861059122924569"]
seen_md5 = {}
for BK in BOOKS:
    page = get(f"https://fanqienovel.com/page/{BK}").text
    t = re.search(r"<title>(.*?)</title>", page, re.S)
    title = t.group(1).split("完整版")[0].strip() if t else "?"
    cids, seen = [], set()
    for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
        if m.group(1) not in seen:
            seen.add(m.group(1)); cids.append(m.group(1))
    cid = cids[1]
    html = get(f"https://fanqienovel.com/reader/{cid}").text
    print(f"=== 《{title}》 chapter={cid}  len={len(html)}")

    # 各种可能的字体引用写法
    pats = [
        r'url\(\\?["\']?(https?:[^)"\'\\]+\.(?:woff2?|ttf|otf))',
        r'(https?://[^\s"\'<>\\]+\.(?:woff2?|ttf|otf))',
        r'"fontFamily"\s*:\s*"([^"]+)"',
        r'@font-face',
        r'font-family:\s*([^;"}]+)',
    ]
    found = set()
    for p in pats:
        for m in re.finditer(p, html):
            found.add(m.group(0)[:110])
    for f in list(found)[:10]:
        print("    " + f)

    # 找 CSS link
    for m in re.finditer(r'<link[^>]+href="([^"]+)"[^>]*>', html):
        if ".css" in m.group(1):
            u = m.group(1)
            if u.startswith("/"):
                u = "https://fanqienovel.com" + u
            if "fanqienovel" not in u:
                continue
            try:
                cr = get(u, minlen=50)
                w = re.findall(r'url\(["\']?([^)"\']+\.woff2?[^)"\']*)', cr.text)
                if w:
                    print(f"    CSS {u[:80]} -> 内含字体 {len(w)} 个")
                    for wi in w[:3]:
                        wu = wi if wi.startswith("http") else "https://fanqienovel.com" + ("" if wi.startswith("/") else "/") + wi
                        try:
                            fr = s.get(wu, headers=H, timeout=25)
                            md5 = hashlib.md5(fr.content).hexdigest()
                            print(f"       {wu[:100]} -> {fr.status_code} {len(fr.content)}B md5={md5[:16]}")
                            seen_md5.setdefault(md5, []).append((title, wu))
                        except Exception as e:
                            print("       下载失败", type(e).__name__)
            except Exception:
                pass
    print()
    import time as _t; _t.sleep(0.6)

print("== 字体文件 md5 去重结果 ==")
for md5, users in seen_md5.items():
    print(f"  {md5[:16]}  被 {len(users)} 本书使用: {[u[0] for u in users]}")
if len(seen_md5) > 1:
    print("\n结论：不同书用**不同**字体文件 → 字体是按书下发的子集")
else:
    print("\n结论：所有书共用同一个字体文件 → 映射表可全局复用")
