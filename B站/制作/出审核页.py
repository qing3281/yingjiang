# -*- coding: utf-8 -*-
r"""出审核页.py —— 给一部片子生成本地审片页（审核.html）。

用法：
    python 出审核页.py "D:\DSHworkspace\B站\成片\光明顶"
    python 出审核页.py                      # 默认《光明顶》

页面直接读同目录的 成片.mp4 / 封面 / 分镜图，双击就能在浏览器里看片、
看技术参数、看投稿文案，不用起服务器。
"""
from __future__ import annotations

import argparse
import html
import json
import os

样式 = """*{box-sizing:border-box}
body{margin:0;background:#0d0e11;color:#e6e8ec;
 font:15px/1.7 "Microsoft YaHei","Segoe UI",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:36px 28px 80px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:.5px}
.sub{color:#8b93a1;font-size:14px;margin-bottom:26px}
.badge{display:inline-block;padding:3px 12px;border-radius:20px;font-size:13px;
 font-weight:600;vertical-align:middle;margin-left:10px}
.b-待审{background:#3a2f12;color:#f0c04a;border:1px solid #6b5520}
.b-通过{background:#12301c;color:#57d98a;border:1px solid #24623a}
.b-打回{background:#351519;color:#f0736f;border:1px solid #6b2a2c}
.card{background:#14161b;border:1px solid #23262e;border-radius:12px;
 padding:20px 22px;margin-bottom:18px}
.card h2{font-size:16px;margin:0 0 14px;color:#9aa3b2;font-weight:600;
 letter-spacing:.4px;text-transform:uppercase}
video{width:100%;border-radius:8px;background:#000;display:block}
img.cover{width:100%;max-width:640px;border-radius:8px;display:block}
img.wide{width:100%;border-radius:8px;display:block}
.kv{display:grid;grid-template-columns:110px 1fr;gap:6px 16px;font-size:14px}
.kv .k{color:#7c8492} .kv .v{color:#dde1e8;word-break:break-all}
.tags span{display:inline-block;background:#1d2029;border:1px solid #2c313c;
 border-radius:6px;padding:3px 10px;margin:0 6px 6px 0;font-size:13px;color:#a9b2c0}
.desc{white-space:pre-wrap;background:#0f1115;border-left:3px solid #2c313c;
 padding:12px 16px;border-radius:6px;color:#c6ccd6;font-size:14px}
.judge{background:#14161b;border:1px solid #2a2f3a;border-radius:12px;padding:20px 22px}
code{background:#1d2029;padding:2px 7px;border-radius:5px;font-size:13px;
 color:#8fd0ff;font-family:Consolas,monospace}
.hint{color:#7c8492;font-size:13px;margin-top:10px}
.格{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px}
.格 img{width:100%;border-radius:6px;display:block;background:#000}
.格 figure{margin:0} .格 figcaption{font-size:12px;color:#7c8492;margin-top:3px}"""


def 找(目录: str, *候选: str) -> str | None:
    for c in 候选:
        p = os.path.join(目录, c)
        if os.path.isfile(p):
            return c.replace(os.sep, "/")
    return None


def 格子(目录: str, 子目录: str, 模式: str = "_首帧.png", 列数: int = 0) -> str:
    """把某个子目录里的图排成网格（按文件名排序）。"""
    根 = os.path.join(目录, 子目录)
    if not os.path.isdir(根):
        return ""
    文件 = sorted(f for f in os.listdir(根) if f.endswith(模式))
    if not 文件:
        return ""
    块 = ['<div class="格">']
    for f in 文件:
        名 = f.replace(模式, "")
        块.append(f'<figure><img loading="lazy" src="{子目录}/{f}">'
                  f'<figcaption>{html.escape(名)}</figcaption></figure>')
    块.append("</div>")
    return "".join(块)


def 生成(目录: str) -> str:
    目录 = os.path.abspath(目录)
    名 = os.path.basename(目录)
    信息 = {}
    p = os.path.join(目录, "投稿信息.json")
    if os.path.isfile(p):
        try:
            信息 = json.load(open(p, encoding="utf-8"))
        except Exception:
            信息 = {}
    # 投稿信息也可能是 md，退化成纯文本展示
    文案md = 找(目录, "投稿信息.md", "投稿信息.txt")
    成片 = 找(目录, f"{名}_成片.mp4", "成片.mp4")
    封面 = 找(目录, "封面/封面_光明顶.png", "封面/封面_金句.png", "封面/封面.png")
    分镜 = 找(目录, "_分镜.jpg", "_分镜.png")
    参数 = 信息.get("技术参数", {}) if isinstance(信息, dict) else {}
    标签 = 信息.get("标签", []) if isinstance(信息, dict) else []

    段 = [f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
           f'<meta name="viewport" content="width=device-width,initial-scale=1">',
           f'<title>审片 · {html.escape(名)}</title><style>{样式}</style></head><body>',
           f'<div class="wrap"><h1>审片 · {html.escape(名)}'
           f'<span class="badge b-待审">待审</span></h1>',
           f'<div class="sub">落盘于 {html.escape(目录)}</div>']

    if 成片:
        海 = f' poster="{封面}"' if 封面 else ""
        段.append(f'<div class="card"><h2>成片</h2>'
                  f'<video src="{成片}" controls preload="metadata"{海}></video></div>')
    else:
        段.append('<div class="card"><h2>成片</h2><p>还没合成，目录里没有 *_成片.mp4。</p></div>')

    if 参数:
        行 = "".join(f'<div class="k">{html.escape(str(k))}</div>'
                     f'<div class="v">{html.escape(str(v))}</div>'
                     for k, v in 参数.items())
        段.append(f'<div class="card"><h2>技术参数</h2><div class="kv">{行}</div></div>')

    if 信息 or 文案md:
        段.append('<div class="card"><h2>投稿文案</h2>')
        if isinstance(信息, dict) and 信息:
            kv = []
            for k in ("标题", "分区", "AI声明", "简介"):
                if k in 信息 and k != "简介":
                    kv.append(f'<div class="k">{k}</div>'
                              f'<div class="v">{html.escape(str(信息[k]))}</div>')
            备选 = 信息.get("备选标题") or []
            if 备选:
                kv.append('<div class="k">备选标题</div><div class="v">'
                          + "<br>".join(html.escape(str(t)) for t in 备选) + "</div>")
            if kv:
                段.append(f'<div class="kv">{"".join(kv)}</div>')
            if 标签:
                段.append('<div style="margin-top:14px" class="tags">'
                          + "".join(f"<span>{html.escape(str(t))}</span>" for t in 标签)
                          + "</div>")
            简介 = 信息.get("简介")
            if 简介:
                段.append(f'<div class="desc" style="margin-top:14px">'
                          f'{html.escape(str(简介))}</div>')
        if 文案md:
            文 = open(os.path.join(目录, 文案md), encoding="utf-8").read()
            段.append(f'<details style="margin-top:14px"><summary style="cursor:pointer;'
                      f'color:#7c8492;font-size:13px">展开 {html.escape(文案md)} 原文</summary>'
                      f'<div class="desc" style="margin-top:10px">{html.escape(文)}</div>'
                      f'</details>')
        段.append("</div>")

    if 封面:
        段.append(f'<div class="card"><h2>封面</h2>'
                  f'<img class="cover" src="{封面}"></div>')
    if 分镜:
        段.append(f'<div class="card"><h2>分镜</h2>'
                  f'<img class="wide" loading="lazy" src="{分镜}"></div>')

    首 = 格子(目录, "首帧", "_首帧.png")
    if 首:
        段.append(f'<div class="card"><h2>首帧（逐镜）</h2>{首}</div>')

    段.append('<div class="judge"><h2 style="font-size:16px;margin:0 0 12px;color:#9aa3b2">'
              '怎么表态</h2>'
              '<p style="margin:0 0 10px">看完在命令行签字，或者直接跟我说。</p>'
              f'<p style="margin:0 0 8px"><code>python 审片.py "{html.escape(目录)}" '
              '--通过 -备注 "可以投"</code></p>'
              f'<p style="margin:0"><code>python 审片.py "{html.escape(目录)}" '
              '--打回 -备注 "哪里不行"</code></p>'
              '<div class="hint">当前状态：<b>待审</b></div></div>')

    段.append("</div></body></html>")
    return "".join(段)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成审片页")
    ap.add_argument("目录", nargs="?", default=r"D:\DSHworkspace\B站\成片\光明顶")
    a = ap.parse_args()
    文 = 生成(a.目录)
    p = os.path.join(os.path.abspath(a.目录), "审核.html")
    open(p, "w", encoding="utf-8").write(文)
    print(f"✓ {p}  {len(文)/1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
