# -*- coding: utf-8 -*-
"""记忆监工台 —— 让你看见「我到底记住了什么、读的是什么、欠你什么」。

## 为什么要有这个东西

用户 2026-10-15 原话：

    你能不能给我做一个简单的软件也好、界面也好、或者工具也好，
    能让我可视化的看见你存储的记忆、我们对话的档案、
    以及各类的你所遇到的问题踩过的坑、以及每一次明确的你的阅读的链路？
    不然的话，我没有办法确定你给现在给我说的这些东西，你以后到底还记不记得。
    你能不能把它做成？插件也好，代码仓也好，别的什么也好，
    反正要我能清晰明确简单看到的、你以后也能记得的、并且能够确定读取的、确定使用的。
    这样之后我才敢继续给你派活。

## ★ 四条设计原则（都是被坑出来的）

1. **阅读链路不许我自己上报。** 我说「我读了 AGENTS.md」你没法验证。
   → 全部从 `D:\\DSH\\home\\sessions\\**\\session.v4.jsonl.zstd` 的
     `tool/call` 记录里挖。**那是 DSH 写的，我改不了。**
2. **不假装有。** 没有的东西就显示「没有」，不显示一个好看的 0。
3. **只读。** 这个台子挂了，影匠和生产脚本照样跑。
4. **能一眼看完。** 页面第一屏必须回答「我欠你几条 / 我这次读了什么」。

## 起

    python _记忆台.py                # 默认 127.0.0.1:8792
    python _记忆台.py --口 8800
    python _记忆台.py --重扫          # 丢掉缓存，重新挖全部会话
    python _记忆台.py --不开          # 只扫一遍打印统计，不起服务

配 `开记忆台.cmd`（**必须存 GBK**，cmd.exe 按 GBK 解码）。
"""
import argparse
import collections
import glob
import io
import json
import os
import re
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

根 = os.path.dirname(os.path.abspath(__file__))
会话根 = r"D:\DSH\home\sessions\--D-DSHworkspace--"
缓存 = os.path.join(根, "_记忆台_缓存.json")

# 这些工具算「读」—— 它们会往我上下文里灌东西
读工具 = {
    "read": "文件",
    "grep": "搜内容",
    "glob": "搜文件名",
    "decompress": "解压折叠",
    "search_context": "搜折叠摘要",
    "acp_status": "看上下文",
    "web_fetch": "抓网页",
    "read_page": "读网页",
    "cache_search": "搜网页缓存",
    "webfetch": "抓网页",
}
# 这些不算读（是写 / 是算 / 是等）
不算读 = {
    "write", "edit", "present", "pwsh", "job_output", "job_kill", "job_list",
    "todo_write", "compress", "skill", "create_goal", "get_goal", "update_goal",
    "schedule_create", "schedule_list", "schedule_delete", "schedule_update",
    "send_message", "spawn_teammate", "wait_agent", "list_agents",
    "interrupt_agent", "team_task_create", "team_task_get", "team_task_list",
    "team_task_update", "subagent", "subagent_fork", "workflow",
    "ask_user_question", "browser_session", "browser_page", "browser_inspect",
    "browser_interact", "browser_tabs", "browser_assist", "present",
}


# ══════════════════════════════════════════════════════════════
#  一、扫会话存档 → 阅读链路
# ══════════════════════════════════════════════════════════════
def 挖一场(路):
    """从一场会话的 jsonl.zstd 里挖出：读了什么、搜了什么、问了几轮。"""
    try:
        import zstandard as zstd
    except ImportError:
        return None
    出 = {"读": [], "轮": 0, "用户": [], "工具数": 0, "起": None, "止": None,
          "字节": os.path.getsize(路)}
    try:
        d = zstd.ZstdDecompressor()
        txt = d.stream_reader(open(路, "rb")).read().decode("utf-8", "replace")
    except Exception as e:
        出["坏"] = str(e)[:80]
        return 出
    for l in txt.split("\n"):
        if not l.strip():
            continue
        try:
            o = json.loads(l)
        except Exception:
            continue
        t = o.get("type")
        if t == "session":
            出["起"] = o.get("createdAt")
            出["id"] = o.get("id", "")
        elif t == "user/message":
            d2 = o.get("data") or {}
            文 = _文本(d2.get("message") or d2)
            if 文 and 文.strip():
                出["用户"].append(文.strip()[:300])
        elif t == "tool/call":
            d2 = o.get("data") or {}
            名 = d2.get("name") or ""
            出["工具数"] += 1
            if 名 in 读工具:
                try:
                    参 = json.loads(d2.get("arguments") or "{}")
                except Exception:
                    参 = {}
                目 = (参.get("file_path") or 参.get("path") or 参.get("query")
                      or 参.get("url") or "")
                出["读"].append({
                    "时": o.get("time"),
                    "名": 名,
                    "目": str(目)[:220],
                     "轮": d2.get("turn"),
                })
        elif t == "turn/start":
            出["轮"] += 1
    # ★ 子代理的「用户消息」其实是主代理发的任务书，不是用户本人的话。
    #   识别：第一条用户消息以 You are / Reply with exactly 开头，或者整场 0 次工具调用。
    首 = (出["用户"][0] if 出["用户"] else "")
    出["子代理"] = bool(
        re.match(r"^\s*(You are|Your task|Reply with exactly|你是)", 首)
        or (出["工具数"] == 0 and 出["轮"] <= 2)
    )
    # 用户本人的话：滤掉子代理任务书那种
    出["用户"] = [u for u in 出["用户"]
                 if not re.match(r"^\s*(You are|Your task|Reply with exactly|你是)", u)]
    return 出


def _文本(m):
    if isinstance(m, str):
        return m
    if isinstance(m, dict):
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def 扫全部会话(重扫=False):
    if not 重扫 and os.path.isfile(缓存):
        try:
            c = json.load(open(缓存, encoding="utf-8"))
            if c.get("场数") == len(glob.glob(os.path.join(会话根, "*", "session.v4.jsonl.zstd"))):
                return c
        except Exception:
            pass
    场s = sorted(glob.glob(os.path.join(会话根, "*", "session.v4.jsonl.zstd")),
                 key=os.path.getmtime)
    出 = {"场数": len(场s), "场": [], "扫于": time.time()}
    for i, p in enumerate(场s, 1):
        r = 挖一场(p)
        if r:
            r["目录"] = os.path.basename(os.path.dirname(p))
            出["场"].append(r)
        if i % 20 == 0:
            print("    扫了 %d/%d 场" % (i, len(场s)))
    with open(缓存, "w", encoding="utf-8") as f:
        json.dump(出, f, ensure_ascii=False)
    return 出


# ══════════════════════════════════════════════════════════════
#  二、扫记忆各层
# ══════════════════════════════════════════════════════════════
def 层(名, 路们, 自动, 说明):
    总 = 0
    份 = []
    for 路 in 路们:
        if os.path.isfile(路):
            份.append(路)
        elif os.path.isdir(路):
            份 += [f for f in glob.glob(os.path.join(路, "**", "*"), recursive=True)
                   if os.path.isfile(f)]
    for f in 份:
        try:
            总 += os.path.getsize(f)
        except OSError:
            pass
    return {
        "名": 名, "自动": 自动, "说明": 说明,
        "份数": len(份), "字节": 总, "词": round(总 / 2.6),
        "文件": sorted(份),
    }


def 扫记忆层():
    W = 根
    出 = [
        层("工作区指令", [os.path.join(W, "AGENTS.md")], True,
           "DSH 每次会话自动注入 —— 我躲不掉，也改不了它进不进"),
        层("开工自查", [os.path.join(W, "_开工.py")], True,
           "不是自动的，是 AGENTS.md 里写着「第一件事跑它」。输出跳不过去"),
        层("要求台账", [os.path.join(W, "要求台账.md")],
           False, "你翻的表；我开局不读全文，_开工.py 只打欠账那几行"),
        层("交接状态", [os.path.join(W, "接续.md")], False,
           "★ 38 KB —— 我前几天一直整份读，是纯浪费。该只读 §零"),
        层("踩坑知识", [os.path.join(W, "影匠", "知识")], False,
           "155 份。开局一份都不读；遇到那个坑时只读那一份"),
        层("攒的经验", [os.path.join(W, "记忆", "经验")], False,
           "★ 一行一条，只追加。做完一件事就往这儿添 —— 这是我唯一会「长大」的地方"),
        层("★ 犯过的病", [os.path.join(W, "记忆", "模式.md")], False,
           "`_找复发.py` 数出来的「犯过两次以上」的毛病。"
           "★ 这一份就是回答你那句「记住你前面出现过的所有问题，我不想再看见了」——"
           "单次是事故，重复才是病"),
        层("长期记忆", [os.path.join(W, ".memsearch", "memory")], False,
           "MemSearch 插件写的，按天"),
        层("对话档案", [os.path.join(W, "记忆", "对话")], False,
           "99 场会话挖出来的原文。是档案，不是读物 —— 用查的"),
    ]
    return 出


def 主题(名):
    """把知识文件归到一个大类 —— 为了以后几百份的时候还能查。

    ★ 为什么要有这个：用户 2026-10-15 01:04 问
    「才这么多的这个什么 30 多个账，90 多个存档。那么以后更多的时候怎么办呢？
    我怎么查的，我怎么看呢？」
    一长条列表在 30 份时能看，300 份时就是垃圾。**必须分组。**
    """
    表 = [
        ("画面与镜头", "字幕 假字幕 运动 动 图片 镜头 分镜 锚点 锁脸 角色 构图 一致性 景别 首帧 尾帧"),
        ("提示词", "提示词 写法 模型 采样 参数 种子 LoRA 节点 工作流"),
        ("声音", "配音 音 TTS 语音 台词 混音 音乐"),
        ("流程与脚本", "脚本 流程 判据 假 检查 核对 台账 缓存 端口 进程 拼 成片"),
        ("存储与系统", "盘 硬链 删除 空间 内存 显存 装 备份 路径"),
        ("协作与规矩", "规矩 用户 要求 汇报 代理 团队 审核"),
    ]
    for 类, 词s in 表:
        for w in 词s.split():
            if w in 名:
                return 类
    return "其他"


def 扫经验():
    """`记忆\\经验\\*.md` —— 每做完一件事往这里追加的沉淀。

    ★ 用户 2026-10-15 01:04 的要求原文：
    「他需要是一个能够迭代的。你比如说我给你安排完了某些任务，做完某些东西之后，
    你得把你的经验或者知识什么东西都得有存储的。」
    """
    目 = os.path.join(根, "记忆", "经验")
    出 = []
    if os.path.isdir(目):
        for p in sorted(glob.glob(os.path.join(目, "*.md"))):
            行s = []
            try:
                with io.open(p, encoding="utf-8", errors="replace") as f:
                    行s = f.read().splitlines()
            except Exception:
                pass
            条 = [l for l in 行s if l.strip().startswith("- ")]
            出.append({"名": os.path.basename(p)[:-3], "路": p,
                       "条数": len(条), "字节": os.path.getsize(p),
                       "改": os.path.getmtime(p), "行s": 行s})
    return 出


def 扫坑():
    """踩坑知识 —— 文件名 + 首行一句话 + 主题。"""
    出 = []
    for p in sorted(glob.glob(os.path.join(根, "影匠", "知识", "*.md"))):
        头 = ""
        try:
            with io.open(p, encoding="utf-8", errors="replace") as f:
                for l in f:
                    l = l.strip()
                    if l and not l.startswith("#") and not l.startswith(">"):
                        头 = l[:150]
                        break
                    if l.startswith("#"):
                        头 = l.lstrip("# ").strip()[:150]
                        break
        except Exception:
            pass
        名 = os.path.basename(p)
        出.append({"名": 名, "路": p,
                   "字节": os.path.getsize(p), "头": 头,
                   "题": 主题(名),
                   "改": os.path.getmtime(p)})
    return 出


def 扫欠账():
    """从 要求台账.md 里数出没打勾的条目。"""
    p = os.path.join(根, "要求台账.md")
    if not os.path.isfile(p):
        return {"有": False, "条": [], "数": {}}
    so = io.open(p, encoding="utf-8", errors="replace").read()
    so = so.split("## §〇")[0] if "## §〇" in so else so
    条 = []
    for m in re.finditer(r"^\|\s*([^|]{2,60}?)\s*\|\s*([^|]{2,200}?)\s*\|\s*(✅|🟡|✗|⛔)",
                         so, re.M):
        条.append({"时": m.group(1).strip(), "要求": m.group(2).strip(),
                   "状": m.group(3)})
    数 = collections.Counter(x["状"] for x in 条)
    return {"有": True, "条": 条, "数": dict(数),
            "没做": [x for x in 条 if x["状"] in ("🟡", "✗")]}


def 扫画像():
    """从 _用户原话.json + 用户画像.md 读「他要什么 / 他反感什么 / 他说过我没做的」。

    ★ 为什么要有这一块：他 2026-10-15 00:49 说
    「我想要的是。越聪明，越用越懂我的 1 个 AI 助手。不是每一次都像重头来过……
    每一次我都要花费这么长的时间，这么多的精力来纠正你的错误的一个。打杂的。」
    原话清单是这一页最该摆在最上面的东西 —— 它比「欠账」还靠前。
    """
    根 = os.path.dirname(os.path.abspath(__file__))
    原话路 = os.path.join(根, "_用户原话.json")
    画像路 = os.path.join(根, "用户画像.md")
    出 = {"有": False, "原话": [], "按天": {}, "篇数": 0, "起": 0, "止": 0}
    if os.path.isfile(原话路):
        try:
            with io.open(原话路, encoding="utf-8") as f:
                数据 = json.load(f)
            条 = 数据 if isinstance(数据, list) else 数据.get("条", [])
            for x in 条:
                t = x.get("时") or x.get("time") or 0
                文 = x.get("话") or x.get("文") or x.get("text") or ""
                if not 文:
                    continue
                出["原话"].append({"时": t, "文": 文})
            出["原话"].sort(key=lambda z: z["时"])
            if 出["原话"]:
                出["起"] = 出["原话"][0]["时"]
                出["止"] = 出["原话"][-1]["时"]
                天 = collections.Counter(
                    time.strftime("%m-%d", time.localtime(z["时"] / 1000))
                    for z in 出["原话"])
                出["按天"] = dict(sorted(天.items()))
            出["有"] = True
        except Exception as e:
            出["错"] = str(e)
    if os.path.isfile(画像路):
        出["篇数"] = os.path.getsize(画像路)
        出["画像路"] = 画像路
    return 出


# ══════════════════════════════════════════════════════════════
#  三、页面
# ══════════════════════════════════════════════════════════════
CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0f1115;color:#d8dee9;font:14px/1.62 "Segoe UI","Microsoft YaHei",sans-serif}
a{color:#7fb3ff;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1500px;margin:0 auto;padding:16px}
h1{font-size:19px;margin:0 0 4px}h2{font-size:15px;margin:26px 0 8px;padding-left:9px;
   border-left:3px solid #4a9eff;color:#eaf1f8}
.条{margin:2px 0 4px;color:#8b98a8;font-size:12.5px}
.grid{display:grid;gap:10px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:5px 8px;border-bottom:1px solid #232833;text-align:left;vertical-align:top}
th{color:#8b98a8;font-weight:600;font-size:12px}
tr:hover td{background:#171b24}
.卡{background:#151922;border:1px solid #232833;border-radius:8px;padding:11px 13px}
.数{font-size:22px;font-weight:700}
.红{color:#ff7b72}.黄{color:#e3b341}.绿{color:#56d364}.灰{color:#7d8590}
.签{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11.5px;
     border:1px solid #30363d;margin-right:5px}
.签自{background:#1f3d2b;border-color:#2ea043;color:#7ee787}
.签按{background:#3d3520;border-color:#9e6a03;color:#e3b341}
.目{font-family:Consolas,monospace;font-size:12px;color:#a5d6ff;word-break:break-all}
.时{font-family:Consolas,monospace;font-size:11.5px;color:#6e7681;white-space:nowrap}
details{background:#151922;border:1px solid #232833;border-radius:8px;margin:5px 0}
summary{cursor:pointer;padding:8px 12px;font-weight:600;color:#c9d1d9}
summary:hover{background:#1a1f29}
.内{padding:4px 14px 12px;border-top:1px solid #232833}
pre{background:#0b0e13;border:1px solid #232833;border-radius:6px;padding:10px;
    overflow:auto;max-height:460px;font-size:12px;color:#c9d1d9;white-space:pre-wrap}
.栏{position:sticky;top:0;background:#0f1115ee;backdrop-filter:blur(6px);
     padding:10px 0;z-index:9;border-bottom:1px solid #232833;margin-bottom:8px}
input[type=text]{background:#0b0e13;border:1px solid #30363d;color:#d8dee9;
     padding:5px 9px;border-radius:6px;font-size:13px;width:280px}
.流{max-height:560px;overflow:auto;border:1px solid #232833;border-radius:8px}
.流行{display:grid;grid-template-columns:96px 78px 1fr;gap:8px;padding:3px 10px;
      border-bottom:1px solid #1b2029;font-size:12.5px}
.流行:hover{background:#171b24}
.流行.搜{background:#151c26}
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def 时间戳(ms):
    if not ms:
        return "—"
    return time.strftime("%m-%d %H:%M", time.localtime(ms / 1000))


def 页首():
    return ('<!doctype html><html lang="zh"><head><meta charset="utf-8">'
            '<title>记忆监工台</title><style>' + CSS + '</style></head><body><div class="wrap">')


def 页尾():
    return ('</div><script>'
            'function 筛(q){q=q.toLowerCase();'
            'document.querySelectorAll("[data筛]").forEach(function(e){'
            'e.style.display=e.dataset.筛.toLowerCase().indexOf(q)>=0?"":"none";});}'
            '</script></body></html>')


def 渲染(会, 层s, 坑s, 账, 像=None, 经s=None):
    W = []
    W.append(页首())
    W.append('<h1>记忆监工台</h1>')
    W.append('<div class="条">这一页回答一个问题：<b>我到底记住了什么、读的是什么、欠你什么。</b>'
             '　阅读链路不是我上报的 —— 是从 <span class="目">D:\\DSH\\home\\sessions\\</span> '
             '里 DSH 自己写的 <span class="目">tool/call</span> 记录里挖出来的，我改不了。</div>')

    # ── 全局搜索（一个框搜全页：你的原话 / 欠账 / 我翻的文件 / 坑 / 经验）
    W.append('<div class="栏" style="margin-top:10px">'
             '<input type="text" id="全搜" placeholder="一个框搜全页：你的原话 · 欠账 · '
             '我翻的文件 · 坑 · 经验" style="width:520px" oninput="筛全(this.value)">'
             '　<span class="条" id="搜果"></span></div>')
    W.append('<script>'
             'function 筛全(q){q=(q||"").trim().toLowerCase();var n=0,t=0;'
             'document.querySelectorAll("[data-筛]").forEach(function(e){'
             't++;var hit=!q||e.dataset.筛.toLowerCase().indexOf(q)>=0;'
             'e.style.display=hit?"":"none";if(hit&&q)n++;});'
             'var o=document.getElementById("搜果");'
             'o.textContent=q?("命中 "+n+" / "+t+" 条"):("全页 "+t+" 条可搜");}'
             'window.addEventListener("DOMContentLoaded",function(){筛全("");});'
             '</script>')

    # ── ★ 零：他要什么（摆在最前面 —— 比「欠账」还靠前）
    if 像 and 像.get("有"):
        W.append('<h2>零、你说过的话 <span class="条">（%d 条本人发言，'
                 '%s → %s；从会话存档里挖的，滤掉了系统注入）</span></h2>'
                 % (len(像["原话"]), 时间戳(像["起"]), 时间戳(像["止"])))
        W.append('<div class="条">'
                 '<b>他要什么</b>：看得见（12 次／4 天）· 能自己操作（4 次）· '
                 '直白谁都能看懂（5 次）· 对 token 算得清（6 次）· 用现成的别重画（5 次）'
                 '　｜　<b>他反感</b>：偷加条件 · 文学腔玄乎 · 思考刷空转 · 自作主张 · '
                 '不给他审核 · 要管理员权限 · 占满机器'
                 '　｜　全文 <span class="目">用户画像.md</span>（%s B）</div>'
                 % f"{像.get('篇数', 0):,}")
        W.append('<div class="条">按天：' + '　'.join(
            '%s <b>%d</b>' % (k, v) for k, v in 像.get("按天", {}).items()) + '</div>')
        W.append('<div class="栏"><input type="text" placeholder="搜你的原话…" '
                 'oninput="筛(this.value)"></div>')
        W.append('<div class="流">')
        for i, x in enumerate(像["原话"]):
            文 = x["文"]
            W.append('<div class="流行" data-筛="%s"><span class="时">%s</span>'
                     '<span class="时">#%d</span><span>%s</span></div>'
                     % (esc(文[:400]), 时间戳(x["时"]), i + 1, esc(文[:400])))
        W.append('</div>')

    # ── 第一屏：三个数
    自 = [x for x in 层s if x["自动"]]
    按 = [x for x in 层s if not x["自动"]]
    账数 = 账.get("数", {})
    没 = 账数.get("🟡", 0) + 账数.get("✗", 0)
    W.append('<div class="grid" style="grid-template-columns:repeat(4,1fr);margin-top:12px">')
    W.append('<div class="卡"><div class="条">欠你的账（没打勾）</div>'
             '<div class="数 %s">%d</div><div class="条">✅ %d ／ 🟡 %d ／ ✗ %d ／ ⛔ %d</div></div>'
             % ("红" if 没 else "绿", 没, 账数.get("✅", 0), 账数.get("🟡", 0),
                账数.get("✗", 0), 账数.get("⛔", 0)))
    W.append('<div class="卡"><div class="条">每次会话我必读（躲不掉）</div>'
             '<div class="数 黄">%s</div><div class="条">token，就算我什么都不干也要付</div></div>'
             % f"{sum(x['词'] for x in 自):,}")
    W.append('<div class="卡"><div class="条">按需读（开局一个都不读）</div>'
             '<div class="数">%s</div><div class="条">token，%d 组文件</div></div>'
             % (f"{sum(x['词'] for x in 按):,}", len(按)))
    W.append('<div class="卡"><div class="条">会话存档</div>'
             '<div class="数">%d</div><div class="条">场，%s</div></div>'
             % (会.get("场数", 0),
                time.strftime("%m-%d %H:%M", time.localtime(会.get("扫于", 0)))))
    W.append('</div>')

    # ── 欠账
    W.append('<h2>一、欠你的账 <span class="条">（原话对齐；判 ✅ 必须能指出磁盘路径）</span></h2>')
    if not 账.get("有"):
        W.append('<div class="条 红">找不到 要求台账.md</div>')
    else:
        W.append('<div class="条">' + '　'.join(
            '<span class="签">%s %d</span>' % (k, v) for k, v in 账数.items()) + '</div>')
        W.append('<table><tr><th style="width:90px">时间</th><th>你说过的</th>'
                 '<th style="width:56px">状态</th></tr>')
        for x in 账["条"]:
            色 = {"✅": "绿", "🟡": "黄", "✗": "红", "⛔": "灰"}.get(x["状"], "")
            W.append('<tr data-筛="%s"><td class="时">%s</td><td>%s</td>'
                     '<td class="%s">%s</td></tr>'
                     % (esc(x["要求"]), esc(x["时"]), esc(x["要求"]), 色, x["状"]))
        W.append('</table>')

    # ── 阅读链路
    W.append('<h2>二、我干活时翻过哪些文件 <span class="条">（证据，不是我上报的）</span></h2>')
    W.append('<div class="条">'
             '我说「我读了你的知识文件、我记得那个坑」—— <b>口说无凭，你没法验证。</b>'
             '这一栏不是我写的，是 <span class="目">DSH</span> 在我每次调用工具时自己记下的，'
             '<b>我改不了，也删不掉</b>。所以它能当证据用：<br>'
             '　· 我说「我查过了」→ 你能看见我到底开没开那个文件<br>'
             '　· 我说「这是个老坑」→ 你能看见我这一场<b>根本一次都没翻过坑文件</b><br>'
             '　· 下一场会话我也能自己看：<b>上次我是真读了，还是在瞎说</b><br>'
             '<span class="灰">（旧名字叫「阅读链路」，太难懂，改了。）</span></div>')
    主 = [f for f in 会.get("场", []) if not f.get("子代理")]
    子 = [f for f in 会.get("场", []) if f.get("子代理")]
    有读 = [f for f in 主 if f.get("读")]
    W.append('<div class="条">%d 场里有 <b>%d 场是真会话</b>（%d 场挖出了「读」记录），'
             '另外 %d 场是子代理的任务书，不是我们说过的。'
             '按时间倒序，每行 = 一次工具调用。</div>'
             % (会.get("场数", 0), len(主), len(有读), len(子)))
    场s = sorted(有读, key=lambda x: (x.get("起") or 0), reverse=True)
    if not 场s:
        场s = sorted(主, key=lambda x: (x.get("起") or 0), reverse=True)
    for f in 场s[:15]:
        读s = f.get("读", [])
        标 = "%s　读 %d 次　工具 %d 次　轮 %d　对话 %d 条" % (
            时间戳(f.get("起")), len(读s), f.get("工具数", 0),
            f.get("轮", 0), len(f.get("用户", [])))
        W.append('<details data-筛="%s"><summary>%s</summary><div class="内">' % (
            esc(f.get("目录", "")), esc(标)))
        W.append('<div class="条">%s　%.1f MB</div>' % (
            esc(f.get("目录", "")), f.get("字节", 0) / 1048576))
        if 读s:
            W.append('<div class="流">')
            for r in 读s:
                W.append('<div class="流行 搜"><span class="时">%s</span>'
                         '<span class="签">%s</span>'
                         '<span class="目">%s</span></div>'
                         % (time.strftime("%H:%M:%S", time.localtime((r["时"] or 0) / 1000)),
                            esc(读工具.get(r["名"], r["名"])), esc(r["目"])))
            W.append('</div>')
        else:
            W.append('<div class="条 灰">这一场没有「读」类调用。</div>')
        if f.get("用户"):
            W.append('<div class="条" style="margin-top:8px">你那场说过的话：</div><pre>%s</pre>'
                     % esc("\n\n".join("· " + u for u in f["用户"][:14])))
        W.append('</div></details>')

    # ── 记忆分层
    W.append('<h2>三、记忆分层 <span class="条">（读它的成本就是它的价格）</span></h2>')
    W.append('<table><tr><th style="width:110px">层</th><th style="width:76px">进上下文</th>'
             '<th style="width:88px">份数</th><th style="width:110px">读一遍</th>'
             '<th>说明</th></tr>')
    for x in 层s:
        W.append('<tr data-筛="%s %s"><td><b>%s</b></td><td>%s</td><td>%d</td>'
                 '<td class="时">%s 字 ≈ %s tok</td><td>%s</td></tr>'
                 % (esc(x["名"]), esc(x["说明"]), esc(x["名"]),
                    '<span class="签 签自">自动</span>' if x["自动"]
                    else '<span class="签 签按">按需</span>',
                    x["份数"], f"{x['字节']:,}", f"{x['词']:,}", esc(x["说明"])))
    W.append('</table>')

    # ── 踩坑（按主题分组）
    题s = collections.OrderedDict()
    for x in 坑s:
        题s.setdefault(x["题"], []).append(x)
    W.append('<h2>四、踩过的坑 <span class="条">（%d 份，分 %d 类 —— '
             '以后涨到几百份也这么查）</span></h2>' % (len(坑s), len(题s)))
    W.append('<div class="条">点类别展开。' + '　'.join(
        '<b>%s</b> %d' % (k, len(v)) for k, v in 题s.items()) + '</div>')
    for 类, 项s in 题s.items():
        W.append('<details data-筛="%s"><summary>%s　<span class="条">%d 份</span></summary>'
                 '<div class="内"><table>'
                 '<tr><th style="width:230px">文件</th><th>它讲什么（首行）</th>'
                 '<th style="width:110px">改于</th></tr>' % (esc(类), esc(类), len(项s)))
        for x in sorted(项s, key=lambda z: -z["改"]):
            W.append('<tr data-筛="%s %s"><td><a href="/f?p=%s">%s</a></td>'
                     '<td>%s</td><td class="时">%s</td></tr>'
                     % (esc(x["名"]), esc(x["头"]),
                        urllib.parse.quote(os.path.relpath(x["路"], 根).replace("\\", "/")),
                        esc(x["名"]), esc(x["头"]), 时间戳(x["改"] * 1000)))
        W.append('</table></div></details>')

    # ── 沉淀（经验）
    W.append('<h2>五、攒下来的经验 <span class="条">（做完一件事就往这里追加，只加不改）</span></h2>')
    if not 经s:
        W.append('<div class="条 黄">还没有 —— 目录 <span class="目">记忆\\经验\\</span> '
                 '一个文件都没有。规矩：<b>每做完一件事，往对应的主题文件里追加一行</b>'
                 '（一行 = 一句教训 + 一句判据）。</div>')
    else:
        W.append('<div class="条">%d 个主题，共 %d 条。'
                 '一行一条，只追加不覆盖 —— 所以它<b>能迭代</b>。</div>'
                 % (len(经s), sum(x["条数"] for x in 经s)))
        for x in sorted(经s, key=lambda z: -z["改"]):
            W.append('<details data-筛="%s"><summary>%s　<span class="条">%d 条　%s</span>'
                     '</summary><div class="内"><pre>%s</pre></div></details>'
                     % (esc(x["名"]), esc(x["名"]), x["条数"],
                        时间戳(x["改"] * 1000), esc("\n".join(x["行s"]))))

    W.append(页尾())
    return "".join(W)


# ══════════════════════════════════════════════════════════════
#  四、HTTP
# ══════════════════════════════════════════════════════════════
白名单 = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".md", ".txt", ".json", ".srt"}


class 服务(BaseHTTPRequestHandler):
    会 = {}
    层s = []
    坑s = []
    账 = {}

    def log_message(self, *a):
        pass

    def _发(self, 码, 型, 体):
        self.send_response(码)
        self.send_header("Content-Type", 型)
        self.send_header("Content-Length", str(len(体)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(体)
        except Exception:
            pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            h = 渲染(self.会, self.层s, self.坑s, self.账,
                     getattr(self, "像", None), getattr(self, "经s", None))
            self._发(200, "text/html; charset=utf-8", h.encode("utf-8"))
        elif u.path == "/api":
            像 = getattr(self, "像", None) or {}
            j = {
                "场数": self.会.get("场数"),
                "扫于": self.会.get("扫于"),
                "层": [{k: v for k, v in x.items() if k != "文件"} for x in self.层s],
                "坑数": len(self.坑s),
                "账": self.账.get("数", {}),
                "没做": self.账.get("没做", []),
                "原话数": len(像.get("原话", [])),
                "原话按天": 像.get("按天", {}),
                "原话起": 像.get("起"),
                "原话止": 像.get("止"),
                "场": [{k: v for k, v in f.items() if k != "用户"}
                       for f in self.会.get("场", [])],
            }
            self._发(200, "application/json; charset=utf-8",
                     json.dumps(j, ensure_ascii=False).encode("utf-8"))
        elif u.path == "/f":
            q = urllib.parse.parse_qs(u.query).get("p", [""])[0]
            真 = os.path.realpath(os.path.join(根, q))
            if not 真.startswith(os.path.realpath(根)):
                return self._发(403, "text/plain", b"403")
            if os.path.splitext(真)[1].lower() not in 白名单:
                return self._发(403, "text/plain", b"403")
            if not os.path.isfile(真):
                return self._发(404, "text/plain", b"404")
            体 = open(真, "rb").read()
            型 = {".md": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8",
                  ".json": "application/json", ".srt": "text/plain; charset=utf-8",
                  ".mp4": "video/mp4", ".png": "image/png", ".jpg": "image/jpeg",
                  ".jpeg": "image/jpeg", ".webp": "image/webp",
                  ".gif": "image/gif"}.get(os.path.splitext(真)[1].lower(), "application/octet-stream")
            self._发(200, 型, 体)
        else:
            self._发(404, "text/plain", b"404")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--口", type=int, default=8792)
    ap.add_argument("--重扫", action="store_true", help="丢掉缓存，重新挖全部会话")
    ap.add_argument("--不开", action="store_true", help="只扫一遍打印统计，不起服务")
    参 = ap.parse_args()

    print("  ══ 记忆监工台")
    print("  ── 挖会话存档（%s）" % 会话根)
    会 = 扫全部会话(参.重扫)
    读总 = sum(len(f.get("读", [])) for f in 会.get("场", []))
    print("  %d 场　读类调用共 %d 次" % (会.get("场数", 0), 读总))

    层s = 扫记忆层()
    坑s = 扫坑()
    账 = 扫欠账()
    像 = 扫画像()
    经s = 扫经验()
    if 像.get("有"):
        print("    你的原话 %d 条（%s → %s）" % (
            len(像["原话"]), 时间戳(像["起"]), 时间戳(像["止"])))
        print("      按天：" + "　".join("%s %d" % (k, v) for k, v in 像["按天"].items()))
    else:
        print("    ⚠ 找不到 _用户原话.json（先跑 python _用户原话.py）")
    for x in 层s:
        print("    %-10s %-4s %4d 份  %10s 字 ≈ %9s tok" % (
            x["名"], "自动" if x["自动"] else "按需", x["份数"],
            f"{x['字节']:,}", f"{x['词']:,}"))
    print("    坑 %d 份　台账 %d 条（没打勾 %d）" % (
        len(坑s), len(账.get("条", [])),
        len(账.get("没做", []))))

    if 参.不开:
        return 0

    服务.会, 服务.层s, 服务.坑s, 服务.账, 服务.像, 服务.经s = 会, 层s, 坑s, 账, 像, 经s
    srv = ThreadingHTTPServer(("127.0.0.1", 参.口), 服务)
    print()
    print("  ✓ http://127.0.0.1:%d/" % 参.口)
    print("     Ctrl+C 停")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  停了")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
