# -*- coding: utf-8 -*-
r"""把《雪线》的台词轴画出来：加那一句之前 / 之后。

一张图说清一件事 ——「例外」这个词第一次出现的位置，从 82.6% 挪到了 15.9%。

★ 画法上的一个教训：**不要把台词文字直接贴在时间轴上**。
末句（180.0s）和「那就没有例外。」（151.1s）只差 29 秒，在 1500 像素宽里就是 200 像素，
两条标签必然叠在一起；试过「靠边就向左对齐」和「撞了就往上抬一行」，
结果是时间标签又跟文字标签撞上。**改成只画编号，文字一律放到下面的清单里** ——
轴上只留位置信息，文字交给列表，谁都不会撞谁。
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

总 = 182.98  # 成片时长（秒）
旧 = [
    (0.60, "旁白", "雪线以北，不许有活物。"),
    (41.40, "凌霜", "十年了。"),
    (81.80, "凌霜", "站住。"),
    (123.00, "凌霜", "……是我。"),
    (151.12, "凌霜", "那就没有例外。"),
    (180.04, "旁白", "雪线以北，不许有活物。"),
]
新 = [
    (0.60, "旁白", "雪线以北，不许有活物。"),
    (29.12, "凌霜", "没有例外。", True),
    (41.40, "凌霜", "十年了。"),
    (81.80, "凌霜", "站住。"),
    (123.00, "凌霜", "……是我。"),
    (151.12, "凌霜", "那就没有例外。"),
    (180.04, "旁白", "雪线以北，不许有活物。"),
]
圈 = "①②③④⑤⑥⑦⑧"

宽, 高 = 1500, 830
画 = Image.new("RGB", (宽, 高), (15, 17, 21))
d = ImageDraw.Draw(画)


def 字(n, 粗=False):
    for p in ((r"C:\Windows\Fonts\msyhbd.ttc" if 粗 else r"C:\Windows\Fonts\msyh.ttc"),
              r"C:\Windows\Fonts\msyh.ttc"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, n)
            except Exception:
                pass
    return ImageFont.load_default()


f22, f18, f15, f13 = 字(22, True), 字(18), 字(15), 字(13)

d.text((34, 22), "《雪线》台词轴 —— 加那一句「没有例外。」之前 / 之后", font=f22, fill=(230, 232, 238))
d.text((34, 56), "3 分 03 秒 · 45 格。量的是「那句话转的那个词第一次被说出来」在百分之几。",
       font=f15, fill=(124, 135, 152))

左, 右 = 96, 宽 - 56
轴y = [180, 330]


def 画轴(y, 名字, 行):
    d.text((34, y - 62), 名字, font=f18, fill=(230, 232, 238))
    d.line([(左, y), (右, y)], fill=(60, 68, 84), width=2)
    for s in range(4):
        x = 左 + (右 - 左) * s / 3
        d.line([(x, y - 6), (x, y + 6)], fill=(70, 80, 98), width=2)
        d.text((x - 14, y + 12), f"{s}:00", font=f13, fill=(90, 100, 118))
    for i, 项 in enumerate(行, 1):
        t, 谁 = 项[0], 项[1]
        强 = len(项) > 3
        x = 左 + (右 - 左) * t / 总
        c = (245, 197, 66) if 强 else ((61, 220, 132) if 谁 == "凌霜" else (150, 170, 200))
        d.line([(x, y - 16), (x, y + 16)], fill=c, width=3 if 强 else 2)
        r = 13 if 强 else 11
        d.ellipse([x - r, y - 16 - r * 2, x + r, y - 16], fill=(15, 17, 21), outline=c, width=2)
        tx = x - d.textlength(圈[i - 1], font=f13) / 2
        d.text((tx, y - 16 - r * 2 + 3), 圈[i - 1], font=f13, fill=c)
        d.text((x - d.textlength(f"{t:.1f}s", font=f13) / 2, y + 16), f"{t:.1f}s",
               font=f13, fill=c)


画轴(轴y[0], "改之前（六句）", 旧)
画轴(轴y[1], "改之后（七句）", 新)

# ── 两张清单 ──
def 清单(x0, y0, 标, 行, 色):
    d.text((x0, y0), 标, font=f18, fill=色)
    yy = y0 + 32
    for i, 项 in enumerate(行, 1):
        t, 谁, 文 = 项[0], 项[1], 项[2]
        强 = len(项) > 3
        c = (245, 197, 66) if 强 else (200, 206, 216)
        d.text((x0, yy), 圈[i - 1], font=f15, fill=c)
        d.text((x0 + 26, yy), f"{t:>6.2f}s", font=f15, fill=(124, 135, 152))
        d.text((x0 + 108, yy), f"{t / 总 * 100:>5.1f}%", font=f15, fill=(124, 135, 152))
        d.text((x0 + 186, yy), 谁, font=f15, fill=(124, 135, 152))
        d.text((x0 + 244, yy), 文, font=f15, fill=c)
        yy += 25


清单(34, 420, "改之前", 旧, (245, 197, 66))
清单(790, 420, "改之后", 新, (61, 220, 132))

d.rectangle([34, 640, 宽 - 34, 800], fill=(23, 27, 37), outline=(38, 44, 58))
d.text((52, 656), "「例外」这个词第一次出现的位置", font=f15, fill=(124, 135, 152))
d.text((52, 682), "改之前　151.12s = 82.6%", font=f18, fill=(245, 197, 66))
d.text((400, 682), "→", font=f18, fill=(124, 135, 152))
d.text((440, 682), "改之后　29.12s = 15.9%", font=f18, fill=(61, 220, 132))
d.text((52, 718), "高潮那句「那就没有例外。」一个字没动。变的是：观众在 0:29 就听过「例外」这个词，", font=f13, fill=(150, 160, 178))
d.text((52, 740), "所以 2:31 那一剑是「她把自己的规矩用在自己身上」，不是突然的。", font=f13, fill=(150, 160, 178))
d.text((52, 766), "对照《磨刀》：它的核心矛盾在 46s / 183s = 25% 就由人物当面说出来，所以它讲清了。",
       font=f13, fill=(150, 160, 178))

出 = r"D:\DSHworkspace\影匠\作品\雪线\_台词轴.png"
画.save(出)
print(f"  ✓ {出}　{画.width}x{画.height}　{os.path.getsize(出):,} B")
