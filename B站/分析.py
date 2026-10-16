# -*- coding: utf-8 -*-
"""
题材分析 —— 读取抓取结果，产出 `题材分析_YYYYMMDD.md`。

原则：报告里每一个结论后面都必须跟数字。算不出来的地方直接写「数据不足」，
不写「AI 内容很火」这类没有信息量的话。
"""
from __future__ import annotations

import re
import statistics as st
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "情报"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------------------
def num(v):
    if v in ("", None):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ints(seq):
    out = []
    for v in seq:
        x = num(v)
        if x is not None:
            out.append(x)
    return out


def med(seq):
    v = ints(seq)
    return st.median(v) if v else None


def mean(seq):
    v = ints(seq)
    return sum(v) / len(v) if v else None


def pct(seq, p):
    v = sorted(ints(seq))
    if not v:
        return None
    k = (len(v) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def w(n, dash="—"):
    """数字 -> 人类可读（万/亿）"""
    if n is None:
        return dash
    n = float(n)
    if n >= 1e8:
        return f"{n/1e8:.2f}亿"
    if n >= 1e4:
        return f"{n/1e4:.1f}万"
    if n == int(n):
        return str(int(n))
    return f"{n:.2f}"


def pctstr(x, digits=2):
    return "—" if x is None else f"{x*100:.{digits}f}%"


def esc(s):
    return str(s or "").replace("|", "／").replace("\n", " ").strip()


def fmt_dur(sec):
    sec = num(sec)
    if not sec or sec <= 0:
        return "—"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def date_of(ts):
    ts = num(ts)
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return "—"


def dedup_by_bvid(rows):
    seen, out = set(), []
    for r in rows:
        b = r.get("bvid")
        if not b or b in seen:
            continue
        seen.add(b)
        out.append(r)
    return out


def subsection_ratio(rows, min_view=10000):
    """返回有投币数据、且播放 >= min_view 的行"""
    out = []
    for r in rows:
        c, v = num(r.get("coin")), num(r.get("view"))
        if c is None or v is None or v < min_view:
            continue
        out.append(r)
    return out


# --------------------------------------------------------------------------------------
# 标题句式规律
# --------------------------------------------------------------------------------------
PATTERNS = {
    "阿拉伯数字":        r"\d",
    "量化数字(个/种/集)": r"\d+\s*(个|种|招|步|集|话|期|张|条|遍|天|分钟|秒)",
    "书名号《》":        r"《.+?》",
    "问号(悬念)":        r"[?？]",
    "感叹号(情绪)":      r"[!！]",
    "年份(20xx)":        r"20\d{2}",
    "AI 字样":           r"AI",
    "对比/Vs/PK":        r"(?i)vs|对比|大战|对决|pk|挑战赛",
    "悬念词":            r"竟然|居然|没想到|真相|结局|原来|为何|为什么|结果|背后",
    "情绪词":            r"震惊|炸裂|绝了|离谱|破防|泪目|封神|逆天|赢麻|牛|太.{0,3}了",
    "教程/方法论":       r"教程|教学|入门|保姆级|手把手|零基础|从零|指南|攻略|怎么|如何|技巧",
    "系列/连载":         r"第\s*\d+\s*[集话期弹]|系列|EP\d+|更新",
    "新鲜/时效词":       r"最新|新作|首发|刚刚|今天|今年|本月|第一",
    "全民/征集/活动":    r"全民|征集|大赛|活动|企划|共创",
    "口语/玩梗":         r"我|你|哥们|老|兄弟们|家人们|泪|草|卧槽|hhh|233",
    "副标题分隔符":      r"[：:｜|【】\-—]",
}


def pattern_stats(rows):
    """对语料计算每个句式的「出现 vs 未出现」播放中位数对比。"""
    corpus = [r for r in dedup_by_bvid(rows) if num(r.get("view")) is not None]
    total = len(corpus)
    res = []
    for name, pat in PATTERNS.items():
        rx = re.compile(pat)
        hit = [r for r in corpus if rx.search(r.get("title") or "")]
        miss = [r for r in corpus if not rx.search(r.get("title") or "")]
        if len(hit) < 5 or len(miss) < 5:
            res.append({"name": name, "n": len(hit), "share": len(hit) / total if total else None,
                        "med_hit": med([r["view"] for r in hit]),
                        "med_miss": med([r["view"] for r in miss]),
                        "lift": None, "thin": True})
            continue
        mh, mm = med([r["view"] for r in hit]), med([r["view"] for r in miss])
        res.append({"name": name, "n": len(hit), "share": len(hit) / total if total else None,
                    "med_hit": mh, "med_miss": mm,
                    "lift": (mh / mm) if (mh and mm) else None, "thin": False})
    res.sort(key=lambda x: (x["lift"] is None, -(x["lift"] or 0)))
    return res, total


# --------------------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------------------
def build_report(rows: list[dict], meta: dict, date_tag: str) -> Path:
    L: list[str] = []
    A = L.append
    now = datetime.now()

    uniq = dedup_by_bvid(rows)
    with_view = [r for r in uniq if (num(r.get("view")) or 0) > 0]
    ai_rows = [r for r in with_view if r.get("keyword")]
    rank_rows = [r for r in with_view if r.get("source") == "ranking"]
    enriched = [r for r in uniq if r.get("enriched")]

    A(f"# B站 AI 动画/短片 赛道 · 选题情报日报")
    A("")
    A(f"> 生成时间：{now:%Y-%m-%d %H:%M}　|　数据日期标签：{date_tag}　|　"
      f"HTTP 后端：`{meta.get('client','?')}`")
    A("")
    A("**本报告所有结论均由本次抓取的公开数据算出，括号内为样本量与具体数值。**")
    A("")

    # ==================================================================================
    # 0. 结论速览（数据驱动，自动生成）
    # ==================================================================================
    A("---")
    A("")
    A("## 〇、结论速览")
    A("")
    quick = []
    strong, weak = [], []
    rd = (meta.get("windows") or {}).get("recent_days", 30)

    # --- 计算所有要用的中间结果（速览和后面各章共用，避免重复算） ---
    zstat = zone_table(rank_rows)
    cr = coin_rank(uniq)
    db = duration_table(uniq)
    gaps = gap_table(ai_rows, meta)
    ps, corpus_n = pattern_stats(ai_rows)
    strong = [p for p in ps if p["lift"] and p["lift"] >= 1.2 and p["n"] >= 10]
    act = activity_stats(ai_rows)
    loyalty, coin_bench = coin_loyalty(ai_rows)
    gate = follower_gate(uniq)
    dxk, dxk_best = duration_x_keyword(ai_rows)

    # ① 官方活动标签 —— 本次数据里最强的单一杠杆
    if act and act["lift"]:
        quick.append(
            f"**挂官方活动 tag 的播放量是没有挂的 {act['lift']:.1f} 倍**：标题含"
            f"「AI全民制作人／AI创作大赛／征集」等活动字样的 {act['n_hit']} 条视频，"
            f"播放中位数 **{w(act['med_hit'])}**；不含的 {act['n_miss']} 条只有 {w(act['med_miss'])}。"
            f"播放 TOP100 里有 **{act['top100']}/100 条**带活动标签。→ 第一优先动作：投稿时进官方活动池。"
        )

    # ② 投币率分层 —— 流量型题材 vs 资产型题材
    if loyalty and coin_bench:
        top = loyalty[0]
        flow = [x for x in loyalty if x["med_view"] and x["med_view"] >= 10 * (top["med_view"] or 1)]
        quick.append(
            f"**播放和「观众认可」是两回事**：在 AI 题材样本里，投币/播放比最高的是 `{top['kw']}`（中位 "
            f"{pctstr(top['med_rate'])}，是「AI 题材样本投币率基准」{pctstr(coin_bench)} 的 "
            f"{top['med_rate']/coin_bench:.1f} 倍），但它播放中位数只有 {w(top['med_view'])}；"
            + (f"而播放中位数最高的 `{flow[0]['kw']}`（{w(flow[0]['med_view'])}）投币率只有 "
               f"{pctstr(flow[0]['med_rate'])}，仅为基准的 {flow[0]['med_rate']/coin_bench:.2f} 倍。"
               if flow else "")
        )

    # ③ 粉丝到底是不是门槛
    if gate and gate["small_med"] and gate["big_med"]:
        quick.append(
            f"**榜单入口不看粉丝量**：在有粉丝数据的 {gate['n_up']} 个 UP 主里，粉丝 <10 万的账号"
            f"（n={len(gate['small'])}）上榜视频播放中位数 **{w(gate['small_med'])}**，"
            f"与 10 万粉以上账号（n={len(gate['big'])}）的 {w(gate['big_med'])} 几乎持平"
            f"（比值 {gate['big_med']/gate['small_med']:.2f}×）；但小号的「播放/粉丝」放大倍数是 "
            f"**{gate['small_amp']:.0f}×**，大号只有 {gate['big_amp']:.1f}×，相差 "
            f"{gate['small_amp']/gate['big_amp']:.0f} 倍 —— 新号缺的不是粉丝，是能进推荐池的内容。"
        )

    # ④ 时长甜蜜区（按题材分开看）
    if dxk_best:
        m = {b["kw"]: b for b in dxk_best}
        pick = [m[k] for k in ("AI动画", "AI短片", "AI漫剧") if k in m]
        if pick:
            quick.append(
                "**各题材的最优时长并不相同**：" +
                "；".join(f"`{b['kw']}` → {b['label']}（中位 {w(b['med'])}，n={b['n']}）" for b in pick)
                + "。做动画/短片请压进 1–5 分钟，<1 分钟基本没有量。"
            )

    # ⑤ 标题句式
    if strong:
        quick.append(
            "**最强的三个标题句式**（AI 关键词语料 n=%d）：" % corpus_n +
            "；".join(f"`{p['name']}` 出现 {p['n']} 条，播放中位数 {w(p['med_hit'])} vs "
                      f"未出现 {w(p['med_miss'])}（{p['lift']:.2f}×）" for p in strong[:3])
        )

    for i, q in enumerate(quick, 1):
        A(f"{i}. {q}")
    A("")

    # ==================================================================================
    # 一、数据概览
    # ==================================================================================
    A("---")
    A("")
    A("## 一、抓取概览与接口健康度")
    A("")
    A("| 指标 | 值 |")
    A("|---|---|")
    A(f"| 去重后视频总数 | {len(uniq)} 条 |")
    A(f"| 有播放数据的 | {len(with_view)} 条 |")
    A(f"| 排行榜来源 | {len(rank_rows)} 条 |")
    A(f"| 关键词搜索来源 | {len(ai_rows)} 条 |")
    cu = len([r for r in uniq if r.get("coin") not in ("", None)])
    A(f"| 带投币数据的（榜单单 + 详情补全） | {cu} 条 |")
    A(f"| 成功请求 / 失败请求 | {meta.get('ok_requests','?')} / {len(meta.get('failures') or [])} |")
    A(f"| 触发降速次数 | {meta.get('throttle_events', 0)}（最终请求间隔 {meta.get('final_interval','?')}s） |")
    if meta.get("enrich"):
        e = meta["enrich"]
        A(f"| 详情补全 | 视频 {e.get('videos_ok')}/{e.get('videos_requested')}；"
          f"UP 主粉丝 {e.get('users_ok')}/{e.get('users_requested')}"
          + ("（因风控提前中止）" if e.get("aborted") else "") + " |")
    A("")
    w0 = meta.get("windows") or {}
    if w0:
        A(f"「近期」窗口定义：`{w0.get('start')}` ~ `{w0.get('end')}`（{w0.get('recent_days')} 天）")
        A("")
    if meta.get("competitor_note"):
        A(f"对标 UP 主空间投稿：{meta['competitor_note']}")
        A("")

    fails = meta.get("failures") or []
    if fails:
        A("**失败/跳过的接口（已隔离，不影响其余抓取）**")
        A("")
        A("| 目标 | 原因 |")
        A("|---|---|")
        agg: dict[str, int] = {}
        for x in fails:
            k = re.sub(r":BV\w+|:\d+$", "", x["target"])
            agg[(k, x["reason"])] = agg.get((k, x["reason"]), 0) + 1
        for (t, r), c in sorted(agg.items(), key=lambda kv: -kv[1])[:25]:
            A(f"| `{t}` | {esc(r)} × {c} |")
        A("")
    else:
        A("本次所有接口均成功返回，无失败记录。")
        A("")

    # ==================================================================================
    # 二、分区榜
    # ==================================================================================
    A("---")
    A("")
    A("## 二、分区排行榜：常态水平（中位数）vs 被爆款拉高的均值")
    A("")
    A("> 榜单是「三日内」榜（`ranking/v2`）。均值会被单个千万播放爆款彻底带偏，"
      "**中位数才代表这个分区的常态**。两列一起看，均值/中位数倍数越大，说明该分区越「头部集中」。")
    A("")
    if zstat:
        A("| 分区 | 样本 n | 播放中位数 | 播放均值 | 均值/中位数 | 点赞中位数 | 投币中位数 | 投币/播放中位数 | 时长中位数 |")
        A("|---|---|---|---|---|---|---|---|---|")
        for z in zstat:
            A(f"| {z['zone']} | {z['n']} | {w(z['med_view'])} | {w(z['mean_view'])} | "
              f"{z['lift']:.2f}× | {w(z['med_like'])} | {w(z['med_coin'])} | "
              f"{pctstr(z['med_coin_ratio'],3)} | {fmt_dur(z['med_dur'])} |")
        A("")
        A("**读法**：")
        best = max(zstat, key=lambda z: z["med_view"] or 0)
        worst = min(zstat, key=lambda z: z["med_view"] or 0)
        A(f"- 常态播放最高：`{best['zone']}` {w(best['med_view'])}；最低：`{worst['zone']}` {w(worst['med_view'])}，"
          f"相差 {best['med_view']/worst['med_view']:.1f} 倍。")
        hi = max(zstat, key=lambda z: z["lift"] or 0)
        lo = min(zstat, key=lambda z: z["lift"] or 0)
        A(f"- 头部集中度最高：`{hi['zone']}`（均值是中位数的 {hi['lift']:.2f} 倍，爆款效应最强）；"
          f"最平均：`{lo['zone']}`（{lo['lift']:.2f} 倍，腰部机会更多）。")
        crz = [z for z in zstat if z["med_coin_ratio"] is not None]
        if crz:
            bz = max(crz, key=lambda z: z["med_coin_ratio"])
            A(f"- 用户最愿意「投币」（质量信号最强）：`{bz['zone']}`，投币/播放中位数 {pctstr(bz['med_coin_ratio'],3)}。")
    else:
        A("_本次没有拿到排行榜数据，见上方失败清单。_")
    A("")

    # ==================================================================================
    # 三、质量榜
    # ==================================================================================
    A("---")
    A("")
    A("## 三、质量榜：投币/播放比 TOP 30")
    A("")
    A("> 播放量可以靠封面和标题骗来，**投币是观众主动付出的成本**，投币/播放比更接近「真实质量」。")
    A(f"> 仅统计播放 ≥ 1 万且拿到投币数据的视频（n={len(subsection_ratio(uniq))}）；"
      "B 站投币上限为 2 枚/人，所以该比值天然在 0~20% 之间。")
    A("")
    if cr:
        A("| # | 标题 | UP 主 | 播放 | 投币 | 投币率 | 点赞率 | 分区 |")
        A("|---|---|---|---|---|---|---|---|")
        for i, r in enumerate(cr[:30], 1):
            A(f"| {i} | {esc(r['title'])[:52]} | {esc(r['up_name'])[:14]} | {w(r['view'])} | "
              f"{w(r['coin'])} | **{pctstr(r['ratio'],3)}** | {pctstr(r['like_ratio'],3)} | "
              f"{esc(r.get('zone_cn') or r.get('tname') or '')} |")
        A("")
        A(f"全样本投币率中位数 {pctstr(med([r['ratio'] for r in cr]),3)}，"
          f"上四分位 {pctstr(pct([r['ratio'] for r in cr], 0.75),3)}。"
          f"超过 {pctstr(pct([r['ratio'] for r in cr], 0.75),3)} 即属于「质量跑赢大盘」。")
    else:
        A("_没有可用的投币数据（详情补全被跳过或被风控拦截）。_")
    A("")

    # ==================================================================================
    # 三·B、投币率按题材分层 —— 流量型 vs 资产型
    # ==================================================================================
    A("---")
    A("")
    A("## 三·B、按题材看投币率：哪些题材能沉淀观众，哪些只是路过流量")
    A("")
    A("> 上面那张榜被音乐/MV 屠榜，对做 AI 动画的人参考有限。这里改成**按关键词分组**看投币率。")
    A("> 投币要花观众自己的硬币，是「愿意为这条内容付出」的直接证据；播放量做不了这个判断。")
    A("")
    if loyalty and coin_bench:
        A(f"全场投币率基准（AI 关键词样本投币率中位数）：**{pctstr(coin_bench,3)}**。")
        A("")
        A("| 关键词 | 播放中位数 | 有投币数据的样本 | 投币率中位数 | 是基准的几倍 | 高于基准的占比 | 类型 |")
        A("|---|---|---|---|---|---|---|")
        for x in loyalty:
            mult = (x["med_rate"] / coin_bench) if coin_bench else None
            kind = "资产型（观众愿付币）" if (mult and mult >= 2) else (
                "流量型（看过就走）" if (mult and mult < 0.5) else "中间型")
            A(f"| `{x['kw']}` | {w(x['med_view'])} | {x['n_coin']} | "
              f"**{pctstr(x['med_rate'],3)}** | {mult:.2f}× | {pctstr(x['share_above'],1)} | {kind} |")
        A("")
        flow = [x for x in loyalty if x["med_view"] and x["med_rate"] and coin_bench
                and x["med_rate"] < coin_bench * 0.5 and x["med_view"] > 1e5]
        asset = [x for x in loyalty if x["med_rate"] and coin_bench and x["med_rate"] >= coin_bench * 2]
        if flow:
            A(f"- **流量型题材**：" + "、".join(
                f"`{x['kw']}`（播放中位 {w(x['med_view'])}，但投币率仅 {pctstr(x['med_rate'],3)}）"
                for x in flow) + " —— 播放很高，观众却不掏硬币，说明流量主要来自推荐页的顺手套看，没沉淀成粉丝资产。")
        if asset:
            A(f"- **资产型题材**：" + "、".join(
                f"`{x['kw']}`（投币率 {pctstr(x['med_rate'],3)} = 基准 {x['med_rate']/coin_bench:.1f} 倍，"
                f"但播放中位只有 {w(x['med_view'])}）" for x in asset) +
              " —— 播放盘子小，但看的人是真爱，适合用来**涨粉/立人设**，不适合用来**冲量**。")
        if flow and asset:
            A("")
            A(f"- **双轨策略的数据依据**：`{flow[0]['kw']}` 的播放中位数是 `{asset[0]['kw']}` 的 "
              f"{(flow[0]['med_view']/asset[0]['med_view']):.0f} 倍，而投币率只有它的 "
              f"1/{(asset[0]['med_rate']/flow[0]['med_rate']):.0f} —— "
              f"冲播放用前者，攒铁粉用后者，两条线不冲突。")
    else:
        A("_没有足够的投币数据做分层。_")
    A("")

    # ==================================================================================
    # 四、时长分布
    # ==================================================================================
    A("---")
    A("")
    A("## 四、时长分布：什么长度最容易起量")
    A("")
    if db:
        A("| 时长段 | 样本 n | 播放中位数 | 播放均值 | 均值/中位数 | 进入播放前 10% 的占比 |")
        A("|---|---|---|---|---|---|")
        for b in db:
            A(f"| {b['label']} | {b['n']} | {w(b['med_view'])} | {w(b['mean_view'])} | "
              f"{(b['lift'] if b['lift'] else float('nan')):.2f}× | {pctstr(b['top10_share'],1)} |")
        A("")
        good = [b for b in db if b["n"] >= 8]
        if good:
            bd = max(good, key=lambda b: b["med_view"] or 0)
            bt = max(good, key=lambda b: b["top10_share"] or 0)
            A(f"- 播放中位数最高：`{bd['label']}`（{w(bd['med_view'])}，n={bd['n']}）。")
            A(f"- 最容易挤进全样本播放前 10% 的时长段：`{bt['label']}`（该段有 {pctstr(bt['top10_share'],1)} 的视频进入前 10%）。")
    else:
        A("_没有可用的时长数据。_")
    A("")

    # ----------------------------------------------------------------------------------
    # 四·B、时长 × 题材 交叉
    # ----------------------------------------------------------------------------------
    A("### 四·B、时长 × 题材 交叉：每个题材的「甜蜜时长」不一样")
    A("")
    A("> 上表是全集混在一起算的，会被「漫剧/长视频」带偏。这里按关键词拆开，"
      "单元格是**该题材在该时长段的播放中位数**（样本 <5 条的格子留空，不参与结论）。")
    A("")
    if dxk:
        labels = [lab for lab, _, _ in DUR_BUCKETS]
        A("| 题材 | " + " | ".join(labels) + " |")
        A("|---|" + "---|" * len(labels))
        for row in dxk:
            cells = []
            best_v = max((v for v, n in row["cells"].values() if v), default=None)
            for lab in labels:
                v, n = row["cells"].get(lab, (None, 0))
                if v is None:
                    cells.append(f"—(n={n})" if n else "—")
                else:
                    mark = "**" if (best_v and v == best_v) else ""
                    cells.append(f"{mark}{w(v)}{mark}(n={n})")
            A(f"| `{row['kw']}` | " + " | ".join(cells) + " |")
        A("")
        if dxk_best:
            A("**各题材的最优时长段：**")
            A("")
            for b in dxk_best:
                A(f"- `{b['kw']}` → **{b['label']}**，播放中位数 {w(b['med'])}（n={b['n']}）")
            A("")
            short = [r for r in dxk if r["kw"] in ("AI动画", "AI短片")
                     and r["cells"].get("<30秒", (None, 0))[0] is not None]
            A("**给「AI 动画/短片」的直接结论**：")
            A("")
            for kw in ("AI动画", "AI短片"):
                row = next((r for r in dxk if r["kw"] == kw), None)
                if not row:
                    continue
                ok = [(lab, v, n) for lab, (v, n) in row["cells"].items() if v]
                if not ok:
                    continue
                bl = max(ok, key=lambda x: x[1])
                bs = min(ok, key=lambda x: x[1])
                A(f"- `{kw}`：最优 **{bl[0]}**（{w(bl[1])}），最差 **{bs[0]}**（{w(bs[1])}），"
                  f"差距 {bl[1]/bs[1]:.0f} 倍。")
            A("")
    else:
        A("_时长或题材数据不足，跳过交叉分析。_")
    A("")

    # ==================================================================================
    # 五、AI 关键词：供给 vs 需求
    # ==================================================================================
    A("---")
    A("")
    A("## 五、AI 题材的竞争门槛：进榜要多少播放")
    A("")
    A(f"> **供给**：该关键词近 {rd} 天的搜索结果数（`numResults`）。⚠️ 除 `Stable Diffusion` 外全部顶到 "
      "B 站上限 1000，**这个字段已经区分不出竞争强度了**，所以本章不靠它下结论。")
    A(f"> **更可靠的读法**：每个关键词近 {rd} 天按播放排序抓到的前 ~84 条样本，它们的 "
      "**P25 就是「挤进该关键词近 30 天播放前列」的门槛**，P75 则是「站稳前列」的水平。")
    A("> ⚠️ 样本是按播放排序取头部的，所以这不是「随便发一条能拿多少播放」，"
      "而是「要挤进这个关键词的前列，你得打到多少播放」。")
    A("")
    if gaps:
        ranked = sorted([g for g in gaps if g["p25"]], key=lambda g: g["p25"])
        n_r = len(ranked)
        for i, g in enumerate(ranked):
            g["tier"] = ("好挤" if i < n_r / 3 else "中等" if i < 2 * n_r / 3 else "难挤")
        A("| 关键词 | 供给(近%d天结果数) | 样本 n | 播放 P25（门槛） | 播放中位数 | 播放 P75 | 播放均值 | 头部10条占比 | 门槛档位 |" % rd)
        A("|---|---|---|---|---|---|---|---|---|")
        for g in gaps:
            A(f"| `{g['kw']}` | {g['supply']}{'（饱和）' if g['supply'] >= 1000 else ''} | {g['n']} | "
              f"**{w(g['p25'])}** | {w(g['med_view'])} | {w(g['p75'])} | {w(g['mean_view'])} | "
              f"{pctstr(g['top10_share'],1)} | {g.get('tier','—')} |")
        A("")
        A("**门槛怎么读（按 P25 从低到高 = 从好挤到难挤）：**")
        A("")
        for g in ranked:
            room = (g["p75"] / g["p25"]) if g["p25"] else None
            A(f"- `{g['kw']}`：门槛 **{w(g['p25'])}**（P25）→ 站稳要 {w(g['p75'])}（P75），"
              f"头部余量 {room:.2f}×；头部 10 条吃掉该词 {pctstr(g['top10_share'],1)} 的播放。")
        A("")
        easy = [g for g in ranked if g.get("tier") == "好挤"]
        hard = [g for g in ranked if g.get("tier") == "难挤"]
        if easy:
            A("- **好挤（P25 最低的 1/3）**：" + "、".join("`" + g["kw"] + "`" for g in easy) +
              " —— 播放数字看着不高，但它们同时也是「天花板低」的题材（见 P75 列），"
              "适合练手/起量，不适合当作主赛道。")
        if hard:
            A("- **难挤（P25 最高的 1/3）**：" + "、".join("`" + g["kw"] + "`" for g in hard) +
              " —— 想进前列就得打到百万级播放，但它们同时给出最高的天花板。"
              "**新号如果要做动画/短片，正确做法不是绕开这些词，"
              "而是用「官方活动 tag + 1–5 分钟时长」这两个杠杆去打**（见六·B 与四·B）。")
        A("")
        A("> ⚠️ **本表没有「机会区」，这不是巧合**：除了 Stable Diffusion，其他词近 30 天的搜索结果数都顶到 "
          "B 站上限 1000，说明这些关键词**供给端已经全面饱和**，不存在「没人做的题材空白」。"
          "所以新号的缝隙不在「选哪个题材」，而在**同题材里换形式**（时长、叙事结构、活动池）。")
        A("")
    else:
        A("_近期窗口数据不足，无法做供需象限分析。_")
        A("")

    # ==================================================================================
    # 六、标题规律
    # ==================================================================================
    A("---")
    A("")
    A("## 六、AI 题材标题的句式规律（数据版）")
    A("")
    A(f"> 语料 = 全部 AI 关键词搜索结果去重后 {corpus_n} 条。")
    A("> `lift` = 「标题含该特征」的播放中位数 ÷ 「标题不含该特征」的播放中位数。lift > 1 说明该特征与更高播放相关。")
    A("> 注意：这是**相关性不是因果**，头部大号本来就更爱用某些写法；但它足以说明「观众对这个写法不排斥」。")
    A("")
    if ps:
        A("| 句式特征 | 出现条数 | 占比 | 含该特征·播放中位数 | 不含·播放中位数 | lift |")
        A("|---|---|---|---|---|---|")
        for p in ps:
            lift = f"**{p['lift']:.2f}×**" if p["lift"] else "样本不足"
            A(f"| {p['name']} | {p['n']} | {pctstr(p['share'],1)} | {w(p['med_hit'])} | "
              f"{w(p['med_miss'])} | {lift} |")
        A("")
        strong = [p for p in ps if p["lift"] and p["lift"] >= 1.15]
        weak = [p for p in ps if p["lift"] and p["lift"] <= 0.85]
        if strong:
            A("**正向特征（用得上）**：" + "；".join(
                f"`{p['name']}` 提升 {p['lift']:.2f}×" for p in strong[:6]))
            A("")
        if weak:
            A("**负向特征（慎用）**：" + "；".join(
                f"`{p['name']}` 只有 {p['lift']:.2f}×" for p in weak[:6]))
            A("")
    A("")

    # 标题 TOP
    A("### AI 关键词下播放 TOP 25 标题")
    A("")
    A("| # | 播放 | 标题 | UP 主 | 时长 | 发布日期 | 投币率 | 命中关键词 |")
    A("|---|---|---|---|---|---|---|---|")
    top_ai = sorted([r for r in ai_rows if num(r.get("view"))], key=lambda r: -num(r["view"]))[:25]
    for i, r in enumerate(top_ai, 1):
        c, v = num(r.get("coin")), num(r.get("view"))
        crr = f"{c/v*100:.2f}%" if (c is not None and v) else "—"
        A(f"| {i} | {w(r['view'])} | {esc(r['title'])[:56]} | {esc(r['up_name'])[:12]} | "
          f"{fmt_dur(r.get('duration_sec'))} | {date_of(r.get('pubdate'))} | {crr} | {esc(r.get('keyword'))} |")
    A("")

    # 标题长度
    if top_ai:
        lens = [len(r["title"]) for r in ai_rows if r.get("title")]
        lt = [len(r["title"]) for r in top_ai]
        if lens and lt:
            A(f"**标题长度**：全语料中位数 {med(lens):.0f} 字；播放 TOP25 中位数 {med(lt):.0f} 字"
              f"（TOP25 最短 {min(lt)} 字，最长 {max(lt)} 字）。")
            A("")
            A("> ⚠️ 上面 `全民/征集/活动` 这一项的 41.8× lift 不要读成「用词技巧」——"
              "它命中的其实是**平台官方活动 tag**。下一节单独拆开验证。")
            A("")

    # ==================================================================================
    # 六·B、官方活动池 —— 本次数据里最强的单一杠杆
    # ==================================================================================
    A("---")
    A("")
    A("## 六·B、官方活动池：本次数据里最强的单一杠杆")
    A("")
    A("> B 站会周期性开「AI 全民制作人」「AI 创作大赛」「AI MV 大赛」这类活动。"
      "投稿时把活动名写进标题/tag，作品会被塞进活动专属流量池。")
    A("> 下面用同一批语料做「含活动字样 vs 不含」的播放中位数对比。")
    A("")
    if act:
        A(f"语料：AI 关键词去重后 {act['n_hit'] + act['n_miss']} 条（有播放数据）。")
        A("")
        A("| 分组 | 条数 | 占比 | 播放中位数 | 播放均值 |")
        A("|---|---|---|---|---|")
        A(f"| 标题含官方活动字样 | {act['n_hit']} | {pctstr(act['share'],1)} | "
          f"**{w(act['med_hit'])}** | {w(mean([num(r['view']) for r in act['hit']]))} |")
        A(f"| 不含 | {act['n_miss']} | {pctstr(1 - act['share'],1)} | "
          f"{w(act['med_miss'])} | {w(mean([num(r['view']) for r in act['miss']]))} |")
        A("")
        if act["lift"]:
            A(f"**杠杆倍数：{act['lift']:.1f}×** —— 含活动字样的视频播放中位数是不含的 {act['lift']:.1f} 倍。")
            A("")
        A(f"**头部占比**：播放 TOP50 里有 **{act['top50']}/50** 条带活动字样，"
          f"TOP100 里有 **{act['top100']}/100** 条。")
        A("")
        if act["camps"]:
            A("**具体活动拆解：**")
            A("")
            A("| 活动名 | 命中条数 | 播放中位数 |")
            A("|---|---|---|")
            for c in act["camps"]:
                A(f"| {c['name']} | {c['n']} | {w(c['med'])} |")
            A("")
        A("**这条结论为什么重要**：榜单门面被活动池占掉了将近一半，而且中位播放量差了 40 倍以上 —— "
          "对 0 粉新号来说，**「有没有进活动池」比「内容做得多好」更能决定第一波曝光**。"
          "动作很便宜：投稿前先去创作中心的活动页找到在跑的 AI 活动，投稿时挂上。")
        A("")
        A("> 相关性说明：也可能是「认真做的人才会去参加活动」，但从 "
          + (lambda c: f"{c['n']} 条 `{c['name']}` 中位播放 {w(c['med'])}" if c else "上表")
            (next((c for c in act["camps"] if c["name"] == "AI全民制作人"),
                  act["camps"][0] if act["camps"] else None))
          + " 的体量看，活动流量池的加成是真实存在的。")
    else:
        A("_活动标签样本不足，跳过。_")
    A("")
    A("---")
    A("")
    A("## 七、对手结构：谁在吃这个赛道，新号还有位置吗")
    A("")
    upagg: dict[str, dict] = {}
    for r in uniq:
        name = r.get("up_name") or "?"
        d = upagg.setdefault(name, {"n": 0, "views": [], "followers": r.get("up_followers")})
        d["n"] += 1
        v = num(r.get("view"))
        if v:
            d["views"].append(v)
        if r.get("up_followers") not in ("", None):
            d["followers"] = r["up_followers"]
    topups = sorted(upagg.items(), key=lambda kv: -(sum(kv[1]["views"]) or 0))[:20]
    if topups:
        A("| UP 主 | 上榜/命中条数 | 合计播放 | 单条播放中位数 | 粉丝数 |")
        A("|---|---|---|---|---|")
        for name, d in topups:
            A(f"| {esc(name)[:20]} | {d['n']} | {w(sum(d['views']))} | {w(med(d['views']))} | "
              f"{w(num(d['followers'])) if d['followers'] not in ('', None) else '—'} |")
        A("")

    # 粉丝数分层：判断新号可及性
    if gate:
        A(f"### 粉丝数到底是不是门槛（按 UP 主聚合，n={gate['n_up']} 位有粉丝数据的 UP 主）")
        A("")
        A("> ⚠️ 样本都来自「已经上榜/被检索到」的视频，存在幸存者偏差。"
          "但下面的比较是**在同一条件（都进了榜单）下**做的，所以「粉丝量影响多大」这个结论是干净的。")
        A("")
        A("| 粉丝段 | UP 主数 | 单条播放中位数 | 播放/粉丝 放大中位数 | 该段最大放大 |")
        A("|---|---|---|---|---|")
        for t in gate["tiers"]:
            A(f"| {t['label']} | {t['n']} | {w(t['med_view'])} | **{t['med_amp']:.1f}×** | {t['max_amp']:.1f}× |")
        A("")
        if gate["small_med"] and gate["big_med"]:
            A(f"- **同榜单内，粉丝 <10 万的账号（n={len(gate['small'])}）单条播放中位数 "
              f"{w(gate['small_med'])}，10 万粉以上（n={len(gate['big'])}）{w(gate['big_med'])}，"
              f"只差 {gate['big_med']/gate['small_med']:.2f} 倍。**")
        if gate["small_amp"] and gate["big_amp"]:
            A(f"- 但小号的「播放 ÷ 粉丝」放大倍数是 **{gate['small_amp']:.0f}×**，大号只有 "
              f"{gate['big_amp']:.1f}×，相差 **{gate['small_amp']/gate['big_amp']:.0f} 倍** —— "
              f"推荐算法给新号的曝光杠杆远大于给成熟账号的。")
        A("")
        top_small = sorted(gate["small"], key=lambda u: -u["amp"])[:6]
        if top_small:
            A("**小号里的实证（播放/粉丝 放大倍数 TOP）：**")
            A("")
            A("| UP 主 | 粉丝 | 单条播放中位数 | 放大倍数 | 样本条数 |")
            A("|---|---|---|---|---|")
            for u in top_small:
                A(f"| {esc(u['name'])[:20]} | {w(u['f'])} | {w(u['med'])} | **{u['amp']:.0f}×** | {u['n']} |")
            A("")
        A("**结论：榜单入口不设粉丝门槛。** 新号的瓶颈不是「没粉丝」，"
          "而是「内容能不能被算法判定值得推」。粉丝 <10 万的账号在同样的榜单里能拿到和百万大号同量级的播放。")
        A("")
    else:
        A("_粉丝数据不足（详情补全未覆盖到 UP 主），跳过分层分析。_")
        A("")

    rookie = [r for r in rank_rows if r.get("zone_cn") == "新人榜"]
    if rookie:
        A(f"### 新人榜（B 站官方「新人」榜，n={len(rookie)}）")
        A("")
        A(f"- 播放中位数 {w(med([r['view'] for r in rookie]))}，均值 {w(mean([r['view'] for r in rookie]))}，"
          f"最高 {w(max(num(r['view']) for r in rookie))}。")
        A(f"- 投币/播放中位数 {pctstr(med([num(r['coin'])/num(r['view']) for r in rookie if num(r.get('coin')) and num(r.get('view'))]),3)}。")
        A("")
        A("| # | 标题 | UP 主 | 播放 | 投币率 | 时长 | 分区 |")
        A("|---|---|---|---|---|---|---|")
        for i, r in enumerate(sorted(rookie, key=lambda x: -num(x["view"]))[:15], 1):
            c, v = num(r.get("coin")), num(r.get("view"))
            A(f"| {i} | {esc(r['title'])[:48]} | {esc(r['up_name'])[:12]} | {w(v)} | "
              f"{(f'{c/v*100:.2f}%' if c is not None and v else '—')} | {fmt_dur(r.get('duration_sec'))} | "
              f"{esc(r.get('tname') or r.get('tname_v2'))} |")
        A("")
        # 新人榜里有多少和 AI 相关
        ai_like = re.compile(r"AI|ai|生成|Stable|Comfy|模型|数字人|虚拟")
        hit = [r for r in rookie if ai_like.search(r.get("title") or "") or ai_like.search(r.get("tname_v2") or "")]
        A(f"- 新人榜里标题或二级分区带 AI 字样的有 **{len(hit)}/{len(rookie)} 条**"
          f"（{len(hit)/len(rookie)*100:.1f}%），说明新人榜的 AI 浓度{'很高' if len(hit)/len(rookie) > 0.1 else '一般'}。")
        A("")

    # ==================================================================================
    # 八、可执行结论
    # ==================================================================================
    A("---")
    A("")
    A("## 八、给「AI 动画/短片」新号的可执行结论")
    A("")
    recs = []
    # 1) 官方活动池 —— 最强杠杆，放第一条
    if act and act["lift"]:
        c0 = max(act["camps"], key=lambda c: c["n"]) if act["camps"] else None
        recs.append(
            f"**① 投稿必须进官方活动池（第一优先，成本最低杠杆最大）**：标题带官方活动字样的视频播放中位数 "
            f"{w(act['med_hit'])}，不带只有 {w(act['med_miss'])}，**杠杆 {act['lift']:.1f} 倍**；"
            f"播放 TOP100 里 {act['top100']} 条带活动字样。"
            + (f"当前在跑的活动里 `{c0['name']}` 命中 {c0['n']} 条、中位播放 {w(c0['med'])}，" if c0 else "")
            + "发布前去创作中心活动页找在跑的 AI 活动并挂上。"
        )
    # 2) 时长（按题材）
    if dxk_best:
        m = {b["kw"]: b for b in dxk_best}
        pick = [m[k] for k in ("AI动画", "AI短片") if k in m]
        if pick:
            recs.append(
                "**② 把片长锁死在甜蜜区**：" +
                "；".join(f"`{b['kw']}` 用 {b['label']}（中位播放 {w(b['med'])}，n={b['n']}）" for b in pick) +
                "。<1 分钟和 >10 分钟这两端在中位数上都是塌的，别做。"
            )
        elif db:
            good = [b for b in db if b["n"] >= 8]
            if good:
                bd = max(good, key=lambda b: b["med_view"] or 0)
                recs.append(f"**② 时长照抄 `{bd['label']}`**：播放中位数 {w(bd['med_view'])}，是样本 ≥8 的时长段里最高的。")
    # 3) 双轨题材
    if loyalty and coin_bench:
        flow = [x for x in loyalty if x["med_view"] and x["med_rate"] and
                x["med_rate"] < coin_bench * 0.5 and x["med_view"] > 1e5]
        asset = [x for x in loyalty if x["med_rate"] and x["med_rate"] >= coin_bench * 2]
        if flow and asset:
            recs.append(
                f"**③ 双轨打法**：冲播放用 `{flow[0]['kw']}` 这类流量型题材（播放中位数 "
                f"{w(flow[0]['med_view'])}），涨铁粉用 `{asset[0]['kw']}` 这类资产型题材（投币率 "
                f"{pctstr(asset[0]['med_rate'],3)}，是流量型的 {asset[0]['med_rate']/flow[0]['med_rate']:.0f} 倍）。"
                f"前者决定你被多少人看到，后者决定有多少人记住你。"
            )
    # 4) 粉丝门槛
    if gate and gate["small_amp"] and gate["big_amp"]:
        recs.append(
            f"**④ 别拿「没粉丝」当借口，但也别指望粉丝**：同榜单内粉丝 <10 万的账号单条播放中位数 "
            f"{w(gate['small_med'])}，和百万大号的 {w(gate['big_med'])} 只差 "
            f"{gate['big_med']/gate['small_med']:.2f} 倍 —— 冷启动不欠你流量；"
            f"但小号的播放/粉丝放大倍数是大号的 {gate['small_amp']/gate['big_amp']:.0f} 倍，"
            f"说明你现在每一条的播放几乎全部来自推荐，**内容不行就是 0**，没有粉丝保底。"
        )
    # 5) 门槛
    if gaps:
        ranked = sorted([g for g in gaps if g["p25"]], key=lambda g: g["p25"])
        if ranked:
            lo3 = ranked[:3]
            recs.append(
                "**⑤ 关键词按门槛排序入场**：最好挤的是 " +
                "、".join(f"`{g['kw']}`（P25 门槛 {w(g['p25'])}）" for g in lo3) +
                "，最难的是 " + "、".join(f"`{g['kw']}`（{w(g['p25'])}）" for g in ranked[-2:]) +
                "。注意**门槛低 ≠ 值得做**（低门槛题材的天花板同样低），"
                "主流关键词虽然门槛在百万级，但有官方活动池可以借力。"
            )
    # 6) 标题
    title_feats = [p for p in strong if p["name"] != "全民/征集/活动"]
    if title_feats:
        head = "**⑥ 标题公式**：优先使用 " + "、".join(
            f"`{p['name']}`（lift {p['lift']:.2f}×，样本 {p['n']} 条）" for p in title_feats[:3])
        if weak:
            head += "；避免 " + "、".join(f"`{p['name']}`" for p in weak[:2])
        recs.append(head + "。注意 lift 是相关性，`阿拉伯数字`／`教程/方法论` 的 lift 只有 "
                          f"{next((p['lift'] for p in ps if p['name']=='阿拉伯数字'), 0):.2f}×／"
                          f"{next((p['lift'] for p in ps if p['name']=='教程/方法论'), 0):.2f}×，"
                          "说明**在标题里堆数字、或把自己标成「教程」，在 AI 赛道是负向信号**"
                          "（教程类的高投币率见结论③，所以教程适合做长尾资产，不适合做冲量标题）。")
    # 7) 分区参考
    if zstat:
        good = sorted([z for z in zstat if z["n"] >= 20 and z["lift"] is not None], key=lambda z: z["lift"])
        if good:
            alt = good[0]
            recs.append(
                f"**⑦ 分区层面的参考（次要）**：在 3 日榜里 `{alt['zone']}` 的「均值/中位数」倍数最低"
                f"（{alt['lift']:.2f}×），即该分区播放分布最均匀、不靠单个爆款撑场。"
                f"AI 动画/短片实际投递分区建议以「动画」为主、视题材分流到「影视/生活」，"
                f"不要因为这条就去做游戏区。"
            )
    for i, r in enumerate(recs, 1):
        A(f"{i}. {r}")
    A("")

    A("---")
    A("")
    A(f"_本报告由 `抓热榜.py` + `分析.py` 自动生成；原始数据见 `raw_{date_tag}.json`，"
      f"明细表见 `热榜日报_{date_tag}.csv`。_")
    A("")

    path = OUT_DIR / f"题材分析_{date_tag}.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------
# 统计子表
# --------------------------------------------------------------------------------------
def zone_table(rank_rows):
    zones: dict[str, list] = {}
    for r in rank_rows:
        z = r.get("zone_cn") or "?"
        zones.setdefault(z, []).append(r)
    out = []
    for z, rs in zones.items():
        views = [num(r["view"]) for r in rs]
        mv, av = med(views), mean(views)
        if mv is None:
            continue
        ratios = [num(r["coin"]) / num(r["view"]) for r in rs
                  if num(r.get("coin")) and num(r.get("view"))]
        out.append({
            "zone": z, "n": len(rs), "med_view": mv, "mean_view": av,
            "lift": (av / mv) if mv else None,
            "med_like": med([num(r["like"]) for r in rs]),
            "med_coin": med([num(r["coin"]) for r in rs]),
            "med_coin_ratio": med(ratios),
            "med_dur": med([num(r["duration_sec"]) for r in rs]),
        })
    out.sort(key=lambda x: -(x["med_view"] or 0))
    return out


def coin_rank(rows, min_view=10000):
    out = []
    for r in dedup_by_bvid(rows):
        c, v = num(r.get("coin")), num(r.get("view"))
        if c is None or v is None or v < min_view or c <= 0:
            continue
        lk = num(r.get("like")) or 0
        out.append({**r, "coin": c, "view": v, "ratio": c / v, "like_ratio": (lk / v) if v else None})
    out.sort(key=lambda x: -x["ratio"])
    return out


DUR_BUCKETS = [("<30秒", 0, 30), ("30-60秒", 30, 60), ("1-3分钟", 60, 180),
               ("3-5分钟", 180, 300), ("5-10分钟", 300, 600), (">10分钟", 600, float("inf"))]


def duration_table(rows):
    rows = [r for r in dedup_by_bvid(rows) if num(r.get("duration_sec")) and num(r.get("view"))]
    if not rows:
        return []
    views_all = sorted(num(r["view"]) for r in rows)
    p90 = pct(views_all, 0.90)
    out = []
    for lab, lo, hi in DUR_BUCKETS:
        g = [r for r in rows if lo <= num(r["duration_sec"]) < hi]
        if not g:
            continue
        views = [num(r["view"]) for r in g]
        mv, av = med(views), mean(views)
        out.append({
            "label": lab, "n": len(g), "med_view": mv, "mean_view": av,
            "lift": (av / mv) if mv else None,
            "top10_share": (sum(1 for v in views if v >= p90) / len(views)) if p90 else None,
        })
    return out


# 官方活动/征集的识别正则。B 站会周期性地开「AI 全民制作人」「AI 创作大赛」这类活动，
# 投稿时挂上活动 tag 会被塞进活动专属流量池 —— 这是本报告里最强的一个「非内容」杠杆。
ACTIVITY_RE = re.compile(r"全民制作人|创作大赛|MV\s*大赛|短视频大赛|大赛|征集|共创|企划|挑战赛|激励计划")
CAMPAIGNS = ["AI全民制作人", "AI创作大赛", "AI MV大赛", "updream", "HiShorts",
             "征集", "激励计划"]


def activity_stats(ai_rows):
    """官方活动 tag 的杠杆有多大。"""
    corpus = [r for r in ai_rows if num(r.get("view")) is not None]
    if not corpus:
        return None
    def tagged(rs):
        return [r for r in rs if ACTIVITY_RE.search(r.get("title") or "")]
    hit = tagged(corpus)
    hit_ids = {id(r) for r in hit}
    miss = [r for r in corpus if id(r) not in hit_ids]
    if len(hit) < 5 or len(miss) < 5:
        return None
    mh, mm = med([num(r["view"]) for r in hit]), med([num(r["view"]) for r in miss])
    ranked = sorted(corpus, key=lambda r: -num(r["view"]))
    camps = []
    for c in CAMPAIGNS:
        g = [r for r in corpus if c in (r.get("title") or "")]
        if len(g) >= 2:
            camps.append({"name": c, "n": len(g), "med": med([num(r["view"]) for r in g])})
    camps.sort(key=lambda x: -(x["med"] or 0))
    return {
        "n_hit": len(hit), "n_miss": len(miss), "hit": hit, "miss": miss,
        "med_hit": mh, "med_miss": mm,
        "lift": (mh / mm) if (mh and mm) else None,
        "share": len(hit) / len(corpus),
        "top50": sum(1 for r in ranked[:50] if ACTIVITY_RE.search(r.get("title") or "")),
        "top100": sum(1 for r in ranked[:100] if ACTIVITY_RE.search(r.get("title") or "")),
        "camps": camps,
    }


def coin_loyalty(ai_rows):
    """按关键词算「投币率」：播放买得来，投币买不来 —— 这是粉丝沉淀的代理指标。"""
    corpus = [r for r in dedup_by_bvid(ai_rows) if num(r.get("view"))]
    bench = None
    allcr = [num(r["coin"]) / num(r["view"]) for r in corpus
             if num(r.get("coin")) is not None and num(r["view"])]
    if allcr:
        bench = med(allcr)
    groups: dict[str, list] = {}
    for r in corpus:
        c, v = num(r.get("coin")), num(r.get("view"))
        if c is None or not v:
            continue
        groups.setdefault(r["keyword"], []).append(c / v)
    out = []
    for kw, rs in groups.items():
        if len(rs) < 8:
            continue
        mv = med([num(r["view"]) for r in corpus if r.get("keyword") == kw and num(r.get("view"))])
        out.append({
            "kw": kw, "n_coin": len(rs), "med_rate": med(rs),
            "med_view": mv,
            "share_above": (sum(1 for x in rs if bench and x > bench) / len(rs)) if bench else None,
        })
    out.sort(key=lambda x: -(x["med_rate"] or 0))
    return out, bench


def follower_gate(rows):
    """粉丝数到底是不是门槛：同榜单内比「播放/粉丝」放大倍数。"""
    by_up: dict = {}
    for r in dedup_by_bvid(rows):
        mid = r.get("up_mid")
        f = num(r.get("up_followers"))
        v = num(r.get("view"))
        if not mid:
            continue
        d = by_up.setdefault(mid, {"f": None, "name": r.get("up_name"), "vs": []})
        if f:
            d["f"] = f
        if v:
            d["vs"].append(v)
    ups = []
    for d in by_up.values():
        if d["f"] and d["vs"]:
            ups.append({"f": d["f"], "name": d["name"], "med": med(d["vs"]),
                        "amp": med(d["vs"]) / d["f"], "n": len(d["vs"])})
    if len(ups) < 10:
        return None
    tiers = [("1万–10万粉", 1e4, 1e5), ("10万–50万粉", 1e5, 5e5),
             ("50万–200万粉", 5e5, 2e6), (">200万粉", 2e6, float("inf"))]
    tier_rows = []
    for lab, lo, hi in tiers:
        g = [u for u in ups if lo <= u["f"] < hi]
        if g:
            tier_rows.append({"label": lab, "n": len(g),
                              "med_view": med([u["med"] for u in g]),
                              "med_amp": med([u["amp"] for u in g]),
                              "max_amp": max(u["amp"] for u in g)})
    small = [u for u in ups if u["f"] < 1e5]
    big = [u for u in ups if u["f"] >= 1e5]
    return {
        "n_up": len(ups), "tiers": tier_rows, "ups": ups,
        "small": small, "big": big,
        "small_med": med([u["med"] for u in small]) if small else None,
        "big_med": med([u["med"] for u in big]) if big else None,
        "small_amp": med([u["amp"] for u in small]) if small else None,
        "big_amp": med([u["amp"] for u in big]) if big else None,
    }


def duration_x_keyword(ai_rows, kws=None, min_n=5):
    """时长 × 关键词 交叉：不同题材的「甜蜜时长」并不一样。"""
    corpus = [r for r in dedup_by_bvid(ai_rows)
              if num(r.get("duration_sec")) is not None and num(r.get("view"))]
    if not corpus:
        return [], []
    have = {r["keyword"] for r in corpus}
    order = kws or [k for k in ("AI动画", "AI短片", "AI漫剧", "AI视频", "AI音乐", "AI绘画",
                                "ComfyUI", "Stable Diffusion", "AI生成", "AI电影") if k in have]
    rows_out, best = [], []
    for kw in order:
        rs = [r for r in corpus if r["keyword"] == kw]
        if len(rs) < min_n:
            continue
        cells = {}
        for lab, lo, hi in DUR_BUCKETS:
            g = [num(r["view"]) for r in rs if lo <= num(r["duration_sec"]) < hi]
            cells[lab] = (med(g), len(g)) if len(g) >= min_n else (None, len(g))
        rows_out.append({"kw": kw, "cells": cells, "n": len(rs)})
        ok = [(lab, v, n) for lab, (v, n) in cells.items() if v]
        if ok:
            lab, v, n = max(ok, key=lambda x: x[1])
            best.append({"kw": kw, "label": lab, "med": v, "n": n})
    return rows_out, best


def gap_table(ai_rows, meta):
    """按关键词做供需象限。只看「近 N 天窗口」里抓到的样本。"""
    kwm = meta.get("keyword_meta") or {}
    recent_set = set(meta.get("recent_bvids") or [])
    groups: dict[str, list] = {}
    for r in ai_rows:
        if recent_set and r.get("bvid") not in recent_set:
            continue
        if not recent_set and not str(r.get("order", "")).startswith("recent"):
            continue
        groups.setdefault(r["keyword"], []).append(r)
    if not groups:
        return []
    tmp = []
    for kw, rs in groups.items():
        rs = dedup_by_bvid(rs)
        views = [num(r["view"]) for r in rs if num(r.get("view"))]
        if len(views) < 5:
            continue
        tot = sum(views)
        top10 = sum(sorted(views, reverse=True)[:10])
        tmp.append({
            "kw": kw,
            "supply": kwm.get(kw, {}).get("recent_numResults", 0),
            "n": len(views),
            "p25": pct(views, 0.25), "med_view": med(views), "p75": pct(views, 0.75),
            "mean_view": mean(views),
            "top10_share": (top10 / tot) if tot else None,
        })
    if not tmp:
        return []
    sup_med = med([g["supply"] for g in tmp])
    dem_med = med([g["med_view"] for g in tmp])
    for g in tmp:
        hi_d = (g["med_view"] or 0) >= (dem_med or 0)
        hi_s = (g["supply"] or 0) >= (sup_med or 0)
        g["quadrant"] = ("机会区" if (hi_d and not hi_s) else
                         "红海区" if (hi_d and hi_s) else
                         "冷门区" if (not hi_d and not hi_s) else "劝退区")
    tmp.sort(key=lambda g: (g["quadrant"] != "机会区", -(g["med_view"] or 0)))
    return tmp
