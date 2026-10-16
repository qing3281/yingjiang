# -*- coding: utf-8 -*-
r"""_修桌面指向.py —— 搬家之后，把桌面上那些指向旧路径的 .lnk 修好。

为什么要有这一条：`AGENTS.md` 第 0.05 条那张表里「少问一句『他打开它要敲几下』」
犯过 11 次，里面最狠的一种是 —— **改了「他双击那个图标」背后的东西，没去点一次**。
这次整个工作区搬了家，桌面上每一个 .lnk 都可能指到一个已经不存在的路径。

为什么不直接用 Python 读 .lnk：这个 venv 里**没有 pywin32**（`ModuleNotFoundError: No module named 'win32com'`）。
所以照 `_建桌面2.py` 的老办法：**Python 写 .ps1（utf-8-sig，因为这台机器只有 PowerShell 5.1，按 ANSI 读无 BOM 文件会拆坏中文），再 `powershell -File` 跑。**
分工：Python 负责文件系统（判断目标在不在、按文件名在新结构里找），PowerShell 只负责读写 .lnk。

用法：
    python 工具\_修桌面指向.py            干跑，只列不改
    python 工具\_修桌面指向.py --真跑
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

根 = r"D:\DSHworkspace"
临时 = os.path.join(根, "工具", "_修桌面指向_临时.ps1")
真 = "--真跑" in sys.argv


def 跑ps(脚本):
    with open(临时, "w", encoding="utf-8-sig") as f:
        f.write(脚本)
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", 临时],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or "", r.stderr or ""


def 列出():
    """→ [(桌面, 名字, 目标)]，只列指向本工作区的。"""
    桌 = r"[Environment]::GetFolderPath('Desktop')"
    脚本 = r"""$ErrorActionPreference='Continue'
$桌面 = %s
$sh = New-Object -ComObject WScript.Shell
Get-ChildItem -LiteralPath $桌面 -Filter *.lnk | ForEach-Object {
  try { $t = $sh.CreateShortcut($_.FullName).TargetPath } catch { $t = '' }
  Write-Output ($_.Name + "`t" + $t)
}
""" % 桌
    out, err = 跑ps(脚本)
    if err.strip():
        print("STDERR:", err[:400])
    行 = []
    for s in out.splitlines():
        if "\t" not in s:
            continue
        n, t = s.split("\t", 1)
        行.append((n, t.strip()))
    return 行


def 新位置(名):
    """按文件名在新结构里找。

    ★ 要跳过 `记忆\\归档\\**` —— 那是搬家前留的原件备份（`记忆\\归档\\搬家前\\记忆\\文档\\...`），
      不跳的话「本地AI 环境说明」会被指到那份备份上（第一版就是这个错）。
    """
    排除 = os.path.normcase(os.path.join(根, "记忆", "归档"))
    for d in ("工具", "素材", "记忆", "影匠", "B站", ""):
        p = os.path.join(根, d, 名) if d else os.path.join(根, 名)
        if os.path.exists(p):
            return p
    for d in ("工具", "素材", "记忆"):
        q = os.path.join(根, d)
        if not os.path.isdir(q):
            continue
        for b, _s, fs in os.walk(q):
            if os.path.normcase(b).startswith(排除):
                continue
            if 名 in fs:
                return os.path.join(b, 名)
    return None


def main():
    lnks = 列出()
    print("桌面 .lnk 一共 %d 个（只处理指向 %s 的）" % (len(lnks), 根))
    要改, 坏的, 好的 = [], [], 0
    for n, t in lnks:
        if not t or not t.lower().startswith(根.lower()):
            continue
        if os.path.exists(t):
            好的 += 1
            continue
        新 = 新位置(os.path.basename(t))
        if not 新:
            坏的.append((n, t))
            print("✗  %-30s → %s　（找不到同名文件）" % (n, t))
            continue
        print("%s %-30s → %s" % ("→" if 真 else "·", n, 新))
        要改.append((n, 新))

    print()
    print("指向还在的 %d 个　要改 %d 个　找不到 %d 个" % (好的, len(要改), len(坏的)))

    if not 要改:
        return 0
    if not 真:
        print("（干跑。加 --真跑 才改。）")
        return 0

    行 = ["$ErrorActionPreference='Stop'",
          "$桌面 = " + r"[Environment]::GetFolderPath('Desktop')",
          "$sh = New-Object -ComObject WScript.Shell"]
    for n, 新 in 要改:
        行.append("$s = $sh.CreateShortcut((Join-Path $桌面 '%s'))" % n)
        行.append("$s.TargetPath = '%s'" % 新)
        行.append("$s.WorkingDirectory = Split-Path '%s' -Parent" % 新)
        行.append("$s.Save()")
    行.append("Write-Output 'SAVED'")
    out, err = 跑ps("\n".join(行))
    print(out.strip() or err[:400])

    print("── 改完复核 ──")
    复核 = 列出()
    坏2 = 0
    for n, t in 复核:
        if n in [x for x, _ in 要改]:
            好 = os.path.exists(t)
            坏2 += 0 if 好 else 1
            print("  %s %-30s → %s" % ("✓" if 好 else "✗", n, t))
    print("复核：还坏着 %d 个" % 坏2)
    return 0 if 坏2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
