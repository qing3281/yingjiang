# -*- coding: utf-8 -*-
"""
探针 34 —— 验证码封禁的判定维度与恢复条件

A. 换一个全新的 curl_cffi session（无 cookie 继承）立刻再抓 → 判断是 session 级还是 IP 级
B. 换 impersonate 指纹（chrome vs safari vs edge）→ 看是否与 TLS 指纹有关
C. 只抓详情页（/page/）→ 看是否只有 /reader/ 路径被封
D. 静默 60 秒后再抓 → 看是否时间衰减
"""
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

CID = "7137980122702807592"
BID = "7137359676424850443"
H = {"Accept-Language": "zh-CN,zh;q=0.9"}


def check(sess, url, label):
    try:
        r = sess.get(url, headers=H, timeout=25)
        t = re.search(r"<title>(.*?)</title>", r.text, re.S)
        title = t.group(1).strip()[:40] if t else "?"
        captcha = "验证码" in title
        ok = (not captcha) and len(r.text) > 20000
        print(f"  {label:38s} {r.status_code} len={len(r.text):7d} title={title:22s} {'✅正常' if ok else '⛔拦截'}")
        return ok
    except Exception as e:
        print(f"  {label:38s} 异常 {type(e).__name__}")
        return False


print("=== A. 全新 session + 默认指纹 ===")
for i in range(3):
    s = creq.Session(impersonate="chrome131")
    check(s, f"https://fanqienovel.com/reader/{CID}", f"fresh-session #{i+1}")
    time.sleep(1.5)

print("\n=== B. 不同 TLS 指纹 ===")
for imp in ["chrome131", "chrome124", "chrome120", "safari17_0", "edge101", "chrome110"]:
    try:
        s = creq.Session(impersonate=imp)
        check(s, f"https://fanqienovel.com/reader/{CID}", f"impersonate={imp}")
    except Exception as e:
        print(f"  impersonate={imp} 不可用: {type(e).__name__}")
    time.sleep(1.5)

print("\n=== C. 只抓详情页 /page/ 和首页 ===")
s = creq.Session(impersonate="chrome131")
check(s, "https://fanqienovel.com/", "首页 /")
time.sleep(1.2)
check(s, f"https://fanqienovel.com/page/{BID}", f"详情页 /page/{BID[:8]}")
time.sleep(1.2)
check(s, f"https://fanqienovel.com/reader/{CID}", "阅读页 /reader/")

print("\n=== D. 静默 60 秒后重试阅读页 ===")
time.sleep(60)
s = creq.Session(impersonate="chrome131")
check(s, f"https://fanqienovel.com/reader/{CID}", "60s 后 fresh-session")
