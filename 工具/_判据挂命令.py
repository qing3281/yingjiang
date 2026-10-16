# -*- coding: utf-8 -*-
"""_判据挂命令.py —— 给 `_找复发.py` 词表里每一类病的判据，挂上「跑哪条命令」。

为什么要做这个：
    `_该补判据.py` 把两份数对起来之后，头 12 条是这样的 ——

        20 次  每格都拼的公共段落里塞进了不该有的实物名词
        16 次  用否定句描述不想要的东西
        14 次  判据说 OK，其实什么都没量
        …

    **犯得最多的那 12 类，判据文字里一个脚本名都没有。** 也就是说：
    `_总检查.py` 明明能查第 1 类、`_记忆自查.py` 明明能查第 2 类，
    **可是词表自己没说「去跑它」** —— 于是我每次读完那段话，就只是读完了。

    用户 2026-10-16 00:20 追问的「这条闸有意义吗 / 换个活怎么办」，
    答案就在这儿：**判据不是一句规矩，判据是一条命令。**
    没有命令的判据，等于没有。

做法：
    读 `_找复发.py`，把 `词表` 里每一类的判据字符串末尾追加一句
        `**跑**：python _总检查.py`          （这一类的检查器）
    或者
        `**跑**：★ 还没判据 —— 这一条现在只是一句话`
    已经挂过的（含 `**跑**`）不重复挂。

用法：
    python _判据挂命令.py --看      # 只打印将要怎么改
    python _判据挂命令.py           # 真改（改前备份）
"""
import io
import os
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
源 = os.path.join(根, "_找复发.py")

# 病名（前缀匹配）→ 跑哪条命令。空字符串 = 还没有判据，老实写出来。
命令 = {
    "每格都拼的公共段落": "python _总检查.py",
    "用否定句描述不想要的东西": "python _记忆自查.py",
    "否定写法": "python _记忆自查.py",
    "只修被点到的那一处": "python _总检查.py",
    "同一个人在一格里被描述两遍": "python _总检查.py",
    "把尺子改短": "python _记忆自查.py",
}


def 主(看):
    if not os.path.exists(源):
        print("  ✗ 找不到 %s" % 源)
        return 1
    s = io.open(源, encoding="utf-8").read()
    if "**跑**：" in s and not 看:
        print("  · 已经挂过了（文件里有 `**跑**：`），不重复")
        return 0

    i = s.find("词表 = [")
    if i < 0:
        print("  ✗ 找不到 词表 = [")
        return 1
    深 = 0
    for k in range(i + len("词表 = "), len(s)):
        if s[k] in "[(":
            深 += 1
        elif s[k] in "])":
            深 -= 1
            if 深 == 0:
                尾巴 = k + 1
                break
    else:
        print("  ✗ 词表没有收尾")
        return 1

    段 = s[i:尾巴]
    新段 = 段
    n挂 = n无 = 0
    for m in re.finditer(r'\("([^"]+)",\s*"([^"]*)",', 段, re.S):
        名 = m.group(1)
        if "**跑**" in m.group(2):
            continue
        c = ""
        for 键, v in 命令.items():
            if 键 in 名:
                c = v
                break
        if c:
            追加 = ' **跑**：`%s`。' % c
            n挂 += 1
        else:
            追加 = " **跑**：★ 还没判据 —— 这一条现在只是一句话。"
            n无 += 1
        # 在判据字符串的收尾引号前插入
        起 = m.start(2)
        止 = 起 + len(m.group(2))
        新段 = 新段.replace(段[起:止] + '"', 段[起:止] + 追加 + '"', 1)
        print("   %s %s" % ("✓" if c else "·", 名[:34]))

    print()
    print("  → 挂了命令的 %d 类，老实标「还没判据」的 %d 类" % (n挂, n无))
    if 看:
        print("  （--看：没有落盘）")
        return 0

    备份 = 源 + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(源, 备份)
    print("  ✓ 备份 %s" % os.path.basename(备份))
    io.open(源, "w", encoding="utf-8").write(s[:i] + 新段 + s[尾巴:])
    print("  ✓ 落盘 %s" % 源)
    return 0


if __name__ == "__main__":
    sys.exit(主("--看" in sys.argv))
