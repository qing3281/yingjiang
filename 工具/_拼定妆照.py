# -*- coding: utf-8 -*-
r"""把四部戏的定妆照拼成一张总表 —— 用户 2026-10-14 02:09 的原话：

> 我要所有人物的最终的参考形象图。

## ★ 第一版我犯的错（2026-10-15 07:25）

第一版里「定位」那一行是**我凭记忆手写的**，写错了四个：
沈砚我写「学徒」（原文：磨刀匠 · 十年前听雪楼最年轻的刀客）、
赵崇武写「刀坊主人」（原文：提刑按察使司按察使）、
阿七/阿满写「刀坊伙计」（原文：参将 · 真叛徒 / 偏院茶铺烧火的 · 活人证）、
周泰写「对头」（原文：按察司的打手头目）。

→ **改法：定位一律从 `01-节拍拆解.md` 的锚点表里读，一个字都不手写。**
这正是 `影匠\知识\假判据族.md` 里「编动作」那一族 —— 产物在不在 ≠ 产物是不是这么来的。

用法：python _拼定妆照.py
产出：D:\DSHworkspace\影匠\作品\_定妆照总表.png
"""
import io
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

作品 = r"D:\DSHworkspace\影匠\作品"
出图 = os.path.join(作品, "_定妆照总表.png")


def 读锚点(戏):
    r"""从 `01-节拍拆解.md` 的「## 角色文字锚点串」表抠 `{角色: (定位, 锚点串)}`。

    跟 `影匠\_出定妆照.py` 的 `读锚点()` 同一套正则 —— 整段搬，不另写。
    """
    路 = os.path.join(作品, 戏, "01-节拍拆解.md")
    if not os.path.isfile(路):
        return {}
    文 = io.open(路, encoding="utf-8").read()
    m = re.search(r"^##\s*角色文字锚点串.*?$(.*?)(?=^##\s|\Z)", 文, re.S | re.M)
    if not m:
        return {}
    出 = {}
    for 行 in m.group(1).splitlines():
        行 = 行.strip()
        if not 行.startswith("|") or set(行) <= set("|-: "):
            continue
        列 = [c.strip() for c in 行.strip("|").split("|")]
        if len(列) < 3 or 列[0] in ("角色", ""):
            continue
        名 = re.sub(r"\*\*", "", 列[0]).strip()
        if not 名 or 名.startswith("角色"):
            continue
        出[名] = (列[1], 列[2])
    return 出


列顺序 = ["觉醒", "雪线", "磨刀"]
清单 = []
for 戏 in 列顺序:
    锚 = 读锚点(戏)
    for 角, (定位, _串) in 锚.items():
        路 = os.path.join(作品, 戏, "_定妆照", f"{角}.png")
        清单.append((戏, 角, 定位, 路))
    print(f"  {戏}：锚点表 {len(锚)} 个角色　有图 {sum(1 for a in 锚 if os.path.isfile(os.path.join(作品, 戏, '_定妆照', f'{a}.png')))} 张")

格宽, 格高, 头 = 380, 380, 62
列 = 4
行 = (len(清单) + 列 - 1) // 列
边 = 16
标题高 = 74

画 = Image.new("RGB", (列 * 格宽 + 边 * (列 + 1), 标题高 + 行 * (格高 + 头 + 边) + 边), (15, 17, 21))
d = ImageDraw.Draw(画)


def 字(号, 粗=False):
    for 路 in ((r"C:\Windows\Fonts\msyhbd.ttc" if 粗 else r"C:\Windows\Fonts\msyh.ttc"),
               r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if os.path.isfile(路):
            try:
                return ImageFont.truetype(路, 号)
            except Exception:
                pass
    return ImageFont.load_default()


f, fb, ft = 字(15), 字(19, True), 字(26, True)
d.text((边, 16), "影匠 · 三部戏人物定妆照总表", font=ft, fill=(230, 232, 238))
d.text((边, 48), "每张都是「正面半身 + 正面全身」两个视角同一个人的影棚图　·　「定位」逐字抄自各戏 01-节拍拆解.md 的锚点表　·　2026-10-15",
       font=f, fill=(124, 135, 152))

for i, (戏, 角, 定位, 路) in enumerate(清单):
    c, r = i % 列, i // 列
    x = 边 + c * (格宽 + 边)
    yy = 标题高 + 边 + r * (格高 + 头 + 边)
    d.text((x, yy), f"{戏}　{角}", font=fb, fill=(230, 232, 238))
    d.text((x, yy + 25), 定位[:24], font=f, fill=(124, 135, 152))
    if os.path.isfile(路):
        图 = Image.open(路).convert("RGB")
        图.thumbnail((格宽, 格高), Image.LANCZOS)
        画.paste(图, (x + (格宽 - 图.width) // 2, yy + 头))
    else:
        d.rectangle([x, yy + 头, x + 格宽, yy + 头 + 格高], outline=(255, 91, 91), width=2)
        d.text((x + 12, yy + 头 + 12), "缺", font=fb, fill=(255, 91, 91))

画.save(出图)
有 = sum(1 for _, _, _, 路 in 清单 if os.path.isfile(路))
print(f"  ✓ {出图}　{画.width}x{画.height}　{os.path.getsize(出图):,} B　{有}/{len(清单)} 张齐")
