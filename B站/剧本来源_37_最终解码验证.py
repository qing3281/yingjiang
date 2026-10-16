# -*- coding: utf-8 -*-
"""
探针 37 —— 应用合并补丁后的最终解码验证
"""
import html as _html
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
import fanqie_font

MP = r"D:\DSHworkspace\B站\情报\_font_probe\font_corrections_merged.json"
j = json.load(open(MP, encoding="utf-8"))
clean = {}
for k, v in j.items():
    try:
        clean[int(k, 0)] = v
    except (ValueError, TypeError):
        pass          # 跳过 '_note' 之类非码位键
fanqie_font.PUA2CHAR.update(clean)
print(f"已应用补丁 {len(clean)} 条，映射表总数 {len(fanqie_font.PUA2CHAR)}")

from curl_cffi import requests as creq
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
t = s.get("https://fanqienovel.com/reader/7137980122702807592", headers=H, timeout=25).text
raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(re.findall(r"<p>(.*?)</p>", t, re.S))))
d = fanqie_font.decrypt(raw)

print("\n=== 最终解密（前 460 字）===")
print(d[:460])
print("\n=== 末尾 180 字 ===")
print(d[-180:])
pua = sum(1 for c in raw if "\ue000" <= c <= "\uf8ff")
left = sum(1 for c in d if "\ue000" <= c <= "\uf8ff")
print(f"\n原文 {len(raw)} 字 / PUA {pua} / 残留 {left} -> 覆盖率 {(1 - left / max(1, pua)) * 100:.1f}%")
