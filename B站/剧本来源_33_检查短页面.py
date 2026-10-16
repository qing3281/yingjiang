# -*- coding: utf-8 -*-
"""
探针 33 —— 检查阅读页为何返回 6371 字节的短页面（是不是触发了风控/验证页）

对比：之前成功过的章节 id vs 新抽到的章节 id vs 裸 session vs 全新 session
"""
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

KNOWN_OK = "7137980122702807592"   # 之前成功抓到过正文的章节
H = {"Accept-Language": "zh-CN,zh;q=0.9"}


def probe(sess, url, label):
    try:
        r = sess.get(url, headers=H, timeout=25)
        body = r.text
        title = re.search(r"<title>(.*?)</title>", body, re.S)
        has_state = "__INITIAL_STATE__" in body
        has_p = body.count("<p>")
        print(f"  [{label}] {r.status_code} len={len(body)} __INITIAL_STATE__={has_state} <p>数={has_p}")
        print(f"       title={title.group(1).strip()[:70] if title else '?'}")
        if len(body) < 20000:
            txt = re.sub(r"<script.*?</script>", "", body, flags=re.S)
            txt = re.sub(r"<[^>]+>", " ", txt)
            txt = re.sub(r"\s+", " ", txt).strip()
            print(f"       正文片段: {txt[:300]}")
        return r
    except Exception as e:
        print(f"  [{label}] 异常 {type(e).__name__}: {e}")
        return None


print("=== A. 全新 session 抓已知可用的章节 ===")
s1 = creq.Session(impersonate="chrome131")
probe(s1, f"https://fanqienovel.com/reader/{KNOWN_OK}", "fresh-session")

print("\n=== B. 同一个 session 先访问详情页再访问章节页（带 Referer） ===")
s2 = creq.Session(impersonate="chrome131")
try:
    s2.get("https://fanqienovel.com/page/7137359676424850443", headers=H, timeout=25)
except Exception:
    pass
time.sleep(0.8)
probe(s2, f"https://fanqienovel.com/reader/{KNOWN_OK}", "with-referer")

print("\n=== C. 从详情页实时抽章节 id 再抓 ===")
s3 = creq.Session(impersonate="chrome131")
pg = s3.get("https://fanqienovel.com/page/7137359676424850443", headers=H, timeout=25).text
ids = []
seen = set()
for m in re.finditer(r'["\'/]reader/(\d{15,25})', pg):
    if m.group(1) not in seen:
        seen.add(m.group(1)); ids.append(m.group(1))
print(f"  详情页抽到 {len(ids)} 个章节 id，前 5: {ids[:5]}")
for cid in ids[:4]:
    probe(s3, f"https://fanqienovel.com/reader/{cid}", f"live-{cid[:8]}")
    time.sleep(1.2)

print(f"\n  已知可用 id 是否出现在本次抽出的列表里: {KNOWN_OK in ids}")
print(f"  所有抽到的 id: {ids[:8]}")
