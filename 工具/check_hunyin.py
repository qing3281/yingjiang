# -*- coding: utf-8 -*-
"""验「混音」这一站 —— 无人值守链上唯一没拿真数据跑过的一步。

为什么要单独验：这一步把 32 个人声文件按格起点贴到 H3 的环境音上，
一条 ffmpeg 命令行里有 32 个 `-i` + 32 条 adelay。任何一条写错，
整条命令直接失败 —— 而这一步失败，观众听到的就是**一句人声都没有**。

做法：不重写混音，把 `_接子镜` import 进来，只把它的 `片目` 指到临时目录，
调它自己的 `混音()`。造一条 298.67 秒的**静音**假片当底（真片还没接出来）。

判据（四条）：
  ① 混音返回了非空路径，产物在磁盘上
  ② 产物有音轨
  ③ 第 1 句该响的窗口（0.35–2.0 秒）RMS 明显高于「不该响」的窗口（5.0–6.0 秒）
  ④ 第 27 句（最长的一句 4.34 秒，格27 起点 = 26×9.3333+0.35 ≈ 243.0 秒）那一带也该响
"""
import os, sys, json, shutil, subprocess, importlib.util

sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
接子镜路 = r"D:\DSHworkspace\影匠\作品\楚子航\_接子镜.py"
临 = r"D:\DSHworkspace\_试混音"
一格秒 = 4 * 56 / 24.0
总秒 = 128 * 56 / 24.0          # 298.667


def RMS(路, 起, 止):
    """量一段窗口的平均电平（dB）。用 ffmpeg 的 astats，不自己解 aac。"""
    r = subprocess.run([FF, "-v", "info", "-i", 路, "-af",
                        f"atrim=start={起}:end={止},astats=measure_overall=RMS_level:measure_perchannel=none",
                        "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for 线 in (r.stderr or "").splitlines():
        if "RMS level dB" in 线:
            try:
                return float(线.split(":")[-1].strip())
            except ValueError:
                pass
    return None


def 主():
    print("=" * 66)
    print("验「混音」这一站（拿真函数、真配音表，只把片目指到临时目录）")
    print("=" * 66)
    os.makedirs(临, exist_ok=True)

    # 把生产模块 import 进来
    规 = importlib.util.spec_from_file_location("接子镜_验", 接子镜路)
    m = importlib.util.module_from_spec(规)
    规.loader.exec_module(m)

    # 只改落盘目录，别的都不动
    m.片目 = 临
    m.锁路 = os.path.join(临, "_接子镜锁.json")
    m.成片 = os.path.join(临, "楚子航_成片_字幕.mp4")

    无 = os.path.join(临, "假无声.mp4")
    print("\n① 造一条 %.2f 秒的静音假片当底…" % 总秒)
    if not os.path.isfile(无):
        r = subprocess.run([FF, "-y", "-v", "error",
                            "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=%.3f" % 总秒,
                            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                            "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                            "-crf", "51", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", 无],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print("  ✗ 造假片失败：\n" + (r.stderr or "")[-1500:])
            return 1
    print("  ✓ 假底 %s  %.2f 秒" % (无, m.数秒(无)))

    print("\n② 出 srt（用真的台词表）…")
    srt = m.出srt()
    print("  ✓ %s" % srt)

    print("\n③ 调生产函数 混音()…")
    果 = m.混音(无, srt)
    if not 果 or not os.path.isfile(果):
        print("✗ 判据① 不过：混音没产出")
        return 1
    print("  ✓ 判据① 产物在：%s  %d B" % (果, os.path.getsize(果)))

    # 判据② 有没有音轨
    r = subprocess.run([FF, "-v", "error", "-i", 果, "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    r2 = subprocess.run([FF, "-hide_banner", "-i", 果], capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    有音 = "Audio:" in (r2.stderr or "")
    print("  %s 判据② 有音轨：%s" % ("✓" if 有音 else "✗", 有音))
    if not 有音:
        return 1

    # 判据③④ 该响的地方响
    print("\n④ 量电平（dB，越大越响）…")
    窗 = [
        ("第1句该响 0.35–2.00s", 0.35, 2.00, "响"),
        ("不该响   5.00–6.00s", 5.00, 6.00, "静"),
        # ★ 这里原来写 290.0–291.0s 当「不该响」，是**我的尺子错**，不是混音错：
        #   第 32 句「再见。」起点 = 31×9.3333+0.35 = 289.68 秒、长 1.277 秒 → 到 290.96 秒，
        #   290.0–291.0 正好压在它身上。选静窗必须先算清楚每一句的起止。
        ("不该响  42.00–43.00s", 42.00, 43.00, "静"),
        ("不该响 106.00–107.00s", 106.00, 107.00, "静"),
        ("第27句该响 243.0–246.0s", 243.0, 246.0, "响"),
        ("第32句该响 290.0–290.9s", 290.0, 290.9, "响"),
    ]
    表 = {}
    for 名, a, b, 类 in 窗:
        v = RMS(果, a, b)
        表[名] = (v, 类)
        print("   %-26s %s dB   （应该%s）" % (名, ("%.2f" % v) if v is not None else "量不到", 类))

    响 = [表[k][0] for k in 表 if 表[k][1] == "响" and 表[k][0] is not None]
    静 = [表[k][0] for k in 表 if 表[k][1] == "静" and 表[k][0] is not None]
    if not 响 or not 静:
        print("✗ 电平量不全，判据③④ 算不了")
        return 1
    过 = min(响) - max(静) > 12
    print("\n   最轻的「该响」= %.2f dB　最响的「该静」= %.2f dB　差 %.2f dB" %
          (min(响), max(静), min(响) - max(静)))
    print("   %s 判据③④ 人声确实只在该说话的时候出现（门槛 >12 dB）" % ("✓" if 过 else "✗"))
    print("\n" + "=" * 66)
    print("结论：%s" % ("混音这一站可以，无人值守链上没有裸奔的步了" if 过 else "混音这一站有问题"))
    return 0 if 过 else 1


if __name__ == "__main__":
    sys.exit(主())
