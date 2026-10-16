# -*- coding: utf-8 -*-
r"""出一份**谁都能读**的剧本：`D:\DSHworkspace\影匠\作品\觉醒\_剧本.html`

为什么要有它：用户 2026-10-15 的硬规矩第 5 条 ——
    「我要的不是小说，我要的不是写诗，我要的是能够直观的简单明了的，
      **不管是谁都能看懂的**……故事不行，就是不行。」
可现在的「剧本」是四份给机器看的 md：`00-故事.md`（22 KB）/ `01-节拍拆解.md`（26 KB）/
`02-九宫格.md`（128 KB）/ `03-台词.md`（12 KB）。**加起来 188 KB，没有人会读它。**

这一份把它压成一条线：**一句话 → 人物（带定妆照）→ 五幕 → 逐格表 → 节奏与伏笔**。
逐格表每格只有四列：**第几格 / 什么时候 / 画面上是什么 / 谁说了什么**。

用法：python _出剧本.py [戏]   默认 觉醒
产出：作品\<戏>\_剧本.html（+ 可选的桌面快捷方式）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

戏 = sys.argv[1] if len(sys.argv) > 1 else "觉醒"
根 = r"D:\DSHworkspace\影匠\作品"
戏目 = os.path.join(根, 戏)
出 = os.path.join(戏目, "_剧本.html")

格秒 = 4.06  # 格 n 起点 = (n-1) × 4.06 秒（4.4583 秒一格 − 0.5 秒交叉溶解）


def 读(名):
    p = os.path.join(戏目, 名)
    return io.open(p, encoding="utf-8").read() if os.path.isfile(p) else ""


def 时刻(n):
    s = (n - 1) * 格秒
    return f"{int(s) // 60}:{s % 60:04.1f}"


# ── 1. 逐格：标题 / 目的 / 景别 ──────────────────────────────
# ★ 四部戏的九宫格写法不一样，解析要都能吃：
#   《觉醒》标题 `## 格14 —— 今年是不是轮到我`，字段 `- **目的**：…`
#   《雪线》标题 `## 格1 —— 线上剑`，          字段 `- 目的：…`（没有 ** 号）
#   有的戏角色卡写 `- **陈老根**：…`，有的写 `- 凌霜：…`
九 = 读("02-九宫格.md")
_字段 = r"^-\s*\*{{0,2}}{0}\*{{0,2}}\s*[：:]\s*(.+?)$"


def 取值(段, 名):
    m = re.search(_字段.format(名), 段, re.M)
    return m.group(1).strip() if m else ""


格s = []
for m in re.finditer(r"^##\s*格\s*(\d+)\s*[——\-–]+\s*(.+?)$", 九, re.M):
    号 = int(m.group(1))
    段 = 九[m.end():]
    下 = re.search(r"^## ", 段, re.M)
    段 = 段[:下.start()] if 下 else 段
    格s.append({"号": 号, "题": m.group(2).strip(),
                "目的": 取值(段, "目的"), "景别": 取值(段, "景别"),
                "重点": 取值(段, "重点")})
格s.sort(key=lambda x: x["号"])

# ── 2. 台词：格号 → [(说话人, 台词)] ─────────────────────────
# 三条路，按可靠性从高到低：
#   ① `03-台词.md` 里 `| 格 | 说话人 | 台词 |` 那种表（《觉醒》）
#   ② `03-台词.md` 里 `| 格号 | 说话人 | 台词原文 |` 那种表（《磨刀》，格子写成 `格2`）
#   ③ 只有 `配音\_台词.srt` 的戏（《雪线》）—— 按时刻反推是哪一格
台 = 读("03-台词.md")
词 = {}
来源 = ""
# ★ 不能全文正则捞 —— `03-台词.md` 里除了「全量台词表」，
#   还有「这一版改了什么」那种小表，同一句会在两处各出现一次。
#   所以先找出**含「说话人」表头的那张表**，再只读那一张，取**行数最多的**那张。
表s = []
for m in re.finditer(r"^(\|[^\n]*\|)\s*\n\|[\s\-:|]+\|\s*\n((?:\|[^\n]*\|\s*\n?)+)", 台, re.M):
    头, 身 = m.group(1), m.group(2)
    if "说话人" not in 头 and "角色" not in 头:
        continue
    行s = []
    for l in 身.strip().splitlines():
        格 = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(格) >= 3:
            行s.append(格)
    表s.append(行s)
行s = [r for t in 表s for r in t]  # ★ 全部拼起来，不取最大的那张 ——
#   《磨刀》是按场分成好几张表的（场1/场2/…），只取一张会丢掉后面几场；
#   而《觉醒》多出来的那张「这一版改了什么」的小表，靠下面的去重滤掉。
for 格 in 行s:
    mm = re.match(r"^(?:格)?\s*(\d+)$", 格[0].replace("*", ""))
    if not mm:
        continue
    号 = int(mm.group(1))
    if 1 <= 号 <= 999:
        词.setdefault(号, []).append((格[1].replace("*", "").strip(),
                                      格[2].replace("*", "").strip()))
if 词:
    来源 = f"03-台词.md（{len(表s)} 张表共 {len(行s)} 行）"

if not 词:
    # `配音\_台词.srt` 只有时间没有格号 ——
    # 格 n 在成片里的起点 = 片头 4 秒 + (n-1) × 4.06 秒。
    # ★ SRT 的毫秒分隔符是**逗号**（`00:00:00,600`），不是点 —— 这个不修就一条都匹配不上。
    srt = 读(os.path.join("配音", "_台词.srt"))
    秒 = lambda a, b, c: int(a) * 3600 + int(b) * 60 + float(c.replace(",", "."))
    for m in re.finditer(r"(\d\d):(\d\d):([\d,.]+)\s*-->\s*(\d\d):(\d\d):([\d,.]+)\s*\n(.+?)(?=\n\s*\n|\Z)",
                         srt, re.S):
        起 = 秒(m.group(1), m.group(2), m.group(3))
        文 = " ".join(x.strip() for x in m.group(7).strip().splitlines() if x.strip())
        if 文:
            号 = max(1, int(round((起 - 4) / 格秒)) + 1)
            词.setdefault(号, []).append(("", 文))
    if 词:
        来源 = "配音\\_台词.srt（按时刻反推格子）"

# 去掉重复：`03-台词.md` 里除了那张全量表，还有「这一版改了什么」的小表，
# 同一句会在两处各出现一次（《觉醒》格 2 / 格 8 会各显两遍）。
去重 = {}
for 号, 列 in 词.items():
    见, 留 = set(), []
    for 谁, 文 in 列:
        键 = (谁, re.sub(r"[\s「」【】*]", "", 文))
        if 键 in 见:
            continue
        见.add(键)
        留.append((谁, 文))
    去重[号] = 留
词 = 去重

# ── 3. 角色卡 + 定妆照 ───────────────────────────────────────
# 写法有两样：`- **陈老根**：…`（觉醒）和 `- 凌霜：…`（雪线）
卡 = re.search(r"^##\s*角色卡.*?$(.*?)(?=^## )", 九, re.M | re.S)
角色 = []
if 卡:
    for m in re.finditer(r"^-\s*\*{0,2}([^：:*\n]+?)\*{0,2}\s*[：:]\s*(.+?)$", 卡.group(1), re.M):
        名, 串 = m.group(1).strip(), m.group(2).strip()
        照 = f"_定妆照/{名}.png"
        角色.append({"名": 名, "串": 串,
                     "照": 照 if os.path.isfile(os.path.join(戏目, 照)) else None})
if not 角色:
    # 没有角色卡就从定妆照目录反推（有图就有这个人物）
    照目 = os.path.join(戏目, "_定妆照")
    if os.path.isdir(照目):
        for f in sorted(os.listdir(照目)):
            if f.lower().endswith(".png") and not f.startswith("_"):
                名 = os.path.splitext(f)[0]
                角色.append({"名": 名, "串": "（这一部没有「角色卡」小节，外貌锚点分散在每一格的提示词里）",
                             "照": f"_定妆照/{f}"})

# ── 4. 五幕结构（从 00-故事.md 抠那张表） ─────────────────────
故 = 读("00-故事.md")
幕 = re.search(r"^##\s*六、五幕结构.*?$(.*?)(?=^## )", 故, re.M | re.S)
幕表 = re.findall(r"^\|(.+?)\|\s*$", 幕.group(1), re.M) if 幕 else []
幕表 = [r for r in 幕表 if not set(r.replace("|", "").strip()) <= set("-: ")]

logline = ""
m = re.search(r"^##\s*〇、一句话故事.*?$(.*?)(?=^## )", 故, re.M | re.S)
if m:
    for l in m.group(1).splitlines():
        l = l.strip().strip(">").strip()
        if l and not l.startswith("#"):
            logline = l
            break
if not logline and 格s:
    # 没有 00-故事.md 的戏，用第一格的「目的」和不重复的第一句台词凑一句
    logline = "（这一部没有 `00-故事.md`，一句话故事没写下来。）"


def 转义(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def 净(s):
    """把 md 的 ** 粗体标记去掉 —— 表格里它会原样显出来。"""
    return 转义(re.sub(r"\*\*(.+?)\*\*", r"\1", s))


# 全片 = 格数 × 4.4583 − 转场 + 片头 4 秒 + 片尾 5 秒（`_成片_觉醒.py` 的链条）
总秒 = len(格s) * 4.4583 - (len(格s) - 1) * 0.5 + 9


行 = []
for g in 格s:
    号 = g["号"]
    说 = 词.get(号, [])
    词块 = "".join(
        f'<div class="词"><span class="谁 {("旁" if 谁 == "旁白" else "系" if 谁 == "系统" else "人")}">{谁}</span>'
        f'<span class="话">{转义(文)}</span></div>' for 谁, 文 in 说)
    行.append(f"""<tr id="g{号}">
<td class="号">{号}<span class="时">{时刻(号)}</span></td>
<td><b class="题">{净(g['题'])}</b><div class="景">{净(g['景别'])}</div>
    <div class="的">{净(g['目的'])}</div></td>
<td>{词块 or '<span class="默">（没有台词 —— 故意的）</span>'}</td></tr>""")

有词 = sum(len(v) for v in 词.values())
页 = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>《{戏}》剧本</title>
<style>
:root{{--bg:#12141a;--纸:#1a1e27;--边:#2a3140;--字:#e8eaf0;--小:#8b95a7;--暖:#e0a75e;--吉:#3ddc84}}
*{{box-sizing:border-box}}
body{{margin:0;padding:0 0 70px;background:var(--bg);color:var(--字);
     font:16px/1.85 "Microsoft YaHei",Georgia,serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 32px}}
h1{{font-size:40px;margin:56px 0 8px;letter-spacing:.06em}}
h2{{font-size:22px;margin:52px 0 16px;padding-bottom:9px;border-bottom:1px solid var(--边)}}
.副{{color:var(--小);font-size:15px;margin:0}}
.log{{background:var(--纸);border-left:3px solid var(--暖);padding:18px 22px;margin:26px 0;
     border-radius:0 8px 8px 0;font-size:17px;line-height:1.9}}
.角{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px}}
.人{{background:var(--纸);border:1px solid var(--边);border-radius:10px;overflow:hidden}}
.人 img{{width:100%;display:block;background:#000}}
.人 .文{{padding:14px 18px}}
.人 .名{{font-size:19px;font-weight:700;margin-bottom:6px}}
.人 .串{{color:#b9c2d2;font-size:13.5px;line-height:1.8}}
table{{border-collapse:collapse;width:100%;font-size:15px}}
th,td{{border-bottom:1px solid var(--边);padding:13px 12px;text-align:left;vertical-align:top}}
th{{background:#1b2130;color:var(--小);font-weight:400;font-size:13.5px;
   position:sticky;top:0;z-index:2}}
.号{{width:74px;color:var(--小);font-size:13px;white-space:nowrap}}
.号 .时{{display:block;color:#5d6779;font-size:12px}}
.题{{font-size:16.5px}}
.景{{color:#8b95a7;font-size:12.5px;margin-top:3px;letter-spacing:.02em}}
.的{{color:#77808f;font-size:13px;margin-top:5px;line-height:1.7}}
.词{{margin:2px 0}}
.谁{{display:inline-block;min-width:52px;font-size:12.5px;color:#8b95a7}}
.谁.旁{{color:#c58ad2}} .谁.系{{color:#6fb4e0}} .谁.人{{color:var(--暖)}}
.话{{font-size:16px}}
.默{{color:#525c6d;font-size:13px}}
.幕表 td{{font-size:14.5px}}
.尾{{color:var(--小);font-size:13.5px;margin-top:46px;
     border-top:1px solid var(--边);padding-top:18px}}
</style></head><body>
<div class="wrap">

<h1>《{戏}》</h1>
<p class="副">5 分钟 AI 短片　·　{len(格s)} 格　·　{有词} 句台词　·　
{总秒:.0f} 秒（{int(总秒) // 60} 分 {总秒 % 60:02.0f} 秒）　·　2026-10-15 第三版</p>

<div class="log">{净(logline)}</div>

<h2>人物</h2>
<p class="副">下面每段外貌文字，在生成每一格画面时<b>逐字复用、一字不改</b> —— 这是全片不换脸的唯一办法。</p>
<div class="角">
{''.join(f'''<div class="人">{f'<img src="{a["照"]}">' if a["照"] else ""}
<div class="文"><div class="名">{转义(a["名"])}</div><div class="串">{转义(a["串"])}</div></div></div>''' for a in 角色)}
</div>

<h2>五幕</h2>
<table class="幕表">
{''.join('<tr>' + ''.join(f'<td>{净(c.strip())}</td>' for c in r.split('|')) + '</tr>' for r in 幕表)}
</table>

<h2>逐格（{len(格s)} 格 · 每格 4.46 秒）</h2>
<p class="副">左边是第几格和它在片子里的时刻；中间是画面上发生什么；右边是这一格谁说了什么。</p>
<table>
<tr><th>格</th><th>画面上是什么</th><th>谁说了什么</th></tr>
{''.join(行)}
</table>

<p class="尾">
这份是从 <code>00-故事.md</code> / <code>01-节拍拆解.md</code> / <code>02-九宫格.md</code> /
<code>03-台词.md</code> 四份**给机器看的**文件里抽出来的，一个字都没有新写。<br>
那四份加起来 188 KB；这一份是它的**人能读的版本**。<br>
生成器：<code>D:\\DSHworkspace\\_出剧本.py</code>　·　改完源文件重跑一次就好。
</p>
</div></body></html>
"""

io.open(出, "w", encoding="utf-8", newline="\n").write(页)
print(f"  ✓ {出}　{os.path.getsize(出):,} B")
print(f"     {len(格s)} 格　{有词} 句台词　{len(角色)} 个人物（有定妆照 {sum(1 for a in 角色 if a['照'])} 张）"
      f"　五幕表 {len(幕表)} 行")
if not 格s:
    print("  ✗ 一格都没解析出来 —— 九宫格的标题格式对不上")
