# -*- coding: utf-8 -*-
"""把番茄公开接口能拿到的书全部抓下来，存成剧本池。

背景：`https://fanqienovel.com/api/rank/list` 是个**降级接口**——
  · 参数是 `type`，不是 `rank_id`（`rank_id` 传什么都返回同一份榜单）
  · `type` 只认 1 和 2，3 以上返回「榜单类型错误」
  · `category_id` / `gender` / `rank_type` 全部无效
  · `offset` 无效，翻页返回同一页
  → 全网可得的唯一去重池只有 19 本

结论：**靠公开接口拿不到「有意思的剧本」**，只能拿到 19 本战神/女婿爽文的简介。
这个脚本的用途是留个底：万一以后接口修好了，直接重跑就能拿到大池子。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"}
输出目录 = r"D:\DSHworkspace\B站\素材"


def 拉榜单(类型, 偏移=0, 条数=20):
    u = "https://fanqienovel.com/api/rank/list?" + urllib.parse.urlencode(
        {"type": 类型, "offset": 偏移, "count": 条数}
    )
    d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20).read())
    return (d.get("data") or {}).get("list") or []


def main():
    print("=" * 60)
    print("抓番茄公开榜单")
    print("=" * 60)
    全部 = {}
    for 类型, 名 in [(1, "榜单一"), (2, "榜单二")]:
        本页 = 拉榜单(类型)
        print(f"  type={类型}（{名}）  {len(本页)} 本")
        for b in 本页:
            bid = b.get("bookId") or b.get("bookName")
            if bid not in 全部:
                全部[bid] = {
                    "书名": b.get("bookName", ""),
                    "作者": b.get("author", ""),
                    "简介": b.get("abstract", ""),
                    "来源榜单": f"type={类型}",
                    "长度": len(b.get("abstract", "")),
                }
        time.sleep(0.6)

    条 = list(全部.values())
    # 按简介长度排，长简介信息量大
    条.sort(key=lambda x: -x["长度"])

    os.makedirs(输出目录, exist_ok=True)
    今天 = datetime.now().strftime("%Y%m%d")
    路径 = os.path.join(输出目录, f"剧本池_{今天}.json")
    with open(路径, "w", encoding="utf-8") as f:
        json.dump({"抓取时间": datetime.now().isoformat(timespec="seconds"), "条数": len(条), "书": 条},
                  f, ensure_ascii=False, indent=2)

    print(f"\n✅ 去重后 {len(条)} 本 → {路径}")
    print(f"\n   最长简介 {条[0]['长度']} 字：")
    print(f"   《{条[0]['书名']}》")
    print(f"   {条[0]['简介'][:180]}…")
    print("\n   ⚠ 全部是都市/战神/女婿类网文，做文艺向 AI 短剧不合适")
    return 0


if __name__ == "__main__":
    sys.exit(main())
