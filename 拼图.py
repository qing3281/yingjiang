# -*- coding: utf-8 -*-
"""
影匠 · 拼图  —— 把一叠镜头拼成一张看片表
================================================================
用法：
    python 拼图.py 作品/试镜              把整个目录的图拼成一张
    python 拼图.py 作品/试镜 3            每行 3 张
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# 能渲染中文的字体（按优先级找）
_字体候选 = [
    r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",    # 黑体
    r"C:\Windows\Fonts\Deng.ttf",      # 等线
    r"C:\Windows\Fonts\simsun.ttc",    # 宋体
]


def _字体(号):
    for p in _字体候选:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, 号)
            except Exception:
                pass
    return ImageFont.load_default()


def _标题(路径):
    n = os.path.splitext(os.path.basename(路径))[0]
    return n.replace("_", " ")


def 拼(目录, 每行=2, 格边=620, 出=None):
    图们 = sorted(
        f for f in os.listdir(目录)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) and not f.startswith("_")
    )
    if not 图们:
        print("目录里没有图：", 目录)
        return None

    行数 = (len(图们) + 每行 - 1) // 每行
    格 = 格边
    图 = Image.new("RGB", (格 * 每行 + 12, 格 * 行数 + 12), (16, 16, 18))
    画 = ImageDraw.Draw(图)
    字 = _字体(22)

    for i, f in enumerate(图们):
        try:
            im = Image.open(os.path.join(目录, f)).convert("RGB")
        except Exception as e:
            print("  跳过", f, e)
            continue
        im.thumbnail((格 - 14, 格 - 14))
        x = (i % 每行) * 格 + 6 + (格 - 14 - im.width) // 2
        y = (i // 每行) * 格 + 6
        图.paste(im, (x, y))
        # 名字条压在图片左下角
        条 = Image.new("RGBA", (im.width, 34), (0, 0, 0, 165))
        图.paste(Image.alpha_composite(
            Image.new("RGBA", (im.width, 34), (0, 0, 0, 0)), 条).convert("RGB"),
            (x, y + im.height - 34), 条)
        画.text((x + 10, y + im.height - 30), _标题(f), fill=(245, 245, 245), font=字)

    出 = 出 or os.path.join(目录, "_看片表.png")
    图.save(出)
    print("✓", 出, 图.size, f"({len(图们)} 张)")
    return 出


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    d = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    if not os.path.isabs(d):
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), d)
    拼(d, 每行=n)
