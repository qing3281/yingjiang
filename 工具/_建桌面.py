# -*- coding: utf-8 -*-
"""在桌面建一个指向本地文件的快捷方式。

为什么不直接在命令行里写：这台机器的 `pwsh` 不在 PATH 上，只有 Windows PowerShell 5.1，
而 5.1 读 .ps1 是按 **ANSI** 读的 —— 我写出去的 UTF-8 无 BOM 文件里的中文会被拆坏。
所以：**由 Python 把 .ps1 写成 utf-8-sig（带 BOM）**，再交给 powershell 跑。
"""
import os, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8")

目标 = r"D:\DSHworkspace\影匠\作品\楚子航\_怎么做出来的.html"
名字 = "楚子航·怎么做出来的"
ps1 = r"D:\DSHworkspace\_建桌面快捷方式.ps1"

if not os.path.isfile(目标):
    print("✗ 目标不在：%s" % 目标)
    sys.exit(1)

脚本 = r'''$ErrorActionPreference = 'Stop'
$目标 = '%s'
$名字 = '%s'
$桌面 = [Environment]::GetFolderPath('Desktop')
Write-Output ('桌面 = ' + $桌面)
$lnk = Join-Path $桌面 ($名字 + '.lnk')
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = $目标
$s.WorkingDirectory = Split-Path $目标 -Parent
$s.IconLocation = ($env:SystemRoot + '\System32\shell32.dll,70')
$s.Description = '这片子是怎么做出来的'
$s.Save()
if (Test-Path $lnk) {
    $i = Get-Item $lnk
    Write-Output ('OK ' + $i.FullName)
    Write-Output ('   ' + $i.Length + ' 字节  ' + $i.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))
    $s2 = $sh.CreateShortcut($lnk)
    Write-Output ('   指向 = ' + $s2.TargetPath)
    if ($s2.TargetPath -ne $目标) { Write-Output 'BAD 指向不对'; exit 1 }
} else { Write-Output 'BAD 没建成'; exit 1 }
exit 0
''' % (目标, 名字)

# ★ 必须带 BOM：Windows PowerShell 5.1 不认无 BOM 的 UTF-8
with open(ps1, "w", encoding="utf-8-sig") as f:
    f.write(脚本)

print("已写 %s（utf-8-sig，%d 字节）" % (ps1, os.path.getsize(ps1)))
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout or "")
if r.stderr:
    print("STDERR:", r.stderr[:800])
print("退出码 =", r.returncode)

# 复验：快捷方式真的在桌面上、而且 mtime 是刚刚
桌面 = os.path.join(os.path.expanduser("~"), "Desktop")
lnk = os.path.join(桌面, 名字 + ".lnk")
print("复验 %s -> %s" % (lnk, os.path.isfile(lnk)))
sys.exit(0 if (r.returncode == 0 and os.path.isfile(lnk)) else 1)
