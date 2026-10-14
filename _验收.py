# -*- coding: utf-8 -*-
r"""生成验收页 `D:\DSHworkspace\_验收.html` —— 一个双击就能打开、能点开每一样东西的页面。

为什么要有它：用户 2026-10-15 的原话里「**要看得见**」说了 12 次（跨 4 天）。
台账在 md 里、截图散在十几个目录里 —— 验收的时候他不该去翻目录。
**每一样都要能点开。**

页面用相对路径引本地文件（`file://` 页面可以这么干），所以它必须待在
`D:\DSHworkspace\` 根下。

用法：python _验收.py
"""
import io
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
出 = os.path.join(根, "_验收.html")

# (标题, 相对路径, 说明, 类型)  类型：img / mp4 / link
四部戏 = [
    ("《觉醒》5 分 02 秒 · 74 格 · 66 句台词", r"影匠\作品\觉醒\片\_成片_觉醒_字幕.mp4",
     "2026-10-15 06:12 第三版。核心矛盾从 85% 处提到 **2.7%**（第 9 秒就说出口）；"
     "四格模型自己画上去的假字幕已修掉；19 格的动作重出过。"),
    ("《雪线》3 分 02 秒 · 45 格 · 7 句台词", r"影匠\作品\雪线\片\《雪线》成片_有声_字幕.mp4",
     "2026-10-15 07:20 重拼 + 加了一句台词。两轮共改 19 格的「动作」字段（原先那些格自己写着「不动」），"
     "全片去噪后动作量中位 0.283 → 0.567，冻住的格子 17 → 6；"
     "**第 29 秒补了一句「没有例外。」**，「例外」这个词第一次出现的位置从 82.6% 提到 **15.9%**。"),
    ("《磨刀》3 分 03 秒 · 45 格 · 51 句台词", r"影匠\作品\磨刀\片\《磨刀》成片_有声_字幕.mp4",
     "现有四部里唯一「讲清了」的一部 —— 核心矛盾在第 46 秒（25% 处）就由人物当面说出来。"),
    ("《试镜》30 秒 · 9 格", r"影匠\作品\试镜\片\_成片_双线_有声.mp4",
     "最早的一条，单场戏。它的主角也是凌霜。"),
]

界面 = [
    ("影匠控制台", "http://127.0.0.1:8791/",
     "能操作的软件（`影匠控制台.exe`，8.0 MB，双击就开，不需要 python）。"
     "起活 / 看进度条 / 选片子超分 / 出片不再需要写脚本。"),
    ("记忆台", "http://127.0.0.1:8792/",
     "22 份知识 + 135 条经验 + 你这几天说过的每一句话，顶上有个搜索框。"),
    ("依据面板", "http://127.0.0.1:8794/",
     "这一轮读了哪些文件、做了什么 —— 数据是 DSH 自己记的 tool/call，我改不了。"),
    ("三个界面方向（草图）", r"_界面草图.html",
     "甲 仪表盘 / 乙 剪辑台 / 丙 任务队列 —— 挑一个，或者说混搭。"),
]

剧本 = [
    ("《觉醒》剧本（74 格 · 66 句台词）", r"影匠\作品\觉醒\_剧本.html",
     "**谁都能读的一版。** 一句话故事 → 人物（带定妆照）→ 五幕 → 逐格表。"
     "逐格表每格只有三列：第几格和它的时刻 / 画面上是什么 / 谁说了什么。"),
    ("《磨刀》剧本（45 格 · 51 句台词）", r"影匠\作品\磨刀\_剧本.html", "同上。"),
    ("《雪线》剧本（45 格 · 7 句台词）", r"影匠\作品\雪线\_剧本.html",
     "它没有 `00-故事.md`，所以没有一句话故事和五幕表 —— 台词是从配音的 srt 按时刻反推回格子的。"),
    ("《试镜》剧本（9 格）", r"影匠\作品\试镜\_剧本.html", "最早的一条，单场戏。"),
]

证据 = [
    ("定妆照总表（三部戏 11 个人物）", r"影匠\作品\_定妆照总表.png",
     "每张是「正面半身 + 正面全身」同一个人的影棚图，「定位」逐字抄自各戏的锚点表。"),
    ("超分对比 · 开头 12 秒（左右并排，带声音）", r"影匠\作品\_超分试验\对比_觉醒开头12s.mp4",
     "左 1280x704 · 右 2560x1408。同一段 SeedVR2 跑了 **974 秒**（81 秒/秒视频）。"),
    ("超分对比 · 1:1 像素对照", r"影匠\作品\_超分试验\对比_觉醒开头12s.png",
     "下排是同一个位置 1:1 —— 原片把 400x280 拉到 800x560，超分的 800x560 原样贴。"),
    ("《觉醒》第三版头一分钟", r"影匠\作品\觉醒\_开头验.png",
     "新加的两句台词（格2 旁白「册子上也没有他。」、格8 系统「册上无名。」）"
     "和两个新画面（格5/6 那页纸上有一道划掉的名字、格14 桌沿那摞引荐帖）。"),
    ("假字幕逐格查（全片 74 格）", r"影匠\作品\觉醒\_查假字幕.png",
     "每格取第 2 秒那一帧的下缘，数「三通道都 ≥235 的纯白像素」。"
     "**全片中位数就是 0.000%** —— 判据不是「偏高」，是「别人是 0，它是 1%」。"),
    ("起手式第一批 · 相邻帧差拉亮图", r"影匠\作品\觉醒\_起手式运动差.png",
     "全黑 = 冻住，有轮廓 = 在动。改前 / 改后 / 真实画面三列。"),
    ("起手式第二批 · 相邻帧差拉亮图", r"影匠\作品\觉醒\_起手式第二批运动差.png",
     "8 格平均 1.32×。格56 是这一批唯一的雷，已整格回退（宁可少一点动作，也不要画面上挂乱码白字）。"),
    ("《雪线》改动作 · 13 格", r"影匠\作品\雪线\_改动作验\十三格.png",
     "平均 2.78×。逐个看过，没有假字幕。"),
    ("《雪线》成片抽查四帧", r"影匠\作品\雪线\_改动作验\成片验.png",
     "122.5s 摘面罩 / 171.0s 扑在雪上 / 82.5s「站住。」/ 42.0s「十年了。」"),
    ("控制台 · 进度条在跑的那一刻", r"_归档\截图\控制台_进度条.png",
     "`格 1 / 3` + 33% + 「预计还要 5 分 51 秒」，同一屏的日志就是 `[1/3] ✓ 格19 175.9 秒 2.33 MB 空院子`。"),
    ("依据面板的内容", r"_归档\截图\依据窗_内容.png",
     "这一轮 333 次工具 / 25 份文件 / 读 59 · 写 97 · 跑 141。"),
]

还欠 = [
    ("P1⑦ 上传 GitHub", "**只差你一个 token**", 
     "仓库早就装好了：`D:\\DSHworkspace\\_GitHub\\影匠工作台\\`，36 个文件，5 次提交。"
     "先在 <https://github.com/new?name=yingjiang-workbench> 建一个空仓库，然后敲：<br>"
     "`python D:\\DSHworkspace\\_推仓库.py --token ghp_你的token`"),
    ("P2-1 超分方案选型", "数据齐了，等你拍板",
     "SeedVR2 实测：12 秒片用 974 秒，严格 2×（1280x704 → 2560x1408）。"
     "**全片 302.54 秒外推 ≈ 6.8 小时**。要不要现在跑整部？"),
    ("P2-2 软件界面选型", "三个草图已交，等你挑",
     "甲 仪表盘 / 乙 剪辑台 / 丙 任务队列 —— 回一句「甲」就行，也可以混搭。"),
    ("P2-3 网盘 A 组 36.73 GB", "**没删，等你点头**",
     "查清了是什么。规矩一：删任何东西之前先给你核对。"),
    ("P2-4 模型路由表", "等你拍板", "真人用哪个模型、动漫用哪个。"),
    ("虚拟内存", "要管理员权限", "你 10-14 01:57 提过一次，至今一次没查。"),
    ("微信对话", "没做", "台账 #4，只做了邮箱发成品。"),
    ("《雪线》的核心矛盾位置", "仍是 67%", 
     "《磨刀》25% · 《觉醒》已改到 2.7% —— **《雪线》还没按这个方子改**。"
     "它的反转「……是我。」在最冻的那几格之后，观众前面不知道在等什么。"),
]


def 尺寸(相对):
    p = os.path.join(根, 相对)
    if not os.path.isfile(p):
        return None
    n = os.path.getsize(p)
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{n / 1024:.0f} KB"


def 美化(s):
    """卡片说明里的 `**粗体**` 和 `` `代码` `` 要真渲染出来 —— 不然页面上是一堆星号。"""
    import html as _h
    import re as _re
    s = _h.escape(s)
    s = s.replace("&lt;br&gt;", "<br>")
    s = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = _re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def 卡(标题, 说明, 相对=None, 是图=False):
    在 = 相对 is None or os.path.isfile(os.path.join(根, 相对))
    尺 = 尺寸(相对) if 相对 else None
    徽 = f'<span class="尺">{尺}</span>' if 尺 else ""
    if not 在:
        徽 = '<span class="尺 缺">文件不在</span>'
    h = f'<div class="卡"><div class="头"><b>{标题}</b>{徽}</div><p>{美化(说明)}</p>'
    if 相对 and 在:
        u = 相对.replace("\\", "/")
        if 是图:
            h += f'<a href="{u}" target="_blank"><img src="{u}" loading="lazy"></a>'
        else:
            h += f'<video src="{u}" controls preload="metadata"></video>'
    h += "</div>"
    return h


def 链接卡(标题, 网址, 说明):
    return (f'<div class="卡"><div class="头"><b>{标题}</b></div><p>{美化(说明)}</p>'
            f'<a class="钮" href="{网址}" target="_blank">打开 →</a></div>')


现在 = datetime.now().strftime("%Y-%m-%d %H:%M")

剧本卡 = ""
for 题, 路, 说 in 剧本:
    尺 = 尺寸(路)
    徽 = f'<span class="尺">{尺}</span>' if 尺 else '<span class="尺 缺">文件不在</span>'
    u = 路.replace("\\", "/")
    r = f"""<div class="卡"><div class="头"><b>{题}</b>{徽}</div><p>{美化(说)}</p>""" + \
        f'<a class="钮" href="{u}" target="_blank">打开剧本 →</a></div>'
    剧本卡 += r

页 = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>影匠工作台 · 验收</title>
<style>
:root{{--bg:#0f1115;--卡:#171b25;--边:#262c3a;--字:#e6e8ee;--小:#7c8798;
      --吉:#3ddc84;--凶:#ff5b5b;--警:#f5c542}}
*{{box-sizing:border-box}}
body{{margin:0;padding:26px 30px 60px;background:var(--bg);color:var(--字);
     font:15px/1.75 "Microsoft YaHei",system-ui,sans-serif}}
h1{{font-size:26px;margin:0 0 6px}}
h2{{font-size:19px;margin:38px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--边)}}
.副{{color:var(--小);font-size:14px;margin:0 0 4px}}
.格{{display:grid;grid-template-columns:repeat(auto-fill,minmax(430px,1fr));gap:16px}}
.卡{{background:var(--卡);border:1px solid var(--边);border-radius:10px;padding:16px 18px}}
.头{{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:6px}}
.卡 p{{margin:0 0 10px;color:#c3c9d6;font-size:14px}}
.尺{{color:var(--小);font-size:12.5px;white-space:nowrap}}
.缺{{color:var(--凶)}}
.卡 img,.卡 video{{width:100%;border-radius:6px;display:block;background:#000}}
.钮{{display:inline-block;background:#1f6f43;color:#fff;text-decoration:none;
     padding:7px 16px;border-radius:6px;font-size:14px}}
.钮:hover{{background:#2a8f57}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{border:1px solid var(--边);padding:9px 12px;text-align:left;vertical-align:top}}
th{{background:#1b2130;color:var(--小);font-weight:400;white-space:nowrap}}
code{{background:#1b2130;padding:2px 7px;border-radius:4px;font-size:13px;color:#9fd3b4}}
.吉{{color:var(--吉)}} .凶{{color:var(--凶)}} .警{{color:var(--警)}}
</style></head><body>

<h1>影匠工作台 · 验收</h1>
<p class="副">生成于 {现在}　·　每一样都能点开：图点开看大图，片子点开就能放，界面点开是新标签页</p>

<h2>一、你桌面上那三个图标</h2>
<div class="格">
{''.join(链接卡(*x) for x in 界面)}
</div>

<h2>二、四部片子（点开就能放）</h2>
<div class="格">
{''.join(卡(标题, 说明, 相对) for 标题, 相对, 说明 in 四部戏)}
</div>

<h2>三、剧本（谁都能读的那一版）</h2>
<p class="副">原先的「剧本」是四份给机器看的 md，加起来 188 KB，没有人会读它。
这一版把它抽成一条线：<b>一句话故事 → 人物（带定妆照）→ 五幕 → 逐格表</b>。一个字都没有新写。</p>
<div class="格">
{剧本卡}
</div>

<h2>四、这次做出来的东西（点开看图 / 看片）</h2>
<div class="格">
{''.join(卡(标题, 说明, 相对, 是图=not 相对.lower().endswith(".mp4")) for 标题, 相对, 说明 in 证据)}
</div>

<h2>四、还欠你的（没做完就说没做完）</h2>
<table>
<tr><th>哪一件</th><th>卡在哪</th><th>说明</th></tr>
{''.join(f'<tr><td><b>{a}</b></td><td class="警">{美化(b)}</td><td>{美化(c)}</td></tr>' for a, b, c in 还欠)}
</table>

<h2>五、这一整轮踩的坑（原样留着，不美化）</h2>
<table>
<tr><th>#</th><th>坑</th><th>判据 / 现在的做法</th></tr>
<tr><td>1</td><td>模型把提示词里的<strong>动作句</strong>当字幕画进了画面（全片 4 格中招，交给你的那版里就有）</td>
<td>逐格量「下缘纯白像素占比」—— <strong>先找一个干净时期望值就是 0 的量</strong>，判据是「别人是 0，它是 1%」</td></tr>
<tr><td>2</td><td>那把「运动量」的尺子 <strong>58–71% 是噪点</strong>（压缩抖动、光影闪动全算进去了）</td>
<td>量之前先 <code>gblur=sigma=3</code>；报「提升 N 倍」时 <strong>N&lt;1.2 一律标「在噪声里」</strong>（同种子重跑的波动约 ±15%）</td></tr>
<tr><td>3</td><td>拉亮帧差图用 <code>eq=contrast</code> 拉不出来，出来全黑，看着像「都没动」</td>
<td>必须 <code>curves=all='0/0 0.02/1'</code> —— 帧差本身才 0.5–2 个灰度级</td></tr>
<tr><td>4</td><td>备份脚本 <code>shutil.copy2</code> 的目标<strong>忘了拼文件名</strong>，7 个段互相覆盖成一个叫「段」的文件</td>
<td>复制完<strong>数一遍个数对不对</strong>；现在一律用 <code>_备份格.py</code></td></tr>
<tr><td>5</td><td>我报过一条<strong>不存在的「问题」</strong>（「《觉醒》台词挤得太靠后」）</td>
<td>说有问题之前<strong>先把那个数算出来</strong>；比较两个数先确认是同一把尺子。已写进 <code>影匠\\知识\\假判据族.md</code> 第八族</td></tr>
<tr><td>6</td><td>定妆照的「定位」那一行我凭记忆手写，<strong>五个错了四个</strong></td>
<td>凡是「从别处抄一行字」的地方，就真去读那个文件</td></tr>
<tr><td>7</td><td>锚点里写「围裙（颜色是灰的，<strong>绝不是白色</strong>）」，模型照样画成米白</td>
<td><strong>否定写法等于没说</strong> —— 要描述它是什么，不要描述它不是什么（跟「别在提示词里提『字幕』这个词」是同一个病）</td></tr>
<tr><td>8</td><td>PyInstaller 只顺着入口的 import 找依赖，<code>--add-data</code> 进去的 .py 的 import 它不看</td>
<td>exe 起来、页面全绿，第一条直调就 <code>ModuleNotFoundError: No module named 'uuid'</code>。用 <code>ast</code> 算差集补 <code>--hidden-import</code></td></tr>
</table>

<p class="副" style="margin-top:40px">
规矩一：删任何东西之前，先给你核对。这份页面里没有删过任何东西。<br>
汇报第一行永远是「我加的条件：___」—— 这一轮是<strong>无</strong>。
</p>
</body></html>
"""

io.open(出, "w", encoding="utf-8", newline="\n").write(页)
print(f"  ✓ {出}　{os.path.getsize(出):,} B")

# 桌面快捷方式
import subprocess
lnk = r"C:\Users\青\Desktop\验收.lnk"
ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
      f"$s.TargetPath='{出}';$s.Description='影匠工作台 · 验收';$s.Save()")
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, text=True, errors="replace")
if os.path.isfile(lnk):
    print(f"  ✓ 桌面快捷方式：{lnk}")
else:
    print(f"  ✗ 快捷方式没建成：{r.stderr[:200]}")
