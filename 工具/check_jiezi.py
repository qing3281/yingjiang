# -*- coding: utf-8 -*-
"""验「子镜 → 接片 → 出 srt → 烧硬字幕」这条链 —— 拿**生产函数本身**跑，不重写一份。

## 为什么要这么验（不是多此一举）

链上唯一几处会「用户早上拿到一个没字幕/时长不对的片子」的地方：
- `接片()` 的 concat 列表（128 行，路径里全是中文）
- `出srt()` 的时间公式 —— ★ 这次 `一格秒` 从 `107/24 = 4.4583` 改成了 `4×56/24 = 9.3333`，
  公式改错了字幕会**整体错位**，而 srt 本身看着完全正常
- `烧()` 那行 ffmpeg 滤镜：Windows 路径 + 中文文件名 + 滤镜转义**挤在一行**

所以：import `_接子镜.py`，**只把 `片目/成片` 换到临时目录**，调它自己的 `接片()/出srt()/烧()`。
判据是**像素**不是文件 —— 同一条台词中点，从「无声片」和「烧完的片」各切底部一条，
用 `ImageChops.difference` 比 —— 全黑就是字幕根本没烧上去。

用法：python check_jiezi.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
临时 = r"D:\DSHworkspace\_试接子镜"
sys.path.insert(0, 目)
import _接子镜 as M          # noqa: E402
from _台词表 import 一格秒     # noqa: E402


def main():
    os.makedirs(临时, exist_ok=True)
    段 = [os.path.join(M.段目, "格1_%d.mp4" % k) for k in range(1, 5)]
    缺 = [p for p in 段 if not (os.path.isfile(p) and os.path.getsize(p) > 10000)]
    if 缺:
        print(f"✗ 格1 的 4 段还没出齐，缺：{[os.path.basename(p) for p in 缺]}")
        return 1
    print(f"① 格1 四段都在，" + "、".join("%s %.2fMB" % (os.path.basename(p), os.path.getsize(p) / 1048576)
                                        for p in 段))

    # 只把 格1 当成整部戏：找子镜 打桩，别的格返回空
    M.片目 = 临时
    M.成片 = os.path.join(临时, "楚子航_成片_字幕.mp4")

    def 找子镜(号):
        return 段 if 号 == 1 else []
    M.找子镜 = 找子镜

    表 = M.全表()
    if len(表) != 4:
        print(f"✗ 全表应该有 4 段，实际 {len(表)}")
        return 1
    print(f"② 全表 {len(表)} 段，按格/段排好：{[ (a, b) for a, b, _ in 表]}")

    无 = M.接片()
    if not 无:
        return 1
    秒 = M.数秒(无)
    期 = 4 * 一格秒 / 4          # 4 小段 × (一格秒/4)
    if abs(秒 - 期) > 0.25:
        print(f"✗ 无声片时长 {秒:.3f} 秒，应该是 {期:.3f} 秒（差 {abs(秒 - 期):.3f}）")
        return 1
    print(f"③ 时长对得上：{秒:.3f} 秒 vs 期望 {期:.3f} 秒（差 {abs(秒 - 期):.3f}）")

    srt = M.出srt()
    文 = open(srt, encoding="utf-8").read()
    print("④ srt 头三行：" + " / ".join(x for x in 文.splitlines()[:3] if x.strip()))
    if "00:00:00,350" not in 文:
        print("✗ srt 里没有 00:00:00,350 —— 一格秒 的公式算错了")
        return 1
    print("    ✓ 第一条字幕起在 00:00:00,350（=（格1−1）×9.3333 + 0.35）")

    成 = M.烧(无, srt)
    if not 成:
        return 1

    # 判据：像素。同一条台词中点，无声片 vs 成片，切底部 35%，比最大像素差。
    import cv2
    import numpy as np
    import subprocess
    ff = M.FF

    def 切条(源, 出):
        subprocess.run([ff, "-y", "-v", "error", "-ss", "1.0", "-i", 源, "-frames:v", "1",
                        "-vf", "crop=iw:ih*0.35:0:ih*0.65", 出], check=True,
                       capture_output=True)
        return cv2.imdecode(np.fromfile(出, dtype=np.uint8), cv2.IMREAD_COLOR)
    a = 切条(无, os.path.join(临时, "_条_无.png"))
    b = 切条(成, os.path.join(临时, "_条_有.png"))
    if a is None or b is None or a.shape != b.shape:
        print("✗ 切出来的两条形状不对")
        return 1
    差 = int(np.abs(a.astype(int) - b.astype(int)).max())
    print(f"⑤ 同一条台词中点、底部 35%：最大像素差 {差}")
    if 差 < 200:
        print("✗ 像素差太小 —— 字幕没烧上去（或烧在别的地方）")
        return 1
    print("    ✓ 字幕是像素，真的画在画面上了")
    print(f"\n★ 全过。成片 {成}　{os.path.getsize(成)} B　{秒:.3f} 秒")
    print(f"  看一眼：{os.path.join(临时, '_条_有.png')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
