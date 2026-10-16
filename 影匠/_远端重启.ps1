$ErrorActionPreference = 'Stop'
$基础 = 'E:\影匠AI\ComfyUI'
$py = Join-Path $基础 '.venv\Scripts\python.exe'

Write-Output "基础目录存在: $(Test-Path $基础)"
Write-Output "python 存在: $(Test-Path $py)"

# 1) 杀掉旧的
$旧 = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object { $_.CommandLine -like '*ComfyUI*main.py*' }
Write-Output "找到 $($旧.Count) 个旧进程"
foreach ($p in $旧) {
    Write-Output "  杀 PID $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 4

# 2) 清日志
$出 = 'C:\Users\Seele\_comfyui_r.log'
$错 = 'C:\Users\Seele\_comfyui_re.log'
Remove-Item $出, $错 -Force -ErrorAction SilentlyContinue

# 3) 用 Start-Process 起（它自己会脱离父进程）
$参 = @(
    '-X', 'utf8', 'main.py',
    '--port', '8188',
    '--listen', '0.0.0.0',
    '--extra-model-paths-config', (Join-Path $基础 'extra_model_paths.yaml')
)
$p = Start-Process -FilePath $py -ArgumentList $参 -WorkingDirectory $基础 `
     -RedirectStandardOutput $出 -RedirectStandardError $错 `
     -WindowStyle Hidden -PassThru
Write-Output "新进程 PID $($p.Id)"

# 4) 等它起来
$好了 = $false
for ($i = 1; $i -le 72; $i++) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 8 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
            Write-Output "★ 起来了，等了 $($i * 5) 秒"
            $好了 = $true
            break
        }
    } catch { }
}
if (-not $好了) {
    Write-Output "★ $((72*5)) 秒还没起来"
    Write-Output "--- 输出日志尾部 ---"
    if (Test-Path $出) { Get-Content $出 -Tail 40 -Encoding UTF8 }
    Write-Output "--- 错误日志尾部 ---"
    if (Test-Path $错) { Get-Content $错 -Tail 40 -Encoding UTF8 }
}
