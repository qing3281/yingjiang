$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== 1. 那些启动器文件到底在不在、内容对不对 ==="
foreach ($f in @('C:\yjai_start.cmd', 'C:\yjai_t2.cmd')) {
    if (Test-Path -LiteralPath $f) {
        '  {0}  {1} 字节' -f $f, (Get-Item -LiteralPath $f).Length
        Get-Content -LiteralPath $f -Encoding Default | ForEach-Object { '      ' + $_ }
    } else { '  ✗ 不存在 {0}' -f $f }
}

"=== 2. 那两个 8MB 的 cmd 在干嘛（拿它的父子关系和线程数看）==="
Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -EA SilentlyContinue | ForEach-Object {
    '  PID {0}  父={1}  线程={2}  命令行={3}' -f $_.ProcessId, $_.ParentProcessId, $_.ThreadCount, $_.CommandLine
}

"=== 3. ★★ 干脆不用 cmd：WMI 直接拉 python 本体 ==="
Get-Process -Name python, cmd -EA SilentlyContinue | ForEach-Object { $_.Kill() }
Start-Sleep 3
Remove-Item -LiteralPath "$根\logs\comfy.log", "$根\logs\comfy.err" -Force -EA SilentlyContinue
'  删完还剩: log={0} err={1}' -f (Test-Path "$根\logs\comfy.log"), (Test-Path "$根\logs\comfy.err")

$args = '-X utf8 "{0}" --port 8188 --listen 0.0.0.0 --extra-model-paths-config "{1}"' -f "$新程序\main.py", "$新程序\extra_model_paths.yaml"
$cl = '"{0}" {1} 1> "{2}" 2> "{3}"' -f $py, $args, "$根\logs\comfy.log", "$根\logs\comfy.err"
'  命令行: ' + $cl
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine      = $cl
    CurrentDirectory = $新程序
} -EA SilentlyContinue
'  WMI: ReturnValue={0} ProcessId={1}' -f $r.ReturnValue, $r.ProcessId

$起 = $false
for ($i = 1; $i -le 55; $i++) {
    Start-Sleep 4
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 4 -EA Stop; $起 = $true; break } catch { }
}
if ($起) { '  ✓✓✓ 起来了！（{0} 秒）' -f ($i * 4) } else { '  ✗ 220 秒还没起来' }

"=== 4. 日志 ==="
'  log {0} 字节 / err {1} 字节' -f (Get-Item -LiteralPath "$根\logs\comfy.log" -EA SilentlyContinue).Length, (Get-Item -LiteralPath "$根\logs\comfy.err" -EA SilentlyContinue).Length
Get-Content -LiteralPath "$根\logs\comfy.err" -Tail 25 -EA SilentlyContinue | ForEach-Object { '    ' + $_ }
Get-Content -LiteralPath "$根\logs\comfy.log" -Tail 10 -EA SilentlyContinue | ForEach-Object { '    ' + $_ }

"=== 5. 进程 ==="
Get-Process -Name python -EA SilentlyContinue | Select-Object Id, @{n='MB';e={[int]($_.WorkingSet64/1MB)}} | ForEach-Object { '  PID {0}  {1} MB' -f $_.Id, $_.MB }
