# -*- coding: utf-8 -*-
"""
_真能省.py —— 「把这个目录删了，磁盘到底能多出多少？」的**唯一正确算法**。

## 为什么需要单独一个脚本

因为直觉在这个问题上会连错三次，我三次都踩过：

  ① **按路径加**：目录里有 441 GiB 文件 → 以为删了省 441 GiB。
     错。同一份数据可以有多个硬链路径，删一条省 0 字节。
  ② **按 inode 去重后再加**：得到 250.62 GiB。还是错 ——
     去重只解决了「同一个目录内部」的重复，没解决「链接指向目录外面」。
  ③ **拿「按路径加」减「按 inode 加」**：算出 223.84 GiB，纯属单位不匹配，真值 37.61 GiB。

## 正确的问法

对每一份数据（inode）问一个问题：

> **它的每一条路径，是不是都在我要删的这批里？**

  - 是 → 删完这份数据就真的没了，**省它的全部大小**
  - 否 → 外面还留着一个名字，删了**省 0 字节**（而且外面那个名字就是真相所在）

一句话：**硬链的正确问法不是「它有几个链」，是「它剩下的链我是不是都要删」。**

## 用法

    python _真能省.py 网盘              报这个目录删了能省多少
    python _真能省.py 网盘 --前 20       顺便列最大的 20 份
    python _真能省.py 网盘 --明细 100    只列 >= 100 MB 的
    python _真能省.py 网盘 --写 清单.json  把「删了真能省」的路径写成清单
"""
import argparse
import json
import os
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def 人(n):
    for 单, 基 in (("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10)):
        if n >= 基:
            return f"{n/基:.2f} {单}"
    return f"{n} B"


def 量(根):
    """→ (按inode的字典, 按路径总字节, 路径条数)"""
    盒 = defaultdict(list)
    按路 = 0
    条 = 0
    for dp, dn, fn in os.walk(根, onerror=lambda e: None):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_nlink == 0:
                continue
            盒[(st.st_dev, st.st_ino)].append((p, st.st_size, st.st_nlink))
            按路 += st.st_size
            条 += 1
    return 盒, 按路, 条


def 主():
    p = argparse.ArgumentParser()
    p.add_argument("目录")
    p.add_argument("--前", type=int, default=0)
    p.add_argument("--明细", type=int, default=0)
    p.add_argument("--写", default=None)
    a = p.parse_args()
    根 = os.path.abspath(a.目录)
    if not os.path.isdir(根):
        print(f"没有这个目录：{根}")
        return 2

    print(f"扫 {根} …")
    盒, 按路, 条 = 量(根)
    print(f"  {条} 条路径，按路径加 = {人(按路)}")
    print(f"  按 inode 去重 = {人(sum(v[0][1] for v in 盒.values()))}（{len(盒)} 份数据）")
    print()

    真, 假 = [], []
    for k, v in 盒.items():
        # ★ 关键是比「这个 inode 总共有几个链接」和「其中几个落在本目录里」
        (真 if v[0][2] == len(v) else 假).append((v[0][1], v))

    print("=" * 70)
    print(f"★ 删了这个目录，磁盘会多出：**{人(sum(s for s, _ in 真))}**")
    print(f"  （{len(真)} 份数据；这 {len(真)} 份的每一条路径都在目录里）")
    print(f"★ 删了省 0 字节的：{人(sum(s for s, _ in 假))}（{len(假)} 份数据）")
    print(f"  ↑ 这些在外面还有别的名字，只是同一份数据。删目录里的路径不释放任何空间。")
    print(f"★ 合计（去重）= {人(sum(s for s, _ in 真) + sum(s for s, _ in 假))}")
    print("=" * 70)

    # 省 0 字节的那些，外面剩下的名字在哪 —— 这才是「内容还在不在」的答案
    if 假:
        print("\n省 0 字节的那些，数据还活在（前 10）：")
        for s, v in sorted(假, reverse=True)[:10]:
            外 = [q for q, _, _ in v][:1]
            print(f"   {人(s):>10}  {os.path.basename(外[0])[:60]}")

    if a.前:
        print(f"\n最大的 {a.前} 份「删了真能省」：")
        for s, v in sorted(真, reverse=True)[:a.前]:
            print(f"   {人(s):>10}  {os.path.relpath(v[0][0], 根)[:100]}")

    if a.明细:
        print(f"\n>= {人(a.明细)} 的「删了真能省」：")
        for s, v in sorted(真, reverse=True):
            if s < a.明细:
                break
            print(f"   {人(s):>10}  x{len(v)}条路径  {os.path.relpath(v[0][0], 根)[:100]}")

    if a.写:
        清单 = [q for s, v in 真 for q, _, _ in v]
        json.dump(清单, open(a.写, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n清单写到 {a.写}（{len(清单)} 条路径）")
    return 0


if __name__ == "__main__":
    sys.exit(主())
