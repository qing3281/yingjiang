$ErrorActionPreference = 'Continue'

function Get-Size($p) {
    if (-not (Test-Path -LiteralPath $p)) { return $null }
    $f = Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue
    $s = ($f | Measure-Object Length -Sum).Sum
    [PSCustomObject]@{ Path = $p; GB = [math]::Round($s / 1GB, 2); Files = $f.Count }
}

"=== DRIVES ==="
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    $t = [math]::Round($_.Size / 1GB, 1)
    $fr = [math]::Round($_.FreeSpace / 1GB, 1)
    '{0}  total {1,8} GB  free {2,8} GB' -f $_.DeviceID, $t, $fr
}

"`n=== COMFY-RELATED ON D: ==="
$targets = @(
    'D:\Comfy-Desktop',
    'D:\Comfy-Desktop\ComfyUI-Shared',
    'D:\Comfy-Desktop\ComfyUI-Shared\models',
    'D:\Comfy-Desktop\ComfyUI-Installs',
    'D:\Comfy-Desktop\ComfyUI-Cache',
    'D:\ComfyUI',
    'D:\ComfyUI-Shared'
)
$sum = 0
foreach ($p in $targets) {
    $r = Get-Size $p
    if ($r) {
        '  {0,9:N2} GB  {1,7} files  {2}' -f $r.GB, $r.Files, $r.Path
        $sum += $r.GB
    } else {
        '  {0,9}      {1,7}        {2}  <-- MISSING' -f '-', '-', $p
    }
}
'  ----------------------------------------'
'  {0,9:N2} GB  TOTAL' -f $sum

"`n=== MODEL SUBDIRS ==="
$m = 'D:\Comfy-Desktop\ComfyUI-Shared\models'
if (Test-Path -LiteralPath $m) {
    Get-ChildItem -LiteralPath $m -Directory -Force -EA SilentlyContinue | ForEach-Object {
        $r = Get-Size $_.FullName
        '  {0,9:N2} GB  {1,5} files  {2}' -f $r.GB, $r.Files, $_.Name
    }
}

"`n=== E: ==="
Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='E:'" | ForEach-Object {
    '  total {0:N1} GB  free {1:N1} GB' -f ($_.Size / 1GB), ($_.FreeSpace / 1GB)
}

"`n=== RUNNING? ==="
$p = Get-Process -Name python, python3, ComfyUI -EA SilentlyContinue
if ($p) { $p | ForEach-Object { '  RUNNING: {0} PID={1}' -f $_.ProcessName, $_.Id } } else { '  no python process -- not running' }
$l = Get-NetTCPConnection -LocalPort 8188 -State Listen -EA SilentlyContinue
if ($l) { '  port 8188 LISTENING' } else { '  port 8188 not listening' }

"`n=== DEPLOY JUNK I LEFT ON D:\ ==="
Get-ChildItem 'D:\' -File -Force -EA SilentlyContinue |
    Where-Object { $_.Name -match '^(comfy|deploy|fixdl|clipdl)' } |
    ForEach-Object { '  {0,9:N1} KB  {1}' -f ($_.Length / 1KB), $_.Name }

"`n=== TOP-LEVEL D: FOLDERS ==="
Get-ChildItem 'D:\' -Directory -Force -EA SilentlyContinue | ForEach-Object {
    $r = Get-Size $_.FullName
    '  {0,9:N2} GB  {1}' -f $r.GB, $_.Name
} | Sort-Object
