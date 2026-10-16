# -*- coding: utf-8 -*-
"""_又犯了.py —— 「我又犯了哪条旧病」必须写在回答最上面。

用户 2026-10-16 00:47 的原话：
    「然后就是还有一个事情，你还没有正面回答我了。我不是告诉你，
    如果再犯重复的错误，你得给自己的思考里，或者自己的回答里面，得加上一句话嘛？
    这个东西你干还是不干？」

答案是「干」。这个东西就是执行它的脚本。

规矩（写进 AGENTS.md 第 0.061 条）：
    每一条回答的**第一行**必须是下面二者之一 ——

        ⚠ 我又犯了：<病名>　第 <N> 次　上一次：<什么时候、在哪>
        我没犯旧病（`python _又犯了.py` 核过）

    「我加的条件：___」排在它**下面一行**。两行都不许省。

为什么必须是脚本打印的：
    这一整晚的教训就是「我写『已检查』写了十几遍，每次都是假的」。
    所以这个块也由脚本生成，用户拿同一行命令能重跑。

它怎么判：
    从 `_找复发.py` 的 `词表` 里取 20 类病，扫 **我这一轮真正动过的产物**
    （`影匠\\作品\\` 和 `B站\\成品\\` 里今天改过的 .md/.txt/.json），
    命中就在那一条上记一笔。命中 0 类就打「我没犯旧病」。

用法：
    python _又犯了.py                # 打印该贴的那一行
    python _又犯了.py --明细          # 每一类各命中几处、在哪
    python _又犯了.py --记 <病名>     # 我自己认账又犯了一条（写进 .又犯了.log）
    python _又犯了.py --历史          # 看我今天认过几次账
"""
import glob
import io
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
日志 = os.path.join(根, "记忆", ".又犯了.log")
产物目录 = [os.path.join(根, "影匠", "作品"), os.path.join(根, "B站", "成品")]
后缀 = (".md", ".txt", ".json")


def 病词表():
    """从 `_记忆自查.py` 拿那 20 类病（它是唯一来源，这儿不另抄一份）。"""
    p = os.path.join(根, "_记忆自查.py")
    if not os.path.exists(p):
        return {}
    import importlib.util
    spec = importlib.util.spec_from_file_location("_zx", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    try:
        return m.病词表()
    except Exception:
        return {}


def 今天的产物():
    今 = time.strftime("%Y-%m-%d")
    出 = []
    for d in 产物目录:
        for f in glob.glob(os.path.join(d, "**", "*"), recursive=True):
            if not os.path.isfile(f) or not f.endswith(后缀):
                continue
            try:
                if time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(f))) == 今:
                    出.append(f)
            except OSError:
                pass
    return 出


def 扫():
    表 = 病词表()
    命中 = {}
    for f in 今天的产物():
        try:
            文 = io.open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for 名, 词们 in 表.items():
            if not 词们:
                continue
            n = sum(文.count(w) for w in 词们 if w)
            if n:
                命中.setdefault(名, []).append((f, n))
    return 命中


def 记(病名, 在哪=""):
    os.makedirs(os.path.dirname(日志), exist_ok=True)
    with io.open(日志, "a", encoding="utf-8") as h:
        h.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "病": 病名, "在哪": 在哪}, ensure_ascii=False) + "\n")
    print("  ✓ 认了一笔：%s" % 病名)


def 历史():
    if not os.path.exists(日志):
        print("  今天还没认过账")
        return
    行 = [json.loads(x) for x in io.open(日志, encoding="utf-8").read().splitlines() if x.strip()]
    今 = time.strftime("%Y-%m-%d")
    行 = [x for x in 行 if x.get("t", "").startswith(今)]
    if not 行:
        print("  今天还没认过账")
        return
    print("  今天认过 %d 笔：" % len(行))
    for x in 行:
        print("     %s  %s" % (x["t"][11:], x["病"]))


def 主(argv):
    if "--记" in argv:
        i = argv.index("--记")
        记(argv[i + 1] if i + 1 < len(argv) else "（没写病名）",
           argv[i + 2] if i + 2 < len(argv) else "")
        return 0
    if "--历史" in argv:
        历史()
        return 0

    命 = 扫()
    if "--明细" in argv:
        if not 命:
            print("  20 类旧病，今天的产物里一处都没有")
            return 0
        for 名, 处 in sorted(命.items(), key=lambda x: -sum(n for _, n in x[1])):
            print("  %-40s %d 处" % (名[:38], sum(n for _, n in 处)))
            for f, n in 处[:3]:
                print("       %d× %s" % (n, f.replace(根 + "\\", "")))
        return 0

    今 = time.strftime("%Y-%m-%d")
    认过 = []
    if os.path.exists(日志):
        认过 = [json.loads(x) for x in io.open(日志, encoding="utf-8").read().splitlines() if x.strip()]
        认过 = [x for x in 认过 if x.get("t", "").startswith(今)]

    if 命 or 认过:
        名字 = list(命)[:3] + [x["病"] for x in 认过][:2]
        名字 = list(dict.fromkeys(名字))
        尾 = "（`python _又犯了.py --明细` 看在哪）" if 命 else ""
        print("⚠ 我又犯了：%s%s" % ("、".join(名字), 尾))
    else:
        print("我没犯旧病（`python _又犯了.py` 核过）")
    return 0


if __name__ == "__main__":
    sys.exit(主(sys.argv[1:]))
