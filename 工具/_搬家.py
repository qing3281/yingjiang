# -*- coding: utf-8 -*-
"""_搬家.py —— 把根目录的 232 个散文件 + 21 个文件夹，收成 5 个文件夹。

用户原话（2026-10-16 22:41）：
「你根目录里面放了200多个文件，你觉得这对吗？你把根目录的文件给我文件夹，
把它们放到很多的相似的相同的，或者是有关联的，放到一个文件夹里面去。文件夹我顶多要5个。
py文件更别放到个陌录里。什么文件都放在一起，你让谁去看？」

目标形态：
    D:\\DSHworkspace\\
      AGENTS.md          必须在根（DSH 每次自动注入）
      交接.md            ★ 下一个 AI 先读这个
      记忆\\              ★ 他对我的要求 + 我犯过的错 + 经验 + 记忆 + 归档 + 会话存档 + 研究
      影匠\\              影视产线
      B站\\               发布
      工具\\              全部脚本
      素材\\              网盘 / 本地AI / 下载 / 字体 / 远程装机 / 片场

跑法：`python _搬家.py`（干跑，只打印计划）　`python _搬家.py --真跑`
"""
import glob
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
真 = "--真跑" in sys.argv
备份 = os.path.join(根, "记忆", "归档", "搬家前")

# ── ① 目录：旧名 → 新家 ───────────────────────────────────────────
挪的目录 = [
    ("网盘", "素材"),
    ("本地AI", "素材"),
    ("downloads", "素材\\下载"),
    ("_字体", "素材\\字体"),
    ("远程装机包", "素材\\远程装机包"),   # ★ 长的写在短的前面
    ("远程", "素材\\远程"),
    ("片场", "素材\\片场"),
    ("_运行时", "工具\\_运行时"),
    ("会话存档", "记忆"),
    ("研究", "记忆"),
    ("_归档", "记忆\\归档"),
    ("仓库", "记忆"),
    ("_GitHub", "记忆"),
]

# 空目录直接删
删的空目录 = ["_出连片", "_对比"]

# ── ② 根文件：按名字/后缀分流 ────────────────────────────────────
留根 = {"AGENTS.md", "交接.md"}

进记忆的MD = {
    "要求台账.md", "要求台账.bak-雪线第2句-20261015-073530.md", "用户画像.md",
    "计划.md", "计划_你要的东西.md", "任务单.md", "接续.md",
    "欠账总表.md", "欠账总表.html", "_待你点头.md", "_等Agent.md", "_等你定夺.md",
    "_我看明白了.md", "龙族_夏弥之死_原文核对.md", "预算_觉醒开头.md",
    "交接_楚子航产线.md", "_验收.html",
    "_大扫除_复验.txt", "_大扫除_真跑.txt", "_理知识库.txt", "_验交接.txt",
    "_出图前闸.md",
}

进工具的尾巴 = {".py", ".cmd", ".ps1", ".json", ".log", ".bat"}

# 这几个后缀不在上面，但也要进 `工具\`
进工具的 = {"_保命清单.txt", "_活工具.txt", "_清理清单.md", "_dsh启动输出.txt"}

直接删的 = {
    "_插件已加载.log.bak-手动测试那次",
    "_找复发.py.bak-20261016-003903",
    "影匠控制台.cmd.bak-20261015",
    "_dsh启动错误.txt",          # 0 字节
}

# 重命名（搬进去之后叫什么）
改名 = {"downloads": "下载", "_字体": "字体", "_归档": "归档", "会话存档": "会话存档", "研究": "研究"}


def 大小(p):
    try:
        if os.path.isfile(p):
            return os.path.getsize(p)
        n = 0
        for b, _d, fs in os.walk(p):
            for f in fs:
                try:
                    n += os.path.getsize(os.path.join(b, f))
                except OSError:
                    pass
        return n
    except OSError:
        return 0


def 人(n):
    for u in ("B", "K", "M", "G"):
        if n < 1024:
            return "%.1f%s" % (n, u)
        n /= 1024.0
    return "%.1fP" % n


def 挪(源, 目标目录, 新名=None):
    """同卷 rename；目标已存在就报错不覆盖。"""
    目标 = os.path.join(目标目录, 新名 or os.path.basename(源))
    if os.path.exists(目标):
        print("    ✗ 目标已存在，跳过：%s" % 目标)
        return False
    if not 真:
        print("    · %s  →  %s" % (os.path.relpath(源, 根), os.path.relpath(目标, 根)))
        return True
    try:
        os.makedirs(目标目录, exist_ok=True)
        os.replace(源, 目标)
        print("    ✓ %s  →  %s" % (os.path.relpath(源, 根), os.path.relpath(目标, 根)))
        return True
    except OSError as e:
        print("    ✗ %s：%s" % (os.path.relpath(源, 根), e))
        return False


# ── ③ 引用改写表 ───────────────────────────────────────────────────
def 造替换表():
    表 = {}

    def 加(旧, 新):
        表["D:\\DSHworkspace\\" + 旧] = "D:\\DSHworkspace\\" + 新
        表["D:/DSHworkspace/" + 旧] = "D:/DSHworkspace/" + 新

    for 旧, 新家 in 挪的目录:
        加(旧, (新家 + "\\" + 改名.get(旧, 旧)))
    # 根文件一个个点名的一批
    for n in sorted(进记忆的MD):
        加(n, "记忆\\" + n)
    # 根目录所有要进工具的散文件
    for p in glob.glob(os.path.join(根, "*")):
        if not os.path.isfile(p):
            continue
        n = os.path.basename(p)
        if n in 留根 or n in 进记忆的MD or n in 直接删的:
            continue
        if os.path.splitext(n)[1].lower() in 进工具的尾巴 or n in 进工具的:
            加(n, "工具\\" + n)
    return 表


def 改写引用(表):
    """把所有提到旧路径的文件改过来。只碰 ≤2 MB 的文本文件。"""
    后缀 = (".py", ".cmd", ".ps1", ".bat", ".json", ".md", ".txt", ".html", ".yaml", ".yml", ".js", ".mjs")
    扫的 = []
    for 子 in ("", "影匠", "B站", "工具", "记忆"):
        底 = os.path.join(根, 子) if 子 else 根
        for 模式 in ("*", "**/*"):
            扫的 += glob.glob(os.path.join(底, 模式), recursive=("**" in 模式))
    扫的 = sorted(set(扫的))

    改过 = []
    for p in 扫的:
        if not os.path.isfile(p) or os.path.splitext(p)[1].lower() not in 后缀:
            continue
        try:
            if os.path.getsize(p) > 2 * 1024 * 1024:
                continue
            t0 = open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        t = t0
        for 旧, 新 in sorted(表.items(), key=lambda kv: -len(kv[0])):
            if 旧 in t:
                t = t.replace(旧, 新)
        # 文档里「python _xxx.py」这种裸名字
        import re
        if p.lower().endswith((".md", ".txt", ".html")):
            t = re.sub(r"(python\s+)(_[\w\u4e00-\u9fff]+\.py)", r"\1工具\\\2", t)
            t = re.sub(r"(python\s+)(check_[\w\u4e00-\u9fff]+\.py)", r"\1工具\\\2", t)
        if t != t0:
            改过.append((os.path.relpath(p, 根), sum(1 for a, b in 表.items() if a in t0)))
            if 真:
                # ★ 改之前先留一份原件 —— 路径前缀替换是纯文本操作，但覆盖就回不去了
                q = os.path.join(备份, os.path.relpath(p, 根))
                os.makedirs(os.path.dirname(q), exist_ok=True)
                if not os.path.exists(q):
                    shutil.copy2(p, q)
                open(p, "w", encoding="utf-8").write(t)
    return 改过


def 修根行():
    """19 个脚本写的是 `根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根` ——
    它们原来住在根目录，搬进 `工具\\` 之后要**再往上一级**。"""
    旧 = "根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根"
    新 = "根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\\ 的上一级 = 工作区根"
    改 = []
    for p in glob.glob(os.path.join(根, "_*.py")) + glob.glob(os.path.join(根, "check_*.py")):
        try:
            t0 = open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if 旧 in t0:
            t = t0.replace(旧, 新)
            if 真:
                open(p, "w", encoding="utf-8").write(t)
            改.append(os.path.basename(p))
    return 改


def 主():
    print("★ %s\n" % ("真跑" if 真 else "干跑（什么都没动；加 --真跑 才动）"))

    print("── ① 挪文件夹 ──")
    for 旧, 新家 in 挪的目录:
        s = os.path.join(根, 旧)
        if not os.path.isdir(s):
            print("    （没有）%s" % 旧)
            continue
        print("  %-12s %8s → %s\\" % (旧, 人(大小(s)), 新家))
    print("")

    print("── ② 根文件分流 ──")
    n记忆 = n工具 = n删 = n留 = 0
    for p in sorted(glob.glob(os.path.join(根, "*"))):
        if not os.path.isfile(p):
            continue
        n = os.path.basename(p)
        if n in 留根:
            n留 += 1
        elif n in 直接删的:
            n删 += 1
        elif n in 进记忆的MD:
            n记忆 += 1
        elif os.path.splitext(n)[1].lower() in 进工具的尾巴 or n in 进工具的:
            n工具 += 1
        else:
            print("    ？没归类：%s" % n)
    print("    留根 %d 个　→记忆\\ %d 个　→工具\\ %d 个　删 %d 个" % (n留, n记忆, n工具, n删))
    print("")

    print("── ③ 引用改写表 %d 条 ──" % len(造替换表()))
    print("")

    if not 真:
        print("（干跑到此为止。加 --真跑 执行。）")
        return 0

    print("── 执行 ──")
    print("[1/4] 改写引用")
    改过 = 改写引用(造替换表())
    print("      改了 %d 个文件" % len(改过))
    for k, v in 改过[:15]:
        print("        %-56s %d 条" % (k, v))
    if len(改过) > 15:
        print("        … 还有 %d 个" % (len(改过) - 15))

    print("[2/4] 修「根 = __file__」的脚本")
    改 = 修根行()
    print("      %d 个：%s" % (len(改), "、".join(改[:8]) + ("…" if len(改) > 8 else "")))

    print("[3/4] 挪文件夹")
    for 旧, 新家 in 挪的目录:
        s = os.path.join(根, 旧)
        if os.path.isdir(s):
            # ★ 新家已经带了最终名字，不能再传 改名 —— 第一版就是两个都传，
            #   结果出来 `素材\下载\下载` 这种套一层的（已修）
            挪(s, os.path.join(根, 新家))
    print("[4/4] 挪根文件")
    for p in sorted(glob.glob(os.path.join(根, "*"))):
        if not os.path.isfile(p):
            continue
        n = os.path.basename(p)
        if n in 留根:
            continue
        if n in 直接删的:
            try:
                os.remove(p)
                print("    ✓ 删 %s" % n)
            except (PermissionError, OSError) as e:
                print("    · 跳过（占用中）%s　%s" % (n, e.strerror or e))
        elif n in 进记忆的MD:
            挪(p, os.path.join(根, "记忆"))
        elif os.path.splitext(n)[1].lower() in 进工具的尾巴 or n in 进工具的:
            挪(p, os.path.join(根, "工具"))
    for d in 删的空目录:
        q = os.path.join(根, d)
        if os.path.isdir(q) and not os.listdir(q):
            os.rmdir(q)
            print("    ✓ 删空目录 %s" % d)

    print("")
    print("=== 根目录现在 ===")
    for e in sorted(os.listdir(根)):
        p = os.path.join(根, e)
        print("  %s %s" % ("[目录]" if os.path.isdir(p) else "      ", e))
    return 0


if __name__ == "__main__":
    raise SystemExit(主())
