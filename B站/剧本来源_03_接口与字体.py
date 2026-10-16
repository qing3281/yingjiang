# -*- coding: utf-8 -*-
"""
剧本来源探针 03 —— 字体混淆的「逐章随机」取证 + 候选 API 端点探测

关键问题：
  A) 同一本书不同章节，字体 cmap 是否不同？ => 若不同，静态映射表失效，必须逐章建映射
  B) 不同书的字体是否不同？
  C) noval.snssdk.com / 网页 /api/ 端点哪些能直接返回 JSON？
"""
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as rq

OUT = r"D:\DSHworkspace\B站\情报\_font_probe"
os.makedirs(OUT, exist_ok=True)
S = rq.Session(impersonate="chrome")
S.headers.update({"Accept-Language": "zh-CN,zh;q=0.9"})


def state_of(html):
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*)", html, re.S)
    if not m:
        return None
    raw, depth, in_str, esc = m.group(1), 0, False, False
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
                try:
                    return json.loads(raw[: i + 1])
                except Exception:
                    return None
    return None


def font_of(html):
    fams = re.findall(r"@font-face[^}]*?font-family:\s*([A-Za-z0-9]+)", html, re.S)
    urls = re.findall(r"https://([a-z0-9\-]+)\.bytetos\.com/obj/awesome-font/c/([0-9a-f]+)\.woff2", html)
    return (fams[0] if fams else None), sorted(set(u[1] for u in urls))


def cmap_of(hash_id, tag):
    p = os.path.join(OUT, f"{tag}_{hash_id}.woff2")
    if not os.path.exists(p):
        r = S.get(f"https://lf6-awef.bytetos.com/obj/awesome-font/c/{hash_id}.woff2", timeout=30)
        open(p, "wb").write(r.content)
    from fontTools.ttLib import TTFont
    tt = TTFont(p)
    cm = tt.getBestCmap()
    # 用字形轮廓坐标做指纹（字体被洗过，gid 无意义）
    gs = tt.getGlyphSet()
    from fontTools.pens.recordingPen import RecordingPen
    fp = []
    for cp in sorted(cm):
        pen = RecordingPen()
        gs[cm[cp]].draw(pen)
        fp.append((cp, tuple(pen.value)[:3]))
    return cm, fp


print("=" * 72)
print("A) 同一本书 · 不同章节的字体对比")
print("=" * 72)
BOOK = "7069948840148732967"  # 部族荣光
r = S.get(f"https://fanqienovel.com/page/{BOOK}", timeout=30)
ids = re.findall(r"/reader/(\d+)", r.text)
# 去重保序
seen, chap_ids = set(), []
for i in ids:
    if i not in seen:
        seen.add(i)
        chap_ids.append(i)
print("书:", BOOK, " 目录章节数:", len(chap_ids))
probe = chap_ids[:2] + chap_ids[len(chap_ids) // 2 : len(chap_ids) // 2 + 1]
print("取 3 章做对比:", probe)

recs = []
for idx, item in enumerate(probe):
    time.sleep(1.5)
    rr = S.get(f"https://fanqienovel.com/reader/{item}", timeout=30)
    fam, hashes = font_of(rr.text)
    st = state_of(rr.text)
    cd = (st or {}).get("reader", {}).get("chapterData", {}) if st else {}
    content = cd.get("content", "") or ""
    pua = len(re.findall(r"[\ue000-\uf8ff]", content))
    han = len(re.findall(r"[\u4e00-\u9fff]", content))
    print(f"\n--- 章节{idx+1} itemId={item}")
    print(f"    title={cd.get('title')!r}  字数={cd.get('chapterWordNumber')}")
    print(f"    正文字符数={len(content)}  汉字={han}  PUA私用区={pua}")
    print(f"    font-family={fam}  font hashes={hashes}")
    recs.append({"item": item, "fam": fam, "hashes": hashes, "pua": pua, "han": han, "len": len(content), "content": content})

print("\n>>> 字体 hash 是否逐章不同?")
for r_ in recs:
    print("    ", r_["item"], r_["fam"], r_["hashes"])

print("\n>>> cmap 是否逐章洗牌（对比第1章 vs 第2章）")
if len(recs) >= 2 and recs[0]["hashes"] and recs[1]["hashes"]:
    c1, f1 = cmap_of(recs[0]["hashes"][0], "ch1")
    c2, f2 = cmap_of(recs[1]["hashes"][0], "ch2")
    print("    第1章 cmap 条目:", len(c1), " 第2章 cmap 条目:", len(c2))
    common_cp = sorted(set(c1) & set(c2))
    print("    共同码位数:", len(common_cp))
    # 对共同码位，比较字形轮廓指纹
    d1 = dict(f1)
    d2 = dict(f2)
    diff = [cp for cp in common_cp if d1.get(cp) != d2.get(cp)]
    print(f"    共同码位中 字形轮廓不同 的数量: {len(diff)} / {len(common_cp)}")
    print("    => 结论:", "逐章洗牌，静态映射表失效" if len(diff) > len(common_cp) * 0.5 else "码位稳定，可建全局映射表")
    for cp in common_cp[:5]:
        print(f"       U+{cp:04X}: ch1轮廓={str(d1.get(cp))[:60]}")
        print(f"                ch2轮廓={str(d2.get(cp))[:60]}")

print("\n" + "=" * 72)
print("B) 候选 API 端点探测（不带签名，看谁裸奔）")
print("=" * 72)
cands = [
    ("web /api/reader/full", "https://fanqienovel.com/api/reader/full?itemId=7535344092251685400"),
    ("web /api/reader/directory/detail", f"https://fanqienovel.com/api/reader/directory/detail?bookId={BOOK}"),
    ("web /api/reader/full 无参", "https://fanqienovel.com/api/reader/full"),
    ("app snssdk content", "https://novel.snssdk.com/api/novel/book/reader/full/v1/?item_id=7535344092251685400&aid=1967"),
    ("app snssdk directory", f"https://novel.snssdk.com/api/novel/book/directory/list/v1/?book_id={BOOK}&aid=1967"),
    ("app snssdk batch_full", "https://novel.snssdk.com/api/novel/book/reader/batch_full/v1/?item_ids=7535344092251685400&aid=1967"),
    ("app fqnovel content", "https://api5-normal-sinfonlineb.fqnovel.com/reading/reader/full/v1/?item_id=7535344092251685400&aid=1967"),
    ("app snssdk book info", f"https://novel.snssdk.com/api/novel/book/detail/v1/?book_id={BOOK}&aid=1967"),
]
HDR = {
    "User-Agent": "com.dragon.read/6.0.0 (Linux; U; Android 12; zh_CN; Pixel 5; Build/SQ3A.220705.004; Cronet/58.0.2991.0)",
    "Accept": "application/json",
}
for name, url in cands:
    time.sleep(1.2)
    try:
        rr = S.get(url, headers=HDR, timeout=20)
        body = rr.text
        snippet = body[:220].replace("\n", " ")
        print(f"\n[{name}]  HTTP {rr.status_code}  len={len(body)}  ct={rr.headers.get('content-type')}")
        print(f"    {snippet}")
        if rr.status_code == 200 and body.lstrip().startswith("{"):
            try:
                j = rr.json()
                print("    JSON 顶层键:", list(j.keys())[:12])
                print("    json 内容长度:", len(json.dumps(j, ensure_ascii=False)))
            except Exception as e:
                print("    json 解析失败:", e)
    except Exception as e:
        print(f"\n[{name}]  FAIL {type(e).__name__}: {e}")

print("\n" + "=" * 72)
print("C) 正文 PUA 字符样本（证明是「有意义的字」被替换成私用区）")
print("=" * 72)
c = recs[0]["content"]
plain = re.sub(r"<[^>]+>", "", c)
pua_chars = sorted(set(re.findall(r"[\ue000-\uf8ff]", plain)))
print("  该章不同 PUA 字符数:", len(pua_chars))
print("  codepoints:", " ".join(f"{ord(x):04X}" for x in pua_chars[:40]))
print("  正文前 120 字符原样:", plain[:120])
print("  其中 PUA 占比: %.1f%%" % (100 * len(re.findall(r"[\ue000-\uf8ff]", plain)) / max(1, len(plain))))
