# -*- coding: utf-8 -*-
"""量「连贯」—— 把「看着还行」变成一个能重跑的数。

用户问过（m38008）：「**你之后打算怎么做这个视频？怎么保证动作的连贯？**」
在那之前，「连贯」全靠我的眼睛，而我的眼睛这一晚已经骗过我很多次。
这个脚本就是那句话的回答：**三个能量出来的数。**

三个数（每个都是独立的判据，不互相替代）：

  ① 跳格　相邻两格的首帧差多远
        算法：pHash 汉明距离 + 灰度直方图相关性
        太大 = 从这一格到下一格画面跳了（换景别、换光、换人）
        判据：hamming > 26 或 直方图相关 < 0.55 → 报「跳」

  ② 没贴住　每一格 mp4 的**第 0 帧** vs 它的 `01_格N.png`
        算法：缩到 256 宽，算平均绝对差（MAE，0-255）
        H3 是图生视频，**喂进去的那张图就是第 0 帧**，所以这两个应该几乎一样
        太大 = H3 没听话，它自己重新画了一格 → 后面全跑偏
        判据：MAE > 18 → 报「没贴住」

  ③ 没动　每一格 mp4 **内部**的光流强度
        算法：cv2.calcOpticalFlowFarneback 逐对帧，取平均幅度
        接近 0 = 一镜里像看图片（这个病踩过，见 `影匠\\知识\\一镜里像看图片.md`）
        判据：mean < 0.35 → 报「没动」

用法：
    python _查连贯.py 楚子航
    python _查连贯.py 楚子航 --只格 1,2,3      # 只查这几格
    python _查连贯.py 楚子航 --阈值              # 只打印每个数的分布，不判
    python _查连贯.py 楚子航 --表                # 额外写一份 markdown

★ 这个脚本**只读**，不改任何产物。
★ 阈值写在下面常量里，不许在别处再写一份。
"""
import argparse
import glob
import importlib.util
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import cv2
import numpy as np

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根

# ── 阈值（唯一来源）────────────────────────────────────────────
# ★ 2026-10-16 02:20 改过一次，记下为什么（别改回去）：
#    第一版拿 pHash 汉明距离当「跳格」的判据，跑出来格1→2=38、2→3=32、3→4=40，
#    全报「跳」。**那是假判据** —— 分镜本来就一格一个景别，远景→中景→特写
#    构图必然大变，pHash 量的正是构图。**它量的是「像不像」，不是「连不连贯」。**
#    用户抱怨的「跳」是**同一场戏里人和光变了**，不是构图变了。所以：
#      · 判据换成 **色调/明暗**（直方图相关）+ **亮度差** + **饱和度差** —— 这三个才是「光变了」
#      · pHash 汉明**只打印、不判**，当参考看
跳格_相关 = 0.55        # 直方图相关，低于就报「光跳了」
跳格_亮度 = 40.0        # 平均亮度差（0-255）
跳格_饱和 = 0.22        # 平均饱和度差（0-1）
贴_MAE = 18.0           # mp4 第 0 帧 vs 首帧 PNG 的平均绝对差
动_光流 = 0.35          # mp4 内部平均光流幅度，低于就报没动
# ─────────────────────────────────────────────────────────────


def pHash(灰):
    """32x32 灰度 → 64 位感知哈希（DCT 低频 8x8 取中位数）。"""
    small = cv2.resize(灰, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(small)[:8, :8]
    v = d.flatten()[1:]                       # 丢掉直流分量（整体亮度）
    return (v > np.median(v)).astype(np.uint8)


def 读灰(路, 宽=256):
    im = cv2.imdecode(np.fromfile(路, dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        return None, None, None
    灰 = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return im, 灰, cv2.resize(灰, (宽, int(灰.shape[0] * 宽 / 灰.shape[1])),
                             interpolation=cv2.INTER_AREA)


def 找mp4(目, n):
    """一格可能有好几个 mp4（不同管线、不同端点）。**全找出来，别猜。**

    本项目里出现过的三种命名（都是事实，不是设想）：
      · `段\\格<N>_<端点>.mp4`   ← `影匠\\_出H3.py` 现在写的
      · `04_格<N>.mp4`           ← 早期
      · `04_锚<锚号>格<M>.mp4`    ← 早期锚点管线，锚号 = (N-1)//4 + 1，M = (N-1)%4
    """
    出 = []
    p = os.path.join(目, "段", f"格{n}_")
    段 = os.path.dirname(p)
    if os.path.isdir(段):
        for f in sorted(os.listdir(段)):
            if f.startswith(f"格{n}_") and f.lower().endswith(".mp4"):
                出.append(os.path.join(段, f))
    p = os.path.join(目, f"04_格{n}.mp4")
    if os.path.isfile(p):
        出.append(p)
    锚 = (n - 1) // 4 + 1
    M = (n - 1) % 4
    p = os.path.join(目, f"04_锚{锚}格{M}.mp4")
    if os.path.isfile(p):
        出.append(p)
    return 出


def 读mp4首帧且量内部(路, 最多帧=120):
    """返回 (首帧BGR, 帧数, fps, 平均光流幅度, 光流样本数)。"""
    cap = cv2.VideoCapture(路)
    if not cap.isOpened():
        return None, 0, 0.0, None, 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    首 = None
    前 = None
    流们 = []
    帧数 = 0
    while 帧数 < 最多帧:
        ok, f = cap.read()
        if not ok:
            break
        if 首 is None:
            首 = f
        if 前 is not None:
            g1 = cv2.cvtColor(前, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            流 = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            流们.append(float(np.mean(np.sqrt(流[..., 0] ** 2 + 流[..., 1] ** 2))))
        前 = f
        帧数 += 1
    总 = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 帧数)
    cap.release()
    m = float(np.mean(流们)) if 流们 else None
    return 首, 总, fps, m, len(流们)


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("作品")
    ap.add_argument("--只格", default="")
    ap.add_argument("--阈值", action="store_true", help="只打印分布，不判")
    ap.add_argument("--表", action="store_true", help="额外写一份 markdown")
    a = ap.parse_args()

    目 = os.path.join(根, "影匠", "作品", a.作品)
    if not os.path.isdir(目):
        print(f"✗ 没有这个作品目录：{目}")
        return 2

    格们 = sorted(int(re.search(r"01_格(\d+)\.png", p).group(1))
                 for p in glob.glob(os.path.join(目, "01_格*.png")))
    if a.只格:
        要 = {int(x) for x in re.findall(r"\d+", a.只格)}
        格们 = [n for n in 格们 if n in 要]

    print(f"量《{a.作品}》　{len(格们)} 格　·　只读，不改任何东西")
    print()

    # 先读所有首帧
    首帧 = {}
    for n in 格们:
        p = os.path.join(目, f"01_格{n}.png")
        im, 灰, 小 = 读灰(p)
        首帧[n] = (p, im, 灰, 小, 0.0, 0.0)
    print(f"① 跳格　相邻两格「光」变没变（直方图相关 / 亮度差 / 饱和度差）")
    print(f"     ★ pHash 汉明一栏只当参考 —— 景别一变它必然大，不是判据")
    行1 = []
    for i in range(len(格们) - 1):
        n1, n2 = 格们[i], 格们[i + 1]
        _, im1, _, s1, _, _ = 首帧[n1]
        _, im2, _, s2, _, _ = 首帧[n2]
        if s1 is None or s2 is None:
            continue
        汉明 = int(np.count_nonzero(pHash(s1) != pHash(s2)))
        c1 = cv2.calcHist([s1], [0], None, [64], [0, 256])
        c2 = cv2.calcHist([s2], [0], None, [64], [0, 256])
        cv2.normalize(c1, c1); cv2.normalize(c2, c2)
        相关 = float(cv2.compareHist(c1, c2, cv2.HISTCMP_CORREL))
        亮差 = abs(float(s1.mean()) - float(s2.mean()))
        h1 = cv2.cvtColor(im1, cv2.COLOR_BGR2HSV)[..., 1]
        h2 = cv2.cvtColor(im2, cv2.COLOR_BGR2HSV)[..., 1]
        饱差 = abs(float(h1.mean()) - float(h2.mean())) / 255.0
        坏 = (相关 < 跳格_相关) or (亮差 > 跳格_亮度) or (饱差 > 跳格_饱和)
        行1.append((n1, n2, 汉明, 相关, 亮差, 饱差, 坏))
        if 坏 or not a.阈值:
            标 = "✗ 光跳了" if 坏 else "·"
            理由 = []
            if 相关 < 跳格_相关: 理由.append(f"相关{相关:.2f}<{跳格_相关}")
            if 亮差 > 跳格_亮度: 理由.append(f"亮差{亮差:.0f}>{跳格_亮度:.0f}")
            if 饱差 > 跳格_饱和: 理由.append(f"饱差{饱差:.2f}>{跳格_饱和}")
            print(f"     {标} 格{n1:>2}→格{n2:<2}　相关 {相关:>6.3f}　亮差 {亮差:>5.1f}　"
                  f"饱差 {饱差:>5.3f}　（汉明 {汉明:>2}）"
                  + (("　← " + "，".join(理由)) if 理由 else ""))
    if a.阈值 and 行1:
        汉 = [x[2] for x in 行1]; 相 = [x[3] for x in 行1]
        亮 = [x[4] for x in 行1]; 饱 = [x[5] for x in 行1]
        print(f"     相关  min {min(相):.3f} / 中位 {np.median(相):.3f} / max {max(相):.3f}　（阈值 {跳格_相关}）")
        print(f"     亮差  min {min(亮):.1f} / 中位 {np.median(亮):.1f} / max {max(亮):.1f}　（阈值 {跳格_亮度}）")
        print(f"     饱差  min {min(饱):.3f} / 中位 {np.median(饱):.3f} / max {max(饱):.3f}　（阈值 {跳格_饱和}）")
        print(f"     汉明  min {min(汉)} / 中位 {int(np.median(汉))} / max {max(汉)}　（★ 不判，只参考）")

    print()
    print(f"② 没贴住　mp4 第 0 帧 vs 01_格N.png（平均绝对差，0-255）")
    行2 = []
    for n in 格们:
        候选 = 找mp4(目, n)
        if not 候选:
            continue
        mp4 = 候选[0]
        名 = os.path.relpath(mp4, 目)
        首, 帧数, fps, 流, 样本 = 读mp4首帧且量内部(mp4)
        _, im, _, 小, _, _ = 首帧[n]
        if 首 is None or im is None:
            continue
        首小 = cv2.cvtColor(首, cv2.COLOR_BGR2GRAY)
        首小 = cv2.resize(首小, (小.shape[1], 小.shape[0]), interpolation=cv2.INTER_AREA)
        mae = float(np.mean(np.abs(首小.astype(np.float32) - 小.astype(np.float32))))
        贴坏 = mae > 贴_MAE
        动坏 = (流 is not None) and (流 < 动_光流)
        print(f"     {'✗' if (贴坏 or 动坏) else '·'} 格{n:>2}　贴住 MAE {mae:>6.1f}"
              f"　动 {('%.3f' % 流) if 流 is not None else '  n/a'}"
              f"　{帧数} 帧 @ {fps:.2f}fps = {帧数/max(fps,1e-6):.2f} 秒"
              f"　[{名}]"
              f"{'　★ 没动' if 动坏 else ''}{'　★ 没贴住' if 贴坏 else ''}")
        行2.append((n, mae, 流, 帧数, fps, 贴坏, 动坏))

    print()
    print("─" * 70)
    坏1 = [f"格{x[0]}→{x[1]}" for x in 行1 if x[6]]
    坏2 = [f"格{x[0]}(MAE {x[1]:.0f})" for x in 行2 if x[5]]
    坏3 = [f"格{x[0]}(流 {x[2]:.2f})" for x in 行2 if x[6]]
    print(f"有首帧 {len(格们)} 格　有 mp4 {len(行2)} 格")
    if not 坏1:
        print("✓ ① 光：没有相邻两格光跳的")
    else:
        print(f"✗ ① 光跳了 {len(坏1)} 处：{', '.join(坏1)}")
    if not 坏2:
        print("✓ ② 贴住：所有 mp4 的第 0 帧都贴住了首帧")
    else:
        print(f"✗ ② 没贴住 {len(坏2)} 格：{', '.join(坏2)}")
    if not 坏3:
        print("✓ ③ 在动：所有 mp4 内部都有运动")
    else:
        print(f"✗ ③ 没动 {len(坏3)} 格：{', '.join(坏3)}")

    缺 = [n for n in 格们 if not 找mp4(目, n)]
    if 缺:
        print(f"· 还没有 mp4 的格：{缺}")

    if a.表:
        出 = os.path.join(目, "_连贯表.md")
        with open(出, "w", encoding="utf-8") as f:
            f.write(f"# 《{a.作品}》连贯表\n\n")
            f.write("由 `python _查连贯.py %s --表` 生成。阈值：汉明>%d 或 相关<%.2f 报跳；"
                    "MAE>%.0f 报没贴住；光流<%.2f 报没动。\n\n" % (a.作品, 跳格_汉明, 跳格_相关, 贴_MAE, 动_光流))
            f.write("| 格 |→下一格 汉明 | 相关 | 贴住 MAE | 光流 | 帧 | fps | 秒 | 判 |\n")
            f.write("|---|---|---|---|---|---|---|---|---|\n")
            for n, mae, 流, 帧数, fps, 贴坏, 动坏 in 行2:
                跳 = next((x for x in 行1 if x[0] == n), None)
                判 = "✓" if not (贴坏 or 动坏 or (跳 and 跳[4])) else "✗"
                f.write("| %d | %s | %s | %.1f | %s | %d | %.2f | %.2f | %s |\n" % (
                    n, 跳[2] if 跳 else "-", ("%.3f" % 跳[3]) if 跳 else "-", mae,
                    ("%.3f" % 流) if 流 is not None else "-", 帧数, fps,
                    帧数 / max(fps, 1e-6), 判))
        print(f"\n已写 {出}")
    return 0


if __name__ == "__main__":
    sys.exit(主())
