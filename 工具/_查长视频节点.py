# -*- coding: utf-8 -*-
"""查「长视频内循环 + Prompt Relay」这两个节点的入参名与顺序。

为什么要这个：示例 JSON 是 UI 格式（widgets_values 是一串没有名字的值）。
要照它搭 API 格式的图，必须知道**第几个值对应哪个入参名** —— 猜错一位，
整张图就是错的，而报错可能要到采样时才炸。
"""
import sys, json, urllib.request

sys.stdout.reconfigure(encoding="utf-8")

节点们 = [
    "MiniMaxH3LongVideoInNodeLoopEffectsT8Advanced",
    "MiniMaxH3PromptRelayPlanT8Advanced",
    "MiniMaxH3LongVideoSamplingPlanT8Advanced",
]
端点们 = {
    "本机": "http://127.0.0.1:8188",
    "远端": "http://100.127.224.106:8188",
}


def 拉(服务, 名):
    try:
        with urllib.request.urlopen(f"{服务}/object_info/{名}", timeout=30) as r:
            return json.load(r)
    except Exception as e:
        return {"错": str(e)}


for 端点名, 服务 in 端点们.items():
    print("=" * 70)
    print(f"【{端点名}】{服务}")
    for 名 in 节点们:
        信 = 拉(服务, 名)
        if not 信 or 名 not in 信:
            print(f"  ✗ {名} —— 没有这个节点（返回 {list(信)[:3] if 信 else '空'}）")
            continue
        必 = 信[名]["input"].get("required", {})
        选 = 信[名]["input"].get("optional", {})
        print(f"  ✓ {名}   required {len(必)} 项 / optional {len(选)} 项")
        for i, (k, v) in enumerate(必.items(), 1):
            型 = v[0] if isinstance(v[0], str) else "COMBO"
            默 = ""
            if isinstance(v[0], list):
                型 = "COMBO"
                默 = f" 选项{len(v[0])}个 首个={v[0][0] if v[0] else ''}"
            elif len(v) > 1 and isinstance(v[1], dict):
                d = v[1].get("default", "—")
                默 = f" 默认={d}"
                for kk in ("min", "max", "step"):
                    if kk in v[1]:
                        默 += f" {kk}={v[1][kk]}"
            print(f"      {i:2d}. {k} : {型}{默}")
        if 选:
            print("      -- optional --")
            for k, v in 选.items():
                型 = v[0] if isinstance(v[0], str) else "COMBO"
                print(f"         {k} : {型}")
        print()
