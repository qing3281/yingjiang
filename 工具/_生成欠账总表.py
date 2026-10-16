# -*- coding: utf-8 -*-
"""把 `欠账总表.md` 变成一张能双击打开的 HTML，并在桌面留一个 `.lnk`。

用户 10-15 01:20 的原话：「**假如哪天我把这个网址给忘了呢，好麻烦呀**」
AGENTS.md 第 0.05 条那一条病：「**少问一句『他打开它要敲几下』** —— 凡是我给他的东西，
桌面必须有 `.lnk` 或一个能点开的页；超过双击一下就是没做完。」

所以这个脚本干三件事：
  1. 把 md 转成自带样式的单文件 html（不联网、不依赖 CDN —— 他可能断网）
  2. 源 md 一变，html 就重生成（看 mtime）
  3. 桌面建/刷新快捷方式「欠账总表」
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
W = r"D:\DSHworkspace"
源 = os.path.join(W, "欠账总表.md")
出 = os.path.join(W, "欠账总表.html")

CSS = """
:root{--bg:#0f1115;--fg:#e8eaf0;--dim:#9aa1ad;--line:#262b34;--ok:#4ade80;--mid:#fbbf24;--no:#f87171;--hi:#60a5fa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:16px/1.75 "Microsoft YaHei","PingFang SC",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:32px 22px 90px}
h1{font-size:30px;margin:0 0 6px;border-bottom:2px solid var(--hi);padding-bottom:12px}
h2{font-size:22px;margin:42px 0 12px;color:var(--hi);border-left:4px solid var(--hi);padding-left:12px}
h3{font-size:18px;margin:26px 0 10px;color:var(--dim)}
p{margin:10px 0}
blockquote{margin:14px 0;padding:10px 16px;border-left:3px solid var(--line);
 background:#161a21;color:var(--dim);border-radius:0 6px 6px 0}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:15px}
th,td{border:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}
th{background:#1a1f27;color:var(--hi);font-weight:600;white-space:nowrap}
tr:nth-child(even) td{background:#13171d}
code{background:#1c2129;padding:2px 6px;border-radius:4px;font-family:Consolas,monospace;
 font-size:14px;color:#ffd479}
strong{color:#fff}
hr{border:0;border-top:1px solid var(--line);margin:34px 0}
ul{margin:10px 0;padding-left:24px}
li{margin:5px 0}
a{color:var(--hi)}
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def 行内(s):
    """`code` **粗** 两种够用了。"""
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def 转(md):
    W_ = []
    表 = []
    for 行 in md.splitlines():
        if 行.strip().startswith("|"):
            表.append(行.strip())
            continue
        if 表:
            W_.append(出表(表))
            表 = []
        s = 行.rstrip()
        if not s.strip():
            continue
        if s.startswith("### "):
            W_.append("<h3>%s</h3>" % 行内(s[4:]))
        elif s.startswith("## "):
            W_.append("<h2>%s</h2>" % 行内(s[3:]))
        elif s.startswith("# "):
            W_.append("<h1>%s</h1>" % 行内(s[2:]))
        elif s.startswith("> "):
            W_.append("<blockquote>%s</blockquote>" % 行内(s[2:]))
        elif s.strip() == "---":
            W_.append("<hr>")
        elif s.lstrip().startswith("- "):
            W_.append("<li>%s</li>" % 行内(s.lstrip()[2:]))
        else:
            W_.append("<p>%s</p>" % 行内(s))
    if 表:
        W_.append(出表(表))
    # 连着几个 <li> 包进 <ul>
    出s = []
    在表 = False
    for x in W_:
        if x.startswith("<li>"):
            if not 在表:
                出s.append("<ul>")
                在表 = True
        else:
            if 在表:
                出s.append("</ul>")
                在表 = False
        出s.append(x)
    if 在表:
        出s.append("</ul>")
    return "\n".join(出s)


def 出表(行们):
    """把连续的 | … | 行转成 <table>。第二行如果是 |---| 就当分隔。"""
    def 格(s):
        return [c.strip() for c in s.strip().strip("|").split("|")]

    头 = 格(行们[0])
    体 = 行们[1:]
    if 体 and set(体[0].replace("|", "").replace("-", "").replace(" ", "")) == set():
        体 = 体[1:]
    o = ["<table><thead><tr>"] + ["<th>%s</th>" % 行内(c) for c in 头] + ["</tr></thead><tbody>"]
    for r in 体:
        o.append("<tr>" + "".join("<td>%s</td>" % 行内(c) for c in 格(r)) + "</tr>")
    o.append("</tbody></table>")
    return "".join(o)


def 生成(强制=False):
    if not os.path.isfile(源):
        print("  ✗ 没有 %s" % 源)
        return False
    if not 强制 and os.path.isfile(出) and os.path.getmtime(出) > os.path.getmtime(源):
        print("  – html 比 md 新，不用重生成")
        return True
    with open(源, encoding="utf-8") as f:
        md = f.read()
    html = ("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>欠账总表 —— 阿实欠你的</title><style>" + CSS + "</style></head>"
            "<body><div class=\"wrap\">" + 转(md) + "</div></body></html>")
    with open(出, "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✓ %s  %d B" % (出, os.path.getsize(出)))
    return True


def 建快捷方式():
    桌面 = os.path.join(os.path.expanduser("~"), "Desktop")
    lnk = os.path.join(桌面, "欠账总表.lnk")
    ps = (
        "$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut('%s');"
        "$s.TargetPath='%s';"
        "$s.Arguments='\"%s\"';"
        "$s.WorkingDirectory='%s';"
        "$s.IconLocation='%s,0';"
        "$s.Description='阿实欠你的每一条 + 怎么做 + 什么时候完';"
        "$s.Save()" % (lnk, os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "explorer.exe"),
                       出, W, 出)
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=60)
    if os.path.isfile(lnk):
        print("  ✓ 桌面快捷方式「欠账总表」  %d B" % os.path.getsize(lnk))
    else:
        print("  ✗ 快捷方式没建成：%s" % r.stderr.decode("utf-8", "replace")[:200])


if __name__ == "__main__":
    生成("--强制" in sys.argv)
    建快捷方式()
    print()
    print("  双击桌面上的「欠账总表」就能看。源文件：%s" % 源)
