# -*- coding: utf-8 -*-
"""_大扫除.py —— 整理 D:\\DSHworkspace。默认**干跑**，加 `--真跑` 才动手。

判据来源（不是我自己拍脑袋）：
  · 活工具 = `_活工具.txt`（`_盘点3.py` 从 AGENTS.md / 交接.md / 记忆\\** / 影匠\\知识\\**
    顺着引用做传递闭包算出来的 122 个）
  · 除此之外的根目录 `_*.py` = 一次性调试脚本 → 挪进 `_归档\\一次性脚本\\`
  · 只有这四类**真删**：`__pycache__`（不含任何 venv）、0 字节文件、`.part/.tmp`、
    以及明确可再生的临时目录（见 删目录 表）

一切动作都写进 `_清理清单.md`（路径 + 字节 + mtime + 为什么）。
"""
import argparse
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
归 = os.path.join(根, "_归档")

活动脚本 = set()
for 文 in ("_活工具.txt", "_保命清单.txt"):
    p = os.path.join(根, 文)
    if not os.path.isfile(p):
        print("★★ 警告：%s 不在！白名单是空的，**这时候不许真跑** —— 先跑 `_写保命清单.py` 重建" % 文)
        continue
    for L in open(p, encoding="utf-8"):
        L = L.strip()
        if L and not L.startswith("#"):
            活动脚本.add(L)
# 我自己这几把整理用的刀当然留着
活动脚本 |= {"_大扫除.py", "_盘点.py", "_盘点2.py", "_盘点3.py", "_盘点4.py", "_写保命清单.py"}
# ★ 白名单文件自己也要保住 —— 第一版漏了这一步，结果 `_活工具.txt` / `_保命清单.txt`
#   被当成「.txt 调试残留」挪进 `_归档\调试图\`，**再跑第二次白名单就是空的**，
#   那时候它会把活工具当一次性脚本挪走。（2026-10-16 21:5x 逮到并复原。）
保命文件 = {os.path.normcase(os.path.join(根, f)) for f in ("_活工具.txt", "_保命清单.txt")}
print("活工具 + 保命清单：%d 个根目录脚本不动" % len(活动脚本))

# 根目录里这些后缀是「调试残留」，挪去 _归档\调试图\
残留后缀 = {".png", ".jpg", ".jpeg", ".txt", ".log", ".err", ".pid", ".mp4", ".gif", ".webp"}
# 这些后缀是「装东西时留下的」，挪去 _归档\安装残留\
安装后缀 = {".ps1", ".cmd", ".mjs", ".js", ".html", ".yaml", ".yml", ".bak"}

# 明确可再生的临时目录：真删
删目录 = {
    "_超分分段": "15 段超分中间件（703 MB）。终版已复制到 影匠\\作品\\楚子航\\片_官方\\，可再跑 109 分钟再生",
    "_邮件临时": "发邮件时的压缩暂存，发完即无用",
    "_寄片试": "`_寄片.py --干跑` 的产物，只为验代码路径",
    "_超分试": "20 秒超分小样与对照图，结论已写进 记忆\\经验\\流程与脚本.md",
    "_试烧临时": "烧字幕试渲染的临时帧",
    "_字幕试": "试字号/试边距的临时产物，定稿 30/48/4 已写进经验",
}
# 这些目录挪去 _归档（里面有当时的证据，留着可查但别占根目录）
归档目录 = {
    "_试接子镜": "接子镜试跑",
    "_试混音": "混音小样",
    "_试中间帧": "qwen_edit 中间帧试验（三条替代路全被证伪，产物留证）",
    "_试多关键帧": "多关键帧试验",
    "_试I2VA": "I2VA 试片",
    "_试FL2VA": "FL2VA 试片",
    "_试配音": "配音试听",
    "_试配音批": "配音批处理试",
    "_量一格": "量一格运动",
    "_量一格_1344": "量一格运动（1344 档）",
    "_新音轨查": "音轨排查",
    "_短提示词查": "提示词长度排查",
    "_声检": "声音检查",
    "_diag": "诊断输出",
    "_tmp_longzu": "临时",
    "_probe": "探测",
    "_网盘处理_tmp": "网盘处理临时",
    "_验末尾": "成片末尾体检的证据图",
    "_验超分": "2× 验收的证据图（结论已进交接与经验）",
    "_验官方": "官方长片的证据图",
    "_验字幕": "字幕验收的证据图",
    "_验成片2": "成片验收的证据图",
    "_连片试": "官方 H3 母版 + 20 秒小样（母版另存 _归档\\母版\\）",
    "_试接缝": "接缝试片",
}
# 不带 `_` 开头、但确实是「装完就没用」的目录
归档目录2 = {
    "_打包": "影匠控制台 exe 的构建产物（build/dist/spec），随时可重建",
    "_会话_LMtio": "早期一场会话的导出（A_用户/B_助手/C_工具/全文.jsonl）",
    "魔法少女示例": "FLUX 示例图参考素材（49 MB）",
}
临时目录2 = {
    "_网盘处理_tmp": "网盘处理的分析中间件",
    "_tmp_longzu": "龙族原文抓取的中间件",
    "_diag": "诊断脚本与 DSH asar 探测残留",
}
# 只删这些目录里明确是中间件的东西？不 —— 上面两张表就是全部判断。

行 = []
统计 = {"删文件": 0, "删字节": 0, "删目录": 0, "挪文件": 0, "挪字节": 0}


def 记(动作, p, 字节, 为什么):
    行.append("| %s | `%s` | %s | %s | %s |" % (
        动作, p.replace(根 + os.sep, ""), ("%.1f KB" % (字节 / 1024)) if 字节 < 1048576 else ("%.1f MB" % (字节 / 1048576)),
        time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p))) if os.path.exists(p) else "-", 为什么))


def 大(p):
    if os.path.isfile(p):
        try:
            return os.path.getsize(p)
        except OSError:
            return 0
    s = 0
    for 底, 目, 文 in os.walk(p):
        for f in 文:
            try:
                s += os.path.getsize(os.path.join(底, f))
            except OSError:
                pass
    return s


def 挪(源, 目标目录, 动作, 为什么, 真):
    目标 = os.path.join(目标目录, os.path.basename(源))
    if os.path.exists(目标):
        目标 = 目标 + "." + time.strftime("%H%M%S")
    z = 大(源)
    记(动作, 源, z, 为什么)
    if 真:
        os.makedirs(目标目录, exist_ok=True)
        try:
            shutil.move(源, 目标)
        except (PermissionError, OSError) as e:
            # 有程序正开着它（ComfyUI 日志、正在渲的 mp4…）→ 跳过，别把整轮打断
            print("  · 跳过（占用中）%s → %s" % (os.path.basename(源), type(e).__name__))
            行[-1] = 行[-1].replace("| 挪 |", "| 跳过(占用中) |")
    if 真 and not os.path.exists(源):
        统计["挪文件" if False else "挪文件"] += 1
        统计["挪字节"] += z
    elif not 真:
        统计["挪文件"] += 1
        统计["挪字节"] += z


def 删(源, 为什么, 真):
    z = 大(源)
    记("删", 源, z, 为什么)
    if 真:
        try:
            if os.path.isdir(源):
                shutil.rmtree(源, ignore_errors=True)
            else:
                os.remove(源)
        except (PermissionError, OSError) as e:
            print("  · 跳过（占用中）%s → %s" % (os.path.basename(源), type(e).__name__))
            行[-1] = 行[-1].replace("| 删 |", "| 跳过(占用中) |")
            return
    统计["删文件" if os.path.isfile(源) else "删目录"] += 1
    统计["删字节"] += z


def 是venv内(p):
    s = p.lower()
    return (os.sep + "venv" + os.sep) in s or (os.sep + "site-packages" + os.sep) in s


def 主(真):
    # ① 桌面 lnk 指到的东西不许动
    保命 = set()
    桌面 = r"C:\Users\青\Desktop"
    if os.path.isdir(桌面):
        import subprocess
        for f in os.listdir(桌面):
            if not f.lower().endswith(".lnk"):
                continue
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "(New-Object -ComObject WScript.Shell).CreateShortcut('%s').TargetPath"
                                % os.path.join(桌面, f)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            t = (r.stdout or "").strip()
            if t:
                保命.add(os.path.normcase(os.path.abspath(t)))
    print("桌面 lnk 指到的目标 %d 个（一律不动）" % len(保命))

    # ② 根目录的 `_*` 文件分流
    for 名 in sorted(os.listdir(根)):
        p = os.path.join(根, 名)
        if not os.path.isfile(p) or not 名.startswith("_"):
            continue
        if os.path.normcase(os.path.abspath(p)) in 保命:
            continue
        if os.path.normcase(os.path.abspath(p)) in 保命文件:   # ★ 白名单文件自己不许挪
            continue
        e = os.path.splitext(名)[1].lower()
        if e == ".py":
            if 名 in 活动脚本:
                continue
            挪(p, os.path.join(归, "一次性脚本"), "挪", "不在活工具清单里（`_盘点3.py` 的传递闭包）", 真)
        elif e in 残留后缀:
            挪(p, os.path.join(归, "调试图"), "挪", "调试残留", 真)
        elif e in 安装后缀:
            挪(p, os.path.join(归, "安装残留"), "挪", "装机/写页时留下的", 真)
        elif 是venv内(p):
            continue

    # ③ 根目录的临时目录
    for 名, 为什么 in list(删目录.items()) + list(归档目录.items()):
        p = os.path.join(根, 名)
        if not os.path.isdir(p):
            continue
        if 名 in 删目录:
            删(p, 为什么, 真)
        else:
            挪(p, os.path.join(归, "试验音视频"), "挪", 为什么, 真)
    for 名, 为什么 in 归档目录2.items():
        p = os.path.join(根, 名)
        if os.path.isdir(p):
            挪(p, os.path.join(归, "装机与导出"), "挪", 为什么, 真)
    for 名, 为什么 in 临时目录2.items():
        p = os.path.join(根, 名)
        if os.path.isdir(p):
            挪(p, os.path.join(归, "中间产物"), "挪", 为什么, 真)

    # ③b mmh3 里那份 H3 提示词写作规范是知识，归到 影匠\知识\，其余归档
    知 = os.path.join(根, "影匠", "知识")
    m = os.path.join(根, "mmh3")
    if os.path.isdir(m):
        for f in sorted(os.listdir(m)):
            if f.lower().endswith(".md"):
                源 = os.path.join(m, f)
                t = os.path.join(知, "H3提示词-" + f)
                if not os.path.exists(t):
                    记("挪", 源, os.path.getsize(源), "H3 提示词写作规范 → 归到 影匠\\知识\\")
                    if 真:
                        os.makedirs(知, exist_ok=True)
                        shutil.copy2(源, t)
                    统计["挪文件"] += 1
        挪(m, os.path.join(归, "素材"), "挪", "H3 提示词技能包的其余文件（.yaml/参考）", 真)

    # ④ __pycache__（不碰任何 venv）
    for 底, 目们, 文们 in os.walk(根):
        if 是venv内(底):
            目们[:] = []
            continue
        for d in list(目们):
            if d == "__pycache__":
                q = os.path.join(底, d)
                if not 是venv内(q):
                    删(q, "Python 字节码缓存，随时会自己重建", 真)
                目们.remove(d)

    # ⑤ 0 字节 / .part / .tmp（根目录与影匠顶层，不进 venv）
    for 子 in ("", "影匠", "B站"):
        起 = os.path.join(根, 子)
        if not os.path.isdir(起):
            continue
        for 底, 目们, 文们 in os.walk(起):
            if 是venv内(底):
                目们[:] = []
                continue
            if 底.count(os.sep) - 起.count(os.sep) > 2:
                目们[:] = []
                continue
            for f in 文们:
                q = os.path.join(底, f)
                e = os.path.splitext(f)[1].lower()
                if e in (".part", ".tmp", ".crdownload"):
                    删(q, "断点续传/临时文件", 真)
                elif os.path.getsize(q) == 0:
                    删(q, "0 字节空文件", 真)

    # ⑥ 定妆照：每个角色只留最终版
    戏 = os.path.join(根, "影匠", "作品", "楚子航")
    for 名, 为什么 in {
        "_定妆4": "第 4 轮定妆迭代（中间版）",
        "_定妆5": "第 5 轮定妆迭代（中间版）",
        "_定妆6": "第 6 轮定妆迭代（中间版）",
        "_定妆7": "第 7 轮定妆迭代（中间版）",
        "_定妆8": "第 8 轮定妆迭代（中间版）",
        "_定妆9": "第 9 轮定妆迭代（中间版）",
        "_定妆10": "第 10 轮定妆迭代（中间版）",
        "_设定集2": "第 2 版设定集（中间版）",
        "_设定集3": "第 3 版设定集（中间版）",
    }.items():
        p = os.path.join(戏, 名)
        if os.path.isdir(p):
            挪(p, os.path.join(归, "定妆照中间版"), "挪", 为什么, 真)
    for 路, 为什么 in ((os.path.join(戏, "_定妆照", "_旧"), "定妆照的旧版"),
                      (os.path.join(戏, "_定妆卡_楚子航_爆血", "_眼睛试色"), "爆血眼睛试色（中间版）")):
        if os.path.isdir(路):
            挪(路, os.path.join(归, "定妆照中间版"), "挪", 为什么, 真)

    # ⑦ 影匠\ 下的 .bak-* 旧版脚本
    for f in sorted(os.listdir(os.path.join(根, "影匠"))):
        if ".bak" in f and os.path.isfile(os.path.join(根, "影匠", f)):
            挪(os.path.join(根, "影匠", f), os.path.join(归, "旧脚本"), "挪", "改之前的旧版", 真)

    # ⑧ 母版单独存
    p = os.path.join(根, "_连片试", "官方_chuzihang_20261016_115413.mp4")
    if os.path.isfile(p):
        t = os.path.join(归, "母版")
        os.makedirs(t, exist_ok=True) if 真 else None
        if 真:
            shutil.move(p, os.path.join(t, os.path.basename(p)))
        记("挪", p, os.path.getsize(p) if os.path.exists(p) else 0, "官方 H3 原始母版（181 MB），终版已配字幕另存", )
        统计["挪文件"] += 1

    # 写清单
    # ★ 第一版这里是 `open(_清理清单.md, "w")` —— 每跑一次就把上一次的记录**盖掉**。
    #   2026-10-16 21:54 我重跑了一次干跑，把真跑那 979 行「什么被挪到哪了」冲没了。
    #   现在：每次写一个带时间戳的清单到 `_归档\清理清单\`，再把最新那份顺手写进根目录。
    清单 = os.path.join(根, "_清理清单.md")
    档 = os.path.join(归, "清理清单")
    os.makedirs(档, exist_ok=True)
    本份 = os.path.join(档, "清理清单_%s%s.md" % (time.strftime("%Y%m%d-%H%M%S"), "" if 真 else "_干跑"))
    头 = ["# 大扫除清单（%s，%s）\n" % (time.strftime("%Y-%m-%d %H:%M"), "真跑" if 真 else "干跑"),
          "判据：`_盘点.py` / `_盘点2.py` / `_盘点3.py` 先摊开，活工具来自 `_活工具.txt`。",
          "本文件由 `_大扫除.py` 生成，%s。\n" % ("**真的动了磁盘**" if 真 else "`--干跑` 时**什么都没动**"),
          "| 动作 | 路径 | 大小 | mtime | 为什么 |", "|---|---|---|---|---|"]
    正文 = "\n".join(头 + 行) + "\n"
    with open(本份, "w", encoding="utf-8") as fp:
        fp.write(正文)
    if 真:                       # 干跑不许污染根目录那份权威记录
        with open(清单, "w", encoding="utf-8") as fp:
            fp.write(正文)
    总字节 = 统计["删字节"]
    print("")
    print("删目录 %d 个　删文件 %d 个　合计释放 %.1f MB" % (统计["删目录"], 统计["删文件"], 总字节 / 1048576))
    print("挪目录 %d 个　挪文件 %d 个　合计搬走 %.1f MB" % (0, 统计["挪文件"], 统计["挪字节"] / 1048576))
    print("清单 %d 行 → %s" % (len(行), 本份))
    print("（%s）" % ("真跑了" if 真 else "★ 干跑，什么都没动；加 --真跑 才动"))


if __name__ == "__main__":
    参 = argparse.ArgumentParser()
    参.add_argument("--真跑", action="store_true")
    主(参.parse_args().真跑)
