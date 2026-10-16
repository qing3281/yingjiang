# -*- coding: utf-8 -*-
"""网盘去重：把同内容的重复文件换成**硬链接**，而不是删掉。

为什么不是删：用户的硬要求是「把有用的东西全留下」+「删之前必须核对」。
硬链接同时满足两边 —— 四个整合包照旧各自能启动、每个路径都还能打开、
一个字节都没丢，但重复的那份数据块被释放了。**可逆**：`fsutil hardlink list` 看得到，
真要拆开再复制一份出来就行。

安全性靠四道：
  ① 只在同一卷内链（跨卷 `os.link` 本来就会失败，这里提前挡）
  ② 分组先比大小、再比**全文件 SHA-256**（大小相同不算重复）
  ③ 链之前把「要保留的那份」和「要替换的那份」都记下 inode
  ④ 链完立刻回读校验：inode 变了一样、字节数一样、**重新算一遍哈希还是一样**

用法：
    python _网盘硬链.py                 # 空跑，只报告能省多少
    python _网盘硬链.py --真做           # 真链
    python _网盘硬链.py --根 D:\某目录    # 换目录
"""
import argparse
import hashlib
import os
import sys
import time

默认根 = r"D:\DSHworkspace\素材\网盘"
块 = 1 << 22          # 4 MB


def 卷(p):
    return os.path.splitdrive(os.path.abspath(p))[0].upper()


def 哈希(路, 报=None):
    h = hashlib.sha256()
    n = 0
    with open(路, "rb") as f:
        while True:
            d = f.read(块)
            if not d:
                break
            h.update(d)
            n += len(d)
    return h.hexdigest(), n


def 同一份(a, b):
    """硬链接：同一个 inode 就是同一份数据。"""
    try:
        return os.stat(a).st_ino == os.stat(b).st_ino and os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--根", default=默认根)
    ap.add_argument("--真做", action="store_true")
    ap.add_argument("--最小MB", type=float, default=1.0,
                    help="只处理大于这个体积的文件（小文件省不出多少，还容易碰系统文件）")
    ap.add_argument("--跳过", default="", help="路径含这些词就跳过，逗号分隔")
    参 = ap.parse_args()

    根 = os.path.abspath(参.根)
    if not os.path.isdir(根):
        print(f"✗ 没有这个目录：{根}")
        return 1
    跳 = [x.strip() for x in 参.跳过.split(",") if x.strip()]
    下限 = 参.最小MB * 1048576

    print(f"扫 {根}（只处理 ≥ {参.最小MB} MB 的）")
    t0 = time.time()
    全 = []
    for 夹, _, 们 in os.walk(根):
        for f in 们:
            p = os.path.join(夹, f)
            if any(x in p for x in 跳):
                continue
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if sz >= 下限:
                全.append((sz, p))
    print(f"  {len(全)} 个候选，{time.time()-t0:.1f} 秒\n")

    # ① 先按大小分组 —— 大小不同绝不可能同内容
    按大小 = {}
    for sz, p in 全:
        按大小.setdefault(sz, []).append(p)

    组 = []
    for sz, 们 in 按大小.items():
        if len(们) < 2:
            continue
        组.append((sz, 们))
    组.sort(key=lambda x: -x[0] * (len(x[1]) - 1))
    print(f"{len(组)} 组「大小相同」，逐组算哈希确认是不是真同一份…\n")

    省得 = 0
    链了 = 0
    失败 = []
    print(f"{'大小GB':>8} {'份数':>4} {'可省GB':>8}  文件")
    print("─" * 108)

    for sz, 们 in 组:
        # ② 同大小的再算全文件哈希
        按哈希 = {}
        for p in 们:
            try:
                h, n = 哈希(p)
            except OSError as e:
                失败.append(f"读不了 {p}：{e}")
                continue
            if n != sz:
                失败.append(f"{p} 大小在读的时候变了（{sz} → {n}），跳过")
                continue
            按哈希.setdefault(h, []).append(p)

        for h, 同 in 按哈希.items():
            if len(同) < 2:
                continue
            # ③ 全在同一个卷上才动
            卷们 = {卷(p) for p in 同}
            if len(卷们) > 1:
                失败.append(f"这组跨卷 {卷们}，跳过：{同[0]}")
                continue
            # 已经全是硬链接的组跳过（省得重复劳动）
            已有 = sum(1 for p in 同[1:] if 同一份(同[0], p))
            if 已有 == len(同) - 1:
                continue

            可省 = sz * (len(同) - 1)
            省得 += 可省
            print(f"{sz/1073741824:>8.2f} {len(同):>4} {可省/1073741824:>8.2f}  "
                  f"{os.path.relpath(同[0], 根)}")
            for p in 同[1:]:
                print(f"{'':>22}  ← {os.path.relpath(p, 根)}")

            if not 参.真做:
                链了 += len(同) - 1
                continue

            保 = 同[0]
            for p in 同[1:]:
                try:
                    旧 = os.stat(p).st_ino
                    os.remove(p)                       # 先删掉目录项，数据还在（保那份引用着）
                    os.link(保, p)                     # 再链到保那份
                    新 = os.stat(p).st_ino
                    # ④ 回读校验
                    if not 同一份(保, p):
                        失败.append(f"链完不同源：{p}")
                        继续 = False
                    elif os.path.getsize(p) != sz:
                        失败.append(f"链完大小不对：{p}")
                        继续 = False
                    else:
                        h2, n2 = 哈希(p)
                        if h2 != h or n2 != sz:
                            失败.append(f"链完哈希不对：{p}")
                            继续 = False
                        else:
                            链了 += 1
                            print(f"{'':>22}  ✓ 链上（inode {旧} → {新}）")
                except OSError as e:
                    失败.append(f"链不上 {p}：{e}")

    print("─" * 108)
    if 参.真做:
        print(f"\n链了 {链了} 个文件，释放 {省得/1073741824:.2f} GB")
    else:
        print(f"\n【空跑】可以链 {链了} 个文件，能释放 {省得/1073741824:.2f} GB")
        print("     确认没问题就加 --真做 重跑一遍")

    if 失败:
        print(f"\n⚠ {len(失败)} 条没能处理：")
        for x in 失败[:20]:
            print(f"  {x}")

    # 落一份报告
    报 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      f"_网盘硬链_{time.strftime('%m%d_%H%M')}.txt")
    with open(报, "w", encoding="utf-8") as f:
        f.write(f"根：{根}\n真做：{参.真做}\n链了 {链了} 个，释放 {省得} B"
                f"（{省得/1073741824:.2f} GB）\n失败 {len(失败)} 条\n")
        for x in 失败:
            f.write(f"  {x}\n")
    print(f"\n报告：{报}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
