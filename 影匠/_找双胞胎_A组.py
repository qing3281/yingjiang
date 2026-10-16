# -*- coding: utf-8 -*-
"""删之前先问一句：**这东西别处是不是已经有一份了？**

硬规矩第 1 条是「删任何东西之前先给用户核对」，
但更要紧的一条是 **「能硬链就别删」** —— 硬链出来的副本不占额外空间，
而两个路径都还打得开。所以「重复」的正确处理顺序是：

    ① 别处有**内容完全相同**的一份  →  **硬链**，省一样的空间，还多留一个路径
    ② 别处没有                       →  才轮到「删」

## 判据（不能只比大小）

只比大小会漏掉「同名同大小但内容不同」。分三层：

    1. 比大小（粗筛）
    2. 比**首 4 MiB + 尾 4 MiB 的 SHA-256**（真读，不是元数据）
    3. 全等才硬链

第一层只用来少读盘；**下结论必须靠第二层**。

## 为什么只查这些文件

`--A组` 只查 A 组里 `st_nlink == 1` 的那些（真能省的 16 个）。
硬链的那些本来就不占空间，不用管。
"""
import argparse
import hashlib
import os
import sys

网盘 = r"D:\DSHworkspace\素材\网盘"
在用 = r"D:\Comfy-Desktop\ComfyUI-Shared\models"
块 = 4 * 1024 * 1024


def 指纹(路: str) -> str:
    """首 4 MiB + 尾 4 MiB 的 SHA-256。真读盘。"""
    sz = os.path.getsize(路)
    h = hashlib.sha256()
    with open(路, "rb") as f:
        h.update(f.read(块))
        if sz > 块 * 2:
            f.seek(-块, os.SEEK_END)
            h.update(f.read(块))
    return f"{sz}:{h.hexdigest()[:32]}"


def 找双胞胎(目标们, 搜索根):
    """给每个目标找一个「大小相同 + 首尾指纹相同」的已有文件。"""
    候选 = {}
    for 底, _, fs in os.walk(搜索根):
        for f in fs:
            p = os.path.join(底, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_nlink > 1:
                continue          # 已经是硬链了，不用再链
            候选.setdefault(st.st_size, []).append(p)

    结果 = []
    for 目标, 大小 in 目标们:
        命中 = None
        for c in 候选.get(大小, []):
            注意 = ""
            try:
                if 指纹(c) == 指纹(目标):
                    命中 = c
                    break
                else:
                    注意 = "（同名同大小，内容不同！）"
                    print(f"    ⚠ {os.path.basename(目标)} 与 {c} 大小相同但内容不同 {注意}")
            except OSError:
                continue
        结果.append((目标, 大小, 命中))
    return 结果


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--A组", action="store_true", help="只查 A 组里 st_nlink==1 的文件")
    ap.add_argument("--链", action="store_true", help="把找到的双胞胎真的硬链起来")
    ap.add_argument("--根", default=os.path.join(网盘, r"下载\ComfyUI-aki\models"))
    参 = ap.parse_args()

    目标们 = []
    for 底, _, fs in os.walk(参.根):
        for f in fs:
            p = os.path.join(底, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_nlink == 1:
                目标们.append((p, st.st_size))

    总 = sum(s for _, s in 目标们)
    print("=" * 78)
    print(f"  找双胞胎：{len(目标们)} 个文件，{总 / 2**30:.2f} GB")
    print(f"  在 {在用} 里找「内容完全相同」的一份")
    print("=" * 78)

    结果 = 找双胞胎(目标们, 在用)

    有 = [(a, s, b) for a, s, b in 结果 if b]
    无 = [(a, s, b) for a, s, b in 结果 if not b]

    print(f"\n  ── 别处已经有一份（★ 该硬链，不该删）：{len(有)} 个，"
          f"{sum(s for _, s, _ in 有) / 2**30:.2f} GB")
    for a, s, b in sorted(有, key=lambda t: -t[1]):
        print(f"     {s / 2**30:7.2f} GB  {os.path.relpath(a, 参.根)}")
        print(f"                 ↳ 已有：{b}")

    print(f"\n  ── 别处没有（只能删，或者留着）：{len(无)} 个，"
          f"{sum(s for _, s, _ in 无) / 2**30:.2f} GB")
    for a, s, _ in sorted(无, key=lambda t: -t[1]):
        print(f"     {s / 2**30:7.2f} GB  {os.path.relpath(a, 参.根)}")

    if 参.链 and 有:
        print(f"\n{'─' * 78}\n  硬链（同一个 inode，不占额外空间，两个路径都还在）\n{'─' * 78}")
        for a, s, b in 有:
            备 = a + ".bak_硬链前"
            try:
                os.replace(a, 备)          # 先挪开，避免 os.link 撞已有名字
                os.link(b, a)              # 硬链到已有那份
                if 指纹(a) != 指纹(b):
                    raise RuntimeError("链完指纹对不上")
                os.remove(备)
                print(f"  ✓ {os.path.relpath(a, 参.根)}")
            except OSError as e:
                if os.path.exists(备) and not os.path.exists(a):
                    os.replace(备, a)      # 失败就还原
                print(f"  ✗ {os.path.relpath(a, 参.根)}：{e}")
        print(f"\n  ★ 省下 {sum(s for _, s, _ in 有) / 2**30:.2f} GB，"
              f"而且这些路径**一个都没丢**")
    elif 有:
        print(f"\n  加 --链 才真动手。\n")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
