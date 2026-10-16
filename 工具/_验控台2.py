# -*- coding: utf-8 -*-
"""验 `影匠/_控台.py` 第 35 轮新加的两块：ComfyUI 官方接口 + agent 接管。

★ 为什么不用 PowerShell 的 Invoke-WebRequest：中文放进 `-Body '...'` 里，
  PowerShell 到底按 UTF-8 还是 UTF-16 发出去要试才知道；而且 JSON 里的引号
  要跟 PowerShell 的引号打架。**要验接口就用真的客户端**，别隔着两层壳猜。
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
口 = sys.argv[1] if len(sys.argv) > 1 else "8793"
基 = f"http://127.0.0.1:{口}"


def 打(路, 体=None, 法=None, 超时=30):
    数 = json.dumps(体).encode("utf-8") if 体 is not None else None
    r = urllib.request.Request(基 + 路, data=数, method=法 or ("POST" if 数 else "GET"),
                               headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(r, timeout=超时) as f:
            return f.status, json.loads(f.read())
    except urllib.error.HTTPError as e:
        return e.code, {"错": (e.read() or b"")[:300].decode("utf-8", "replace")}
    except Exception as e:
        return None, {"错": f"{type(e).__name__}: {e}"}


失败 = 0


def 看(名, 好, 说明=""):
    global 失败
    if 好:
        print(f"  ✓ {名}　{说明}")
    else:
        print(f"  ✗ {名}　{说明}")
        失败 += 1


print("=== 一、只读面：两台机器 × 四个面 ===")
for 机 in ("本机", "远端"):
    for 面 in ("queue", "history", "system_stats", "object_info"):
        c, j = 打(f"/api/comfy?machine={urllib.parse.quote(机)}&face={面}")
        if j.get("活"):
            长 = len(json.dumps(j, ensure_ascii=False))
            看(f"{机}/{面}", True, f"{长:,} 字符　{j.get('说','')}")
        else:
            看(f"{机}/{面}", False, str(j.get("错"))[:90])

print("\n=== 二、写面：打断 / 清待办（此刻两台都没活，动它不会弄坏任何东西）===")
for 机 in ("本机", "远端"):
    c, j = 打("/api/comfy", {"machine": 机, "action": "打断"})
    看(f"{机} 打断", bool(j.get("ok")), str(j.get("说") or j.get("错"))[:90])
    c, j = 打("/api/comfy", {"machine": 机, "action": "清待办"})
    看(f"{机} 清待办", bool(j.get("ok")), str(j.get("说") or j.get("错"))[:90])

print("\n=== 三、不认的动作必须挡住 ===")
c, j = 打("/api/comfy", {"machine": "本机", "action": "删库跑路"})
看("乱来的动作被挡", (not j.get("ok")) and "不认" in str(j.get("错")), str(j.get("错"))[:80])
c, j = 打("/api/comfy", {"machine": "火星", "action": "打断"})
看("不存在的机器被挡", not j.get("ok"), str(j.get("错"))[:80])

print("\n=== 四、agent 接管：写进去、读回来 ===")
c, j = 打("/api/handoff", {"what": "【自测】这一行等下我来删", "why": "验 /api/handoff 能不能写",
                        "want": "读完就把它删掉"})
看("写一件事", bool(j.get("ok")), str(j.get("说") or j.get("错"))[:90])
c, j = 打("/api/handoff")
行 = j.get("行") or []
看("读回来", any("【自测】" in (x[1] if len(x) > 1 else "") for x in 行),
   f"一共 {len(行)} 行；末行 = {行[-1] if 行 else '（空）'}")

print(f"\n{'★ 全过' if 失败 == 0 else f'✗ 有 {失败} 项没过'}")
sys.exit(1 if 失败 else 0)
