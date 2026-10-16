# -*- coding: utf-8 -*-
"""_出官方片.py —— 把「官方长片节点」跑出来的那条连续长片，配上我们自己的 32 句人声 + 硬字幕。

为什么要单独一个脚本：`_接子镜.py` 是给「128 段拼起来」那条线写的，它一上来先 `接片()`。
官方那条**本来就是一条连续的片子**，没有段可接 —— 只需要借它的 出srt / 混音 / 烧 三步。
所以这里 import `_接子镜`，把它的 `片目` / `成片` 两个全局**指到一个新文件夹**，
去调它那三个函数（能用就用、能抄就抄，不重写）。

产物都落在 `影匠\\作品\\楚子航\\片_官方\\`，**绝不动已经交付的那一版 `片\\`**。

用法：
    python _出官方片.py --查                只查远端落地了没（0 个中间文件、一次性落盘）
    python _出官方片.py --取                从远端拉最新那条到 _连片试\\，并打印时长/帧数
    python _出官方片.py --看                列出 _连片试 里的 mp4
    python _出官方片.py                     自动挑最新的一条，走完 出srt → 混音 → 烧
    python _出官方片.py --片 <本机绝对路径>   指定某一条
    python _出官方片.py --自动              = --查 → 有就 --取 → 再装配（落地那一刻一条命令收工）
"""
import os
import sys
import glob
import json
import time
import argparse
import urllib.parse
import urllib.request
import importlib.util

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
连片试 = r"D:\DSHworkspace\_连片试"
官方目 = os.path.join(目, "片_官方")
FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
远端 = "http://100.127.224.106:8188"

# 正在跑的那条的尺寸（写死成默认值，也能从 --总帧 覆盖）
总帧 = 7179
渲染窗 = 124
上下文 = 22


def 总窗数():
    步进 = 渲染窗 - 上下文
    return max(1, (总帧 + 步进 - 1) // 步进)


def 读正在跑的():
    """从远端 /queue 里读出正在跑的那个长片节点的链号和前缀。"""
    try:
        with urllib.request.urlopen(远端 + "/queue", timeout=15) as r:
            q = json.load(r)
    except Exception as e:
        print(f"（连不上远端：{e}）")
        return None, None
    for it in q.get("queue_running", []):
        for _k, n in (it[2] or {}).items():
            if n.get("class_type") == "MiniMaxH3LongVideoInNodeLoopEffectsT8Advanced":
                i = n["inputs"]
                return i.get("chain_id"), i.get("filename_prefix")
    return None, None


def 安全名(前缀):
    """把前缀按「非 ASCII 一个字符换一个下划线」洗一遍。

    ★ 但**不能只靠这个**：实测 `H3_连片_1016_1154` 远端落下来的是 `H3___1016_1154`（3 个下划线），
      而按上面这条规则算是 4 个。远端到底怎么合并的我不去猜 —— 所以 `探远端()` 会把
      1~6 个下划线全试一遍，试中就算数。
    """
    return "".join(c if (c.isascii() and (c.isalnum() or c in "._-")) else "_" for c in 前缀)


def 名字候选们(前缀):
    """给出所有合理的中文被洗掉后的前缀写法（下划线个数 1~6）。"""
    出 = []
    # 做法：把非 ASCII 段整段换成 k 个下划线，k 从 1 到 6
    import re
    for k in range(1, 7):
        s = re.sub(r"[^\x00-\x7f]+", "_" * k, 前缀)
        出.append(s)
    出.append(安全名(前缀))
    # 去重且保持顺序
    见, 去 = set(), []
    for s in 出:
        if s not in 见:
            见.add(s)
            去.append(s)
    return 去


def 探远端(链号, 前缀):
    """返回 (远端文件名, subfolder, 字节)；没落地返回 (None, sub, 0)。"""
    sub = "minimax_h3_t8_long_video/%s/assembled" % 链号
    n = 总窗数()
    for 安 in 名字候选们(前缀):
        for k in (n, n - 1, n + 1):
            fn = "%s_r%04d_cosine_bridge.mp4" % (安, k)
            q = urllib.parse.urlencode({"filename": fn, "subfolder": sub, "type": "output"})
            try:
                req = urllib.request.Request(远端 + "/view?" + q, method="HEAD")
                with urllib.request.urlopen(req, timeout=15) as r:
                    return fn, sub, int(r.headers.get("Content-Length") or 0)
            except Exception:
                continue
    return None, sub, 0


def 取片(链号, 前缀):
    fn, sub, 大 = 探远端(链号, 前缀)
    if not fn:
        return None
    os.makedirs(连片试, exist_ok=True)
    出 = os.path.join(连片试, "官方_%s.mp4" % 链号)
    if os.path.isfile(出) and os.path.getsize(出) == 大 and 大 > 0:
        print(f"   已经拉过了（{os.path.getsize(出):,} B）")
        return 出
    q = urllib.parse.urlencode({"filename": fn, "subfolder": sub, "type": "output"})
    print(f"   下载 {fn}（{大:,} B）→ {出}")
    临时 = 出 + ".part"
    urllib.request.urlretrieve(远端 + "/view?" + q, 临时)
    if os.path.getsize(临时) != 大:
        print(f"   ★ 拉下来的 {os.path.getsize(临时):,} B ≠ 远端 {大:,} B —— 不改名，留在 .part")
        return None
    os.replace(临时, 出)
    print(f"   ✓ {os.path.getsize(出):,} B")
    return 出


def 时长(路):
    try:
        import cv2
        c = cv2.VideoCapture(路)
        n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(c.get(cv2.CAP_PROP_FPS)) or 24.0
        c.release()
        return n / fps if n else -1.0
    except Exception:
        return -1.0


def 分辨率(路):
    try:
        import cv2
        c = cv2.VideoCapture(路)
        n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(c.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
        c.release()
        return [str(n), f"{w}x{h}"]
    except Exception:
        return ["?", "?"]


def 候选():
    出 = []
    for p in glob.glob(os.path.join(连片试, "**", "*.mp4"), recursive=True) + \
             glob.glob(os.path.join(连片试, "*.mp4")):
        if os.path.isfile(p) and not p.endswith(".part"):
            出.append((os.path.getmtime(p), p))
    出.sort(reverse=True)
    去重, 见过 = [], set()
    for m, p in 出:
        if p not in 见过:
            见过.add(p)
            去重.append((m, p))
    return 去重


def 载接子镜():
    p = os.path.join(目, "_接子镜.py")
    spec = importlib.util.spec_from_file_location("_接子镜官方", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["_接子镜官方"] = m
    spec.loader.exec_module(m)
    return m


def 装配(源):
    if not os.path.isfile(源):
        print(f"✗ 找不到 {源}")
        return 1
    秒 = 时长(源)
    宽高 = 分辨率(源)
    print(f"\n源片 {源}\n      {os.path.getsize(源):,} B　{秒:.2f} 秒　{'x'.join(宽高[:2])}")

    os.makedirs(官方目, exist_ok=True)
    接 = 载接子镜()
    接.片目 = 官方目                                   # ★ 把产物改道，不动交付版
    接.成片 = os.path.join(官方目, "楚子航_官方_成片_字幕.mp4")
    格秒 = 接.一格秒
    print(f"     一格秒 = {格秒:.4f}　32 格 = {32 * 格秒:.2f} 秒")
    if abs(秒 - 32 * 格秒) > 6:
        print(f"★ 注意：源片 {秒:.1f} 秒 和 32 格的 {32*格秒:.1f} 秒 差 "
              f"{秒 - 32*格秒:+.1f} 秒 —— 字幕/人声会和画面错位，先想清楚再往下走")

    print("\n① 出 srt")
    srt = 接.出srt()
    print("\n② 混音（32 句人声贴到官方那条的环境音上）")
    混 = 接.混音(源, srt)
    if not 混:
        print("✗ 混音没出片，停")
        return 1
    print("\n③ 烧硬字幕")
    成 = 接.烧(混, srt)
    if not 成:
        print("✗ 烧字幕没出片，停")
        return 1
    print(f"\n★ 官方版成片　{成}　{os.path.getsize(成):,} B　{时长(成):.2f} 秒")
    return 0


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--查", action="store_true")
    ap.add_argument("--取", action="store_true")
    ap.add_argument("--看", action="store_true")
    ap.add_argument("--自动", action="store_true")
    ap.add_argument("--片", default="")
    a = ap.parse_args()

    链号, 前缀 = 读正在跑的()
    还在跑 = bool(链号)
    if 链号:
        print(f"远端正在跑：链号 {链号}　前缀 {前缀}（洗成 {安全名(前缀)}）　共 {总窗数()} 个窗")
    else:
        print("远端 /queue 里没有正在跑的长片节点（可能已经跑完了）")
        链号, 前缀 = "chuzihang_20261016_115413", "H3_连片_1016_1154"
        print(f"　回落用上次记下的：链号 {链号}　前缀 {前缀}")

    落 = None
    if a.查 or a.取 or a.自动:
        fn, sub, 大 = 探远端(链号, 前缀)
        if fn:
            print(f"★ 远端已落地：{sub}/{fn}（{大:,} B）")
            落 = True
        else:
            print(f"✗ 远端还没落地（探了 {总窗数()} 号附近的名字，subfolder={sub}）")
            print("  那个节点是**一次性落盘**的，中途一个文件都不写 —— 所以只能等。")
            落 = False
        if a.查:
            return 0
        if not 落 and not a.自动:
            return 1
        if 落:
            取片(链号, 前缀)
        elif a.自动:
            print("\n还没落地，什么都不做。")
            return 0

    列 = 候选()
    print(f"\n`{连片试}` 里的 mp4：{len(列)} 条")
    for m, p in 列[:8]:
        w, h = 分辨率(p)[1].split("x") if "x" in 分辨率(p)[1] else ("?", "?")
        print(f"   {os.path.basename(p):<52} {os.path.getsize(p):>13,} B"
              f"　{时长(p):7.2f} 秒　{w}x{h}")
    if a.看:
        return 0
    if not 列:
        print("✗ 一条都没有 —— 官方那条还在远端跑？先用 `--取` 拉回来")
        return 1

    if a.片:
        return 装配(a.片)
    # 自动挑：优先挑「官方_」开头、时长最接近 32 格的
    首选 = [p for _m, p in 列 if os.path.basename(p).startswith("官方_")]
    池 = 首选 or [p for _m, p in 列]
    池.sort(key=lambda p: abs(时长(p) - 32 * 24.0 * 0 + 0))
    源 = max(池, key=lambda p: 时长(p))
    print(f"\n自动选中的源：{源}（{时长(源):.2f} 秒）")
    return 装配(源)


if __name__ == "__main__":
    sys.exit(主())
