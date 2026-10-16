# -*- coding: utf-8 -*-
"""_写保命清单.py —— 把「今天这一整套活干下来真正在用的脚本」写进 `_保命清单.txt`。

为什么还要人手列一张：`_盘点4.py` 的传递闭包只能找到**已经被别处提到**的脚本。
我今天新写的（`_出官方片.py`、`_验超分片.py`、`_寄片.py`…）还没被任何文档引用，
闭包看不见它们 —— 差点当成一次性脚本搬走。
**判「谁还在用」时，文档闭包 + 生产代码闭包 + 人手确认，三样缺一不可。**
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"

保 = """
# ── 生产：出片 / 超分 / 装配 / 交付 ──
_出连片.py
_取连片.py
_看连片进度.py
_连片进度2.py
_连片进度3.py
_查长视频节点.py
_出官方片.py
_超分.py
_超分分段.py
_超分装配.py
_看超分.py
_看2x.py
_寄片.py
_寄官方片.py
_建桌面.py
_建桌面2.py
_建快捷方式.py
_配音楚子航.py

# ── 关键帧 / 中间帧那一摊（结论都进了经验库）──
_查中间帧提示词.py
_试中间帧.py
_试中帧2.py
_重出中间帧.py
_试纯文生图.py
_试多关键帧.py
_出H3.py

# ── 子镜 / 质量闸 / 配音 ──
_查子镜质量.py
_修一人一嗓.py
_验成片2.py
_量楚子航.py
_量动没动.py
_归档非链.py

# ── 看图 / 量数（我拿来判断的那些刀）──
_看落点.py
_看跳帧.py
_看格32.py
_比格32.py
_换格32.py
_看官方刀.py
_看新中帧.py
_试字号.py
_试边距.py

# ── check_* 一族（验收用的，跟工具同等重要）──
check_html.py
check_接缝.py
check_落点.py
check_走了几成.py
check_子镜落点.py
check_官方动没动.py
check_官方格缝.py
check_2x拼缝.py
check_32格都有词.py
check_字幕宽度.py
check_字幕溢出.py
check_zimu.py
check_hunyin.py
check_burn.py
check_srt.py
check_末尾.py
check_peiyin_files.py
check_peiyin_dup.py
check_dub_batch.py
check_yan.py
check_argv.py
check_jiezi.py
check_seam.py
check_jielun.py
check_怪帧.py
check_试用.py
check_末帧.py
check_jiepian.py
check_i2va.py
check_dub.py

# ── 记忆 / 台账 / 自查（AGENTS.md 里点名要跑的那几条）──
_开工.py
_记忆.py
_整理记忆.py
_记忆自查.py
_丢人了.py
_又犯了.py
_找复发.py
_候你点头.py
_生成欠账总表.py
_承诺自检.py
_核台账.py
_压缩台账.py
_查我答偏了.py
_查无名指代.py
_该补判据.py
_判据挂命令.py
_用户原话.py
_耗账簿.py
_记忆台.py
_开台.py
_重启台.py
_守护台.py
_归档会话.py
_知识索引.py

# ── 远端 / 环境 ──
_远端.py
_远端体温.py
_看远端.py
_看远端状态.py
_看远端队列.py
_远端看进度.py
_起本机.py
_重启Comfy.py
_导出仓库.py
_推仓库.py
_生成三件套.py

# ── 内容闸（提示词/字幕/公共段落那几张网）──
_总检查.py
_查假字.py
_查假字幕.py
_查公共段落.py
_查画面字幕.py
_查字幕残留.py
_逐格查字幕.py
_出图前闸.py
_四步_楚子航.py
_查连贯.py
_看首尾帧.py
_拼运动差图.py

# ── 整理工作区本身 ──
_盘点.py
_盘点2.py
_盘点3.py
_盘点4.py
_写保命清单.py
_大扫除.py
_补汇报页.py
_补经验32.py
_补经验33.py
"""

名们 = []
for L in 保.splitlines():
    L = L.strip()
    if L and not L.startswith("#"):
        名们.append(L)

在 = [f for f in 名们 if os.path.isfile(os.path.join(根, f))]
缺 = [f for f in 名们 if f not in 在]
with open(os.path.join(根, "_保命清单.txt"), "w", encoding="utf-8") as fp:
    fp.write("\n".join(在) + "\n")
print("✓ 写 _保命清单.txt　%d 个在磁盘上" % len(在))
if 缺:
    print("（列了但磁盘上没有的 %d 个，已略过）" % len(缺))
    for f in 缺[:20]:
        print("   ", f)
