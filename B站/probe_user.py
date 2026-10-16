# -*- coding: utf-8 -*-
"""探针4：时间窗搜索 / 视频详情补全 / UP 主数据。"""
import asyncio, json, os, shutil
from datetime import datetime, timedelta

import certifi
ascii_ca = r"C:\Windows\Temp\dsh_cacert.pem"
os.makedirs(os.path.dirname(ascii_ca), exist_ok=True)
shutil.copyfile(certifi.where(), ascii_ca)
os.environ["CURL_CA_BUNDLE"] = ascii_ca

import bilibili_api
bilibili_api.select_client("curl_cffi")
from bilibili_api import search, video, user
from bilibili_api.search import SearchObjectType, OrderVideo


async def safe(label, coro):
    try:
        r = await coro
        print(f"[OK]   {label}")
        return r
    except Exception as e:
        print(f"[FAIL] {label} :: {type(e).__name__} code={getattr(e,'code',None)} msg={getattr(e,'msg',None)} {e}")
        return None


async def main():
    today = datetime.now()
    start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    print("window:", start, "->", end)

    s = await safe("search window", search.search_by_type(
        "AI动画", search_type=SearchObjectType.VIDEO, order_type=OrderVideo.CLICK,
        time_start=start, time_end=end, page=1))
    if s:
        print("numResults:", s.get("numResults"), "numPages:", s.get("numPages"), "len:", len(s.get("result") or []))
        for it in (s.get("result") or [])[:3]:
            print("  ", it.get("bvid"), it.get("play"), it.get("pubdate"), it.get("title", "")[:40])
    await asyncio.sleep(1.3)

    # 视频详情（含投币）
    if s and s.get("result"):
        bv = s["result"][0]["bvid"]
        v = await safe(f"video.get_info {bv}", video.Video(bvid=bv).get_info())
        if v:
            print("  detail keys:", list(v.keys()))
            print("  stat:", json.dumps(v.get("stat"), ensure_ascii=False))
            print("  owner:", json.dumps(v.get("owner"), ensure_ascii=False))
            print("  duration:", v.get("duration"), "tname:", v.get("tname"), "pubdate:", v.get("pubdate"))
        await asyncio.sleep(1.3)
        mid = s["result"][0].get("mid")
        if mid:
            u = await safe(f"user.get_relation_info {mid}", user.User(uid=mid).get_relation_info())
            if u:
                print("  relation:", json.dumps(u, ensure_ascii=False)[:400])
            await asyncio.sleep(1.3)
            uv = await safe(f"user.get_videos {mid}", user.User(uid=mid).get_videos(ps=5))
            if uv:
                vl = (uv.get("list") or {}).get("vlist") or []
                print("  user videos:", len(vl))
                if vl:
                    print("  sample:", json.dumps(vl[0], ensure_ascii=False)[:600])
            await asyncio.sleep(1.3)


asyncio.run(main())
