r"""把 `D:\DSHworkspace\记忆\_GitHub\影匠工作台\` 推上 GitHub（用户 `qing3281`）。

★ 卡点只有一个：**没有 token**。token 只能用户给 —— 我造不出来，也不该去翻他的。

用法（三选一）：

    # 1) 直接把 token 当参数（会留在 PowerShell 历史里，不太推荐）
    python _推仓库.py --token ghp_xxxxxxxx

    # 2) 从环境变量读（推荐）
    $env:GH_TOKEN = 'ghp_xxxxxxxx'
    python _推仓库.py

    # 3) 已经配过 credentials 的话
    python _推仓库.py

    先干跑看一眼要推什么（不写远端）：
    python _推仓库.py --看

**这个脚本只读本地、只写远端**，不碰工作区里任何别的文件。
"""
import argparse
import os
import subprocess
import sys

根 = os.path.join(r"D:\DSHworkspace", "_GitHub", "影匠工作台")
远端名 = "origin"


def git(*参, 回显=True, 环境=None):
    r = subprocess.run(["git"] + list(参), cwd=根, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=环境)
    if 回显 and r.stdout.strip():
        for s in r.stdout.strip().splitlines():
            print(f"    {s}")
    if r.returncode != 0 and r.stderr.strip():
        for s in r.stderr.strip().splitlines():
            print(f"    ! {s}")
    return r


def 干():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--用户", default="qing3281")
    ap.add_argument("--仓", default="yingjiang-workbench")
    ap.add_argument("--看", action="store_true", help="只干跑，不写远端")
    a = ap.parse_args()

    if not os.path.isdir(os.path.join(根, ".git")):
        print(f"  ✗ {根} 里没有 .git —— 先跑 `python _导出仓库.py` 再 `git init`")
        return 1

    print(f"  仓库：{根}")
    git("log", "--oneline", "-1")
    r = git("ls-files", 回显=False)
    print(f"  文件数：{len(r.stdout.strip().splitlines())} 个")

    # 远端地址：有 token 就带上（只在这条命令里用，不落到 .git/config）
    址 = f"https://{a.用户}:{a.token}@github.com/{a.用户}/{a.仓}.git" if a.token \
        else f"https://github.com/{a.用户}/{a.仓}.git"

    if a.看:
        print("\n  ── 干跑：要推的内容 ──")
        git("remote", "-v")
        git("status", "--short", "--branch")
        print(f"\n  真正推的时候会执行：")
        print(f"    git remote set-url {远端名} https://<token>@github.com/{a.用户}/{a.仓}.git")
        print(f"    git push -u {远端名} main")
        print(f"\n  ⚠ 仓库得先在 GitHub 上建好：https://github.com/new?name={a.仓}")
        return 0

    if not a.token:
        print("\n  ✗ 没有 token。")
        print("    去 https://github.com/settings/tokens 建一个 classic token，勾 `repo` 就行，")
        print("    然后 `$env:GH_TOKEN = 'ghp_…'` 再跑这个脚本。")
        print("    （仓库也别忘了先在 https://github.com/new 建好，名字 yingjiang-workbench）")
        return 1

    print(f"\n  ── 推 {a.用户}/{a.仓} ──")
    git("remote", "remove", 远端名, 回显=False)
    git("remote", "add", 远端名, 址)
    # ★ 地址里带着 token，不能让它留进 repo 的配置里
    r = git("push", "-u", 远端名, "main")
    git("remote", "set-url", 远端名, f"https://github.com/{a.用户}/{a.仓}.git")
    if r.returncode != 0:
        print("\n  ✗ 推失败。多半是：① 仓库还没建 ② token 没勾 `repo` ③ token 过期")
        return 1
    print(f"\n  ✓ 推上去了：https://github.com/{a.用户}/{a.仓}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(干())
