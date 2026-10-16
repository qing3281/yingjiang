# -*- coding: utf-8 -*-
"""量接缝处的声音跳变 —— 「128 段拼起来会不会咔哒响」。

## 为什么要这个脚本

新片子是 **128 个小段拼起来**的（`_接子镜.py` 用 ffmpeg concat demuxer + `-c copy`，
不重编码）。视频那头每一小段的两端都是真图，接得上；**音频那头是 128 段各自独立生成的
环境音，接缝处波形是断的** —— 断一次就是一个咔哒。

这条链是无人值守的（`_守成片2.py` 会在半夜自己跑完），所以我必须在它跑之前
先量出「接缝到底明不明显」。**不能等片子出来再听** —— 那时候已经寄出去了。

## 判据

对每一小段边界（k × 段秒），取边界前后 10 毫秒里 `|相邻采样差|` 的最大值；
再取**远离边界处**同样统计量的 99.9 百分位当基准。

    边界最大跳变 / 远离边界 99.9 百分位 <= 3     → 听不出来，可以接受
    > 10                                        → 一定听得见，必须处理

（参照：H3 插件自己的长视频 README 记着「音频单采样跳变由 0.02231 降到 0.00104」
是他们做接缝平滑的成绩单，所以这个量级是「有没有做事」的分界线。）

用法：
    python check_seam.py <mp4 路径> [--段秒 2.333333]
"""
import os
import sys
import subprocess
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

try:
    import numpy as np
except Exception as e:
    print("✗ 没有 numpy：%s" % e)
    sys.exit(2)

FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"


def 取音(路, 临时):
    r = subprocess.run([FF, "-y", "-v", "error", "-i", 路, "-ac", "1", "-ar", "32000",
                        "-f", "f32le", 临时],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.isfile(临时):
        print("✗ 取音失败：" + (r.stderr or "")[-600:])
        return None
    x = np.fromfile(临时, dtype="<f4").astype(np.float64)
    os.remove(临时)
    return x


def 主():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    路 = sys.argv[1]
    段秒 = 2.3333333
    if "--段秒" in sys.argv:
        段秒 = float(sys.argv[sys.argv.index("--段秒") + 1])
    if not os.path.isfile(路):
        print("✗ 文件不在：%s" % 路)
        return 1

    频 = 32000
    临时 = os.path.join(tempfile.gettempdir(), "seam_%d.raw" % os.getpid())
    x = 取音(路, 临时)
    if x is None:
        return 1
    秒 = len(x) / 频
    d = np.abs(np.diff(x))
    半窗 = int(0.010 * 频)          # 10 毫秒

    # 边界：k × 段秒
    n段 = int(round(秒 / 段秒))
    边界 = [int(round(k * 段秒 * 频)) for k in range(1, n段)]
    边界 = [b for b in 边界 if 半窗 < b < len(d) - 半窗]

    掩 = np.zeros(len(d), dtype=bool)
    for b in 边界:
        掩[max(0, b - 半窗):b + 半窗] = True

    界内 = d[掩]
    界外 = d[~掩]
    基准 = float(np.percentile(界外, 99.9)) if len(界外) else 0.0
    最 = float(界内.max()) if len(界内) else 0.0
    各 = [(b, float(d[max(0, b - 半窗):b + 半窗].max())) for b in 边界]
    各.sort(key=lambda t: -t[1])

    print("=" * 64)
    print("接缝体检　%s" % os.path.basename(路))
    print("  时长 %.2f 秒　采样 %d 点　段秒 %.4f　边界 %d 个" % (秒, len(x), 段秒, len(边界)))
    print("  边界处最大单采样跳变   %.6f" % 最)
    print("  远离边界 99.9 百分位    %.6f" % 基准)
    print("  比值                    %.2f×" % (最 / 基准 if 基准 else 0))
    print("  最响的 5 个接缝：")
    for b, v in 各[:5]:
        print("    第 %5.3f 秒　跳变 %.6f　（是基准的 %.1f 倍）" % (b / 频, v, v / 基准 if 基准 else 0))
    print("-" * 64)
    比 = (最 / 基准) if 基准 else 0
    if 比 <= 3:
        print("  ✓ 接缝听不出来（≤3×）—— `-c copy` 直接拼可以接受")
        return 0
    if 比 <= 10:
        print("  ~ 接缝可能有一点点（3–10×）——能接受，但记进报告")
        return 0
    print("  ✗ 接缝一定听得见（>10×）——接片时必须给音频做处理（见 _接子镜.py 的说明）")
    return 1


if __name__ == "__main__":
    sys.exit(主())
