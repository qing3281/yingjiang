# -*- coding: utf-8 -*-
"""
依据台 —— 「这一轮我读了哪些文件、做了哪些动作」的实时证据板。

数据源：DSH 自己写的会话存档
    D:\\DSH\\home\\sessions\\--D-DSHworkspace--\\<会话id>\\session.v4.jsonl.zstd
里面每条 `tool/call` 是 DSH 记的，我改不了 —— 所以它能当证据：
我说「我查过了」，你在这里能看见我到底开没开那个文件。

只用标准库 + zstandard。只读，不写任何东西。

跑法：
    python _依据台.py            起在 8794
    python _依据台.py --看       只打一次本轮摘要，不起服务
"""
import json
import os
import re
import sys
import time
import http.server
import socketserver
import threading
import urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

存档根 = r"D:\DSH\home\sessions"
口 = 8794
缓存 = {"时": 0.0, "数": None, "路": None, "大小": -1}

# 按工具名分类，方便一眼看懂
读类 = {"read", "grep", "glob", "search_context", "cache_search",
        "web_fetch", "read_page", "read_image", "modlens_read_image"}
写类 = {"write", "edit", "notebook_edit"}
跑类 = {"pwsh", "bash", "shell"}
看类 = {"web_search", "multi_search", "advanced_search", "research",
        "platform_search", "domain_search", "video_search", "weather",
        "x_search", "anysearch_search", "free_search_test"}


# ─────────────────────────── 找活的存档 ───────────────────────────
def 找活的():
    """最近 30 分钟动过的存档里，挑最大的那个（正在跑的那一场）。"""
    if not os.path.isdir(存档根):
        return None
    候选 = []
    for 顶 in os.listdir(存档根):
        子 = os.path.join(存档根, 顶)
        if not os.path.isdir(子):
            continue
        for 会 in os.listdir(子):
            路 = os.path.join(子, 会, "session.v4.jsonl.zstd")
            if not os.path.isfile(路):
                continue
            try:
                st = os.stat(路)
            except OSError:
                continue
            候选.append((st.st_mtime, st.st_size, 路))
    if not 候选:
        return None
    候选.sort(reverse=True)
    现在 = time.time()
    # 正在长的那个：5 分钟内动过，且体积最大
    活的 = [c for c in 候选 if 现在 - c[0] < 300]
    if 活的:
        活的.sort(key=lambda c: -c[1])
        return 活的[0][2]
    return 候选[0][2]


def 解压(路):
    import zstandard as zstd
    d = zstd.ZstdDecompressor()
    with open(路, "rb") as f:
        try:
            return d.stream_reader(f).read().decode("utf-8", "replace")
        except Exception:
            # 活文件可能还没有结尾帧 —— 能读多少算多少
            f.seek(0)
            try:
                r = d.stream_reader(f, read_across_frames=True)
                return r.read().decode("utf-8", "replace")
            except Exception:
                return ""


def 文本(块):
    if isinstance(块, str):
        return 块
    if isinstance(块, list):
        出 = []
        for c in 块:
            if isinstance(c, dict) and c.get("type") == "text":
                出.append(c.get("text") or "")
        return "\n".join(出)
    if isinstance(块, dict):
        return 文本(块.get("content"))
    return ""


空转词 = set("""emit go write writing ok okay enough now hmm wait actually let
me here nope yes good right so and but first next then done alright fine sure
just""".split()) | set("嗯 好 行 开始 写 做 走 来 继续 那么 现在 干 上 冲".split())


def 数空转(文):
    n = 0
    for 句 in re.split(r"[。.!?！？\n]+", 文 or ""):
        句 = 句.strip().strip("`*_ ")
        if not 句 or len(句) > 14:
            continue
        词 = re.findall(r"[A-Za-z]+", 句.lower())
        if 词 and all(w in 空转词 for w in 词):
            n += 1
        elif not 词 and 句 in {"嗯", "好", "行", "开始", "写", "做", "走", "来", "继续"}:
            n += 1
    return n


# ─────────────────────────── 解析 ───────────────────────────
def 解析(路):
    出 = {
        "路": 路, "会话": os.path.basename(os.path.dirname(路)),
        "本轮起": None, "工具": [], "空转": 0, "推理段": 0,
        "助手条": 0, "token新": 0, "token读": 0, "token出": 0,
        "轮": 0, "字节": 0,
    }
    try:
        出["字节"] = os.path.getsize(路)
    except OSError:
        return 出
    txt = 解压(路)
    if not txt:
        出["坏"] = "解不开"
        return 出

    记录 = []
    for l in txt.split("\n"):
        if not l.strip():
            continue
        try:
            记录.append(json.loads(l))
        except Exception:
            continue

    # 1) 找「本轮」的起点：最后一条带 rpcId 的用户消息（那是人敲的）
    起点 = 0
    for i, o in enumerate(记录):
        if o.get("type") != "user/message":
            continue
        d = o.get("data") or {}
        src = d.get("source") or {}
        # ⚠ kind=="user" 不算数：子代理任务书也这么标。只有 rpcId 是人敲的。
        if src.get("kind") == "user" and src.get("rpcId"):
            起点 = i
    出["本轮起"] = (记录[起点].get("time") if 记录 else None)

    本轮 = 记录[起点:] if 起点 else 记录

    # 2) 本轮里的工具调用 / 思考 / token
    序 = 0
    for o in 本轮:
        t = o.get("type")
        d = o.get("data") or {}
        if t == "tool/call":
            序 += 1
            名 = d.get("name") or "?"
            try:
                参 = json.loads(d.get("arguments") or "{}")
            except Exception:
                参 = {}
            目 = (参.get("file_path") or 参.get("path") or 参.get("query")
                  or 参.get("url") or 参.get("pattern") or "")
            if not 目 and 参.get("command"):
                目 = str(参["command"])[:200]
            出["工具"].append({
                "行": 序, "名": 名, "目": str(目)[:240],
                "时": o.get("time"),
            })
        elif t == "assistant/message":
            出["助手条"] += 1
            u = d.get("usage") or {}
            出["token新"] += u.get("inputTokens") or 0
            出["token读"] += u.get("cacheReadTokens") or 0
            出["token出"] += u.get("outputTokens") or 0
            信 = d.get("message") or {}
            for c in (信.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "reasoning":
                    出["推理段"] += 1
                    出["空转"] += 数空转(c.get("text") or "")
        elif t == "turn/start":
            出["轮"] += 1

    # 3) 分类
    def 归(名):
        if 名 in 读类:
            return "读"
        if 名 in 写类:
            return "写"
        if 名 in 跑类:
            return "跑"
        if 名 in 看类:
            return "查"
        return "其它"

    for x in 出["工具"]:
        x["类"] = 归(x["名"])
    出["按类"] = {}
    for x in 出["工具"]:
        出["按类"].setdefault(x["类"], 0)
        出["按类"][x["类"]] += 1
    # 本轮的「我读了哪些文件」——只留读类，去重，保留最后一次
    见 = {}
    for x in 出["工具"]:
        if x["类"] == "读" and x["目"]:
            见[x["目"]] = x
    出["读过"] = list(见.values())
    return 出


def 拿(强制=False):
    现在 = time.time()
    if not 强制 and 缓存["数"] and 现在 - 缓存["时"] < 12:
        return 缓存["数"]
    路 = 找活的()
    if not 路:
        return {"坏": "没找到会话存档"}
    try:
        大 = os.path.getsize(路)
    except OSError:
        大 = -1
    if not 强制 and 缓存["数"] and 缓存["路"] == 路 and 缓存["大小"] == 大:
        缓存["时"] = 现在
        return 缓存["数"]
    数 = 解析(路)
    缓存.update({"时": 现在, "数": 数, "路": 路, "大小": 大})
    return 数


# ─────────────────────────── 页面 ───────────────────────────
def 逃(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


样式 = """
*{box-sizing:border-box}
html,body{margin:0;padding:0;height:100%;background:#12141a;color:#dfe3ea;
  font:13px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.top{position:sticky;top:0;z-index:9;background:#171a21;border-bottom:1px solid #262b36;
  padding:8px 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.top h1{font-size:14px;margin:0;font-weight:600;letter-spacing:.5px}
.dot{width:8px;height:8px;border-radius:50%;background:#3ddc84;display:inline-block}
.dot.off{background:#666}
.sub{color:#7d8698;font-size:11.5px}
.wrap{padding:10px 12px 40px}
.card{background:#171a21;border:1px solid #242936;border-radius:8px;margin:0 0 10px}
.card h2{font-size:12px;margin:0;padding:8px 12px;color:#9fb0c9;font-weight:600;
  border-bottom:1px solid #222734;letter-spacing:.4px}
.card .body{padding:8px 12px}
.k{display:flex;gap:14px;flex-wrap:wrap}
.k div{min-width:74px}
.k b{display:block;font-size:17px;font-weight:600;color:#eaf0fa}
.k span{color:#7d8698;font-size:11px}
.row{display:flex;gap:8px;padding:3px 0;border-bottom:1px dashed #1e2330;align-items:baseline}
.row:last-child{border-bottom:0}
.row .n{flex:0 0 74px;color:#6f7a8d;font-size:11px;font-family:ui-monospace,Consolas,monospace}
.row .m{flex:0 0 92px;color:#8fd0ff;font-size:11.5px;font-family:ui-monospace,Consolas,monospace}
.row .p{flex:1;word-break:break-all;font-size:11.5px;color:#c7d0de}
.row .t{flex:0 0 62px;text-align:right;color:#5d6675;font-size:10.5px}
.类{display:inline-block;padding:0 5px;border-radius:3px;font-size:10px;margin-right:4px}
.类读{background:#123a2a;color:#5fe0a0}.类写{background:#3a2412;color:#ffb35c}
.类跑{background:#2a1c3a;color:#c79bff}.类查{background:#12303a;color:#5fd0e0}
.类其它{background:#252a35;color:#9aa4b5}
.empty{color:#5d6675;font-size:12px;padding:4px 0}
.warn{color:#ffb35c}
.bad{color:#ff7b72}
"""


def 渲染(数):
    if 数.get("坏"):
        return ("<html><head><meta charset='utf-8'><title>依据</title></head>"
                "<body style='background:#12141a;color:#dfe3ea;font-family:sans-serif;padding:20px'>"
                f"<p class='bad'>看不了：{逃(数['坏'])}</p></body></html>")

    工 = 数["工具"]
    读 = 数.get("读过") or []
    类 = 数.get("按类") or {}
    空 = 数["空转"]
    段 = 数["推理段"] or 1
    每段 = 空 / 段

    def 时刻(t):
        if not t:
            return ""
        try:
            return time.strftime("%H:%M:%S", time.localtime(t / 1000))
        except Exception:
            return ""

    行 = []
    for x in 工[-80:][::-1]:
        行.append(
            f"<div class='row'><div class='n'>{x['行']:>3}</div>"
            f"<div class='m'><span class='类 类{x['类']}'>{x['类']}</span>{逃(x['名'])}</div>"
            f"<div class='p'>{逃(x['目']) or '<span class=empty>（无参数）</span>'}</div>"
            f"<div class='t'>{时刻(x['时'])}</div></div>")

    读行 = []
    for x in 读[::-1][:40]:
        读行.append(f"<div class='row'><div class='m'>{逃(x['名'])}</div>"
                    f"<div class='p'>{逃(x['目'])}</div>"
                    f"<div class='t'>{时刻(x['时'])}</div></div>")

    空色 = "" if 每段 < 0.5 else (" warn" if 每段 < 5 else " bad")

    return f"""<html><head><meta charset="utf-8"><title>依据</title>
<style>{样式}</style></head><body>
<div class="top">
  <span class="dot"></span><h1>依据</h1>
  <span class="sub">这一轮我读了哪些文件 · 做了哪些动作</span>
  <span class="sub" style="margin-left:auto">会话 {逃(数['会话'][:8])} · 更新于 {time.strftime('%H:%M:%S')}</span>
</div>
<div class="wrap">

  <div class="card"><h2>本轮</h2><div class="body"><div class="k">
    <div><b>{len(工)}</b><span>次工具</span></div>
    <div><b>{len(读)}</b><span>份文件</span></div>
    <div><b>{类.get('读',0)}</b><span>读</span></div>
    <div><b>{类.get('写',0)}</b><span>写</span></div>
    <div><b>{类.get('跑',0)}</b><span>跑命令</span></div>
    <div><b>{类.get('查',0)}</b><span>查网</span></div>
    <div><b>{数['轮']}</b><span>轮</span></div>
    <div><b class="{空色.strip()}">{空}</b><span>空转<br>每段 {每段:.1f} 次</span></div>
  </div>
  <div class="sub" style="margin-top:6px">
    token 本场：新输入 {数['token新']:,} / 缓存读 {数['token读']:,} / 输出 {数['token出']:,}
    （助手消息 {数['助手条']} 条）
  </div></div></div>

  <div class="card"><h2>我读过哪些文件（本轮的，倒序）</h2><div class="body">
    {''.join(读行) or "<div class='empty'>这一轮还没读过文件。</div>"}
  </div></div>

  <div class="card"><h2>全部动作（最近 80 次，倒序）</h2><div class="body">
    {''.join(行) or "<div class='empty'>还没有动作。</div>"}
  </div></div>

  <div class="sub" style="padding:0 2px">
    这些不是我上报的，是 DSH 自己写在
    <code>D:\\DSH\\home\\sessions\\…\\session.v4.jsonl.zstd</code> 里的
    <code>tool/call</code> 记录 —— 我改不了。
  </div>
</div>
<script>setTimeout(()=>location.reload(), 5000)</script>
</body></html>"""


class 服务(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                体 = 渲染(拿()).encode("utf-8")
                型 = "text/html; charset=utf-8"
            elif u.path == "/api/now":
                体 = json.dumps(拿(), ensure_ascii=False, default=str).encode("utf-8")
                型 = "application/json; charset=utf-8"
            else:
                self.send_response(404)
                self.end_headers()
                return
        except Exception as e:
            import traceback
            traceback.print_exc()
            体 = f"<pre>{逃(type(e).__name__)}: {逃(e)}</pre>".encode("utf-8")
            型 = "text/html; charset=utf-8"
            self.send_response(500)
        else:
            self.send_response(200)
        self.send_header("Content-Type", 型)
        self.send_header("Content-Length", str(len(体)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(体)


def 主():
    if "--看" in sys.argv:
        数 = 拿(True)
        if 数.get("坏"):
            print("  ✗", 数["坏"])
            return 1
        print(f"  会话 {数['会话']}")
        print(f"  存档 {数['路']}  {数['字节']:,} B")
        print(f"  本轮：{len(数['工具'])} 次工具 / {len(数.get('读过') or [])} 份文件 / "
              f"{数['轮']} 轮 / 空转 {数['空转']} 次（{数['推理段']} 段推理）")
        print(f"  分类 {数.get('按类')}")
        print("  读过：")
        for x in (数.get("读过") or [])[-20:]:
            print(f"    {x['名']:<10} {x['目'][:110]}")
        return 0

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", 口), 服务) as s:
        s.daemon_threads = True
        print(f"  依据台 http://127.0.0.1:{口}/")
        s.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(主())
