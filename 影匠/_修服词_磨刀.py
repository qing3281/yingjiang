# -*- coding: utf-8 -*-
r"""把《磨刀》分镜里两个会漂的词换掉。

为什么必须改（都是实测出来的，不是理论）：

1. `深靛蓝军服` → 模型画成**民国军官制服**（立领 + 肩章 + 铜扣 + 皮带）。
   「军服」这个词对模型来说是现代的。产出的是阿七一个人穿着 20 世纪的制服
   站在一群古装人里 —— 一眼出戏。
   换成点名「古代武官袍」并把三个现代特征**显式排除**（没有肩章、没有领章、
   没有金属纽扣）—— 排除项比肯定项管用，因为模型会去凑那些词。

2. `银补子` → 模型画成**一块发亮的金属方牌**。补子是**绣在布上的**，
   材质错了整个官服就假了。把「银线绣的、是布料不是金属牌」写进去。

顺带踩到的坑（第 N 次）：这段代码第一版是用 PowerShell here-string 喂给
python -c 的，`r"作品\磨刀\..."` 被 PowerShell 吃掉引号后变成
`r作品\磨刀\...` → `SyntaxError: unexpected character after line continuation character`。
**带中文和引号的 Python 一律写成 .py 跑。**

用法：
    python _修服词_磨刀.py            # 空跑
    python _修服词_磨刀.py --真做
"""
import argparse
import io
import os
import re
import sys

分镜 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "作品", "磨刀", "02-九宫格.md")

对 = [
    # 长的先换，免得短词先把长词的一部分替掉
    ("胸前一块磨旧发暗的银补子",
     "胸前一方磨旧发暗的银线绣补子（银线绣在布上的方形补子，是布料不是金属牌）"),
    ("胸前一块磨旧发暗的银线绣补子", None),   # 幂等保护：已换过就跳过
    ("银补子", "银线绣补子（绣在布上的，不是金属牌）"),
    ("深靛蓝军服",
     "深靛蓝的古代武官袍（交领右衽、布腰带束在腰上，没有肩章、没有领章、没有金属纽扣）"),
    # 「洗得发白」里的「发白」被模型当成了颜色 → 画出一条雪白的围裙。
    # 中文里它是「旧到褪色」的意思，模型不这么读。把颜色钉死，把「不是白的」写进去。
    ("洗得发白的旧牛皮围裙",
     "深褐色的旧牛皮围裙（熟牛皮，颜色是深的，只是磨得发亮、边角磨出了毛边，绝不是白色）"),
    ("洗得发白的旧牛皮", "深褐色的旧牛皮（磨得发亮，颜色仍是深的，不是白色）"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--真做", action="store_true")
    参 = ap.parse_args()

    s = io.open(分镜, encoding="utf-8").read()
    原 = s
    计 = {}
    for a, b in 对:
        if b is None:
            continue
        if a in s:
            计[a] = s.count(a)
            s = s.replace(a, b)

    print(f"文件：{分镜}")
    for a, c in 计.items():
        print(f"  换 {c} 处：{a}")
    if not 计:
        print("  没有可换的（可能已经换过）")

    # 找出受影响的格号
    块 = re.split(r"^##\s*格\s*(\d+)", s, flags=re.M)
    受 = []
    for i in range(1, len(块), 2):
        if "古代武官袍" in 块[i + 1] or "银线绣" in 块[i + 1]:
            受.append(int(块[i]))
    print(f"  受影响的格：{受}")

    if not 参.真做:
        print("\n【空跑】没写盘")
        return 0

    if s == 原:
        print("\n内容没变，不写")
        return 0

    # 备份一次就够
    备 = 分镜 + ".改前"
    if not os.path.exists(备):
        io.open(备, "w", encoding="utf-8").write(原)
        print(f"  备份 → {备}")

    io.open(分镜, "w", encoding="utf-8").write(s)

    新 = io.open(分镜, encoding="utf-8").read()
    print(f"\n写回 {分镜}（{len(新)} 字）")
    print(f"  残留「深靛蓝军服」：{新.count('深靛蓝军服')}")
    print(f"  出现「古代武官袍」：{新.count('古代武官袍')}")
    print(f"  残留裸「银补子」：{len(re.findall(r'(?<!银线绣)银补子', 新))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
