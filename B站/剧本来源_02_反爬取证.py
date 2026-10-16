# -*- coding: utf-8 -*-
"""
剧本来源探针 02 —— 阅读页反爬机制取证
1) 抓阅读页，dump __INITIAL_STATE__ 结构
2) 提取 @font-face 的字体 URL（动态字体 = 字体混淆反爬）
3) 下载字体，统计 cmap 映射，证明「字形码位被随机化」
4) 证明同一章节两次请求字体不同（=> 静态映射表失效）
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as rq

S = rq.Session(impersonate="chrome")
S.headers.update({"Accept-Language": "zh-CN,zh;q=0.9"})

ITEM = sys.argv[1] if len(sys.argv) > 1 else "7535344092251685400"
URL = f"https://fanqienovel.com/reader/{ITEM}"


def fetch():
    r = S.get(URL, timeout=30)
    print(f"[HTTP {r.status_code}] {URL} len={len(r.text)}")
    return r.text


def extract_state(h):
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", h, re.S)
    if not m:
        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*)", h, re.S)
    if not m:
        return None
    raw = m.group(1)
    # 括�-count 找 JS 对象边界
    depth, in_str, esc, end = 0, False, False, None
    for i, ch in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    try:
        return json.loads(raw[:end])
    except Exception as e:
        print("  json parse fail:", e)
        return None


def walk(o, path="", depth=0, out=None):
    if out is None:
        out = []
    if depth > 3:
        return out
    if isinstance(o, dict):
        for k, v in o.items():
            p = f"{path}.{k}"
            if isinstance(v, (dict, list)):
                out.append((p, type(v).__name__, len(v)))
                walk(v, p, depth + 1, out)
            else:
                s = str(v)
                out.append((p, type(v).__name__, s[:100]))
    elif isinstance(o, list):
        for i, v in enumerate(o[:2]):
            walk(v, f"{path}[{i}]", depth + 1, out)
    return out


print("=" * 70)
print("STEP 1: 阅读页 HTML / __INITIAL_STATE__")
print("=" * 70)
h = fetch()

print("\n--- @font-face 出现次数:", h.count("@font-face"))
fonts = re.findall(r"@font-face\s*\{[^}]*?font-family:\s*([A-Za-z0-9]+)[^}]*?src:\s*url\(([^)]+)\)", h)
print("--- 动态字体条目:", len(fonts))
for fam, u in fonts:
    print(f"    family={fam}\n      url={u[:160]}")

# woff2 全部 URL
woffs = sorted(set(re.findall(r"https://[a-z0-9\-]+\.bytetos\.com/obj/awesome-font/[^\s\"')]+\.woff2", h)))
print("--- 全部 woff2 URL:", len(woffs))
for u in woffs[:6]:
    print("    ", u)

state = extract_state(h)
if state:
    print("\n--- __INITIAL_STATE__ 顶层键:", list(state.keys()))
    for k, t, v in walk(state):
        if any(w in k.lower() for w in ["chapter", "content", "title", "book", "item", "font"]) and len(str(v)) < 130:
            print(f"    {k}  <{t}>  {v}")
else:
    print("  __INITIAL_STATE__ 解析失败")

print("\n--- HTML 中 <div class=\"muye-reader-content\"> 类正文区域 ---")
for m in re.finditer(r'<div[^>]*class="[^"]*(?:reader-content|content)[^"]*"[^>]*>(.{0,400})', h, re.S):
    seg = m.group(1)
    print("    RAW:", seg[:300].replace("\n", " "))
    break

print("\n" + "=" * 70)
print("STEP 2: 同一章节第二次请求，字体是否变化（=> 映射不可缓存）")
print("=" * 70)
h2 = fetch()
f2 = re.findall(r"@font-face\s*\{[^}]*?font-family:\s*([A-Za-z0-9]+)[^}]*?src:\s*url\(([^)]+)\)", h2)
print("--- 第二次 font-family:", [x[0] for x in f2])
print("--- 第二次 woff2:", [x[1][:120] for x in f2])
print("--- 同一章节两次字体 URL 相同?", [x[1] for x in fonts] == [x[1] for x in f2])
print("--- 两次 HTML 长度:", len(h), len(h2))
same_html = h == h2
print("--- 两次 HTML 完全相同?", same_html)

print("\n" + "=" * 70)
print("STEP 3: 下载字体，看 cmap 是不是被洗过")
print("=" * 70)
WOFF_DIR = r"D:\DSHworkspace\B站\情报\_font_probe"
import os
os.makedirs(WOFF_DIR, exist_ok=True)
if woffs:
    try:
        fr = S.get(woffs[0], timeout=30)
        p = os.path.join(WOFF_DIR, "probe1.woff2")
        with open(p, "wb") as fp:
            fp.write(fr.content)
        print(f"    saved {p}  bytes={len(fr.content)}")
        try:
            from fontTools.ttLib import TTFont
            tt = TTFont(p)
            cmap = tt.getBestCmap()
            print("    cmap 条目数:", len(cmap))
            items = sorted(cmap.items())
            print("    最小/最大码位:", hex(items[0][0]), hex(items[-1][0]))
            print("    前 24 个映射:")
            for cp, name in items[:24]:
                print(f"       {hex(cp)} U+{cp:04X} -> {name}")
            print("    glyph 名是否多为 uniXXXX 形式:", sum(1 for _, n in items if n.startswith("uni")) , "/", len(items))
        except ImportError:
            print("    [SKIP] fontTools 未安装")
        except Exception as e:
            print("    fontTools 解析失败:", type(e).__name__, e)
    except Exception as e:
        print("    字体下载失败:", e)
else:
    print("    未找到 woff2")
