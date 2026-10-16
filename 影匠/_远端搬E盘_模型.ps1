$ErrorActionPreference = 'Continue'
$根 = 'E:\影匠AI'

"=== 1. 建目录 ==="
foreach ($d in @(
        "$根",
        "$根\ComfyUI-Shared\models",
        "$根\ComfyUI",
        "$根\输出",
        "$根\输入"
    )) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    '  {0}  {1}' -f $(if (Test-Path -LiteralPath $d) { 'OK ' } else { 'FAIL' }), $d
}

"`n=== 2. 搬模型 D:\Comfy-Desktop\ComfyUI-Shared\models -> $根\ComfyUI-Shared\models ==="
$源 = 'D:\Comfy-Desktop\ComfyUI-Shared\models'
$标 = "$根\ComfyUI-Shared\models"
$t0 = Get-Date
robocopy $源 $标 /E /COPY:DAT /R:2 /W:5 /NP /NFL /NDL /NJH
$码 = $LASTEXITCODE
'  robocopy 退出码 {0}  用时 {1:N1} 分钟' -f $码, ((Get-Date) - $t0).TotalMinutes

"`n=== 3. 逐个校验 ==="
$坏 = 0
Get-ChildItem -LiteralPath $源 -Recurse -File -Force -EA SilentlyContinue | ForEach-Object {
    $相对 = $_.FullName.Substring($源.Length)
    $目标 = Join-Path $标 $相对
    if (-not (Test-Path -LiteralPath $目标)) {
        '  ✗ 缺   {0}' -f $相对; $坏++
    } elseif ((Get-Item -LiteralPath $目标).Length -ne $_.Length) {
        '  ✗ 大小不符  {0}  源 {1:N0} / 目标 {2:N0}' -f $相对, $_.Length, (Get-Item -LiteralPath $目标).Length; $坏++
    }
}
if ($坏 -eq 0) { '  ✓ 全部对上，0 个不符' } else { '  ✗ {0} 个不符' -f $坏 }

"`n=== 4. 两边的绝对路径与剩余空间 ==="
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    '{0}  free {1,8:N1} GB' -f $_.DeviceID, ($_.FreeSpace / 1GB)
}
'  E 盘模型目录大小 {0:N2} GB' -f ((Get-ChildItem -LiteralPath $标 -Recurse -File -Force -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB)
