$ErrorActionPreference = 'Continue'

"=== A. 隔离测试：SYSTEM 身份的计划任务本身能不能跑（最傻的命令）==="
$t = 'C:\yjai_x.cmd'
[System.IO.File]::WriteAllText($t, "@echo off`r`necho HELLO > C:\yjai_x.txt`r`necho DONE >> C:\yjai_x.txt`r`n", [System.Text.Encoding]::ASCII)
Remove-Item 'C:\yjai_x.txt' -Force -EA SilentlyContinue
schtasks /delete /tn yjx /f 2>&1 | Out-Null
schtasks /create /tn yjx /tr "cmd /c C:\yjai_x.cmd" /sc once /st 23:59 /ru SYSTEM /rl HIGHEST /f 2>&1 | Select-Object -Last 1
schtasks /run /tn yjx 2>&1 | Select-Object -Last 1
Start-Sleep 10
if (Test-Path 'C:\yjai_x.txt') { '  ✓ SYSTEM 任务能跑：'; Get-Content 'C:\yjai_x.txt' | ForEach-Object { '     ' + $_ } } else { '  ✗ 连 echo 都不行 —— SYSTEM 任务被挡了' }
schtasks /query /tn yjx /fo LIST /v 2>&1 | Select-String '上次结果|Last Result' | ForEach-Object { '  ' + $_.Line.Trim() }

"`n=== B. E: 是什么盘 ==="
Get-CimInstance Win32_LogicalDisk -EA SilentlyContinue | Where-Object { $_.DeviceID -in @('C:', 'D:', 'E:') } | ForEach-Object {
    '  {0}  DriveType={1} (3=本地 4=网络 2=可移动)  {2}  剩 {3} GB' -f $_.DeviceID, $_.DriveType, $_.FileSystem, [int]($_.FreeSpace / 1GB)
}
$sub = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\DOS Devices' -EA SilentlyContinue).'E:'
if ($sub) { '  ⚠ E: 是 subst → {0}' -f $sub } else { '  E: 不是 subst' }

"`n=== C. 试试【当前用户 + 不要求登录】的计划任务（要密码，先看能不能免密）==="
# 换个思路：用 /ru 当前用户 /it（交互式）在【已有登录会话】里跑。
# 关键前提：这台机器现在有没有人【本地登录】着（SSH 不算交互式登录会话）。
'  当前交互式登录会话:'
& qwinsta 2>&1 | ForEach-Object { '     ' + $_ }

"`n=== D. 看看到底是谁在杀我的进程 —— 查 AppLocker / WDAC / 第三方安全软件 ==="
'  AppLocker 服务: {0}' -f (Get-Service AppIDSvc -EA SilentlyContinue).Status
'  WDAC 策略文件:'
Get-ChildItem 'C:\Windows\System32\CodeIntegrity\CiPolicies\Active' -EA SilentlyContinue | ForEach-Object { '     ' + $_.Name }
'  安全软件:'
Get-CimInstance -Namespace root\SecurityCenter2 -ClassName AntiVirusProduct -EA SilentlyContinue | ForEach-Object { '     ' + $_.displayName }
