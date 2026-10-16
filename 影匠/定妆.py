# -*- coding: utf-8 -*-
"""★ 定妆 —— 影匠里**所有出图都必须走这里**，不许各写各的提示词。

为什么要有这个文件：
  同一个提示词每次出的人脸都不一样。**固定种子 = 固定这个人。**
  形象定住靠三样一起锁：**种子 + 一字不改的提示词 + 尺寸和模型名**
  （换其中任何一个，脸就换了）。

用法：
    import 定妆
    定妆.提示词("楚子航")                    # 拿到锁死的提示词
    定妆.出图("楚子航")                      # 用锁死的种子重出成图
    定妆.出图("楚子航", 换="背景是雨夜的地铁隧道")   # 换场景但同一个脸
    定妆.列表()                              # 有哪几个角色
    定妆.卡("夏弥")                          # 整张卡

卡在 `影匠\\角色卡\\<角色>.json`，人看的那份在 `影匠\\角色卡\\<角色>.md`。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

卡目录 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "角色卡")


def 列表() -> list:
    """有哪些角色是定过妆的。"""
    if not os.path.isdir(卡目录):
        return []
    return sorted(f[:-5] for f in os.listdir(卡目录)
                  if f.endswith(".json") and not f.startswith("_"))


def 卡(角色: str) -> dict:
    """读一整张卡。找不到就抛，不兜底 —— 没定妆的角色不许拿去出图。"""
    p = os.path.join(卡目录, 角色 + ".json")
    if not os.path.isfile(p):
        raise FileNotFoundError(
            "「%s」没有定妆卡（看过的是：%s）。先去定妆，别拿一个没锁的形象去出图。"
            % (角色, "、".join(列表()) or "一个都没有"))
    return json.load(open(p, encoding="utf-8"))


def 提示词(角色: str) -> str:
    return 卡(角色)["提示词"]


def 种子(角色: str) -> int:
    return int(卡(角色)["种子"])


def 尺寸(角色: str) -> tuple:
    c = 卡(角色)
    return int(c["宽"]), int(c["高"])


def 出图(角色: str, 换: str = "", 存到: str = "", 报=None, **多) -> dict:
    """用锁死的种子 + 锁死的提示词出图。

    `换` —— 附在提示词**末尾**的一句话，用来换场景/动作/景别，但**脸和种子不变**。
            （末尾权重最高，所以要换的东西放这里。）
    """
    import 引擎
    c = 卡(角色)
    文 = c["提示词"]
    if 换:
        文 = 文 + "。" + 换.strip().rstrip("。") + "。"
    return 引擎.文生图(文, 宽=int(多.pop("宽", c["宽"])), 高=int(多.pop("高", c["高"])),
                      种子=int(多.pop("种子", c["种子"])), 模板=多.pop("模板", c.get("模板", "zimage_turbo")),
                      前缀=多.pop("前缀", "定妆_" + 角色),
                      存到=存到 or os.path.join(卡目录, "_出图", 角色 + ".png"),
                      报=报, **多)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("  定过妆的角色：")
    for r in 列表():
        c = 卡(r)
        print("     %-14s 种子 %-5d %dx%d  %s" % (r, c["种子"], c["宽"], c["高"], c.get("模板", "")))
