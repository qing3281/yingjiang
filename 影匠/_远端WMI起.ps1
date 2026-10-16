$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== 1. 那两个计划任务到底报什么错 ==="
foreach ($n in @('yjcomfy', 'yjt2')) {
    $i = schtasks /query /tn $n /fo LIST /v 2>&1
    $i | Select-String '上次运行时间|Last Run Time|上次结果|Last Result|要运行的任务|Task To Run|登录状态|Logon Mode' | ForEach-Object { '  [{0}] {1}' -f $n, $_.Line.Trim() }
}

"=== 2. ★ 换路子：用 WMI 建【脱离 SSH 会话】的进程 ==="
# 原理：Win32_Process.Create 由 WMI 服务（常驻）在它自己的会话里拉起进程，
# 不挂在 ssh → powershell 的进程树上，SSH 一断不会被连坐杀掉。
Get-Process -Name python -EA SilentlyContinue | ForEach-Object { $_.Kill() }
Start-Sleep 2
Remove-Item -LiteralPath "$根\logs\comfy.log", "$根\logs\comfy.err" -Force -EA SilentlyContinue

$cmdline = 'cmd.exe /c C:\yjai_start.cmd'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmdline } -EA SilentlyContinue
if ($r) { '  WMI 返回: ReturnValue={0}  ProcessId={1}' -f $r.ReturnValue, $r.ProcessId } else { '  WMI 调用失败' }

$起 = $false
for ($i = 1; $i -le 50; $i++) {
    Start-Sleep 4
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 4 -EA Stop; $起 = $true; break } catch { }
}
if ($起) { '  ✓✓✓ 起来了！（{0} 秒）' -f ($i * 4) } else { '  ✗ 200 秒还没起来' }

"=== 3. 追踪 + 日志 ==="
if (Test-Path 'C:\yjai_trace.txt') { Get-Content 'C:\yjai_trace.txt' | ForEach-Object { '  T ' + $_ } } else { '  ✗ 追踪文件还是没有' }
'  comfy.log {0} 字节 / comfy.err {1} 字节' -f (Get-Item -LiteralPath "$根\logs\comfy.log" -EA SilentlyContinue).Length, (Get-Item -LiteralPath "$根\logs\comfy.err" -EA SilentlyContinue).Length
Get-Content -LiteralPath "$根\logs\comfy.err" -Tail 18 -EA SilentlyContinue | ForEach-Object { '    ' + $_ }

"=== 4. 进程 ==="
Get-Process -Name python, cmd -EA SilentlyContinue | Select-Object Id, ProcessName, @{n='MB';e={[int]($_.WorkingSet64/1MB)}} | ForEach-Object { '  PID {0,-7} {1,-8} {2} MB' -f $_.Id, $_.ProcessName, $_.MB }
