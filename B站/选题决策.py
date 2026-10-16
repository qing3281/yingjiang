#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
选题决策引擎 —— 把「热榜日报」变成「本周该做什么片子」

输入：情报/热榜日报_YYYYMMDD.csv + raw_YYYYMMDD.json（由 抓热榜.py 产出）
输出：情报/本周片单_YYYYMMDD.md

它做的不是再统计一遍，而是**给出可执行决定**：
  1. 从 tag / 标题里识别当前在跑的官方活动（最高杠杆，41.6×）
  2. 按「进榜门槛 P25」给题材排序，判断新号挤不挤得进去
  3. 给每个题材算时长甜蜜区、标题句式 lift、投币率（质量信号）
  4. 直接生成 N 条选题：题材 + 时长 + 分区 + 标题草稿 + tag 组合 + 依据

用法：
    python 选题决策.py                          # 用最新一天的数据
    python 选题决策.py --date 20261012          # 指定日期
    python 选题决策.py --top 8                  # 要几条选题（默认 5）
    python 选题决策.py --题材 AI动画,AI短片       # 只看这几个题材
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
INTEL = HERE / "情报"

# ---------------------------------------------------------------- 常量与规则

# 官方活动信号（来自 2026-10 实测语料：这些字样是活动池的实际写法）
活动正则 = re.compile(
    r"AI全民制作人|AI创作大赛|创作大赛|征集|活动|挑战赛|扶持计划|激励计划|有奖|大赛"
)

# 标题句式规则：lift 来自上一轮分析（相关性，非因果，但方向稳定）
# (名字, 正则, 方向)  方向 +1 = 正向使用，-1 = 避免
句式规则 = [
    ("活动字样", 活动正则, +1),
    ("书名号《》", re.compile(r"《.+?》"), +1),
    ("悬念词", re.compile(r"结局|没想到|真相|居然|竟然|最后|反转|原来|结果"), +1),
    ("口语玩梗", re.compile(r"我|你|这|那|怎么|为什么|吗|吧|呢|啊|草|绝了|离谱"), +1),
    ("对比VsPK", re.compile(r"对比|VS|vs|Vs|PK|pk"), -1),
    ("情绪感叹号", re.compile(r"！|!"), -1),
    ("阿拉伯数字", re.compile(r"\d"), -1),
    ("教程方法论", re.compile(r"教程|教学|方法|攻略|入门|指南|如何|怎么用"), -1),
]

# 时长甜蜜区（按题材，来自上一轮分析；单位：秒）
时长甜蜜区 = {
    "AI动画": (60, 180),
    "AI短片": (180, 300),
    "AI漫剧": (180, 300),
    "AI电影": (180, 600),
    "AI视频": (60, 300),
    "AI音乐": (60, 300),
    "AI生成": (60, 300),
    "AI绘画": (30, 300),
    "ComfyUI": (120, 900),
    "Stable Diffusion": (120, 900),
    "AI": (60, 300),
}
默认时长区 = (90, 300)


def 读数据(date: str | None):
    """读最新（或指定日期）的 CSV。返回 (rows, date_tag, csv路径)。"""
    if date:
        csv路径 = INTEL / f"热榜日报_{date}.csv"
        if not csv路径.exists():
            raise SystemExit(f"找不到 {csv路径}")
    else:
        候选 = sorted(INTEL.glob("热榜日报_*.csv"))
        if not 候选:
            raise SystemExit(f"{INTEL} 下没有 热榜日报_*.csv，先跑 run_daily.ps1")
        csv路径 = 候选[-1]
    date_tag = csv路径.stem.split("_")[-1]

    with open(csv路径, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    def 数(x, 默认=0):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 默认

    for r in rows:
        r["_view"] = 数(r.get("view"))
        r["_like"] = 数(r.get("like"))
        r["_coin"] = 数(r.get("coin"))
        r["_fav"] = 数(r.get("favorite"))
        r["_dur"] = 数(r.get("duration_sec"))
        r["_coin_rate"] = 数(r.get("coin_play_ratio"))
        r["_followers"] = 数(r.get("up_followers"))
        r["_title"] = (r.get("title") or "").strip()
        r["_tags"] = [t.strip() for t in (r.get("tag") or "").split(",") if t.strip()]
    return rows, date_tag, csv路径


def pct(样本, p):
    """百分位数（线性插值）。样本为空返回 0。"""
    if not 样本:
        return 0.0
    s = sorted(样本)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def 万(x):
    return f"{x/1e4:,.1f}万" if x >= 1e4 else f"{x:,.0f}"


# ---------------------------------------------------------------- 第一块：活动池

def 找活动(rows):
    """
    活动识别走两条路：
      a) tag 列里出现活动字样（最可靠 —— 发布时挂的 tag 会原样存下来）
      b) 标题里出现活动字样
    返回 {活动名: {n, 播放中位数, 投币率中位数}}
    """
    桶 = defaultdict(lambda: {"views": [], "coins": [], "标题样本": []})

    tag计数 = Counter()
    for r in rows:
        for t in r["_tags"]:
            if 活动正则.search(t):
                tag计数[t] += 1

    # 只保留有一定样本量的 tag，避免把偶发 tag 当成活动
    活动tag = {t for t, c in tag计数.items() if c >= 8}

    for r in rows:
        命中 = [t for t in r["_tags"] if t in 活动tag]
        if not 命中 and 活动正则.search(r["_title"]):
            命中 = ["（标题命中）"]
        for h in 命中:
            b = 桶[h]
            b["views"].append(r["_view"])
            if r["_coin_rate"]:
                b["coins"].append(r["_coin_rate"])
            if len(b["标题样本"]) < 3:
                b["标题样本"].append(r["_title"])

    out = {}
    for k, v in 桶.items():
        out[k] = {
            "n": len(v["views"]),
            "播放中位数": st.median(v["views"]) if v["views"] else 0,
            "投币率中位数": st.median(v["coins"]) if v["coins"] else 0,
            "标题样本": v["标题样本"],
        }
    return out, tag计数


# ---------------------------------------------------------------- 第二块：题材评分

def 评题材(rows, 限定: list[str] | None):
    """
    对每个关键词（= 题材）算一组指标，重点回答「新号挤不挤得进去」。
    门槛用 P25 而不是中位数 —— 中位数是「要上榜需要多少」，P25 是「及格线」。
    """
    按关键词 = defaultdict(list)
    for r in rows:
        kw = (r.get("keyword") or "").strip()
        if not kw:
            continue
        if 限定 and kw not in 限定:
            continue
        按关键词[kw].append(r)

    结果 = []
    for kw, rs in 按关键词.items():
        views = [r["_view"] for r in rs if r["_view"] > 0]
        coins = [r["_coin_rate"] for r in rs if r["_coin_rate"] > 0]
        durs = [r["_dur"] for r in rs if r["_dur"] > 0]
        if len(views) < 10:
            continue

        活动命中 = sum(1 for r in rs if 活动正则.search(r["_title"]) or any(活动正则.search(t) for t in r["_tags"]))
        # 这个题材实际最常和哪个活动 tag 一起出现 —— 比全局挑活动靠谱
        本题材活动 = Counter()
        for r in rs:
            for t in r["_tags"]:
                if 活动正则.search(t):
                    本题材活动[t] += 1

        结果.append({
            "题材": kw,
            "样本": len(rs),
            "P25": pct(views, 0.25),
            "P50": pct(views, 0.50),
            "P75": pct(views, 0.75),
            "投币率": st.median(coins) if coins else 0,
            "时长中位": st.median(durs) if durs else 0,
            "活动占比": 活动命中 / len(rs) if rs else 0,
            "本题材活动": 本题材活动.most_common(3),
        })

    # 门槛从低到高 = 从好挤到难挤
    结果.sort(key=lambda x: x["P25"])
    return 结果


# ---------------------------------------------------------------- 第三块：标题句式

def 评句式(rows):
    """对每条规则算 lift，并抽回真实标题当例子。"""
    输出 = []
    for 名, 正则, 方向 in 句式规则:
        有, 无 = [], []
        例 = []
        for r in rows:
            if r["_view"] <= 0:
                continue
            if 正则.search(r["_title"]):
                有.append(r["_view"])
                if len(例) < 3 and r["_view"] > 1e5:
                    例.append(r["_title"][:60])
            else:
                无.append(r["_view"])
        if len(有) < 20 or len(无) < 20:
            continue
        m有, m无 = st.median(有), st.median(无)
        lift = (m有 / m无) if m无 else 0
        输出.append({
            "句式": 名, "方向": 方向, "n": len(有),
            "有中位": m有, "无中位": m无, "lift": lift, "例": 例,
        })
    输出.sort(key=lambda x: -x["lift"])
    return 输出


# ---------------------------------------------------------------- 第四块：生成选题

def 造标题(*_a, **_k):
    """已废弃：标题改由 标题模板 直接生成。保留占位避免旧引用报错。"""
    raise NotImplementedError


标题模板 = {
    "AI动画": ("《{主题}》第1集：她推开那扇门之后，再也没回来",
               "我做了个AI动画，结果结局把我自己看愣了"),
    "AI短片": ("《{主题}》：一个关于告别的三分钟",
               "没想到这个AI短片的最后一秒才是重点"),
    "AI漫剧": ("《{主题}》第1集｜原来他一直在骗我",
               "这个AI漫剧我看了三遍才看懂"),
    "AI音乐": ("《{主题}》：写给回不去的那年夏天",
               "我用AI写了首歌，听到副歌绷不住了"),
    "AI电影": ("《{主题}》：全片没有一句台词",
               "花了半个月做的AI电影，最后反转我没想到"),
    "AI视频": ("《{主题}》：如果那天我没有回头",
               "这个AI视频的结局，评论区吵翻了"),
    "AI生成": ("《{主题}》：我把它交给AI，然后它就失控了",
               "让AI自己发挥了一次，结果比我想的好"),
    "AI绘画": ("《{主题}》：画了三十遍才满意的那个瞬间",
               "把同一个提示词喂了三十次，挑出最好的那张"),
    "ComfyUI": ("《{主题}》：本地跑ComfyUI出片的全过程",
                "用ComfyUI做《{主题}》，显卡差点没扛住"),
    "Stable Diffusion": ("《{主题}》：SD出图参数全记录",
                         "Stable Diffusion做《{主题}》，这套参数最好用"),
}


def 生成片单(rows, date_tag, top_n, 限定):
    活动池, tag计数 = 找活动(rows)
    题材表 = 评题材(rows, 限定)
    句式表 = 评句式(rows)

    基准 = st.median([r["_view"] for r in rows if r["_view"] > 0]) or 1

    # 选活动：样本够、中位播放高
    活动排序 = sorted(
        [(k, v) for k, v in 活动池.items() if v["n"] >= 10 and not k.startswith("（")],
        key=lambda kv: -kv[1]["播放中位数"],
    )

    # 选题材：优先「活动占比高」的（说明该题材吃活动红利），再按门槛
    题材排序 = sorted(题材表, key=lambda x: (-x["活动占比"], x["P25"]))

    L = []
    L.append(f"# 本周片单 · {date_tag}")
    L.append("")
    L.append(f"> 数据源：`热榜日报_{date_tag}.csv`（{len(rows)} 条）　｜　由 `选题决策.py` 生成")
    L.append(f"> 全样本播放中位数基准：**{万(基准)}**　（下文所有「倍数」都相对它）")
    L.append("")
    L.append("---")
    L.append("")

    # ---- 一、活动池 ----
    L.append("## 一、可挂的官方活动（最高杠杆）")
    L.append("")
    if 活动排序:
        L.append("| 活动 tag | 命中条数 | 播放中位数 | 相对基准 | 投币率中位 |")
        L.append("|---|---|---|---|---|")
        for k, v in 活动排序[:10]:
            L.append(f"| `{k}` | {v['n']} | {万(v['播放中位数'])} | "
                     f"**{v['播放中位数']/基准:.1f}×** | {v['投币率中位数']*100:.3f}% |")
        L.append("")
        L.append("**动作**：投稿时把上面排名靠前的活动 tag 挂进 tag 列表，并让标题带上活动字样。")
        L.append("这是本次数据里单一杠杆最大的一项，成本几乎为零。")
    else:
        L.append("本次数据里没有识别到样本量足够的活动 tag，需要人工去创作中心活动页确认。")
    L.append("")
    L.append("---")
    L.append("")

    # ---- 二、题材排序 ----
    L.append("## 二、题材进入难度排序（P25 = 及格线）")
    L.append("")
    L.append("> P25 是「挤进这个位置需要的播放」，比中位数更接近新号的现实目标。**门槛低 ≠ 值得做**，")
    L.append("> 还要看活动占比和投币率。活动占比高 = 这个题材吃活动红利明显。")
    L.append("")
    L.append("| 题材 | 样本 | P25 门槛 | P50 | 投币率中位 | 时长中位 | 活动占比 |")
    L.append("|---|---|---|---|---|---|---|")
    for t in 题材排序:
        L.append(f"| `{t['题材']}` | {t['样本']} | {万(t['P25'])} | {万(t['P50'])} | "
                 f"{t['投币率']*100:.3f}% | {t['时长中位']/60:.1f}分 | {t['活动占比']*100:.0f}% |")
    L.append("")
    L.append("---")
    L.append("")

    # ---- 三、标题句式 ----
    L.append("## 三、标题句式 lift（实测）")
    L.append("")
    L.append("| 句式 | 建议 | 出现中位 | 未出现中位 | lift | 样本 |")
    L.append("|---|---|---|---|---|---|")
    for s in 句式表:
        标记 = "✅ 用" if s["方向"] > 0 else "❌ 避"
        L.append(f"| {s['句式']} | {标记} | {万(s['有中位'])} | {万(s['无中位'])} | "
                 f"{s['lift']:.2f}× | {s['n']} |")
    L.append("")
    L.append("---")
    L.append("")

    # ---- 四、本周片单 ----
    L.append(f"## 四、本周片单（{top_n} 条）")
    L.append("")
    主活动 = 活动排序[0][0] if 活动排序 else ""
    主活动中位 = 活动排序[0][1]["播放中位数"] if 活动排序 else 0

    for i in range(top_n):
        t = 题材排序[i % len(题材排序)] if 题材排序 else None
        if not t:
            break
        题材 = t["题材"]
        低, 高 = 时长甜蜜区.get(题材, 默认时长区)
        目标秒 = int((低 + 高) / 2)

        # 该题材实际共现最多的活动 tag；没有就用全局最强的
        本题材活动 = [x for x in (t.get("本题材活动") or []) if x[1] >= 3]
        活动 = 本题材活动[0][0] if 本题材活动 else 主活动
        活动依据 = (f"该题材 {本题材活动[0][1]} 条挂了 `{活动}`" if 本题材活动
                    else f"该题材没有 ≥3 条共现的活动 tag，回退到全局最高的 `{活动}`")
        前缀 = f"{活动}｜" if 活动 else ""

        模板 = 标题模板.get(题材, (f"《{{主题}}》第1集", "我做了一个{题材}，结局没想到"))
        标题A = 前缀 + 模板[0].format(主题="你的故事名")
        标题B = 前缀 + 模板[1].format(主题="你的故事名")

        L.append(f"### 选题 {i+1}：{题材}")
        L.append("")
        L.append(f"- **片长**：{目标秒//60}分{目标秒%60:02d}秒（甜蜜区 {低//60}–{高//60} 分钟）")
        L.append(f"- **进榜门槛**：P25 = {万(t['P25'])}（这个题材 {t['样本']} 条样本）")
        L.append(f"- **投币率**：{t['投币率']*100:.3f}%　"
                 f"（{'资产型，能沉淀观众' if t['投币率'] > 0.005 else '流量型，播放高但留存弱'}）")
        L.append(f"- **建议活动**：`{活动}`　（{活动依据}）")
        L.append(f"- **标题 A**：`{标题A}`")
        L.append(f"- **标题 B**：`{标题B}`")
        L.append(f"- **建议 tag**：{题材}," + (f"{活动}," if 活动 else "") + "AI,AIGC,原创")
        L.append(f"- **依据**：{t['活动占比']*100:.0f}% 的样本挂了活动字样")
        L.append("")

        if 本题材活动:
            L.append(f"  <sub>该题材其它可用活动 tag："
                     + "、".join(f"`{k}`({c})" for k, c in 本题材活动[1:])
                     + "</sub>")
            L.append("")

    L.append("---")
    L.append("")
    L.append("## 五、执行检查清单")
    L.append("")
    活动lift = next((x["lift"] for x in 句式表 if x["句式"] == "活动字样"), 0)
    L.append(f"- [ ] 标题带了活动字样了吗（**{活动lift:.1f}×** 杠杆，本次数据里单项最大）")
    L.append("- [ ] 片长落在甜蜜区了吗（<1 分钟和 >10 分钟两端都塌）")
    L.append("- [ ] tag 里挂了官方活动 tag 吗")
    L.append("- [ ] 标题避开了阿拉伯数字 / 感叹号 / 「教程」标签吗（这三项 lift 为负）")
    L.append("- [ ] 投稿时勾了「AI 生成」声明吗（biliup 只能写进简介，官方勾选要去网页端）")
    L.append("")

    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="把热榜数据变成本周片单")
    ap.add_argument("--date", help="数据日期标签，如 20261012；缺省用最新一份")
    ap.add_argument("--top", type=int, default=5, help="生成几条选题（默认 5）")
    ap.add_argument("--题材", help="逗号分隔，只看这些题材")
    args = ap.parse_args()

    限定 = [s.strip() for s in args.题材.split(",")] if args.题材 else None

    rows, date_tag, csv路径 = 读数据(args.date)
    print(f"读取 {csv路径.name}：{len(rows)} 条")

    md = 生成片单(rows, date_tag, args.top, 限定)

    输出 = INTEL / f"本周片单_{date_tag}.md"
    输出.write_text(md, encoding="utf-8")
    print(f"已生成 {输出}（{len(md.splitlines())} 行）")


if __name__ == "__main__":
    main()
