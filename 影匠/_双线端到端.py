# -*- coding: utf-8 -*-
"""双线一致性 —— 端到端真跑一遍 L1 / L2 / L3。

和 `_双线一致性.py` 的区别：那个用 monkeypatch 把 `引擎.派工` 换掉了（图是抓到了，
但视频根本没真出），所以 L2 比对的是"我伪造的图 vs 对端的真图"，必然不等。
这个脚本**只包一层、照常放行**，所以拿到的是"真正发出去的那张图"，L2 才有意义。

跑法：
    python _双线端到端.py [--段 格7] [--宽 832 --高 480] [--帧数 49] [--帧率 16]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 双线
import 引擎

这里 = os.path.dirname(os.path.abspath(__file__))


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--段", default="格7", help="用哪一格的图当首帧")
    ap.add_argument("--宽", type=int, default=832)
    ap.add_argument("--高", type=int, default=480)
    ap.add_argument("--帧数", type=int, default=49)
    ap.add_argument("--帧率", type=int, default=16)
    ap.add_argument("--模板", default="wan22_i2v")
    ap.add_argument("--端点", default="远端")
    ap.add_argument("--种子", type=int, default=0)
    a = ap.parse_args()

    条 = []

    def 记(名, 过):
        条.append((名, 过))
        return 过

    print("=" * 70)
    print("L1 模型一致")
    print("=" * 70)
    r1 = 双线.比模型([a.模板])
    记("L1 模型一致", r1.get("通过") if isinstance(r1, dict) else r1)

    print()
    print("=" * 70)
    print(f"派工到{a.端点}（真跑，不拦）")
    print("=" * 70)
    引擎.换端点(a.端点)
    在 = 引擎.在线()
    if not 在.get("在线"):
        print(f"  ✗ {a.端点} 不在线：{在.get('错')}")
        return 2
    print(f"  端点 {在['端点']}  {在.get('显卡')}  空闲显存 {在.get('显存空闲GB')} GB")

    首帧 = os.path.join(这里, "作品", "试镜", f"01_{a.段}.png")
    if not os.path.exists(首帧):
        print(f"  ✗ 找不到首帧 {首帧}")
        return 2

    词 = ("银发剑客立于雪原，黑发黑衣白饰，侧身回望，剑垂于侧，"
          "风吹发丝微动，电影写实，冷蓝色调，雪花缓落")
    种子 = a.种子 or int(time.time()) % 2_000_000_000

    抓 = {}
    原派工 = 引擎.派工

    def 包(w, *x, **k):
        抓["图"] = json.loads(json.dumps(w, ensure_ascii=False))
        r = 原派工(w, *x, **k)
        抓["提示号"] = r.get("提示号")
        return r

    引擎.派工 = 包
    t = time.time()
    try:
        r = 引擎.图生视频(
            首帧, 词, 种子=种子, 帧数=a.帧数, 帧率=a.帧率, 宽=a.宽, 高=a.高,
            前缀="双线端到端",
        )
    finally:
        引擎.派工 = 原派工
    秒 = time.time() - t

    # 把"我方发出去的那张图"存盘 —— 不过盘就没法在事后复盘 L2 差在哪
    with open(os.path.join(这里, "_双线_我方图.json"), "w", encoding="utf-8") as f:
        json.dump(抓["图"], f, ensure_ascii=False, indent=1)

    路 = r.get("路") if isinstance(r, dict) else None
    if not 路:
        print(f"  ✗ 没拿到出片：{r}")
        return 2
    print(f"  {a.端点}出片 {秒:.1f} 秒")
    print(f"  片子 {路}")
    print(f"  提示号 {抓.get('提示号')}")

    print()
    print("=" * 70)
    print("L2 工作流一致（对端执行的图 == 本机发的图？）")
    print("=" * 70)
    r2 = 双线.验回执(抓.get("提示号"), 抓["图"])
    记("L2 工作流一致", r2.get("通过"))

    print()
    print("=" * 70)
    print("L3 成片一致（画幅/帧数/帧率是不是本机要求的）")
    print("=" * 70)
    r3 = 双线.验片(路, a.宽, a.高, a.帧数, a.帧率)
    记("L3 成片一致", r3.get("通过"))

    print()
    print("=" * 70)
    print("汇总")
    print("=" * 70)
    for 名, 过 in 条:
        标 = "✓ 通过" if 过 is True else ("✗ 没过" if 过 is False else "－ 没验成")
        print(f"  {名:<14} {标}")
    全过 = all(v is True for _, v in 条)
    print()
    if 全过:
        print("★ 三条全过 —— 远端确实只是算力：模型一样、图没被改、出片规格也对。")
    else:
        print("✗ 有没过/没验成的 —— 这条线的「纯算力」资格这次不能算成立。")
    return 0 if 全过 else 2


if __name__ == "__main__":
    sys.exit(主())
