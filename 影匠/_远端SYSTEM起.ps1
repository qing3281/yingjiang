$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'

"=== 0. 先看看上回失败后日志里留了什么 ==="
'  comfy.log {0} 字节' -f (Get-Item -LiteralPath "$根\logs\comfy.log" -EA SilentlyContinue).Length
'  comfy.err {0} 字节' -f (Get-Item -LiteralPath "$根\logs\comfy.err" -EA SilentlyContinue).Length
Get-Content -LiteralPath "$根\logs\comfy.err" -Tail 25 -EA SilentlyContinue | ForEach-Object { '    ' + $_ }

Get-Process -Name python -EA SilentlyContinue | ForEach-Object { $_.Kill() }
Start-Sleep 2

"`n=== 1. 注册成 SYSTEM 身份的计划任务（关键：SYSTEM 不需要交互登录会话，SSH 断开也不会被杀）==="
schtasks /delete /tn yjcomfy /f 2>&1 | Out-Null
schtasks /create /tn yjcomfy /tr "cmd /c C:\yjai_start.cmd" /sc onstart /ru SYSTEM /rl HIGHEST /f 2>&1 | ForEach-Object { '  ' + $_ }
schtasks /query /tn yjcomfy /fo LIST 2>&1 | Select-String '任务名|TaskName|状态|Status|作为用户运行|Run As User' | ForEach-Object { '  ' + $_.Line.Trim() }

"`n=== 2. 用它把 ComfyUI 拉起来（脱离 SSH 会话）==="
Remove-Item -LiteralPath "$根\logs\comfy.log", "$根\logs\comfy.err" -Force -EA SilentlyContinue
schtasks /run /tn yjcomfy 2>&1 | ForEach-Object { '  ' + $_ }
$起 = $false
for ($i = 1; $i -le 60; $i++) {
    Start-Sleep 5
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 4 -EA Stop; $起 = $true; break } catch { }
}
if ($起) { '  ✓✓✓ 起来了！（{0} 秒）' -f ($i * 5) } else { '  ✗ 300 秒还没起来' }

"`n=== 3. 日志 ==="
Get-Content -LiteralPath "$根\logs\comfy.err" -Tail 30 -EA SilentlyContinue | ForEach-Object { '    ' + $_ }

"`n=== 4. 进程在不在 ==="
Get-Process -Name python, cmd -EA SilentlyContinue | Select-Object Id, ProcessName, @{n='MB';e={[int]($_.WorkingSet64/1MB)}} | ForEach-Object { '  PID {0,-7} {1,-8} {2} MB' -f $_.Id, $_.ProcessName, $_.MB }
