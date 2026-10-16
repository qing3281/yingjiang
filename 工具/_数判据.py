import os, re, sys, glob
sys.stdout.reconfigure(encoding="utf-8")
print("══ 80 条经验里，有多少条真的带一个「能跑的判据」 ══")
print("   能跑 = 那一行里有 `python xxx.py` / `_xxx.py` / 反引号包着的脚本名")
n_总 = 0; n_能 = 0; n_只字 = 0
for f in sorted(glob.glob(r"D:\DSHworkspace\记忆\经验\*.md")):
    文 = open(f, encoding="utf-8").read()
    # 一条 = 一个 "- 2026-…" 或 "## " 块，到下一个同级为止
    块 = re.split(r"(?m)^(?=-\s*\d{4}-\d{2}-\d{2}|##\s)", 文)
    for b in 块:
        if not b.strip(): continue
        if not re.match(r"(?m)^(-\s*\d{4}-\d{2}-\d{2}|##\s)", b): continue
        n_总 += 1
        可跑 = re.search(r"(?:python[^\n]{0,80}?\.py|`_[\w\u4e00-\u9fa5]+\.py`|`[\w\u4e00-\u9fa5]+\.py`)", b)
        if 可跑: n_能 += 1
        else:
            n_只字 += 1
            if n_只字 <= 8:
                头 = b.strip().split("\n")[0][:74]
                print("      ✗ 只有文字没判据：%s   ← %s" % (头, os.path.basename(f)))
print()
print("   合计 %d 条：能跑的 %d 条（%.0f%%）／只有文字的 %d 条（%.0f%%）"
      % (n_总, n_能, 100*n_能/max(n_总,1), n_只字, 100*n_只字/max(n_总,1)))
print()
print("══ 今晚手写的一次性检查脚本（全都会随用随丢）══")
import glob as g
脚本 = sorted(g.glob(r"D:\DSHworkspace\_查*.py") + g.glob(r"D:\DSHworkspace\_诊*.py"))
for s in 脚本: print("   " + os.path.basename(s))
print("   共 %d 个 —— 每一个只跑过一次，跑完就没用了" % len(脚本))
