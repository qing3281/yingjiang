# -*- coding: utf-8 -*-
"""量「中间帧的提示词到底和首帧差在哪」—— 回答用户 m01714「你的中间帧的图片怎么生成的」。

判据只有两个，都是数出来的：
  1) 同一格 3 张中间帧的提示词，公共前缀占全长的百分之几
     （公共前缀越长 = 它们越是同一句话、只是尾巴不同）
  2) 那几条不同的尾巴长什么样，逐格打出来看

不猜、不引原文，全部从 _中间帧数据.py 里读。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"D:\DSHworkspace\影匠\作品\楚子航")

import _中间帧数据 as 数据  # noqa: E402

分格 = {}
for d in 数据.中间帧:
    分格.setdefault(d["格"], {})[d["序"]] = d["词"]

print("中间帧总条数：%d　格数：%d" % (len(数据.中间帧), len(分格)))
print("一格秒（这份数据自己的口径）= %.4f 秒" % 数据.一格秒)
print()

前缀率 = []
for 号 in sorted(分格):
    词们 = [分格[号][k] for k in sorted(分格[号])]
    a, b = 词们[0], 词们[1]
    长 = 0
    while 长 < min(len(a), len(b)) and a[长] == b[长]:
        长 += 1
    前缀率.append(长 / max(1, min(len(a), len(b))))

前缀率.sort()
print("=== 1) 同一格 3 张中间帧的提示词，公共前缀占全长 ===")
print("  格数 %d　前缀率 中位 %.1f%%　最小 %.1f%%　最大 %.1f%%"
      % (len(前缀率), 前缀率[len(前缀率) // 2] * 100, 前缀率[0] * 100, 前缀率[-1] * 100))
print()

print("=== 2) 只不同的那截尾巴（前 6 格） ===")
for 号 in sorted(分格)[:6]:
    都 = 词们 = [分格[号][k] for k in sorted(分格[号])]
    长 = 0
    a = 都[0]
    while 长 < min(len(x) for x in 都) and all(x[长] == a[长] for x in 都):
        长 += 1
    print("  格%d（公共前缀 %d / %d 字）：" % (号, 长, len(a)))
    for i, x in enumerate(都, 1):
        print("      中%d 尾巴：…%s" % (i, x[长:]))
    print()
