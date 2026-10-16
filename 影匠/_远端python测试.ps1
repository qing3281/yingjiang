$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== A. SYSTEM 能跑 python 吗（最小测试）==="
$t = 'C:\yjai_py.cmd'
$c = @"
@echo off
echo [1] start > C:\yjai_py.txt
"$py" -c "print('PYTHON ALIVE')" > C:\yjai_py2.txt 2>&1
echo [2] exit=%ERRORLEVEL% >> C:\yjai_py.txt
"$py" -c "import torch;print('CUDA',torch.cuda.is_available())" >> C:\yjai_py2.txt 2>&1
echo [3] exit=%ERRORLEVEL% >> C:\yjai_py.txt
"@
[System.IO.File]::WriteAllText($t, $c, [System.Text.Encoding]::GetEncoding(936))
Remove-Item 'C:\yjai_py.txt', 'C:\yjai_py2.txt' -Force -EA SilentlyContinue
schtasks /delete /tn yjpy /f 2>&1 | Out-Null
schtasks /create /tn yjpy /tr "cmd /c C:\yjai_py.cmd" /sc once /st 23:59 /ru SYSTEM /rl HIGHEST /f 2>&1 | Out-Null
schtasks /run /tn yjpy 2>&1 | Out-Null
Start-Sleep 25
'  --- yjai_py.txt ---'
if (Test-Path 'C:\yjai_py.txt') { Get-Content 'C:\yjai_py.txt' | ForEach-Object { '     ' + $_ } } else { '     ✗ 没有' }
'  --- yjai_py2.txt（python 自己的输出）---'
if (Test-Path 'C:\yjai_py2.txt') { Get-Content 'C:\yjai_py2.txt' | ForEach-Object { '     ' + $_ } } else { '     ✗ 没有' }

"`n=== B. 360 是不是在拦 ==="
Get-Process -EA SilentlyContinue | Where-Object { $_.ProcessName -match '360|ZhuDongFangYu|QHSafe|deepscan' } | Select-Object Id, ProcessName, @{n='MB';e={[int]($_.WorkingSet64/1MB)}} | ForEach-Object { '  PID {0,-7} {1,-22} {2} MB' -f $_.Id, $_.ProcessName, $_.MB }
'  --- 360 拦截日志（最近）---'
foreach ($d in @('C:\ProgramData\360safe', 'C:\Program Files (x86)\360\360Safe')) {
    if (Test-Path $d) { Get-ChildItem $d -Recurse -Include '*.log', '*.txt' -EA SilentlyContinue | Sort-Object LastWriteTime -Desc | Select-Object -First 3 | ForEach-Object { '     {0}  {1}' -f $_.LastWriteTime, $_.FullName } }
}

"`n=== C. 换个更稳的：让 ComfyUI 在【交互式控制台会话】里跑（用户已经本地登录着）==="
'  console 会话里有没有 explorer/python:'
Get-CimInstance Win32_Process -Filter "Name='explorer.exe' OR Name='python.exe' OR Name='pythonw.exe'" -EA SilentlyContinue | ForEach-Object { '     PID {0} {1} 会话={2}' -f $_.ProcessId, $_.Name, $_.SessionId }
'  当前 SSH 进程在哪个会话: {0}' -f (Get-Process -Id $PID).SessionId

"`n=== D. 决定性一试：SYSTEM 跑一个 5 分钟的 python 长命进程，看它能不能活 ==="
$t2 = 'C:\yjai_long.cmd'
@"
@echo off
"$py" -c "import time,sys;f=open(r'C:\yjai_long.txt','w');[ (f.write(str(i)+chr(10)),f.flush(),time.sleep(5)) for i in range(60) ]" 
echo done=%ERRORLEVEL% >> C:\yjai_long.txt
"@ | Set-Content -LiteralPath $t2 -Encoding Default
Remove-Item 'C:\yjai_long.txt' -Force -EA SilentlyContinue
schtasks /delete /tn yjlong /f 2>&1 | Out-Null
schtasks /create /tn yjlong /tr "cmd /c C:\yjai_long.cmd" /sc once /st 23:59 /ru SYSTEM /rl HIGHEST /f 2>&1 | Out-Null
schtasks /run /tn yjlong 2>&1 | Out-Null
foreach ($k in 1..4) {
    Start-Sleep 6
    $n = if (Test-Path 'C:\yjai_long.txt') { (Get-Content 'C:\yjai_long.txt' -EA SilentlyContinue | Measure-Object).Count } else { -1 }
    $p = (Get-Process -Name python -EA SilentlyContinue | Measure-Object).Count
    '  第 {0} 次检查（{1} 秒）: 计数文件写了 {2} 行；python 进程 {3} 个' -f $k, ($k * 6), $n, $p
}
