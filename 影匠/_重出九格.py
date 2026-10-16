# -*- coding: utf-8 -*-
"""重出九宫格到 1344x768 横构图（与视频画幅对齐）。

用法：
    python _重出九格.py            # 出到作品/试镜
    python _重出九格.py --空跑      # 只读 md、打印每格提示词，不出图

为什么单独写这一步：`剧组.py 出图` 用 02-九宫格.md 里的默认尺寸（1024×1024 方图），
而视频线 `让镜动` 出的是 16:9。方图硬塞进 16:9 会裁掉上下 —— 直接按 1344×768 出，
画质和构图都对齐。
"""
import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 导演          # noqa: E402
import 角色库        # noqa: E402

戏名 = "试镜"
戏目录 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "作品", 戏名)
种子 = 1735946766
宽, 高 = 1344, 768


def 读九格(md路):
    """从 02-九宫格.md 里抠出每格的 (号, 标题, 景别, 提示词, 机位)。"""
    文 = open(md路, encoding="utf-8").read()
    块 = re.split(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$", 文, flags=re.M)

    def 取(体, 键):
        m = re.search(rf"^-\s*{键}\s*[:：]\s*(.*)$", 体, flags=re.M)
        return m.group(1).strip() if m else ""

    格 = []
    for i in range(1, len(块), 3):
        体 = 块[i + 2] if i + 2 < len(块) else ""
        格.append({
            "号": int(块[i]),
            "标题": 块[i + 1],
            "景别": 取(体, "景别"),
            "机位": 取(体, "机位"),
            "提示词": 取(体, "提示词"),
        })
    return 格


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--空跑", action="store_true")
    ap.add_argument("--只格", default="")
    参 = ap.parse_args()

    md路 = os.path.join(戏目录, "02-九宫格.md")
    if not os.path.exists(md路):
        print(f"✗ 找不到 {md路}")
        return 1

    格表 = 读九格(md路)
    print(f"读到 {len(格表)} 格 · 目标 {宽}×{高}")

    只要 = set()
    if 参.只格:
        只要 = {int(x) for x in 参.只格.replace("，", ",").split(",") if x.strip()}

    角 = 角色库.取("凌霜")
    if not 角:
        print("✗ 角色库里没有『凌霜』")
        return 1
    # 必须先立戏 —— 不立戏 _当前戏 是空的，导演.开镜 会把图落进「作品\未命名\」
    # （第一版就踩了：九张图全跑进 未命名，正主目录纹丝不动）
    导演.立戏(戏名, 默认风格="cinematic-real", 默认角色=["凌霜"])
    # 锚点不自己拼 —— 角色卡的字段是 名/性别/年龄/发/眼/肤/服/特征/体态，
    # 自己拼很容易拼出「凌霜，，，」这种空档（第一版就踩了）。
    # 直接调 角色库.外貌串()，它吐的是英文锚点串（导演.开镜 内部用的就是它）。
    锚 = 角色库.外貌串("凌霜")["串"]
    print(f"  锚点：{锚[:80]}…")

    成 = 败 = 0
    for g in 格表:
        if 只要 and g["号"] not in 只要:
            continue
        词 = f"{锚}。{g['提示词']}，冷蓝低饱和，电影写实，硬光长阴影，{g['景别']}"
        if 参.空跑:
            print(f"  格{g['号']} {g['标题']} [{g['景别']}] {g['机位']}")
            print(f"      {词[:110]}…")
            continue
        t = time.time()
        try:
            r = 导演.开镜(词, 风格="cinematic-real", 角色="凌霜", 种子=种子,
                          宽=宽, 高=高, 文件名=f"01_格{g['号']}")
            print(f"  格{g['号']} {g['标题']}  {time.time()-t:.1f} 秒  "
                  f"{os.path.basename(r.get('路', ''))}")
            成 += 1
        except Exception as e:
            print(f"  格{g['号']} ✗ {type(e).__name__}: {e}")
            败 += 1

    if not 参.空跑:
        print(f"\n▶ 出图收工：成功 {成}　失败 {败}")
    return 0 if 败 == 0 else 1


if __name__ == "__main__":
    sys.exit(主())
