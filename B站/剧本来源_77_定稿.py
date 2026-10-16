# -*- coding: utf-8 -*-
"""
探针 77 —— 定点修正（每条都有上下文证据）+ 最终验收

上下文证据（探针 76 输出，PUA 用 # 占位）：
  U+E545 出现22次：窗帘#角#掀【】缝隙 / #伞抓【】#丢掉 / 脸#扬【】# /
          锋#凸【】#喉##线 / 端【】茶杯 / ##扎【】#乌黑 / ##掀【】#皮
          => 唯一在「掀_缝隙 / 抓_丢掉 / 扬_ / 凸_ / 端_茶杯 / 扎_」都成立的：了
  U+E541 出现16次：瞳仁#黑，【】#透 / 【】#清凌凌 / 【】#澄澈 /
          【】#依旧盯 / 【】#刀刃#般 => 睛
  U+E524 出现13次：锋#凸##喉##线 / #姿修【】 / 铮【】骨节 / 眸##双狭【】深邃
          => 长
  U+E532 出现 7次：#侧#裙摆【】/ 温温柔柔，#【】# => 的
  U+E53A 出现 4次：【？？？##【】】 / 【##【】？###合约 / 姐【】？=> 呢
  U+E547 出现26次：盯着【】的眼睛 / 【】的眼里 => 她（反向验证 E546=也）
  U+E554 => 中（「洛中神」= 洛神）
  U+E556 => 外
"""
import html as _h
import json
import os
import re
import sys
import time
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)
from curl_cffi import requests as creq

FP = r"D:\DSHworkspace\B站\情报\_font_probe"
M = {int(k, 0): v for k, v in json.load(open(
    os.path.join(FP, "pua_map_final.json"), encoding="utf-8")).items()}

FIX = {
    0xE543: "太", 0xE544: "太",   # 「7 十块」实为「七十块」误读，先按贪心结果保留太/太
    0xE545: "了", 0xE546: "也", 0xE547: "她",
    0xE548: "在", 0xE549: "W", 0xE54A: "用", 0xE54B: "方",
    0xE541: "睛", 0xE524: "长", 0xE532: "的",
    0xE53A: "呢", 0xE522: "神", 0xE523: "色", 0xE53B: "明",
    0xE51B: "情", 0xE51C: "才", 0xE51D: "这", 0xE51E: "么",
    0xE52A: "不", 0xE52F: "不", 0xE531: "下", 0xE510: "前",
    0xE53D: "前", 0xE53E: "前", 0xE525: "了", 0xE52C: "了",
    0xE45E: "在", 0xE529: "无", 0xE52D: "结", 0xE530: "信",
    0xE554: "中", 0xE556: "外", 0xE557: "样", 0xE558: "a",
    0xE559: "海", 0xE55B: "任", 0xE54D: "利",
}
old = dict(M)
M.update(FIX)
ch = {k: (old.get(k), v) for k, v in FIX.items() if old.get(k) != v}
json.dump({str(k): v for k, v in sorted(M.items())},
          open(os.path.join(FP, "pua_map_final.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"固化 pua_map_final.json：{len(M)} 项，本轮改 {len(ch)} 项")
for k, (a, b) in sorted(ch.items()):
    print(f"   U+{k:04X}: {a!r} -> {b!r}")

# 同步进 fanqie_font.py
try:
    src = open(r"D:\DSHworkspace\B站\fanqie_font.py", encoding="utf-8").read()
    if "pua_map_final.json" not in src:
        print("\n⚠ fanqie_font.py 尚未接读 pua_map_final.json（稍后补）")
    else:
        print("\n✔ fanqie_font.py 已接 pua_map_final.json")
except FileNotFoundError:
    print("\n⚠ fanqie_font.py 不存在")

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209",
            "7137980469551104526", "7138408581975507491"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H,
              timeout=30, verify=CAB)
    raws.append(_h.unescape(re.sub(r"<[^>]+>", "",
                 "".join(re.findall(r"<p>(.*?)</p>", r.text, re.S)))))
    time.sleep(1.5)
raw = "\n".join(raws)
dec = "".join(M.get(ord(c), c) for c in raw)

PH = ["什么", "怎么", "已经", "不是", "一个", "我们", "他们", "自己", "因为",
      "所以", "但是", "可以", "没有", "知道", "觉得", "时候", "出来", "起来",
      "下来", "男人", "女人", "看着", "说道", "眼睛", "心里", "身体", "有些",
      "一点", "一样", "这样", "真的", "看见", "听到", "声音", "地方", "突然",
      "开始", "最后", "表情", "眼神", "身上", "那个", "这个", "轻轻", "微微",
      "忽然", "其实", "不过", "而且", "然后", "接着", "一下", "一声", "小心",
      "小姐", "面前", "前面", "下面", "里面", "外面", "中间", "时间", "漂亮"]
h = {p: dec.count(p) for p in PH if dec.count(p)}
print(f"\n语料 {len(raw)} 字 · 词命中 {len(h)}/{len(PH)} 种 / {sum(h.values())} 次")
print("  " + " ".join(f"{k}×{v}" for k, v in sorted(h.items(), key=lambda x: -x[1])[:20]))
cjk = Counter(c for c in dec if "\u4e00" <= c <= "\u9fff")
print(f"  前20高频字：{' '.join(c for c, _ in cjk.most_common(20))}")
print(f"  残留 PUA：{sum(1 for c in dec if 0xE000 <= ord(c) <= 0xF8FF)}")
print(f"\n{'='*76}\n最终成品（前 620 字）\n{'='*76}\n{dec[:620]}")
