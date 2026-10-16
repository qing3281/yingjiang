# -*- coding: utf-8 -*-
"""工作流要的模型 vs 本机有什么 vs 只在网盘有 —— 决定删不删的唯一依据。

判据：一个模型文件「留着有用」当且仅当
  (a) 至少一个工作流引用它，且
  (b) 本机没有同名文件（别处的等价量化不算数 —— 名字不同就是不同文件）
"""
import collections
import glob
import json
import os

工作流根 = r"D:\DSHworkspace\影匠\_网盘整理\取出\01_工作流"
网盘 = r"D:\DSHworkspace\素材\网盘"
本机模型根 = [
    r"D:\Comfy-Desktop\ComfyUI-Shared\models",
    r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models",
]
模型后缀 = (".safetensors", ".pt", ".pth", ".gguf", ".bin", ".ckpt", ".onnx")

# ---- 1) 工作流引用了哪些模型
引用 = collections.Counter()


def 走(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k != "class_type":
                走(v)
    elif isinstance(o, list):
        for x in o:
            走(x)
    elif isinstance(o, str):
        if o.lower().endswith(模型后缀) and not o.startswith("http"):
            引用[o.replace("\\", "/").split("/")[-1]] += 1


n = 0
for p in glob.glob(os.path.join(工作流根, "**", "*.json"), recursive=True):
    try:
        走(json.load(open(p, encoding="utf-8")))
        n += 1
    except Exception:
        pass
print(f"扫了 {n} 个工作流，引用 {len(引用)} 个不同的模型文件名\n")

# ---- 2) 本机已装（按文件名）
本机 = {}
for r in 本机模型根:
    if not os.path.isdir(r):
        continue
    for dp, dn, fn in os.walk(r):
        for f in fn:
            本机.setdefault(f, []).append(os.path.join(dp, f))
print(f"本机模型文件：{len(本机)} 种\n")

# ---- 3) 网盘里有哪些（文件名 -> 总大小、路径数）
盘 = {}
for dp, dn, fn in os.walk(网盘):
    for f in fn:
        if f.lower().endswith(模型后缀):
            try:
                s = os.stat(os.path.join(dp, f)).st_size
            except OSError:
                continue
            e = 盘.setdefault(f, [0, 0])
            e[0] += 1
            e[1] = max(e[1], s)
print(f"网盘里的模型文件：{len(盘)} 种\n")

# ---- 4) 结论
要但本机没有 = {m: c for m, c in 引用.items() if m not in 本机}
print("=" * 92)
print(f"★ 工作流要、但本机没有的模型：{len(要但本机没有)} 个")
可删 = 0
留 = 0
for m, c in sorted(要但本机没有.items(), key=lambda kv: -盘.get(kv[0], [0, 0])[1]):
    大小 = 盘.get(m, [0, 0])[1]
    份数 = 盘.get(m, [0, 0])[0]
    if m in 盘:
        print(f"  {大小 / 2**30:8.2f} GiB  ×{份数}份  被引{c}次  {m}")
        if 大小 >= 1 << 30:
            留 += 大小
    else:
        print(f"  {'（网盘也没有）':>12}  被引{c}次  {m}")
print(f"\n  其中网盘里有且 >1 GiB 的合计：{留 / 2**30:.2f} GiB —— 这些删了就真没了")

print("\n" + "=" * 92)
print("★ 只在网盘、且没有任何工作流引用的模型（= 没人用的）")
没引 = []
for m, (份, sz) in 盘.items():
    if m not in 引用 and m not in 本机 and sz >= 1 << 30:
        没引.append((sz, 份, m))
for sz, 份, m in sorted(没引, reverse=True):
    print(f"  {sz / 2**30:8.2f} GiB  ×{份}份  {m}")
print(f"\n  合计 {sum(x[0] for x in 没引) / 2**30:.2f} GiB（去重前）")

print("\n" + "=" * 92)
print("★ 工作流要、本机也有的（这些是安全可删的重复）")
都有 = [(盘.get(m, [0, 0])[1], m) for m in 引用 if m in 本机 and m in 盘]
for sz, m in sorted(都有, reverse=True)[:25]:
    print(f"  {sz / 2**30:8.2f} GiB  {m}")
print(f"\n  合计 {sum(x[0] for x in 都有) / 2**30:.2f} GiB")
