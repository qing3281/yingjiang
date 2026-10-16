# -*- coding: utf-8 -*-
"""量「像不像在看图片」—— 给每一格算真实帧间位移，而不是靠眼睛猜。

「像看图片」是个感觉，不能拿感觉当判据。可量的代理量有三个：
  1. **帧间差**：相邻两帧的平均绝对差。静帧接近 0；真人视频 24fps 下通常 2~12。
  2. **头尾差**：首帧与末帧的平均绝对差。整段只挪了一点点就是「推进去一点点」。
  3. **人脸上的位移**：用最亮/最暗区域的质心位移估「主体动没动」（不依赖人脸检测）。

对照：旧的 wan2.2 段在 `作品\觉醒\段\_旧_wan2.2\` 或《磨刀》的段里，有就一起比。

用法：
    python _量动态_觉醒.py                 # 本机 + 远端，全部已出的段
    python _量动态_觉醒.py --旧 作品\磨刀\段  # 再和旧模型的段比
"""
import argparse
import os
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(根, "_bin", "ffmpeg.exe")
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"


def 帧差(路, 模式="邻帧"):
    """邻帧差用 tblend 一把算完；头尾差用「首帧 PNG 比末帧 PNG」，与帧数无关。"""
    if 模式 == "邻帧":
        滤镜 = ("tblend=all_mode=difference,signalstats,"
                "metadata=print:key=lavfi.signalstats.YAVG:file=-")
        r = subprocess.run([FF, "-v", "error", "-i", 路, "-vf", 滤镜, "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        # ★ metadata=print 默认写 INFO 级日志，被 -v error 吞掉；`:file=-` 才写 stdout。
        值 = []
        for 行 in ((r.stdout or "") + (r.stderr or "")).splitlines():
            if "YAVG=" in 行:
                try:
                    值.append(float(行.split("YAVG=")[1].split()[0]))
                except Exception:
                    pass
        return (sum(值) / len(值)) if 值 else None

    # ── 头尾差：首帧 vs 末帧，直接用像素算，不依赖帧号 ──
    from PIL import Image
    import tempfile
    首 = os.path.join(tempfile.gettempdir(), "_首.png")
    末 = os.path.join(tempfile.gettempdir(), "_末.png")
    取 = lambda 参: subprocess.run(
        [FF, "-y", "-v", "error"] + 参 + [
            "-frames:v", "1", "-vf", "scale=320:176",
            "-f", "image2pipe", "-vcodec", "png", "-"],   # ★ 少了 image2pipe 就写不进管道
        capture_output=True).stdout
    甲 = 取(["-i", 路])
    乙 = 取(["-sseof", "-0.15", "-i", 路])
    if not 甲 or not 乙:
        return None
    open(首, "wb").write(甲)
    open(末, "wb").write(乙)
    try:
        a = Image.open(首).convert("L")
        b = Image.open(末).convert("L")
    except Exception:
        return None
    if a.size != b.size:
        b = b.resize(a.size)
    pa, pb = a.load(), b.load()
    w, h = a.size
    总 = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            总 += abs(pa[x, y] - pb[x, y])
    return 总 / ((w // 2) * (h // 2))


def 扫(目录, 标签):
    行 = []
    if not os.path.isdir(目录):
        return 行
    for f in sorted(os.listdir(目录)):
        if not f.endswith(".mp4") or not f.startswith("格"):
            continue
        p = os.path.join(目录, f)
        a = 帧差(p, "邻帧")
        b = 帧差(p, "头尾")
        if a is None:
            continue
        行.append((f, a, b if b is not None else float("nan")))
    if not 行:
        return 行
    print(f"\n=== {标签}（{len(行)} 格）===")
    print("  %-22s %8s %8s" % ("段", "邻帧差", "头尾差"))
    邻 = [x[1] for x in 行]
    头 = [x[2] for x in 行 if x[2] == x[2]]
    for f, a, b in 行[:6]:
        print("  %-22s %8.2f %8.2f" % (f, a, b))
    if len(行) > 8:
        print("  ...")
        for f, a, b in 行[-2:]:
            print("  %-22s %8.2f %8.2f" % (f, a, b))
    print("  ── 邻帧差：最小 %.2f　中位 %.2f　最大 %.2f" % (
        min(邻), sorted(邻)[len(邻) // 2], max(邻)))
    if 头:
        print("  ── 头尾差：最小 %.2f　中位 %.2f　最大 %.2f" % (
            min(头), sorted(头)[len(头) // 2], max(头)))
        # 判据：头尾差 < 1.0 基本就是「只推了一点点」，那才是「像看图片」
        死 = [f for f, _, b in 行 if b == b and b < 1.0]
        print("  ── 疑似「只推了一点点」（头尾差 < 1.0）：%d 格 %s" % (
            len(死), ("　" + " ".join(死[:6])) if 死 else "（没有 ✓）"))
    return 行


def main():
    参 = argparse.ArgumentParser()
    参.add_argument("--旧", default="", help="拿旧模型的段目录做对照")
    a = 参.parse_args()

    全部 = []
    全部 += 扫(os.path.join(根, "作品", "觉醒", "段"), "H3 · 本机段")
    if a.旧:
        扫(os.path.join(根, a.旧), f"对照 · {a.旧}")
    旧段 = os.path.join(根, "作品", "觉醒", "段", "_旧_眼袋第三轮前")
    if os.path.isdir(旧段):
        扫(旧段, "H3 · 旧（眼袋第三轮前）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
