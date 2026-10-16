# -*- coding: utf-8 -*-
"""探针 14：诊断——是否触发了反爬/频率限制"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

BOOK = "7069948840148732967"
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
s = creq.Session(impersonate="chrome131")

for i in range(3):
    r = s.get(f"https://fanqienovel.com/page/{BOOK}", headers=H, timeout=25)
    t = r.text
    print(f"第{i+1}次  HTTP={r.status_code}  长度={len(t)}  "
          f"含验证码={'verify' in t.lower() or 'captcha' in t.lower()}  "
          f"含 itemId={t.count('itemId')}  "
          f"含'验证'={t.count('验证')}  含'频繁'={t.count('频繁')}")
    print("  前 300 字:", repr(t[:300]))
    time.sleep(2)

print("\n--- 换 impersonate 重试 ---")
for imp in ["chrome124", "chrome120", "safari17_0", "edge101"]:
    try:
        r = creq.get(f"https://fanqienovel.com/page/{BOOK}", impersonate=imp,
                     headers=H, timeout=25)
        print(f"  {imp:12} HTTP={r.status_code} 长度={len(r.text)} itemId={r.text.count('itemId')}")
    except Exception as e:
        print(f"  {imp:12} 异常 {type(e).__name__}: {e}")
