# -*- coding: utf-8 -*-
"""_记忆自查.py —— 每次回答末尾那段「记忆自查」块的唯一来源。

用法：
    python _记忆自查.py            # 打印块
    python _记忆自查.py --读了 开工,经验   # 记一笔「我这一轮读了哪几样」
    python _记忆自查.py --查了 复发,判据   # 记一笔「我这一轮跑了哪几个检查」

为什么要有这个脚本：
    用户 2026-10-16 原话 ——
    「你都得在回答完我的问题之后，给自己加一个条件，或者加一个输出。
      显示你有没有读过自己的记忆，有没有检查过自己的问题。
      最后一次阅读自己的记忆，检查自己的问题是在什么时候。
      然后显示出你当天到底有没有重新犯过已经犯过的错误。」

    这一段**不许我手写**。手写的自查等于没有自查 —— 今晚一整晚的教训就是这一条
    （我写「已检查」写了十几遍，每次都是假的）。
    所以：块由脚本打印，数由脚本算，命令留在块里让用户能自己重跑。
"""
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
日志 = os.path.join(根, "记忆", ".读过.log")
病表 = os.path.join(根, "_找复发.py")
经验 = os.path.join(根, "记忆", "经验")


def 记(类, 内容):
    os.makedirs(os.path.dirname(日志), exist_ok=True)
    行 = json.dumps(
        {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "类": 类, "内容": 内容},
        ensure_ascii=False,
    )
    with open(日志, "a", encoding="utf-8") as f:
        f.write(行 + "\n")
    print("  ✓ 记下：%s %s" % (类, 内容))


def 读日志():
    出 = []
    if not os.path.exists(日志):
        return 出
    for 行 in open(日志, encoding="utf-8"):
        行 = 行.strip()
        if not 行:
            continue
        try:
            出.append(json.loads(行))
        except Exception:
            pass
    return 出


def 最后一次(类):
    s = [x for x in 读日志() if x.get("类") == 类]
    return s[-1] if s else None


def 今天():
    return time.strftime("%Y-%m-%d")


def 病词表():
    """从 _找复发.py 的 `词表` 里把词读出来 —— 唯一真相在那边，这里不另存一份。

    那边的形状是**列表套元组**：
        词表 = [
            ("病名", "一行判据……", ["一看到就说明又犯了的词", …]),
            …
        ]
    所以这里直接 exec 出那个变量，不自己解析文本 —— 解析文本今晚已经错过一次。
    """
    if not os.path.exists(病表):
        return {}
    src = open(病表, encoding="utf-8").read()
    i = src.find("词表 = [")
    if i < 0:
        return {}
    深 = 0
    for k in range(i + len("词表 = "), len(src)):
        if src[k] in "[(":
            深 += 1
        elif src[k] in "])":
            深 -= 1
            if 深 == 0:
                段 = src[i + len("词表 = ") : k + 1]
                break
    else:
        return {}
    try:
        表 = eval(段, {"__builtins__": {}}, {})
    except Exception:
        return {}
    出 = {}
    for 项 in 表:
        if isinstance(项, (list, tuple)) and len(项) >= 3 and isinstance(项[2], (list, tuple)):
            出[str(项[0])] = [str(w) for w in 项[2]]
    return 出


def 今天动过的产物():
    """今天被改过、且是**我交出去或喂给模型的东西**。

    ★ 范围不能是「工作区里所有 .md/.py」 —— 那会把我自己那些
      「讨论这些病的脚本」也算成犯病（实测一次报 201 处，全是假阳性）。
      产物 = 影匠作品目录下的成品 + 本机的交付文档。
    """
    今 = 今天()
    出 = []
    只看 = (
        os.path.join(根, "影匠", "作品"),
        os.path.join(根, "B站", "成品"),
    )
    for 顶 in 只看:
        if not os.path.isdir(顶):
            continue
        for d, _, fs in os.walk(顶):
            if any(x in d for x in ("_动画切片", "_网盘整理", "__pycache__")):
                continue
            for f in fs:
                if not f.lower().endswith((".md", ".txt", ".json")):
                    continue
                p = os.path.join(d, f)
                try:
                    if time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))) == 今:
                        出.append(p)
                except OSError:
                    pass
    return 出


def 扫病():
    """拿 20 类病的词表，扫今天动过的产物。

    ★ 只扫**喂给模型的那三份**（02/03/04）的全篇，和 `剧本.md` 里**不是表格行**的部分。
      `剧本.md` 的对账表有一栏是「原文是怎么写的」—— 那里出现的「脸上没有任何表情」
      是**被纠正掉的东西**，不是我还留在提示词里的病。实测这类假阳性占两次。
    """
    表 = 病词表()
    命 = {}
    提示词件 = ("02-九宫格.md", "03-四宫格.md", "04-动态提示词.md")
    for p in 今天动过的产物():
        名 = os.path.basename(p)
        if 名 not in 提示词件 and 名 != "剧本.md":
            continue
        try:
            行们 = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        for 行 in 行们:
            if 名 == "剧本.md" and 行.lstrip().startswith("|"):
                continue  # 对账表的表格行，跳过
            if 行.lstrip().startswith("#"):
                continue  # 标题行（`## 角色卡` 之类是格式契约，不是我塞进去的名词）
            for 病名, 词们 in 表.items():
                for w in 词们:
                    if w and w in 行:
                        命.setdefault(病名, []).append((p, w))
    return 命


def 今天记了几笔():
    """今天往 `.读过.log` 里记过几笔。用来轮换红线 —— 数得出来，用户能自己核。"""
    return len([x for x in 读日志() if str(x.get("t", "")).startswith(今天())])


# ══ 十三条硬红线：轮着出现在块里 ═════════════════════════════════════
# 用户 2026-10-16 04:15 原话：
#   「让这个阅读这些红线这些问题，这些经验……能够在你的日常对话中也能记得去读，
#     你想一想有没有什么办法……比如每一个小时去读一次这样的方式吗？」
#
# ★ 为什么写成脚本里的字面表，而不是去解析 `AGENTS.md` / `记忆\需求红线.md`：
#   这个文件自己的上一版注释里就写着 ——「解析文本今晚已经错过一次」。
#   源在 `AGENTS.md` 第三节「硬规矩」+ `交接.md` 第三节（13 条）。
#   **改了那边就同步这里**，否则这张表会漂。
#
# 为什么不是「每小时跑一次定时器」：那一版要烧 token，而且同一段字看第二遍就成墙纸了
# （`AGENTS.md` 第一节自己记着：「规矩写得一字不差，当晚照样犯」）。
# 这一版挂在**我每条回答本来就要跑的那个块**上，成本几乎为零，
# 位置随「今天第几笔自查」滚动 —— 轮换看得见，代价看不见。
红线们 = [
    ("删任何东西之前，先给用户核对",
     "能硬链就别删 —— 同卷 `os.link` 出来的副本不占额外空间，而每个路径都还在"),
    ("远端那台机器只提供算力，效果由本机决定",
     "模板 / 提示词 / 种子 / 模型全部在本机定好再发过去，远端只跑同一份"),
    ("要字幕，而且是烧进画面的硬字幕",
     "成片里字幕是**像素**，不是一条 `.srt` 轨道 —— 软字幕在微信 / QQ / 手机相册里默认不显示"),
    ("片子要有剧情、有对话",
     "把台词单独抄出来念一遍，念得通才算。原话：「没有剧情看个毛线」"),
    ("★ 故事必须直白、简单、明了，谁都能看懂",
     "没看过背景的人看一遍，能不能说出讲了什么事；5 分钟至少 6 个「一个人要什么、另一个人不让」的回合"),
    ("每做完一个片子，发到 2821719816@qq.com",
     "`python D:\\DSHworkspace\\B站\\制作\\寄邮件.py --测` 能通"),
    ("少搞需要管理员身份的事",
     "要 UAC 的，先问他，别自己造替代方案"),
    ("用户对时间和 token 敏感",
     "花他钱之前先想这一步值不值；别用「更彻底」的名义多花"),
    ("给他留 2 GB 内存，别占满 CPU，别动他正在看的视频",
     "`python D:\\DSHworkspace\\_远端体温.py` —— 本机内存剩 ≥2 GB；远端 GPU <83°C 且显存留 ≥1 GB"),
    ("片子要 3–5 分钟、有剧情有对话有战斗",
     "成片时长落在这个区间，别交 30 秒的东西"),
    ("能并行的都优先并行，多派子代理",
     "单线的活先问一句「能不能拆」，拆得动就拆"),
    ("不立「只学设计不抄代码」这种死规矩",
     "能用就用、能抄就抄、能整段搬就整段搬，不许重写、不许另行创作"),
    ("报告必须给退出码和具体命令",
     "不许只说「已完成」；真跑真测，没跑过的一律标「没测」"),
]


def 块():
    最读 = 最后一次("读了")
    最查 = 最后一次("查了")
    病 = 扫病()
    n病 = sum(len(v) for v in 病.values())
    行 = []
    行.append("──── 记忆自查（`_记忆自查.py` 打印，不是我手写的）────")
    行.append(
        "最后一次读记忆：%s"
        % (("%s　读了 %s" % (最读["t"], 最读["内容"])) if 最读 else "★ 今天没记过 —— 等于没读")
    )
    行.append(
        "最后一次查旧病：%s"
        % (("%s　跑了 %s" % (最查["t"], 最查["内容"])) if 最查 else "★ 今天没记过 —— 等于没查")
    )
    if n病 == 0:
        行.append("今天在产物里扫到的旧病：0 处　词表 %d 类" % len(病词表()))
    else:
        行.append("★ 今天在产物里扫到旧病：**%d 处**（%d 类）" % (n病, len(病)))
        for 名, v in list(病.items())[:6]:
            样例 = v[0]
            行.append(
                "    · %s —— %s 里的「%s」" % (名, os.path.basename(样例[0]), 样例[1])
            )
    几笔 = 今天记了几笔()
    第几条 = (几笔 - 1) % len(红线们) if 几笔 else 0
    条, 判据 = 红线们[第几条]
    行.append("")
    行.append("本轮红线 #%d/%d　★ %s" % (第几条 + 1, len(红线们), 条))
    行.append("　　　判据：%s" % 判据)
    行.append("　　（今天第 %d 笔自查，÷%d 取余 —— 你自己重跑会看到同一条）"
             % (几笔, len(红线们)))
    行.append("你可以自己重跑：`python _记忆自查.py`　　（数不对就是我编的）")
    return "\n".join(行)


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--读了" in a:
        记("读了", a[a.index("--读了") + 1] if len(a) > a.index("--读了") + 1 else "未写明")
    elif "--查了" in a:
        记("查了", a[a.index("--查了") + 1] if len(a) > a.index("--查了") + 1 else "未写明")
    else:
        print(块())
