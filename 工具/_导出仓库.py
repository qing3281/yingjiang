# -*- coding: utf-8 -*-
"""把「影匠」这套软件**导出成一个能上 GitHub 的代码仓**。

★ 为什么不能直接 `git init D:\\DSHworkspace`：
   那个目录 **393 GiB / 10 万+ 个文件**（`素材\\网盘` 一个就 362 GB）。
   把片子、模型、缓存全塞进 git 是灾难。

★ 为什么不是「一张手写的 56 个文件的清单」：
   老版 `_导出仓库.py` 是手写白名单（56 项）。两个问题：
   ① `_搬家.py` 把根目录文件挪进 `工具\\` 之后，**38 / 56 个源路径静默失灵** ——
      因为它写的是 `os.path.join(工作区, "_开台.py")`，字符串里没有一整条盘符路径，
      我的替换表一条都匹配不上。**手写路径 = 迟早烂。**
   ② 手写清单永远落后于今天写的代码。
   → 改成**按目录 + 后缀扫**，路径由代码算出来，不由我手写。

**只读源目录，只写目标目录。**

用法：
    python 工具\\_导出仓库.py            干跑：列出会导出什么、多大、有没有冲突
    python 工具\\_导出仓库.py --真跑      真的拷进去
    python 工具\\_导出仓库.py --真跑 --清  连目标里多出来的也删（默认不删）
"""
import argparse
import os
import shutil
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

工作区 = r"D:\DSHworkspace"
装 = os.path.join(工作区, "记忆", "_GitHub", "影匠工作台")

# ── 扫哪些子目录（相对工作区）──
扫的 = ["影匠", "工具", "B站"]

# ── 这些目录名出现在任何一层都跳过 ──
跳目录 = {
    # 产物 / 素材 / 模型（不是代码，而是几十 GB）
    "作品", "_work", "_网盘整理", "_bin", "音色", "音色库", "模型", "models",
    "input", "output", "temp", "temp_upload", "_超分试验", "_试成片", "_对比",
    "截图", "字体", "下载", "网盘", "本地AI", "片场", "远程", "远程装机包",
    # 运行时 / 依赖 / 缓存
    "_运行时", "__pycache__", "node_modules", ".git", ".venv", "venv", "site-packages",
    "dist", "build", ".idea", ".vscode", "ms-playwright",
    # 归档（里面是搬家前的旧副本，进去只会把树撑大）
    "归档", "搬家前",
    # 第三方装下来的整包 / 成品片（都不是他写的代码）
    "配音环境", "成片",
}
# 目录名前缀也跳（chromium-1208 这种带版本号的）
跳前缀 = ("chromium-", "chrome-", "node-v")

# ── 带这些后缀的才算「代码」──
带 = {".py", ".cmd", ".bat", ".ps1", ".mjs", ".js", ".ts", ".svelte",
      ".json", ".md", ".html", ".htm", ".css", ".toml", ".yml", ".yaml", ".txt"}

# ── 单个文件超过这个大小就不带（模型、缓存、语料）──
上限 = 2 * 1024 * 1024

# ── 逐个点名不许带的（都写清为什么）──
黑名单 = {
    os.path.join("工具", "_记忆台_缓存.json"): "941 KB 的界面缓存，重跑就有",
    os.path.join("工具", "_用户原话.json"): "11 万字节的私人对话语料，是数据不是代码",
    os.path.join("B站", "制作", "微信配置.md"): "★ 里面 3 条企业微信机器人 webhook，是密钥",
    os.path.join("工具", "_导出仓库.py"): None,     # None = 例外，下面单独处理
}
# 上面那条 `_导出仓库.py` 是「不许由它自己决定不带自己」的意思，实际要带 —— 移除
黑名单.pop(os.path.join("工具", "_导出仓库.py"))

# ── 根目录上这几份文档一起走 ──
根上带的 = ["AGENTS.md", "交接.md", "目录说明.md"]

# ── 少数几张图：README 里要给人看「这东西长什么样」，按老仓的目录名放回去 ──
#    扫的时候按后缀过滤会把 .png 全滤掉，所以这几张得点名带上。
额外 = {
    os.path.join("截图", "控制台_直调.png"): os.path.join(工作区, "记忆", "归档", "截图", "控制台_直调.png"),
    os.path.join("截图", "控制台_exe.png"): os.path.join(工作区, "记忆", "归档", "截图", "控制台_exe.png"),
    os.path.join("截图", "控制台_进度条.png"): os.path.join(工作区, "记忆", "归档", "截图", "控制台_进度条.png"),
    os.path.join("截图", "界面草图.png"): os.path.join(工作区, "记忆", "归档", "截图", "界面草图.png"),
    os.path.join("截图", "依据窗_内容.png"): os.path.join(工作区, "记忆", "归档", "截图", "依据窗_内容.png"),
    os.path.join("截图", "对比_觉醒格17.png"): os.path.join(工作区, "影匠", "作品", "_超分试验", "对比_觉醒格17.png"),
}
# `作品\示例\` 整个目录（README 拿它演示「这东西能出什么」）
示例源 = os.path.join(工作区, "影匠", "作品", "示例")

# ── DSH 客户端插件（挂右侧栏那个页签），源在 DSH 自己家里 ──
插件源 = r"D:\DSH\home\profiles\desktop\node_modules\dsh-yingjiang-panel"
插件件 = ["package.json", "cordis.patch.yml",
          os.path.join("lib", "index.js"), os.path.join("lib", "client.js")]


def 扫一遍():
    """走一遍源目录，返回 {目标相对路径: 源绝对路径}"""
    表 = {}
    跳过 = 0
    太大 = 0
    黑 = 0
    for 顶 in 扫的:
        起 = os.path.join(工作区, 顶)
        if not os.path.isdir(起):
            print(f"  ! 不在：{起}")
            continue
        for 底, 目录们, 文件们 in os.walk(起):
            目录们[:] = [d for d in 目录们
                         if d not in 跳目录 and not d.startswith(跳前缀)]
            for f in 文件们:
                源 = os.path.join(底, f)
                相对 = os.path.relpath(源, 工作区)
                if 相对 in 黑名单:
                    print(f"  ⊘ 点名不带：{相对}　（{黑名单[相对]}）")
                    黑 += 1
                    continue
                if os.path.splitext(f)[1].lower() not in 带:
                    跳过 += 1
                    continue
                try:
                    s = os.path.getsize(源)
                except OSError:
                    continue
                if s > 上限:
                    print(f"  ⊘ 太大（{s:,} B）：{相对}")
                    太大 += 1
                    continue
                表[相对] = 源
    for f in 根上带的:
        源 = os.path.join(工作区, f)
        if os.path.isfile(源):
            表[f] = 源
    for 到, 源 in 额外.items():
        if os.path.isfile(源):
            表[到] = 源
    if os.path.isdir(示例源):
        for f in sorted(os.listdir(示例源)):
            源 = os.path.join(示例源, f)
            if os.path.isfile(源):
                表[os.path.join("作品", "示例", f)] = 源
    for 一 in 插件件:
        源 = os.path.join(插件源, 一)
        if os.path.isfile(源):
            表[os.path.join("dsh-插件", "dsh-yingjiang-panel", 一)] = 源
    return 表, 跳过, 太大, 黑


def 干(真跑, 清):
    表, 跳过, 太大, 黑 = 扫一遍()
    总 = sum(os.path.getsize(p) for p in 表.values())
    print(f"\n  扫出 {len(表)} 个文件　{总/1024/1024:.1f} MiB")
    print(f"  按后缀跳过 {跳过} 个　按大小跳过 {太大} 个　点名不带 {黑} 个")

    # 目标里现在有什么
    现 = {}
    for 底, 目录们, 文件们 in os.walk(装):
        目录们[:] = [d for d in 目录们 if d != ".git"]
        for f in 文件们:
            现[os.path.relpath(os.path.join(底, f), 装)] = os.path.join(底, f)

    新 = sorted(set(表) - set(现))
    旧 = sorted(set(现) - set(表))
    改 = []
    for k in sorted(set(表) & set(现)):
        if os.path.getsize(表[k]) != os.path.getsize(现[k]):
            改.append(k)

    print(f"\n  ── 目标：{装}")
    print(f"     目标里现在 {len(现)} 个")
    print(f"     新增 {len(新)} 个　更新 {len(改)} 个　目标多出来 {len(旧)} 个")

    if 新:
        print("\n  ── 新增（前 25）")
        for k in 新[:25]:
            print(f"     + {k}")
        if len(新) > 25:
            print(f"     …… 还有 {len(新)-25} 个")
    if 改:
        print("\n  ── 更新（前 15）")
        for k in 改[:15]:
            print(f"     ~ {k}")
    if 旧 and not 清:
        print("\n  ── 目标里多出来的（默认不删；要删加 --清）")
        for k in 旧[:15]:
            print(f"     - {k}")
        if len(旧) > 15:
            print(f"     …… 还有 {len(旧)-15} 个")

    if not 真跑:
        print("\n  ★ 干跑，什么都没写。要真拷加 --真跑")
        return 0

    os.makedirs(装, exist_ok=True)
    写 = 0
    for 相对, 源 in 表.items():
        到 = os.path.join(装, 相对)

        os.makedirs(os.path.dirname(到), exist_ok=True)
        shutil.copy2(源, 到)
        写 += 1
    删 = 0
    if 清:
        for k in 旧:
            # ★ 这两份只住在目标仓里（工作区里没有对应物），
            #   `--清` 会把它们当「多出来的」删掉 —— 上一版就这么把 .gitignore 删了。
            if k in ("README.md", ".gitignore"):
                print(f"     ⊘ 保住：{k}（它只住在仓库里，不跟着工作区）")
                continue
            os.remove(现[k])
            删 += 1
        # 清空掉的目录也收拾一下
        for 底, 目录们, 文件们 in os.walk(装, topdown=False):
            if 底 == 装 or ".git" in 底:
                continue
            try:
                if not os.listdir(底):
                    os.rmdir(底)
            except OSError:
                pass
    print(f"\n  ✓ 拷了 {写} 个　删了 {删} 个　→ {装}")
    print(f"    想推的话：python 工具\\_推仓库.py")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--真跑", action="store_true")
    ap.add_argument("--清", action="store_true", help="连目标里多出来的也删（默认不删）")
    a = ap.parse_args()
    print("═" * 70)
    print(f"导出影匠代码仓　{'真跑' if a.真跑 else '干跑'}"
          f"{'　带清' if a.清 else ''}　{datetime.now():%Y-%m-%d %H:%M:%S}")
    print("═" * 70)
    sys.exit(干(a.真跑, a.清))
