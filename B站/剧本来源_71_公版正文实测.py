# -*- coding: utf-8 -*-
"""
探针 71 —— 公版中文故事源：能不能真的批量拿到正文？
候选：中文维基文库、ctext、殆知阁/GitHub 上的公版中文语料
"""
import json
import sys
import time
import urllib.parse as up
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (drama-research)"}


def get(url, timeout=30):
    t0 = time.time()
    try:
        with u.urlopen(u.Request(url, headers=UA), timeout=timeout) as r:
            b = r.read()
            return r.status, b, time.time() - t0
    except Exception as e:
        return getattr(e, "code", "ERR"), b"", time.time() - t0


print("=" * 92)
print("A. 中文维基文库 —— 用 parse API 取整篇正文")
print("=" * 92)
for title in ["聊齋誌異", "三言二拍", "閱微草堂筆記", "唐宋傳奇集", "搜神記"]:
    code, b, dt = get("https://zh.wikisource.org/w/api.php?action=parse&page="
                      + up.quote(title) + "&prop=text&format=json&redirects=1")
    n = 0
    if code == 200:
        try:
            txt = json.loads(b).get("parse", {}).get("text", {}).get("*", "")
            n = len(txt)
        except Exception:
            pass
    print(f"[{str(code):>4s}] {title:12s} {len(b):>8,d}B  {dt:5.2f}s  正文HTML {n:>7,d} 字符")

print()
print("=" * 92)
print("B. 中文维基文库 —— 分类枚举（能不能按『短篇小說』批量列条目）")
print("=" * 92)
code, b, dt = get("https://zh.wikisource.org/w/api.php?action=query&list=categorymembers"
                  "&cmtitle=" + up.quote("Category:短篇小說")
                  + "&cmlimit=20&format=json")
print(f"[{code}] {dt:.2f}s {len(b)}B")
if code == 200:
    try:
        d = json.loads(b)
        ms = d.get("query", {}).get("categorymembers", [])
        print(f"  枚举到 {len(ms)} 条：")
        for m in ms[:15]:
            print(f"    - {m['title']}")
    except Exception as e:
        print("  解析失败", e, b[:200])

code, b, dt = get("https://zh.wikisource.org/w/api.php?action=query&list=allcategories"
                  "&acprefix=" + up.quote("短篇") + "&aclimit=20&format=json")
print(f"\n[list=allcategories acprefix=短篇] [{code}] {dt:.2f}s")
if code == 200:
    for c in json.loads(b).get("query", {}).get("allcategories", []):
        print("   ", c["*"])

print()
print("=" * 92)
print("C. ctext.org API —— 公版古籍全文")
print("=" * 92)
for urn in ["ctp:analects/xue-er", "ctp:liaozhai/1", "ctp:shishuoxinyu/1"]:
    code, b, dt = get(f"https://api.ctext.org/gettext?urn={urn}")
    print(f"[{str(code):>4s}] {urn:26s} {len(b):>7,d}B  {dt:5.2f}s  {b[:100]!r}")

print()
print("=" * 92)
print("D. GitHub 上的公版中文语料库（搜 API）")
print("=" * 92)
for q in ["chinese classic texts corpus", "殆知阁", "公版书 语料", "chinese poetry corpus json"]:
    url = ("https://api.github.com/search/repositories?q=" + up.quote(q)
           + "&sort=stars&per_page=4")
    code, b, dt = get(url)
    if code != 200:
        print(f"[{code}] {q}")
        continue
    d = json.loads(b)
    print(f"== {q}  (total {d.get('total_count')})")
    for it in d.get("items", []):
        print(f"   {it['full_name']:44s} ★{it['stargazers_count']:<6d}"
              f" {(it['language'] or '-'):10s} push={it['pushed_at'][:10]}")
        print(f"      {(it.get('description') or '')[:100]}")
