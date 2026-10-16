# -*- coding: utf-8 -*-
"""探针 80 —— 验收：报告里给出的三段可运行代码是否真的能跑"""
import json
import sys
import time
import urllib.parse as up
import urllib.request as u

sys.path.insert(0, r"D:\DSHworkspace\B站")
sys.stdout.reconfigure(encoding="utf-8")

print("=" * 70)
print("验收 1：报告 §8 的「选题雷达」片段")
print("=" * 70)
from fanqie_reader import list_chapters, read_chapter

title, chapters = list_chapters("7069948840148732967")
print(f"《{title}》共 {len(chapters)} 章；前 8 章名：")
for cid, name in chapters[:8]:
    print("   ", name)

ch = read_chapter("7137980122702807592")
print(f"\n单章：{ch['title'][:40]}  正文 {len(ch['text'])} 字  未覆盖 {ch.get('pua_codes')}")
print("前 160 字：", ch["text"][:160])

print()
print("=" * 70)
print("验收 2：报告 §8 的「殆知阁公版素材」片段")
print("=" * 70)
RAW = "https://raw.githubusercontent.com/garychowcmu/daizhigev20/master/"
rel = "子藏/笔记/阅微草堂笔记.txt"
req = u.Request(RAW + up.quote(rel), headers={"User-Agent": "drama-pipeline"})
with u.urlopen(req, timeout=60) as r:
    txt = r.read().decode("utf-8", "replace")
print(f"取到 {len(txt)} 字")
print("开头：", txt[:110].replace("\n", " "))
# 抽一则看看「单则篇幅」是否符合 3 分钟短剧
import re
secs = re.split(r"\n\s*\n", txt)
lens = sorted((len(s) for s in secs if 50 < len(s) < 4000), reverse=True)[:8]
print("最长的几则字数：", lens)

print()
print("=" * 70)
print("验收 3：报告 §8 的「维基文库」片段")
print("=" * 70)


def wikisource(title, tries=4, timeout=45):
    url = ("https://zh.wikisource.org/w/api.php?action=parse&prop=text"
           "&format=json&redirects=1&page=" + up.quote(title))
    for i in range(tries):
        try:
            with u.urlopen(u.Request(url, headers={"User-Agent": "drama"}),
                           timeout=timeout) as r:
                d = json.loads(r.read())
            return d.get("parse", {}).get("text", {}).get("*", "")
        except Exception as e:
            print(f"     重试 {i+1}（{type(e).__name__}）")
            time.sleep(2 * (i + 1))
    return ""


for t in ["喻世明言", "警世通言", "初刻拍案驚奇"]:
    h = wikisource(t)
    print(f"  {t:8s} -> {len(h):>7,d} 字符")
