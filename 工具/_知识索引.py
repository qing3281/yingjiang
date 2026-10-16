# -*- coding: utf-8 -*-
"""
_知识索引.py —— 让我「动手前先查知识库」这件事**有地方可查**，而不是靠我自觉。

## 为什么要有它

用户 2026-10-15 20:5x 原话（问了三次）：

    「你怎么保证以后你做一个任务的时候，不是看着任务就开始动手就做了，
      而是去先去自己的知识库也好，而是自己的技能区也好，去查询……」

    「你积累的知识经验不在以后加以运用，就是白干。
      给你了很多的文档内容参考，你不把它整理出来，加以利用，我也就是白给了。」

病根不是「没有知识」，是**知识躺在 137 份文件里、而我开工时看不见它们**。
`AGENTS.md` 第四节只列了 7 份「值得先看的」—— 剩下 130 份等于不存在。

## 它怎么工作

`影匠\\知识\\` 下每份 .md 抽三样东西存进 `影匠\\知识\\_索引.json`：
    · 标题（第一行 `#`）
    · 小标题（所有 `##` / `###`）
    · 关键词（正文里出现次数最高的中文词和英文标识符）

查的时候按命中位置加权：文件名 > 标题 > 小标题 > 关键词。

## 用法

    python _知识索引.py --建              重建索引（知识文件改了就重跑）
    python _知识索引.py --问 超分          查「做超分这件事该看哪几份」
    python _知识索引.py --问 字幕 --多 10
    python _知识索引.py --看              索引概况

★ 判据：**说「我查过知识库了」时必须能指到这个命令的这一次输出**，不是心里想过。
"""
import argparse
import io
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根
知识目 = os.path.join(根, "影匠", "知识")
索引路 = os.path.join(知识目, "_索引.json")

# 抽词时扔掉的：太常见、没信息量的
停 = set("""
的 了 是 在 和 与 或 也 都 就 而 及 等 被 把 让 给 对 从 到 有 没有 一个 一些 这个 那个 这些 那些
我 你 他 她 它 我们 你们 他们 这 那 什么 怎么 为什么 因为 所以 但是 如果 那么 现在 可以 需要 应该
要 会 能 不 没 很 更 最 太 再 又 还 只 才 就是 这样 那样 一起 已经 正在 还是 或者 然后 之后 之前
上 下 里 外 中 内 前 后 左 右 大 小 多 少 好 坏 新 旧 真 假 一 二 三 四 五 六 七 八 九 十
未 用 做 走 来 去 看 说 写 想 知道 时候 问题 地方 东西 事情 方式 方法 情况 结果 部分 内容
the a an of to in on at is are was were be been for with and or if then this that it its as by from
""".split())


def 抽词(文):
    """英文标识符 + 中文 2~4 字词，按出现次数排。"""
    数 = {}
    for w in re.findall(r"[A-Za-z_][A-Za-z0-9_\-\.]{2,}", 文):
        w = w.lower()
        if w in 停:
            continue
        数[w] = 数.get(w, 0) + 1
    for 段 in re.findall(r"[\u4e00-\u9fff]{2,}", 文):
        for n in (4, 3, 2):
            for i in range(len(段) - n + 1):
                w = 段[i:i + n]
                if w in 停:
                    continue
                数[w] = 数.get(w, 0) + 1
    # 长的优先（信息量大），出现 >=2 次的才算
    出 = [(w, c) for w, c in 数.items() if c >= 2 and len(w) >= 2]
    出.sort(key=lambda x: (-x[1], -len(x[0])))
    # 去掉被更长词包含的短词（「超分」在「视频超分」已有时降权）
    留 = []
    已 = []
    for w, c in 出:
        if any(w in L for L in 已):
            continue
        留.append(w)
        已.append(w)
        if len(留) >= 40:
            break
    return 留


def 读一份(p):
    文 = io.open(p, encoding="utf-8", errors="replace").read()
    行s = 文.split("\n")
    标题 = ""
    for l in 行s[:40]:
        m = re.match(r"^#\s+(.+)$", l.strip())
        if m:
            标题 = m.group(1).strip()
            break
    小 = [m.group(1).strip() for m in
          (re.match(r"^#{2,3}\s+(.+)$", l.strip()) for l in 行s) if m][:60]
    return 文, 标题, 小[:60]


def 建():
    if not os.path.isdir(知识目):
        print(f"✗ 没有 {知识目}")
        return 1
    条 = []
    n = 0
    for dp, dn, fn in os.walk(知识目, onerror=lambda e: None):
        for f in sorted(fn):
            if not f.endswith(".md") or f.startswith("_"):
                continue
            p = os.path.join(dp, f)
            try:
                文, 标题, 小 = 读一份(p)
            except Exception as e:
                print(f"  ✗ 读不了 {f}：{e}")
                continue
            n += 1
            条.append({
                "名": f,
                "相对": os.path.relpath(p, 知识目).replace("\\", "/"),
                "大小": os.path.getsize(p),
                "标题": 标题,
                "小标题": 小,
                "关键词": 抽词(文),
                "mtime": int(os.path.getmtime(p)),
            })
    os.makedirs(知识目, exist_ok=True)
    io.open(索引路, "w", encoding="utf-8").write(json.dumps({
        "建时": time.strftime("%Y-%m-%d %H:%M:%S"),
        "份数": len(条),
        "总字节": sum(x["大小"] for x in 条),
        "条": 条,
    }, ensure_ascii=False, indent=1))
    print(f"✓ 索引了 {n} 份知识 → {索引路}")
    print(f"  索引文件 {os.path.getsize(索引路):,} B")
    print(f"  知识总量 {sum(x['大小'] for x in 条)/2**20:.1f} MiB")
    return 0


def 载():
    if not os.path.isfile(索引路):
        return None
    try:
        return json.load(io.open(索引路, encoding="utf-8"))
    except Exception:
        return None


def 查(词s, 多=8):
    """词s = 一串关键词（空格或顿号分隔都行）。返回 [(分数, 条目, 为什么)]"""
    索 = 载()
    if not 索:
        return None
    q = [w for w in re.split(r"[\s、,，/]+", 词s.strip()) if w]
    if not q:
        return []
    出 = []
    for it in 索["条"]:
        名 = it["名"]; 标题 = it["标题"]; 小 = it["小标题"]; 关 = it["关键词"]
        分 = 0
        由 = []
        for w in q:
            lw = w.lower()
            if lw in 名.lower():
                分 += 12; 由.append(f"文件名有「{w}」")
            if lw in 标题.lower():
                分 += 8; 由.append(f"标题有「{w}」")
            命小 = [t for t in 小 if lw in t.lower()]
            if 命小:
                分 += 4 * min(3, len(命小)); 由.append(f"小标题有「{w}」×{len(命小)}")
            if lw in [k.lower() for k in 关]:
                分 += 3; 由.append(f"关键词有「{w}」")
            elif any(lw in k.lower() or k.lower() in lw for k in 关):
                分 += 1; 由.append(f"关键词近「{w}」")
        if 分:
            出.append((分, it, 由))
    出.sort(key=lambda x: -x[0])
    return 出[:多]


def 看():
    索 = 载()
    if not 索:
        print("还没有索引，先跑 `python _知识索引.py --建`")
        return 1
    print(f"索引建于 {索['建时']}，{索['份数']} 份，{索['总字节']/2**20:.1f} MiB")
    按 = {}
    for it in 索["条"]:
        d = it["相对"].split("/")[0] if "/" in it["相对"] else "(根)"
        按[d] = 按.get(d, 0) + 1
    print("\n按子目录：")
    for d, c in sorted(按.items(), key=lambda x: -x[1]):
        print(f"    {d:<32} {c:>4} 份")
    print("\n最大的 12 份：")
    for it in sorted(索["条"], key=lambda x: -x["大小"])[:12]:
        print(f"    {it['大小']/2**10:>8.0f} KiB  {it['相对']}")
    return 0


def 主():
    参 = argparse.ArgumentParser()
    参.add_argument("--建", action="store_true")
    参.add_argument("--问", default="")
    参.add_argument("--看", action="store_true")
    参.add_argument("--多", type=int, default=8)
    a = 参.parse_args()
    if a.建:
        return 建()
    if a.看:
        return 看()
    if a.问:
        出 = 查(a.问, a.多)
        if 出 is None:
            print("还没有索引，先跑 `python _知识索引.py --建`")
            return 1
        if not 出:
            print(f"「{a.问}」在 {载()['份数']} 份知识里没有命中。")
            return 0
        print(f"「{a.问}」相关 {len(出)} 份（分数高 = 越该先看）：")
        for 分, it, 由 in 出:
            print(f"  [{分:>3}] {it['相对']}")
            if it["标题"]:
                print(f"        {it['标题']}")
            print(f"        {it['大小']/2**10:.0f} KiB · " + "；".join(dict.fromkeys(由))[:110])
        print()
        print("★ 说「我查过知识库」时必须能指到上面这几行。")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(主())
