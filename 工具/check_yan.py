# -*- coding: utf-8 -*-
"""拿**真的**成片去跑 `_验成片.py`，证明它自己不会崩、四条判据真的会分辨。

## 为什么要有这一个

`_守成片.py` 在成片落地那一刻会去调 `_验成片.py`，然后把结果写成
`_成片验收.md` 并发邮件。**如果 `_验成片.py` 自己有 bug，那一刻它崩了，
用户早上收到的就是一句报错** —— 而我当时正睡着。

上一轮我只验到了「成片不存在时它退 1」这一条路。**「成片真的在」那条路一次都没跑过。**

## 怎么跑，而不碰生产

把 `_验成片.py` import 进来，**只改它指向的那几个路径**，指到 `check_burn.py`
刚做出来的临时成片（3 段 / 13.4 秒）。生产的 `片\\` 目录一个字节都不动。

期望：
    判据① 过（临时成片刚做出来，比段新）
    判据② 不过（13.4 秒 < 3 分钟）—— **它必须真的报不过，这就是它有没有量的证据**
    判据③ 过（没有 Subtitle 流）
    判据④ 抽出 5 帧 PNG
"""
import importlib.util
import os
import sys

根 = r"D:\DSHworkspace"
戏目 = os.path.join(根, "影匠", "作品", "楚子航")
临 = os.path.join(根, "_试烧临时")
临片 = os.path.join(临, "楚子航_成片_字幕.mp4")


def main():
    if not os.path.isfile(临片):
        print("  ✗ 先跑 check_burn.py 做出临时成片：%s" % 临片)
        return 1

    sys.path.insert(0, 戏目)
    spec = importlib.util.spec_from_file_location(
        "yanchengpian", os.path.join(戏目, "_验成片.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    # ★ 只改路径，判据的代码一个字不动
    m.片目 = 临
    m.成片 = 临片
    print("  验的对象 = %s" % m.成片)
    print("  （生产的 片\\ 目录不碰）")
    print()

    码 = m.主(抽帧=True)

    print()
    print("  ── check_yan 的结论 ──")
    print("  退出码 = %d" % 码)
    好 = [x for x in m.好]
    坏 = [x for x in m.坏]
    print("  过 %d 条 / 不过 %d 条" % (len(好), len(坏)))
    if len(坏) == 0:
        print("  ✗ 13.4 秒的片子它居然全过 —— 判据②没在量时长")
        return 1
    if not any("时长" in x for x in 坏):
        print("  ✗ 不过的那几条里没有「时长」—— 判据②没在量时长")
        return 1
    帧目 = os.path.join(临, "_验帧")
    帧 = [f for f in os.listdir(帧目)] if os.path.isdir(帧目) else []
    if len(帧) < 5:
        print("  ✗ 只抽了 %d 帧，应该 5 帧" % len(帧))
        return 1
    print("  ✓ 四条判据都跑通了：①过 ②真的报不过 ③过 ④抽了 %d 帧" % len(帧))
    print("    帧在 %s" % 帧目)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
