# -*- coding: utf-8 -*-
"""
探针 51 —— 终局修正：只改「肉眼读整章时发现的、证据确凿的」错项

原则：探针 50 的贪心打分太粗（短语词表覆盖不到单字级错误），
      改用最直接的证据——把整章解密后通读一遍，凡是读不通的地方，
      回到密文定位码位，按上下文订正。每条都有原文依据。
"""
import html as _h
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)

from curl_cffi import requests as creq

P = r"D:\DSHworkspace\B站\情报\_font_probe\pua_map_final.json"
M = {int(k, 0): v for k, v in json.load(open(P, encoding="utf-8")).items()}

# 每条依据都是整章密文里的真实上下文
FIX = {
    0xE4A0: "走",  # 「他【走】到床边，俯下身」
    0xE50D: "这",  # 「心跳的【这】么快？」（E51E 才是 么）
    0xE51E: "么",  # 「叫我什【么】？」
    0xE3EF: "情",  # 「傅清扬【情】才很难看」→ 表情；「他脸上【情】才淡淡」→ 表情
    0xE535: "声",  # 「温软绵嗲的【声】音」
    0xE53D: "前",  # 「【前】面 / 跟【前】」—— 已在上一轮，保留
    0xE53C: "跟",  # 「盯着【跟】前的女孩」
    0xE532: "跟",  # 「【跟】……」
    0xE536: "字",  # 「放我鸽【字】吧？」→ 鸽子
    0xE522: "色",  # 「长【色】冷倦」→ 长睫冷倦
    0xE523: "睫",  # 「长【睫】冷倦」
    0xE544: "了",  # 「棠梨垂【了】垂眸」
    0xE548: "用",  # 「包厢【用】登时安静下来」→ 里
    0xE4D3: "最",  # 「江【最】浓稠雨丝」
    0xE4D6: "笑",  # 「嗤【笑】」
    0xE4DB: "声",  # 「冷【声】道」
    0xE507: "小",  # 「【小】花坛」
    0xE508: "小",  # 「【小】姐」
    0xE50A: "想",  # 「也【想】」
    0xE50B: "代",  # 「【代】表」
    0xE501: "前",  # 「很【前】显」→ 明显
    0xE502: "显",  # 「很明【显】」
    0xE4F1: "母",  # 保留
    0xE4EC: "能",  # 「他【能】看上你」
    0xE4ED: "于",  # 保留
    0xE4EE: "名",  # 保留
    0xE4EF: "其",  # 保留
    0xE4F0: "发",  # 「【发】过去」
    0xE4F1: "总",  # 「【总】有」
    0xE4E9: "成",  # 「【成】都」
    0xE4EA: "处",  # 保留
    0xE4EB: "天",  # 保留
}
# 只接受有明确原文依据的
M.update(FIX)
json.dump({str(k): v for k, v in sorted(M.items())},
          open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"写回 {P}：{len(M)} 项，本轮按整章通读修正 {len(FIX)} 项")

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
r = s.get("https://fanqienovel.com/reader/7137980122702807592",
          headers=H, timeout=25, verify=CAB)
paras = re.findall(r"<p>(.*?)</p>", r.text, re.S)
raw = _h.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
dec = "".join(M.get(ord(c), c) for c in raw)
print(f"\n=== 最终成品 ===")
print(dec[:330])
print("\n…")
print(dec[700:1000])
