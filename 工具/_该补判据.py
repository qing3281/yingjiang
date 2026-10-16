# -*- coding: utf-8 -*-
"""_该补判据.py —— 把两份数**对起来**：犯得最多的病，有没有一条能跑的判据？

为什么要有这个：
    用户 2026-10-16 00:20 追问过 ——「你觉得这条闸有意义吗？这个问题只会出现在生成视频上吗？
    如果以后我要让你做别的活怎么办呢？」

    我在 `_记忆自查.py` 里给了「词表 × 扫描器 × 交付块」。但那只覆盖 `_找复发.py` 的 20 类。
    `_数判据.py` 说 238 条经验里只有 60 条（25%）带一条能跑的判据 —— 另外 178 条是纯散文。
    **这两份数一直是分开看的**，所以「犯得最多的那几条，恰恰可能是没判据的那几条」这件事
    从来没被算出来过。

    这个脚本就是把它们对起来：**按「犯过几次」排序，标出有没有脚本。**
    头几行就是最该补判据的地方 —— 补完再跑 `_数判据.py`，那个百分数才会动。

用法：
    python _该补判据.py            # 全部
    python _该补判据.py --前 8      # 只看前 8 条
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
病表 = os.path.join(根, "_找复发.py")
模式 = os.path.join(根, "记忆", "模式.md")


def 读复发():
    """从 `_找复发.py` 的 `词表` 里读出 (病名, 判据文字, 词们)。"""
    if not os.path.exists(病表):
        return []
    src = io.open(病表, encoding="utf-8").read()
    i = src.find("词表 = [")
    if i < 0:
        return []
    深 = 0
    for k in range(i + len("词表 = "), len(src)):
        if src[k] in "[(":
            深 += 1
        elif src[k] in "])":
            深 -= 1
            if 深 == 0:
                段 = src[i + len("词表 = ") : k + 1]
                break
    else:
        return []
    try:
        表 = eval(段, {"__builtins__": {}}, {})
    except Exception:
        return []
    出 = []
    for 项 in 表:
        if isinstance(项, (list, tuple)) and len(项) >= 3:
            出.append((str(项[0]), str(项[1]), list(项[2])))
    return 出


def 读模式():
    """`记忆\\模式.md` 是 `_找复发.py` 生成的，每节长这样：

        ## 每格都拼的公共段落里塞进了不该有的实物名词　（20 次）

    第一次写这个函数时我猜的是 `### N 次 ... **名**` —— 猜错了，一律返回 0，
    于是下面那张表每一行的次数都是「—」。**先读一眼真文件再写解析**。
    """
    次 = {}
    if not os.path.exists(模式):
        return 次
    s = io.open(模式, encoding="utf-8").read()
    for m in re.finditer(r"^##\s+(.+?)\s*[（(](\d+)\s*次[)）]\s*$", s, re.M):
        次[m.group(1).strip()] = int(m.group(2))
    return 次


def 有脚本(文):
    """这一类的判据文字里，提没提到一个能跑的脚本。"""
    return bool(re.search(r"(_[\u4e00-\u9fa5A-Za-z0-9]+\.py|python\s+[\w\u4e00-\u9fa5_]+\.py)", 文))


def main():
    前 = 8
    a = sys.argv[1:]
    if "--前" in a:
        try:
            前 = int(a[a.index("--前") + 1])
        except Exception:
            pass

    病 = 读复发()
    次 = 读模式()
    # 一类的名字在 模式.md 里可能被截断，用前缀对上
    def 命中数(名):
        if 名 in 次:
            return 次[名]
        for k, v in 次.items():
            if k[:12] == 名[:12] or 名[:12] in k:
                return v
        return 0

    行 = sorted(病, key=lambda x: -命中数(x[0]))
    有 = [x for x in 行 if 有脚本(x[1])]
    无 = [x for x in 行 if not 有脚本(x[1])]

    print("══ 20 类病里，判据能不能跑 ══")
    print("   带脚本的 %d 类　只有文字的 %d 类" % (len(有), len(无)))
    print()
    print("══ 按「犯过几次」排序 —— 头 %d 条就是最该补判据的 ══" % 前)
    for 名, 判据, 词 in 行[:前]:
        n = 命中数(名)
        标 = "✓ 有脚本" if 有脚本(判据) else "✗ 只有文字"
        print("   %-4s %-12s %s" % (("%d 次" % n) if n else "—", 标, 名))
        if not 有脚本(判据):
            print("        现在只有一句话：%s" % 判据[:78].replace("\n", " "))
    print()
    print("══ 全部没有脚本的 %d 类 ══" % len(无))
    for 名, 判据, 词 in 无:
        print("   · %s" % 名)
    print()
    print("补一条判据 = 写一个 `_查xxx.py`，能对**产物**重跑，输出非 0 就是犯了。")
    print("补完再跑 `python _数判据.py` —— 那个 25% 才会动。")


if __name__ == "__main__":
    main()
