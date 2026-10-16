# -*- coding: utf-8 -*-
"""
探针 49 —— 最终修正：补上第 4 轮上下文定罪

依据：把整章解密后通读，找出所有「读不通」的位置，
      再回到密文里定位对应码位，逐个订正。
"""
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)

sys.path.insert(0, r"D:\DSHworkspace\B站")
from curl_cffi import requests as creq

P = r"D:\DSHworkspace\B站\情报\_font_probe\pua_map_final.json"
M = {int(k, 0): v for k, v in json.load(open(P, encoding="utf-8")).items()}

FIX = {
    0xE3E9: "在", 0xE3EC: "家", 0xE3EF: "情", 0xE3F8: "还", 0xE3F9: "在",
    0xE3FB: "看", 0xE40E: "都", 0xE40F: "平",
    0xE41C: "些", 0xE41E: "是", 0xE41F: "十", 0xE420: "张",
    0xE423: "大", 0xE424: "爱", 0xE425: "两", 0xE426: "命", 0xE427: "全",
    0xE428: "后", 0xE42C: "被", 0xE42D: "1",
    0xE436: "了", 0xE444: "着", 0xE44B: "少", 0xE44C: "色", 0xE44D: "里",
    0xE45D: "地", 0xE461: "写",
    0xE46A: "没", 0xE46B: "书", 0xE46E: "像",
    0xE471: "为", 0xE477: "看", 0xE47D: "上", 0xE47F: "有",
    0xE480: "有", 0xE481: "法", 0xE483: "应",
    0xE488: "声", 0xE489: "身", 0xE48A: "国", 0xE48E: "他",
    0xE499: "对", 0xE4A0: "到", 0xE4A8: "点", 0xE4AA: "定",
    0xE4AB: "8", 0xE4AE: "正", 0xE4B5: "得", 0xE4B7: "告",
    0xE4BC: "过", 0xE4BE: "让", 0xE4C1: "人", 0xE4C2: "人",
    0xE4C4: "者", 0xE4C6: "原", 0xE4CC: "如", 0xE4D7: "部",
    0xE4DE: "一", 0xE4DF: "条", 0xE4E2: "光", 0xE4E4: "头",
    0xE4E7: "自", 0xE4F2: "的", 0xE4F3: "的", 0xE4F9: "心", 0xE4FA: "来",
    0xE505: "很", 0xE507: "小", 0xE508: "小", 0xE50B: "代",
    0xE50D: "么", 0xE50E: "分", 0xE510: "口", 0xE514: "西",
    0xE51B: "情", 0xE51D: "这", 0xE51E: "么", 0xE521: "我",
    0xE524: "长", 0xE528: "眼", 0xE52A: "不", 0xE52C: "0",
    0xE52E: "信", 0xE52F: "下", 0xE530: "却", 0xE531: "重",
    0xE535: "音", 0xE537: "m", 0xE53A: "之", 0xE53B: "前",
    0xE53E: "高", 0xE540: "太", 0xE541: "眼", 0xE543: "起",
    0xE545: "了", 0xE547: "她", 0xE54C: "子", 0xE54F: "四",
    0xE556: "a", 0xE557: "海", 0xE559: "个", 0xE55A: "个",
}
M.update(FIX)
json.dump({str(k): v for k, v in sorted(M.items())},
          open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"更新 {P}：{len(M)} 项（本轮修正 {len(FIX)} 项）")

# 验收
import html as _h
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25, verify=CAB)
    paras = re.findall(r"<p>(.*?)</p>", r.text, re.S)
    raws.append(_h.unescape(re.sub(r"<[^>]+>", "", "".join(paras))))
raw = "\n".join(raws)
dec = "".join(M.get(ord(c), c) for c in raw)

PHRASES = ["什么", "怎么", "这里", "那里", "已经", "不是", "一个", "我们", "你们",
           "他们", "自己", "因为", "所以", "但是", "如果", "可以", "没有", "知道",
           "觉得", "时候", "出来", "进去", "起来", "下来", "过来", "男人", "女人",
           "看着", "说道", "一声", "眼睛", "心里", "身体", "有些", "一点", "一样",
           "这样", "那样", "真的", "还是", "看见", "听到", "抬头", "低头", "手指",
           "声音", "地方", "突然", "开始", "最后", "表情", "眼神", "身上", "你们"]
EXPECT = "的一了是我不你在他人有着个这她上就都而及与说们来到时大地为子中"
cjk = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
top = [ch for ch, _ in cjk.most_common(24)]
h = sum(dec.count(p) for p in PHRASES)
inexp = sum(1 for ch in top if ch in EXPECT)
dev = sum((abs(i - EXPECT.find(ch)) if ch in EXPECT else 24) for i, ch in enumerate(top))
print(f"短语命中 {h}（修正前 128）")
print(f"前24高频字 {''.join(top)}")
print(f"落在期望集 {inexp}/24   序位总偏差 {dev}（修正前 392）")
print(f"\n样本：\n{dec[:300]}")
