# -*- coding: utf-8 -*-
"""_放桌面成片.py —— 保证「他双击就能看到成片」，不是「路径在某个 md 里」。

为什么单独一个脚本：`_守成片.py` 此刻**已经加载进内存**了，改磁盘上的它
对那个进程没用（它自己开头就写着这条）。所以「桌面留一个 .lnk」这件事
不能塞进它，得单独做一次。

而且这件事本来就是 AGENTS.md 第 0.05 条第二个病：
    「少问一句『他打开它要敲几下』」—— 犯过 11 次。
    「凡是我给他的东西，桌面必须有 .lnk 或一个能点开的页。」

复用 `_建快捷方式.py` 里的 `建快捷方式()`，不重写（第 0.2 条：能用就用、能抄就抄）。

    python _放桌面成片.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\DSHworkspace")
import _建快捷方式 as 建  # noqa: E402

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
成片 = os.path.join(目, "片", "楚子航_成片_字幕.mp4")
报告 = os.path.join(目, "_成片验收.md")
验帧 = os.path.join(目, "片", "_验帧")


def 做(桌, 名, 目标, 说明, 图):
    壳 = os.path.join(桌, "%s.lnk" % 名)
    ok, 日 = 建.建快捷方式(壳, 目标, os.path.dirname(目标), 说明, 图)
    if ok:
        print("  ✓ 桌面：%s　%d B　→ %s" % (壳, os.path.getsize(壳), 目标))
        print("      目标现在存在吗：%s" % ("在" if os.path.exists(目标) else "还没（成片出来就有了）"))
    else:
        print("  ✗ %s 建失败：%s" % (名, 日[:300]))
    return ok


def main():
    桌 = 建.桌面()
    if not os.path.isdir(桌):
        print("  ✗ 找不到桌面：%s" % 桌)
        return 1
    print("  桌面：%s" % 桌)
    print()
    好 = 0
    好 += 做(桌, "楚子航成片", 成片, "《楚子航》成片（硬字幕）—— 双击就放", 116)
    好 += 做(桌, "楚子航验收", 报告, "《楚子航》成片验收报告 —— 逐条判据 + 没做到的明说", 70)
    print()
    if os.path.isdir(验帧):
        print("  逐帧留证在：%s　%d 个文件" % (验帧, len(os.listdir(验帧))))
    else:
        print("  逐帧留证目录还没建（验片时才会生成）：%s" % 验帧)
    print()
    print("  %d / 2 建好了" % 好)
    return 0 if 好 == 2 else 1


if __name__ == "__main__":
    sys.exit(main())
