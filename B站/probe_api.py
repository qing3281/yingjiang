# -*- coding: utf-8 -*-
"""接口连通性探针：逐个测试，记录成功/失败与返回码，不因单点失败中断。"""
import asyncio, json, sys, traceback

from bilibili_api import rank, search
from bilibili_api.rank import RankType, RankDayType
from bilibili_api.search import SearchObjectType, OrderVideo


def brief(obj, n=200):
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s[:n]


async def probe(name, coro):
    try:
        r = await coro
        print(f"[OK]   {name} -> {brief(r)}")
        return ("ok", name, r)
    except Exception as e:
        code = getattr(e, "code", None)
        msg = getattr(e, "msg", None)
        print(f"[FAIL] {name} -> {type(e).__name__} code={code} msg={msg} raw={e}")
        return ("fail", name, str(e))


async def main():
    tests = []

    # 1. 全区排行榜
    async def t_all():
        return await rank.get_rank(RankType.All, RankDayType.THREE_DAY)
    tests.append(("rank.All", t_all()))

    # 2. 舞蹈区（动画/鬼畜等 rid 分区用 get_rank 的 rank_type 参数）
    async def t_douga():
        return await rank.get_rank(RankType.Douga, RankDayType.THREE_DAY)
    tests.append(("rank.Douga(动画)", t_douga()))

    # 3. 关键词搜索
    async def t_search():
        return await search.search_by_type(
            "AI动画",
            search_type=SearchObjectType.VIDEO,
            order_type=OrderVideo.TOTALRANK,
            page=1,
        )
    tests.append(("search.AI动画", t_search()))

    results = []
    for name, coro in tests:
        results.append(await probe(name, coro))
        await asyncio.sleep(1.5)  # 请求间隔 >= 1s

    print("\n=== SUMMARY ===")
    for st, name, _ in results:
        print(st, name)


asyncio.run(main())
