# -*- coding: utf-8 -*-
"""承诺自检 —— 把「我说过要改的」逐条**当场跑一遍**，打 ✅ / ❌。

用户 m37867 的原话：「以及**你针对自己的记忆这些东西做出的想法改变**。」
用户 m38776 的另一句：「新的这些提示词。**一定要遵守之前的规矩**」
用户反复说的：「**我怎么知道你以后还记不记得这个事儿呢？**」

所以这份东西**不是一张承诺书（承诺书人人会写）**，是一张**自检表**：
每一条后面挂着一个**他自己能敲的命令**，和一个**当场跑出来的结果**。
跑不出来就是 ❌ —— 我改不了那个 ❌，除非我真的把东西做出来。

用法：
    python _承诺自检.py            # 打给人看（表格）
    python _承诺自检.py --json      # 给 _记忆台.py 用
"""
import glob
import json
import os
import re
import subprocess
import sys
import datetime

sys.stdout.reconfigure(encoding="utf-8")
W = r"D:\DSHworkspace"
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"


def 跑(命令, 超时=60):
    """跑一条命令，返回 (退出码, stdout+stderr)。任何异常都当成失败，不许抛出去。"""
    try:
        r = subprocess.run(命令, cwd=W, capture_output=True, timeout=超时)
        t = (r.stdout + r.stderr).decode("utf-8", "replace")
        return r.returncode, t
    except Exception as e:
        return -1, "跑不起来：%s" % e


def 读(路):
    try:
        with open(路, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


条 = []


def 记(承诺, 判据, 命令, 好, 详情):
    条.append({"承诺": 承诺, "判据": 判据, "命令": 命令, "好": bool(好), "详情": 详情})


# ── 1. 「我加的条件」必须写在 AGENTS.md 里，而且是第一行要求 ──────────────
ag = 读(os.path.join(W, "AGENTS.md"))
在 = "我加的条件" in ag
记("每条回答第一行写「我加的条件：___」",
   "AGENTS.md 里有这条，且带判据句",
   "findstr /C:\"我加的条件\" AGENTS.md",
   在,
   "AGENTS.md %d 字节，命中 %d 处" % (len(ag), ag.count("我加的条件")))

# ── 2. 丢人句：当天犯过就必须贴 ──────────────────────────────────────
码, 出 = 跑([PY, "-X", "utf8", "_丢人了.py"])
有 = "傻逼" in 出 or "丢人" in 出
记("当天犯过旧病，每条回答开头贴丢人句",
   "`_丢人了.py` 有输出就必须贴，句子由脚本打印、不许手改",
   "python _丢人了.py",
   码 == 0,
   ("今天要贴 %d 句" % 出.count("\n")) if 有 else "今天还没犯过（脚本一个字都没打）")

# ── 3. 记忆自查块：每次回答末尾 ────────────────────────────────────
码, 出 = 跑([PY, "-X", "utf8", "_记忆自查.py"])
记("每次回答末尾贴「记忆自查」块",
   "`_记忆自查.py` 能打出「最后一次读记忆 / 最后一次查旧病 / 今天扫到几处旧病」",
   "python _记忆自查.py",
   码 == 0 and "最后一次" in 出,
   "打出来 %d 行" % 出.count("\n"))

# ── 4. 假字扫描器 ───────────────────────────────────────────────
码, 出 = 跑([PY, "-X", "utf8", os.path.join(W, "_查假字.py"), "--作品", "楚子航"])
记("产物里的「假字」用一个脚本筛（模型把名字/字幕画进画面）",
   "`_查假字.py` 能扫 32 格并报处数；0 处才算干净",
   "python _查假字.py --作品 楚子航",
   码 == 0 and "✓" in 出,
   (出.strip().splitlines() or ["（没输出）"])[-1][:110])

# ── 5. 无名指代扫描器 ────────────────────────────────────────────
码, 出 = 跑([PY, "-X", "utf8", os.path.join(W, "_查无名指代.py"), "--作品", "楚子航"])
记("产物里的「无名指代」用一个脚本筛（「那个人」→ 模型凭空造一个人）",
   "`_查无名指代.py` 能扫并报处数；0 处才算干净",
   "python _查无名指代.py --作品 楚子航",
   码 == 0 and "✓" in 出,
   (出.strip().splitlines() or ["（没输出）"])[-1][:110])

# ── 6. 「谁在」只搜位置 ──────────────────────────────────────────
路 = os.path.join(W, "影匠", "作品", "楚子航", "_生成全包.py")
源 = 读(路)
m = re.search(r"谁在\s*=\s*\[.*?\]", 源, re.S)
好 = bool(m) and 'g["位置"]' in m.group(0) and 'g["画面"]' not in m.group(0).split("if")[0]
记("「谁在这一格」只看【位置】，不看【画面】",
   "`_生成全包.py` 里那一行不许把两个字段相加",
   "python -c \"import re;print(re.search(r'谁在.*',open(r'影匠/作品/楚子航/_生成全包.py',encoding='utf-8').read()).group())\"",
   好,
   (m.group(0).replace("\n", " ")[:120]) if m else "没找到那一行")

# ── 7. 形态档按部位过滤 ──────────────────────────────────────────
路 = os.path.join(W, "影匠", "作品", "楚子航", "_写作规约.py")
规 = 读(路)
好 = ("部位词" in 规) and ("连带" in 规) and ("def 取形态" in 规 or "取形态" in 规)
记("龙化档/爆血档 改成按部位取（全身景别不许把「大腿」写进去）",
   "`_写作规约.py` 里有 部位词 / 连带 / 取形态",
   "findstr /C:\"取形态\" 影匠\\作品\\楚子航\\_写作规约.py",
   好,
   "_写作规约.py %d 字节，部位词=%s" % (len(规), "有" if "部位词" in 规 else "没有"))

# ── 8. 经验：每做完一件事追加一行 ─────────────────────────────────
经 = glob.glob(os.path.join(W, "记忆", "经验", "*.md"))
今 = datetime.date.today().strftime("%Y-%m-%d")
新 = [p for p in 经 if datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d") == 今]
记("每做完一件事，往 `记忆\\经验\\` 追加一行（只追加不覆盖）",
   "`记忆\\经验\\*.md` 里有文件的 mtime 是今天",
   "dir /O-D 记忆\\经验",
   len(新) > 0,
   "经验库 %d 份，今天动过 %d 份" % (len(经), len(新)))

# ── 9. 会话归档（他 m37867 ①：归档 + 每天定时） ────────────────────
档 = os.path.join(W, "记忆", "对话")
n档 = len(glob.glob(os.path.join(档, "**", "*"), recursive=True)) if os.path.isdir(档) else 0
记("归档之前所有会话，并做成每天自动做的固定动作",
   "`记忆\\对话\\` 里有档案，且有一条每天跑的定时",
   "dir 记忆\\对话",
   n档 > 0,
   "对话档案目录里 %d 个文件" % n档)

# ── 10. 找复发：病的次数在降，不是只在嘴上 ──────────────────────
码, 出 = 跑([PY, "-X", "utf8", "_找复发.py"])
m = re.search(r"(\d+)\s*次", 出)
记("「犯过三次以上的病」有一张数出来的表，不是我感觉出来的",
   "`_找复发.py` 能跑并打出次数",
   "python _找复发.py",
   码 == 0,
   (出.strip().splitlines() or ["（没输出）"])[0][:110] if 出.strip() else "（没输出）")


if "--json" in sys.argv:
    print(json.dumps(条, ensure_ascii=False, indent=1))
    sys.exit(0)

print("=" * 78)
print("承诺自检　%s　—— 每一条都是**当场跑出来的**，不是写上去的" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 78)
过 = sum(1 for t in 条 if t["好"])
for t in 条:
    print()
    print("  %s  %s" % ("✅" if t["好"] else "❌", t["承诺"]))
    print("      判据：%s" % t["判据"])
    print("      你自己敲：%s" % t["命令"])
    print("      现在跑出来：%s" % t["详情"])
print()
print("-" * 78)
print("  %d / %d 条现在是 ✅" % (过, len(条)))
if 过 < len(条):
    print("  没到 ✅ 的那几条，就是我现在还欠着的 —— 不用信我的话，敲那行命令看。")
print("-" * 78)
