# -*- coding: utf-8 -*-
"""整理记忆 —— 空闲时跑一遍，把散的东西收拢。

## 为什么要有它

用户 2026-10-15 01:04 的原话：

    而且这个东西你空闲的时候得没事去维护一下他，或者是说。
    扩展一下也好，或者是说整理它的结构样式形式也好，
    要方便我查询，方便我看，方便我阅读的。
    现在是。才这么多的这个什么 30 多个账，90 多个存档。
    那么以后更多的时候怎么办呢？我怎么查的，我怎么看呢？

**他担心的不是现在这 30 条，是 300 条、3000 条的时候。**

所以这个脚本干四件事：

1. **数清楚** —— 每一层现在有多少份、多少字、读一遍多少 token
2. **找重复** —— 同一个坑写了三遍的，挑出来
3. **建索引** —— 生成 `记忆\\索引.md`，按主题分组，**这是给人看的目录**
4. **报该整理的** —— 太久没更新的、空文件、超过 40 KB 该拆的

**它只报告，不删不改。** 要动文件得人来点头（硬规矩 1）。

## 用法

    python _整理记忆.py              # 扫一遍，打印报告
    python _整理记忆.py --写索引      # 顺便把 记忆\\索引.md 写出来

★ 设计原则：**不假装有。** 空的就写 0，不写一个好看的数。
"""
import argparse
import collections
import glob
import hashlib
import io
import os
import re
import sys
import time

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根

要扫的层 = [
    ("工作区指令", ["AGENTS.md"], "DSH 每次会话自动注入"),
    ("用户画像", ["用户画像.md"], "他是谁、要什么、反感什么"),
    ("要求台账", ["要求台账.md"], "他提过的要求 + 状态"),
    ("交接状态", ["接续.md"], "上一次会话做到哪"),
    ("技术知识", ["影匠/知识"], "踩过的坑，一份一坑"),
    ("攒的经验", ["记忆/经验"], "★ 一行一条，只追加"),
    ("长期记忆", [".memsearch/memory"], "MemSearch 插件按天写的"),
    ("对话档案", ["记忆/对话"], "从会话存档挖的原文"),
]


def 算词(字):
    """中文按 1.3 字/token 估（和 _记忆台.py 一致）。"""
    return int(字 / 1.3)


def 首行(p):
    头 = ""
    try:
        with io.open(p, encoding="utf-8", errors="replace") as f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                if l.startswith("#"):
                    头 = l.lstrip("# ").strip()
                elif not l.startswith(">"):
                    头 = l
                break
    except Exception:
        pass
    return 头[:160]


def 扫层(W, 名, 相对们, 说明):
    份 = []
    for r in 相对们:
        p = os.path.join(W, r.replace("/", os.sep))
        if os.path.isfile(p):
            份.append(p)
        elif os.path.isdir(p):
            份 += sorted(glob.glob(os.path.join(p, "**", "*.md"), recursive=True))
    字 = 0
    for p in 份:
        try:
            with io.open(p, encoding="utf-8", errors="replace") as f:
                字 += len(f.read())
        except Exception:
            pass
    return {"名": 名, "份": 份, "份数": len(份), "字": 字,
            "词": 算词(字), "说明": 说明}


def 指纹(p):
    """首 4 KB + 尾 4 KB 的 md5 —— 判重不看大小（大小一样内容可能不同）。"""
    try:
        with open(p, "rb") as f:
            头 = f.read(4096)
            f.seek(max(0, os.path.getsize(p) - 4096))
            尾 = f.read(4096)
        return hashlib.md5(头 + b"|" + 尾).hexdigest()
    except Exception:
        return ""


def 主题(名):
    表 = [
        ("画面与镜头", "字幕 假字幕 运动 动 图片 镜头 分镜 锚点 锁脸 角色 构图 一致性 景别 首帧 尾帧"),
        ("提示词", "提示词 写法 模型 采样 参数 种子 LoRA 节点 工作流"),
        ("声音", "配音 音 TTS 语音 台词 混音 音乐"),
        ("流程与脚本", "脚本 流程 判据 假 检查 核对 台账 缓存 端口 进程 拼 成片"),
        ("存储与系统", "盘 硬链 删除 空间 内存 显存 装 备份 路径"),
        ("协作与规矩", "规矩 用户 要求 汇报 代理 团队 审核"),
    ]
    for 类, 词s in 表:
        for w in 词s.split():
            if w in 名:
                return 类
    return "其他"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--写索引", action="store_true", help="把 记忆\\索引.md 写出来")
    ap.add_argument("--根", default=根)
    参 = ap.parse_args()
    W = 参.根

    print("  ══ 整理记忆　%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print()

    层s = [扫层(W, 名, 相对们, 说明) for 名, 相对们, 说明 in 要扫的层]

    print("  ── 一、现在有多少 ──")
    print("    %-12s %6s %12s %12s  %s" % ("层", "份数", "字", "读一遍 tok", "说明"))
    总字 = 0
    for x in 层s:
        总字 += x["字"]
        print("    %-12s %6d %12s %12s  %s" % (
            x["名"], x["份数"], f"{x['字']:,}", f"{x['词']:,}", x["说明"]))
    print("    %-12s %6s %12s %12s" % ("合计", "", f"{总字:,}", f"{算词(总字):,}"))
    print()

    # ── 二、找重复
    print("  ── 二、重复的（同内容不同名 / 同主题多份）──")
    纹 = collections.defaultdict(list)
    for x in 层s:
        if x["名"] in ("对话档案", "长期记忆"):
            continue
        for p in x["份"]:
            f = 指纹(p)
            if f:
                纹[f].append(p)
    重 = {k: v for k, v in 纹.items() if len(v) > 1}
    if 重:
        for k, v in 重.items():
            print("    ★ %d 份内容相同：" % len(v))
            for p in v:
                print("        %s" % os.path.relpath(p, W))
    else:
        print("    没有内容完全相同的文件。")
    print()

    # ── 三、太久没动 / 空 / 太大
    print("  ── 三、该整理的 ──")
    今 = time.time()
    空 = []; 大 = []; 老 = []
    for x in 层s:
        if x["名"] in ("对话档案", "长期记忆"):
            continue
        for p in x["份"]:
            sz = os.path.getsize(p)
            if sz < 200:
                空.append(p)
            if sz > 40 * 1024:
                大.append(p)
            if 今 - os.path.getmtime(p) > 14 * 86400:
                老.append(p)
    for 标, 组, 建议 in (
            ("空的（< 200 B）", 空, "删掉或补内容"),
            ("太大的（> 40 KB）", 大, "拆成几份，一份一个主题"),
            ("14 天没动过", 老, "要么还有用（那就别慌），要么已经过时")):
        print("    %s：%d 份" % (标, len(组)))
        for p in 组[:8]:
            print("        %-46s %6d B" % (os.path.relpath(p, W), os.path.getsize(p)))
        if len(组) > 8:
            print("        …… 还有 %d 份" % (len(组) - 8))
    print()

    # ── 四、攒的经验（唯一会「长大」的一层）
    经 = next((x for x in 层s if x["名"] == "攒的经验"), None)
    print("  ── 四、攒的经验 ──")
    if 经 and 经["份数"]:
        总条 = 0
        for p in 经["份"]:
            try:
                with io.open(p, encoding="utf-8", errors="replace") as f:
                    条 = sum(1 for l in f if l.strip().startswith("- "))
            except Exception:
                条 = 0
            总条 += 条
            print("    %-22s %3d 条  %6d B  %s" % (
                os.path.basename(p)[:-3], 条, os.path.getsize(p),
                time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))))
        print("    合计 %d 条" % 总条)
    else:
        print("    还没有。规矩：每做完一件事往 记忆\\经验\\<主题>.md 追加一行。")
    print()

    # ── 五、索引
    if 参.写索引:
        出 = os.path.join(W, "记忆", "索引.md")
        os.makedirs(os.path.dirname(出), exist_ok=True)
        题 = collections.OrderedDict()
        for x in 层s:
            if x["名"] in ("对话档案", "长期记忆"):
                continue
            for p in x["份"]:
                题.setdefault(主题(os.path.basename(p)), []).append(p)
        L = ["# 记忆索引", "",
             "> 这份是 `_整理记忆.py --写索引` 生成的。**给人看的目录。**",
             "> 生成于 %s。要改内容去改原文件，别改这里。" % time.strftime("%Y-%m-%d %H:%M"),
             "", "## 一、现在有多少", "",
             "| 层 | 份数 | 字 | 读一遍 tok |", "|---|---:|---:|---:|"]
        for x in 层s:
            L.append("| %s | %d | %s | %s |" % (x["名"], x["份数"],
                                              f"{x['字']:,}", f"{x['词']:,}"))
        L += ["", "## 二、按主题", ""]
        for 类, 路s in sorted(题.items(), key=lambda z: -len(z[1])):
            L.append("### %s（%d 份）" % (类, len(路s)))
            L.append("")
            for p in sorted(路s):
                L.append("- [`%s`](%s) —— %s" % (
                    os.path.basename(p),
                    os.path.relpath(p, os.path.dirname(出)).replace("\\", "/"),
                    首行(p)[:100]))
            L.append("")
        with io.open(出, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(L) + "\n")
        print("  ✓ 索引写到 %s（%.1f KB）" % (出, os.path.getsize(出) / 1024))

    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
