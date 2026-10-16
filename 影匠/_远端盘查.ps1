$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function 量($路) {
    if (-not (Test-Path $路)) { return $null }
    $f = Get-ChildItem $路 -Recurse -File -Force -ErrorAction SilentlyContinue
    $s = ($f | Measure-Object Length -Sum).Sum
    [PSCustomObject]@{ 路 = $路; GB = [math]::Round($s / 1GB, 2); 文件 = $f.Count }
}

"=== 磁盘 ==="
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    $t = [math]::Round($_.Size / 1GB, 1)
    $fr = [math]::Round($_.FreeSpace / 1GB, 1)
    '{0}  总 {1,8} GB  空闲 {2,8} GB' -f $_.DeviceID, $t, $fr
}

"`n=== 远端 D 盘上跟 ComfyUI 有关的东西 ==="
$要看 = @(
    'D:\Comfy-Desktop',
    'D:\Comfy-Desktop\ComfyUI-Shared',
    'D:\Comfy-Desktop\ComfyUI-Shared\models',
    'D:\Comfy-Desktop\ComfyUI-Installs',
    'D:\Comfy-Desktop\ComfyUI-Cache',
    'D:\ComfyUI',
    'D:\ComfyUI-Shared'
)
$总 = 0
foreach ($p in $要看) {
    $r = 量 $p
    if ($r) { '  {0,9:N2} GB  {1,7} 文件  {2}' -f $r.GB, $r.文件, $r.路; $总 += $r.GB }
    else { '  {0,9}     {1,7}       {2}   ← 不存在' -f '-', '-', $p }
}
'  ────────────────────────────────────────'
'  {0,9:N2} GB  合计' -f $总

"`n=== 模型分部 ==="
$m = 'D:\Comfy-Desktop\ComfyUI-Shared\models'
if (Test-Path $m) {
    Get-ChildItem $m -Directory -Force -EA SilentlyContinue | ForEach-Object {
        $r = 量 $_.FullName
        '  {0,9:N2} GB  {1,5} 文件  {2}' -f $r.GB, $r.文件, $_.Name
    }
}

"`n=== E 盘现状 ==="
Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='E:'" | ForEach-Object {
    '  总 {0:N1} GB  空闲 {1:N1} GB' -f ($_.Size / 1GB), ($_.FreeSpace / 1GB)
}
"`n=== ComfyUI 在跑吗 ==="
$p = Get-Process -Name python, python3, ComfyUI -EA SilentlyContinue
if ($p) { $p | ForEach-Object { '  运行中: {0} PID={1}' -f $_.ProcessName, $_.Id } } else { '  没有 python 进程 —— 没在跑' }
$l = Get-NetTCPConnection -LocalPort 8188 -State Listen -EA SilentlyContinue
if ($l) { '  8188 端口在监听' } else { '  8188 端口没监听' }

"`n=== 我留下的部署垃圾 ==="
Get-ChildItem 'D:\' -File -Force -EA SilentlyContinue |
    Where-Object { $_.Name -match '^(comfy|deploy|fixdl|clipdl)' } |
    ForEach-Object { '  {0,9:N1} KB  {1}' -f ($_.Length / 1KB), $_.Name }
