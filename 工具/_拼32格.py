import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont

# 2026-10-15：单格从正方形改成了 1344x768（16:9）。拼图跟着按格子真实比例走，
# 不再写死 470x470 —— 写死的话 16:9 的图会被塞进正方格、上下留黑边。
落 = r"D:\DSHworkspace\影匠\作品\楚子航"
目 = ["01_格%d.png" % i for i in range(1, 33)]
try: 字 = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
except Exception: 字 = ImageFont.load_default()

列 = 6
单 = 470                      # 每个格子的宽
s = Image.open(os.path.join(落, 目[0]))
高 = int(round(单 * s.size[1] / s.size[0]))   # 按真实宽高比算格子高 → 16:9 时是 269
条 = 40
行数 = (len(目) + 列 - 1) // 列
出 = Image.new("RGB", (单 * 列, (高 + 条) * 行数), (12, 12, 16))
画 = ImageDraw.Draw(出)
for i, f in enumerate(目):
    p = os.path.join(落, f)
    if not os.path.isfile(p):
        continue
    im = Image.open(p).convert("RGB").resize((单, 高), Image.LANCZOS)
    x, y = (i % 列) * 单, (i // 列) * (高 + 条)
    画.text((x + 10, y + 6), f[:-4].replace("01_", ""), font=字, fill=(255, 226, 150))
    出.paste(im, (x, y + 条))
q = os.path.join(落, "_32格总览.png")
出.save(q)
print("  →", q, 出.size, "%.1f MB" % (os.path.getsize(q) / 1048576))
