schtasks /delete /tn yjcomfy /f 2>&1 | Out-Null
schtasks /create /tn yjcomfy /tr "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\yjai_boot.ps1" /sc onstart /ru SYSTEM /rl HIGHEST /f 2>&1
schtasks /query /tn yjcomfy /fo LIST /v 2>&1 | Select-String 'Task To Run|Logon Mode|Run As User|要运行的任务|登录状态|作为用户运行' | ForEach-Object { '  ' + $_.Line.Trim() }

"=== 顺便试一次：手动跑这个开机脚本，看它能不能把已停的 ComfyUI 再拉起来 ==="
$before = (Get-Process -Name python -EA SilentlyContinue | Measure-Object).Count
'  当前 python 进程数: {0}' -f $before
'  （不动它，端口在跑就不重复拉 —— yjai_run.py 里已有幂等检查）'
'  yjai_run.py 在不在: {0}' -f (Test-Path 'C:\yjai_run.py')
'  yjai_boot.ps1 在不在: {0}' -f (Test-Path 'C:\yjai_boot.ps1')
'  yjai_run.py 头部:'
Get-Content 'C:\yjai_run.py' -TotalCount 6 | ForEach-Object { '     ' + $_ }