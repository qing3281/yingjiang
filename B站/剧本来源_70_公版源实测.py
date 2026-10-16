# -*- coding: utf-8 -*-
"""
探针 70 —— 公版/开放版权故事源可用性实测（这是版权最稳的一条路）

逐个真实请求，记录 HTTP 状态、返回体量、是否可程序化批量取用。
"""
import json
import sys
import time
import urllib.parse as up
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
try:
    import shutil
    if not __import__("os").path.exists(CAB):
        shutil.copy(certifi.where(), CAB)
except Exception:
    pass

UA = {"User-Agent": "Mozilla/5.0 (short-drama-research)"}


def probe(name, url, note=""):
    t0 = time.time()
    try:
        r = u.Request(url, headers=UA)
        with u.urlopen(r, timeout=30) as resp:
            body = resp.read()
            code = resp.status
            ctype = resp.headers.get("Content-Type", "")
    except Exception as e:
        code = getattr(e, "code", "ERR")
        body = b""
        ctype = str(e)[:80]
    dt = time.time() - t0
    print(f"[{str(code):>5s}] {name:34s} {len(body):>9,d}B  {dt:5.2f}s  {ctype[:38]}")
    if note:
        print(f"        {note}")
    return body


print("=" * 96)
print("一、Project Gutenberg（美国公版书，法人已进入公有领域）")
print("=" * 96)
probe("gutendex API 搜索", "https://gutendex.com/books?search=detective",
      "第三方只读 API，无需 key")
probe("gutendex 中文书", "https://gutendex.com/books?languages=zh")
probe("Gutendex 单本", "https://gutendex.com/books/1342")
probe("PG 官方 catalog", "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv",
      "全站目录 CSV，含语言/版权标记")

print()
print("=" * 96)
print("二、中文维基文库（明清小说等，公版）")
print("=" * 96)
probe("zh.wikisource API 搜索", "https://zh.wikisource.org/w/api.php?action=query"
      "&list=search&srsearch=" + up.quote("聊斋志异") + "&format=json&srlimit=3")
probe("维基文库 页面内容", "https://zh.wikisource.org/w/api.php?action=parse"
      "&page=" + up.quote("聊斋志异") + "&prop=wikitext&format=json")

print()
print("=" * 96)
print("三、中国哲学书电子化计划 ctext.org（先秦至清，公版古籍）")
print("=" * 96)
probe("ctext 首页", "https://ctext.org/zhs")
probe("ctext API 取文本", "https://api.ctext.org/gettext?urn=ctp:analects/xue-er")

print()
print("=" * 96)
print("四、Standard Ebooks / Open Library")
print("=" * 96)
probe("Standard Ebooks 目录", "https://standardebooks.org/feeds/atom/all")
probe("Open Library 搜索", "https://openlibrary.org/search.json?q=detective"
      "&language=chi&limit=3")
