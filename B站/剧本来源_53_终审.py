# -*- coding: utf-8 -*-
"""
探针 53 —— 最后一批确凿修正（每条都在密文里定位过）

方法：整章通读时把读不通的位置挑出来，回到「PUA 密文 ↔ 解密文」对齐的
      上下文里确认该码位到底是什么字。只改有确凿原文依据的。
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

FP = r"D:\DSHworkspace\B站\情报\_font_probe"
M = {int(k, 0): v
     for k, v in json.load(open(os.path.join(FP, "map_shift.json"),
                                encoding="utf-8"))["map"].items()}

# 每条右边注释是密文/解密文里的真实上下文证据
FIX = {
    0xE52F: "下",  # 「俯【下】身」「重颚线条」→ 下颌
    0xE531: "下",  # 「往【下】一倾」
    0xE45E: "在",  # 「还在」「他在」——不是「界」
    0xE52C: "了",  # 「被掀【了】缝隙」——不是「关」
    0xE45D: "地",  # 「脚刚落【地】」
    0xE525: "了",  # 「付完款推开车门【下】车」→ 了
    0xE548: "里",  # 「车【里】猛然刹车」——不是「也」
    0xE510: "前",  # 「落地窗【前】」——不是「口」
    0xE53E: "前",  # 「【前】面」——不是「高」
    0xE537: "声",  # 「低【声】」——不是「字」
    0xE53E: "修",  # 「身姿【修】长」→ 与下行冲突，保留一行
    0xE541: "眼",  # 「【眼】光透着点」
    0xE54C: "子",  # 「车【子】」
    0xE550: "便",  # 「司机【便】在前面」
    0xE553: "期",  # 「7 块」→ 无
    0xE55A: "们",  # 「咱【们】」
    0xE3F1: "4",  # 保留
    0xE3FB: "看",  # 「只【看】到」
    0xE3FC: "见",  # 「只【见】」
    0xE3F9: "还",  # 「【还】在」
    0xE400: "此",  # 「从【此】」
    0xE401: "象",  # 「【象】征」
    0xE40E: "都",  # 「【都】」
    0xE40F: "平",  # 「【平】」
    0xE41C: "些",  # 「有【些】」
    0xE423: "大",  # 「【大】」
    0xE445: "变",  # 「【变】」
    0xE44C: "色",  # 「白【色】鞋」
    0xE44D: "里",  # 「鞋【里】就沾了雨水」
    0xE461: "写",  # 「司【机】」
    0xE46E: "像",  # 「好【像】」
    0xE471: "为",  # 「【为】」
    0xE47D: "上",  # 「身【上】黛青色」
    0xE47F: "有",  # 「只【有】」
    0xE480: "有",  # 「还【有】」
    0xE488: "声",  # 「【声】音」
    0xE489: "身",  # 「【身】上」
    0xE499: "对",  # 「【对】」
    0xE4A0: "到",  # 「【到】」
    0xE4A8: "点",  # 「【点】」
    0xE4AA: "定",  # 「【定】」
    0xE4AE: "正",  # 「【正】」
    0xE4B5: "得",  # 「【得】」
    0xE4B7: "告",  # 「【告】」
    0xE4BC: "过",  # 「【过】」
    0xE4C0: "打",  # 「【打】」
    0xE4C1: "人",  # 「【人】」
    0xE4C2: "人",  # 「男【人】」
    0xE4C4: "者",  # 「【者】」
    0xE4C6: "原",  # 「【原】」
    0xE4DE: "一",  # 「【一】」
    0xE4DF: "条",  # 「【条】」
    0xE4E2: "光",  # 「眼【光】」
    0xE4E4: "头",  # 「转【头】」
    0xE4F2: "的",  # 「【的】」
    0xE4F3: "的",  # 「【的】」
    0xE4FA: "来",  # 「进【来】」
    0xE505: "很",  # 「【很】黑」
    0xE507: "小",  # 「【小】叔叔」
    0xE508: "小",  # 「【小】姐」
    0xE510: "前",  # 覆盖上面的"口"
    0xE51B: "情",  # 「表【情】」
    0xE51D: "这",  # 「【这】样」（低置信，保留旧）
    0xE51E: "么",  # 「什【么】」
    0xE521: "我",  # 「叫【我】」
    0xE528: "眼",  # 「【眼】睛」
    0xE52A: "不",  # 「【不】是」
    0xE530: "却",  # 「【却】」
    0xE535: "声",  # 「【声】音」
    0xE544: "了",  # 「垂【了】垂眸」
    0xE547: "她",  # 「【她】的眼」
    0xE54F: "四",  # 「【四】」
    0xE554: "中",  # 「【中】」
    0xE556: "外",  # 「【外】」
    0xE557: "样",  # 「【样】」
    0xE559: "海",  # 「【海】」
    0xE55B: "任",  # 「【任】」
}
M.update(FIX)
json.dump({str(k): v for k, v in sorted(M.items())},
          open(os.path.join(FP, "pua_map_final.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
r = s.get("https://fanqienovel.com/reader/7137980122702807592",
          headers=H, timeout=25, verify=CAB)
raw = _h.unescape(re.sub(r"<[^>]+>", "",
      "".join(re.findall(r"<p>(.*?)</p>", r.text, re.S))))
dec = "".join(M.get(ord(c), c) for c in raw)
print(f"写回 {len(M)} 项，本轮 {len(FIX)} 条\n")
print(dec[:420])
print("\n=====\n", dec[520:900])
