# -*- coding: utf-8 -*-
"""探针 83 —— 报告 §8 三段片段最终验收（修正键名：pua_codes 是「全部 PUA 码位」，
未映射的要自己跟 PUA2CHAR 比）"""
import json
import re
import sys
import time
import urllib.parse as up
import urllib.request as u

sys.path.insert(0, r"D:\DSHworkspace\B站")
sys.stdout.reconfigure(encoding="utf-8")
from fanqie_font import PUA2CHAR
from fanqie_reader import list_chapters, read_chapter

print("=" * 72)
print("验收 1：§8「选题雷达」片段（list_chapters / read_chapter）")
print("=" * 72)
title, chapters = list_chapters("7069948840148732967")
print(f"《{title}》共 {len(chapters)} 章；前 6 章名（已按章号排序）：")
for cid, name in chapters[:6]:
    print("   ", name)

ch = read_chapter("7137980122702807592")
unmapped = [c for c in ch["pua_codes"] if c not in PUA2CHAR]
print(f"\n单章《{ch['title'][:34]}》")
print(f"   正文字数 {len(ch['text'])}  PUA 字符 {ch['pua_total']}/{len(ch['raw'])}")
print(f"   未映射码位 {len(unmapped)} 个 -> 残留乱码率 {len(unmapped)/max(len(ch['raw']),1):.4%}")
print(f"\n   正文前 200 字：\n   {ch['text'][:200]}")

print()
print("=" * 72)
print("验收 2：§8「殆知阁公版素材」片段")
print("=" * 72)
RAW = "https://raw.githubusercontent.com/garychowcmu/daizhigev20/master/"
req = u.Request(RAW + up.quote("子藏/笔记/阅微草堂笔记.txt"),
                headers={"User-Agent": "drama-pipeline"})
with u.urlopen(req, timeout=60) as r:
    txt = r.read().decode("utf-8", "replace")
print(f"取到 {len(txt):,} 字")
print("开头：", txt[:96].replace("\n", " "))
secs = [s for s in re.split(r"\n\s*\n", txt) if 50 < len(s) < 4000]
if secs:
    lens = sorted((len(s) for s in secs), reverse=True)
    n = len(lens)
    print(f"可切出 {n} 个独立段落；字数 中位 {lens[n//2]}  最长 {lens[0]}  "
          f"-> 单则篇幅正好是 3 分钟短剧量级")

print()
print("=" * 72)
print("验收 3：§8「维基文库」片段")
print("=" * 72)


def wikisource(title, tries=4, timeout=45):
    url = ("https://zh.wikisource.org/w/api.php?action=parse&prop=text"
           "&format=json&redirects=1&page=" + up.quote(title))
    for i in range(tries):
        try:
            with u.urlopen(u.Request(url, headers={"User-Agent": "drama"}),
                           timeout=timeout) as r:
                return json.loads(r.read()).get("parse", {}).get("text", {}).get("*", "")
        except Exception as e:
            print(f"      重试 {i+1}（{type(e).__name__}）")
            time.sleep(2 * (i + 1))
    return ""


for t in ["喻世明言", "警世通言", "初刻拍案驚奇", "二刻拍案驚奇"]:
    h = wikisource(t)
    print(f"   {t:8s} -> {len(h):>7,d} 字符")
