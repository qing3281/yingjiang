# -*- coding: utf-8 -*-
"""
探针 48 —— 锁定最终映射表：以 map_shift(旧表) 为底，套上已由上下文定罪的修正

为什么以旧表为底：
  频率验收（探针 47）——旧表前 24 高频字 = 的了一棠梨人没上着傅她里小重在开叔冷有清色淡扬是
  其中 10/24 落在中文期望高频集，且序位总偏差 392；
  而「权威字形表」新转录只有 2/24、偏差 550。
  短语命中（探针 45）：旧表 152 次，新表 0 次。
  → 旧表在字级上基本正确，只需修掉被上下文明确证伪的少量错位。
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import certifi

CAB = r"C:\Windows\Temp\dsh_cacert.pem"
if not os.path.exists(CAB):
    import shutil
    shutil.copy(certifi.where(), CAB)

sys.path.insert(0, r"D:\DSHworkspace\B站")
import fanqie_novel as F
from curl_cffi import requests as creq

BASE = {int(k, 0): v for k, v in json.load(
    open(r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json", encoding="utf-8"))["map"].items()}

# 全部修正项：依据 = 真实语料上下文 + 字体高频码位对账图（情报/_font_probe/对账_最高频码位.png）
FIX = {
    0xE3E9: "在",   # 对账图直接渲染 U+E3E9 字形 = 在
    0xE409: "男",   # 对账图渲染 = 男
    0xE41E: "是",   # 对账图渲染 = 是
    0xE428: "后",   # 「宽阔的【后】背」
    0xE44C: "色",   # 对账图渲染 = 色
    0xE44D: "里",   # 对账图渲染 = 里
    0xE480: "有",   # 对账图渲染 = 有
    0xE488: "声",   # 「轻笑了【声】」
    0xE489: "身",   # 「【身】姿修长」
    0xE4BC: "过",   # 「男人转【过】头」
    0xE4E2: "光",   # 「月【光】泄进来」
    0xE4E4: "头",   # 「转过身【头】」→ 转【过】头
    0xE4F3: "的",   # 出现 163 次，对账图渲染 = 的
    0xE4F9: "心",   # 「【心】跳的有些快」
    0xE4FA: "来",   # 对账图渲染 = 来
    0xE505: "很",   # 「瞳仁【很】黑」
    0xE508: "小",   # 对账图渲染 = 小
    0xE50E: "分",   # 「切割的【分】明」
    0xE510: "口",   # 对账图渲染 = 口
    0xE521: "我",   # 对账图渲染 = 我
    0xE524: "长",   # 「身姿修【长】」
    0xE528: "眼",   # 对账图渲染 = 眼
    0xE52A: "不",   # 对账图渲染 = 不
    0xE531: "下",   # 对账图渲染 = 下；「俯【下】身」「【下】颚线」
    0xE53B: "前",   # 「切割的分【前】」→ 分明
    0xE53D: "前",   # 「落地窗【外】」→ 前?
    0xE545: "了",   # 「被掀【了】缝隙」
    0xE547: "她",   # 对账图渲染 = 她
    0xE54C: "子",   # 对账图渲染 = 子
    0xE433: "车",   # 「【车】里猛然刹车」
    0xE436: "了",   # 对账图渲染 = 了
    0xE4DE: "一",   # 对账图渲染 = 一
    0xE4C2: "人",   # 对账图渲染 = 人
    0xE444: "着",   # 对账图渲染 = 着
    0xE47D: "上",   # 对账图渲染 = 上
    0xE4FF: "开",   # 对账图渲染 = 开
}

FINAL = dict(BASE)
FINAL.update(FIX)

out = r"D:\DSHworkspace\B站\情报\_font_probe\pua_map_final.json"
json.dump({str(k): v for k, v in sorted(FINAL.items())},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"写出 {out}：{len(FINAL)} 项（底表 {len(BASE)} + 修正 {len(FIX)}）")

# ── 验收 ──
s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209", "7137980469551104526"]:
    r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25, verify=CAB)
    raws.append(F.clean_chapter_text(r.text))
raw = "\n".join(raws)

PHRASES = ["什么", "怎么", "这里", "那里", "已经", "不是", "一个", "我们", "你们",
           "他们", "自己", "因为", "所以", "但是", "如果", "可以", "没有", "知道",
           "觉得", "时候", "出来", "进去", "起来", "下来", "过来", "男人", "女人",
           "看着", "说道", "一声", "眼睛", "心里", "身体", "有些", "一点", "一样",
           "这样", "那样", "真的", "还是", "看见", "听到", "抬头", "低头", "手指",
           "声音", "地方", "突然", "已经", "开始", "最后", "表情", "眼神", "身上"]
EXPECT = "的一了是我不你在他人有着个这她上就都而及与说们来到时大地为子中"

from collections import Counter

for tag, tab in (("修正前(BASE)", BASE), ("修正后(FINAL)", FINAL)):
    dec = "".join(tab.get(ord(c), c) for c in raw)
    h = sum(dec.count(p) for p in PHRASES)
    cjk = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
    top = [ch for ch, _ in cjk.most_common(24)]
    inexp = sum(1 for ch in top if ch in EXPECT)
    dev = sum((abs(i - EXPECT.find(ch)) if ch in EXPECT else 24) for i, ch in enumerate(top))
    print(f"\n=== {tag} ===")
    print(f"  短语命中 {h}   前24高频字 {''.join(top)}")
    print(f"  落在期望集 {inexp}/24   序位总偏差 {dev}")
    print(f"  样本: {dec[:200]}".replace("\n", " "))
