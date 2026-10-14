# -*- coding: utf-8 -*-
r"""_核台账.py —— 把「他敲过的每一句」和 `要求台账.md` 对一遍，找出**漏记的指令**。

════════════════════════════════════════════════════════════════════
★ 为什么写这个（2026-10-15 07:50）

用户台账里的 **#6** 到现在还是 ✗：

> **「记忆系统搞好，把我给你说的每个指令都记一下」**（10-15）

还有当天的：

> 13:12 **今天最重要**：……**记忆系统有问题，优化下**……

`_用户原话.py` 已经在做了「把他敲的每一句抽出来」（判据 `kind=='user'` 且
`source.rpcId` 存在），但它**只写一个 json，没人拿它跟台账对**。
所以他新说的指令，只要我忘了手写进台账，就永远丢了。

这个脚本就是那道闸门：**抽原话 → 逐条跟台账比 → 报出没记进去的**。
`--补` 直接把漏的追加进台账（状态写 🟡，备注写「自动补记，待核」）。

════════════════════════════════════════════════════════════════════
用法：
    python _核台账.py             # 只报，不改
    python _核台账.py --短 8      # 公共子串阈值（默认 8 个字）
    python _核台账.py --补        # 把漏的追加进 要求台账.md（自动备份）
    python _核台账.py --全        # 连已记上的也列出来
"""

import io
import os
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

台账路 = os.path.join(根, "要求台账.md")


def 读台账原话():
    """把 `要求台账.md` 里所有 `|` 表格行的**整行**抠出来，逐列都当可比对的料。

    ★ 一开始我只比第 2 列（「他原话」那列），结果把一大堆「其实记上了」的判成漏记 ——
      因为台账的备注列里常常直接抄着他的原话。**整行都要比。**
    """
    if not os.path.isfile(台账路):
        return []
    出 = []
    for i, 行 in enumerate(io.open(台账路, encoding="utf-8").read().splitlines(), 1):
        s = 行.strip()
        if not s.startswith("|"):
            continue
        列 = [c.strip() for c in s.strip("|").split("|")]
        if len(列) < 2 or set(s) <= set("|-: "):
            continue
        出.append((i, 列[0], 列[1], 归一(s)))
    return 出


def 归一(s):
    """只留中日韩字和字母数字 —— 标点、空格、加粗星号都不参与比对。"""
    return "".join(c for c in s if "\u4e00" <= c <= "\u9fff" or c.isalnum())


def 最长公共(a, b):
    """最长公共子串长度（a、b 都别太长；台账行和原话都在几百字内）。"""
    if not a or not b:
        return 0
    # 滚动数组，省内存
    上 = [0] * (len(b) + 1)
    好 = 0
    for i in range(1, len(a) + 1):
        今 = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                今[j] = 上[j - 1] + 1
                if 今[j] > 好:
                    好 = 今[j]
        上 = 今
    return 好


def 主():
    argv = sys.argv[1:]
    阈 = 8
    if "--短" in argv:
        i = argv.index("--短")
        if i + 1 < len(argv) and argv[i + 1].isdigit():
            阈 = int(argv[i + 1])

    # 少说几句没用的话：太短的（「好」「继续」）不算指令
    try:
        import _用户原话
    except Exception as e:
        print(f"  ✗ 引不到 _用户原话.py：{e}")
        return 2

    净, 会话数, _ = _用户原话.扫()
    台账 = 读台账原话()
    台账归 = [(n, 时, 原, g) for n, 时, 原, g in 台账]

    print(f"  会话存档 {会话数} 个　他敲的 {len(净)} 条　台账 {len(台账)} 行")
    print(f"  判「记上了」的门槛：某一行跟它的最长公共子串 ≥ {阈} 个字\n")

    漏 = []
    记 = 0
    for x in 净:
        话 = re.sub(r"\s+", " ", x["话"]).strip()
        if len(归一(话)) < 4:          # 「好」「可以」这类不算指令
            continue
        归 = 归一(话)
        最好 = (0, None)
        for n, 时, 原, g in 台账归:
            L = 最长公共(归, g)
            if L > 最好[0]:
                最好 = (L, (n, 时, 原))
        if 最好[0] >= 阈:
            记 += 1
            if "--全" in argv:
                t = time.strftime("%m-%d %H:%M", time.localtime(x["时"] / 1000))
                print(f"    ✓ [{t}] {话[:60]}　→ 台账第 {最好[1][0]} 行（{最好[0]} 字）")
        else:
            漏.append((x["时"], 话, 最好[0], 最好[1]))

    print(f"  ── 结果 ──")
    print(f"    已记上：{记} 条")
    print(f"    ★ 没记上：{len(漏)} 条")

    if 漏:
        漏.sort(key=lambda z: z[0])
        print()
        for 时, 话, L, 近 in 漏:
            t = time.strftime("%m-%d %H:%M", time.localtime(时 / 1000))
            尾 = f"　（最像的一行是第 {近[0]} 行，只重合 {L} 字）" if 近 else "　（台账里一行都不像）"
            print(f"    · [{t}] {话[:100]}{尾}")
    else:
        print("    （他说过的每一句，台账里都找得到对应）")
        return 0

    if "--补" not in argv:
        print(f"\n  想补进台账就加 --补")
        return 1

    备 = 台账路.replace(".md", f".bak-补记前-{time.strftime('%Y%m%d-%H%M%S')}.md")
    shutil.copy2(台账路, 备)
    新 = []
    for 时, 话, _L, _近 in 漏:
        t = time.strftime("%m-%d %H:%M", time.localtime(时 / 1000))
        净话 = re.sub(r"\s+", " ", 话).replace("|", "／")[:150]
        新.append(f"| {t} | {净话} | 🟡 | 由 `_核台账.py --补` 自动补记（2026-10-15），待核 |")
    文 = io.open(台账路, encoding="utf-8").read()
    if not 文.endswith("\n"):
        文 += "\n"
    文 += "\n## 自动补记（`_核台账.py` 2026-10-15）\n\n"
    文 += "| 时间 | 他说的 | 状态 | 备注 |\n|---|---|---|---|\n"
    文 += "\n".join(新) + "\n"
    io.open(台账路, "w", encoding="utf-8", newline="\n").write(文)
    print(f"\n  ✓ 备份 {os.path.basename(备)}")
    print(f"  ✓ 补了 {len(新)} 行 → {台账路}")
    return 0


if __name__ == "__main__":
    sys.exit(主())
