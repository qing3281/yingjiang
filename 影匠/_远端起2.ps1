$ErrorActionPreference = 'Continue'
$基础 = 'E:\影匠AI\ComfyUI'
$py = Join-Path $基础 '.venv\Scripts\python.exe'
$日志 = 'C:\Users\Seele\_comfyui_r.log'

Write-Output "基础目录: $(Test-Path $基础)"
Write-Output "python: $(Test-Path $py)"

# 杀掉现有
$旧 = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object { $_.CommandLine -like '*ComfyUI*main.py*' }
Write-Output "旧进程 $($旧.Count) 个"
foreach ($p in $旧) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3

# 先删旧的计划任务
schtasks /Delete /TN "ComfyUI_H3" /F 2>$null | Out-Null

# 写一个启动用的 .cmd（计划任务里跑 bat 最省事，重定向也简单）
$cmd = @"
@echo off
cd /d "$基础"
"$py" -X utf8 main.py --port 8188 --listen 0.0.0.0 --extra-model-paths-config "$基础\extra_model_paths.yaml" > "$日志" 2>&1
"@
$cmd路 = 'C:\Users\Seele\_start_comfy.cmd'
Set-Content -Path $cmd路 -Value $cmd -Encoding ASCII
Write-Output "写好 $cmd路"

# 建计划任务并立刻跑
schtasks /Create /TN "ComfyUI_H3" /TR "$cmd路" /SC ONCE /ST 23:59 /F /RL HIGHEST | Out-Null
Write-Output "建任务 $LASTEXITCODE"
schtasks /Run /TN "ComfyUI_H3" | Out-Null
Write-Output "已触发"

# 等
$好了 = $false
for ($i = 1; $i -le 72; $i++) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 8 -UseBasicParsing
        if ($r.StatusCode -eq 200) { Write-Output "★ 起来了，等了 $($i*5) 秒"; $好了 = $true; break }
    } catch { }
}
if (-not $好了) {
    Write-Output "★ 没起来"
    $p = 'C:\Users\Seele\_comfyui_r.log'
    if (Test-Path $p) { Get-Content $p -Tail 30 -Encoding UTF8 }
}

# 报告监听
Write-Output "--- netstat 8188 ---"
netstat -ano | Select-String '8188'
