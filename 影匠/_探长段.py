# -*- coding: utf-8 -*-
"""探长段：一段能出多少帧还站得住？

现在的流水线一段 = 49 帧 @16fps = 3.06 秒。3 分钟的片子就要 59 段，
分镜要写 59 格、接缝 58 处 —— 每处接缝都是脸/衣服/光线漂移的机会。

这段脚本试几档帧数，看画质什么时候开始塌。判定不靠"我觉得"，
靠三样硬东西：①出片宽高帧数（ffmpeg 读）②生成耗时 ③同一段跑两次的差异。

跑法：
    python _探长段.py --档 49,73,97,121 --端点 远端 --宽 1344 --高 768
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 引擎

这里 = os.path.dirname(os.path.abspath(__file__))


def 读片(路: str) -> dict:
    ff = os.path.join(这里, "_bin", "ffmpeg.exe")
    r = subprocess.run([ff, "-i", 路], capture_output=True, text=True, errors="replace")
    文 = (r.stderr or "") + (r.stdout or "")
    import re
    m = re.search(r"Video:\s.*?,\s*(\d{2,5})x(\d{2,5})(?=[\s,\[])", 文)
    m2 = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", 文)
    m3 = re.search(r"(\d+(?:\.\d+)?)\s*fps", 文)
    秒 = 0.0
    if m2:
        秒 = int(m2.group(1)) * 3600 + int(m2.group(2)) * 60 + float(m2.group(3))
    return {
        "宽": int(m.group(1)) if m else 0,
        "高": int(m.group(2)) if m else 0,
        "秒": round(秒, 2),
        "帧率": float(m3.group(1)) if m3 else 0.0,
        "字节": os.path.getsize(路) if os.path.exists(路) else 0,
    }


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--档", default="49,73,97,121", help="试哪几档帧数")
    ap.add_argument("--端点", default="远端")
    ap.add_argument("--宽", type=int, default=1344)
    ap.add_argument("--高", type=int, default=768)
    ap.add_argument("--帧率", type=int, default=16)
    ap.add_argument("--首帧", default=r"作品\试镜\01_格8.png")
    ap.add_argument("--种子", type=int, default=20261014)
    a = ap.parse_args()

    引擎.换端点(a.端点)
    在 = 引擎.在线()
    print(f"端点 {在.get('端点')}  在线 {在.get('在线')}  {在.get('显卡')}")
    if not 在.get("在线"):
        print("  ✗ 端点不在线：", 在.get("错"))
        return 1

    首帧 = a.首帧 if os.path.isabs(a.首帧) else os.path.join(这里, a.首帧)
    if not os.path.exists(首帧):
        print("  ✗ 找不到首帧", 首帧)
        return 1
    print(f"首帧 {首帧}")

    词 = ("银发剑客立于雪原，黑发黑衣白饰，挥剑斩出，积雪炸开，"
          "长发飞散，电影写实，冷蓝色调，雪花四溅")

    出 = os.path.join(这里, "作品", "长段")
    os.makedirs(出, exist_ok=True)

    行 = []
    for 档 in [int(x) for x in a.档.split(",") if x.strip()]:
        存 = os.path.join(出, f"长段_{档}帧.mp4")
        print(f"\n=== {档} 帧（理论 {档/a.帧率:.2f} 秒）===")
        t = time.time()
        try:
            r = 引擎.图生视频(首帧, 词, 种子=a.种子, 帧数=档, 帧率=a.帧率,
                              宽=a.宽, 高=a.高, 前缀=f"长段_{档}",
                              存到=存)
        except Exception as e:
            print(f"  ✗ 炸了：{type(e).__name__}: {e}")
            行.append({"帧数": 档, "错": f"{type(e).__name__}: {e}"})
            continue
        秒 = time.time() - t
        路 = r.get("路") if isinstance(r, dict) else None
        if not 路 or not os.path.exists(路):
            print(f"  ✗ 没出片：{r}")
            行.append({"帧数": 档, "错": "没出片"})
            continue
        信 = 读片(路)
        实际帧 = round(信["秒"] * 信["帧率"])
        比 = 信["字节"] / 实际帧 if 实际帧 else 0
        print(f"  用时 {秒:.1f} 秒   出片 {信['宽']}×{信['高']}  "
              f"{信['秒']} 秒 / {信['帧率']} fps ≈ {实际帧} 帧   "
              f"{信['字节']/1024/1024:.2f} MB   {比:.0f} B/帧")
        print(f"  片子 {路}")
        行.append({"帧数": 档, "要的": 档, "实际": 实际帧, "秒": 信["秒"],
                   "用时": round(秒, 1), "字节": 信["字节"], "路": 路})

    print("\n" + "=" * 74)
    print("汇总")
    print("=" * 74)
    print(f"  {'要的帧':>7} {'实际帧':>7} {'时长':>8} {'耗时':>9} {'大小':>10} {'每帧耗时':>10}")
    for x in 行:
        if "错" in x:
            print(f"  {x['帧数']:>7}   ✗ {x['错']}")
            continue
        print(f"  {x['要的']:>7} {x['实际']:>7} {x['秒']:>7.2f}s {x['用时']:>8.1f}s "
              f"{x['字节']/1024/1024:>8.2f}MB {x['用时']/max(x['实际'],1):>9.3f}s")

    print("\n读法：每帧耗时应该基本恒定（说明是线性放大，不是指数塌）；")
    print("      实际帧 ≈ 要的帧 才说明 length 真被尊重了。")
    with open(os.path.join(出, "_探长段.json"), "w", encoding="utf-8") as f:
        json.dump(行, f, ensure_ascii=False, indent=2)
    print(f"\n明细写到 {os.path.join(出, '_探长段.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(主())
