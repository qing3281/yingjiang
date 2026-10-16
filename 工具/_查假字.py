# -*- coding: utf-8 -*-
"""查「假字」—— 提示词里给了模型一个「这里该有字」的缺口，它就会自己填字。

来历（用户提过多次，最近一次是 2026-10-16 凌晨看首帧）：
    格2 画出来的是 **墙上三个一米高的「楚子航」大字 + 一张带字的告示牌**。
    根：【画面】里写「墙上被人用黑漆喷了**一行一米高的涂鸦**」——
    **我没说那是什么字，模型就填了它最熟的字：角色的名字。**

    同类的还有格21 的「柱子上的**广告纸**卷着边」——那也是请它画字。

判据（两类，分开报）：
    ① **请它画字**：涂鸦 / 告示 / 广告 / 标语 / 招牌 / 海报 / 通知 / 横幅 /
       报纸 / 书 / 册子 / 笔记 / 路牌 / 门牌 / 编号 / 写着 / 印着 / 刻着 …
       → 这些词在提示词里出现，模型**几乎一定会**画出可读的字。
    ② **直接要字**：「文字」「字幕」「水印」「写上」—— 这些是明着要，直接报错。

怎么改（不是删掉那句话，是**把"字"换成一个不是字的形状**）：
    ✗ 「墙上被人用黑漆喷了一行一米高的**涂鸦**」
    ✓ 「墙上被人用黑漆喷了**一道一米高的斜杠**、漆已经褪成暗灰色、下沿淌出七八条漆痕」
    ✗ 「贴着一张褪色的施工**告示**」
    ✓ 「墙上贴过东西留下的**四块方形胶印**、纸早没了」

用法：
    python _查假字.py             # 查楚子航
    python _查假字.py --作品 <名>
"""
import argparse
import importlib.util
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根

# ① 请它画字的词。★ 这一行就是判据本身，想到新的就往这儿加。
请它画字 = [
    "涂鸦", "告示", "广告", "标语", "招牌", "牌匾", "海报", "通知",
    "布告", "横幅", "报纸", "路牌", "站牌", "门牌", "匾", "锦旗",
    "编号", "序号", "标牌", "标签", "封条",
]

# ② 明着要字的词 —— 直接报错，没有商量。
直接要字 = [
    "文字", "字幕", "水印", "写着", "写着字", "印着", "刻着", "题着",
    "一行字", "几个字", "汉字", "英文单词", "字母",
]

# ③ 这些词看着像①，但说的是**没有字**，放过。
不算 = [
    r"没有一个字", r"没有字", r"没有任何字", r"全都不认识的字",
]


def 载入(路, 名):
    sp = importlib.util.spec_from_file_location(名, 路)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def 查一格(g):
    出 = []
    for 字段 in ("位置", "画面", "动作", "特效", "点", "目的", "标"):
        文 = g.get(字段, "")
        if not isinstance(文, str) or not 文:
            continue
        for w in 请它画字:
            i = 文.find(w)
            if i >= 0:
                片 = 文[max(0, i - 26): i + 26 + len(w)]
                if any(__import__("re").search(p, 片) for p in 不算):
                    continue
                出.append(("请它画字", 字段, w, 片.replace("\n", " ")))
        for w in 直接要字:
            i = 文.find(w)
            if i >= 0:
                片 = 文[max(0, i - 26): i + 26 + len(w)]
                if any(__import__("re").search(p, 片) for p in 不算):
                    continue
                出.append(("★ 直接要字", 字段, w, 片.replace("\n", " ")))
    return 出


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--作品", default="楚子航")
    a = ap.parse_args()
    目 = os.path.join(根, "影匠", "作品", a.作品)

    格们 = []
    for f in ("_格数据_上.py", "_格数据_下.py"):
        路 = os.path.join(目, f)
        if os.path.isfile(路):
            格们 += 载入(路, "数据_" + f[-6:-3]).格
    格们.sort(key=lambda g: g["号"])

    print(f"查《{a.作品}》　{len(格们)} 格　·　查提示词里有没有给模型留「该有字」的缺口")
    print()
    总 = 0
    硬 = 0
    坏格 = []
    for g in 格们:
        问题 = 查一格(g)
        if 问题:
            总 += len(问题)
            坏格.append(g["号"])
            print(f"  ✗ 格{g['号']:>2}　{g.get('标','')[:26]}　{len(问题)} 处")
            for 类, 字段, w, 片 in 问题:
                if 类.startswith("★"):
                    硬 += 1
                print(f"       {类}　[{字段}] 「{w}」　…{片}…")
    print()
    print("─" * 70)
    if not 总:
        print(f"✓ {len(格们)} 格里没有任何「该有字」的缺口。")
    else:
        print(f"★ 共 {总} 处（其中直接要字 {硬} 处），在格 {坏格}。")
        print()
        print("  怎么改：**不要删掉那句话，把「字」换成一个不是字的形状。**")
        print("    ✗「喷了一行一米高的涂鸦」   →  ✓「喷了一道一米高的斜杠、下沿淌出漆痕」")
        print("    ✗「贴着一张施工告示」       →  ✓「贴过东西留下的四块方形胶印、纸早没了」")
        print("    ✗「柱子上的广告纸卷着边」   →  ✓「柱面上有一层干掉的灰」")
        print()
        print("  ★ 改完**必须重出这些格**。")
    return 1 if 总 else 0


if __name__ == "__main__":
    sys.exit(主())
