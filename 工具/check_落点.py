# -*- coding: utf-8 -*-
"""量「已经出来的子镜到底落没落在该落的那些关键帧上」。

为什么要量这个：他 2026-10-16 让我生成了 96 张中间帧，并在 m01758 里画了这条链
（「首帧-2s-尾-2s-中间-2s-尾-2s-下一格的首」）。现在跑的这一批用的是 `--全无末帧`
（每段只钉第一帧、不钉末帧），所以那些中间帧**当没当上「该走到的地方」**这件事，
只能拿真产物量出来 —— 不能靠读代码猜。

判据（和 `记忆\\经验\\流程与脚本.md` 里那条一致）：
  ① 落点差：这一段**真出来的最后一帧** vs **它该落的那张关键帧**，MAE（0~255，越小越近）
  ② 尺子：同一段内相邻帧的 MAE 中位数 —— 落点差要比它大还是小，得跟它比才有意义
  ③ 方向：落点对「终点」是不是比「起点」更近（只给一个数会得出反的结论）
"""
import glob, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
import cv2
import numpy as np

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
子镜目 = os.path.join(目, "子镜")
宽 = 320


def 读图(p):
    im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    h = max(1, int(im.shape[0] * 宽 / im.shape[1]))
    return cv2.resize(im, (宽, h)).astype(np.float32)


def 读片(p):
    """返回 (首帧, 末帧, 相邻帧差中位数, 相邻帧差最大, 帧数)。"""
    cap = cv2.VideoCapture(p)
    首 = 末 = None
    前 = None
    差们 = []
    n = 0
    while True:
        好, f = cap.read()
        if not 好:
            break
        n += 1
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        h = max(1, int(g.shape[0] * 宽 / g.shape[1]))
        g = cv2.resize(g, (宽, h)).astype(np.float32)
        if 首 is None:
            首 = g
        if 前 is not None:
            差们.append(float(np.abs(g - 前).mean()))
        前 = g
        末 = g
    cap.release()
    if 首 is None:
        return None
    a = np.array(差们) if 差们 else np.array([0.0])
    return 首, 末, float(np.median(a)), float(a.max()), n


def 差(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.abs(a - b).mean())


print("读已出的子镜 …")
有 = {}
for p in glob.glob(os.path.join(子镜目, "格*_*.mp4")):
    m = re.match(r"^格(\d+)_(\d+)\.mp4$", os.path.basename(p))
    if m:
        有.setdefault(int(m.group(1)), {})[int(m.group(2))] = p

齐 = sorted(g for g, d in 有.items() if len(d) == 4)
print("完整的格 %d 个：%s" % (len(齐), 齐))

# 关键帧
K = {}
for g in 齐:
    K[g] = [读图(os.path.join(目, "01_格%d.png" % g))]
    for k in (1, 2, 3):
        K[g].append(读图(os.path.join(目, "02_中%d_%d.png" % (g, k))))
    K[g].append(读图(os.path.join(目, "末帧", "末_格%d.png" % g)))

print()
print("格   段  落点差  段内中位  倍数    帧数   方向(对起点-对终点)")
总倍 = []
落点表 = []
for g in 齐:
    前末 = None
    for 段 in (1, 2, 3, 4):
        p = 有[g][段]
        r = 读片(p)
        if r is None:
            print("  格%s_%s 读不出来" % (g, 段))
            continue
        首, 末, 中位, 最大, n = r
        标 = K[g][段]          # 这一段该落的那张关键帧
        起 = K[g][段 - 1]      # 这一段该从哪张出发
        d落 = 差(末, 标)
        d起 = 差(末, 起)
        倍 = 最大 / 中位 if 中位 > 0 else 0
        总倍.append(倍)
        if d落 is not None:
            落点表.append(d落)
        向 = ""
        if d落 is not None and d起 is not None:
            向 = "%.2f - %.2f = %+.2f %s" % (d起, d落, d起 - d落, "→更近终点 ✓" if d起 > d落 else "→更近起点 ✗")
        print("  %-3s %-3s %7.2f %8.2f %6.2fx %5d   %s" % (g, 段, d落, 中位, 倍, n, 向))
        # 跨段接缝
        if 前末 is not None:
            缝 = 差(前末, 首)
            print("        接缝(上一段真尾帧 vs 这一段的真首帧) = %.2f" % 缝)
        前末 = 末

a = np.array(落点表) if 落点表 else np.array([0.0])
b = np.array(总倍) if 总倍 else np.array([0.0])
print()
print("★ 落点差（真出来的末帧 vs 该落的关键帧）：中位 %.2f  最小 %.2f  最大 %.2f  （n=%d）"
      % (np.median(a), a.min(), a.max(), len(a)))
print("★ 段内跳变倍数（最大相邻帧差 ÷ 中位）：中位 %.2f  最大 %.2f" % (np.median(b), b.max()))
print()
print("怎么读这两个数：")
print("  落点差 越小 = 这一段真的走到了中间帧那里（中间帧当上了刻度）")
print("  倍数   ≈1~3 平顺；>10 说明段中间有一次瞬移")
