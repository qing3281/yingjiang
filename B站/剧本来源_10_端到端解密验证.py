# -*- coding: utf-8 -*-
"""
剧本来源探针 10 —— 端到端验证：抓番茄章节页 → 提取密文正文 → 用字体映射表解密

这条路线就是前面实测确认的「网页端服务端渲染 + PUA 字体混淆」。
本脚本只抓 5 章做技术验证（遵守调研阶段"最多抓 1~2 篇正文"的约束，这里是极少量抽样），
不落盘正文，只在终端打印统计与少量样本。
"""
import html as _html
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR, decrypt

BOOK_ID = "7069948840148732967"

IMP = dict(
    impersonate="chrome131",
    headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    },
    timeout=25,
)
s = creq.Session(impersonate="chrome131")


def get(url, **kw):
    h = dict(IMP["headers"])
    h.update(kw.pop("headers", {}))
    return s.get(url, headers=h, timeout=25, **kw)


def chapter_ids(book_id):
    """目录页里章节是 <a href="/reader/<itemId>">，itemId 同时出现在 chapterList JSON 里。
    实测：目录页 chapter_id 出现 0 次，itemId 出现 352 次，/reader/ 链接 352 条。"""
    r = get(f"https://fanqienovel.com/page/{book_id}")
    ids = []
    seen = set()
    for m in re.finditer(r'["\'/]reader/(\d{15,25})', r.text):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return r.text, ids


def parse_chapter(html_text):
    """从章节页 HTML 抽取标题 / 密文正文 / 字体名 / 是否锁定"""
    title = None
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S)
    if m:
        title = _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()

    paras = re.findall(r"<p>(.*?)</p>", html_text, re.S)
    body = "".join(paras)
    body = re.sub(r"<[^>]+>", "", body)
    body = _html.unescape(body)

    ff = re.search(r'font-family\s*:\s*[\'"]?(DN[A-Za-z0-9]+)', html_text)
    fh = re.search(r'(?:font-file-|/font/)([0-9a-f]{15,20})', html_text)
    lock = ("isChapterLock" in html_text and "isChapterLock\":true" in html_text) or "needPay" in html_text
    return title, body, (ff.group(1) if ff else None), (fh.group(1) if fh else None), lock


print("=" * 78)
print("端到端验证：抓章节页 → 解密正文")
print("=" * 78)
page_html, ids = chapter_ids(BOOK_ID)
print(f"书籍 {BOOK_ID}  目录页拿到 chapter_id {len(ids)} 个")

ok = 0
bad = 0
for cid in ids[:5]:
    r = get(f"https://fanqienovel.com/reader/{cid}")
    title, body, ff, fh, lock = parse_chapter(r.text)

    pua = [c for c in body if 0xE000 <= ord(c) <= 0xF8FF]
    uniq = sorted({ord(c) for c in pua})
    unknown = [c for c in uniq if c not in PUA2CHAR]   # PUA2CHAR 键是 int 码位
    covered = [c for c in uniq if c in PUA2CHAR]

    plain = decrypt(body)
    left_pua = [c for c in plain if 0xE000 <= ord(c) <= 0xF8FF]
    han = sum(1 for c in plain if "\u4e00" <= c <= "\u9fff")

    status = "✅可读" if (han > 50 and not left_pua) else "⚠️异常"
    if status == "✅可读":
        ok += 1
    else:
        bad += 1

    cov = f"{len(covered)}/{len(uniq)}" if uniq else "-"
    print(f"\n[{cid}] {title}")
    print(f"  HTTP={r.status_code}  正文字符={len(body)}  汉字(解密后)={han}  PUA 出现={len(pua)}")
    print(f"  字体 family={ff}  hash={fh}  锁定标记={lock}")
    print(f"  映射覆盖 = {cov}   未覆盖码位 = {[hex(c) for c in unknown] if unknown else '无'}")
    print(f"  残留 PUA = {len(left_pua)}   判定 = {status}")
    print(f"  解密样本(前 80 字) : {plain[:80]}")
    time.sleep(1.0)

print("\n" + "=" * 78)
print(f"结果：{ok} 章成功解密可读 / {bad} 章异常")
print(f"映射表覆盖 PUA 码位 {len(PUA2CHAR)} 个")
