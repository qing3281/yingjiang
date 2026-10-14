# -*- coding: utf-8 -*-
"""出片 v2：多角色长片流水线（图 → 段 → 接 → 配音 → 烧字幕）。

和 `_出长片.py` 的区别（那个是《雪线》的单角色版，只有一个凌霜）：

1. **多角色**。每格从 md 里读 `**人物**：沈砚、裴照`，把在场角色的外貌串拼起来喂给
   `导演.开镜`。不在场的角色**一个词都不出现** —— 多写一个名字，模型就会在画面里
   多画一个人。
2. **种子按「第一在场角色」定**。`导演.开镜` 内部取 `角色[0]` 的种子，所以同一格
   里谁排第一会影响脸。md 里的人物顺序就是优先级，别乱改顺序。
3. **远景不喂锚点**（继承 `_出长片.py` 的实测结论，见下面 `出首帧` 的注释）。
4. **一条命令跑到底**：`--全 --烧字幕` 出完图、出完段、接片、烧字幕。

用法：
    python _出片.py 刀鞘 --图                    # 只出首帧
    python _出片.py 刀鞘 --段 --端点 远端          # 这一段走远端算力
    python _出片.py 刀鞘 --全 --烧字幕
    python _出片.py 刀鞘 --图 --只格 1,2,3
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 导演          # noqa: E402
import 引擎          # noqa: E402
import 角色库        # noqa: E402

种子 = 1735946766
首帧种子偏移 = 0        # `--种子偏移` 加在这上头。★ 首帧的构图就是被这个种子定的，
                        #   换构图（而不只是换运镜）必须换它 —— 2026-10-14 格56
                        #   连着六个视频种子都往画面下缘画字幕，就是因为首帧没换。
宽, 高 = 1344, 768
帧数 = 73               # 73 帧 @16fps = 4.56 秒
转场 = "交叉溶解"
每段转场 = 0.5
远端景别 = ("extreme wide shot", "wide shot", "establishing shot")


def 读格(md路):
    """从 02-九宫格.md 里抠每格。多一个『人物』字段（多人用『、』或『,』分隔）。"""
    文 = open(md路, encoding="utf-8").read()
    块 = re.split(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$", 文, flags=re.M)

    def 取(体, 键):
        m = re.search(rf"^-\s*\*{{0,2}}{键}\*{{0,2}}\s*[:：]\s*(.*)$", 体, flags=re.M)
        return m.group(1).strip() if m else ""

    格 = []
    for i in range(1, len(块), 3):
        体 = 块[i + 2] if i + 2 < len(块) else ""
        人 = 取(体, "人物")
        名单 = [x.strip() for x in re.split(r"[、,，/|]", 人) if x.strip()]
        格.append({
            "号": int(块[i]),
            "标题": 块[i + 1],
            "人物": 名单,
            "景别": 取(体, "景别"),
            "机位": 取(体, "机位"),
            "提示词": 取(体, "提示词"),
            "重点": 取(体, "重点"),
            "光色": 取(体, "光色"),
            "动作": 取(体, "动作"),
        })
    return 格


def 出首帧(戏, 格, 报):
    """一格 → 一张 1344x768 首帧。返回路径。

    四条实测出来的写法（每一条都是踩过坑才写的）：

    1. **景别必须放最前**。原来把角色锚点放句首，模型直接被拽去画肖像，
       后面写死 `extreme wide shot` 也没用。景别先框住，再写字。
    2. **远景/极远景一个锚点都不喂**，连 `开镜` 内部那份也要断掉（传 `角色=[]`）。
       实测三版：全锚点在句首 → 大特写；短锚点「a single lone figure」→
       一个大的加一个小的（**变成两个人**）；锚点不写但 `角色` 照给 → 还是大特写，
       因为 `开镜` 自己会把人拼回去。人物描写交给提示词自己带。
    3. **光色字段要进提示词**。它是分镜里唯一能控制「这场戏什么颜色」的东西，
       不写进去模型就按自己的默认来，全片会糊成一个色调。
    4. **md 没有『人物：』字段时，一律不喂锚点。** 《磨刀》的分镜把每个在场角色的
       完整锚点**直接写进提示词了**（「……蹲着一个三十岁上下的男人：黑发在脑后束成
       一条低马尾，用一根削得极短的竹签别住；……」），而且只写在场的、不在场的一个
       字不提。这时候再喂一次 `角色=` 就是**把锚点拼两遍**，模型收到两段一模一样的人
       物描述，会倾向于画两个人。所以有『人物：』字段才走锚点，没有就信提示词。
    """
    景 = (格["景别"] or "medium shot").strip()
    远 = 景 in 远端景别
    光 = 格.get("光色", "")
    尾 = "，".join(x for x in (光, "电影写实，胶片颗粒，硬光长阴影") if x)
    词 = f"{景}。{格['提示词']}，{尾}"

    自足 = not 格["人物"]          # 提示词自己带了人物描写
    缺 = []
    if 远 or 自足:
        在 = []
    else:
        在 = [n for n in 格["人物"] if 角色库.取(n)]
        缺 = [n for n in 格["人物"] if not 角色库.取(n)]
    if 缺:
        报(f"    ⚠ 角色库里没有：{'、'.join(缺)}")

    t = time.time()
    r = 导演.开镜(词, 风格="cinematic-real", 角色=在, 种子=种子 + 首帧种子偏移,
                  宽=宽, 高=高, 文件名=f"01_格{格['号']}", 用定妆照=False)
    路 = r.get("路", "")
    注 = "[远景·不喂锚点]" if 远 else ("[提示词自带锚点]" if 自足 else "+".join(在))
    报(f"    ✓ 图 {os.path.basename(路)}  {time.time()-t:.1f} 秒　{注}")
    return 路


def 出段(戏, 格, 图路, 端点, 报):
    """一张首帧 → 一段视频。落点 `段\\格N_<端点>.mp4`。

    两台机器都出同一格时，`让镜动` 的默认落盘名 `<图名>.mp4` 会撞名互删
    （第一版真删过用户三段片）。所以出完立刻改名搬走。
    """
    目录 = os.path.join(根, "作品", 戏)
    段目录 = os.path.join(目录, "段")
    os.makedirs(段目录, exist_ok=True)

    旧 = os.path.join(目录, f"{os.path.splitext(os.path.basename(图路))[0]}.mp4")
    旧备份 = None
    if os.path.exists(旧):
        旧备份 = os.path.join(段目录, f"_临时旧_{os.path.basename(旧)}")
        shutil.copyfile(旧, 旧备份)

    t = time.time()
    果 = 导演.让镜动({"路": 图路, "种子": 种子}, 格["动作"],
                      帧数=帧数, 帧宽=宽, 帧高=高, 报=报)
    落点 = os.path.join(段目录, f"格{格['号']}_{端点}.mp4")
    shutil.move(果["路"], 落点)
    if 旧备份:
        shutil.move(旧备份, 旧)
    报(f"    ✓ 段 {os.path.basename(落点)}  {time.time()-t:.1f} 秒 "
       f"{os.path.getsize(落点)/1024/1024:.2f} MB")
    return 落点


def 接片(戏, 号表, 报):
    目录 = os.path.join(根, "作品", 戏)
    段目录 = os.path.join(目录, "段")
    清单, 用了 = [], {"本机": 0, "远端": 0}
    for 号 in 号表:
        for 端 in ("本机", "远端"):
            p = os.path.join(段目录, f"格{号}_{端}.mp4")
            if os.path.exists(p):
                清单.append(p)
                用了[端] += 1
                break
        else:
            报(f"  ⚠ 格{号} 没有段，跳过")

    if not 清单:
        报("  ✗ 一段都没有")
        return None

    出 = os.path.join(目录, f"《{戏}》成片.mp4")
    报(f"  接 {len(清单)} 段（本机 {用了['本机']} · 远端 {用了['远端']}）")
    import 视频
    r = 视频.接片(片子们=清单, 转场=转场, 每段=每段转场, 存到=出, 报=报)
    if r and os.path.exists(出):
        秒 = 探时长(出)
        报(f"  ✓ 成片 {os.path.basename(出)}  {秒:.2f} 秒  "
            f"{os.path.getsize(出)/1048576:.2f} MB")
        return 出
    return None


def 探时长(路):
    ff = os.path.join(根, "_bin", "ffmpeg.exe")
    if not os.path.exists(ff):
        ff = "ffmpeg"
    try:
        r = subprocess.run([ff, "-i", 路, "-hide_banner"],
                           capture_output=True, text=True, errors="replace")
        m = re.search(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d{1,3})", r.stderr or "")
        if m:
            h, mi, s, ms = m.groups()
            return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--图", action="store_true")
    ap.add_argument("--段", action="store_true")
    ap.add_argument("--拼", action="store_true")
    ap.add_argument("--全", action="store_true")
    ap.add_argument("--只格", default="")
    ap.add_argument("--端点", default="本机", choices=["本机", "远端"])
    ap.add_argument("--跳过已有", action="store_true")
    ap.add_argument("--种子偏移", type=int, default=0,
                    help="首帧种子偏移。换首帧的**构图**用这个（0.5 秒视频种子换不掉构图）")
    参 = ap.parse_args()

    global 首帧种子偏移
    首帧种子偏移 = 参.种子偏移
    if 首帧种子偏移:
        print(f"  ★ 首帧种子偏移 {首帧种子偏移:+d}　实际种子 {种子 + 首帧种子偏移}")

    戏 = 参.戏
    目录 = os.path.join(根, "作品", 戏)
    md路 = os.path.join(目录, "02-九宫格.md")
    if not os.path.exists(md路):
        print(f"✗ 找不到 {md路}")
        return 1

    def 报(s):
        print(s, flush=True)

    格表 = 读格(md路)
    if not 格表:
        print(f"✗ {md路} 里一格都没读到")
        return 1
    号表 = [g["号"] for g in 格表]
    只要 = {int(x) for x in 参.只格.replace("，", ",").split(",") if x.strip()} if 参.只格 else set()
    要跑 = [g for g in 格表 if not 只要 or g["号"] in 只要]

    # 全片登场的角色（顺序 = md 里第一次出现的顺序）
    全体 = []
    for g in 格表:
        for n in g["人物"]:
            if n not in 全体:
                全体.append(n)
    有卡 = [n for n in 全体 if 角色库.取(n)]
    if 全体 and not 有卡:
        print(f"✗ md 写了『人物：』但角色库里一个都没有：{全体}")
        return 1
    导演.立戏(戏, 默认风格="cinematic-real", 默认角色=有卡)

    报(f"《{戏}》 {len(格表)} 格 · 本次跑 {len(要跑)} 格 · {宽}×{高} · {帧数} 帧/格")
    if 有卡:
        报(f"角色 {len(有卡)} 个：{'、'.join(有卡)}")
    空 = [g["号"] for g in 格表 if not g["人物"]]
    if 空 and len(空) == len(格表):
        报("这份分镜没有『人物：』字段 —— 按规矩**不喂角色锚点**，"
           "在场人物的完整描写由提示词自己带（磨刀就是这样）。")
    elif 空:
        报(f"⚠ 这些格没写『人物：』字段：{空}　（会当成空镜，不喂锚点）")

    do图 = 参.图 or 参.全
    do段 = 参.段 or 参.全
    do拼 = 参.拼 or 参.全

    if do段 or do拼:
        引擎.换端点(参.端点)
        在 = 引擎.在线()
        报(f"端点 {在.get('端点')}  在线 {在.get('在线')}  {在.get('显卡','')}")
        if not 在.get("在线"):
            print("✗ 端点不在线")
            return 1

    成 = 败 = 0
    for g in 要跑:
        号 = g["号"]
        图路 = os.path.join(目录, f"01_格{号}.png")
        报(f"\n  格{号} —— {g['标题']}"
           f"{'　[' + '、'.join(g['人物']) + ']' if g['人物'] else ''}")
        if do图:
            if not g["提示词"]:
                报("    ✗ md 里没有提示词")
                败 += 1
                continue
            try:
                图路 = 出首帧(戏, g, 报)
                成 += 1
            except Exception as e:  # noqa: BLE001
                报(f"    ✗ {type(e).__name__}: {e}")
                败 += 1
                continue

        if do段:
            端名 = 参.端点
            落点 = os.path.join(目录, "段", f"格{号}_{端名}.mp4")
            if 参.跳过已有 and os.path.exists(落点):
                报("    已有段，跳过")
                continue
            if not os.path.exists(图路):
                报(f"    ✗ 没有首帧图 {os.path.basename(图路)}")
                败 += 1
                continue
            if not g["动作"]:
                报("    ✗ md 里没有『动作：』字段，图生视频没法动")
                败 += 1
                continue
            try:
                出段(戏, g, 图路, 端名, 报)
                成 += 1
            except Exception as e:  # noqa: BLE001
                报(f"    ✗ {type(e).__name__}: {e}")
                败 += 1

    if do拼:
        报("")
        接片(戏, 号表, 报)

    报(f"\n▶ 收工：成功 {成}　失败 {败}")
    return 0 if 败 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
