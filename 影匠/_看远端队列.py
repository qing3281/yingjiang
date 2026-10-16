# -*- coding: utf-8 -*-
"""直接问远端 ComfyUI 的 /queue 和 /history，而不是猜。

为什么要直接问：日志里那句 `HTTP Error 400` 是**没有正文的**，
分不清「工作流被拒」还是「提交成功但跑挂了」。服务端的 /queue 才是真相。
"""
import json
import sys
import urllib.request

服务 = "http://100.127.224.106:8188"



def 取(路):
    try:
        with urllib.request.urlopen(服务 + 路, timeout=30) as r:
            return json.load(r)
    except Exception as e:
        return {"__错__": repr(e)}


def main():
    q = 取("/queue")
    if "__错__" in q:
        print("✗ /queue 读不到：%s" % q["__错__"])
        return 1

    跑 = q.get("queue_running") or []
    等 = q.get("queue_pending") or []
    print("=== 远端队列 ===")
    print("  正在跑 %d 个　排队 %d 个" % (len(跑), len(等)))
    for 项 in 跑[:2]:
        try:
            号 = 项[1]
            图 = 项[2]
            节 = sorted({v.get("class_type") for v in 图.values() if isinstance(v, dict)})
            print("    ▶ prompt_id=%s  节点 %d 种：%s" % (号, len(节), ", ".join(节[:6])))
        except Exception as e:
            print("    (读不出：%r)" % e)
    for 项 in 等[:3]:
        print("    … 排队 %s" % (项[1] if len(项) > 1 else "?"))

    h = 取("/history?max_items=4")
    if "__错__" not in h:
        print("\n=== 最近历史 ===")
        键 = list(h.keys())
        print("  共 %d 条" % len(键))
        for k in 键[:4]:
            v = h[k]
            状 = v.get("status", {})
            print("    %s  status=%s  completed=%s" % (
                k[:8], 状.get("status_str"), 状.get("completed")))
            for m in (状.get("messages") or [])[:4]:
                print("        %s" % (str(m)[:200]))
            # 输出文件
            出 = v.get("outputs") or {}
            for nid, o in 出.items():
                for kk in ("gifs", "videos", "audio", "images"):
                    for f in (o.get(kk) or []):
                        print("        出 %s/%s" % (kk, f.get("filename")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
