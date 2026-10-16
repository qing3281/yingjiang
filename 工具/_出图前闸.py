# -*- coding: utf-8 -*-
"""_出图前闸.py —— 提交出图 / 出段**之前**必须过的那道闸。

用户 2026-10-16 04:15 的原话：
    「让这个阅读这些红线这些问题，这些经验……能够在你的日常对话中也能记得去读，
      你想一想有没有什么办法……比如每一个小时去读一次这样的方式吗？」
    → 04:16 我回的是：**病根不是「我没读到」，是「读到了，也没有任何东西拦我」。**
    → 04:17 他说：「可以的。两个我都要。」

所以这一版不做「每小时读一遍」（那是墙纸），做**闸**：
    读一遍拦不住我，退出码能。

依据：`_判据挂命令.py` 里那张「病 → 跑哪条命令」的表。那一步已经把命令挂到词表上了，
        缺的只是**在提交那一刻真的去跑，报红就停**。

────────── 怎么算「过」──────────
每一条检查器都是一个**子进程**，判据是它的**退出码**：
    0 = 过　非 0 = 红 —— ★ 整道闸返回非 0，提交方**不许继续**。

有两个老脚本永远退 0（`_总检查.py`、`_记忆自查.py`），
对这种只能**解析它自己打印的那行合计**。解析字符串脆，所以这两条在下面写明了是解析，
而且解析不到 = **算红**（不许「没看懂就当过了」—— 那正是第 0.05 条第一个病）。

────────── 用法 ──────────
    python _出图前闸.py --作品 楚子航          # 过闸（退出码 0 才放行）
    python _出图前闸.py --作品 楚子航 --看      # 只列会跑哪几条，不跑
    python _出图前闸.py --自检                 # ★ 证明这道闸真的会红，不是摆设
"""
import argparse
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

W = r"D:\DSHworkspace"
PY = sys.executable
页 = os.path.join(W, "_出图前闸.md")
日志 = os.path.join(W, "_出图前闸.log")


def 排检查器(作品):
    """(病名, 命令, 判定方式)　判定方式：'码' = 看退出码；'析' = 解析它打印的合计"""
    目 = os.path.join(W, "影匠", "作品", 作品)
    列 = [
        ("假字 / 假字幕 —— 提示词里给模型留了「该有字」的缺口（会画出一堆乱码）",
         [PY, "-X", "utf8", os.path.join(W, "_查假字.py"), "--作品", 作品], "码"),
        ("无名指代 —— 「一个女孩」这种写法会画成两个人（格21 多出一个夏弥就是这么来的）",
         [PY, "-X", "utf8", os.path.join(W, "_查无名指代.py"), "--作品", 作品], "码"),
        ("产物里残留的旧病词（否定写法等）—— 扫的是产物，不含我自己的笔记",
         [PY, "-X", "utf8", os.path.join(W, "_记忆自查.py")], "析", "今天在产物里扫到的旧病：0 处"),
    ]
    # `_总检查.py` 把作品路径**写死成楚子航**了（第 5 行）。别的作品跑它会查错人 ——
    # 那比不查更坏，所以这里明说，不静默套用。
    if 作品 == "楚子航":
        列.insert(0, ("公共段落 / 逐格 17 条（九宫格 · 写作规约 · 挑角色）",
                      [PY, "-X", "utf8", os.path.join(W, "_总检查.py")], "析", "合计 0 处"))
    else:
        列.insert(0, ("公共段落 / 逐格 17 条 —— ★ 跳过：`_总检查.py` 把作品写死成楚子航，"
                      "对《%s》跑它会查错人" % 作品, None, "跳"))
    return 列, 目


def 跑一条(名, 命令, 方式, 期望=None):
    t0 = time.time()
    r = subprocess.run(命令, capture_output=True)
    秒 = time.time() - t0
    出 = (r.stdout or b"").decode("utf-8", "replace")
    错 = (r.stderr or b"").decode("utf-8", "replace")
    if 方式 == "码":
        过 = r.returncode == 0
        证 = "退出码 %d" % r.returncode
    else:
        过 = 期望 in 出
        证 = ("打印里有「%s」" % 期望) if 过 else ("★ 打印里**找不到**「%s」—— 按红算（不许「没看懂当过了」）" % 期望)
    # ★ 上一版没有这一项，「跑得起来」是拿 `能跑 += 1` 无条件数的 ——
    #   于是自检打出「真检查器都跑得起来 ✓」而左边明明是 ✗。**这就是假判据本身。**
    #   真的「跑得起来」判据只有一条：stderr 里没有 Traceback（崩了才是没跑起来）。
    崩 = "Traceback" in 错
    return 过, 证, 秒, 出, 错, 崩


def 写页(作品, 结论, 条):
    行 = ["# 出图前闸　%s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
    行.append("- 作品：**%s**" % 作品)
    行.append("- 结论：**%s**" % 结论)
    行.append("- 重跑：`python _出图前闸.py --作品 %s`" % 作品)
    行.append("")
    行.append("| 过 | 检查器 | 判据 |")
    行.append("|---|---|---|")
    for 过, 名, 证, _ in 条:
        行.append("| %s | %s | %s |" % ("✓" if 过 else "✗", 名, 证))
    行.append("")
    行.append("### 为什么要有这道闸")
    行.append("")
    行.append("`_开工.py` 每次开工都念那 19 类复发，念得一字不差 —— 照样犯。")
    行.append("**读一遍拦不住我，退出码能。** 所以每一条检查器都是一个子进程，看它的退出码；")
    行.append("报红就返回非 0，提交方不许继续。")
    with open(页, "w", encoding="utf-8") as f:
        f.write("\n".join(行) + "\n")


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--作品", default="楚子航")
    ap.add_argument("--看", action="store_true")
    ap.add_argument("--自检", action="store_true")
    a = ap.parse_args()

    if a.自检:
        return 自检()

    列, 目 = 排检查器(a.作品)
    print("═" * 74)
    print("  出图前闸　作品《%s》　%s" % (a.作品, time.strftime("%m-%d %H:%M:%S")))
    print("═" * 74)

    if a.看:
        for i, x in enumerate(列, 1):
            if len(x) == 3 and x[2] == "跳":
                print("  %d. · %s" % (i, x[0]))
            else:
                print("  %d. %s" % (i, x[0]))
                print("       跑：%s" % " ".join(x[1]))
        print()
        print("  （--看：一条都没跑）")
        return 0

    条 = []
    for x in 列:
        名 = x[0]
        if len(x) == 3 and x[2] == "跳":
            print("  · 跳过　%s" % 名)
            continue
        命令, 方式 = x[1], x[2]
        期望 = x[3] if len(x) > 3 else None
        print()
        print("  ▶ %s" % 名)
        过, 证, 秒, 出, 错, 崩 = 跑一条(名, 命令, 方式, 期望)
        print("    %s %s　（%.1f 秒）" % ("✓ 过" if 过 else "✗ 红", 证, 秒))
        if not 过:
            # 把证据也打出来 —— 报红必须能指到具体哪一格哪一处
            证行 = [l for l in 出.splitlines() if l.strip().startswith(("✗", "★", "【"))]
            for l in (证行[:8] or 出.strip().splitlines()[-8:]):
                print("      " + l[:150])
            if 错.strip():
                print("      错| " + 错.strip().splitlines()[-1][:150])
        条.append((过, 名, 证, 秒))

    红 = [x for x in 条 if not x[0]]
    结论 = "放行（%d 条全过）" % len(条) if not 红 else "★ 拦住 —— %d 条红" % len(红)
    print()
    print("═" * 74)
    print("  结论：%s" % 结论)
    print("═" * 74)
    写页(a.作品, 结论, 条)
    with open(日志, "a", encoding="utf-8") as f:
        f.write("[%s] 作品=%s %s\n" % (time.strftime("%m-%d %H:%M:%S"), a.作品, 结论))
    print("  页 → %s" % 页)
    return 1 if 红 else 0


def 自检():
    """★ 证明这道闸真的会红。

    一个**永远不红的闸**跟没有闸是一样的 —— 这正是「判据说 OK，其实什么都没量」。
    所以这里塞一条**故意失败**的假检查器进去，看闸会不会拦。

    诚实标注：验的是**闸的判定和退出码**，不是各检查器本身的准头（那是另一件事）。
    """
    print("═" * 74)
    print("  出图前闸 · 自检")
    print("═" * 74)
    假 = os.path.join(W, "_闸自检_故意失败.py")
    with open(假, "w", encoding="utf-8") as f:
        f.write("# 自检用的假检查器：永远返回 1（红）\nimport sys\nsys.exit(1)\n")
    过1, 证1, _, _, _, _ = 跑一条("假", [PY, 假], "码")
    print("  · 假检查器（永远退 1）→ 闸判它是：%s　%s" % ("过" if 过1 else "红", 证1))
    os.remove(假)

    真, _ = 排检查器("楚子航")
    真 = [(x[0], x[1], x[2], x[3] if len(x) > 3 else None) for x in 真 if x[2] != "跳"]
    print("  · 真的 %d 条检查器逐条跑（红绿都算正常，**崩**才是不合格）：" % len(真))
    崩了 = []
    for 名, 命令, 方式, 期望 in 真:
        过, 证, 秒, _, 错, 崩 = 跑一条(名, 命令, 方式, 期望)
        if 崩:
            崩了.append(名)
        print("      %s %-44s %.1f 秒　%s"
              % ("✓过" if 过 else "✗红", 名[:44], 秒, "★ 崩了" if 崩 else 证[:44]))

    print()
    a = (not 过1)
    b = (not 崩了)
    print("  判据 1　假检查器被闸判成红：%s" % ("✓" if a else "★ 否 —— 这闸根本不会红，是摆设"))
    print("  判据 2　真检查器一条都没崩（红绿不算崩）：%s%s"
          % ("✓" if b else "★ 否 —— 崩的是：%s" % 崩了, "" if b else ""))
    print("═" * 74)
    print("  自检 %s" % ("通过" if (a and b) else "★ 不通过"))
    return 0 if (a and b) else 1


if __name__ == "__main__":
    sys.exit(主())
