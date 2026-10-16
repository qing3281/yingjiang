# -*- coding: utf-8 -*-
"""双线成片 —— 本机与远端各出一部分镜头，拼成同一条片。

    python _双线成片.py 试镜                 默认：格1/5/8 用远端，其余用本机
    python _双线成片.py 试镜 --远端格 1,5,8    指定哪几格走远端
    python _双线成片.py 试镜 --全部本机        对照：九格全本机

产物：
    作品\\<戏>\\片\\_成片_双线.mp4        无声
    作品\\<戏>\\片\\_成片_双线_有声.mp4   带台词与底噪

为什么要有这个脚本：
    用户要的是「用你自己的平台出的图，两条线一起」。
    九格图是本机出的；九段视频里挑几段真的派给远端 DESKTOP-776BJTA 出，
    合起来才叫两条线，不是「远端待命、本机全包」。
"""
import argparse
import os
import shutil
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 视频  # noqa: E402

FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")
缺省远端格 = [1, 5, 8]
每段转场 = 0.5
转场 = "交叉溶解"


def 问时长(路):
    import re
    r = subprocess.run([FFMPEG, "-i", 路], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--远端格", default="")
    ap.add_argument("--全部本机", action="store_true")
    ap.add_argument("--只拼", action="store_true", help="片段已备好，只重新拼接")
    参 = ap.parse_args()

    def 报(s):
        print(s, flush=True)

    戏目录 = os.path.join(根, "作品", 参.戏)
    片目录 = os.path.join(戏目录, "片")
    os.makedirs(片目录, exist_ok=True)

    远端格 = [] if 参.全部本机 else (
        [int(x) for x in 参.远端格.replace("，", ",").split(",") if x.strip().isdigit()]
        or 缺省远端格)

    # 九格号要从两个来源合起来数 —— 远端那几段的本地名会被 _远端出片.py
    # 改成 _远端_格N.mp4（它 os.replace 走了 让镜动 原本写的 01_格N.mp4），
    # 只认 01_格N.mp4 会把远端出过的格整格漏掉。这个坑犯过一次。
    号集 = set()
    for f in os.listdir(戏目录):
        if not f.endswith(".mp4"):
            continue
        if f.startswith("01_格"):
            号集.add(int(f[4:-4]))
        elif f.startswith("_远端_格"):
            号集.add(int(f[5:-4]))
    格号们 = sorted(号集)
    if not 格号们:
        报(f"✗ {戏目录} 里既没有 01_格N.mp4 也没有 _远端_格N.mp4")
        return 2

    报(f"共 {len(格号们)} 段 · 远端出 {远端格}")
    选 = {}
    for n in 格号们:
        远 = os.path.join(戏目录, f"_远端_格{n}.mp4")
        本 = os.path.join(戏目录, f"01_格{n}.mp4")
        if n in 远端格 and os.path.exists(远):
            选[n] = (远, "远端")
        elif os.path.exists(本):
            选[n] = (本, "本机")
        elif os.path.exists(远):
            选[n] = (远, "远端")
        else:
            报(f"  ✗ 格{n} 两边都没有段")
            return 2

    if not 参.只拼:
        # 统一拷成 片\格N.mp4，让 视频.接片 按顺序吃
        for n, (路, 源) in 选.items():
            目标 = os.path.join(片目录, f"格{n}.mp4")
            shutil.copyfile(路, 目标)
            报(f"  格{n}  ← {源}  {问时长(路):.2f}s  {os.path.getsize(目标)/1024:.0f} KB")

    清单 = os.path.join(片目录, "_concat_双线.txt")
    with open(清单, "w", encoding="utf-8") as f:
        for n in sorted(选):
            f.write(os.path.join(片目录, f"格{n}.mp4") + "\n")

    出 = os.path.join(片目录, "_成片_双线.mp4")
    if os.path.exists(出):
        os.remove(出)
    报(f"\n══ 拼接（{转场} {每段转场}s）══")
    try:
        r = 视频.接片(清单路=清单, 转场=转场, 每段=每段转场, 存到=出)
        if not (r and os.path.exists(出)):
            raise RuntimeError("接片没出片")
    except Exception as e:
        报(f"  ⚠ 接片炸了（{type(e).__name__}: {e}），退回硬切")
        r = subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                            "-i", 清单, "-c", "copy", 出],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0 or not os.path.exists(出):
            报(f"  ✗ 硬切也失败：{(r.stderr or '')[-300:]}")
            return 1

    本机数 = sum(1 for _, s in 选.values() if s == "本机")
    远端数 = len(选) - 本机数
    报(f"\n✓ 双线成片：{出}")
    报(f"  {问时长(出):.2f} 秒  {os.path.getsize(出)/1048576:.2f} MB")
    报(f"  本机 {本机数} 段 · 远端 {远端数} 段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
