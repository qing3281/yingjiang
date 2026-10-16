# -*- coding: utf-8 -*-
"""看远端 ComfyUI 在干什么 —— 队列里跑的是哪一格、最近完成了哪几格。

为什么单写一个脚本：PowerShell 的 ConvertFrom-Json 读这个 history 会炸
（「找到 Round 的多个不确定重载」），Invoke-WebRequest 在非交互模式还会直接报错。
用 urllib 拿原始 JSON 最稳。
"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
端点 = sys.argv[1] if len(sys.argv) > 1 else "http://100.127.224.106:8188"


def 拿(路):
    with urllib.request.urlopen(端点 + 路, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def 提示词摘要(pr):
    """从 ComfyUI 的 prompt 图里抽出这一格是第几格（找我们的正提示词里的『第N格』）。"""
    try:
        节点 = pr["prompt"]
        for k, v in 节点.items():
            t = (v.get("inputs") or {}).get("text")
            if isinstance(t, str) and t.startswith("第") and "格" in t[:8]:
                return t[:8].replace("\n", " ")
        # FL2VA 的话，找出 LoadImage 的名字
        for k, v in 节点.items():
            if v.get("class_type") == "LoadImage":
                return "图=" + str(v["inputs"].get("image"))
    except Exception:
        pass
    return "?"


print("══ 队列 ══")
q = 拿("/queue")
跑 = q.get("queue_running", [])
排 = q.get("queue_pending", [])
print("  运行中 %d　排队 %d" % (len(跑), len(排)))
for i, x in enumerate(跑):
    print("    [跑%d] %s  %s" % (i, x[1][:8], 提示词摘要(x[2])))
for i, x in enumerate(排):
    print("    [排%d] %s  %s" % (i, x[1][:8], 提示词摘要(x[2])))

print()
print("══ 最近完成 ══")
h = 拿("/history?max_items=40")
if not h:
    print("  （历史是空的）")
else:
    条 = []
    for k, v in h.items():
        st = v.get("status", {})
        msgs = st.get("messages") or []
        何时 = 0
        for m in msgs:
            if m and m[0] == "execution_start":
                何时 = m[1].get("timestamp", 0)
        条.append((何时, k, st.get("status_str"), 提示词摘要(v.get("prompt") or [None, None, {}] if isinstance(v.get("prompt"), list) else {})))
    条.sort()
    for 何时, k, s, d in 条[-12:]:
        print("  %s  %-10s %s" % (k[:8], s, d))
print()
print("  （完成数 %d）" % len(h))
