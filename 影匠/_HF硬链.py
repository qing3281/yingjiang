# -*- coding: utf-8 -*-
r"""把 `网盘\HF` 里与**已装模型**逐字节相同的那些，换成指向已装那份的硬链接。

为什么不是删：用户的话是「把有用的东西全留下，其他重复的删了」。
HF 和已装模型**在同一个卷 D: 上**，所以硬链同时满足两边 ——
省下的空间和删掉一模一样（那些数据块只剩一份引用），
但 HF 下每个路径都还在、还能打开、还是 66.5 GB 的模型。

比上一版（`_网盘硬链.py`）改掉的一个设计缺陷
------------------------------------------------
上一版是 `os.remove(p)` → `os.link(源, p)`。这中间有**一个真实的时间窗**，
窗口里那个路径是不存在的 —— 网盘子代理在两个时刻亲眼看到 Work-Fisher 和 aki
的两份 25 GB 模型「不在盘上」。进程要是正好死在窗口里，那个**路径**就永久丢了
（数据还在，因为源那份引用着同一个 inode，但整合包会缺文件）。

这一版不删再链，而是：
    os.link(源, 临时名)      # 数据先出现，目标还在
    os.replace(临时名, 目标)  # 原子覆盖，没有「不存在」的时刻
`os.replace` 在 NTFS 上是原子的 —— 要么是旧的，要么是新的，不会两者都不是。

用法：
    python _HF硬链.py           # 空跑
    python _HF硬链.py --真做
"""
import argparse
import hashlib
import os
import sys
import time

HF = r"D:\DSHworkspace\素材\网盘\HF"
已装 = r"D:\Comfy-Desktop\ComfyUI-Shared\models"


def 卷(p):
    return os.path.splitdrive(os.path.abspath(p))[0].upper()


def 哈希(路):
    h = hashlib.sha256()
    n = 0
    with open(路, "rb") as f:
        while True:
            d = f.read(1 << 22)
            if not d:
                break
            h.update(d)
            n += len(d)
    return h.hexdigest(), n


def 扫(基):
    out = {}
    for 夹, _, 们 in os.walk(基):
        for f in 们:
            p = os.path.join(夹, f)
            try:
                out[f] = out.get(f) or []
                out[f].append(p)
            except OSError:
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--HF", default=HF)
    ap.add_argument("--已装", default=已装)
    ap.add_argument("--真做", action="store_true")
    参 = ap.parse_args()

    if 卷(参.HF) != 卷(参.已装):
        print(f"✗ 跨卷（{卷(参.HF)} vs {卷(参.已装)}）—— 硬链接做不到，只能复制或删除")
        return 1

    print(f"HF   ：{参.HF}")
    print(f"已装 ：{参.已装}")
    print(f"同卷 {卷(参.HF)} ✓（硬链可行）\n")

    名2HF = 扫(参.HF)
    名2装 = 扫(参.已装)
    大写 = {k.lower(): v for k, v in 名2装.items()}

    对 = []
    for 名, 们 in sorted(名2HF.items()):
        装们 = 大写.get(名.lower())
        if not 装们:
            print(f"  – 已装里没有同名的，保留原样：{名}")
            continue
        对.append((们, 装们, 名))

    print(f"\n{len(对)} 个同名文件，逐个算 SHA-256 确认是不是真同一份…\n")
    print(f"{'大小GB':>9}  状态  文件")
    print("─" * 100)

    能省 = 0
    做了 = 0
    跳过 = []
    坏了 = []

    for HF们, 装们, 名 in 对:
        源 = 装们[0]
        sz = os.path.getsize(源)
        try:
            h源, n源 = 哈希(源)
        except OSError as e:
            坏了.append(f"读不了已装的 {源}：{e}")
            continue

        全对 = True
        对上 = []
        for p in HF们:
            if os.path.getsize(p) != sz:
                跳过.append(f"{名}：大小不同（HF {os.path.getsize(p)} vs 已装 {sz}）")
                全对 = False
                continue
            h, n = 哈希(p)
            if h != h源 or n != n源:
                跳过.append(f"{p}：内容不同（哈希不一样）—— **保留不动**")
                全对 = False
                continue
            对上.append(p)

        if not 对上:
            continue

        省 = sz * len(对上)
        能省 += 省
        print(f"{sz/1073741824:>9.2f}  {'待链' if not 参.真做 else '链上'}  {名}  ×{len(对上)}")
        for p in 对上:
            print(f"{'':>12}  {os.path.relpath(p, 参.HF)}")

        if not 参.真做:
            做了 += len(对上)
            continue

        for p in 对上:
            try:
                旧 = os.stat(p).st_ino
                # ★ 没有窗口：先链出临时名，再原子覆盖，全程目标路径都存在
                临 = p + f".__链中{os.getpid()}__"
                if os.path.exists(临):
                    os.remove(临)
                os.link(源, 临)
                os.replace(临, p)
                st = os.stat(p)
                if st.st_ino != os.stat(源).st_ino or st.st_nlink < 2:
                    坏了.append(f"{p}：链完 inode 不同源或 nlink<2")
                    continue
                if os.path.getsize(p) != sz:
                    坏了.append(f"{p}：链完大小不对")
                    continue
                h2, n2 = 哈希(p)
                if h2 != h源 or n2 != n源:
                    坏了.append(f"{p}：链完哈希不对")
                    continue
                做了 += 1
                print(f"{'':>12}  ✓ 链上（inode {旧} → {st.st_ino}，nlink {st.st_nlink}）")
            except OSError as e:
                坏了.append(f"链不上 {p}：{e}")

    print("─" * 100)
    if 参.真做:
        print(f"\n链了 {做了} 个，释放 {能省/1073741824:.2f} GB")
    else:
        print(f"\n【空跑】可以链 {做了} 个，能释放 {能省/1073741824:.2f} GB")

    if 跳过:
        print(f"\n保留不动的 {len(跳过)} 条：")
        for x in 跳过:
            print(f"  {x}")
    if 坏了:
        print(f"\n⚠ 出问题的 {len(坏了)} 条：")
        for x in 坏了:
            print(f"  {x}")
        return 1

    报 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      f"_HF硬链_{time.strftime('%m%d_%H%M')}.txt")
    with open(报, "w", encoding="utf-8") as f:
        f.write(f"HF {参.HF}\n已装 {参.已装}\n真做 {参.真做}\n"
                f"链了 {做了} 个，释放 {能省} B（{能省/1073741824:.2f} GB）\n"
                f"保留 {len(跳过)} 条，问题 {len(坏了)} 条\n")
        for x in 跳过 + 坏了:
            f.write(f"  {x}\n")
    print(f"\n报告：{报}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
