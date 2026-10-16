# -*- coding: utf-8 -*-
"""_理知识库.py —— 第二轮整理：只动「记忆\\」和「影匠\\知识\\」两处，默认干跑。

三件事：
  ① `记忆\\经验\\流程与脚本.md.bak-*` 有 12 份（每次补经验都备一份），只留最新一份，其余归档
  ② `记忆\\文档\\远程装机包.zip`（151.7 MB）与根目录 `远程装机包\\` 是同一批东西，zip 归档
  ③ 把 `影匠\\知识\\` 的目录结构写进 `影匠\\知识\\_怎么找.md`（他问「我以后怎么查」的那个答案）
"""
import argparse
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
归 = os.path.join(根, "_归档", "记忆与知识")
行 = []


def 人(n):
    for u in ("B", "K", "M", "G"):
        if n < 1024:
            return "%.1f%s" % (n, u)
        n /= 1024.0
    return "%.1fP" % n


def 挪(源, 目标目录, 为什么, 真):
    t = os.path.join(目标目录, os.path.basename(源))
    z = os.path.getsize(源)
    行.append("| 挪 | `%s` | %s | %s |" % (源.replace(根 + os.sep, ""), 人(z), 为什么))
    if 真:
        os.makedirs(目标目录, exist_ok=True)
        if os.path.exists(t):
            t += "." + time.strftime("%H%M%S")
        shutil.move(源, t)
    return z


def 主(真):
    # ① 经验库的备份只留最新一份
    经 = os.path.join(根, "记忆", "经验")
    bak = sorted([f for f in os.listdir(经) if ".bak-" in f],
                 key=lambda f: os.path.getmtime(os.path.join(经, f)))
    留 = bak[-1] if bak else None
    总 = 0
    for f in bak:
        if f == 留:
            continue
        总 += 挪(os.path.join(经, f), os.path.join(归, "经验库旧备份"),
                 "补经验时自动备的旧版，只留最新一份", 真)
    print("① 经验库备份 %d 份 → 留 1 份《%s》，归档 %d 份（%s）" % (len(bak), 留, len(bak) - 1, 人(总)))

    # ② 远程装机包.zip 是 远程装机包\ 的压缩版
    z = os.path.join(根, "记忆", "文档", "远程装机包.zip")
    d = os.path.join(根, "远程装机包")
    if os.path.isfile(z) and os.path.isdir(d):
        总 += 挪(z, os.path.join(归, "装机包"), "与根目录 远程装机包\\ 同内容的 zip，只留解开的目录", 真)
        print("② 远程装机包.zip %s → 归档" % 人(os.path.getsize(z)) if not 真 else "② 已归档")

    # ③ 写一份「知识在哪」的导读
    if 真:
        知 = os.path.join(根, "影匠", "知识")
        段 = ["# 知识库怎么找（`_理知识库.py` 生成）\n",
              "> 他没记网址（10-15 01:20 原话：「假如哪天我把这个网址给忘了呢，好麻烦呀」）。",
              "> 所以这张表**自带说明**：想找什么，看左边一列。\n",
              "| 想知道什么 | 去哪一份 |", "|---|---|"]
        说明 = {
            "假判据族.md": "**判据说 OK 其实什么都没量的七种形状**（踩了 7 次，3 次差点破坏性动作）",
            "假字幕.md": "模型把提示词当字幕画进画面",
            "一镜里像看图片.md": "格内不动、格间乱跳",
            "锁脸.md": "Qwen-Image-Edit 会把构图也锁进条件",
            "多角色片.md": "锚点怎么写、远景为什么不喂锚点",
            "分镜法.md": "分镜的字段规矩",
            "配音.md": "IndexTTS 接线 + 五关闸门",
            "H3出片.md": "MiniMax H3 出片总入口",
            "动态提示词.md": "一格一张动态提示词怎么写",
            "一致性系统.md": "角色/场景/风格怎么维持一致",
            "两边一起用.md": "本机 + 远端两台机器怎么分",
            "可用性面板.md": "监工台/记忆台那两个页面",
            "功能地图.md": "影匠这套东西有哪些模块",
            "任务账本.md": "任务/预算怎么记",
            "MCP工具设计.md": "MCP 工具怎么设计",
            "MCP挂载.md": "MCP 怎么挂",
            "动作与战斗.md": "打斗镜怎么写",
            "_索引.json": "（机器读的）每份知识文件的摘要索引",
        }
        for f in sorted(os.listdir(知)):
            p = os.path.join(知, f)
            if os.path.isdir(p):
                段.append("| `%s\\` 里的东西 | `%s\\`（%d 个文件）|" % (f, f, len(os.listdir(p))))
            elif f in 说明:
                段.append("| %s | `%s` |" % (说明[f], f))
        段 += ["", "## 子目录", "",
               "- `h3\\` —— MiniMax H3 官方那 115 份文档（`_index`/`FRAME_LIMITS`/`SEMANTIC_BRIDGE_EXP`…）",
               "- `H3提示词-*.md` —— 从根目录 `mmh3\\` 归进来的 H3 提示词写作规范 + 示例",
               "- `飞彩\\` —— 飞彩那套 25 份（九宫格/四宫格分镜 Gem、导演/分镜师 role）",
               "- `网盘清单\\` —— 网盘那 6 份清单 json", ""]
        with open(os.path.join(知, "_怎么找.md"), "w", encoding="utf-8") as fp:
            fp.write("\n".join(段) + "\n")
        print("③ 写 影匠\\知识\\_怎么找.md")

    清 = os.path.join(根, "_清理清单.md")
    if 行:
        with open(清, "a", encoding="utf-8") as fp:
            fp.write("\n\n## 第二轮：记忆与知识（%s）\n\n" % time.strftime("%Y-%m-%d %H:%M"))
            fp.write("| 动作 | 路径 | 大小 | 为什么 |\n|---|---|---|---|\n")
            fp.write("\n".join(行) + "\n")
    print("清单追加 %d 行（%s）" % (len(行), "真跑了" if 真 else "★ 干跑"))


if __name__ == "__main__":
    参 = argparse.ArgumentParser()
    参.add_argument("--真跑", action="store_true")
    主(参.parse_args().真跑)
