$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== 0. 结论回填：A 段那次 exit=9009 = cmd 找不到程序 ==="
'  9009 的含义：命令解释器找不到要执行的文件。'
'  → 极可能是【E:\影匠AI 这个中文路径在 SYSTEM/非交互环境的 OEM 代码页(437)下被解错】'

"=== 1. 拿 8.3 短名（如果有，用短名就能绕开代码页）==="
$sh = cmd /c "dir /x /ad E:\ 2>nul"
$sh | ForEach-Object { '  ' + $_ }
$短 = ($sh | Select-String '影匠AI' | ForEach-Object { ($_.Line -split '\s+') | Where-Object { $_ -match '^[0-9A-Z~]{1,8}$' } } | Select-Object -First 1)
'  E:\影匠AI 的短名: [{0}]' -f $短

"=== 2. SYSTEM 身份下，用【短名】再试一次 ==="
if ($短) {
    $t = 'C:\yjai_s.cmd'
    $c = "@echo off`r`n`"E:\$短\ComfyUI\.venv\Scripts\python.exe`" -c `"print('SHORTNAME OK')`" > C:\yjai_s.txt 2>&1`r`necho exit=%ERRORLEVEL% >> C:\yjai_s.txt`r`n"
    [System.IO.File]::WriteAllText($t, $c, [System.Text.Encoding]::ASCII)
    Remove-Item 'C:\yjai_s.txt' -Force -EA SilentlyContinue
    schtasks /delete /tn yjs /f 2>&1 | Out-Null
    schtasks /create /tn yjs /tr "cmd /c C:\yjai_s.cmd" /sc once /st 23:59 /ru SYSTEM /rl HIGHEST /f 2>&1 | Out-Null
    schtasks /run /tn yjs 2>&1 | Out-Null
    Start-Sleep 15
    if (Test-Path 'C:\yjai_s.txt') { Get-Content 'C:\yjai_s.txt' | ForEach-Object { '     ' + $_ } } else { '     ✗ 没输出' }
} else { '  没有短名（NTFS 8.3 生成可能被关了），跳过' }

"=== 3. ★ WMI 直拉（WMI 的 CommandLine 是 Unicode，理论上不受代码页影响）==="
$w = 'C:\yjai_wmi.py'
[System.IO.File]::WriteAllText($w, "print('WMI UNICODE OK')`n", [System.Text.Encoding]::ASCII)
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = '"{0}" -c "open(r''C:\yjai_wmi.txt'',''w'',encoding=''utf-8'').write(''WMI OK'')"' -f $py
} -EA SilentlyContinue
'  WMI 返回 ReturnValue={0} PID={1}' -f $r.ReturnValue, $r.ProcessId
Start-Sleep 8
if (Test-Path 'C:\yjai_wmi.txt') { '  ✓ WMI 拉中文路径 python 成功：' + (Get-Content 'C:\yjai_wmi.txt' -Raw) } else { '  ✗ WMI 也拉不起来（→ 中文路径确实过不去）' }

"=== 4. 决定性证据：拿一个纯 ASCII 路径的程序对比 ==="
$r2 = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = 'cmd.exe /c echo ASCII_OK > C:\yjai_ascii.txt'
} -EA SilentlyContinue
Start-Sleep 5
'  ASCII 对照: {0}' -f $(if (Test-Path 'C:\yjai_ascii.txt') { '✓ 通了 —— 所以问题就出在中文路径' } else { '✗ 也没通 —— 问题在别处' })

"=== 5. 看看 venv 里有没有硬编码路径（评估能不能安全改名成纯 ASCII）==="
Get-Content "$新程序\.venv\pyvenv.cfg" -EA SilentlyContinue | ForEach-Object { '  ' + $_ }
'  --- Scripts 下有多少 .exe 带硬编码路径 ---'
(Get-ChildItem "$新程序\.venv\Scripts" -Filter '*.exe' -EA SilentlyContinue | Measure-Object).Count
