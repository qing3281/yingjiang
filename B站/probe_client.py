# -*- coding: utf-8 -*-
"""探针2：分别测试 httpx / curl_cffi 客户端哪个可用。"""
import asyncio, os, shutil, sys

print("cwd:", os.getcwd())

# 先把 cacert.pem 复制到纯 ASCII 路径，规避 curl 在非 ASCII 路径下加载 CA 失败的问题
import certifi
ascii_ca = r"C:\Windows\Temp\dsh_cacert.pem"
try:
    os.makedirs(os.path.dirname(ascii_ca), exist_ok=True)
    shutil.copyfile(certifi.where(), ascii_ca)
    print("copied CA to", ascii_ca, os.path.getsize(ascii_ca))
except Exception as e:
    print("CA copy failed:", e)

import bilibili_api
from bilibili_api import rank
from bilibili_api.rank import RankType, RankDayType


async def try_client(name, env_ca=None):
    if env_ca:
        os.environ["CURL_CA_BUNDLE"] = env_ca
    try:
        bilibili_api.select_client(name)
    except Exception as e:
        print(f"[{name}] select failed: {e}")
        return False
    try:
        r = await rank.get_rank(RankType.All, RankDayType.THREE_DAY)
        n = len(r.get("list", []))
        print(f"[OK] [{name}] rank.All list_len={n} keys={list(r.keys())}")
        if n:
            it = r["list"][0]
            print(f"     sample: bvid={it.get('bvid')} title={it.get('title')!r} play={it.get('stat',{}).get('view')}")
        return True
    except Exception as e:
        print(f"[FAIL] [{name}] {type(e).__name__}: {e}")
        return False


async def main():
    print("=== try curl_cffi with ascii CA ===")
    ok1 = await try_client("curl_cffi", ascii_ca)
    await asyncio.sleep(1.5)
    print("=== try httpx ===")
    ok2 = await try_client("httpx")
    await asyncio.sleep(1.5)
    print("=== try aiohttp ===")
    ok3 = False
    try:
        import aiohttp  # noqa
        ok3 = await try_client("aiohttp")
    except ModuleNotFoundError:
        print("[SKIP] aiohttp not installed")
    print(f"\nSUMMARY curl_cffi={ok1} httpx={ok2} aiohttp={ok3}")


asyncio.run(main())
