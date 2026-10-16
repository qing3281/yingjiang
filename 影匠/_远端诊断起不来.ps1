$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== 1. 目录都在吗 ==="
foreach ($d in @($根, $新程序, "$根\logs", "$根\ComfyUI-Shared\models")) {
    '  {0}  {1}' -f $(if (Test-Path -LiteralPath $d) { 'OK  ' } else { 'MISS' }), $d
}

"`n=== 2. 启动脚本原样打印（看字节）==="
$s = "$根\启动ComfyUI.cmd"
'  存在: {0}  大小 {1}' -f (Test-Path -LiteralPath $s), (Get-Item -LiteralPath $s -EA SilentlyContinue).Length

"`n=== 3. 直接手工起一遍，抓报错（前台跑 25 秒）==="
$env:PYTHONUTF8 = '1'
$job = Start-Job -ScriptBlock {
    param($exe, $main, $yaml, $cwd)
    Set-Location $cwd
    & $exe -X utf8 $main --port 8189 --listen 127.0.0.1 --extra-model-paths-config $yaml 2>&1
} -ArgumentList $py, "$新程序\main.py", "$新程序\extra_model_paths.yaml", $新程序

$起 = $false
for ($i = 1; $i -le 10; $i++) {
    Start-Sleep 3
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8189/system_stats' -TimeoutSec 3 -EA Stop; $起 = $true; break } catch { }
}
if ($起) { '  ✓ 手工起得来（8189）' } else { '  ✗ 手工也起不来' }

'  --- 前 40 行输出 ---'
Receive-Job -Job $job -Keep -EA SilentlyContinue | Select-Object -First 40 | ForEach-Object { '   ' + $_ }

Stop-Job -Job $job -EA SilentlyContinue
Remove-Job -Job $job -Force -EA SilentlyContinue

"`n=== 4. 计划任务的状态 ==="
$t = Get-ScheduledTask -TaskName 'yjcomfy' -EA SilentlyContinue
if ($t) {
    '  State: {0}' -f $t.State
    '  Action: {0}' -f $t.Actions[0].Execute
    $i = $t | Get-ScheduledTaskInfo
    '  上次运行: {0}   结果: {1} (0x{1:X8})' -f $i.LastRunTime, $i.LastTaskResult
    '  下次运行: {0}' -f $i.NextRunTime
    '  登录方式: {0}   运行级别: {1}' -f $t.Principal.LogonType, $t.Principal.RunLevel
}

"`n=== 5. 日志文件 ==="
foreach ($f in @("$根\logs\comfy.log", "$根\logs\comfy.err")) {
    if (Test-Path -LiteralPath $f) { '  {0}  {1} 字节' -f $f, (Get-Item -LiteralPath $f).Length }
    else { '  不存在 {0}' -f $f }
}
