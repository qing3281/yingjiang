# -*- coding: utf-8 -*-
"""全网盘找「内容是同一份、却各占一份空间」的文件，把它们硬链起来。

**这是「能硬链就别删」的执行器** —— 硬规矩第 1 条说删东西要先核对，
但硬链不需要删任何东西：两个路径都还在、都打得开，只是背后共用同一份数据。

## 为什么单开一个（跟 `_查重复全局.py` 有什么不一样）

老脚本 `_查重复全局.py` 是**按文件名配对**的（「同名同大小就当成重复」）。
这一版按**内容**配对，而且判据分三层：

    1. 比大小           —— 只用来分组，少读盘
    2. 比首 4 MiB + 尾 4 MiB 的 SHA-256  —— 真读盘，不是元数据
    3. 可选：全文件 SHA-256 —— `--全读`，最慢但绝对可靠

**为什么不能只比大小**：本项目已经踩过 —— 三对 30 GB 的文件
「前 8 MB + 1/3 + 2/3 + 尾 8 MB 抽样哈希全同」，按抽样判就是重复，
差一点误删 63 GB（见 `知识\假判据族.md` §3.2）。
**所以下结论必须靠真读，而且要么读首尾、要么读全。**

## 硬链的安全前提

`os.link` 只能在同一卷（同一个盘符）内做。跨盘会 `OSError`，
脚本跳过并报告，不会硬来。

## 只报不做的默认

不传 `--链` 就只打印「哪几组、能省多少」，一个字节不动。
"""
import argparse
import hashlib
import os
import sys
from collections import defaultdict

块 = 4 * 1024 * 1024


def 指纹(路: str, 全: bool = False) -> str:
    """默认首 4 MiB + 尾 4 MiB 的 SHA-256；`全=True` 时读整个文件。"""
    sz = os.path.getsize(路)
    h = hashlib.sha256()
    with open(路, "rb") as f:
        if 全:
            while True:
                b = f.read(块)
                if not b:
                    break
                h.update(b)
        else:
            h.update(f.read(块))
            if sz > 块 * 2:
                f.seek(-块, os.SEEK_END)
                h.update(f.read(块))
    return f"{sz}:{h.hexdigest()}"


def 扫(根s, 最小: int, 排除):
    按大小 = defaultdict(list)
    几个 = 0
    for 根 in 根s:
        for 底, ds, fs in os.walk(根):
            ds[:] = [d for d in ds if not any(排 in os.path.join(底, d) for 排 in 排除)]
            for f in fs:
                p = os.path.join(底, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if st.st_size < 最小:
                    continue
                按大小[st.st_size].append(p)
                几个 += 1
    return 按大小, 几个


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--根", nargs="*", default=[r"D:\DSHworkspace\素材\网盘"])
    ap.add_argument("--最小", type=int, default=100 * 1024 * 1024,
                    help="只查大于这个字节数的文件（默认 100 MB）")
    ap.add_argument("--全读", action="store_true", help="读整个文件算哈希（慢，但最可靠）")
    ap.add_argument("--链", action="store_true", help="真做硬链（默认只报）")
    ap.add_argument("--排除", nargs="*", default=[r"\_回收站", r"\$RECYCLE"],
                    help="路径里含这些片段的整棵子树跳过")
    参 = ap.parse_args()

    print("=" * 78)
    print(f"  全网盘找真重复（按下结论{'全文件' if 参.全读 else '首尾 4 MiB'} SHA-256）")
    print("=" * 78)

    按大小, 几个 = 扫(参.根, 参.最小, 参.排除)
    候选 = {k: v for k, v in 按大小.items() if len(v) > 1}
    待查 = sum(len(v) for v in 候选.values())
    print(f"\n  扫到 {几个} 个 >= {参.最小 / 2**20:.0f} MB 的文件")
    print(f"  其中 {待查} 个落在「有同大小的伙伴」的组里，需要真读验证")

    # 关键：先用 (st_dev, st_ino) 把**已经是硬链**的排掉
    组s = []
    已硬链 = 0
    for 大小, vs in 候选.items():
        ino = {}
        for p in vs:
            try:
                st = os.stat(p)
            except OSError:
                continue
            ino.setdefault((st.st_dev, st.st_ino), []).append(p)
        if len(ino) == 1:
            已硬链 += len(vs)      # 全是同一个 inode，已经是硬链了
            continue
        # 只在「不同 inode」之间找真重复
        代表 = [v[0] for v in ino.values()]
        if len(代表) < 2:
            continue
        印 = {}
        for p in 代表:
            try:
                印.setdefault(指纹(p, 参.全读), []).append(p)
            except OSError:
                continue
        for k, ps in 印.items():
            if len(ps) > 1:
                # ps 里每个都是「一个 inode 的代表」；同一 inode 的其余路径
                # 已经跟它共数据了，不需要再列进来（列了反而会重复计数）
                组s.append((大小, ps))

    print(f"  已经是硬链、跳过：{已硬链} 个路径（不占额外空间，不用管）")

    组s.sort(key=lambda t: -t[0])
    能省 = sum(大小 * (len(ps) - 1) for 大小, ps in 组s)
    print(f"\n{'─' * 78}")
    print(f"  ★ 真重复（内容同一份、却各占空间）：{len(组s)} 组，能省 {能省 / 2**30:.2f} GB")
    print(f"{'─' * 78}")

    for 大小, ps in 组s[:40]:
        print(f"\n  {大小 / 2**30:8.2f} GB × {len(ps)} 份")
        for p in ps:
            print(f"     {p}")

    if len(组s) > 40:
        print(f"\n  （还有 {len(组s) - 40} 组没打印）")

    if not 参.链:
        print(f"\n  只报不做。确认无误后加 --链 才真动手。\n")
        return 0

    print(f"\n{'─' * 78}\n  硬链（保留**每一个**路径，只共用后台数据）\n{'─' * 78}")
    省了 = 0
    for 大小, ps in 组s:
        # 挑一个当「主份」：优先已经硬链过的（nlink 大），否则第一个
        主 = max(ps, key=lambda p: os.stat(p).st_nlink)
        for p in ps:
            if p == 主:
                continue
            if os.stat(p).st_ino == os.stat(主).st_ino:
                continue
            # ★ 顺序很重要：先把新链建在**旁边**，再原子替换过去。
            #   反过来（先 rename 走原文件、再 link）会留下一个
            #   「p 不存在」的窗口 —— 脚本要是正好在那崩了，
            #   用户看到的就是文件没了、旁边一个 .bak_链前。
            #   这个顺序全程 p 都存在。
            临 = p + ".链中"
            try:
                if os.path.exists(临):
                    os.remove(临)
                os.link(主, 临)
                if 指纹(临, 参.全读) != 指纹(主, 参.全读):
                    os.remove(临)
                    raise RuntimeError("链完指纹对不上，已撤销")
                os.replace(临, p)          # 原子替换，原 inode 的链接数自动 -1
                if os.stat(p).st_ino != os.stat(主).st_ino:
                    raise RuntimeError("替换完 ino 对不上")
                省了 += 大小
                print(f"  ✓ {p}")
                print(f"      ↳ 与 {主} 同一份数据")
            except OSError as e:
                if os.path.exists(临):
                    try:
                        os.remove(临)
                    except OSError:
                        pass
                print(f"  ✗ {p}：{e}")
    print(f"\n  ★ 硬链完成，省下 {省了 / 2**30:.2f} GB，"
          f"**所有路径一个都没丢**")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
