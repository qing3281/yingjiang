$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$源程序 = 'D:\ComfyUI'
$标程序 = "$根\ComfyUI"

"=== 1. 搬程序 $源程序 -> $标程序 （3.85 GB / 6 万文件）==="
$t0 = Get-Date
robocopy $源程序 $标程序 /E /COPY:DAT /R:2 /W:5 /NP /NFL /NDL /NJH /XD __pycache__ temp
'  robocopy 退出码 {0}  用时 {1:N1} 分钟' -f $LASTEXITCODE, ((Get-Date) - $t0).TotalMinutes

"`n=== 2. 校验关键文件在不在、大小对不对 ==="
$关键 = @('main.py', 'nodes.py', 'folder_paths.py', 'execution.py', 'extra_model_paths.yaml', '.venv\Scripts\python.exe', '.venv\pyvenv.cfg', 'requirements.txt')
foreach ($k in $关键) {
    $a = Join-Path $源程序 $k
    $b = Join-Path $标程序 $k
    if (-not (Test-Path -LiteralPath $a)) { '  -- 源里就没有  {0}' -f $k; continue }
    $sa = (Get-Item -LiteralPath $a).Length
    if (-not (Test-Path -LiteralPath $b)) { '  ✗ 缺      {0}' -f $k; continue }
    $sb = (Get-Item -LiteralPath $b).Length
    if ($sa -eq $sb) { '  ✓ {0,10:N0} B  {1}' -f $sb, $k } else { '  ✗ 大小不符 {0}  源 {1:N0} / 目标 {2:N0}' -f $k, $sa, $sb }
}

"`n=== 3. 改 extra_model_paths.yaml 指向 E 盘 ==="
$y = Join-Path $标程序 'extra_model_paths.yaml'
$新 = @"
comfyui:
    base_path: E:/影匠AI/ComfyUI-Shared/models/
    checkpoints: checkpoints
    diffusion_models: diffusion_models
    loras: loras
    vae: vae
    text_encoders: text_encoders
    upscale_models: upscale_models
    model_patches: model_patches
"@
[System.IO.File]::WriteAllText($y, $新, [System.Text.UTF8Encoding]::new($false))
'  写好 {0}（{1} 字节，UTF-8 无 BOM）' -f $y, (Get-Item -LiteralPath $y).Length
Get-Content -LiteralPath $y

"`n=== 4. 现有的启动脚本长什么样 ==="
$bat = 'D:\启动ComfyUI.cmd'
if (Test-Path -LiteralPath $bat) {
    '--- {0}' -f $bat
    Get-Content -LiteralPath $bat -Raw
} else { '  ✗ 找不到 {0}' -f $bat }
Get-ChildItem 'D:\' -File -Force -EA SilentlyContinue -Filter '*ComfyUI*.cmd' | ForEach-Object { '  找到: {0}' -f $_.FullName }

"`n=== 5. 计划任务 yjcomfy 详情 ==="
$t = Get-ScheduledTask -TaskName 'yjcomfy' -EA SilentlyContinue
if ($t) {
    $t.Actions | ForEach-Object { '  EXEC: {0}' -f $_.Execute }
    ($t | Get-ScheduledTaskInfo) | ForEach-Object { '  上次运行 {0}  结果 {1}' -f $_.LastRunTime, $_.LastTaskResult }
    '  主体: {0}' -f ($t.Principal.UserId)
}
