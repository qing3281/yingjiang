# -*- coding: utf-8 -*-
"""试「真正的中间帧」—— 回答用户 m01758 的设计：
   两格之间插一张**处于两张中间状态**的图，用它把硬切变成渐变。

判据（只有这一条，且是数出来的）：
   设 d1 = MAE(生成的图, 格N首帧)、d2 = MAE(生成的图, 格N+1首帧)、D = MAE(格N首, 格N+1首)
   **真中间 = d1 与 d2 差不多（比值 0.6~1.7）且两者都明显小于 D。**
   如果生成的图几乎等于第一张（d1≈0、d2≈D），那就说明 Qwen-Image-Edit 把构图锁死了，
   这个设计走不通 —— `影匠\\_出长片.py:15` 记着这个模型的毛病就是「参考隐变量把构图一起锁死」。

花什么：qwen_edit 每次一张图，两张候选 ≈ 1 分钟本机 GPU。不落成品目录。
"""
import os
import sys
import time

import cv2
import numpy as np

根 = r"D:\DSHworkspace\影匠"
目 = os.path.join(根, "作品", "楚子航")
出 = r"D:\DSHworkspace\_试中间帧"
sys.path.insert(0, 根)
sys.stdout.reconfigure(encoding="utf-8")

import 引擎  # noqa: E402


def 读(p):
    a = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    if a is None:
        raise RuntimeError("读不出 " + p)
    return a


def 差(a, b):
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


提示词 = (
    "这是同一个场景的两个不同机位。请画一张正好处于这两张之间的画面："
    "机位移动到两者中间的位置，画面里同时保留第一张的月台纵深和第二张的人物近景，"
    "人物、服装、光线、环境与两张图完全一致。电影写实，冷蓝低饱和。"
)


def 跑(底, 参考, 名):
    存 = os.path.join(出, 名)
    t = time.time()
    try:
        引擎.文生图(提示词, 种子=1735946766, 宽=1344, 高=768, 步数=20,
                   模板="qwen_edit", 参考图=[底, 参考], 前缀=名[:-4], 存到=存)
    except Exception as e:
        print("  ✗ %s  %s: %s" % (名, type(e).__name__, str(e)[:200]))
        return None
    if not os.path.exists(存):
        print("  ✗ %s  没落盘" % 名)
        return None
    print("  ✓ %s  %.0f KB  %.1f 秒" % (名, os.path.getsize(存) / 1024, time.time() - t))
    return 存


def main():
    os.makedirs(出, exist_ok=True)
    甲 = os.path.join(目, "01_格1.png")
    乙 = os.path.join(目, "01_格2.png")
    if not (os.path.isfile(甲) and os.path.isfile(乙)):
        print("✗ 缺关键帧")
        return 1

    A, B = 读(甲), 读(乙)
    D = 差(A, B)
    print("两张关键帧：01_格1.png  vs  01_格2.png   MAE = %.2f" % D)
    print()

    cand = []
    for 底, 参考, 名 in ((甲, 乙, "中间_以格1为底.png"), (乙, 甲, "中间_以格2为底.png")):
        p = 跑(底, 参考, 名)
        if p:
            cand.append((名, p))

    print()
    print("=== 判读：真中间 = d1≈d2 且都 << D ===")
    过 = 0
    for 名, p in cand:
        C = 读(p)
        d1, d2 = 差(C, A), 差(C, B)
        比 = (d1 / d2) if d2 > 1e-6 else 999
        真中间 = 0.6 <= 比 <= 1.7 and max(d1, d2) < D * 0.95
        print("  %-22s d1(离格1)=%6.2f  d2(离格2)=%6.2f  比=%.2f  %s"
              % (名, d1, d2, 比, "✓ 真中间" if 真中间 else "✗ 不是中间（被锁构图）"))
        if 真中间:
            过 += 1

    # 拼一张总览给人眼看（cv2.imencode，中文路径不能直接 imwrite）
    行 = [读(甲), 读(乙)] + [读(p) for _, p in cand]
    h = min(x.shape[0] for x in 行)
    行 = [cv2.resize(x, (int(x.shape[1] * h / x.shape[0]), h)) for x in 行]
    os.makedirs(出, exist_ok=True)
    总 = np.hstack(行[:3]) if len(行) >= 3 else np.hstack(行)
    ok, buf = cv2.imencode(".png", 总)
    if ok:
        with open(os.path.join(出, "_中间帧对照.png"), "wb") as f:
            f.write(buf.tobytes())
        print("\n  对照图：%s" % os.path.join(出, "_中间帧对照.png"))

    print("\n▶ 结论：%d 张里 %d 张够格当「真中间」" % (len(cand), 过))
    return 0 if 过 else 1


if __name__ == "__main__":
    sys.exit(main())
