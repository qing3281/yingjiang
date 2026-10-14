# -*- coding: utf-8 -*-
"""《觉醒》配音：读 03-台词.md → 逐句合成 → 按格子排在成片时间轴上 → 写 SRT。

    python _配台词_觉醒.py            合成 + 排轴 + 写 SRT
    python _配台词_觉醒.py --只排      音频都在，只重排时间轴和 SRT
    python _配台词_觉醒.py --干跑      只解析台词表，不合成

## 时间轴

H3 每格 **107 帧 @24fps = 4.4583 秒**，格间交叉溶解吃掉 **0.5 秒**，
所以第 N 格在片体里的起点 = `(N-1) × (4.4583 - 0.5)` = `(N-1) × 3.9583`。
再整体加上片头卡（`--头`，默认 4.0 秒）。

一格里两句时：第一句落在 `格顶 + 0.30`，第二句落在 `第一句结束 + 0.25`，
并且**第二句的尾巴不许超过这一格的末尾**（超了就往前顶，不是裁短）。
"""
import argparse
import io
import json
import os
import re
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 配音  # noqa: E402

每格秒 = 107 / 24.0          # 4.45833
转场吃 = 0.5
步长 = 每格秒 - 转场吃       # 3.95833
台词文件 = os.path.join(根, "作品", "觉醒", "03-台词.md")
出夹 = os.path.join(根, "作品", "觉醒", "配音")
映射路 = os.path.join(根, "音色", "角色映射.json")

合法情感 = {"Neutral", "Happy", "Angry", "Sad", "Fear", "Surprised"}


def 读台词(报=print):
    """从 03-台词.md 的表格里抠出 (格, 说话人, 台词, 情感)。"""
    文 = io.open(台词文件, encoding="utf-8").read()
    # 只取第一个表格（后面「静默点」「自查」那两张表不是台词）
    块 = 文.split("| 格 | 说话人 | 台词 | 情感 |", 1)
    if len(块) < 2:
        raise SystemExit("✗ 03-台词.md 里找不到 `| 格 | 说话人 | 台词 | 情感 |` 表头")
    表 = 块[1].split("\n---", 1)[0]

    行 = []
    for 线 in 表.splitlines():
        线 = 线.strip()
        if not 线.startswith("|"):
            continue
        c = [x.strip() for x in 线.strip("|").split("|")]
        if len(c) != 4:
            continue
        if not c[0].isdigit():
            continue
        格, 说, 词, 情 = int(c[0]), c[1], c[2], c[3]
        if not (1 <= 格 <= 74):
            raise SystemExit(f"✗ 格号越界：{格}")
        if 说.startswith("（") or "(" in 说:
            raise SystemExit(f"✗ 说话人带括号：{说}")
        if 情 not in 合法情感:
            raise SystemExit(f"✗ 情感非法：{情}（格{格}）")
        if not (1 <= len(词) <= 20):
            raise SystemExit(f"✗ 台词长度 {len(词)}：格{格}「{词}」")
        行.append({"格": 格, "角色": 说, "台词": 词, "情感": 情})

    报(f"  台词 {len(行)} 句，覆盖 {len({r['格'] for r in 行})} 个格")
    说话人 = sorted({r["角色"] for r in 行})
    报(f"  说话人 {len(说话人)} 个：{'、'.join(说话人)}")
    # 映射表覆盖检查
    映 = json.load(io.open(映射路, encoding="utf-8"))
    有 = set(映.get("角色", {}))
    缺 = [x for x in 说话人 if x not in 有]
    if 缺:
        raise SystemExit(f"✗ 这些说话人不在 音色\\角色映射.json 里：{'、'.join(缺)}")
    报(f"  音色映射 {len(有)} 个角色，全部命中 ✓")
    return 行


def 音色路径(角色):
    映 = json.load(io.open(映射路, encoding="utf-8"))
    t = 映["角色"][角色]
    音 = t["音色"]
    # 映射表里有的写的是「相对 音色\原声\」的相对路径，有的直接写绝对路径
    return 音 if os.path.isabs(音) else os.path.join(根, "音色", "原声", 音)


def 排轴(条们, 头偏, 报=print):
    """按格子把每句放到成片时间轴上。返回带 起 / 时长 的列表。

    ## 第一版的错（2026-10-14 19:50 修）

    原来对「一句太长、放不下」的处理是**把这一句往回挪**
    （`游 = max(格顶+0.30, 格尾-0.10-时)`）。
    往回挪就会**压住上一句** —— 实测 8 处同格内两句重叠，全都是这么来的。
    而且第一句被砍到 `每格秒*0.48` 只砍了**字幕长度**，音频本来多长还是多长，
    所以「截断」这个动作从来没真的解决过问题，只是让数看起来正常了。

    ## 现在的规矩

    **一句都不许往回挪，一句都不许压住上一句。** 放不下就往后顺延，
    顺延到下一格、下下格都行 —— 台词压过镜头切换在电影里是常态
    （这叫 sound bridge），而两句人声叠在一起说话是事故。

    代价是「这一句会比它自己那格晚一点响」。为了不让它悄悄晚到观众
    觉得错位，晚超过 `让位上限` 就报出来看一眼。
    """
    按格 = {}
    for t in 条们:
        按格.setdefault(t["格"], []).append(t)

    轴 = []
    上一句止 = 0.0
    让位上限 = 每格秒 * 1.5
    晚多 = []

    for 格 in sorted(按格):
        组 = 按格[格]
        格顶 = 头偏 + (格 - 1) * 步长
        for i, t in enumerate(组):
            时 = t.get("秒") or 0.0
            # 最早只能从自己这格的头 0.30 秒之后开始
            最早 = 格顶 + 0.30
            起 = 最早 if not 轴 else max(最早, 上一句止 + 0.20)
            让 = 起 - 最早
            if 让 > 0.001:
                t["让位"] = round(让, 3)
            if 让 > 让位上限:
                晚多.append((格, t["台词"][:12], 让))
            t["起"] = round(起, 3)
            t["放"] = round(时, 3)          # 字幕长度 = 音频长度，不砍
            轴.append(t)
            上一句止 = 起 + 时
    if 晚多:
        报(f"  ⚠ {len(晚多)} 句被顺延超过 {让位上限:.2f}s（台词比画面晚，看一眼）：")
        for 格, 词, 让 in 晚多[:6]:
            报(f"      格{格} 晚 {让:.2f}s　「{词}…」")
    return 轴


def 写SRT(轴, 路):
    def 时码(s):
        h = int(s // 3600); m = int(s % 3600 // 60); ss = s % 60
        return f"{h:02d}:{m:02d}:{ss:06.3f}".replace(".", ",")

    行 = []
    for i, t in enumerate(轴, 1):
        起, 止 = t["起"], t["起"] + t["放"]
        行.append(f"{i}\n{时码(起)} --> {时码(止)}\n{t['台词']}\n")
    io.open(路, "w", encoding="utf-8").write("\n".join(行))
    return 路


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--只排", action="store_true", help="音频都在，只重排轴和 SRT")
    ap.add_argument("--干跑", action="store_true", help="只解析台词表")
    ap.add_argument("--头", type=float, default=4.0, help="片头卡秒数（默认 4.0）")
    ap.add_argument("--语速", type=float, default=1.0)
    ap.add_argument("--限", type=int, default=0, help="只做前 N 句（调试用）")
    参 = ap.parse_args()

    报 = lambda s: print(s, flush=True)
    报("═" * 62)
    报("《觉醒》配音")
    报("═" * 62)

    条们 = 读台词(报)
    if 参.限:
        条们 = 条们[:参.限]
        报(f"  ⚠ --限 {参.限}：只做前 {len(条们)} 句")
    if 参.干跑:
        for t in 条们[:8]:
            报(f"    格{t['格']:>2}　{t['角色']:<6}　{t['情感']:<10}　{t['台词']}")
        报(f"    … 共 {len(条们)} 句")
        return 0

    os.makedirs(出夹, exist_ok=True)

    # ── 合成 ──────────────────────────────────────────────
    if not 参.只排:
        if not 配音.在线().get("在线"):
            报("✗ ComfyUI 不在线，先起它")
            return 1
        好 = 坏 = 0
        for i, t in enumerate(条们, 1):
            存 = os.path.join(出夹, f"{i:03d}_格{t['格']:02d}_{t['角色']}.wav")
            t["路"] = 存
            if os.path.exists(存) and os.path.getsize(存) > 2000:
                秒 = 配音._探秒(存)
                if 秒 and 秒 > 0.3:
                    t["秒"] = 秒
                    好 += 1
                    报(f"  [{i:>2}/{len(条们)}] 复用 {os.path.basename(存)}  {秒:.2f}s")
                    continue
            音 = 音色路径(t["角色"])
            报(f"  [{i:>2}/{len(条们)}] 格{t['格']:>2} {t['角色']:<5} {t['情感']:<10} "
                f"「{t['台词']}」")
            try:
                果 = 配音.合成(t["台词"], 音, 情感=t["情感"], 语速=参.语速,
                               存到=存, 报=None)
                t["秒"] = 果["秒"] or 配音.估时长(t["台词"])
                好 += 1
                报(f"        ✓ {t['秒']:.2f}s  {os.path.getsize(存)/1024:.0f} KB"
                   f"  {果.get('耗时', '?')}s")
                for p in (果.get("提示") or [])[:1]:
                    报(f"        {p}")
            except Exception as e:  # noqa: BLE001
                t["秒"] = 配音.估时长(t["台词"])
                坏 += 1
                报(f"        ✗ {e}")
        报(f"\n  合成：成功 {好}　失败 {坏}")
        if 坏:
            报("  失败的不排轴，先修完再跑 --只排")
    else:
        for i, t in enumerate(条们, 1):
            存 = os.path.join(出夹, f"{i:03d}_格{t['格']:02d}_{t['角色']}.wav")
            t["路"] = 存
            t["秒"] = 配音._探秒(存) if os.path.exists(存) else 0.0
        报(f"  复用 {sum(1 for t in 条们 if t['秒'])}/{len(条们)} 句音频")

    # ── 排轴 ─────────────────────────────────────────────
    轴 = 排轴(条们, 参.头, 报)
    晚 = [t for t in 轴 if t.get("让位")]

    末 = max(t["起"] + t["放"] for t in 轴)
    报(f"\n  时间轴：第一句 {轴[0]['起']:.2f}s　最后一句止于 {末:.2f}s")

    # 重叠检查：**全片任意两句都不许压在一起**（不只看同格）
    #   第一版只查「同格内」，而顺延本来就会让台词跨到下一格里去 ——
    #   只查同格等于放过了真正会出事的那一类。
    冲 = []
    for a, b in zip(轴, 轴[1:]):
        if a["起"] + a["放"] > b["起"] + 0.001:
            冲.append((a["格"], b["格"], round(a["起"] + a["放"] - b["起"], 3)))
    if 冲:
        报(f"  ✗ {len(冲)} 处人声重叠（任意两句）")
        for 格a, 格b, 越 in 冲[:6]:
            报(f"      格{格a} → 格{格b}　压了 {越}s")
    else:
        报(f"  ✓ 全片 {len(轴)} 句零重叠")

    路 = 写SRT(轴, os.path.join(出夹, "台词.srt"))
    报(f"  ✓ SRT → {os.path.relpath(路, 根)}")

    # 落一份轴表给 _配片.py 用
    轴路 = os.path.join(出夹, "_轴.json")
    json.dump({"头偏": 参.头, "每格秒": 每格秒, "步长": 步长,
               "轴": [{k: t[k] for k in ("格", "角色", "台词", "情感", "起", "放", "路")
                       if k in t} for t in 轴]},
              io.open(轴路, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    报(f"  ✓ 轴表 → {os.path.relpath(轴路, 根)}")
    return 0 if not 冲 else 1

if __name__ == "__main__":
    sys.exit(main())
