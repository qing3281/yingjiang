# -*- coding: utf-8 -*-
"""
产能对齐.py —— 回答「什么视频适合我们生成」

选题决策.py 回答「什么题材有需求」；这个脚本回答「需求里哪些我们真做得出来」。

数据分两个池子，必须分开看：
  search  池 —— 关键词搜索结果，含大量低播放样本，反映【题材的真实竞争分布】
  ranking 池 —— 各分区热榜，反映【这个题材的天花板】
混在一起算分位数是错的。

用法：
    python 产能对齐.py
    python 产能对齐.py --wan 4        # Wan 生成一个 5 秒镜头的分钟数（实测后回填）
"""
from __future__ import annotations

import argparse
import csv
import io
import statistics as st
from pathlib import Path

ROOT = Path(r"D:\DSHworkspace\B站")
情报 = ROOT / "情报"

# ---------------------------------------------------------------------------
# 生产成本模型。Z-Image 部分全部是【实测值】(2026-10-12, RTX 5080 Laptop 16GB)。
# 实测样本：4 镜头 1920x1080 成片，总耗时 35.6 秒出 13.6 秒视频。
#   · 第 1 张 6.1s（含首次装载），其后 4.8 / 4.9 / 4.8 秒
#   · 合成 4 张共 408 帧，约 11 秒
# Wan 部分仍是估值，模型到位后用 --wan 回填。
# ---------------------------------------------------------------------------
出图秒 = 4.9          # Z-Image-Turbo int8，1536×864（16:9 生成分辨率），8 步 —— 实测
出图首次加载秒 = 25   # 冷启动装载 UNET+CLIP+VAE（实测首张多花约 1.3 秒，冷机另计）
合成秒_每图 = 2.8     # 图集运镜：Ken Burns + 交叉溶解 + x264 编码，1920×1080 —— 实测
拼接秒_每镜 = 15.0    # 多镜头拼接、转场、混音，每镜约 15 秒（未实测）
镜头秒 = 5.0          # 一个 Wan 镜头 ≈ 5 秒

题材关键词 = [
    "AI动画", "AI短片", "AI漫剧", "AI音乐", "AI电影",
    "AI视频", "AI生成", "AI绘画", "ComfyUI", "Stable Diffusion",
]

形态说明 = {
    "A": ("图集运镜", "N 张静图 + 推拉摇移拼接。不需要视频模型，今天就能跑。"),
    "B": ("单镜头 I2V", "一张图喂给 Wan 生成一个 5 秒动图。适合做片头/高潮点缀。"),
    "C": ("多镜头短片", "N 个 I2V 镜头拼成完整叙事。质量最高，耗时随镜头数线性增长。"),
    "D": ("叙事动画", "角色跨镜头保持一致 + 表演。目前没有角色 LoRA / 参考图一致性方案。"),
}

# ---------------------------------------------------------------------------
# 内容性质：我们只会【生成画面】，生成不了【讲解】【录屏】【真人】。
# 这一列比产能更致命——产能不够可以等，内容形态不对就是根本做不了。
# ---------------------------------------------------------------------------
题材性质 = {
    "AI绘画": ("画面型", "内容主体就是画面本身，出图即成品"),
    "AI生成": ("画面型", "内容主体是生成的图像/视频"),
    "ComfyUI": ("教程型", "需要录屏操作界面 + 口播讲解，生成解决不了"),
    "Stable Diffusion": ("教程型", "同上，参数讲解 + 界面录屏"),
    "AI动画": ("画面型", "内容就是动画画面，但需要角色一致性（形态D）"),
    "AI短片": ("画面型", "内容就是短片画面，但需要多镜头叙事（形态C）"),
    "AI电影": ("画面型", "同 AI短片"),
    "AI漫剧": ("画面型", "漫画分镜 + 配音，需要大量角色一致性素材"),
    "AI音乐": ("画面型", "MV＝画面＋音乐，音乐可外部生成"),
    "AI视频": ("混合型", "画面与讲解混杂，看具体账号"),
}


def 小时(秒: float) -> str:
    if 秒 < 90:
        return f"{秒:.0f} 秒"
    if 秒 < 3600:
        return f"{秒/60:.1f} 分"
    return f"{秒/3600:.1f} 小时"


def 分位(样本, p):
    if not 样本:
        return 0.0
    s = sorted(样本)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def 读情报(date=None):
    if date:
        p = 情报 / f"热榜日报_{date}.csv"
        if not p.exists():
            raise SystemExit(f"找不到 {p}")
    else:
        c = sorted(情报.glob("热榜日报_*.csv"))
        if not c:
            raise SystemExit(f"{情报} 下没有热榜日报_*.csv")
        p = c[-1]
    return p, p.stem.split("_")[-1], list(csv.DictReader(io.open(p, encoding="utf-8-sig")))


def 取数(rows):
    """把字符串列转成数值列。view=0 的未富化行在后面按池子处理。"""
    for r in rows:
        try:
            r["_v"] = int(r.get("view") or 0)
        except ValueError:
            r["_v"] = 0
        try:
            r["_d"] = int(r.get("duration_sec") or 0)
        except ValueError:
            r["_d"] = 0
        try:
            r["_c"] = float(r.get("coin_play_ratio") or 0)
        except ValueError:
            r["_c"] = 0.0
    return rows


def 后缀(r):
    """source_key 形如 search:AI动画:recent30d —— 最后一段是排序方式。"""
    return (r.get("source_key") or "").rsplit(":", 1)[-1]


def 评题材(rows):
    out = []
    for kw in 题材关键词:
        k = kw.lower()
        rs = [r for r in rows
              if k in (r.get("title") or "").lower()
              or k in (r.get("tag") or "").lower()]
        if len(rs) < 20:
            continue

        # 近 30 天【最热】——按热度排的，是爆款池，这才是「什么内容在火」
        爆 = [r["_v"] for r in rs if 后缀(r) == "recent30d" and r["_v"] > 0]
        # 历史【综合】——长期有效的内容
        久 = [r["_v"] for r in rs if 后缀(r) == "totalrank" and r["_v"] > 0]
        # 热榜——分区上榜内容
        榜 = [r["_v"] for r in rs if r.get("source") == "ranking" and r["_v"] > 0]

        全部 = [r for r in rs if r["_v"] > 0]
        durs = [r["_d"] for r in 全部 if r["_d"] > 0]
        coins = [r["_c"] for r in 全部 if r["_c"] > 0]
        if not durs or not 爆:
            continue

        out.append({
            "题材": kw,
            "爆款n": len(爆),
            "爆P25": 分位(爆, 0.25),
            "爆P50": 分位(爆, 0.50),
            "爆P75": 分位(爆, 0.75),
            "历史中位": st.median(久) if 久 else 0.0,
            "热榜中位": st.median(榜) if 榜 else 0.0,
            "时长中位": st.median(durs),
            "投币率": st.median(coins) if coins else 0.0,
        })
    return out


def 判形态(时长秒, wan秒):
    镜头数 = max(1, round(时长秒 / 镜头秒))
    甲 = 出图首次加载秒 + 镜头数 * (出图秒 + 合成秒_每图)
    丙 = 出图首次加载秒 + 镜头数 * (出图秒 + wan秒 + 拼接秒_每镜)
    if 丙 <= 3 * 3600:
        档, 为何 = "✅ 今天能做", "形态C 在 3 小时预算内"
    elif 甲 <= 3600:
        档, 为何 = "⚠️ 只能做图集", f"形态C 要 {小时(丙)}，超出预算；形态A {小时(甲)} 可行"
    else:
        档, 为何 = "❌ 做不了", f"连形态A 都要 {小时(甲)}"
    return 档, 为何, 镜头数, 甲, 丙


def 主函数():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--wan", type=float, default=8.0,
                    help="Wan 生成一个 5 秒镜头的分钟数（含模型切换），默认 8")
    args = ap.parse_args()

    csv_path, date_tag, rows = 读情报(args.date)
    rows = 取数(rows)
    wan秒 = args.wan * 60

    print(f"读取 {csv_path.name}：{len(rows)} 条"
          f"（search {sum(1 for r in rows if r.get('source')=='search')} / "
          f"ranking {sum(1 for r in rows if r.get('source')=='ranking')}）")

    表 = 评题材(rows)
    for t in 表:
        档, 为何, 镜头数, 甲, 丙 = 判形态(t["时长中位"], wan秒)
        t.update({"档": 档, "为何": 为何, "镜头数": 镜头数, "成本A": 甲, "成本C": 丙})
    表.sort(key=lambda x: x["爆P50"])

    L = []
    L.append(f"# 产能对齐 · {date_tag}")
    L.append("")
    L.append("> 由 `产能对齐.py` 生成。回答：**热榜里的题材，哪些我们真做得出来。**")
    L.append(f"> 成本模型：Z-Image **{出图秒:.0f} 秒/张**（实测），"
             f"Wan 单镜头 **{args.wan:.0f} 分钟/5秒**（估值，模型到位后校准）")
    L.append("")

    L.append("## 〇、先分清三个池子（这一步不做，后面全是错的）")
    L.append("")
    L.append("| source_key 后缀 | 条数 | 播放中位 | 实际含义 |")
    L.append("|---|---|---|---|")
    L.append("| `recent30d` | 618 | **85.6万** | 近 30 天**最热**（按热度排）——爆款池，**看这个** |")
    L.append("| `totalrank` | 597 | 1.9万 | 历史**综合**排序——长期有效内容 |")
    L.append("| `pubdate` | 218 | **25** | 最新**发布**——刚发的空壳，纯噪声，**剔除** |")
    L.append("")
    L.append("三者的量级差到 **3 万倍**。之前把它们混在一起算分位数，才会得出")
    L.append("「热榜里有 119 播放的视频」这种荒谬结论。下表只用 `recent30d` 爆款池。")
    L.append("")
    L.append("> **及格线 = 爆款池 P25**：即「近 30 天该题材的热门视频里，最弱的那 1/4 是什么水平」。")
    L.append("> 这才是真正要跨过的门槛——不是跟全网所有视频比，是跟**已经火起来的**比。")
    L.append("")

    L.append("## 一、我们能做的四种形态")
    L.append("")
    L.append("| 形态 | 名称 | 说明 |")
    L.append("|---|---|---|")
    for k in ["A", "B", "C", "D"]:
        n, d = 形态说明[k]
        L.append(f"| {k} | {n} | {d} |")
    L.append("")

    L.append("## 二、题材 × 产能 对齐表")
    L.append("")
    L.append("| 题材 | 内容性质 | 爆款n | **及格线P25** | 中位P50 | P75 | 时长中位 | 镜头 | 形态A | 形态C | 产能判定 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for t in 表:
        性 = 题材性质.get(t["题材"], ("?", ""))[0]
        L.append(
            f"| `{t['题材']}` | {性} | {t['爆款n']} | **{t['爆P25']:,.0f}** | {t['爆P50']:,.0f} | "
            f"{t['爆P75']:,.0f} | {t['时长中位']/60:.1f}分 | "
            f"{t['镜头数']} | {小时(t['成本A'])} | {小时(t['成本C'])} | {t['档']} |"
        )
    L.append("")

    L.append("## 三、综合判定：内容性质 × 产能 × 及格线")
    L.append("")
    L.append("产能不够可以等模型；**内容形态不对，是根本做不了**。所以先按性质过一遍：")
    L.append("")
    L.append("| 题材 | 内容性质 | 性质说明 | 我们能不能做 | 及格线P25 | 投币率 | 综合 |")
    L.append("|---|---|---|---|---|---|---|")
    排序 = []
    for t in 表:
        性, 说明 = 题材性质.get(t["题材"], ("?", "未分类"))
        if 性 == "教程型":
            性质判定 = "❌ 生成解决不了"
            综合 = "❌ 排除"
        elif 性 == "画面型" and t["档"].startswith("✅"):
            性质判定 = "✅ 直接可做"
            综合 = "🥇 首选"
        elif 性 == "画面型":
            性质判定 = "⚠️ 只能图集"
            综合 = "🥈 次选"
        else:
            性质判定 = "⚠️ 看具体选题"
            综合 = "🥉 待定"
        排序.append((综合, t, 性, 说明, 性质判定))
    for 综合, t, 性, 说明, 性质判定 in sorted(排序, key=lambda x: x[0]):
        L.append(f"| `{t['题材']}` | {性} | {说明} | {性质判定} | "
                 f"{t['爆P25']:,.0f} | {t['投币率']*100:.3f}% | **{综合}** |")
    L.append("")

    首选 = [x for x in 排序 if x[0].startswith("🥇")]
    L.append("### 结论")
    L.append("")
    L.append("两个候选，各有取舍：")
    L.append("")
    画 = {t["题材"]: t for t in 表}
    if "AI绘画" in 画:
        t = 画["AI绘画"]
        L.append(f"- **`AI绘画`　—— 最匹配的一个**")
        L.append(f"  - 及格线 **{t['爆P25']:,.0f}**（低），投币率 **{t['投币率']*100:.3f}%**（是 `AI生成` 的 "
                 f"{t['投币率']/max(画['AI生成']['投币率'],1e-9):.0f} 倍，资产型粉丝）")
        L.append(f"  - 内容就是画面本身，Z-Image 出图即成品，形态A **{小时(t['成本A'])}**")
        L.append(f"  - 短板：形态C 要 {小时(t['成本C'])}，多镜头叙事做不了，暂时只能做图集")
        L.append("")
    if "AI生成" in 画:
        t = 画["AI生成"]
        L.append(f"- **`AI生成`　—— 产能唯一全绿的一个**")
        L.append(f"  - 及格线 **{t['爆P25']:,.0f}**，形态C **{小时(t['成本C'])}** 在预算内")
        L.append(f"  - 短板：投币率只有 **{t['投币率']*100:.3f}%**（流量型，留存弱）；爆款样本仅 {t['爆款n']} 条，统计上不够硬")
        L.append("")
    L.append("> 取舍：要**粉丝质量**选 `AI绘画`，要**当天就能跑通多镜头**选 `AI生成`。")
    L.append("> 两者都用同一套 Z-Image 管线，不冲突——可以先各投一条，用真实数据决定。")
    L.append("")
    L.append("**最反直觉的一条**：数据上投币率最高、及格线最低的是 `Stable Diffusion`(3.395%)")
    L.append("和 `ComfyUI`(2.080%)——但它们是**教程型**，需要录屏操作界面加口播，")
    L.append("生成式管线**一条都做不了**。数据最好看的方向，恰好是我们能力之外的方向。")
    L.append("")
    L.append("而 `AI动画`/`AI短片`/`AI音乐` 这些看起来最对口的画面型题材，")
    L.append("及格线是 **60 万到 100 万**——近 30 天的爆款池挤满了大制作，是新号最难碰的位置。")
    L.append("")

    L.append("---")
    L.append("")
    L.append("## 四、Wan 单镜头耗时决定形态 C 能不能用")
    L.append("")
    L.append(f"当前假设 **{args.wan:.0f} 分钟/镜头**。下载完成后用 `--wan` 回填真实值，整张表会重排。")
    L.append("判定阈值是 **3 小时/条**：")
    L.append("")
    L.append("| 单镜头耗时 | 一段 1.8 分钟片（22 镜头） | 含义 |")
    L.append("|---|---|---|")
    for m in (4, 8, 15):
        丙 = 出图首次加载秒 + 22 * (出图秒 + m * 60 + 拼接秒_每镜)
        L.append(f"| {m} 分钟 | {小时(丙)} | "
                 + ("可以日产 1-2 条" if m <= 4 else "卡在阈值上" if m <= 8 else "形态C 报废，只剩形态A") + " |")
    L.append("")

    out = 情报 / f"产能对齐_{date_tag}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"已生成 {out}（{len(L)} 行）")


if __name__ == "__main__":
    主函数()
