# -*- coding: utf-8 -*-
"""影匠监工台 —— 把「我在干什么」摆到屏幕上。

## 为什么有这个东西

用户 2026-10-14 原话：

> 你做的平台，你进行的操作，能不能可视化，你做的时候，生成的图片，输入的提示词这些，
> 我能不能同步显示，在你的平台上看到，否则你每次生成的东西，人物形象，这些对我来说
> 都是看不见的，很容易有问题

说得很对：在此之前所有产出都在磁盘上，用户看不见人物长什么样、提示词写了什么，
只能等我发邮件。**看不见就没法在早期拦住问题。**

## 它怎么工作

**只读磁盘**，不改任何生产脚本 —— 就算监工台挂了，出片流程照样跑。

数据源（每次刷新重扫）：

| 从哪 | 拿到什么 |
|---|---|
| `作品\\<戏>\\02-九宫格.md` | 每格的 景别 / 动作 / 光色（**这就是喂给模型的提示词原料**） |
| `作品\\<戏>\\01_格N.png` | 首帧（喂进 H3 的那张图） |
| `作品\\<戏>\\段\\格N_本机|远端.mp4` | 已出的段 + 是哪条线出的 + 多大 |
| `作品\\<戏>\\片\\*.mp4` | 成片 |
| `作品\\<戏>\\*.txt` `*日志*.txt` | 最近几行日志 |
| `作品\\<戏>\\_*.png` | 联系表 / 底部条这类检查图 |

## 用法

    python _监工.py                 # 起在 127.0.0.1:8791，自动开浏览器
    python _监工.py --戏 觉醒
    python _监工.py --口 8791 --不开

然后在浏览器里看。页面每 5 秒自己刷一遍。
"""
import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

根 = os.path.dirname(os.path.abspath(__file__))
作品 = os.path.join(根, "作品")
允许后缀 = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".gif"}


# ─────────────────────────── 读生产状态 ───────────────────────────

def 读九宫格(戏):
    """从 02-九宫格.md 抠出每格的 景别/动作/光色 —— 这三样就是提示词的原料。"""
    路 = os.path.join(作品, 戏, "02-九宫格.md")
    if not os.path.isfile(路):
        return {}
    文 = open(路, encoding="utf-8", errors="replace").read()
    块 = re.split(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$", 文, flags=re.M)
    出 = {}
    for i in range(1, len(块), 3):
        号 = int(块[i])
        题 = 块[i + 1].strip()
        体 = 块[i + 2]

        def 抠(键, 体=体):
            m = re.search(rf"^-\s*\*{{0,2}}{键}\*{{0,2}}\s*[:：]\s*(.*)$", 体, flags=re.M)
            return m.group(1).strip() if m else ""
        出[号] = {"题": 题, "景别": 抠("景别"), "动作": 抠("动作"),
                  "光色": 抠("光色"), "提示词": 抠("提示词"), "重点": 抠("重点")}
    return 出


def 读台词(戏):
    """从 03-台词.md 的表格抠出 {格号: [(说话人, 台词, 情感), ...]}。

    ★ 2026-10-15：**两种表格格式都要认**，因为「拿到一个新剧本页面还能不能用」
       正是用户问的问题，而第一版只认觉醒那一种，磨刀直接读出 0 句：

       觉醒：  | 格 | 说话人 | 台词 | 情感 |     ← 第一列是纯数字
       磨刀：  | 格号 | 说话人 | 台词原文 |        ← 第一列带「格」字，而且只有三列
    """
    路 = os.path.join(作品, 戏, "03-台词.md")
    if not os.path.isfile(路):
        return {}
    出 = {}
    for 行 in open(路, encoding="utf-8", errors="replace"):
        行 = 行.strip()
        if not 行.startswith("|"):
            continue
        c = [x.strip() for x in 行.strip("|").split("|")]
        if len(c) < 3:
            continue
        # 第一列：纯数字，或者「格12」「格号」；「格号」是表头，跳过
        首 = re.sub(r"^格\s*", "", c[0]).strip()
        if not 首.isdigit():
            continue
        出.setdefault(int(首), []).append(
            (c[1], c[2], c[3] if len(c) > 3 else ""))
    return 出


def 读锚点(戏):
    """从 01-节拍拆解.md 的「角色文字锚点串」表抠出 [(角色, 定位, 锚点串), ...]。

    ★ 这张表就是「人物形象」在磁盘上的全部形态 —— 它是**文字**，不是图。
    """
    路 = os.path.join(作品, 戏, "01-节拍拆解.md")
    if not os.path.isfile(路):
        return []
    文 = open(路, encoding="utf-8", errors="replace").read()
    m = re.search(r"##\s*角色文字锚点串.*?\n(.*?)(?=\n##\s|\Z)", 文, re.S)
    if not m:
        return []
    出 = []
    for 行 in m.group(1).splitlines():
        行 = 行.strip()
        if not 行.startswith("|"):
            continue
        c = [x.strip() for x in 行.strip("|").split("|")]
        if len(c) < 3 or c[0].startswith("---") or "角色" in c[0] and "锚点" in c[1]:
            continue
        角 = re.sub(r"\*\*", "", c[0]).strip()
        if not 角 or 角 in ("角色",):
            continue
        # 表里还混着「场1/场2…」那种场次表行 —— 用「场N」开头排掉
        if re.match(r"^场\d+$", 角):
            continue
        出.append((角, c[1].strip(), c[2].strip()))
    return 出


def 读剧本(戏):
    """读三份文字稿，供页面上直接看。"""
    出 = []
    for 名, 标题 in (("00-故事.md", "00 故事（源头）"),
                     ("01-节拍拆解.md", "01 节拍拆解"),
                     ("02-九宫格.md", "02 九宫格（每格的提示词原料）"),
                     ("03-台词.md", "03 台词")):
        路 = os.path.join(作品, 戏, 名)
        if not os.path.isfile(路):
            continue
        文 = open(路, encoding="utf-8", errors="replace").read()
        出.append({"名": 名, "标题": 标题, "文": 文,
                    "kb": round(os.path.getsize(路) / 1024, 1)})
    return 出


def 扫状态(戏):
    戏目 = os.path.join(作品, 戏)
    格表 = 读九宫格(戏)
    台词 = 读台词(戏)
    段目 = os.path.join(戏目, "段")

    # 段：同一格两条线都出了就都留着（页面上标出来）
    段 = {}
    for p in glob.glob(os.path.join(段目, "*.mp4")):
        m = re.match(r"^格(\d+)_(本机|远端)\.mp4$", os.path.basename(p))
        if not m:
            continue
        n = int(m.group(1))
        段.setdefault(n, {})[m.group(2)] = {
            "路": os.path.relpath(p, 根).replace("\\", "/"),
            "mb": round(os.path.getsize(p) / 1048576, 2),
            "改": time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p))),
        }
    # 重抽目录也收进来
    重抽 = {}
    for p in glob.glob(os.path.join(戏目, "_重抽", "*.mp4")):
        m = re.search(r"格(\d+)", os.path.basename(p))
        if m:
            重抽.setdefault(int(m.group(1)), []).append({
                "名": os.path.basename(p),
                "路": os.path.relpath(p, 根).replace("\\", "/"),
                "mb": round(os.path.getsize(p) / 1048576, 2),
                "改": time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p))),
            })

    片 = []
    for p in glob.glob(os.path.join(戏目, "片", "*.mp4")):
        片.append({
            "名": os.path.basename(p),
            "路": os.path.relpath(p, 根).replace("\\", "/"),
            "mb": round(os.path.getsize(p) / 1048576, 2),
            "改": time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p))),
        })
    片.sort(key=lambda d: -d["mb"])

    检查图 = []
    for p in sorted(glob.glob(os.path.join(戏目, "_*.png")) +
                    glob.glob(os.path.join(戏目, "_*.jpg"))):
        检查图.append({
            "名": os.path.basename(p),
            "路": os.path.relpath(p, 根).replace("\\", "/"),
            "mb": round(os.path.getsize(p) / 1048576, 2),
            "改": time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p))),
        })
    检查图.sort(key=lambda d: -os.path.getmtime(os.path.join(根, d["路"])))

    # 日志：每个文件抽尾 12 行
    日志 = []
    for p in sorted(glob.glob(os.path.join(戏目, "*.txt")) +
                    glob.glob(os.path.join(戏目, "**", "*.txt"), recursive=True)):
        if not os.path.isfile(p):
            continue
        try:
            行 = open(p, encoding="utf-8", errors="replace").read().splitlines()[-12:]
        except Exception:
            continue
        日志.append({
            "名": os.path.relpath(p, 戏目).replace("\\", "/"),
            "改": time.strftime("%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p))),
            "行": 行,
        })
    日志.sort(key=lambda d: d["改"], reverse=True)

    格 = []
    for n in sorted(格表):
        d = dict(格表[n])
        d["号"] = n
        d["首帧"] = (os.path.relpath(os.path.join(戏目, f"01_格{n}.png"), 根).replace("\\", "/")
                    if os.path.isfile(os.path.join(戏目, f"01_格{n}.png")) else "")
        d["段"] = 段.get(n, {})
        d["重抽"] = 重抽.get(n, [])
        d["台词"] = 台词.get(n, [])
        格.append(d)

    齐 = len(段)
    return {
        "戏": 戏,
        "时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "格数": len(格表),
        "已出段": len(段),
        "段格号": sorted(段),
        "缺格号": [n for n in sorted(格表) if n not in 段],
        "格": 格,
        "片": 片,
        "检查图": 检查图,
        "日志": 日志[:8],
        "台词总": sum(len(v) for v in 台词.values()),
        "锚点": 读锚点(戏),
        "剧本": 读剧本(戏),
    }


# ─────────────────────────── 页面 ───────────────────────────

页头 = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>影匠监工台</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0e1116;--卡:#161b22;--线:#272e38;--字:#e6edf3;--淡:#8b949e;--亮:#58a6ff;--好:#3fb950;--警:#d29922}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--字);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;z-index:9;background:#0e1116ee;backdrop-filter:blur(8px);
  border-bottom:1px solid var(--线);padding:12px 18px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:600}
.数{color:var(--淡)}.数 b{color:var(--字);font-size:16px}
.条{flex:1;min-width:160px;height:8px;background:#21262d;border-radius:4px;overflow:hidden}
.条 i{display:block;height:100%;background:linear-gradient(90deg,#1f6feb,#3fb950)}
main{padding:16px 18px 60px;max-width:1780px;margin:0 auto}
h2{font-size:15px;margin:26px 0 10px;color:var(--淡);font-weight:600;
  border-left:3px solid var(--亮);padding-left:9px}
.网格{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:13px}
.卡{background:var(--卡);border:1px solid var(--线);border-radius:9px;overflow:hidden;display:flex;flex-direction:column}
.卡 .头{padding:7px 11px;border-bottom:1px solid var(--线);display:flex;justify-content:space-between;
  align-items:center;gap:8px;font-size:13px}
.号{font-weight:700;color:var(--亮);white-space:nowrap}
.签{font-size:11px;padding:1px 7px;border-radius:9px;background:#21262d;color:var(--淡);white-space:nowrap}
.签.有{background:#17351f;color:var(--好)}.签.缺{background:#3a2a10;color:var(--警)}
.图{width:100%;aspect-ratio:16/9;object-fit:cover;background:#0b0e12;display:block;cursor:zoom-in}
.体{padding:9px 11px;font-size:12.5px;flex:1}
.行{margin:5px 0;display:flex;gap:7px}
.键{color:var(--淡);flex:0 0 42px}
.值{flex:1;word-break:break-word}
.词{background:#0d1117;border:1px solid var(--线);border-radius:5px;padding:6px 8px;margin:6px 0;
  font-size:12px;color:#a5d6ff;white-space:pre-wrap;word-break:break-word}
video{width:100%;display:block;background:#000}
.小{display:flex;gap:8px;padding:7px 11px;border-top:1px solid var(--线);font-size:11.5px;color:var(--淡);
  align-items:center;flex-wrap:wrap}
.小 a{color:var(--亮);text-decoration:none}
.日志{background:#0d1117;border:1px solid var(--线);border-radius:7px;padding:9px 11px;margin-bottom:9px;
  font:12px/1.55 ui-monospace,Consolas,monospace;white-space:pre-wrap;max-height:210px;overflow:auto;color:#9fb0c0}
.日志 b{color:var(--淡);font-weight:600;display:block;margin-bottom:5px;font-family:inherit}
.大图{position:fixed;inset:0;background:#000d;display:none;align-items:center;justify-content:center;z-index:99;cursor:zoom-out}
.大图 img,.大图 video{max-width:96vw;max-height:94vh;object-fit:contain}
.大图.开{display:flex}
</style></head><body>
"""

页尾 = """
<div class="大图" id="大图" onclick="this.classList.remove('开')"></div>
<script>
function 放大(src,是视频){
  const d=document.getElementById('大图');
  d.innerHTML = 是视频 ? '<video src="'+src+'" controls autoplay></video>'
                       : '<img src="'+src+'">';
  d.classList.add('开');
}
// ★ 不能无条件 location.reload() —— 那会在你看视频、读剧本读到一半时把页面重置。
//   改成：每 5 秒问一次 /api，**只有状态真的变了才刷**（出了新段、多了新片）。
let 上次 = null;
async function 查变动(){
  try{
    const j = await (await fetch('/api?_=' + Date.now())).json();
    const k = [j.已出段, j.格数, j.片.length, j.检查图.length].join('/');
    if(上次 === null){ 上次 = k; return; }
    if(k !== 上次){
      上次 = k;
      document.getElementById('变动条').style.display = 'flex';
    }
  }catch(e){}
}
setInterval(查变动, 5000);
</script></body></html>
"""


def 渲(状):
    o = [页头]
    齐 = 状["已出段"]; 总 = 状["格数"] or 1
    百 = 齐 * 100 // 总
    o.append(
        f'<header><h1>影匠监工台 · 《{html.escape(状["戏"])}》</h1>'
        f'<span class="数">段 <b>{齐}</b>/{总}</span>'
        f'<div class="条"><i style="width:{百}%"></i></div>'
        f'<span class="数">{百}%</span>'
        f'<span class="数">台词 <b>{状.get("台词总", 0)}</b> 句</span>'
        f'<span class="数">刷新 {html.escape(状["时间"][11:])}</span></header>')
    o.append('<div id="变动条" style="display:none;position:sticky;top:56px;z-index:8;'
             'background:#17351f;border-bottom:1px solid #238636;padding:7px 18px;'
             'align-items:center;gap:14px;font-size:13px">'
             '<span style="color:#3fb950">有新的产出</span>'
             '<a href="#" onclick="location.reload();return false" '
             'style="color:#58a6ff">点这里刷新</a>'
             '<span style="color:#8b949e">（不点就不会打断你正在看的）</span></div>')
    o.append("<main>")

    if 状["缺格号"]:
        缺 = 状["缺格号"]
        示 = ", ".join("格%d" % n for n in 缺[:24]) + (" …" if len(缺) > 24 else "")
        o.append(f'<p style="color:var(--警)">还缺 {len(缺)} 格：{示}</p>')
    else:
        o.append('<p style="color:var(--好)">✓ 段全部出齐</p>')

    # ── 人物形象 ─────────────────────────────────────────────
    # ★ 用户 2026-10-14 原话：「我要能够看到你设计的人物形象」。
    #   在此之前「人物形象」在磁盘上只是 01-节拍拆解.md 里的一段文字，
    #   页面上从来没露过面 —— 这就是他直到现在才发现问题的原因之一。
    #
    # ★ 2026-10-15 补：`_出定妆照.py` 把锚点串变成了图，落在 `作品\<戏>\_定妆照\<角色>.png`。
    #   有图就贴图，没图就只写字（并明说「还没有图」）—— 不要假装有。
    if 状.get("锚点"):
        定 = os.path.join(根, "作品", 状["戏"], "_定妆照")
        o.append("<h2>人物形象（定妆照 + 每一格提示词里逐字复用的文字锚点）</h2>")
        o.append('<p style="color:var(--淡);margin:4px 0 12px">'
                 '左边是定妆照（<code>_出定妆照.py</code> 出的，正面半身像 + 正面全身像），'
                 '下面这段文字是出每一格首帧时<b>原样抄进提示词</b>的串 —— 人物靠它前后一致。</p>'
                 '<div class="网格">')
        for 角, 定位, 串 in 状["锚点"]:
            图 = ""
            for 后 in (".png", ".jpg", ".jpeg", ".webp"):
                p = os.path.join(定, 角 + 后)
                if os.path.isfile(p):
                    相对 = os.path.relpath(p, 根).replace("\\", "/")
                    图 = (f'<a href="/f?p={urllib.parse.quote(相对)}" target="_blank">'
                          f'<img src="/f?p={urllib.parse.quote(相对)}" '
                          f'style="width:100%;display:block;border-bottom:1px solid var(--线)" '
                          f'alt="{html.escape(角)}"></a>')
                    break
            if not 图:
                图 = ('<div style="padding:18px;text-align:center;color:var(--淡);'
                      'border-bottom:1px solid var(--线)">还没有定妆照<br>'
                      '<span style="font-size:11px">跑 <code>python _出定妆照.py '
                      + html.escape(状["戏"]) + '</code> 就有了</span></div>')
            o.append(f'<div class="卡">{图}<div class="头"><span class="号">{html.escape(角)}</span>'
                     f'<span class="签">{html.escape(定位[:26])}</span></div>'
                     f'<div class="体"><div class="行"><span class="键">定位</span>'
                     f'<span class="值">{html.escape(定位)}</span></div>'
                     f'<div class="行"><span class="键">锚点</span><span class="值" '
                     f'style="color:#a5d6ff">{html.escape(串)}</span></div></div></div>')
        o.append("</div>")

    # ── 剧本 ────────────────────────────────────────────────
    if 状.get("剧本"):
        o.append("<h2>剧本（这个故事到底是什么）</h2>")
        o.append('<p style="color:var(--淡);margin:4px 0 12px">'
                 '四份稿子从源头长出来：00 定故事 → 01 拆节拍 → 02 出每格提示词 → 03 定台词。'
                 '点开就能看原文。</p>')
        for d in 状["剧本"]:
            o.append(f'<details style="margin-bottom:9px"><summary style="cursor:pointer;'
                     f'padding:7px 11px;background:var(--卡);border:1px solid var(--线);'
                     f'border-radius:7px">{html.escape(d["标题"])}'
                     f'<span style="color:var(--淡);font-size:12px">　{d["kb"]} KB</span></summary>'
                     f'<div class="日志" style="max-height:520px;margin-top:6px">'
                     f'{html.escape(d["文"])}</div></details>')

    if 状["片"]:
        # ★ 片\ 里堆着 80 多个历史版本。全列出来页面会有 160 个 <video>，
        #   每 5 秒重刷一次 = 浏览器一直在拉元数据，卡到没法用。
        #   只列最大的 5 个（成品一定在里面），其余折起来给个链接。
        片s = 状["片"][:5]
        o.append(f"<h2>成片（共 {len(状['片'])} 个，列最大的 5 个）</h2><div class='网格'>")
        for f in 片s:
            o.append(
                f'<div class="卡"><div class="头"><span class="号">{html.escape(f["名"])}</span>'
                f'<span class="签 有">{f["mb"]} MB</span></div>'
                f'<video src="/f?p={urllib.parse.quote(f["路"])}" controls preload="none"></video>'
                f'<div class="小">{html.escape(f["改"])}</div></div>')
        o.append("</div>")

    if 状["检查图"]:
        o.append("<h2>检查图（联系表 / 底部条）</h2><div class='网格'>")
        for f in 状["检查图"][:8]:
            o.append(
                f'<div class="卡"><div class="头"><span class="号">{html.escape(f["名"])}</span>'
                f'<span class="签">{f["mb"]} MB</span></div>'
                f'<img class="图" style="aspect-ratio:auto;object-fit:contain;max-height:340px" '
                f'src="/f?p={urllib.parse.quote(f["路"])}" onclick="放大(this.src,false)">'
                f'<div class="小">{html.escape(f["改"])}</div></div>')
        o.append("</div>")

    o.append("<h2>每一格：喂进去的图 + 写进去的词 + 出来的片</h2><div class='网格'>")
    for d in 状["格"]:
        段 = d["段"]
        if 段:
            签 = '<span class="签 有">' + " + ".join(段) + "</span>"
        else:
            签 = '<span class="签 缺">未出</span>'
        o.append(f'<div class="卡"><div class="头"><span class="号">格 {d["号"]}</span>'
                 f'<span style="flex:1;color:var(--淡);font-size:12px;overflow:hidden;'
                 f'text-overflow:ellipsis;white-space:nowrap">{html.escape(d["题"])}</span>{签}</div>')
        if d["首帧"]:
            o.append(f'<img class="图" src="/f?p={urllib.parse.quote(d["首帧"])}" '
                     f'onclick="放大(this.src,false)" title="首帧 —— 喂进 H3 的那张图">')
        o.append('<div class="体">')
        o.append(f'<div class="行"><span class="键">景别</span><span class="值">{html.escape(d["景别"])}</span></div>')
        o.append(f'<div class="行"><span class="键">动作</span><span class="值">{html.escape(d["动作"])}</span></div>')
        # 台词：摆在这一格上，才能一眼看出「画面上演的」和「嘴里说的」对不对得上
        if d["台词"]:
            口 = "".join(
                f'<div style="margin:2px 0"><b style="color:#79c0ff">{html.escape(谁)}</b>　'
                f'{html.escape(说什么)}</div>' for 谁, 说什么, _ in d["台词"])
        else:
            口 = '<span style="color:var(--淡)">（这一格没有人说话）</span>'
        o.append(f'<div class="行"><span class="键">台词</span><span class="值">{口}</span></div>')
        o.append("<details><summary>首帧提示词（喂给出图那一步的原文）</summary>"
                 f'<div class="词">{html.escape(d["提示词"])}</div></details>')
        o.append(f'<div class="行"><span class="键">光色</span><span class="值" '
                 f'style="color:var(--淡)">{html.escape(d["光色"][:150])}</span></div>')
        if d.get("重点"):
            o.append(f'<details><summary>这一格要的是什么</summary>'
                     f'<div class="词" style="color:var(--淡)">{html.escape(d["重点"])}</div></details>')
        o.append("</div>")
        if 段:
            for 线, v in 段.items():
                # preload="none"：74 格 × 每个 2 MB，一重刷就全下等于把页面拖死。
                # 要看的点一下播放键，浏览器才去拉。
                o.append(f'<video src="/f?p={urllib.parse.quote(v["路"])}" controls '
                         f'preload="none" style="max-height:210px"></video>')
                o.append(f'<div class="小"><b>{线}</b>　{v["改"]}　{v["mb"]} MB</div>')
        for v in d["重抽"]:
            o.append(f'<div class="小">重抽 <a href="#" '
                     f'onclick="放大(\'/f?p={urllib.parse.quote(v["路"])}\',true);return false">'
                     f'{html.escape(v["名"])}</a>　{v["mb"]} MB　{v["改"]}</div>')
        o.append("</div>")
    o.append("</div>")

    if 状["日志"]:
        o.append("<h2>日志尾巴</h2>")
        for g in 状["日志"]:
            o.append(f'<div class="日志"><b>{html.escape(g["名"])}　{html.escape(g["改"])}</b>'
                     + html.escape("\n".join(g["行"])) + "</div>")

    o.append("</main>")
    o.append(页尾)
    return "".join(o)


# ─────────────────────────── HTTP ───────────────────────────

class 手(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _发(self, 码, 体, 型="text/html; charset=utf-8", 头=None):
        self.send_response(码)
        self.send_header("Content-Type", 型)
        self.send_header("Content-Length", str(len(体)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (头 or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(体)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)

        if u.path == "/":
            try:
                状 = 扫状态(戏)
            except Exception as e:
                self._发(500, f"<pre>扫状态出错：{type(e).__name__}: {e}</pre>".encode())
                return
            self._发(200, 渲(状).encode("utf-8"))
            return

        if u.path == "/api":
            self._发(200, json.dumps(扫状态(戏), ensure_ascii=False, indent=1).encode("utf-8"),
                      "application/json; charset=utf-8")
            return

        if u.path == "/f":
            相 = (q.get("p") or [""])[0]
            if not 相:
                self._发(400, b"no p")
                return
            # ★ 只允许工作区内的、白名单后缀的文件 —— 这是个本机服务，别把它做成任意文件读取
            绝 = os.path.realpath(os.path.join(根, 相))
            if not 绝.startswith(os.path.realpath(根) + os.sep) or \
                    os.path.splitext(绝)[1].lower() not in 允许后缀 or not os.path.isfile(绝):
                self._发(403, b"forbidden")
                return
            型 = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                  ".webp": "image/webp", ".gif": "image/gif", ".mp4": "video/mp4"}[
                os.path.splitext(绝)[1].lower()]
            大小 = os.path.getsize(绝)
            起, 止 = 0, 大小 - 1
            码 = 200
            范围 = self.headers.get("Range")
            if 范围:
                m = re.match(r"bytes=(\d*)-(\d*)", 范围)
                if m:
                    起 = int(m.group(1) or 0)
                    止 = int(m.group(2) or 止)
                    码 = 206
            长 = 止 - 起 + 1
            头 = {"Accept-Ranges": "bytes"}
            if 码 == 206:
                头["Content-Range"] = f"bytes {起}-{止}/{大小}"
            self.send_response(码)
            self.send_header("Content-Type", 型)
            self.send_header("Content-Length", str(长))
            self.send_header("Cache-Control", "no-store")
            for k, v in 头.items():
                self.send_header(k, v)
            self.end_headers()
            try:
                with open(绝, "rb") as f:
                    f.seek(起)
                    剩 = 长
                    while 剩 > 0:
                        块 = f.read(min(1 << 20, 剩))
                        if not 块:
                            break
                        self.wfile.write(块)
                        剩 -= len(块)
            except (BrokenPipeError, ConnectionAbortedError):
                pass
            return

        self._发(404, b"not found")


戏 = "觉醒"


def main():
    global 戏
    ap = argparse.ArgumentParser()
    ap.add_argument("--戏", default="觉醒")
    ap.add_argument("--口", type=int, default=8791)
    ap.add_argument("--不开", action="store_true", help="不自动开浏览器")
    参 = ap.parse_args()
    戏 = 参.戏

    if not os.path.isdir(os.path.join(作品, 戏)):
        print(f"  ✗ 没有 作品\\{戏}\\")
        return 1

    srv = ThreadingHTTPServer(("127.0.0.1", 参.口), 手)
    址 = f"http://127.0.0.1:{参.口}/"
    print(f"  影匠监工台 → {址}")
    print(f"  戏：《{戏}》　按 Ctrl+C 停")
    if not 参.不开:
        def 开():
            time.sleep(0.6)
            try:
                os.startfile(址)
            except Exception:
                pass
        threading.Thread(target=开, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  停了")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
