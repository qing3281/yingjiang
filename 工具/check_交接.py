# -*- coding: utf-8 -*-
"""check_交接.py —— 验 `交接.md` 里每一个路径是不是真的在磁盘上。

为什么要有这个：`交接.md` 给下一个 AI 用，**里面写错一个路径，他就要多花半小时找**。
所以本文里凡是出现 `D:\\...` 的地方，一律逐个 Test-Path。

用法：python check_交接.py            （拿默认的 交接.md）
      python check_交接.py --文 <别的.md>
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

默认 = r"D:\DSHworkspace\交接.md"
# 不用验的（写清楚为什么，不然这条就成了藏错的地方）
不验 = {
    r"E:\影匠AI": "★ 这是**远端**那台机器的路径，本机当然找不到",
    r"E:\影匠AI\ComfyUI\input": "同上",
    r"D:\DSHworkspace\素材\网盘\_飞彩解包": "★ 太大，本脚本不递归进去（只用来看它不存在就报，不作为失败）",
}


def 扫(文):
    稿 = open(文, encoding="utf-8").read()
    路 = set()
    # ① 反引号里的
    for m in re.finditer(r"`([A-Za-z]:\\[^`\n]+?)`", 稿):
        路.add(m.group(1))
    # ② 反引号外、行内出现的（表格里很多）
    for m in re.finditer(r"(?<![`\w])([A-Za-z]:\\[^\s`|（）()\[\]，。；：]*)", 稿):
        路.add(m.group(1))
    洁 = set()
    for s in 路:
        s = s.strip().rstrip("。，、）):：*'\"")
        s = re.sub(r":\d+(-\d+)?$", "", s)      # 去掉 :123 行号后缀
        if not s or "*" in s or "<" in s:
            continue
        if len(s) <= 3:                          # 只有盘符
            continue
        洁.add(s)
    return 稿, sorted(洁)


def 主(文):
    稿, 路 = 扫(文)
    在, 缺, 免 = [], [], []
    for p in 路:
        if os.path.exists(p):
            在.append(p)
        elif any(p == k or p.startswith(k) for k in 不验):
            免.append(p)
        else:
            缺.append(p)
    print("══ 验 %s ══" % 文)
    print("  行数 %d　字节 %d" % (稿.count("\n") + 1, os.path.getsize(文)))
    print("  提到绝对路径 %d 个" % len(路))
    print("  ✓ 在磁盘上　　%d" % len(在))
    print("  · 不验（有理由）%d" % len(免))
    for p in 免:
        print("      %s" % p)
    for p in 缺:
        print("  ✗ 找不到　%s" % p)
    print()
    print("  %s　结论：%s" % ("=" * 46, "全对 ✓" if not 缺 else "有 %d 条对不上 ✗" % len(缺)))
    return 1 if 缺 else 0


if __name__ == "__main__":
    参 = argparse.ArgumentParser()
    参.add_argument("--文", default=默认)
    raise SystemExit(主(参.parse_args().文))
