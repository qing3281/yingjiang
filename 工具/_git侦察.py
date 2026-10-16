# -*- coding: utf-8 -*-
"""上 GitHub 之前的 git 侦察：A（真干活的 影匠）和 origin/main 到底是什么关系。

只读。不改任何东西。回答四个问题：
  ① A 和 origin/main 有没有共同祖先、谁在前
  ② origin/main 里有哪些文件 A 的工作树里没有（这些会被「用 A 覆盖」弄丢）
  ③ A 的工作树里有哪些文件 origin/main 没有（这些是今天的新活）
  ④ A 那 3 个本地独有提交里，巨物占了多大（决定能不能直接推）
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

A = r"D:\DSHworkspace\影匠"


def git(*参, 根=A):
    r = subprocess.run(["git", "-C", 根] + list(参), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


print("══ ① 关系 ══")
for 名, 参 in [("merge-base", ("merge-base", "origin/main", "HEAD")),
              ("origin/main 的 HEAD", ("rev-parse", "--short", "origin/main")),
              ("本地的 HEAD", ("rev-parse", "--short", "HEAD"))]:
    c, o, e = git(*参)
    print(f"  {名:<18} {o if c == 0 else '★ ' + e}")

c, o, e = git("merge-base", "--is-ancestor", "origin/main", "HEAD")
print(f"  origin/main 是不是本地 HEAD 的祖先：{'是' if c == 0 else '不是'}")
c, o, e = git("merge-base", "--is-ancestor", "HEAD", "origin/main")
print(f"  本地 HEAD 是不是 origin/main 的祖先：{'是' if c == 0 else '不是'}")

c, o, e = git("rev-list", "--left-right", "--count", "origin/main...HEAD")
print(f"  远端独有 / 本地独有：{o}")

print("\n══ ② origin/main 有、A 工作树里没有的文件 ══")
_, 远端文件, _ = git("ls-tree", "-r", "--name-only", "origin/main")
远端 = [x for x in 远端文件.splitlines() if x.strip()]
缺 = [f for f in 远端 if not os.path.exists(os.path.join(A, f))]
print(f"  origin/main 共 {len(远端)} 个文件；其中 A 工作树里没有的：{len(缺)} 个")
for f in 缺[:40]:
    print(f"     ★ {f}")
if len(缺) > 40:
    print(f"     …… 还有 {len(缺)-40} 个")

print("\n══ ③ A 工作树有、origin/main 没有的文件（今天的新活）══")
_, 本地全部, _ = git("ls-files", "--cached", "--others", "--exclude-standard")
本地 = [x for x in 本地全部.splitlines() if x.strip()]
远端集 = set(远端)
新 = [f for f in 本地 if f not in 远端集]
print(f"  A 的工作树（含未跟踪、已按 .gitignore 过滤）共 {len(本地)} 个；origin/main 没有的：{len(新)} 个")
for f in 新[:30]:
    print(f"     + {f}")
if len(新) > 30:
    print(f"     …… 还有 {len(新)-30} 个")

print("\n══ ④ A 那 3 个本地独有提交里的巨物 ══")
_, 独有, _ = git("log", "--format=%h", "origin/main..HEAD")
总巨 = 0
for c in [x for x in 独有.splitlines() if x.strip()]:
    _, 名, _ = git("log", "-1", "--format=%s", c)
    _, 文件, _ = git("diff-tree", "--no-commit-id", "--name-only", "-r", c)
    大 = []
    for f in 文件.splitlines():
        p = os.path.join(A, f)
        if os.path.isfile(p):
            s = os.path.getsize(p)
            if s > 10 * 1024 * 1024:
                大.append((s, f))
    大.sort(reverse=True)
    if 大:
        print(f"  ── {c}  {名[:50]}")
        for s, f in 大[:4]:
            print(f"       {s:>14,} B  {f}")
        总巨 += sum(s for s, _ in 大)
print(f"\n  ★ 这 3 个提交里 >10 MB 的文件合计 {总巨/1073741824:.2f} GB")
print("  ★ GitHub 硬上限：单文件 100 MB，超过直接拒收")
