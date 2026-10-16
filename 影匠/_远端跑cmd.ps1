$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$脚本 = "$根\启动ComfyUI.cmd"

"=== 1. 先杀掉可能残留的 python ==="
Get-Process -Name python -EA SilentlyContinue | ForEach-Object { '  杀 PID {0}' -f $_.Id; $_.Kill() }
Start-Sleep 3

"=== 2. 直接跑那个 .cmd（不信计划任务，直接看它自己行不行）==="
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', "`"$脚本`"" -WindowStyle Hidden
'  已拉起，等 8188…'
$起 = $false
for ($i = 1; $i -le 40; $i++) {
    Start-Sleep 3
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 3 -EA Stop; $起 = $true; break } catch { }
}
if ($起) { '  ✓ .cmd 直接跑得起来（{0} 秒）' -f ($i * 3) } else { '  ✗ 120 秒没起来' }

"=== 3. 日志 ==="
foreach ($f in @("$根\logs\comfy.log", "$根\logs\comfy.err")) {
    '  --- {0}  {1} 字节' -f $f, (Get-Item -LiteralPath $f -EA SilentlyContinue).Length
    if (Test-Path -LiteralPath $f) { Get-Content -LiteralPath $f -Tail 15 -EA SilentlyContinue | ForEach-Object { '     ' + $_ } }
}

"=== 4. 起来了就看看模型 ==="
if ($起) {
    $oi = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/object_info/UNETLoader' -TimeoutSec 10
    '  UNETLoader 看到 {0} 个模型:' -f $oi.UNETLoader.input.required.unet_name[0].Count
    $oi.UNETLoader.input.required.unet_name[0] | ForEach-Object { '     {0}' -f $_ }
    $cl = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/object_info/CLIPLoader' -TimeoutSec 10
    '  CLIPLoader 看到:'
    $cl.CLIPLoader.input.required.clip_name[0] | ForEach-Object { '     {0}' -f $_ }
    $va = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/object_info/VAELoader' -TimeoutSec 10
    '  VAELoader 看到:'
    $va.VAELoader.input.required.vae_name[0] | ForEach-Object { '     {0}' -f $_ }
}
