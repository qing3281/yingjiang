# -*- coding: utf-8 -*-
"""
取BGM —— 从 ccmixter 抓 CC 授权音乐，建本地曲库（含署名信息）

ccmixter 的直链需要带 Referer，不带会 403。

用法：
  python 取BGM.py --数量 6                    # 默认抓 instrumental
  python 取BGM.py --风格 "ambient cinematic" --数量 8
  python 取BGM.py --列出                      # 只看本地曲库

曲库落在 D:\\DSHworkspace\\B站\\素材\\BGM\\，署名.json 记录每首的作者/协议/来源，
投稿时要把对应署名写进简介（CC-BY 强制要求）。
"""
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = r"D:\DSHworkspace\B站\素材\BGM"
API = "https://ccmixter.org/api/query"
头部 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://ccmixter.org/",
}
署名文件 = os.path.join(ROOT, "署名.json")


def 查(参数):
    """查 ccmixter。注意：limit 一大，服务端会返回超过 64KB 的畸形响应头，
    http.client 直接抛 LineTooLong。所以这里逐步降 limit 重试。"""
    limit = int(参数.get("limit", 20))
    for 试 in range(4):
        参 = dict(参数)
        参["limit"] = limit
        u = API + "?" + urllib.parse.urlencode(参)
        try:
            req = urllib.request.Request(u, headers=头部)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            名 = type(e).__name__
            if 名 in ("LineTooLong", "IncompleteRead", "RemoteDisconnected") and limit > 5:
                limit = max(5, limit // 3)
                time.sleep(1.2)
                continue
            if 试 < 3:
                time.sleep(1.5)
                continue
            raise
    return []


def 下载(url, 存到):
    req = urllib.request.Request(url, headers=头部)
    with urllib.request.urlopen(req, timeout=120) as r:
        数据 = r.read()
    类型 = r.headers.get("Content-Type", "")
    if "audio" not in 类型 and not url.lower().endswith((".mp3", ".flac", ".ogg", ".m4a")):
        raise RuntimeError(f"不是音频（{类型}）")
    if len(数据) < 200_000:
        raise RuntimeError(f"文件太小（{len(数据)}B），可能是错误页")
    with open(存到, "wb") as f:
        f.write(数据)
    return len(数据)


def 安全名(s):
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip()[:80]


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--数量", type=int, default=6)
    ap.add_argument("--风格", default="instrumental", help="ccmixter 标签，空格分隔多个")
    ap.add_argument("--最短秒", type=int, default=60, help="太短的不适合当 BGM")
    ap.add_argument("--只免费", action="store_true", default=True,
                    help="只要允许商用的（默认开）")
    ap.add_argument("--列出", action="store_true")
    args = ap.parse_args()

    os.makedirs(ROOT, exist_ok=True)
    已有 = {}
    if os.path.exists(署名文件):
        with open(署名文件, encoding="utf-8") as f:
            已有 = json.load(f)

    if args.列出:
        if not 已有:
            print("曲库是空的。跑一次 `python 取BGM.py` 抓几首。")
            return
        print(f"本地曲库 {len(已有)} 首（{ROOT}）\n")
        for k, v in 已有.items():
            print(f"  · {k}")
            print(f"    {v['作者']} / {v['协议']}")
            print(f"    {v['来源']}")
        print(f"\n署名模板（投稿简介里加一行）：")
        print(f"  BGM: 「曲名」by 作者 (CC BY 3.0) — ccmixter.org")
        return

    print(f"曲库目录 {ROOT}")
    print(f"已有 {len(已有)} 首，目标再抓 {args.数量} 首\n")

    标签 = args.风格.replace(" ", ",")
    # ccmixter 的 limit 不能大，所以拆成多组标签轮着查，每组只取 15 条
    标签组 = [标签]
    for t in ("instrumental", "ambient", "piano", "electronic", "soundtrack", "chill"):
        if t not in 标签:
            标签组.append(t)

    条 = []
    见过 = set()
    for 组 in 标签组:
        if len(条) >= args.数量 * 6:
            break
        try:
            这批 = 查({"f": "json", "limit": 15, "tags": 组, "lic": "open",
                      "sort": "rank", "ord": "DESC"})
        except Exception as e:
            print(f"  ⚠ 标签 {组} 查询失败：{type(e).__name__}")
            continue
        加 = 0
        for x in 这批:
            i = x.get("upload_id")
            if i in 见过:
                continue
            见过.add(i)
            条.append(x)
            加 += 1
        print(f"  标签 {组:22s} 取到 {加} 条（累计候选 {len(条)}）")
        time.sleep(0.8)
    print(f"\nccmixter 共返回 {len(条)} 条候选\n")

    成功 = 0
    for x in 条:
        if 成功 >= args.数量:
            break
        名字 = x.get("upload_name", "untitled")
        作者 = x.get("user_name", "unknown")
        协议 = x.get("license_name", "?")
        协议URL = x.get("license_url", "")
        页面 = x.get("file_page_url", "")
        扩展 = x.get("upload_extra") or {}
        相对 = 扩展.get("relative_dir", "")
        秒 = int(扩展.get("duration") or 0)

        if 秒 and 秒 < args.最短秒:
            continue

        # 只要音频文件、优先 mp3
        文件表 = x.get("files") or []
        if isinstance(文件表, dict):
            文件表 = [文件表]
        音频 = [f for f in 文件表
                if (f.get("file_format_info") or {}).get("media-type") == "audio"]
        if not 音频:
            continue
        音频.sort(key=lambda f: 0 if str(f.get("file_name", "")).lower().endswith(".mp3") else 1)
        文件 = 音频[0]
        文件名 = 文件.get("file_name", "")
        if not 文件名 or not 相对:
            continue

        短名 = 安全名(os.path.splitext(文件名)[0])
        if 短名 in 已有:
            continue
        存到 = os.path.join(ROOT, 文件名)
        if os.path.exists(存到):
            已有[短名] = {"文件": 文件名, "曲名": 名字, "作者": 作者, "协议": 协议,
                          "协议URL": 协议URL, "来源": 页面, "秒": 秒, "风格": 标签}
            continue

        url = f"https://ccmixter.org/{相对}/{文件名}"
        时长文 = f"{秒//60}:{秒%60:02d}" if 秒 else "?"
        print(f"  ↓ {短名[:52]:52s} {作者[:16]:16s} {协议[:20]:20s} {时长文}")
        try:
            大小 = 下载(url, 存到)
            已有[短名] = {"文件": 文件名, "曲名": 名字, "作者": 作者, "协议": 协议,
                          "协议URL": 协议URL, "来源": 页面, "秒": 秒, "风格": 标签,
                          "字节": 大小}
            成功 += 1
            print(f"      ✅ {大小/1048576:.1f} MB")
        except Exception as e:
            print(f"      ❌ {type(e).__name__}: {str(e)[:70]}")
            if os.path.exists(存到):
                try:
                    os.remove(存到)
                except Exception:
                    pass

    with open(署名文件, "w", encoding="utf-8") as f:
        json.dump(已有, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 新增 {成功} 首，曲库共 {len(已有)} 首")
    print(f"   署名信息 → {署名文件}")
    print(f"\n⚠ ccmixter 大多是 CC-BY（署名即可商用），投稿简介里必须写一行署名。")
    print(f"   出片.py --bgm 会自动把署名追加到 投稿信息.json 里。")
    print(f"\n用法：python 出片.py 脚本.json --bgm auto")


if __name__ == "__main__":
    主()
