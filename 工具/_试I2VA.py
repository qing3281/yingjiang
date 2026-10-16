# -*- coding: utf-8 -*-
"""对照实验：同样的首帧、同样的提示词、同样的种子，只把**末帧去掉**，看那一跳还在不在。

## 为什么要做这个实验

`check_怪帧.py` 扫了 23 段，**22 段都有「某一帧突然比旁边大几十倍」**。
把帧摊开看（`_看子镜_格1_1.png` / `_看子镜_格3_2.png`）：

    格1_1：f10~f17 两个人慢慢走近，**f18 突然「跳」近一大截**（单帧差 39.25，
           而旁边每帧只差 1.5~3.1），f19 之后又平顺了
    格3_2：f24~f27 一样，**f28 直接切了个近景**（单帧差 24.85，旁边只有 0.2）

每一段都发生在**中间某个位置**，不是在结尾。

**假设**：模型被「首帧 + 末帧」两头钉住时，会在中途「跳」过去把两头对上。
如果去掉末帧它就不跳了，那**修法就是把全部子镜改成 I2VA**（只喂首帧），
关键帧退化成「每一段的起点」而不是「两端都要对上的硬边界」。

判据：拿同首帧、同词、同种子出一段 I2VA，跟已有的 FL2VA 版比「单帧最大跳 / 中位数」：
    比值还是几十倍 → 假设错，跳跟末帧无关
    比值掉到个位数   → 假设对，改成 I2VA

用法：python _试I2VA.py
"""
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
根 = r"D:\DSHworkspace\影匠"
spec = importlib.util.spec_from_file_location("chuzijing", os.path.join(根, "_出子镜.py"))
Z = importlib.util.module_from_spec(spec)
sys.path.insert(0, 根)
spec.loader.exec_module(Z)

import _出H3 as H   # noqa: E402

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
出目 = r"D:\DSHworkspace\_试I2VA"


def 主():
    os.makedirs(出目, exist_ok=True)
    戏 = "楚子航"
    号, 段 = 1, 1
    动态 = H.读动态(戏)
    格 = H.读格(戏)
    g = 格.get(号, {})
    光 = g.get("光色", "")
    动作 = 动态.get(号) or g.get("动作") or "轻微的自然动作"
    词 = f"{动作}。环境：{光}。{Z.词尾}"
    种子值 = H.种子 + 号 * 1009 + 段 * 13          # 和 格1_1 一模一样
    首路 = os.path.join(目, "01_格%d.png" % 号)
    出 = os.path.join(出目, "格%d_%d_无末帧.mp4" % (号, 段))
    if os.path.isfile(出) and os.path.getsize(出) > 10000:
        print("· 已经有 %s（%.2f MB），不重出" % (出, os.path.getsize(出) / 1048576))
        return 0
    print("▶ 本机　I2VA（只喂首帧）　格%d_%d　种子 %d" % (号, 段, 种子值))
    print("  首帧：%s" % 首路)
    print("  词：%s" % 词[:120] + "…")
    服务 = H.端点("本机")
    H.帧数 = Z.帧数
    成 = Z.出段(服务, "本机", 首路, "", 词, 种子值, "试I2VA_格%d_%d" % (号, 段), 出)
    print("  %s　%.2f MB" % ("✓ 出来了" if 成 else "✗ 没出",
                            os.path.getsize(出) / 1048576 if os.path.isfile(出) else 0))
    return 0 if 成 else 1


if __name__ == "__main__":
    sys.exit(主())
