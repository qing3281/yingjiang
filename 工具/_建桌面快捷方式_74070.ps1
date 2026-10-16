$ErrorActionPreference = 'Stop'
$目标 = 'D:\DSHworkspace\交接.md'
$名字 = '交接文档'
$说明 = '给下一个 AI 的完整交接（658 行）'
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
