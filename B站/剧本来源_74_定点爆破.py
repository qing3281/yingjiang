# -*- coding: utf-8 -*-
"""
探针 74 —— 定点爆破：对「已知该怎么改」的码位做前后打分对比

打分函数换成更贴近真实阅读的指标：
  1) 词表命中（60 个高频双字词）
  2) 常见虚词/高频字表命中
  3) 明显错字黑名单扣分
逐条 swap 后打分，只保留净提升的。
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
BASE = {int(k, 0): v for k, v in json.load(open(
    os.path.join(FP, "map_shift.json"), encoding="utf-8"))["map"].items()}

s = creq.Session(impersonate="chrome124")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
raws = []
for cid in ["7137980122702807592", "7137980233667314209",
            "7137980469551104526", "7138408581975507491",
            "7137980122702807600", "7137980233667314300"]:
    try:
        r = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H,
                  timeout=30, verify=CAB)
        p = re.findall(r"<p>(.*?)</p>", r.text, re.S)
        if len(p) > 5:
            raws.append(_h.unescape(re.sub(r"<[^>]+>", "", "".join(p))))
    except Exception:
        pass
    time.sleep(1.4)
raw = "\n".join(raws)

WORD = ["什么", "怎么", "已经", "不是", "一个", "我们", "你们", "他们", "自己",
        "因为", "所以", "但是", "可以", "没有", "知道", "觉得", "时候", "出来",
        "起来", "下来", "过去", "过来", "男人", "女人", "看着", "说道", "眼睛",
        "心里", "身体", "有些", "一点", "一样", "这样", "真的", "看见", "听到",
        "声音", "地方", "突然", "开始", "最后", "表情", "眼神", "身上", "那个",
        "这个", "轻轻", "微微", "忽然", "其实", "要是", "不过", "而且", "或者",
        "然后", "接着", "一下", "一声", "一眼", "一身", "小心", "小姐", "心里",
        "面前", "前面", "下面", "上面", "里面", "外面", "中间", "时间", "眼神"]
# 高频虚词/常用字（正文里应大量出现）
COMMON = "的一了是我不你在他人有着个这她上就都而及与说们来到时大地为子中下前里后小心还只把被给对能会要好没很间面重么那从只"
# 这些字出现在解密文里基本可断定映射错了
BAD = set("稜棠傅扬尊瞬肤层凭空哦嗯梨")


def score(tab):
    dec = "".join(tab.get(ord(c), c) for c in raw)
    w = sum(dec.count(x) for x in WORD)
    cjk = Counter(c for c in dec if "\u4e00" <= c <= "\u9fff")
    c = sum(v for k, v in cjk.items() if k in COMMON)
    b = sum(v for k, v in cjk.items() if k in BAD)
    return w * 10 + c - b * 30, w, c, b


b0, w0, c0, x0 = score(BASE)
print(f"基线：总分 {b0}  词命中 {w0}  常用字 {c0}  错字 {x0}")
print(f"语料 {len(raw)} 字\n")

CANDS = {
    0xE51B: "情", 0xE51C: "才", 0xE51D: "这", 0xE51E: "么", 0xE520: "神",
    0xE521: "我", 0xE522: "格", 0xE523: "长", 0xE524: "觉", 0xE526: "间",
    0xE527: "年", 0xE528: "眼", 0xE529: "无", 0xE52B: "亲", 0xE52D: "结",
    0xE52E: "友", 0xE52F: "不", 0xE530: "信", 0xE531: "下", 0xE532: "却",
    0xE533: "重", 0xE534: "己", 0xE535: "老", 0xE536: "2", 0xE537: "音",
    0xE538: "字", 0xE539: "m", 0xE53A: "呢", 0xE53B: "明", 0xE53C: "之",
    0xE53D: "前", 0xE53F: "高", 0xE540: "P", 0xE541: "B", 0xE542: "目",
    0xE543: "太", 0xE544: "e", 0xE545: "9", 0xE546: "起", 0xE547: "稜",
    0xE548: "她", 0xE549: "也", 0xE54A: "W", 0xE54B: "用", 0xE54C: "方",
    0xE54D: "子", 0xE54E: "英", 0xE54F: "每", 0xE550: "理", 0xE551: "便",
    0xE552: "四", 0xE553: "数", 0xE554: "期", 0xE555: "中", 0xE556: "C",
    0xE557: "外", 0xE558: "样", 0xE559: "a", 0xE55A: "海", 0xE55B: "们",
    0xE4A7: "修", 0xE510: "前", 0xE53E: "前", 0xE502: "前", 0xE535: "心",
    0xE4F9: "心", 0xE525: "了", 0xE52C: "了", 0xE544: "了", 0xE45E: "在",
    0xE548: "在", 0xE45D: "地", 0xE541: "眼", 0xE557: "像", 0xE3F9: "还",
    0xE50A: "沉", 0xE507: "小", 0xE508: "小", 0xE529: "无", 0xE52A: "不",
    0xE554: "中", 0xE556: "外", 0xE530: "信", 0xE532: "却", 0xE545: "9",
    0xE546: "起", 0xE54C: "方", 0xE54F: "每", 0xE53F: "高", 0xE540: "P",
    0xE3FF: "-", 0xE4D6: "笑", 0xE4C4: "者", 0xE536: "2", 0xE537: "音",
    0xE538: "字", 0xE539: "m", 0xE53A: "呢", 0xE53B: "明", 0xE53C: "之",
}

cur = dict(BASE)
best = b0
accepted = []
for _ in range(8):
    improved = False
    for cp, ch in CANDS.items():
        if cur.get(cp) == ch:
            continue
        trial = dict(cur)
        trial[cp] = ch
        sc, w, c, x = score(trial)
        if sc > best:
            cur, best = trial, sc
            accepted.append((cp, BASE.get(cp), ch, sc, w, c, x))
            improved = True
    if not improved:
        break

sc, w, c, x = score(cur)
print(f"收敛：总分 {sc}（基线 {b0}）  词命中 {w}（{w0}）  "
      f"常用字 {c}（{c0}）  错字 {x}（{x0}）")
print(f"接受 {len(accepted)} 条修正：")
for cp, old, new, s_, w_, c_, x_ in accepted:
    print(f"   U+{cp:04X}: {old!r} -> {new!r}   （分 {s_} 词{w_} 常用{c_} 错{x_}）")

json.dump({str(k): v for k, v in sorted(cur.items())},
          open(os.path.join(FP, "pua_map_final.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
dec = "".join(cur.get(ord(c), c) for c in raw)
print(f"\n=== 成品 ===\n{dec[:460]}")
