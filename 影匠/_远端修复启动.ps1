$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'
$新程序 = "$根\ComfyUI"
$py = "$新程序\.venv\Scripts\python.exe"

"=== 1. 远端 8188 现在活着吗 ==="
try {
    $s = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 8 -EA Stop
    '  ✓ 活着：ComfyUI {0}  python {1}  显存 {2} MB' -f $s.system.comfyui_version, $s.system.python_version, [int]($s.system.total_vram/1MB)
} catch { '  ✗ 没活：{0}' -f $_.Exception.Message }

"`n=== 2. 日志尾部（那个 ERROR 到底致不致命）==="
Get-Content -LiteralPath "$根\logs\direct.err" -Tail 8 -EA SilentlyContinue | ForEach-Object { '  ' + $_ }
Get-Content -LiteralPath "$根\logs\direct.log" -Tail 12 -EA SilentlyContinue | ForEach-Object { '  ' + $_ }

"`n=== 3. 装那个缺的包（它只是报 ERROR，不致命，但装上免得每回吓一跳）==="
& $py -m pip install comfyui-workflow-templates --quiet --disable-pip-version-check 2>&1 | Select-Object -Last 5 | ForEach-Object { '  ' + $_ }

"`n=== 4. ★ 关键修复：启动器放到【不含中文】的路径 ==="
# 上次失败的原因：Start-Process/计划任务把含中文的命令行交给 cmd.exe 时被代码页搞坏了，
# 所以 "E:\影匠AI\启动ComfyUI.cmd" 这条路根本执行不进去（调试副本连输出文件都没生成）。
# 解法：写一个纯 ASCII 路径的 .cmd，中文路径写在【文件内部】（用 GBK 存，cmd 自己读得对）。
$启动器 = 'C:\yjai_start.cmd'
$c = @"
@echo off
chcp 936 >nul
cd /d $新程序
"$py" -X utf8 "$新程序\main.py" --port 8188 --listen 0.0.0.0 --extra-model-paths-config "$新程序\extra_model_paths.yaml" 1>> "$根\logs\comfy.log" 2>> "$根\logs\comfy.err"
"@
[System.IO.File]::WriteAllText($启动器, $c, [System.Text.Encoding]::GetEncoding(936))
'  写好 {0}（{1} 字节）' -f $启动器, (Get-Item -LiteralPath $启动器).Length
'  --- 内容 ---'
Get-Content -LiteralPath $启动器 -Encoding Default | ForEach-Object { '    ' + $_ }

"`n=== 5. 杀掉旧的，用新启动器起 ==="
Get-Process -Name python -EA SilentlyContinue | ForEach-Object { '  杀 PID {0}' -f $_.Id; $_.Kill() }
Start-Sleep 3
Remove-Item -LiteralPath "$根\logs\comfy.log", "$根\logs\comfy.err" -Force -EA SilentlyContinue
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $启动器 -WindowStyle Hidden
$起 = $false
for ($i = 1; $i -le 50; $i++) {
    Start-Sleep 3
    try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 4 -EA Stop; $起 = $true; break } catch { }
}
if ($起) { '  ✓✓ 新启动器成功！（{0} 秒）' -f ($i * 3) } else { '  ✗ 还是没起来' }

"`n=== 6. 起来了 —— 把远端家底全列出来（后面做双线要对齐）==="
if ($起) {
    '  --- diffusion_models ---'
    (Invoke-RestMethod 'http://127.0.0.1:8188/object_info/UNETLoader' -TimeoutSec 10).UNETLoader.input.required.unet_name[0] | ForEach-Object { '     ' + $_ }
    '  --- vae ---'
    (Invoke-RestMethod 'http://127.0.0.1:8188/object_info/VAELoader' -TimeoutSec 10).VAELoader.input.required.vae_name[0] | ForEach-Object { '     ' + $_ }
    '  --- text_encoders ---'
    (Invoke-RestMethod 'http://127.0.0.1:8188/object_info/CLIPLoader' -TimeoutSec 10).CLIPLoader.input.required.clip_name[0] | ForEach-Object { '     ' + $_ }
    '  --- loras ---'
    (Invoke-RestMethod 'http://127.0.0.1:8188/object_info/LoraLoader' -TimeoutSec 10).LoraLoader.input.required.lora_name[0] | ForEach-Object { '     ' + $_ }
    '  --- 节点总数 ---'
    $oi = Invoke-RestMethod 'http://127.0.0.1:8188/object_info' -TimeoutSec 30
    '     {0} 个节点' -f ($oi.PSObject.Properties.Name.Count)
    '     IndexTTS 在不在: {0}' -f ($oi.PSObject.Properties.Name -contains 'IndexTTS')
}

"`n=== 7. 注册计划任务（用新启动器的纯 ASCII 路径）==="
$act = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c C:\yjai_start.cmd"
$trg = New-ScheduledTaskTrigger -AtStartup
$set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'yjcomfy' -Action $act -Trigger $trg -Settings $set -Force -RunLevel Highest -EA SilentlyContinue | Out-Null
$t = Get-ScheduledTask -TaskName 'yjcomfy' -EA SilentlyContinue
if ($t) { '  任务 yjcomfy: State={0}  Action={1} {2}' -f $t.State, $t.Actions[0].Execute, $t.Actions[0].Arguments }
