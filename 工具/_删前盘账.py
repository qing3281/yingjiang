# -*- coding: utf-8 -*-
"""
_删前盘账.py —— 删之前先算：这一堆东西删了，**磁盘到底能空出多少**。

## 为什么不能直接看「它占多大」

硬链接（hardlink）的多个路径**共用同一份数据**。删掉其中一条路径，磁盘一个字节都不省 ——
只有在它是这份数据的**最后一条路径**时才真省。

实测（2026-10-15）：`D:\\DSHworkspace\\网盘\\HF\\` 报 66.50 GiB，
但那 11 个文件**全是** `D:\\Comfy-Desktop\\ComfyUI-Shared\\models\\` 里同名文件的硬链 ——
删了整个 `HF\\` 目录，磁盘**一个字节都不会多出来**。

所以正确的问题是：**这个 inode 除了我这里，还有没有别的活着的路径？**
没有 → 删了真省；有 → 删了白删。

## 用法

    python _删前盘账.py <候选1> [候选2] ...
    python _删前盘账.py --盘 D:\\DSHworkspace\\网盘
    python _删前盘账.py --盘 D:\\DSHworkspace\\网盘 --盘 D:\\ComfyUI_windows_portable

输出每个候选的：
    逻辑大小      它底下所有文件大小之和（会很吓人，因为含硬链重复）
    真能省        删了磁盘真的会空出来的 bytes
    白删          被别的路径shared、删了不省的部分

★ 判据：**报「省了 N GiB」时必须能指到这个脚本的这一行**，不许拿「文件夹大小」当省钱数。
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

变短 = lambda n: (f"{n/2**40:.2f} TiB" if n >= 2**40 else
                  f"{n/2**30:.2f} GiB" if n >= 2**30 else
                  f"{n/2**20:.1f} MiB" if n >= 2**20 else f"{n/1024:.0f} KiB")


def 归一(p):
    return os.path.normcase(os.path.abspath(p)).rstrip("\\/") + os.sep


def 在谁底下(路, 候选s):
    """这个路径属于哪个候选？都不属于返回 None。"""
    for i, c in enumerate(候选s):
        if 路.startswith(c):
            return i
    return None


def 主():
    候选s = []
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--盘" and i + 1 < len(argv):
            候选s.append(归一(argv[i + 1])); i += 2
        else:
            候选s.append(归一(argv[i])); i += 1
    if not 候选s:
        print(__doc__)
        return 1

    盘 = os.path.splitdrive(候选s[0])[0] + "\\"
    print(f"单遍扫 {盘}，把每个 inode 归到「哪个候选」或「候选之外」…")
    print(f"候选 {len(候选s)} 个：")
    for c in 候选s:
        print(f"    {c}")

    # inode → [大小, set(它出现过的桶)]   桶 = 候选下标 或 -1（候选之外）
    表 = {}
    文件数 = 0
    扫错 = 0
    for dp, dn, fn in os.walk(盘, onerror=lambda e: (globals().__setitem__("扫错", 扫错 + 1))):
        桶 = 在谁底下(os.path.normcase(dp) + os.sep, 候选s)
        for f in fn:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
            except OSError:
                扫错 += 1
                continue
            if st.st_nlink == 0:
                continue
            文件数 += 1
            k = (st.st_dev, st.st_ino)
            e = 表.get(k)
            if e is None:
                表[k] = [st.st_size, {桶 if 桶 is not None else -1}]
            else:
                e[1].add(桶 if 桶 is not None else -1)

    print(f"  扫到 {文件数:,} 个文件，去重后 {len(表):,} 个 inode，读不到的 {扫错} 个")

    逻辑 = [0] * len(候选s)
    真省 = [0] * len(候选s)
    白删 = [0] * len(候选s)
    共享外 = [0] * len(候选s)
    for (dev, ino), (大, 桶s) in 表.items():
        在候选 = [b for b in 桶s if b >= 0]
        if not 在候选:
            continue                      # 数据全在候选之外（候选里只是硬链）
        for b in set(在候选):
            逻辑[b] += 大
        if len(桶s) == 1 and len(在候选) == 1:
            真省[在候选[0]] += 大      # 只出现在这一个候选里 → 删了真省
        elif len(在候选) == 1 and -1 in 桶s:
            白删[在候选[0]] += 大      # 候选里有，候选外也有 → 删了不省
        elif len(在候选) > 1:
            共享外[在候选[0]] += 大    # 同时挂在多个候选下

    print()
    print("=" * 78)
    总真省 = 0
    for b, c in enumerate(候选s):
        总真省 += 真省[b]
        print(f"\n★ {c}")
        print(f"    逻辑大小（含硬链重复）  {变短(逻辑[b])}")
        print(f"    ★ 真能省                {变短(真省[b])}")
        if 白删[b]:
            print(f"    删了不省（别处有孪生）  {变短(白删[b])}")
        if 共享外[b]:
            print(f"    同时挂在别的候选下      {变短(共享外[b])}")
    print()
    print("=" * 78)
    print(f"★ 全删掉，磁盘一共能空出：{变短(总真省)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(主())
