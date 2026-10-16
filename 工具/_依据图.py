# -*- coding: utf-8 -*-
"""
把「依据窗」此刻显示的内容画成一张 PNG —— 好让用户在他的聊天里直接看见，
不用去桌面上找那个小窗。

用法： python _依据图.py [输出路径]
"""
import json
import os
import sys
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

接口 = "http://127.0.0.1:8794/api/now"
出 = sys.argv[1] if len(sys.argv) > 1 else r"D:\DSHworkspace\记忆\归档\归档\截图\依据窗_内容.png"

W, H = 392, 1000
底 = (18, 20, 26)
顶底 = (23, 26, 33)
正 = (223, 227, 234)
淡 = (125, 134, 152)
亮 = (234, 240, 250)
标 = (159, 176, 201)
坏 = (255, 123, 114)
警 = (255, 179, 92)
径 = (199, 208, 222)
名 = (143, 208, 255)
钟 = (93, 102, 117)
类色 = {"读": (95, 224, 160), "写": (255, 179, 92), "跑": (199, 155, 255),
        "查": (95, 208, 224), "其它": (154, 164, 181)}

字 = r"C:\Windows\Fonts\msyh.ttc"
等 = r"C:\Windows\Fonts\consola.ttf"


def 载(路, 号):
    try:
        return ImageFont.truetype(路, 号)
    except Exception:
        return ImageFont.load_default()


f9 = 载(字, 13)
f8 = 载(字, 12)
f13 = 载(字, 18)
f9b = 载(字, 13)
# 路径一律用中文字体：Consolas 没有汉字，路径里的中文会变成一排 □
f等 = 载(字, 11)
f等b = 载(字, 11)


def 取():
    with urllib.request.urlopen(接口, timeout=5) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def 时(t):
    if not t:
        return ""
    try:
        return time.strftime("%H:%M:%S", time.localtime(t / 1000))
    except Exception:
        return ""


def 主():
    数 = 取()
    图 = Image.new("RGB", (W, H), 底)
    笔 = ImageDraw.Draw(图)

    # 顶栏
    笔.rectangle([0, 0, W, 36], fill=顶底)
    笔.text((12, 10), "依据", font=f9b, fill=亮)
    笔.text((46, 12), "这一轮读了哪些文件 · 做了什么", font=f8, fill=淡)
    笔.text((W - 60, 12), time.strftime("%H:%M:%S"), font=f8, fill=淡)

    y = 46
    行距 = 17

    def 写(文, 字, 色, x=12, 换行=True):
        nonlocal y
        笔.text((x, y), 文, font=字, fill=色)
        if 换行:
            y += 行距

    工 = 数.get("工具") or []
    读 = 数.get("读过") or []
    类 = 数.get("按类") or {}
    空 = 数.get("空转") or 0
    段 = max(1, 数.get("推理段") or 1)
    每 = 空 / 段

    写(f"{数.get('会话','')[:8]}", f8, 淡, 换行=False)
    y += 行距

    y += 6
    笔.text((12, y), f"{len(工)}", font=f13, fill=亮)
    w1 = 笔.textlength(f"{len(工)}", font=f13)
    笔.text((12 + w1 + 6, y + 4), "次工具", font=f8, fill=淡)
    x2 = 12 + w1 + 6 + 笔.textlength("次工具", font=f8) + 16
    笔.text((x2, y), f"{len(读)}", font=f13, fill=亮)
    w2 = 笔.textlength(f"{len(读)}", font=f13)
    笔.text((x2 + w2 + 6, y + 4), "份文件", font=f8, fill=淡)
    y += 30

    写(f"读 {类.get('读',0)}   ·   写 {类.get('写',0)}   ·   跑 {类.get('跑',0)}"
       f"   ·   查 {类.get('查',0)}   ·   轮 {数.get('轮',0)}", f8, 淡)
    色 = 正 if 每 < 0.5 else (警 if 每 < 5 else 坏)
    笔.text((12, y), "空转 ", font=f8, fill=淡)
    wx = 12 + 笔.textlength("空转 ", font=f8)
    笔.text((wx, y), f"{空}", font=f8, fill=色)
    wx += 笔.textlength(f"{空}", font=f8)
    笔.text((wx, y), f" 次（每段 {每:.1f}）", font=f8, fill=淡)
    尾巴 = "  ✓ 达标" if 每 < 0.5 else "  ✗ 超标"
    笔.text((wx + 笔.textlength(f" 次（每段 {每:.1f}）", font=f8), y), 尾巴, font=f8, fill=色)
    y += 26

    def 节(题):
        nonlocal y
        笔.text((12, y), 题, font=f9b, fill=标)
        y += 16
        笔.line([12, y, W - 12, y], fill=(36, 41, 54))
        y += 8

    节("我读过哪些文件")
    if not 读:
        写(" 这一轮还没读过文件。", f8, 淡)
    for x in list(reversed(读))[:40]:
        笔.text((12, y), f"{x.get('名','')[:10]}", font=f等b, fill=名)
        z = (x.get("目") or "")[:150]
        笔.text((12 + 76, y), z, font=f等, fill=径)
        y += 15
    y += 10

    节("全部动作（最近 60 次）")
    for x in list(reversed(工))[:60]:
        k = x.get("类", "其它")
        笔.text((12, y), k, font=f8, fill=类色.get(k, 淡))
        笔.text((34, y), f"{x.get('名','')[:14]}", font=f等b, fill=名)
        笔.text((W - 70, y), 时(x.get("时")), font=f等, fill=钟)
        y += 15
        目 = (x.get("目") or "").strip()
        if 目:
            笔.text((40, y), 目[:60], font=f等, fill=径)
            y += 15
        if y > H - 40:
            break

    if y < H - 30:
        笔.text((12, H - 24), " DSH 自己记的 tool/call，我改不了。", font=f8, fill=淡)

    os.makedirs(os.path.dirname(出), exist_ok=True)
    图.save(出)
    print(f"  ✓ {出}  ({os.path.getsize(出):,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(主())
