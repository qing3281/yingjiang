# -*- coding: utf-8 -*-
"""探针 62 —— 公开的字符映射表（charset.json）能不能直接用？对比我自建的映射表"""
import base64
import json
import sys
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "probe", "Accept": "application/vnd.github+json"}


def raw(repo, path):
    r = u.Request(f"https://api.github.com/repos/{repo}/contents/{path}",
                  headers=UA)
    d = json.loads(u.urlopen(r, timeout=25).read())
    return base64.b64decode(d["content"]).decode("utf-8", "replace")


txt = raw("ying-ck/fanqienovel-downloader", "src/charset.json")
print(f"charset.json 长度 {len(txt)} 字节")
try:
    j = json.loads(txt)
    print(f"顶层类型 {type(j).__name__}，条目 {len(j)}")
    items = list(j.items())[:8]
    for k, v in items:
        print(f"   {k!r} -> {v!r}")
except Exception as e:
    print("解析失败：", e, txt[:300])

MINE = {int(k, 0): v
        for k, v in json.load(open(
            r"D:\DSHworkspace\B站\情报\_font_probe\map_shift.json",
            encoding="utf-8"))["map"].items()}
print(f"\n我自建映射表 {len(MINE)} 项")

# 尝试各种可能的键格式对齐
if isinstance(j, dict):
    keys = list(j.keys())
    print(f"样例键：{keys[:6]}")
    hits = 0
    for k, v in j.items():
        try:
            kk = int(k, 0) if isinstance(k, str) else int(k)
        except Exception:
            continue
        if MINE.get(kk) == v:
            hits += 1
    print(f"与自建表一致的条目：{hits}/{len(j)}")
