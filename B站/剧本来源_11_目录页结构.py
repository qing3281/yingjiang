# -*- coding: utf-8 -*-
"""探针 11：定位目录页里 chapter_id 的真实载体结构"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

BOOK = "7069948840148732967"
r = creq.get(
    f"https://fanqienovel.com/page/{BOOK}",
    impersonate="chrome131",
    headers={"Accept-Language": "zh-CN,zh;q=0.9"},
    timeout=25,
)
t = r.text
print("HTTP", r.status_code, "长度", len(t))

for kw in ["chapter_id", "chapterId", "itemId", "chapterList", "chapter-list",
           "__INITIAL_STATE__", "self.__next_f", "reader/", "章节"]:
    print(f"  {kw!r:24} 出现 {t.count(kw)} 次")

print("\n--- 第一个 'chapter_id' 前后 300 字 ---")
i = t.find("chapter_id")
print(repr(t[max(0, i - 150): i + 300]) if i >= 0 else "(无)")

print("\n--- 第一个 'reader/' 前后 300 字 ---")
i = t.find("reader/")
print(repr(t[max(0, i - 200): i + 300]) if i >= 0 else "(无)")

print("\n--- 所有 /reader/ 链接样本 ---")
links = re.findall(r'["\'/]reader/(\d{15,25})', t)
print("数量", len(links), "前 8 个", links[:8])
