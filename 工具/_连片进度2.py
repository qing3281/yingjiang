# -*- coding: utf-8 -*-
"""_连片进度2.py —— 官方长片跑到哪儿了 / 什么时候落地。

★ 上一版写错了：我拿远端日志里「`1/8 [` 出现过几次」当已开窗数，结果打出「0 / 71」。
   原因是 `/internal/logs/raw` **只留最近 300 条**（实测只覆盖 90 秒），早先的窗全滚掉了。
   → 数日志数不出进度，这个文件现在改成**用起跑时刻 + 日志里的实时 s/step** 推。

用法：python _连片进度2.py [起跑时刻 HH:MM:SS]
      起跑时刻不给的话，从远端 /queue 里那个 prompt 的链号尾 6 位读（chuzihang_20261016_115413）。
"""
import re
import sys
import json
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

远端 = "http://100.127.224.106:8188"
总帧 = 7179
渲染窗 = 124
上下文 = 22
窗步 = 渲染窗 - 上下文
总窗 = max(1, (总帧 + 窗步 - 1) // 窗步)


def 读队列():
    with urllib.request.urlopen(远端 + "/queue", timeout=15) as r:
        q = json.load(r)
    for it in q.get("queue_running", []):
        for _k, n in (it[2] or {}).items():
            if n.get("class_type") == "MiniMaxH3LongVideoInNodeLoopEffectsT8Advanced":
                i = n["inputs"]
                return it[1], i.get("chain_id"), i.get("total_duration_seconds")
    return None, None, None


def 读速率():
    """从日志里拿最后一个 `N/8 [已用<剩余, x.xxs/it]`。"""
    with urllib.request.urlopen(远端 + "/internal/logs/raw", timeout=20) as r:
        条 = json.loads(r.read().decode("utf-8", "replace"))["entries"]
    文 = "\n".join(e.get("m", "") for e in 条)
    末 = re.findall(r"(\d+)/8 \[(\d+):(\d+)<(\d+):(\d+),\s*([\d.]+)s/it\]", 文)
    if not 末:
        return None, len(条), (条[-1]["t"][11:19] if 条 else "?")
    a, b, c, d, e, s = 末[-1]
    return (int(a), int(b) * 60 + int(c), int(d) * 60 + int(e), float(s)), len(条), 条[-1]["t"][11:19]


起跑 = sys.argv[1] if len(sys.argv) > 1 else None
pid, 链号, 总秒 = 读队列()
if 链号 and not 起跑 and len(链号) >= 6 and 链号[-6:].isdigit():
    起跑 = "%s:%s:%s" % (链号[-6:-4], 链号[-4:-2], 链号[-2:])

print("远端 ComfyUI %s" % 远端)
print("prompt   %s" % (pid or "（队列里没有正在跑的长片节点）"))
print("链号     %s" % (链号 or "-"))
print("总帧 %d　渲染窗 %d　上下文 %d → 步进 %d 帧 → 共 %d 个窗" % (总帧, 渲染窗, 上下文, 窗步, 总窗))

速, 条数, 末刻 = 读速率()
if not 速:
    print("\n日志里没找到进度行（最近 %d 条，最后一条 %s）" % (条数, 末刻))
    sys.exit(0)

步, 已用, 剩余, 每步 = 速
每窗 = 8 * 每步
print("\n此刻：第 %d/8 步　本窗已用 %d:%02d　还差 %d:%02d　%.2f 秒/步" % (步, 已用 // 60, 已用 % 60, 剩余 // 60, 剩余 % 60, 每步))
print("       → 每个渲染窗 ≈ %.0f 秒（8 步）" % 每窗)

if 起跑:
    h, m, s = (int(x) for x in 起跑.split(":"))
    今 = time.localtime()
    起 = time.mktime((今.tm_year, 今.tm_mon, 今.tm_mday, h, m, s, 0, 0, -1))
    走 = max(0.0, time.time() - 起)
    完 = int(走 / 每窗)
    余 = max(0, 总窗 - 完)
    print("\n起跑 %s　已跑 %.0f 分钟" % (起跑, 走 / 60))
    print("★ 按这个速率已经跑完 ≈ %d / %d 个窗（%.0f%%）" % (完, 总窗, 100.0 * 完 / 总窗))
    print("   剩 %d 个窗 ≈ %.0f 分钟" % (余, 余 * 每窗 / 60))
    print("   → 大约 **%s** 落地" % time.strftime("%H:%M", time.localtime(time.time() + 余 * 每窗)))
else:
    print("\n（链号里没读出起跑时刻，给一个参数：python _连片进度2.py 11:54:13）")
