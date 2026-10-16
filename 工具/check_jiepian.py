# -*- coding: utf-8 -*-
"""check_jiepian.py —— 验两件刚改的东西（文件名故意用 ASCII：
   `AGENTS.md` 第 0.05 条：中文/正则/引号塞进命令行字符串，我今晚已经犯过两次）。

它验什么：
  1. `_接片楚子航.py` 和 `_守成片.py` 语法还过不过
  2. 缺格时 `_接片楚子航.py` 必须退 **1**，而且**不许**留下接片锁
  3. 新加的接片锁两个方向：没人占 → True；已经有人占 → False
  4. 上一轮（上一次进程）留下的锁**必须已经清掉**（atexit 生效）

用法（两次，第二次看第 0 行）：
    python check_jiepian.py
"""
import importlib.util
import os
import py_compile
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
脚本 = os.path.join(目, "_接片楚子航.py")
守 = os.path.join(目, "_守成片.py")
验 = os.path.join(目, "_验成片.py")
锁 = os.path.join(目, "片", "_接片锁.json")

print("  开工时锁在不在：%s　（上一轮没清干净这里会是 True）" % os.path.isfile(锁))

坏 = 0

# ── 1. 语法 ──
for f in (脚本, 守, 验):
    try:
        py_compile.compile(f, doraise=True)
        print("  ✓ 语法过：%s" % os.path.basename(f))
    except Exception as e:
        坏 += 1
        print("  ✗ 语法错：%s　%s" % (f, e))
if 坏:
    sys.exit(1)

# ── 2. 缺格时必须退 1，且不留锁 ──
r = subprocess.run([sys.executable, "-X", "utf8", 脚本],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("  缺格时退出码 %d　（要 1）%s" % (r.returncode, "" if r.returncode == 1 else "  ★ 不对"))
for l in (r.stdout or "").strip().splitlines()[-4:]:
    print("    | " + l)
有无 = os.path.isfile(锁)
print("  缺格跑完留没留锁：%s　（要 False）%s" % (有无, "" if not 有无 else "  ★ 不对"))
if r.returncode != 1 or 有无:
    坏 += 1

# ── 2b. 成片还没出来时，验片脚本必须退 1（判据① 不存在），不许崩 ──
r2 = subprocess.run([sys.executable, "-X", "utf8", 验],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
崩溃 = "Traceback" in (r2.stderr or "")
print("  没成片时 验片退出码 %d　（要 1）%s　崩没崩：%s" % (
    r2.returncode, "" if r2.returncode == 1 else "  ★ 不对", "崩了" if 崩溃 else "没崩"))
for l in (r2.stdout or "").strip().splitlines()[:5]:
    print("    | " + l)
if r2.returncode != 1 or 崩溃:
    坏 += 1
    if 崩溃:
        print("    ★ stderr 尾巴：" + (r2.stderr or "")[-400:])

# ── 3. 锁两个方向 ──
spec = importlib.util.spec_from_file_location("jp", 脚本)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
if os.path.isfile(锁):
    os.remove(锁)
a = m.抢锁()
print("  没人占时 抢锁() = %s　（要 True）%s" % (a, "" if a else "  ★ 不对"))
b = m.抢锁()
print("  已经有人占时 抢锁() = %s　（要 False）%s" % (b, "" if not b else "  ★ 不对"))
if not a or b:
    坏 += 1
print("  这一步之后锁文件在：%s（本进程退出时 atexit 会删）" % os.path.isfile(锁))

print()
print("  %s" % ("全过" if 坏 == 0 else "★ %d 条不过" % 坏))
sys.exit(0 if 坏 == 0 else 1)
