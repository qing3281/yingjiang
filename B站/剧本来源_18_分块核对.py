# -*- coding: utf-8 -*-
"""
探针 18 —— 分块上下文核对（最终判定依据）

把每个 PUA 码位在 ~2.6 万字真实语料里的出现次数 + 最多 10 条上下文，
按码位顺序分块写成纯文本文件。上下文里其它 PUA 一律替换为 〇 占位，
这样每行只考验「当前这一个字」，杜绝连环误读。
"""
import html as _html
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR

BOOKS = ["7069948840148732967"]     # 免费章最多的一本
s = creq.Session(impersonate="chrome131")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}


def get(url, tries=4):
    """番茄偶发返回空/短响应，必须重试并校验长度。"""
    last = ""
    for i in range(tries):
        try:
            r = s.get(url, headers=H, timeout=25)
            if r.status_code == 200 and len(r.text) > 5000:
                return r.text
            last = f"HTTP {r.status_code} len={len(r.text)}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        import time as _t; _t.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url} -> {last}")


texts = []
for BK in BOOKS:
    page = get(f"https://fanqienovel.com/page/{BK}")
    cids, seen = [], set()
    for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            cids.append(m.group(1))
    for cid in cids[1:11]:
        t = get(f"https://fanqienovel.com/reader/{cid}")
        paras = re.findall(r"<p>(.*?)</p>", t, re.S)
        body = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
        texts.append(body)
        sys.stderr.write(f"  {cid} {len(body)} 字\n")
        import time as _t; _t.sleep(0.8)

full = "\n".join(texts)
sys.stderr.write(f"语料 {len(full)} 字\n")
if len(full) < 5000:
    sys.exit("语料太少，中止")

PUA_RUN = re.compile(r"[\ue000-\uf8ff]+")


def mask(s_):
    """把上下文里其它 PUA 换成 〇，只留目标字"""
    return PUA_RUN.sub(lambda m: "〇" * len(m.group(0)), s_)


ctx = defaultdict(list)
for m in re.finditer(r".{7}([\ue000-\uf8ff]).{7}", full):
    ctx[ord(m.group(1))].append(m.group(0))

codes = sorted(ctx)
CHUNK = 40
base = r"D:\DSHworkspace\B站\情报\_font_probe"
for ci in range(0, len(codes), CHUNK):
    part = codes[ci:ci + CHUNK]
    lines = [f"语料 {len(full)} 字 / 共 {len(codes)} 个码位 / 本块 {len(part)} 个\n"]
    for cp in part:
        g = PUA2CHAR.get(cp, "?")
        occ = ctx[cp]
        lines.append(f"U+{cp:04X}  当前={g}  出现 {len(occ)} 次")
        for smp in occ[:10]:
            tgt = mask(smp)
            # 目标字位置：把该 cp 的那一处单独还原
            idx = smp.find(chr(cp))
            tgt = tgt[:idx] + f"【{g}】" + tgt[idx + 1:]
            lines.append("    " + tgt)
        lines.append("")
    p = f"{base}\\核对_{ci//CHUNK + 1}.txt"
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("->", p, len(part))
