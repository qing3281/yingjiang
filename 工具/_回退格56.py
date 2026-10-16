# -*- coding: utf-8 -*-
r"""★ 格56 整格回退 —— 这一格的「起手式」方子治不好假字幕。

## 事是怎么发生的

格56 改完起手式之后动作量 0.429 → 0.884（**2.06×**，第二批里最好的一格），
可是模型在画面下缘那条亮桌面上画了两行字：**「你得照的很平」/「几乎没差册点」**
—— 这两句本来就是这一格 `光色` 字段里的话（「把他的正面照得很平、几乎没有阴影」）。

按 `影匠\知识\假字幕.md` 的方子补了一刀**「用前景占住画面下缘」**（手 + 袖口 + 半卷册子 + 砚台边），
重出之后：纯白占比 0.516% → 0.415%，**字还在**（「照得很平」/「几乎没有册」）。

## 结论：这一格退回原样

新首帧换来的是「动作从 0.43 涨到 0.69」，代价是画面上挂着两秒多的乱码白字。
**乱码白字是观众一眼就看见的硬伤，动作量是个统计数** —— 两害相权，退回。
（原先那一版 `_起手式2前_20261015-053015` 里一个字都没有，是干净的。）

## 这个脚本做四件事

1. `段\格56_远端.mp4` ← 从备份覆盖回去（**旧的干净版**）
2. `段\格56_本机.mp4` → 移到 `_假字幕废\`（不删 —— 规矩一：删之前要给人看）
3. `01_格56.png` ← 从备份覆盖回去
4. `02-九宫格.md` 里格56 的两处改动**反向改回来**（起手式那处 + 下缘那处）

用法：python _回退格56.py [--看]
"""
import io
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace\影匠\作品\觉醒"
备 = os.path.join(根, "_起手式2前_20261015-053015")
废 = os.path.join(根, "_假字幕废")
九宫格 = os.path.join(根, "02-九宫格.md")

# 反向替换：(现在的文字, 改回的文字, 说明)
反改 = [
    ("他左手按在桌上一本摊开的厚册子上，右手刚从册子边上抬起来、还没有抬到胸口，"
     "手掌正在摊开、还没有摊平，就要往院子里的那队年轻后生那边比过去。",
     "他左手按在桌上一本摊开的厚册子上，右手抬起来往身侧比了一下，比的方向是院子里的那队年轻后生。",
     "起手式那处"),
    ("**画面最下缘被前景占住**：一只搭在桌沿上的手和它的深青布袖口压得极低、横在画面最下面，"
     "旁边还压着半卷摊开的册子和一个砚台的边，这几样一起把桌子挡掉大半，这一条占掉画面下面约五分之一。",
     "**桌子只在画面最下沿露出很窄的一条**，上面是册子的边、一方砚台、一个装笔的竹筒，占不到画面高度的五分之一。",
     "下缘那处"),
]


def 主():
    干跑 = "--看" in sys.argv

    计划 = [
        (os.path.join(备, "段", "格56_远端.mp4"), os.path.join(根, "段", "格56_远端.mp4"), "覆盖"),
        (os.path.join(根, "段", "格56_本机.mp4"), os.path.join(废, "格56_本机_带假字幕.mp4"), "移走"),
        (os.path.join(备, "01_格56.png"), os.path.join(根, "01_格56.png"), "覆盖"),
    ]
    for 源, 目, 做 in 计划:
        print(f"  {'[干跑] ' if 干跑 else ''}{做}　{os.path.basename(源)} → {目}"
              + ("" if os.path.isfile(源) else "　✗ 源不在"))

    原文 = io.open(九宫格, encoding="utf-8").read()
    m = re.search(r"\n## 格56(?=[^\d])(.*?)(?=\n## |\Z)", 原文, re.S)
    if not m:
        print("  ✗ 九宫格里找不到格56")
        return 1
    块 = m.group(1)
    for 今, 旧, 说 in 反改:
        print(f"  九宫格 {说}：出现 {块.count(今)} 次" + ("　✓" if 块.count(今) == 1 else "　✗ 要求 1 次"))

    if 干跑:
        return 0

    os.makedirs(废, exist_ok=True)
    shutil.copy2(os.path.join(备, "段", "格56_远端.mp4"), os.path.join(根, "段", "格56_远端.mp4"))
    print(f"  ✓ 段\\格56_远端.mp4 ← 干净版 {os.path.getsize(os.path.join(根, '段', '格56_远端.mp4')):,} B")
    if os.path.isfile(os.path.join(根, "段", "格56_本机.mp4")):
        shutil.move(os.path.join(根, "段", "格56_本机.mp4"), os.path.join(废, "格56_本机_带假字幕.mp4"))
        print(f"  ✓ 段\\格56_本机.mp4 → _假字幕废\\（不删）")
    shutil.copy2(os.path.join(备, "01_格56.png"), os.path.join(根, "01_格56.png"))
    print(f"  ✓ 01_格56.png ← 干净版 {os.path.getsize(os.path.join(根, '01_格56.png')):,} B")

    新块 = 块
    for 今, 旧, 说 in 反改:
        新块 = 新块.replace(今, 旧, 1)
    新文 = 原文[:m.start(1)] + 新块 + 原文[m.end(1):]
    备九 = os.path.join(根, f"_bak_九宫格_回退格56前.md")
    shutil.copy2(九宫格, 备九)
    io.open(九宫格, "w", encoding="utf-8", newline="\n").write(新文)
    print(f"  ✓ 02-九宫格.md 格56 已改回　{len(原文.encode()):,} → {len(新文.encode()):,} B（备份 {os.path.basename(备九)}）")
    print(f"\n  ★ 段\\ 现在格56 只剩："
          + ", ".join(sorted(c for c in os.listdir(os.path.join(根, '段')) if c.startswith('格56_'))))
    return 0


if __name__ == "__main__":
    sys.exit(主())
