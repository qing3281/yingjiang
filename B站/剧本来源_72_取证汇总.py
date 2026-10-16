# -*- coding: utf-8 -*-
"""
探针 72 —— 报告取证汇总：把写进报告的关键结论逐条复测一遍

每条都输出「结论 + 实测证据」，报告里的数字全部来自这个脚本。
"""
import html as _h
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)
from curl_cffi import requests as creq

FP = r"D:\DSHworkspace\B站\情报\_font_probe"
MAP = {int(k, 0): v for k, v in json.load(open(
    os.path.join(FP, "map_shift.json"), encoding="utf-8"))["map"].items()}

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
DELAY = 1.6


def g(url, tries=3):
    for i in range(tries):
        try:
            r = s.get(url, headers=H, timeout=30, verify=CAB)
            if len(r.text) > 2000:
                return r
        except Exception as e:
            print(f"      (重试 {i+1}: {str(e)[:50]})")
        time.sleep(2.0)
    return r


def dec(t):
    return "".join(MAP.get(ord(c), c) for c in t)


print("=" * 90)
print("取证 1：网页端三页是否 SSR、能否无 cookie 取到结构化数据")
print("=" * 90)
r = g("https://fanqienovel.com/")
print(f"  首页       HTTP {r.status_code}  {len(r.text):>7,d}B  "
      f"__INITIAL_STATE__ {r.text.count('__INITIAL_STATE__')} 个  "
      f"/page/ 链接 {len(set(re.findall(r'/page/(\d{15,25})', r.text)))} 个")
BOOK = "7069948840148732967"
r2 = g(f"https://fanqienovel.com/page/{BOOK}")
chs = re.findall(r'["\'/]reader/(\d{15,25})', r2.text)
print(f"  详情页     HTTP {r2.status_code}  {len(r2.text):>7,d}B  "
      f"/reader/ 章节链接 {len(set(chs))} 个（去重）")
m = re.search(r"<title>(.*?)</title>", r2.text, re.S)
print(f"            <title> = {m.group(1)[:70] if m else 'N/A'}")

print()
print("=" * 90)
print("取证 2：字体哈希是否跨书跨章恒定（决定『解一次永久有效』是否成立）")
print("=" * 90)
books = [("7069948840148732967", "部族荣光"),
         ("6838086444733434884", "玄幻我顿悟了混沌体"),
         ("6823667291557727235", "皇后重生要谋反"),
         ("6883748331202284558", "惊鸿")]
for bid, name in books[:2]:
    rp = g(f"https://fanqienovel.com/page/{bid}")
    ids = list(dict.fromkeys(re.findall(r'["\'/]reader/(\d{15,25})', rp.text)))[:2]
    for cid in ids:
        rc = g(f"https://fanqienovel.com/reader/{cid}")
        fam = re.search(r"font-family:\s*([A-Za-z0-9]+)", rc.text)
        urls = re.findall(r"https://[^\"')]+\.woff2", rc.text)
        hsh = re.findall(r"/([0-9a-f]{15,20})\.woff2", rc.text)
        print(f"  {name[:10]:12s} 章 {cid[-6:]}  "
              f"font-family={fam.group(1) if fam else 'N/A'}  "
              f"hash={set(hsh) if hsh else 'N/A'}  字体URL {len(set(urls))} 个")
        time.sleep(DELAY)

print()
print("=" * 90)
print("取证 3：免费书 vs 锁章 —— 抓取能力边界")
print("=" * 90)
rp = g(f"https://fanqienovel.com/page/{BOOK}")
ids = list(dict.fromkeys(re.findall(r'["\'/]reader/(\d{15,25})', rp.text)))
print(f"  《部族荣光》目录共 {len(ids)} 章，抽样检查前 12 章：")
free = locked = 0
for i, cid in enumerate(ids[:12]):
    rc = g(f"https://fanqienovel.com/reader/{cid}")
    paras = re.findall(r"<p>(.*?)</p>", rc.text, re.S)
    body = _h.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
    txt = dec(body)
    lk = "isChapterLock\":true" in rc.text
    wc = re.search(r"chapterWordNumber\\?\":(\d+)", rc.text)
    pua = sum(1 for c in body if 0xE000 <= ord(c) <= 0xF8FF)
    if lk:
        locked += 1
    else:
        free += 1
    print(f"    第{i+1:2d}章 {'锁' if lk else '免费'}  "
          f"标称 {wc.group(1) if wc else '?':>6s} 字  "
          f"实得 {len(txt):>5d} 字  PUA {pua:>4d}")
    time.sleep(DELAY)
print(f"  -> 前 12 章中免费 {free} 章、锁定 {locked} 章")

print()
print("=" * 90)
print("取证 4：解锁文字还原度（抽样人工可读性）")
print("=" * 90)
rc = g(f"https://fanqienovel.com/reader/{ids[0]}")
paras = re.findall(r"<p>(.*?)</p>", rc.text, re.S)
raw = _h.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
txt = dec(raw)
print(f"  第 1 章：密文 {len(raw)} 字，PUA {sum(1 for c in raw if 0xE000<=ord(c)<=0xF8FF)} 个，"
      f"残留未映射 {sum(1 for c in txt if 0xE000<=ord(c)<=0xF8FF)} 个")
print(f"  开头 90 字：{txt[:90]}")
