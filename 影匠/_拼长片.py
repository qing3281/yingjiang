# -*- coding: utf-8 -*-
"""把长片的段拼成一个 mp4（双线：本机 + 远端出的段混着收）。

段命名 `段\格N_本机.mp4` / `段\格N_远端.mp4`。**两个来源都要数**——
只认 `格N.mp4` 会把另一条线出的格整格漏掉（在短片上踩过：以为 9 段齐了，
其实少 3 段，接出来的片子短了 8 秒还不报错）。

用法：
    python _拼长片.py 雪线                  # 交叉溶解 0.5 秒
    python _拼长片.py 雪线 --转场 硬切
    python _拼长片.py 雪线 --每段秒 4.56 --转场吃 0.5
"""
import argparse
import importlib.util
import os
import shutil
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

# 中文模块名 importlib 能认，但直接 import 更省事；引擎/导演 这些是本地模块
spec = importlib.util.spec_from_file_location("视频", os.path.join(根, "视频.py"))
视频 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(视频)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--转场", default="交叉溶解")
    ap.add_argument("--每段秒", type=float, default=4.56)
    ap.add_argument("--转场吃", type=float, default=0.5)
    ap.add_argument("--片名", default="")
    ap.add_argument("--只收", action="store_true", help="只把段规整到 片\\ 下，不接")
    参 = ap.parse_args()

    def 报(s):
        print(s, flush=True)

    段目录 = os.path.join(根, "作品", 参.戏, "段")
    片目录 = os.path.join(根, "作品", 参.戏, "片")
    if not os.path.isdir(段目录):
        报(f"✗ 没有 {段目录}")
        return 1
    os.makedirs(片目录, exist_ok=True)

    # 两个来源都收：格N_本机.mp4 / 格N_远端.mp4（以后可能还有 _云）
    找到 = {}     # 格号 -> (来源, 路径)
    for f in sorted(os.listdir(段目录)):
        if not f.endswith(".mp4"):
            continue
        try:
            号 = int(f.split("_")[0].replace("格", ""))
        except ValueError:
            continue
        来源 = "远端" if "_远端" in f else ("本机" if "_本机" in f else "?")
        路 = os.path.join(段目录, f)
        # 同一格两条线都出了就挑文件大的（码率高，细节多）
        if 号 not in 找到 or os.path.getsize(路) > os.path.getsize(找到[号][1]):
            找到[号] = (来源, 路)

    缺 = [n for n in range(1, max(找到) + 1) if n not in 找到] if 找到 else []
    本 = sum(1 for v in 找到.values() if v[0] == "本机")
    远 = sum(1 for v in 找到.values() if v[0] == "远端")
    报(f"段目录：{len(找到)} 格（本机 {本} / 远端 {远}）"
       + (f"　缺 {缺}" if 缺 else "　一格不缺"))

    清单 = []
    for 号 in sorted(找到):
        s = 视频.探视频(找到[号][1])
        报(f"  {号:02d}  {找到[号][0]}  {s['秒']:.2f}s  {s['宽']}×{s['高']} @{s['帧率']:g}fps")
        目 = os.path.join(片目录, f"格{号}.mp4")
        if os.path.abspath(目) != os.path.abspath(找到[号][1]):
            shutil.copyfile(找到[号][1], 目)
        清单.append(目)

    总 = len(清单) * 参.每段秒 - (len(清单) - 1) * 参.转场吃
    报(f"\n预计成片 {总:.2f} 秒 = {int(总 // 60)} 分 {总 % 60:.1f} 秒")

    if 参.只收:
        return 0

    片名 = 参.片名 or f"《{参.戏}》成片.mp4"
    出 = os.path.join(片目录, 片名)
    接 = 视频.接片(片子们=清单, 转场=参.转场, 每段=参.转场吃, 存到=出, 报=报)
    if not 接:
        报("✗ 接片没返回")
        return 1
    报(f"\n✓ 成片：{出}")
    报(f"  {os.path.getsize(出)/1048576:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
