# -*- coding: utf-8 -*-
"""质量闸：量每一小段「走得够不够」，不够的重摇一次，只留更好的那一版。

为什么要有这道闸（量出来的事实）：
  I2VA 治好了「段内瞬移」，代价是它**只保证起点、终点没人管**。
  12 段里「走了几成」的中位是 89%，但 格3_1 只有 9% —— 那 2.33 秒等于一张定帧。
  这种事机器不报错、成片也不报错，只有人看的时候才骂「一帧一帧跟图片一样」。

判据（每一段一个数）：
  走了几成 = MAE(片尾帧, 片首帧) ÷ MAE(这一段的起点关键帧, 它该走到的目标关键帧)
  1.0 = 真走到了；< 0.40 = 几乎没动就交差。

用法：
  python _查子镜质量.py                 只看，不改
  python _查子镜质量.py --重摇           把不合格的挪走 → 重出 → 两版都量 → 只留更好的
  python _查子镜质量.py --阈值 0.5
  python _查子镜质量.py --限 12          只量前 N 段
"""
import sys
import os
import glob
import json
import shutil
import subprocess
import importlib.util

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
子镜目 = os.path.join(目, "子镜")
挪走目 = os.path.join(子镜目, "_重摇前")
出子镜 = r"D:\DSHworkspace\影匠\_出子镜.py"
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

_s = importlib.util.spec_from_file_location("_ldmd", r"D:\DSHworkspace\工具\_量动没动.py")
L = importlib.util.module_from_spec(_s)
_s.loader.exec_module(L)


def 量一段(路, 号, 段):
    首, 末, n = L.首末帧(路)
    if 首 is None:
        return None, None, 0
    走 = L.差(首, 末)
    a, b = L.关键帧路(号, 段)
    距 = L.差(L.读图(a), L.读图(b)) if a else None
    if 走 is None or not 距:
        return 走, 距, n
    return 走, 距, n


def 全量(限=0):
    文件们 = sorted(glob.glob(os.path.join(子镜目, "格*_*.mp4")))
    行们 = []
    for p in 文件们:
        b = os.path.basename(p)
        try:
            号 = int(b.split("_")[0][1:])
            段 = int(b.split("_")[1].split(".")[0])
        except Exception:
            continue
        走, 距, n = 量一段(p, 号, 段)
        成 = (走 / 距) if (走 is not None and 距) else None
        行们.append({"路": p, "名": b, "号": 号, "段": 段, "帧": n,
                     "走": 走, "距": 距, "成": 成})
        if 限 and len(行们) >= 限:
            break
    return 行们


def 主():
    阈值 = 0.40
    重摇 = False
    限 = 0
    a = sys.argv[1:]
    for i, x in enumerate(a):
        if x == "--重摇":
            重摇 = True
        elif x == "--阈值" and i + 1 < len(a):
            阈值 = float(a[i + 1])
        elif x == "--限" and i + 1 < len(a):
            限 = int(a[i + 1])

    行们 = 全量(限)
    if not 行们:
        print("✗ 子镜目录里一段都没有：%s" % 子镜目)
        return 1

    print("═" * 74)
    print("子镜质量　共 %d 段　阈值 走了几成 >= %.2f" % (len(行们), 阈值))
    print("═" * 74)

    坏 = []
    for r in 行们:
        r["坏"] = (r["成"] is not None and r["成"] < 阈值)
        if r["成"] is None:
            r["坏"] = True
        if r["坏"]:
            坏.append(r)
    for r in 行们:
        print("  %-11s %4d 帧　走 %6s　该走 %6s　成 %6s %s"
              % (r["名"], r["帧"],
                 "%.1f" % r["走"] if r["走"] is not None else "-",
                 "%.1f" % r["距"] if r["距"] is not None else "-",
                 "%.0f%%" % (r["成"] * 100) if r["成"] is not None else "-",
                 "  ★ 重摇" if r["坏"] else ""))

    成们 = [r["成"] for r in 行们 if r["成"] is not None]
    if 成们:
        import statistics
        成们 = sorted(成们)
        print("\n走了几成　中位 %.0f%%　最小 %.0f%%　最大 %.0f%%　不合格 %d/%d"
              % (statistics.median(成们) * 100, 成们[0] * 100, 成们[-1] * 100,
                 len(坏), len(行们)))

    if not 重摇:
        print("\n（只看。要重摇加 --重摇）")
        return 0 if not 坏 else 1

    if not 坏:
        print("\n✓ 全过，不用重摇")
        return 0

    os.makedirs(挪走目, exist_ok=True)
    旧成 = {}
    for r in 坏:
        到 = os.path.join(挪走目, r["名"])
        shutil.move(r["路"], 到)
        r["旧路"] = 到
        旧成[r["名"]] = r["成"]
        print("  → 挪走 %s（成 %s）" % (r["名"], r["成"]))

    只镜 = ",".join("%d-%d" % (r["号"], r["段"]) for r in 坏)
    print("\n── 重摇 %d 段（种子 +777，端点 本机，不加 --跳过已有）──" % len(坏))
    命令 = [PY, "-X", "utf8", 出子镜, "楚子航", "--只镜", 只镜,
            "--端点", "本机", "--全无末帧", "--种子偏移", "777"]
    print("   " + " ".join(命令))
    子 = subprocess.run(命令)
    print("   重摇退出码 %d" % 子.returncode)

    留 = 0
    扔 = 0
    for r in 坏:
        新路 = r["路"]
        if not os.path.isfile(新路):
            shutil.move(r["旧路"], 新路)
            print("  %s 重摇没出东西 → 旧版放回" % r["名"])
            continue
        走, 距, n = 量一段(新路, r["号"], r["段"])
        新 = (走 / 距) if (走 is not None and 距) else None
        if 新 is not None and (r["成"] is None or 新 > r["成"]):
            print("  %s  %s → %s  ✓ 留新版" % (r["名"],
                  "%.0f%%" % (r["成"] * 100) if r["成"] is not None else "-",
                  "%.0f%%" % (新 * 100)))
            留 += 1
        else:
            os.remove(新路)
            shutil.move(r["旧路"], 新路)
            print("  %s  %s → %s  ✗ 新版没更好，旧版放回" % (r["名"],
                  "%.0f%%" % (r["成"] * 100) if r["成"] is not None else "-",
                  "%.0f%%" % (新 * 100) if 新 is not None else "-"))
            扔 += 1
    print("\n重摇结果：留新版 %d　留旧版 %d" % (留, 扔))

    最后 = 全量(0)
    print("重摇后：")
    for r in 最后:
        if r["名"] in 旧成:
            print("  %-11s %s → %s" % (r["名"],
                  "%.0f%%" % (旧成[r["名"]] * 100) if 旧成[r["名"]] is not None else "-",
                  "%.0f%%" % (r["成"] * 100) if r["成"] is not None else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(主())
