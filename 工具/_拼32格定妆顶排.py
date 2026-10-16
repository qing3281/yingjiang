import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont
根 = r"D:\DSHworkspace\影匠\作品\楚子航"
卡 = [("楚子航", os.path.join(根, "_定妆卡_楚子航", "楚子航.png")),
      ("楚子航·爆血", os.path.join(根, "_定妆卡_楚子航_爆血", "楚子航_爆血.png")),
      ("夏弥", os.path.join(根, "_定妆卡_夏弥", "夏弥.png")),
      ("耶梦加得·半龙", os.path.join(根, "_定妆卡_耶梦加得", "耶梦加得.png"))]
try: 字 = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 28)
except Exception: 字 = ImageFont.load_default()

帧 = [os.path.join(根, "01_格%d.png" % n) for n in range(1, 33)]
帧 = [f for f in 帧 if os.path.exists(f)]
s0 = Image.open(帧[0]); 单 = s0.size[0]; 高格 = s0.size[1]
条 = 38; 列 = 6; 行数 = (len(帧) + 列 - 1) // 列

# ★ 定妆照改成**顶上一整排**（用户要「一目了然」，左边一列会被切掉）
卡高 = 520
卡宽 = int(卡高 * 0.75)
总宽 = max(单 * 列, 卡宽 * 4 + 60)
图 = Image.new("RGB", (总宽, 卡高 + 30 + 条 + 高格 * 行数 + 20), (10, 10, 14)); 画 = ImageDraw.Draw(图)
画.text((10, 4), "★ 原设（定妆照）", font=字, fill=(255, 226, 150))
for i, (名, f) in enumerate(卡):
    if not os.path.exists(f): print("  ✗ 缺", f); continue
    im = Image.open(f).convert("RGB")
    im = im.resize((卡宽, 卡高), Image.LANCZOS)
    x = i * (卡宽 + 14) + 10
    画.text((x + 4, 30), 名, font=字, fill=(190, 220, 255))
    图.paste(im, (x, 62))
y0 = 62 + 卡高 + 10
for i, f in enumerate(帧):
    n = int(os.path.basename(f)[4:-4])
    x = (i % 列) * 单
    yy = y0 + (i // 列) * (高格 + 条)
    画.text((x + 8, yy + 5), "格%d" % n, font=字, fill=(255, 226, 150))
    图.paste(Image.open(f).convert("RGB"), (x, yy + 条))
q1 = os.path.join(根, "_32格总览.jpg"); 图.save(q1, quality=88, optimize=True)
q2 = os.path.join(根, "_32格总览_小.jpg"); 图.resize((图.size[0]//2, 图.size[1]//2), Image.LANCZOS).save(q2, quality=84, optimize=True)
os.remove(os.path.join(根, "_32格总览.png"))
for q in (q1, q2): print("  → %s  %s  %.2f MB" % (q, Image.open(q).size, os.path.getsize(q)/1048576))
