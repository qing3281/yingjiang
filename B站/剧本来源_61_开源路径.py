# -*- coding: utf-8 -*-
"""探针 61 —— 看关键开源项目到底走什么路径拿正文（GitHub API 读文件树+关键文件）"""
import base64
import json
import sys
import urllib.request as u

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "probe", "Accept": "application/vnd.github+json"}


def api(path):
    r = u.Request("https://api.github.com" + path, headers=UA)
    return json.loads(u.urlopen(r, timeout=25).read())


def tree(repo, branch=None):
    info = api(f"/repos/{repo}")
    br = branch or info["default_branch"]
    print(f"\n### {repo}  ★{info['stargazers_count']}  lang={info['language']}"
          f"  pushed={info['pushed_at'][:10]}  branch={br}")
    print(f"    {(info.get('description') or '')}")
    t = api(f"/repos/{repo}/git/trees/{br}?recursive=1")
    files = [x["path"] for x in t.get("tree", []) if x["type"] == "blob"]
    print(f"    文件数 {len(files)}；列出前 45 个：")
    for f in files[:45]:
        print(f"      {f}")
    return files


def show(repo, path, n=120):
    try:
        d = api(f"/repos/{repo}/contents/{path}")
        txt = base64.b64decode(d["content"]).decode("utf-8", "replace")
    except Exception as e:
        print(f"  !! {repo}/{path}: {e}")
        return ""
    lines = txt.splitlines()
    print(f"\n----- {repo}/{path}  ({len(lines)} 行) -----")
    for ln in lines[:n]:
        print("   " + ln[:150])
    return txt


for repo in ["ying-ck/fanqienovel-downloader", "zhongbai2333/Tomato-Novel-Downloader"]:
    try:
        fs = tree(repo)
    except Exception as e:
        print(f"!! {repo}: {e}")
        continue
    for cand in ["README.md", "readme.md"]:
        if cand in fs:
            show(repo, cand, 60)
            break
