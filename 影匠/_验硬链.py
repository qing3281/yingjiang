# -*- coding: utf-8 -*-
"""验证硬链后的网盘：每个路径都能读、同一组内容真一致。

硬链是零损失的去重（同卷内 os.link 出来的副本不占额外空间），但有个必须验的
风险：**如果哪一步把副本写坏了，硬链会让「坏」同时出现在所有路径上** ——
而且不会有任何报错。所以判据必须是「真读字节」，不能只看 link count。
"""
import hashlib
import os
import random
import sys

根 = sys.argv[1] if len(sys.argv) > 1 else r"D:\DSHworkspace\素材\网盘"
块 = 1048576


def 指纹(p, sz):
    with open(p, "rb") as f:
        h = f.read(块)
        if sz > 2 * 块:
            f.seek(-块, 2)
            h += f.read(块)
    return hashlib.sha256(h).hexdigest()[:16]


print(f"扫描 {根} …")
多链 = []
读错 = []
for dp, dn, fn in os.walk(根):
    for f in fn:
        p = os.path.join(dp, f)
        try:
            if os.stat(p).st_nlink > 1:
                多链.append(p)
        except OSError as e:
            读错.append((p, str(e)))

print(f"  硬链文件：{len(多链)} 个")
if 读错:
    print(f"  ✗ stat 读不出：{len(读错)} 个")
    for p, e in 读错[:5]:
        print(f"      {p}  {e}")

组 = {}
for p in 多链:
    try:
        s = os.stat(p)
        组.setdefault((s.st_dev, s.st_ino), []).append((p, s.st_size))
    except OSError:
        pass

多成员 = {k: v for k, v in 组.items() if len(v) > 1}
单成员 = len(组) - len(多成员)
省 = sum(v[0][1] * (len(v) - 1) for v in 多成员.values())
print(f"  硬链组：{len(组)}　（成员>1 的 {len(多成员)}，孤链 {单成员}）")
print(f"  这些组省下的空间：{省 / 2**30:.2f} GiB")

print("\n抽样验内容（每组抽一个，每个成员都真读首尾各 1 MB 比指纹）…")
random.seed(7)
样本 = random.sample(list(多成员.values()), min(40, len(多成员)))
好 = 坏 = 0
for v in 样本:
    try:
        标 = {指纹(p, sz) for p, sz in v}
        if len(标) == 1:
            好 += 1
        else:
            坏 += 1
            print(f"  ✗ 内容不一致：{v[0][0]}（{len(v)} 个成员）")
    except OSError as e:
        坏 += 1
        print(f"  ✗ 读不出：{v[0][0]}  {e}")

print(f"\n  抽样 {len(样本)} 组：一致 {好}　不一致/读不出 {坏}")

# 每个包的入口文件在不在（硬链最容易出事的地方是「父目录被换掉」）
print("\n检查四个整合包能不能各自启动（入口文件在不在）：")
包 = [
    r"3.九月整合包（minimax+qwen2.1+自由姿势)",
    r"【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）",
    r"1.MINIMAX打斗专篇",
    r"ComfyUI-aki",
]
下载 = os.path.join(根, "下载")
for b in 包:
    d = os.path.join(下载, b)
    if not os.path.isdir(d):
        print(f"  – {b}：目录不在")
        continue
    n = sum(len(fn) for _, _, fn in os.walk(d))
    # 找一下这个包里有没有 python / main.py 之类的启动件
    有主 = any(
        os.path.isfile(os.path.join(dp, x))
        for dp, dn, fn in os.walk(d)
        for x in fn
        if x in ("main.py", "run_nvidia_gpu.bat", "run_cpu.bat", "A启动器.exe", "ComfyUI.exe")
    )
    大小 = sum(os.path.getsize(os.path.join(dp, f)) for dp, dn, fn in os.walk(d) for f in fn)
    print(f"  {'✓' if n else '✗'} {b}：{n} 文件 / {大小 / 2**30:.2f} GiB　启动件{'在' if 有主 else '（没找到标准的，可能靠 .7z 或别的名字）'}")
