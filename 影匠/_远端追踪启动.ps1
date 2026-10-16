$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== 1. 那个卡住的 cmd 是什么 ==="
Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -EA SilentlyContinue |
    ForEach-Object { '  PID {0}  {1}' -f $_.ProcessId, $_.CommandLine }
'  有没有 python: {0}' -f ((Get-Process -Name python -EA SilentlyContinue | Measure-Object).Count)

"=== 2. 带【追踪】的启动器（每步都往 trace 文件里写一行）==="
$trace = 'C:\yjai_trace.txt'
$启动器 = 'C:\yjai_start.cmd'
$c = @"
@echo off
echo [%DATE% %TIME%] start >> $trace
chcp 936 >nul 2>&1
echo [%DATE% %TIME%] chcp ok >> $trace
cd /d $新程序
echo [%DATE% %TIME%] cd=%CD% err=%ERRORLEVEL% >> $trace
if exist "$py" (echo [%DATE% %TIME%] python YES >> $trace) else (echo [%DATE% %TIME%] python NO >> $trace)
"$py" -X utf8 "$新程序\main.py" --port 8188 --listen 0.0.0.0 --extra-model-paths-config "$新程序\extra_model_paths.yaml" >> "$根\logs\comfy.log" 2>> "$根\logs\comfy.err"
echo [%DATE% %TIME%] python exited=%ERRORLEVEL% >> $trace
"@
[System.IO.File]::WriteAllText($启动器, $c, [System.Text.Encoding]::GetEncoding(936))
Remove-Item -LiteralPath $trace -Force -EA SilentlyContinue
'  已写带追踪的启动器'

"=== 3. 杀掉旧的，重新跑 ==="
Get-Process -Name python, cmd -EA SilentlyContinue | Where-Object { $_.Id -ne $PID } | ForEach-Object { $_.Kill() }
Start-Sleep 3
Remove-Item -LiteralPath "$根\logs\comfy.log", "$根\logs\comfy.err" -Force -EA SilentlyContinue
schtasks /run /tn yjcomfy 2>&1 | ForEach-Object { '  ' + $_ }
Start-Sleep 45

"=== 4. 追踪文件（它执行到第几步）==="
if (Test-Path -LiteralPath $trace) {
    Get-Content -LiteralPath $trace | ForEach-Object { '  ' + $_ }
} else { '  ✗ 追踪文件压根没生成 —— cmd 连第一行都没跑到' }

"=== 5. 进程 ==="
Get-Process -Name python, cmd -EA SilentlyContinue | Select-Object Id, ProcessName, @{n='MB';e={[int]($_.WorkingSet64/1MB)}} | ForEach-Object { '  PID {0,-7} {1,-8} {2} MB' -f $_.Id, $_.ProcessName, $_.MB }

"=== 6. 日志 ==="
'  comfy.log {0} 字节' -f (Get-Item -LiteralPath "$根\logs\comfy.log" -EA SilentlyContinue).Length
'  comfy.err {0} 字节' -f (Get-Item -LiteralPath "$根\logs\comfy.err" -EA SilentlyContinue).Length
Get-Content -LiteralPath "$根\logs\comfy.err" -Tail 20 -EA SilentlyContinue | ForEach-Object { '    ' + $_ }

"=== 7. SYSTEM 到底能不能看 E 盘 —— 用一个 SYSTEM 身份的 cmd 直接试 ==="
$t2 = 'C:\yjai_t2.txt'
@"
@echo off
echo whoami: > $t2
whoami >> $t2
echo --- dir E:\ --- >> $t2
dir E:\ /b >> $t2 2>&1
echo --- dir $根 /b --- >> $t2
dir $根 /b >> $t2 2>&1
echo --- py exists --- >> $t2
if exist "$py" (echo YES >> $t2) else (echo NO >> $t2)
"@ | ForEach-Object { [System.IO.File]::WriteAllText('C:\yjai_t2.cmd', $_, [System.Text.Encoding]::GetEncoding(936)) }
Remove-Item -LiteralPath $t2 -Force -EA SilentlyContinue
schtasks /delete /tn yjt2 /f 2>&1 | Out-Null
schtasks /create /tn yjt2 /tr "cmd /c C:\yjai_t2.cmd" /sc once /st 23:59 /ru SYSTEM /rl HIGHEST /f 2>&1 | Out-Null
schtasks /run /tn yjt2 2>&1 | Out-Null
Start-Sleep 12
if (Test-Path -LiteralPath $t2) { Get-Content -LiteralPath $t2 | Select-Object -First 30 | ForEach-Object { '  ' + $_ } } else { '  ✗ 连 t2 都没生成' }
