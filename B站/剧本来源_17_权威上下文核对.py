# -*- coding: utf-8 -*-
"""
探针 17 —— 权威上下文核对表（最终版）

不再依赖我对密集字形表的第一遍粗读。做法：
  把全部 362 个 PUA 码位（含出现 <3 次的）连同「该码位在 3.5 万字真实语料里的
  全部上下文」逐行打印成纯文本。上下文里的 PUA 用当前映射代入，读起来就是
  近乎正常的中文，哪个字错了会立刻显现。
"""
import html as _html
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as creq

sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR

BOOK = "7069948840148732967"
H = {"Accept-Language": "zh-CN,zh;q=0.9"}
s = creq.Session(impersonate="chrome131")

page = s.get(f"https://fanqienovel.com/page/{BOOK}", headers=H, timeout=25).text
cids, seen = [], set()
for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
    if m.group(1) not in seen:
        seen.add(m.group(1))
        cids.append(m.group(1))

texts = []
for cid in cids[1:11]:                      # 免费章
    t = s.get(f"https://fanqienovel.com/reader/{cid}", headers=H, timeout=25).text
    paras = re.findall(r"<p>(.*?)</p>", t, re.S)
    texts.append(_html.unescape(re.sub(r"<[^>]+>", "", "".join(paras))))

full = "\n".join(texts)
sys.stderr.write(f"语料 {len(full)} 字\n")

ctx = defaultdict(list)
for m in re.finditer(r".{5}([\ue000-\uf8ff]).{5}", full):
    ctx[ord(m.group(1))].append(m.group(0))

out = []
out.append(f"语料 {len(full)} 字；出现过的不同 PUA 码位 {len(ctx)} 个\n")
for cp in sorted(ctx):
    g = PUA2CHAR.get(cp, "?")
    n = len(ctx[cp])
    out.append(f"U+{cp:04X}  当前={g}  x{n}")
    for smp in ctx[cp][:5]:
        out.append("      " + smp.replace(chr(cp), f"〖{g}〗"))
    if n > 5:
        out.append(f"      ...（另有 {n-5} 次）")

p = r"D:\DSHworkspace\B站\情报\_font_probe\上下文核对表.txt"
with open(p, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("已写出", p, "行数", len(out))
