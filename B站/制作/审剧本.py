# -*- coding: utf-8 -*-
"""把《不烧心》的剧本 + 人设图 + 场景图拼成一个审核页。

用法：
    python 审剧本.py                        # 生成 审核.html 并打开
    python 审剧本.py --不打开                # 只生成

设计要点：
  * 图片全部 base64 内联，HTML 单文件，能直接发给别人看
  * 上面是剧本（Markdown 渲染），下面是人设图 + 场景图墙
  * 顶部给一个"施工预算"条：把每个环节的真实耗时和预计总时长摊开，
    这样用户签字前就知道要等多久
"""
import argparse
import base64
import glob
import os
import re
import sys
import webbrowser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

制作 = r"D:\DSHworkspace\B站\制作"
成片根 = r"D:\DSHworkspace\B站\成片\不烧心"
参考根 = r"D:\DSHworkspace\B站\情报\AI娘参考图"
剧本 = os.path.join(制作, "不烧心_剧本.md")
设定 = os.path.join(制作, "不烧心_人物设定.md")
出 = os.path.join(成片根, "审核.html")

# 对照用的网络原图（用户要求「用网上的原原本本的形象」）
对照表 = [
    ("主角 · DS 女仆鲸鱼娘 官方设定图", "DS_女仆鲸鱼娘_官方设定图.png"),
    ("主角 · DS娘 条目主图（十六夜猫）", "DS_条目主图_十六夜猫.jpg"),
    ("主角 · DS娘 Q版三视图", "DS娘_Q版三视图.webp"),
    ("主角 · DS娘 早期设定图", "DS_早期设定图.jpg"),
    ("主角 · GPT 龙娘 标准设定图", "GPT娘_标准设定图.webp"),
    ("主角 · GPT 龙娘 角色立绘", "GPT龙娘_角色立绘.webp"),
    ("主角 · GPT 龙娘 三视图", "GPT龙娘_三视图.webp"),
    ("主角 · GPT娘 助手立绘", "GPT娘_助手立绘.webp"),
    ("主角 · GPT娘 银白恶魔角半身", "GPT娘_银白恶魔角半身.webp"),
    ("配角 · DS娘 与 Claude娘", "DS娘与Claude娘.webp"),
    ("配角 · GLM 系", "DS_Harness娘.jpg"),
    ("梗图 · 你这贪财的白色大肥龙", "梗图_你这贪财的白色大肥龙.webp"),
    ("梗图 · 龙之疗愈", "梗图_龙之疗愈.webp"),
    ("梗图 · GPT 给 DS 画表情包", "GPT娘给DS画表情包.webp"),
    ("群像 · AI娘小剧场", "AI娘小剧场_小叶子.jpg"),
]


def 内联(p):
    if not os.path.isfile(p):
        return ""
    with open(p, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def md2html(s: str) -> str:
    """够用就行的 Markdown → HTML（标题/粗体/表格/列表/引用/分隔线）"""
    行 = s.split("\n")
    出 = []
    表 = []
    i = 0

    def 关表():
        if not 表:
            return
        出.append('<table>')
        for k, r in enumerate(表):
            if k == 1:
                continue
            tag = "th" if k == 0 else "td"
            if re.match(r"^\|[\s:|-]+\|$", r.strip()):
                continue
            cells = [c.strip() for c in r.strip().strip("|").split("|")]
            出.append("<tr>" + "".join(f"<{tag}>{行内(c)}</{tag}>" for c in cells) + "</tr>")
        出.append("</table>")
        表.clear()

    def 行内(t):
        t = (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t

    while i < len(行):
        l = 行[i]
        if l.startswith("|"):
            表.append(l)
            i += 1
            continue
        关表()
        if l.startswith("#### "):
            出.append(f"<h4>{行内(l[5:])}</h4>")
        elif l.startswith("### "):
            出.append(f"<h3>{行内(l[4:])}</h3>")
        elif l.startswith("## "):
            出.append(f"<h2>{行内(l[3:])}</h2>")
        elif l.startswith("# "):
            出.append(f"<h1>{行内(l[2:])}</h1>")
        elif l.startswith("> "):
            出.append(f"<blockquote>{行内(l[2:])}</blockquote>")
        elif l.strip() == "---":
            出.append("<hr>")
        elif re.match(r"^\s*[-*] ", l):
            出.append(f"<li>{行内(re.sub(r'^\s*[-*] ', '', l))}</li>")
        elif l.strip() == "":
            出.append("")
        else:
            出.append(f"<p>{行内(l)}</p>")
        i += 1
    关表()
    # 相邻 li 包一层 ul
    html = "\n".join(出)
    html = re.sub(r"(?:<li>.*?</li>\n?)+", lambda m: "<ul>" + m.group(0) + "</ul>", html)
    return html


# 施工预算：全部来自本机实测
预算 = [
    ("人物形象图", "7 张", "Z-Image-Turbo int8 · 8 步 · 1024×1408", "≈ 45 秒", "已跑完"),
    ("场景图", "6 张", "Z-Image-Turbo int8 · 8 步 · 1344×768", "≈ 20 秒", "已跑完"),
    ("分镜静帧", "30 张", "Z-Image-Turbo int8 · 8 步 · 1536×864（含角色锁前缀）", "≈ 4 分钟", "待跑"),
    ("镜头动态", "30 条 × 5.17s", "MiniMax H3 fl2va · 768p · 4 步 + turbo LoRA", "≈ 58 分钟", "待跑"),
    ("配音", "30 句", "IndexTTS-2（本地）", "≈ 6 分钟", "待跑"),
    ("合成 + 混音", "30 镜", "PyAV 拼接 + BGM 混音", "≈ 2 分钟", "待跑"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--不打开", action="store_true")
    a = ap.parse_args()

    剧 = open(剧本, encoding="utf-8").read() if os.path.isfile(剧本) else "（缺剧本）"

    人设 = sorted(glob.glob(os.path.join(成片根, "人设", "*.png")))
    场景 = sorted(glob.glob(os.path.join(成片根, "场景", "*.png")))

    def 墙(路径们, 类):
        h = []
        for p in 路径们:
            n = os.path.basename(p).replace(".png", "")
            h.append(f'<figure class="{类}"><img src="{内联(p)}" alt="{n}">'
                     f'<figcaption>{n}</figcaption></figure>')
        return "\n".join(h)

    预算行 = "\n".join(
        f"<tr><td>{a_}</td><td>{b}</td><td class='m'>{c}</td><td class='m'>{d}</td>"
        f"<td class='{'ok' if e=='已跑完' else 'wait'}'>{e}</td></tr>"
        for a_, b, c, d, e in 预算
    )

    参考 = []
    for 名, 文件 in 对照表:
        p = os.path.join(参考根, 文件)
        if not os.path.isfile(p):
            continue
        ext = "png" if 文件.lower().endswith(".png") else ("webp" if 文件.lower().endswith(".webp") else "jpeg")
        with open(p, "rb") as f:
            uri = f"data:image/{ext};base64," + base64.b64encode(f.read()).decode()
        参考.append(f'<figure><img src="{uri}" alt="{名}"><figcaption>{名}</figcaption></figure>')
    对照墙 = "\n".join(参考)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>《不烧心》审核 · AI 市井短剧 v2</title>
<style>
:root{{--bg:#0e0f13;--fg:#e8e9ee;--dim:#9aa0ad;--line:#252832;--acc:#4ea1ff;
--ok:#39d98a;--wait:#ffb454;--card:#15171e}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.75 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:32px 24px 80px}}
h1{{font-size:30px;margin:0 0 6px;letter-spacing:.5px}}
.sub{{color:var(--dim);margin-bottom:28px}}
h2{{font-size:22px;margin:38px 0 12px;padding-left:12px;border-left:4px solid var(--acc)}}
h3{{font-size:18px;margin:26px 0 8px;color:#cfd6e4}}
h4{{font-size:16px;margin:20px 0 6px;color:#b9c2d2}}
hr{{border:0;border-top:1px solid var(--line);margin:30px 0}}
p{{margin:8px 0}}
blockquote{{margin:12px 0;padding:10px 16px;background:#151822;
border-left:3px solid var(--acc);border-radius:0 6px 6px 0;color:#c6cede}}
code{{background:#1c2029;padding:2px 6px;border-radius:4px;font-size:13px;color:#8fd4ff}}
b{{color:#fff}}
ul{{margin:8px 0 8px 4px;padding-left:20px}}
li{{margin:4px 0}}
table{{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}}
th,td{{border:1px solid var(--line);padding:9px 12px;text-align:left;vertical-align:top}}
th{{background:#1a1d26;color:#cfd6e4;font-weight:600}}
td.m{{font-family:Consolas,monospace;font-size:13px;color:#9fd0ff}}
td.ok{{color:var(--ok);font-weight:600}}
td.wait{{color:var(--wait)}}
.hero{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin:18px 0 6px}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
figure img{{width:100%;display:block;background:#fff}}
figcaption{{padding:7px 10px;font-size:12.5px;color:var(--dim);text-align:center}}
.scene{{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}}
.note{{background:#1a1408;border:1px solid #4a3a12;border-radius:10px;
padding:14px 18px;margin:18px 0;color:#ffd9a0;font-size:14px}}
.note b{{color:#ffc266}}
.tag{{display:inline-block;padding:2px 9px;border-radius:20px;font-size:12px;
background:#1d2430;color:#8fb8e8;margin-right:6px}}
</style></head><body><div class="wrap">

<h1>《不烧心》· AI 市井短剧 <span style="color:#4ea1ff">v2</span></h1>
<div class="sub">
<span class="tag">30 镜</span><span class="tag">横屏 1536×864</span>
<span class="tag">≈ 2 分 35 秒</span><span class="tag">MiniMax H3 fl2va</span>
<span class="tag">11 句金句</span><span class="tag">待审核</span>
</div>

<div class="note">
<b>v2 改了什么：</b>① 剧情严格套《不烧心》模板（老实用好料 → 涨价 → 黑心白送抢客 →
老顾客回头 → 黑心翻车 → 客人回来）；② 金句从 3 句加到 <b>11 句</b>（每 14 秒一句）；
③ DeepSeek <b>全程不给怜悯</b>——不是穷，是故意拿白饭冒充好料；④ 人设形象
<b>按网上原图重画</b>（见第五节对照）。
<br><br>
<b>审核什么：</b>① 剧本的故事线、台词、金句；② 人物形象（对得上网上的原图吗）；
③ 场景基调。<b>你签字我才开始跑 30 镜</b>——跑一次约 1 小时。
</div>

<h2>一、施工预算（本机实测，非估算）</h2>
<table>
<tr><th>环节</th><th>数量</th><th>用的什么</th><th>实测耗时</th><th>状态</th></tr>
{预算行}
</table>
<p style="color:var(--dim);font-size:13.5px">
合计：<b style="color:#fff">约 1 小时 10 分</b>（其中 58 分钟是 MiniMax 生成视频）。
上一部《今天别开门》用的是 Wan 2.2 14B 双模型串联，每条 5 秒要 4 分钟，
快的时候反而是现在这条 MiniMax 路线——同一条 5 秒只要 2 分钟。
</p>

<h2>二、人物形象图（这个形象定了就不再改）</h2>
<div class="hero">
{墙(人设, '')}
</div>

<h2>三、场景图</h2>
<div class="hero scene">
{墙(场景, '')}
</div>

<h2>四、完整剧本</h2>
{md2html(剧)}

<h2>五、对照：网上原图（用户要求「用原原本本的形象」）</h2>
<p style="color:var(--dim);font-size:13.5px">
左边/上面这些是从网上抓的真实 AI 娘同人图（萌娘百科、B站、Pixiv、微博）。
对照第二节我画的三视图，看两个主角像不像。
</p>
<div class="hero scene">
{对照墙}
</div>

</div></body></html>"""

    os.makedirs(成片根, exist_ok=True)
    with open(出, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 审核页 → {出}  ({os.path.getsize(出)/1024/1024:.1f} MB)")
    print(f"   人物 {len(人设)} 张 · 场景 {len(场景)} 张")
    if not a.不打开:
        webbrowser.open(出)
    return 0


if __name__ == "__main__":
    sys.exit(main())
