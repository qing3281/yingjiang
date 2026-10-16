# -*- coding: utf-8 -*-
"""
fanqie_reader.py —— 番茄小说网页端正文抓取 + PUA 字体解密（可直接运行）

用法：
    python fanqie_reader.py chapters <bookId>            # 列目录 + 标记哪些章免费
    python fanqie_reader.py read <chapterId>             # 抓单章并解密
    python fanqie_reader.py book <bookId> [--max N]      # 抓该书所有「免费」章

技术要点（全部实测确认）：
  * fanqienovel.com 章节页是**服务端渲染**，正文直接内嵌在 HTML 的 <p> 标签里，
    无需 JS 渲染、无需 cookie、无需登录。
  * 正文里的 362 个高频字被替换成 Unicode PUA 码位（U+E3E8~U+E55B）做混淆，
    页面随附一个 woff2 子集字体。字体 cmap 的 gid 无意义，但**全站共用同一张
    固定映射表**（多本书 font-family 均为 DNMrHsV173Pd4pgy、hash 均为 dc027189e0ba4cd），
    因此映射表一次构建、长期有效 —— 见 fanqie_font.py。
  * **只有免费章节能拿到全文**。isChapterLock=True 的章节，正文只返回约 170 字的
    试读片段（实测 6.0% / 1.5% / 4.4% 覆盖度），这不是反爬，是产品设计。

⚠️ 版权提醒：番茄小说内容受著作权保护。本工具仅用于技术验证与「题材/结构」
   层面的参考，不要用抓下来的原文直接生成视频投稿。
"""
import argparse
import html as _html
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
try:
    from curl_cffi import requests as creq
except ImportError:
    sys.exit("需要 curl_cffi：pip install curl_cffi")

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fanqie_font import PUA2CHAR, decrypt

BASE = "https://fanqienovel.com"
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    # 实测：不带 Referer 也能正常拿到正文
}

_session = None


def session():
    global _session
    if _session is None:
        # 番茄/字节系对 TLS 指纹敏感，用 curl_cffi 伪装 Chrome
        _session = creq.Session(impersonate="chrome131")
    return _session


def fetch(url, retries=3):
    last = None
    for i in range(retries):
        try:
            r = session().get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200 and len(r.text) > 1000:
                return r.text
            last = f"HTTP {r.status_code} len={len(r.text)}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"抓取失败 {url} -> {last}")


# ---------------------------------------------------------------- 目录
CH_RE = re.compile(r'["\'/]reader/(\d{15,25})')


CN_NUM = {c: i for i, c in enumerate("零一二三四五六七八九", 0)}


def _chapter_no(name):
    """从「第351章 …」里取章号；取不到返回 None。

    注意：不能直接按文档顺序用目录。实测《部族荣光》目录页把**最新章节**
    （第351章）插在最前面当预告，其余第1~350章才是正常顺序。
    """
    m = re.match(r"\s*第\s*([0-9]+)\s*章", name or "")
    return int(m.group(1)) if m else None


def list_chapters(book_id, sort=True):
    """返回 (书名, [(chapterId, 章节名)])。目录页 chapter_id 出现 0 次，
    章节载体是 <a href="/reader/<itemId>" class="chapter-item-title">。

    sort=True 时按「第N章」的 N 升序重排（无法解析章号的保持文档顺序、排在最后），
    以消除目录页顶部「最新章节」预告造成的错位。
    """
    t = fetch(f"{BASE}/page/{book_id}")
    title = None
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    if m:
        title = _html.unescape(m.group(1)).split("完整版")[0].strip()

    out, seen = [], set()
    for m in CH_RE.finditer(t):
        cid = m.group(1)
        if cid in seen:
            continue
        seen.add(cid)
        # 抓该链接的锚文本作为章节名
        seg = t[m.end(): m.end() + 400]
        nm = re.search(r">([^<>]{2,60})</", seg)
        out.append((cid, _html.unescape(nm.group(1)).strip() if nm else ""))

    if sort:
        out.sort(key=lambda p: (_chapter_no(p[1]) is None,
                                _chapter_no(p[1]) or 0))
    return title, out


# ---------------------------------------------------------------- 正文
def parse_chapter(html_text):
    title = None
    m = re.search(r"<title>(.*?)</title>", html_text, re.S)
    if m:
        title = _html.unescape(m.group(1)).split("在线免费阅读")[0].strip()

    paras = re.findall(r"<p>(.*?)</p>", html_text, re.S)
    raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))

    locked = 'isChapterLock":true' in html_text or '"isChapterLock":true' in html_text
    ff = re.search(r'font-family\s*:\s*[\'"]?(DN[A-Za-z0-9]+)', html_text)
    return {
        "title": title,
        "raw": raw,
        "text": decrypt(raw),
        "locked": locked,
        "font_family": ff.group(1) if ff else None,
        "pua_total": sum(1 for c in raw if 0xE000 <= ord(c) <= 0xF8FF),
        "pua_codes": sorted({ord(c) for c in raw if 0xE000 <= ord(c) <= 0xF8FF}),
    }


def read_chapter(chapter_id):
    return parse_chapter(fetch(f"{BASE}/reader/{chapter_id}"))


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="番茄小说网页端抓取+字体解密（仅供技术调研）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("chapters", help="列目录")
    p1.add_argument("book_id")
    p2 = sub.add_parser("read", help="抓单章")
    p2.add_argument("chapter_id")
    p3 = sub.add_parser("book", help="抓全书免费章")
    p3.add_argument("book_id")
    p3.add_argument("--max", type=int, default=20)
    a = ap.parse_args()

    if a.cmd == "chapters":
        name, chs = list_chapters(a.book_id)
        print(f"《{name}》 共 {len(chs)} 章")
        for i, (cid, ct) in enumerate(chs, 1):
            print(f"  {i:4d}  {cid}  {ct}")

    elif a.cmd == "read":
        d = read_chapter(a.chapter_id)
        cov = "全文" if not d["locked"] else "⚠️ 仅试读片段（该章已锁定）"
        print(f"【{d['title']}】  {cov}")
        print(f"正文 {len(d['raw'])} 字   PUA {d['pua_total']} 个   "
              f"字体 {d['font_family']}")
        unknown = [c for c in d["pua_codes"] if c not in PUA2CHAR]
        print(f"未覆盖码位: {[hex(c) for c in unknown] if unknown else '无'}")
        print("-" * 70)
        print(d["text"])

    elif a.cmd == "book":
        name, chs = list_chapters(a.book_id)
        print(f"《{name}》 共 {len(chs)} 章，最多抓 {a.max} 章")
        got = 0
        for cid, ct in chs:
            d = read_chapter(cid)
            if d["locked"]:
                print(f"  跳过（锁定） {ct}")
                if got:
                    continue
                continue
            got += 1
            print(f"\n===== {d['title']} ({len(d['raw'])} 字) =====")
            print(d["text"])
            if got >= a.max:
                break
            time.sleep(1.0)
        print(f"\n共拿到 {got} 章免费正文")


if __name__ == "__main__":
    main()
