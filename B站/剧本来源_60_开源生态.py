# -*- coding: utf-8 -*-
"""探针 60 —— 用 GitHub API 直接查开源生态（web_search 的 key 已失效，走 API）"""
import json
import sys
import urllib.parse as up
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")


def gh(q, sort="stars"):
    url = ("https://api.github.com/search/repositories?q=" + up.quote(q)
           + f"&sort={sort}&per_page=6")
    r = u.Request(url, headers={"User-Agent": "probe",
                                "Accept": "application/vnd.github+json"})
    try:
        d = json.loads(u.urlopen(r, timeout=25).read())
    except Exception as e:
        print(f"  [{q}] ERR {e}")
        return
    print(f"== {q}   (total {d.get('total_count')})")
    for it in d.get("items", []):
        print(f"   {it['full_name']:46s} ★{it['stargazers_count']:<6d}"
              f" {(it['language'] or '-'):12s} push={it['pushed_at'][:10]}")
        print(f"      {(it.get('description') or '')[:110]}")


for q in ["fanqie novel", "fanqienovel", "番茄小说", "tomato novel downloader",
          "x-gorgon", "x-argus", "fanqie novel api"]:
    gh(q)
