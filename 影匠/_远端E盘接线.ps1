$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$模型 = "$根\ComfyUI-Shared\models"

"=== 1. 补齐标准模型子目录 ==="
foreach ($d in @('checkpoints', 'diffusion_models', 'loras', 'vae', 'text_encoders', 'upscale_models',
        'model_patches', 'clip', 'clip_vision', 'controlnet', 'embeddings', 'audio_encoders',
        'style_models', 'unet', 'diffusers', 'latent_upscale_models', 'photomaker', 'gligen')) {
    $p = Join-Path $模型 $d
    if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}
'  模型子目录 {0} 个' -f (Get-ChildItem -LiteralPath $模型 -Directory -Force).Count

"`n=== 2. 写新的启动脚本（GBK 编码 —— cmd.exe 默认 936，写 UTF-8 中文路径会乱）==="
$cmd = @"
@echo off
chcp 936 >nul
title ComfyUI - E盘
cd /d $新程序
"$新程序\.venv\Scripts\python.exe" -X utf8 "$新程序\main.py" --port 8188 --listen 100.127.224.106 --extra-model-paths-config "$新程序\extra_model_paths.yaml" > "$根\logs\comfy.log" 2> "$根\logs\comfy.err"
"@
New-Item -ItemType Directory -Path "$根\logs" -Force | Out-Null
$新脚本 = "$根\启动ComfyUI.cmd"
[System.IO.File]::WriteAllText($新脚本, $cmd, [System.Text.Encoding]::GetEncoding(936))
'  写好 {0}（{1} 字节, GBK）' -f $新脚本, (Get-Item -LiteralPath $新脚本).Length
'  --- 内容 ---'
Get-Content -LiteralPath $新脚本

"`n=== 3. 改计划任务 yjcomfy 指向新脚本 ==="
$旧 = (Get-ScheduledTask -TaskName 'yjcomfy' -EA SilentlyContinue).Actions[0].Execute
'  旧的: {0}' -f $旧
$act = New-ScheduledTaskAction -Execute $新脚本
Set-ScheduledTask -TaskName 'yjcomfy' -Action $act -EA SilentlyContinue | Out-Null
$现在 = (Get-ScheduledTask -TaskName 'yjcomfy').Actions[0].Execute
'  新的: {0}' -f $现在
if ($现在 -eq $新脚本) { '  ✓ 计划任务已改' } else { '  ✗ 没改成' }

"`n=== 4. 启动它 ==="
Get-Process -Name python -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 2
Start-ScheduledTask -TaskName 'yjcomfy'
'  已触发，等它起来…'

$好 = $false
for ($i = 1; $i -le 40; $i++) {
    Start-Sleep 3
    try {
        $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 3 -EA Stop
        '  ✓ {0} 秒后起来了' -f ($i * 3)
        $好 = $true
        break
    } catch { }
}
if (-not $好) { '  ✗ 120 秒还没起来，看日志：'; Get-Content "$根\logs\comfy.err" -Tail 30 -EA SilentlyContinue }

if ($好) {
    "`n=== 5. 它在 E 盘上看到了什么 ==="
    '  版本 {0}' -f $r.system.comfyui_version
    $r.devices | ForEach-Object { '  卡 {0}  显存空闲 {1:N0}/{2:N0} MiB' -f $_.name, (($_.vram_total - $_.vram_used) / 1MB), ($_.vram_total / 1MB) }
    $oi = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/object_info/UNETLoader' -TimeoutSec 10
    '  UNETLoader 能看到的模型:'
    $oi.UNETLoader.input.required.unet_name[0] | ForEach-Object { '     {0}' -f $_ }
}

"`n=== 6. 日志尾部 ==="
Get-Content "$根\logs\comfy.log" -Tail 12 -EA SilentlyContinue
