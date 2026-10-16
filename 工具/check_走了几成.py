# -*- coding: utf-8 -*-
"""量每一格「走了几成」—— 只看两头，不看过程。

走了几成 = MAE(01_格N, 最后一段真出来的末帧) ÷ MAE(01_格N, 末_格N)
           分子 = 这一段路它真走了多少
           分母 = 这一格该走的全程
  ≈1   整格演完了
  ≈0.2 几乎没动，只是原地喘气 —— 屏幕上就是「一张不动的图」

为什么要这个数：上面那两张对比条（`_看落点.jpg`）已经把结论摆出来了 ——
格13 上下两排根本不是一回事（上排要拉远成全身，下排一直卡在脸的大特写），
格22 上下一眼就配得上。所以「32 格里有几格真的走起来了」必须数出来。
"""
import glob, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
子镜目 = os.path.join(目, "子镜")
宽 = 320


def 图(p):
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    h = max(1, int(im.shape[0] * 宽 / im.shape[1]))
    return cv2.resize(im, (宽, h)).astype(np.float32)


def 末帧(p):
    cap = cv2.VideoCapture(p)
    末 = None
    while True:
        好, f = cap.read()
        if not 好:
            break
        末 = f
    cap.release()
    if 末 is None:
        return None
    g = cv2.cvtColor(末, cv2.COLOR_BGR2GRAY)
    h = max(1, int(g.shape[0] * 宽 / g.shape[1]))
    return cv2.resize(g, (宽, h)).astype(np.float32)


def 差(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.abs(a - b).mean())


有 = {}
for p in glob.glob(os.path.join(子镜目, "格*_*.mp4")):
    m = re.match(r"^格(\d+)_(\d+)\.mp4$", os.path.basename(p))
    if m:
        有.setdefault(int(m.group(1)), {})[int(m.group(2))] = p

print("格   走了几成   它真走的   这一格该走的   最末段")
成表 = []
for g in sorted(有):
    d = 有[g]
    if 4 not in d:
        print("  %-3s  （段4还没出）" % g)
        continue
    起 = 图(os.path.join(目, "01_格%d.png" % g))
    标 = 图(os.path.join(目, "末帧", "末_格%d.png" % g))
    真 = 末帧(d[4])
    走 = 差(起, 真)
    该 = 差(起, 标)
    if 走 is None or 该 in (None, 0):
        continue
    成 = 走 / 该
    成表.append((g, 成, 走, 该))
    print("  %-3s %7.0f%% %9.2f %13.2f    段4 → %s" % (g, 成 * 100, 走, 该, os.path.basename(d[4])))

a = np.array([x[1] for x in 成表])
print()
if len(a):
    print("★ 已满 4 段的格 %d 个" % len(a))
    print("   走了几成：中位 %.0f%%  最小 %.0f%%  最大 %.0f%%" % (np.median(a) * 100, a.min() * 100, a.max() * 100))
    for 线 in (0.5, 0.3, 0.15):
        n = int((a >= 线).sum())
        print("   ≥%.0f%% 的格：%d / %d" % (线 * 100, n, len(a)))
    差格 = [g for g, c, _, _ in 成表 if c < 0.3]
    print("   走了不到三成的格：%s" % 差格)
print()
print("怎么读：≥50% = 这一格真演完了；<30% = 屏幕上基本是一张不动的图。")
