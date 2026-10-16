# -*- coding: utf-8 -*-
"""验 `_记忆自查.py` 里新加的「轮换红线」那几行真的会轮。

第 0.05 条病：「判据说 OK，其实什么都没量」。
所以这个脚本**不重写公式**，而是把 `今天记了几笔()` 换成假数，
去调真的 `块()`，看它每次打出来的是不是真变了。
"""
import importlib.util
import sys

sys.stdout.reconfigure(encoding="utf-8")

spec = importlib.util.spec_from_file_location("mz", r"D:\DSHworkspace\工具\_记忆自查.py")
mz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mz)

print("══ 1. 红线表本身 ══")
print("共 %d 条：" % len(mz.红线们))
for i, (条, 判据) in enumerate(mz.红线们, 1):
    print("  %2d. %s" % (i, 条))

print()
print("══ 2. 真的轮吗（把 `今天记了几笔` 换成假数，调真的 `块()`）══")
看到的 = []
真几笔 = mz.今天记了几笔
for n in (1, 2, 3, 12, 13, 14, 15, 26, 27, 39):
    mz.今天记了几笔 = lambda n=n: n
    b = mz.块()
    行 = [l for l in b.splitlines() if l.startswith("本轮红线")]
    if not 行:
        print("  几笔=%-3d ★ 块里没有「本轮红线」这一行 —— 没加进去！" % n)
        continue
    print("  几笔=%-3d %s" % (n, 行[0]))
    看到的.append(行[0])

print()
print("══ 3. 判据 ══")
# ★ 上一版这里写的是「10 次里 ≥9 种不同」，跑了才发现是**我自己判据写错了**：
#   抽的 10 个数（1,2,3,12,13,14,15,26,27,39）÷13 取余本来就只有 5 种。
#   要验「一轮 13 条不重不漏」，就得**连着抽 1..13**。
一整轮 = []
for n in range(1, len(mz.红线们) + 1):
    mz.今天记了几笔 = lambda n=n: n
    行 = [l for l in mz.块().splitlines() if l.startswith("本轮红线")]
    一整轮.append(行[0] if 行 else "★缺")
mz.今天记了几笔 = lambda: len(mz.红线们) + 1
第14笔 = [l for l in mz.块().splitlines() if l.startswith("本轮红线")]
第14笔 = 第14笔[0] if 第14笔 else "★缺"

print("  块里出现过「本轮红线」这一行：%s" % ("是" if 看到的 else "★ 否 —— 就是没做"))
print("  连着抽 1..%-2d 共 %d 次，打出 %d 种不同的红线：%s"
      % (len(mz.红线们), len(一整轮), len(set(一整轮)),
         "一轮不重不漏 ✅" if len(set(一整轮)) == len(mz.红线们) else "★ 有重复或缺失"))
print("  第 1 笔和第 %d 笔是不是同一条：%s"
      % (len(mz.红线们) + 1,
         "是 ✅（%d 条一循环）" % len(mz.红线们) if 一整轮[0] == 第14笔
         else "★ 不是 —— 公式不对"))

print()
print("══ 4. 真跑一次（不打假数，看今天的实数）══")
# ★ 上一版这里忘了把 `今天记了几笔` 换回真的 —— 第 3 节打假数的 lambda 泄到这儿，
#   于是「真跑一次」打出来的 14 其实是我自己灌进去的假数。**又一个假判据，当场抓到。**
mz.今天记了几笔 = 真几笔
真块 = mz.块()
print("  `今天记了几笔()` = %d" % mz.今天记了几笔())
for l in 真块.splitlines():
    if "红线" in l or "自己重跑" in l:
        print("  " + l)
