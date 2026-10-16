$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== A. 远端有 100.127.224.106 这个地址吗 ==="
Get-NetIPAddress -AddressFamily IPv4 -EA SilentlyContinue | ForEach-Object { '  {0}  ({1})' -f $_.IPAddress, $_.InterfaceAlias }

"=== B. 那个 .cmd 到底执行到哪一步 —— 做个不含重定向的调试副本 ==="
$dbg = "$根\_调试.cmd"
$c = @"
@echo off
echo [1] 进来了
chcp 936
echo [2] chcp=%ERRORLEVEL%
cd /d $新程序
echo [3] cd=%ERRORLEVEL% 现在在 %CD%
echo [4] python 在不在:
if exist "$py" (echo     YES) else (echo     NO)
echo [5] 开始跑 python
"$py" -X utf8 "$新程序\main.py" --port 8188 --listen 100.127.224.106 --extra-model-paths-config "$新程序\extra_model_paths.yaml"
echo [6] python 退出码 %ERRORLEVEL%
"@
[System.IO.File]::WriteAllText($dbg, $c, [System.Text.Encoding]::GetEncoding(936))
'  写好 {0}' -f $dbg

"=== C. 前台跑它，抓全部输出（最多 40 秒）==="
$out = "$根\logs\_dbg.txt"
New-Item -ItemType Directory -Path "$根\logs" -Force | Out-Null
$p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', "`"$dbg`" > `"$out`" 2>&1" -WindowStyle Hidden -PassThru
for ($i = 1; $i -le 14; $i++) {
    Start-Sleep 3
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 3 -EA Stop; '  ✓ 起来了'; break } catch { }
}
if ($p -and -not $p.HasExited) { '  （python 还活着）' } else { '  （进程已退出，码 {0}）' -f $(if ($p) { $p.ExitCode } else { '?' }) }

"=== D. 调试输出 ==="
if (Test-Path -LiteralPath $out) {
    Get-Content -LiteralPath $out -Tail 45 -EA SilentlyContinue | ForEach-Object { '  ' + $_ }
    '  （共 {0} 字节）' -f (Get-Item -LiteralPath $out).Length
} else { '  没有输出文件' }

"=== E. 兜底：绕开 .cmd，用 Start-Process 直接起 python ==="
Get-Process -Name python -EA SilentlyContinue | ForEach-Object { $_.Kill() }
Start-Sleep 2
$pa = Start-Process -FilePath $py -ArgumentList @('-X', 'utf8', "$新程序\main.py", '--port', '8188', '--listen', '100.127.224.106', '--extra-model-paths-config', "$新程序\extra_model_paths.yaml") -WorkingDirectory $新程序 -WindowStyle Hidden -PassThru -RedirectStandardOutput "$根\logs\direct.log" -RedirectStandardError "$根\logs\direct.err"
'  直接起，PID {0}' -f $pa.Id
$起 = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep 3
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 3 -EA Stop; $起 = $true; break } catch { }
}
if ($起) {
    '  ✓ 直接起 python 成功（{0} 秒）—— 说明问题在 .cmd / 计划任务那层' -f ($i * 3)
    $oi = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/object_info/UNETLoader' -TimeoutSec 10
    '  UNETLoader:'
    $oi.UNETLoader.input.required.unet_name[0] | ForEach-Object { '     {0}' -f $_ }
    $va = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/object_info/VAELoader' -TimeoutSec 10
    '  VAELoader:'
    $va.VAELoader.input.required.vae_name[0] | ForEach-Object { '     {0}' -f $_ }
    $cl = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/object_info/CLIPLoader' -TimeoutSec 10
    '  CLIPLoader:'
    $cl.CLIPLoader.input.required.clip_name[0] | ForEach-Object { '     {0}' -f $_ }
} else {
    '  ✗ 直接起也不行，看 direct.err:'
    Get-Content -LiteralPath "$根\logs\direct.err" -Tail 25 -EA SilentlyContinue | ForEach-Object { '     ' + $_ }
}
