# -*- coding: utf-8 -*-
"""_看连片进度.py —— 远端官方长片跑到第几个渲染窗了。

原理：那个节点每跑完一个渲染窗就落一次盘，文件名带窗口号
      `H3___1016_1154_r00NN_cosine_bridge.mp4`（小样跑完 5 个窗时叫 r0005）。
      所以「最大的 NN」= 已经跑完几个窗，除以总窗数就是进度。
      这是从远端 /queue 里那个正在跑的 prompt 自己读出来的链号，不是我猜的。

用法：python _看连片进度.py
"""
import sys
import time
import urllib.request
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8")

远端 = "http://100.127.224.106:8188"
总帧 = 7179
渲染窗 = 124
上下文 = 22
窗尺寸 = 渲染窗 - 上下文
总窗 = max(1, (总帧 + 窗尺寸 - 1) // 窗尺寸)


def 取正在跑的():
    import json
    with urllib.request.urlopen(远端 + "/queue", timeout=10) as r:
        q = json.load(r)
    for it in q.get("queue_running", []):
        for k, n in (it[2] or {}).items():
            if n.get("class_type") == "MiniMaxH3LongVideoInNodeLoopEffectsT8Advanced":
                i = n["inputs"]
                return it[1], i.get("chain_id"), i.get("filename_prefix")
    return None, None, None


def 试(fn, sub):
    q = urllib.parse.urlencode({"filename": fn, "subfolder": sub, "type": "output"})
    try:
        req = urllib.request.Request(远端 + "/view?" + q, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as r:
            return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return None


pid, 链号, 前缀 = 取正在跑的()
if not 链号:
    print("远端队列里没有正在跑的长片节点。")
    print(f"（按上次读到的：链号 chuzihang_20261016_115413　前缀 H3_连片_1016_1154）")
    print(f"  总帧 {总帧}　渲染窗 {渲染窗}　上下文 {上下文}　→ 共 {总窗} 个窗")
    sys.exit(0)

安全 = "".join(c if c.isascii() and (c.isalnum() or c in "._-") else "_" for c in 前缀)
sub = "minimax_h3_t8_long_video/%s/assembled" % 链号
print(f"prompt {pid}")
print(f"链号 {链号}　前缀 {前缀}（远端把它洗成 {安全}）")
print(f"总帧 {总帧}　渲染窗 {渲染窗}　上下文 {上下文}　→ 共 {总窗} 个窗")
print(f"目录 {sub}\n")

有 = []
for n in range(1, 总窗 + 1):
    fn = "%s_r%04d_cosine_bridge.mp4" % (安全, n)
    大 = 试(fn, sub)
    if 大 is not None:
        有.append((n, fn, 大))
print(f"落盘的窗：{len(有)} / {总窗}")
for n, fn, 大 in 有[-4:]:
    print(f"   r{n:04d}　{大:>13,} B")
if 有:
    n = 有[-1][0]
    print(f"\n进度 ≈ {n}/{总窗} = {100.0*n/总窗:.1f}%")
else:
    print("\n一个窗都还没落盘 —— 要么还在第 1 个窗里，要么产物只在最后一次性落地")
