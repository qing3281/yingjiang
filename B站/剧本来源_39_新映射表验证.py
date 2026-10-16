# -*- coding: utf-8 -*-
"""
探针 39 —— 用「字形表重新转录的全新映射表」验证系统性错位假设

发现：初版映射表整体**错位 1 格**（因为首轮转录时把第 2 行的两个空格
U+E3F6/E3F7 漏算了，导致从 U+E3F8 起全部后移一位）。

证据链：
  旧表 E3F8=和, E3F9=6, E3FA=别   → 实测语境是『还/在』『在』『看见』
  新表 E3F8=还, E3F9=在, E3FA=看   → 完美吻合

本探针：写入全新映射表 NEW_MAP，解码真实章节，看是否直接可读。
"""
import html as _html
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 从 D:\DSHworkspace\B站\情报\_font_probe\字形表_1.png（重新精确转录，含空格）
NEWCHARS = list(
    "在主特家军然表场4要只v和6别还在看见儿女"       # E3E8..E3FD
    "岁此象月3出战工相0男直失世F都平文什V"          # E3FE..E411
    "O将真T那当会立些u是十张学气大爱两命全"         # E412..E425
    "后东性通被接而感车山公了常以何可话先p"         # E426..E439
    "i叫轻M土w着变尔快l个说少色里安花远7"           # E43A..E44D
    "难师放t报认面道S克地度I好机U民写把万同水"     # E44E..E461
    "新没书电吃像斯5为y白几日教看但第加候作上"     # E462..E475
    "拉住有法r事应位利你声身国问马女他Y比父x"      # E476..E489
    "AHNSx边美对所金活回意到z从j知又内因点Q"       # E48A..E49C
    "三定8Rb正或夫向德听更得告并本q过记L让打"      # E49D..E4B0
    "f人就者去原满体做经K走如孩cG给使物最笑部"     # E4B1..E4C4
    "员等受k行一条果动光门头见往自解成处天能于"    # E4C5..E4D8
    "名其发总母的死手入路进心来h时力多开已许d"     # E4D9..E4EC
    "至由很界n小与Z想代么分生口再妈望次西风种"     # E4ED..E500
    "带J实情才这E我神格长觉间年眼无不亲关结0"      # E501..E514
    "友信下却重己老2音字m呢明之前高PB目太e9"       # E515..E528
    "起棱她也W用方子英每理便四数期中C外样a海"     # E529..E53B
    "们任"                                          # E53C..E53D
)
# 该字体 cmap 在 U+E3E8~U+E55B 之间有 10 个空档，必须把字符按空档跳过填入
GAPS = [0xE3F6, 0xE3FE, 0xE3FF, 0xE419, 0xE45B, 0xE4B6, 0xE4D4, 0xE4D8, 0xE51A, 0xE51F]

codes = [c for c in range(0xE3E8, 0xE55C) if c not in GAPS]
print(f"码位 {len(codes)} 个，转字符 {len(NEWCHARS)} 个")
n = min(len(codes), len(NEWCHARS))
NEW_MAP = {codes[i]: NEWCHARS[i] for i in range(n)}
if len(codes) != len(NEWCHARS):
    print(f"⚠ 数量不等：码位 {len(codes)} vs 字符 {len(NEWCHARS)}")

from curl_cffi import requests as creq
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
t = s.get("https://fanqienovel.com/reader/7137980122702807592", headers=H, timeout=25).text
raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(re.findall(r"<p>(.*?)</p>", t, re.S))))

dec_new = "".join(NEW_MAP.get(ord(c), c) for c in raw)
print("\n=== 新映射表解码结果（前 500 字）===")
print(dec_new[:500])
left = sum(1 for c in dec_new if "\ue000" <= c <= "\uf8ff")
print(f"\n残留 PUA: {left}")
