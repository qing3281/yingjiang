$ErrorActionPreference = 'Continue'

# 杀掉现有
$旧 = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object { $_.CommandLine -like '*main.py*' }
Write-Output "旧 main.py 进程 $($旧.Count) 个"
foreach ($p in $旧) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3

# 确认 .cmd 内容没坏（中文路径要能看见「影匠AI」）
$cmd路 = 'C:\Users\Seele\_start_comfy.cmd'
if (Test-Path $cmd路) {
    Write-Output "--- .cmd 内容 ---"
    Get-Content $cmd路 -Encoding Default | ForEach-Object { Write-Output "  $_" }
} else {
    Write-Output "★ .cmd 不存在"
}

schtasks /Delete /TN "ComfyUI_H3" /F 2>&1 | Out-Null
schtasks /Create /TN "ComfyUI_H3" /TR "$cmd路" /SC ONCE /ST 23:59 /F /RL HIGHEST 2>&1 | Out-Null
Write-Output "建任务退出码 $LASTEXITCODE"
schtasks /Run /TN "ComfyUI_H3" 2>&1 | Out-Null
Write-Output "已触发"

$好了 = $false
for ($i = 1; $i -le 72; $i++) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 8 -UseBasicParsing
        if ($r.StatusCode -eq 200) { Write-Output "★ 起来了，等了 $($i*5) 秒"; $好了 = $true; break }
    } catch { }
}
if (-not $好了) {
    Write-Output "★ 没起来，日志尾："
    $p = 'C:\Users\Seele\_comfyui_r.log'
    if (Test-Path $p) { Get-Content $p -Tail 25 -Encoding UTF8 }
}
Write-Output "--- netstat 8188 ---"
netstat -ano | Select-String '8188'
