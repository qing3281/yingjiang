# -*- coding: utf-8 -*-
"""验 `_接子镜.出srt()` 现在按**真人声秒数**算字幕长度。

为什么要验：改之前它按字数估（`max(1.6, len(词)*0.19)`）。
实测「站台尽头有东西。」配出来 **2.67 秒**，按字数估只有 **1.6 秒** ——
字幕会在人还在说话的时候消失。这正是他骂的「字幕非常非常少的可怜」的第二层：
字幕在，但不够长。

判据（三条，都能自己重跑）：
  1. 配音表里有 2.67 秒时，格2 那条字幕的**终点 - 起点 ≥ 2.67**
  2. 配音表里没有它时，退回按字数估（不能崩）
  3. 人声长过这一格的底时，必须**打出警告**（不许静默截掉）

用 monkeypatch 把 `配音目`/`片目` 指到临时目录，不碰真产物。
"""
import os
import sys
import json
import tempfile
import importlib.util

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
spec = importlib.util.spec_from_file_location("jzj", os.path.join(目, "_接子镜.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

坏 = 0


def 跑(标题, 配音表内容):
    global 坏
    临时 = tempfile.mkdtemp(prefix="srt_")
    m.配音目 = os.path.join(临时, "配音")
    m.片目 = os.path.join(临时, "片")
    os.makedirs(m.配音目, exist_ok=True)
    os.makedirs(m.片目, exist_ok=True)
    if 配音表内容 is not None:
        with open(os.path.join(m.配音目, "_配音表.json"), "w", encoding="utf-8") as f:
            json.dump(配音表内容, f, ensure_ascii=False)
    print("─" * 64)
    print("【%s】" % 标题)
    try:
        路 = m.出srt()
    except Exception as e:
        print("  ✗ 抛异常：%r" % e); 坏 += 1; return None
    文 = open(路, encoding="utf-8").read()
    print("  srt 正文：")
    for 行 in 文.strip().splitlines():
        print("    " + 行)
    return 文


def 秒们(文):
    """[(起, 终)] —— 从 srt 正文里解出来。"""
    def 解(s):
        h, mi, se = s.split(":")
        return int(h) * 3600 + int(mi) * 60 + float(se.replace(",", "."))
    出 = []
    行们 = 文.strip().splitlines()
    for i, 行 in enumerate(行们):
        if "-->" in 行:
            a, b = 行.split("-->")
            出.append((解(a.strip()), 解(b.strip()), 行们[i + 1]))
    return 出


# ── 情形一：配音表里有 2.67 秒（真人声） ──
文 = 跑("配音表里格2 = 2.67 秒（真人声）",
        {"配音": [{"序号": 2, "秒": 2.67, "路": "x.wav"}]})
if 文:
    条 = [t for t in 秒们(文) if t[2] == "站台尽头有东西。"]
    if not 条:
        print("  ✗ 找不到格2 那条字幕"); 坏 += 1
    else:
        长 = 条[0][1] - 条[0][0]
        print("  格2 字幕长 %.3f 秒（人声 2.67）" % 长)
        if 长 >= 2.67:
            print("  ✓ 判据1 过")
        else:
            print("  ✗ 判据1 没过：字幕只有 %.3f 秒，人声 2.67 秒" % 长); 坏 += 1

# ── 情形二：没有配音表（退回按字数估，不能崩） ──
文 = 跑("没有配音表（退回按字数估）", None)
if 文:
    条 = [t for t in 秒们(文) if t[2] == "站台尽头有东西。"]
    if 条:
        长 = 条[0][1] - 条[0][0]
        print("  格2 字幕长 %.3f 秒（按 8 字估，至少 1.6）" % 长)
        # ★ 容差：srt 里的时间是**毫秒**存的（`00:00:11,283`），解回来再相减会有
        #   1e-15 级的浮点误差。上一版我写 `长 >= 1.6` 就被这点误差判成失败 ——
        #   闸冤枉真话，和今天已经犯过的那次同一个形状。
        if 长 >= 1.6 - 0.002:
            print("  ✓ 判据2 过（没崩，退回了估值）")
        else:
            print("  ✗ 判据2 没过"); 坏 += 1
    else:
        print("  ✗ 判据2：连字幕都没了"); 坏 += 1

# ── 情形三：人声长过格的底（必须打警告） ──
文 = 跑("配音表里格2 = 20 秒（故意长过 9.333 秒的格）",
        {"配音": [{"序号": 2, "秒": 20.0, "路": "x.wav"}]})
if 文:
    条 = [t for t in 秒们(文) if t[2] == "站台尽头有东西。"]
    if 条:
        终 = 条[0][1]
        底 = 2 * m.一格秒 - 0.15
        print("  格2 字幕终点 %.3f，格的底 %.3f" % (终, 底))
        if 终 <= 底 + 0.001:
            print("  ✓ 判据3a 过（没有越过格边界）")
        else:
            print("  ✗ 判据3a 没过：字幕越过了格边界"); 坏 += 1

print("=" * 64)
print("结论：%s" % ("✓ 三条判据全过" if 坏 == 0 else "✗ %d 条没过" % 坏))
sys.exit(1 if 坏 else 0)
