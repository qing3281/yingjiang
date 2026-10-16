$ErrorActionPreference = 'Continue'
$sysPy = 'C:\Users\Seele\AppData\Local\Programs\Python\Python312\python.exe'

"=== 1. 系统 python 在不在 ==="
'  {0}  {1}' -f $sysPy, (Test-Path -LiteralPath $sysPy)

"=== 2. 清场 ==="
Get-Process -Name python -EA SilentlyContinue | ForEach-Object { '  杀 PID ' + $_.Id; $_.Kill() }
schtasks /delete /tn yjcomfy /f 2>&1 | Out-Null
schtasks /delete /tn yjlong /f 2>&1 | Out-Null
schtasks /delete /tn yjpy /f 2>&1 | Out-Null
schtasks /delete /tn yjt2 /f 2>&1 | Out-Null
Start-Sleep 3

"=== 3. 用 WMI 拉系统 python 跑 C:\yjai_run.py（命令行纯 ASCII！）==="
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = '"{0}" C:\yjai_run.py 8188' -f $sysPy
} -EA SilentlyContinue
'  WMI ReturnValue={0} PID={1}' -f $r.ReturnValue, $r.ProcessId

"=== 4. 等它起来 ==="
$起 = $false
for ($i = 1; $i -le 60; $i++) {
    Start-Sleep 4
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 4 -EA Stop; $起 = $true; break } catch { }
}
if ($起) { '  ✓✓✓ 远端 ComfyUI 起来了！（{0} 秒）' -f ($i * 4) } else { '  ✗ 240 秒还没起来' }

"=== 5. 进程 ==="
Get-Process -Name python -EA SilentlyContinue | Select-Object Id, @{n='MB';e={[int]($_.WorkingSet64/1MB)}} | ForEach-Object { '  PID {0}  {1} MB' -f $_.Id, $_.MB }

"=== 6. 日志 ==="
foreach ($f in @('E:\影匠AI\logs\comfy.log', 'E:\影匠AI\logs\comfy.err')) {
    '  --- {0}  {1} 字节' -f $f, (Get-Item -LiteralPath $f -EA SilentlyContinue).Length
    Get-Content -LiteralPath $f -Tail 12 -EA SilentlyContinue | ForEach-Object { '     ' + $_ }
}

"=== 7. 起来了就列家底 ==="
if ($起) {
    '  --- diffusion_models ---'
    (Invoke-RestMethod 'http://127.0.0.1:8188/object_info/UNETLoader' -TimeoutSec 20).UNETLoader.input.required.unet_name[0] | ForEach-Object { '     ' + $_ }
    '  --- vae ---'
    (Invoke-RestMethod 'http://127.0.0.1:8188/object_info/VAELoader' -TimeoutSec 20).VAELoader.input.required.vae_name[0] | ForEach-Object { '     ' + $_ }
    '  --- text_encoders ---'
    (Invoke-RestMethod 'http://127.0.0.1:8188/object_info/CLIPLoader' -TimeoutSec 20).CLIPLoader.input.required.clip_name[0] | ForEach-Object { '     ' + $_ }
    '  --- loras ---'
    (Invoke-RestMethod 'http://127.0.0.1:8188/object_info/LoraLoader' -TimeoutSec 20).LoraLoader.input.required.lora_name[0] | ForEach-Object { '     ' + $_ }
    $oi = Invoke-RestMethod 'http://127.0.0.1:8188/object_info' -TimeoutSec 60
    '  --- 节点 {0} 个；IndexTTS: {1}' -f ($oi.PSObject.Properties.Name.Count), ($oi.PSObject.Properties.Name -contains 'IndexTTS')
}