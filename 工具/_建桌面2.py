# -*- coding: utf-8 -*-
"""_建桌面2.py —— 在桌面建一个指向任意本机文件的快捷方式（`_建桌面.py` 是写死目标的版本）。

为什么不直接在命令行里写：这台机器的 `pwsh` 不在 PATH 上，只有 Windows PowerShell 5.1，
而 5.1 读 .ps1 是按 **ANSI** 读的 —— UTF-8 无 BOM 文件里的中文会被拆坏。
所以：**由 Python 把 .ps1 写成 utf-8-sig（带 BOM）**，再交给 powershell 跑。

用法：python _建桌面2.py "<目标绝对路径>" "<桌面上的名字>" ["<图标说明>"]
"""
import os
import sys
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(2)

目标 = sys.argv[1]
名字 = sys.argv[2]
说明 = sys.argv[3] if len(sys.argv) > 3 else 名字
ps1 = os.path.join(r"D:\DSHworkspace", "_建桌面快捷方式_%d.ps1" % (abs(hash(名字)) % 100000))

if not os.path.exists(目标):
    print("✗ 目标不在：%s" % 目标)
    sys.exit(1)

脚本 = r'''$ErrorActionPreference = 'Stop'
$目标 = '%s'
$名字 = '%s'
$说明 = '%s'
$桌面 = [Environment]::GetFolderPath('Desktop')
Write-Output ('桌面 = ' + $桌面)
$lnk = Join-Path $桌面 ($名字 + '.lnk')
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = $目标
$s.WorkingDirectory = Split-Path $目标 -Parent
$s.IconLocation = ($env:SystemRoot + '\System32\shell32.dll,70')
$s.Description = $说明
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
''' % (目标, 名字, 说明)

with open(ps1, "w", encoding="utf-8-sig") as f:
    f.write(脚本)

r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout or "")
if r.stderr:
    print("STDERR:", r.stderr[:800])

桌面 = os.path.join(os.path.expanduser("~"), "Desktop")
lnk = os.path.join(桌面, 名字 + ".lnk")
print("复验 %s -> %s" % (lnk, os.path.isfile(lnk)))
sys.exit(0 if (r.returncode == 0 and os.path.isfile(lnk)) else 1)
