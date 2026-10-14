# -*- coding: utf-8 -*-
"""量「一格里到底动没动」—— 判「单镜里像看图片」用的。

## 为什么要量

用户说过两次：
  「单镜里像看图片」
  「动作不连贯、前后衔接有问题」

换 H3 之前用的是 `wan2.2_ti2v_5B`，那个 5B 小模型只会做很轻的运动，
所以「像看图片」是**已知的真问题**。换成 MiniMax-H3 之后**到底好没好、好了多少**，
不能靠看一两眼就说 —— 得有个数。

## 量的是什么

逐帧算**平均绝对帧差**（相邻两帧逐像素灰度差的平均），再对整个镜头取平均：

    运动量 = mean( mean(|f[i+1] − f[i]|) )   单位是 0–255 的灰度级

- **画面完全冻住** → 0
- **轻微呼吸/头发飘** → 0.3 – 1.5
- **正常有人物动作、镜头稳** → 1.5 – 5
- **大幅动作 / 镜头运动** → 5 以上

★ 这个数**只说明「像素变了多少」，不说明「变的是不是有意义」**：
   噪点、压缩抖动、光影闪动也会让它变大。所以它只能用来**筛出冻住的格子**，
   不能反过来当「动得好」的证据。要判动作对不对，还得看画面。

## 用法

    python _量运动.py 觉醒                      # 量 段\\ 全部
    python _量运动.py 觉醒 --只格 55,56,59       # 只量几格
    python _量运动.py 觉醒 --画条                 # 顺便拼一张「每格首尾帧」的图
"""
import argparse
import glob
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")


def 量一格(路, 宽=160):
    """用 ffmpeg 把片缩到很小再逐帧比 —— 比开 numpy 读全分辨率快得多，也够用。

    ★ `metadata=print` 默认**写到文件**，不加 `file=-` 就什么都不输出到 stdout，
      脚本会静默地一格都读不出来。这是踩过的坑。
    ★ `format=gray` 必须在 `tblend` **前**面，否则 tblend 在 YUV 上做差，
      signalstats 量到的不是纯亮度差。
    """
    cmd = [
        FFMPEG, "-v", "error", "-i", 路,
        "-vf", f"scale={宽}:-2,format=gray,tblend=all_mode=difference,"
               f"signalstats,metadata=print:file=-",
        "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    出 = []
    for 行 in (r.stdout or "").splitlines():
        m = re.search(r"YAVG=([\d.]+)", 行)
        if m:
            出.append(float(m.group(1)))
    if not 出:
        return None, 0
    # 第一帧的「帧差」是跟黑比出来的，扔掉
    有效 = 出[1:] if len(出) > 1 else 出
    return sum(有效) / len(有效), len(有效)


def 段文件(戏):
    目 = os.path.join(根, "作品", 戏, "段")
    出 = {}
    for p in glob.glob(os.path.join(目, "*.mp4")):
        m = re.match(r"^格(\d+)_(本机|远端)\.mp4$", os.path.basename(p))
        if m:
            n = int(m.group(1))
            if n not in 出 or os.path.getsize(p) > os.path.getsize(出[n]):
                出[n] = p
    return dict(sorted(出.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--只格", default="")
    ap.add_argument("--宽", type=int, default=160)
    参 = ap.parse_args()

    段 = 段文件(参.戏)
    if 参.只格:
        要 = {int(x) for x in re.findall(r"\d+", 参.只格)}
        段 = {k: v for k, v in 段.items() if k in 要}
    if not 段:
        print(f"  ✗ 作品\\{参.戏}\\段\\ 下没有段")
        return 1

    print(f"  量 {len(段)} 格的运动量（相邻帧灰度差平均，0=冻住）")
    print(f"  {'格':<6}{'运动量':>9}   {'判':<8}文件")
    print("  " + "─" * 68)
    果 = {}
    for n, p in 段.items():
        值, 帧 = 量一格(p, 参.宽)
        if 值 is None:
            print(f"  {n:<6}{'读不出':>9}")
            continue
        果[n] = 值
        if 值 < 0.20:
            判 = "★ 冻住"
        elif 值 < 0.60:
            判 = "很轻"
        elif 值 < 2.0:
            判 = "正常"
        elif 值 < 5.0:
            判 = "有动作"
        else:
            判 = "动作大"
        print(f"  {n:<6}{值:>9.3f}   {判:<8}{os.path.basename(p)}")

    if 果:
        值s = sorted(果.values())
        n = len(值s)
        print("  " + "─" * 68)
        print(f"  格数 {n}　最小 {值s[0]:.3f}　中位 {值s[n//2]:.3f}　最大 {值s[-1]:.3f}　"
              f"平均 {sum(值s)/n:.3f}")
        for 阈 in (0.20, 0.60, 1.0, 2.0):
            数 = sum(1 for v in 值s if v < 阈)
            print(f"    运动量 < {阈:<5} 的：{数:>3} 格（{数*100.0/n:.0f}%）")
        最静 = sorted(果.items(), key=lambda kv: kv[1])[:8]
        print("  最静的 8 格：" + ' '.join(f"格{k}({v:.2f})" for k, v in 最静))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
