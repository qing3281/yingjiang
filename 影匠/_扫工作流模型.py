# -*- coding: utf-8 -*-
"""扫一批 ComfyUI 工作流，看它们到底要哪些模型文件。

为什么必须看这个才能决定删不删：
  整合包里那几个「本机没装」的大模型（31.7 / 25.3 / 19.5 GiB），
  留着有用的唯一理由是「本机没有等价替代」。而等价不等价，
  得看**工作流自己引的是哪个文件名** —— 不是看名字像不像。
"""
import collections
import glob
import json
import os
import sys

目录 = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\DSHworkspace\影匠\_网盘整理\取出\01_工作流\6.MINIMAX打戏V2版+配套整合包（全量1391文件）"

模型后缀 = (".safetensors", ".pt", ".pth", ".gguf", ".bin", ".ckpt", ".onnx")
引用 = collections.Counter()
谁引 = collections.defaultdict(set)
坏 = 0


def 收(名, 节点类型):
    if isinstance(名, str) and 名.lower().endswith(模型后缀):
        引用[名] += 1
        谁引[名].add(节点类型)


def 走(obj, 节点类型="?"):
    if isinstance(obj, dict):
        if "class_type" in obj:
            节点类型 = obj["class_type"]
        for k, v in obj.items():
            if k == "class_type":
                continue
            走(v, 节点类型)
    elif isinstance(obj, list):
        for x in obj:
            走(x, 节点类型)
    elif isinstance(obj, str):
        收(obj, 节点类型)


文件 = sorted(glob.glob(os.path.join(目录, "*.json")))
print(f"扫 {len(文件)} 个工作流 …\n")
for p in 文件:
    try:
        w = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        坏 += 1
        print(f"  ✗ 读不了 {os.path.basename(p)}：{e}")
        continue
    走(w)

print(f"（{坏} 个读不了）\n")
print("=== 工作流引用的模型文件 ===")
for m, c in 引用.most_common(60):
    print(f"  {c:4d}×  {m}")
    print(f"        被这些节点引：{', '.join(sorted(谁引[m]))}")
