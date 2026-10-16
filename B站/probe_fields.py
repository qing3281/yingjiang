# -*- coding: utf-8 -*-
"""探针3：字段结构与各分区/搜索接口连通性。"""
import asyncio, json, os, shutil, sys

import certifi
ascii_ca = r"C:\Windows\Temp\dsh_cacert.pem"
os.makedirs(os.path.dirname(ascii_ca), exist_ok=True)
shutil.copyfile(certifi.where(), ascii_ca)
os.environ["CURL_CA_BUNDLE"] = ascii_ca

import bilibili_api
bilibili_api.select_client("curl_cffi")

from bilibili_api import rank, search
from bilibili_api.rank import RankType, RankDayType
from bilibili_api.search import SearchObjectType, OrderVideo


def dump_sample(label, item, n=3000):
    print(f"--- {label} sample fields ---")
    print(json.dumps(item, ensure_ascii=False, default=str)[:n])


async def safe(label, coro):
    try:
        r = await coro
        print(f"[OK]   {label}")
        return r
    except Exception as e:
        print(f"[FAIL] {label} :: {type(e).__name__} code={getattr(e,'code',None)} msg={getattr(e,'msg',None)} {e}")
        return None


async def main():
    # 1) 排行榜字段结构
    r = await safe("rank.All", rank.get_rank(RankType.All, RankDayType.THREE_DAY))
    if r and r.get("list"):
        dump_sample("rank item", r["list"][0])
    await asyncio.sleep(1.2)

    # 2) 各分区排行榜
    zones = ["Douga", "Kichiku", "Life", "Knowledge", "Technology", "Cinephile", "Ent", "Music", "Game", "Rookie"]
    zone_stat = {}
    for z in zones:
        rt = getattr(RankType, z)
        res = await safe(f"rank.{z}", rank.get_rank(rt, RankDayType.THREE_DAY))
        zone_stat[z] = len(res.get("list", [])) if res else 0
        await asyncio.sleep(1.2)

    # 3) 搜索字段结构
    s = await safe("search.AI动画", search.search_by_type(
        "AI动画", search_type=SearchObjectType.VIDEO, order_type=OrderVideo.TOTALRANK, page=1))
    if s:
        print("search keys:", list(s.keys()))
        rs = s.get("result") or []
        print("search result len:", len(rs))
        if rs:
            dump_sample("search item", rs[0])
    await asyncio.sleep(1.2)

    # 4) 多个关键词搜索是否通
    kws = ["AI短片", "AI视频", "AI绘画", "AI音乐", "AI电影", "Stable Diffusion", "ComfyUI", "AI生成"]
    ok_kw = []
    for k in kws:
        res = await safe(f"search.{k}", search.search_by_type(
            k, search_type=SearchObjectType.VIDEO, order_type=OrderVideo.TOTALRANK, page=1))
        if res:
            ok_kw.append((k, len(res.get("result") or [])))
        await asyncio.sleep(1.2)

    print("\n=== ZONE COUNTS ===")
    print(json.dumps(zone_stat, ensure_ascii=False))
    print("=== KEYWORD COUNTS ===")
    print(json.dumps(ok_kw, ensure_ascii=False))


asyncio.run(main())
