# -*- coding: utf-8 -*-
"""
B站选题情报抓取器 —— 每日运行，产出「热榜日报 CSV + 题材分析 MD」。

设计要点
--------
1. 只用公开接口，不登录、不使用任何 cookie / 账号凭据。
2. 所有请求经过统一限速器（默认最小间隔 1.2s + 抖动），遇风控自动降速。
3. 任何单个接口失败都不会中断整个脚本：失败被记录进 failures，最后写入日志与报告。
4. 抓取结果原样落盘 raw_YYYYMMDD.json，分析脚本可离线重跑，不必重新抓。

用法
----
    python 抓热榜.py                # 抓取 + 分析 + 落盘
    python 抓热榜.py --no-enrich    # 跳过逐条视频详情补全（更快、更省风控额度）
    python 抓热榜.py --pages 1      # 每个关键词只抓 1 页搜索
    python 抓热榜.py --analyze-only # 不抓取，用已有 raw JSON 重新生成报告
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import re
import shutil
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# --------------------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent          # D:\DSHworkspace\B站
OUT_DIR = BASE / "情报"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------
# 抓取目标配置
# --------------------------------------------------------------------------------------
ZONES = [
    # (RankType 名, 中文名)   —— 排行榜分类
    ("All", "全区"),
    ("Rookie", "新人榜"),
    ("Douga", "动画"),
    ("Kichiku", "鬼畜"),
    ("Life", "生活"),
    ("Knowledge", "知识"),
    ("Technology", "科技"),
    ("Cinephile", "影视"),
    ("Ent", "娱乐"),
    ("Music", "音乐"),
    ("Game", "游戏"),
]

KEYWORDS = [
    "AI动画",
    "AI短片",
    "AI视频",
    "AI绘画",
    "AI音乐",
    "AI电影",
    "Stable Diffusion",
    "ComfyUI",
    "AI漫剧",
    "AI生成",
]

RECENT_DAYS = 30            # 「近期」窗口，用于缝隙分析
DEFAULT_MIN_INTERVAL = 1.2  # 请求最小间隔（秒）
MAX_INTERVAL = 8.0          # 风控降速上限

HTML_TAG = re.compile(r"<[^>]+>")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    return HTML_TAG.sub("", str(s)).replace("&quot;", '"').replace("&amp;", "&").strip()


# --------------------------------------------------------------------------------------
# HTTP 后端：curl_cffi（带浏览器 TLS 指纹，抗风控最好）→ httpx 兜底
# --------------------------------------------------------------------------------------
def prepare_http_backend() -> tuple[object, str, str]:
    """
    返回 (bilibili_api 模块, client_name, 说明)

    Windows 上 venv 路径含中文（D:\\DSHworkspace\\B站\\...），libcurl 无法从非 ASCII 路径
    加载 CA 文件（curl error 77），因此先把 certifi 的 cacert.pem 复制到纯 ASCII 路径。
    """
    import certifi

    note = ""
    ca_ok = None
    for ca in (
        Path(r"C:\Windows\Temp\dsh_bili_cacert.pem"),
        Path(r"C:\ProgramData\dsh_bili_cacert.pem"),
        Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "dsh_bili_cacert.pem",
        OUT_DIR / "dsh_bili_cacert.pem",
    ):
        try:
            ca.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(certifi.where(), ca)
            os.environ["CURL_CA_BUNDLE"] = str(ca)
            os.environ["SSL_CERT_FILE"] = str(ca)
            ca_ok = ca
            break
        except Exception:
            continue

    import bilibili_api

    if ca_ok is None:
        note = "CA 文件未能复制到 ASCII 路径，跳过 curl_cffi"

    if ca_ok is not None:
        try:
            bilibili_api.select_client("curl_cffi")
            return bilibili_api, "curl_cffi", f"CA 已置于 {ca_ok}"
        except Exception as e:                                  # pragma: no cover
            note = f"curl_cffi 不可用：{e}"

    bilibili_api.select_client("httpx")
    return bilibili_api, "httpx", note or "已回退到 httpx"


# --------------------------------------------------------------------------------------
# 限速 + 容错调用
# --------------------------------------------------------------------------------------
class CircuitBreak(Exception):
    """连续失败过多，主动放弃当前阶段（避免硬刚风控）。"""


class Fetcher:
    def __init__(self, min_interval: float = DEFAULT_MIN_INTERVAL):
        self.min_interval = min_interval
        self.cur_interval = min_interval
        self._last = 0.0
        self.failures: list[dict] = []
        self.ok_count = 0
        self.consecutive_errors = 0
        self.throttle_events = 0

    # ---- 限速 ----
    async def _pace(self) -> None:
        gap = time.monotonic() - self._last
        wait = self.cur_interval - gap + random.uniform(0, 0.35)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last = time.monotonic()

    def _slow_down(self, reason: str) -> None:
        self.throttle_events += 1
        self.cur_interval = min(MAX_INTERVAL, self.cur_interval * 1.6)
        log(f"  ! 触发降速 -> {self.cur_interval:.1f}s（{reason}）")

    def _speed_up(self) -> None:
        if self.cur_interval > self.min_interval:
            self.cur_interval = max(self.min_interval, self.cur_interval * 0.92)

    @staticmethod
    def _classify(err: Exception) -> str:
        s = str(err)
        code = getattr(err, "code", None)
        if "412" in s:
            return "HTTP 412 风控（安全策略拒绝）"
        if code == -352 or "-352" in s:
            return "-352 风控校验失败"
        if "-799" in s:
            return "-799 请求过于频繁"
        if "-509" in s:
            return "-509 请求过于频繁"
        if "SSLError" in type(err).__name__ or "curl" in s.lower() and "SSL" in s:
            return "SSL 证书加载失败"
        if isinstance(err, asyncio.TimeoutError):
            return "请求超时"
        return f"{type(err).__name__}: {str(err)[:160]}"

    async def call(self, label: str, factory, retries: int = 2, critical: bool = False):
        """
        factory: 无参可等待函数工厂（每次重试重新构造协程）
        失败返回 None，并记录进 self.failures。
        """
        for attempt in range(retries + 1):
            await self._pace()
            try:
                res = await factory()
                self.ok_count += 1
                self.consecutive_errors = 0
                self._speed_up()
                return res
            except Exception as e:
                reason = self._classify(e)
                if attempt < retries:
                    if any(k in reason for k in ("风控", "频繁", "412", "-352")):
                        self._slow_down(reason)
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                self.consecutive_errors += 1
                self.failures.append({"target": label, "reason": reason})
                log(f"  x {label} 失败：{reason}")
                if not critical and self.consecutive_errors >= 6:
                    raise CircuitBreak(f"连续 {self.consecutive_errors} 次失败，中止当前阶段")
                return None
        return None


# --------------------------------------------------------------------------------------
# 归一化
# --------------------------------------------------------------------------------------
def norm_rank_item(it: dict, zone_key: str, zone_cn: str, idx: int) -> dict | None:
    stat = it.get("stat") or {}
    owner = it.get("owner") or {}
    if not it.get("bvid"):
        return None
    return {
        "source": "ranking",
        "source_key": f"ranking:{zone_cn}",
        "zone_cn": zone_cn,
        "rank_index": idx,
        "bvid": it.get("bvid", ""),
        "aid": it.get("aid", ""),
        "title": strip_html(it.get("title")),
        "up_name": strip_html(owner.get("name")),
        "up_mid": owner.get("mid", ""),
        "view": stat.get("view", 0) or 0,
        "like": stat.get("like", 0) or 0,
        "coin": stat.get("coin", 0) or 0,
        "favorite": stat.get("favorite", 0) or 0,
        "danmaku": stat.get("danmaku", 0) or 0,
        "reply": stat.get("reply", 0) or 0,
        "share": stat.get("share", 0) or 0,
        "pubdate": it.get("pubdate", 0) or 0,
        "duration_sec": int(it.get("duration", 0) or 0),
        "tid": it.get("tid", ""),
        "tname": it.get("tname", ""),
        "tname_v2": it.get("tnamev2", ""),
        "keyword": "",
        "order": "",
        "tag": "",
        "desc": strip_html(it.get("desc", ""))[:200],
        "enriched": 0,
        "coin_source": "ranking",
        "up_followers": "",
    }


def parse_duration_str(s) -> int:
    """搜索接口返回 '4:59' / '1:02:33' / 数字（秒）"""
    if isinstance(s, (int, float)):
        return int(s)
    if not s:
        return 0
    parts = str(s).strip().split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return 0
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def norm_search_item(it: dict, keyword: str, order: str) -> dict | None:
    if not it.get("bvid"):
        return None
    play = it.get("play")
    if isinstance(play, str):
        play = int(play) if play.isdigit() else 0
    return {
        "source": "search",
        "source_key": f"search:{keyword}:{order}",
        "zone_cn": "",
        "rank_index": it.get("rank_index", ""),
        "bvid": it.get("bvid", ""),
        "aid": it.get("aid", ""),
        "title": strip_html(it.get("title")),
        "up_name": strip_html(it.get("author")),
        "up_mid": it.get("mid", ""),
        "view": play or 0,
        "like": it.get("like", 0) or 0,
        "coin": "",                       # 搜索接口不返回投币，需 enrichment 补全
        "favorite": it.get("favorites", 0) or 0,
        "danmaku": it.get("danmaku", 0) or 0,
        "reply": it.get("review", 0) or 0,
        "share": "",
        "pubdate": it.get("pubdate", 0) or 0,
        "duration_sec": parse_duration_str(it.get("duration")),
        "tid": it.get("typeid", ""),
        "tname": it.get("typename", ""),
        "tname_v2": "",
        "keyword": keyword,
        "order": order,
        "tag": strip_html(it.get("tag", ""))[:200],
        "desc": strip_html(it.get("description", ""))[:200],
        "enriched": 0,
        "coin_source": "",
        "up_followers": "",
    }


# --------------------------------------------------------------------------------------
# 主抓取流程
# --------------------------------------------------------------------------------------
async def collect(args) -> dict:
    bapi, client_name, note = prepare_http_backend()
    from bilibili_api import rank, search, video, user
    from bilibili_api.rank import RankType, RankDayType
    from bilibili_api.search import SearchObjectType, OrderVideo

    log(f"HTTP 后端：{client_name}（{note}）")
    f = Fetcher(min_interval=args.interval)

    # ---- 0. 冒烟测试（后端可用性） ----
    smoke = await f.call("smoke: rank.All",
                         lambda: rank.get_rank(RankType.All, RankDayType.THREE_DAY),
                         retries=1, critical=True)
    if smoke is None:
        # curl_cffi 可能因 CA 问题整体不可用 -> 换 httpx 再试一次
        log("冒烟测试失败，尝试切换 httpx 后端…")
        bapi.select_client("httpx")
        client_name += " -> httpx(兜底)"
        smoke = await f.call("smoke: rank.All(httpx)",
                             lambda: rank.get_rank(RankType.All, RankDayType.THREE_DAY),
                             retries=1, critical=True)
        if smoke is None:
            raise SystemExit("两种 HTTP 后端都不可用，请检查网络/代理。")

    rows: dict[str, dict] = {}      # bvid -> row（去重）
    meta: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "client": client_name,
        "client_note": note,
        "windows": {},
        "keyword_meta": {},
        "zone_counts": {},
        "enrich": {},
    }

    def add(row: dict | None, overwrite_blank: bool = True) -> None:
        """合并同一 bvid 的多来源记录：保留已有非空字段，补全空字段。"""
        if not row:
            return
        bv = row["bvid"]
        if bv not in rows:
            rows[bv] = row
            return
        cur = rows[bv]
        for k, v in row.items():
            if v in ("", None, 0) and k not in ("view", "like"):
                continue
            if cur.get(k) in ("", None, 0) or k in ("view", "like", "favorite", "danmaku", "reply"):
                # 播放/点赞等取较大值（不同接口口径略有差异）
                if k in ("view", "like", "favorite", "danmaku", "reply", "share") and isinstance(v, int) and isinstance(cur.get(k), int):
                    cur[k] = max(cur[k], v)
                elif cur.get(k) in ("", None, 0):
                    cur[k] = v
        # 记录该 bvid 出现在哪些来源
        cur.setdefault("sources", set())
        if isinstance(cur.get("sources"), set):
            cur["sources"].add(row["source_key"])

    # ---- 1. 排行榜 ----
    log("=== 1/5 抓取排行榜 ===")
    for zkey, zcn in ZONES:
        if not hasattr(RankType, zkey):
            f.failures.append({"target": f"ranking:{zcn}", "reason": f"库中无 RankType.{zkey}"})
            continue
        try:
            res = await f.call(
                f"ranking:{zcn}",
                lambda zk=zkey: rank.get_rank(getattr(RankType, zk), RankDayType.THREE_DAY),
                critical=False,
            )
        except CircuitBreak as e:
            log(f"  ! 排行榜阶段中止：{e}")
            break
        if not res:
            continue
        lst = res.get("list") or []
        cnt = 0
        for i, it in enumerate(lst, 1):
            r = norm_rank_item(it, zkey, zcn, i)
            if r:
                add(r)
                cnt += 1
        meta["zone_counts"][zcn] = cnt
        log(f"  排行榜 {zcn}: {cnt} 条")

    # ---- 2. 关键词搜索（综合排序） ----
    kw_meta: dict[str, dict] = {}
    log("=== 2/5 抓取关键词搜索（综合排序）===")
    for kw in KEYWORDS:
        for page in range(1, args.pages + 1):
            try:
                res = await f.call(
                    f"search:{kw}:p{page}",
                    lambda k=kw, p=page: search.search_by_type(
                        k, search_type=SearchObjectType.VIDEO,
                        order_type=OrderVideo.TOTALRANK, page=p),
                )
            except CircuitBreak as e:
                log(f"  ! 搜索阶段中止：{e}")
                res = None
                break
            if not res:
                continue
            if page == 1:
                kw_meta.setdefault(kw, {})["numResults"] = res.get("numResults", 0)
                kw_meta[kw]["numPages"] = res.get("numPages", 0)
            results = res.get("result") or []
            for it in results:
                add(norm_search_item(it, kw, "totalrank"))
            log(f"  搜索 {kw} p{page}: {len(results)} 条")

    # ---- 3. 关键词搜索（近 N 天窗口，用于缝隙分析） ----
    today = datetime.now()
    start_s = (today - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    end_s = today.strftime("%Y-%m-%d")
    meta["windows"] = {"recent_days": RECENT_DAYS, "start": start_s, "end": end_s}
    log(f"=== 3/5 抓取关键词近期窗口 {start_s} ~ {end_s} ===")
    recent_rows: list[dict] = []
    for kw in KEYWORDS:
        got = 0
        for page in range(1, args.recent_pages + 1):
            try:
                res = await f.call(
                    f"search_recent:{kw}:p{page}",
                    lambda k=kw, p=page: search.search_by_type(
                        k, search_type=SearchObjectType.VIDEO,
                        order_type=OrderVideo.CLICK,
                        time_start=start_s, time_end=end_s, page=p),
                )
            except CircuitBreak as e:
                log(f"  ! 近期窗口阶段中止：{e}")
                res = None
                break
            if not res:
                continue
            if page == 1:
                kw_meta.setdefault(kw, {})["recent_numResults"] = res.get("numResults", 0)
            for it in (res.get("result") or []):
                r = norm_search_item(it, kw, f"recent{RECENT_DAYS}d")
                if r:
                    recent_rows.append(r)
                    add(r)
                    got += 1
        kw_meta.setdefault(kw, {})["recent_sampled"] = got
        log(f"  近期窗口 {kw}: {got} 条")
    meta["keyword_meta"] = kw_meta
    meta["recent_bvids"] = sorted({r["bvid"] for r in recent_rows})

    # ---- 4. 关键词搜索（按发布时间最新） ----
    log("=== 4/5 抓取关键词最新投稿 ===")
    for kw in KEYWORDS:
        try:
            res = await f.call(
                f"search_new:{kw}",
                lambda k=kw: search.search_by_type(
                    k, search_type=SearchObjectType.VIDEO,
                    order_type=OrderVideo.PUBDATE, page=1),
            )
        except CircuitBreak as e:
            log(f"  ! 最新投稿阶段中止：{e}")
            break
        if not res:
            continue
        n = 0
        for it in (res.get("result") or []):
            r = norm_search_item(it, kw, "pubdate")
            if r:
                add(r)
                n += 1
        log(f"  最新 {kw}: {n} 条")

    # ---- 5. 详情补全（投币 / 分享 / 精确时长 + UP 主粉丝数） ----
    # 搜索接口不返回投币数，只有 ranking / view 详情接口有。这里对「最有分析价值」的
    # 子集做补全，控制请求量以避开风控。
    enrich_stat = {"videos_requested": 0, "videos_ok": 0, "users_requested": 0, "users_ok": 0,
                   "aborted": False}
    if not args.no_enrich:
        log("=== 5/5 详情补全（投币/分享/粉丝数）===")
        # 候选池：每个关键词综合搜索播放 TOP N + 近期窗口播放 TOP M
        pool: list[str] = []
        seen = set()

        def take(rs, n, key=lambda r: r["view"]):
            c = 0
            for r in sorted(rs, key=key, reverse=True):
                if c >= n:
                    break
                if r["bvid"] not in seen:
                    seen.add(r["bvid"])
                    pool.append(r["bvid"])
                    c += 1

        for kw in KEYWORDS:
            take([r for r in rows.values() if r.get("keyword") == kw and r.get("order") == "totalrank"],
                 args.enrich_top)
            take([r for r in recent_rows if r.get("keyword") == kw], args.enrich_recent)
        log(f"  待补全视频：{len(pool)} 条")
        enrich_stat["videos_requested"] = len(pool)

        try:
            for bv in pool:
                info = await f.call(f"video:{bv}", lambda b=bv: video.Video(bvid=b).get_info())
                if not info:
                    continue
                st = info.get("stat") or {}
                own = info.get("owner") or {}
                cur = rows.get(bv)
                if cur is None:
                    continue
                cur["coin"] = st.get("coin", 0) or 0
                cur["coin_source"] = "view_detail"
                cur["share"] = st.get("share", 0) or 0
                cur["like"] = max(int(cur.get("like") or 0), st.get("like", 0) or 0)
                cur["favorite"] = max(int(cur.get("favorite") or 0), st.get("favorite", 0) or 0)
                cur["danmaku"] = max(int(cur.get("danmaku") or 0), st.get("danmaku", 0) or 0)
                cur["reply"] = max(int(cur.get("reply") or 0), st.get("reply", 0) or 0)
                if st.get("view"):
                    cur["view"] = max(int(cur.get("view") or 0), st["view"])
                if info.get("duration"):
                    cur["duration_sec"] = int(info["duration"])
                if not cur.get("tname"):
                    cur["tname"] = info.get("tname", "")
                if not cur.get("tname_v2"):
                    cur["tname_v2"] = info.get("tname_v2", "")
                if not cur.get("up_mid"):
                    cur["up_mid"] = own.get("mid", "")
                cur["enriched"] = 1
                enrich_stat["videos_ok"] += 1
        except CircuitBreak as e:
            log(f"  ! 详情补全中止：{e}")
            enrich_stat["aborted"] = True

        # UP 粉丝数（用于判断「新号能不能挤进去」）
        mids: list = []
        seen_m = set()
        for r in sorted(rows.values(), key=lambda x: int(x.get("view") or 0), reverse=True):
            m = r.get("up_mid")
            if m and str(m) not in seen_m:
                seen_m.add(str(m))
                mids.append(m)
            if len(mids) >= args.enrich_users:
                break
        enrich_stat["users_requested"] = len(mids)
        log(f"  待补全 UP 主：{len(mids)} 位")
        try:
            for mid in mids:
                rel = await f.call(f"user:{mid}", lambda m=mid: user.User(uid=m).get_relation_info())
                if not rel:
                    continue
                enrich_stat["users_ok"] += 1
                for r in rows.values():
                    if str(r.get("up_mid")) == str(mid):
                        r["up_followers"] = rel.get("follower", "")
        except CircuitBreak as e:
            log(f"  ! UP 主补全中止：{e}")
            enrich_stat["aborted"] = True
    else:
        log("=== 5/5 跳过详情补全（--no-enrich）===")

    meta["enrich"] = enrich_stat

    # ---- 对标 UP 主近期投稿（space 接口，实测 412 风控，做优雅降级） ----
    competitor_note = ""
    try:
        top_ups = []
        seen_m = set()
        for r in sorted(rows.values(), key=lambda x: int(x.get("view") or 0), reverse=True):
            m = r.get("up_mid")
            if m and str(m) not in seen_m:
                seen_m.add(str(m))
                top_ups.append(m)
            if len(top_ups) >= 3:
                break
        if top_ups:
            probe = await f.call(f"user_videos:{top_ups[0]}",
                                 lambda m=top_ups[0]: user.User(uid=m).get_videos(ps=5),
                                 retries=1)
            if probe:
                vl = (probe.get("list") or {}).get("vlist") or []
                n = 0
                for it in vl:
                    r = norm_rank_item(it, "", f"UP:{it.get('author')}", 0)
                    if r:
                        r["source"] = "up_space"
                        r["source_key"] = f"up_space:{it.get('author')}"
                        add(r)
                        n += 1
                competitor_note = f"UP 主空间接口可用，抓到 {n} 条近期投稿"
            else:
                competitor_note = "UP 主空间接口不可用（x/space/wbi/arc/search 返回 412 风控），已跳过"
    except Exception as e:
        competitor_note = f"UP 主空间接口异常，已跳过：{e}"
    meta["competitor_note"] = competitor_note
    log(f"  对标UP主：{competitor_note}")

    # ---- 收尾 ----
    for r in rows.values():
        r.pop("sources", None)
    all_rows = list(rows.values())
    meta["total_rows"] = len(all_rows)
    meta["ok_requests"] = f.ok_count
    meta["failures"] = f.failures
    meta["throttle_events"] = f.throttle_events
    meta["final_interval"] = round(f.cur_interval, 2)
    log(f"抓取完成：成功请求 {f.ok_count}，失败 {len(f.failures)}，去重后 {len(all_rows)} 条视频")
    return {"rows": all_rows, "meta": meta}


# --------------------------------------------------------------------------------------
# 落盘
# --------------------------------------------------------------------------------------
CSV_FIELDS = [
    "bvid", "title", "up_name", "up_mid", "up_followers",
    "view", "like", "coin", "favorite", "danmaku", "reply", "share",
    "coin_play_ratio", "like_play_ratio",
    "pubdate", "pub_date", "duration_sec", "duration_str",
    "zone_cn", "tname", "tname_v2", "tid",
    "source", "source_key", "keyword", "order", "rank_index",
    "enriched", "coin_source", "tag", "desc",
]


def fmt_dur(sec) -> str:
    try:
        sec = int(sec or 0)
    except Exception:
        return ""
    if sec <= 0:
        return ""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def ratio(a, b) -> str:
    try:
        a = float(a)
        b = float(b)
        if b <= 0:
            return ""
        return f"{a / b:.4f}"
    except Exception:
        return ""


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: -int(x.get("view") or 0)):
            rr = dict(r)
            rr["pub_date"] = (datetime.fromtimestamp(r["pubdate"]).strftime("%Y-%m-%d %H:%M")
                              if r.get("pubdate") else "")
            rr["duration_str"] = fmt_dur(r.get("duration_sec"))
            rr["coin_play_ratio"] = ratio(r.get("coin"), r.get("view"))
            rr["like_play_ratio"] = ratio(r.get("like"), r.get("view"))
            w.writerow(rr)


def main() -> int:
    ap = argparse.ArgumentParser(description="B站选题情报抓取器")
    ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="报告日期标签，默认今天")
    ap.add_argument("--pages", type=int, default=2, help="每个关键词综合搜索抓几页（每页 42 条）")
    ap.add_argument("--recent-pages", type=int, default=2, help="近期窗口每个关键词抓几页")
    ap.add_argument("--enrich-top", type=int, default=12, help="每个关键词补全播放 TOP N 的详情")
    ap.add_argument("--enrich-recent", type=int, default=6, help="每个关键词近 N 天窗口补全播放 TOP N")
    ap.add_argument("--enrich-users", type=int, default=50, help="补全粉丝数的 UP 主数量上限")
    ap.add_argument("--interval", type=float, default=DEFAULT_MIN_INTERVAL, help="请求最小间隔（秒）")
    ap.add_argument("--no-enrich", action="store_true", help="跳过详情补全")
    ap.add_argument("--analyze-only", action="store_true", help="不抓取，直接用已有 raw JSON 生成报告")
    args = ap.parse_args()

    date_tag = args.date
    raw_path = OUT_DIR / f"raw_{date_tag}.json"

    if args.analyze_only:
        if not raw_path.exists():
            log(f"找不到 {raw_path}")
            return 2
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        t0 = time.time()
        try:
            payload = asyncio.run(collect(args))
        except SystemExit as e:
            log(str(e))
            return 3
        log(f"抓取耗时 {time.time() - t0:.1f}s")
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"原始数据 -> {raw_path}")

    rows, meta = payload["rows"], payload["meta"]
    csv_path = OUT_DIR / f"热榜日报_{date_tag}.csv"
    write_csv(rows, csv_path)
    log(f"CSV -> {csv_path}（{len(rows)} 行）")

    # 调用分析模块
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("analysis", BASE / "分析.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        md_path = mod.build_report(rows, meta, date_tag)
        log(f"分析报告 -> {md_path}")
    except Exception:
        log("分析阶段异常：\n" + traceback.format_exc())
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
