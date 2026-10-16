$ErrorActionPreference = 'Continue'

"=== extra_model_paths.yaml ==="
Get-Content -LiteralPath 'D:\ComfyUI\extra_model_paths.yaml' -Raw -EA SilentlyContinue

"`n=== scheduled task yjcomfy ==="
$t = Get-ScheduledTask -TaskName 'yjcomfy' -EA SilentlyContinue
if ($t) {
    $t.Actions | ForEach-Object { '  EXEC: {0}' -f $_.Execute; '  ARGS: {0}' -f $_.Arguments; '  CWD : {0}' -f $_.WorkingDirectory }
    $t.Triggers | ForEach-Object { '  TRIG: {0}' -f $_.CimClass.CimClassName }
    $t.Settings | ForEach-Object { '  ENABLED: {0}' -f $_.Enabled }
}

"`n=== D:\ComfyUI top level ==="
Get-ChildItem 'D:\ComfyUI' -Force -EA SilentlyContinue | ForEach-Object {
    '  {0}  {1}' -f $(if ($_.PSIsContainer) { '<DIR> ' } else { '{0,9:N0}' -f $_.Length }), $_.Name
}

"`n=== D:\ComfyUI\models ==="
Get-ChildItem 'D:\ComfyUI\models' -Force -EA SilentlyContinue | ForEach-Object {
    if ($_.PSIsContainer) {
        $f = Get-ChildItem $_.FullName -Recurse -File -Force -EA SilentlyContinue
        '  {0,9:N2} GB  {1,5} files  {2}' -f (($f | Measure-Object Length -Sum).Sum / 1GB), $f.Count, $_.Name
    }
}

"`n=== ComfyUI Desktop app data dir (where the Desktop app keeps models) ==="
foreach ($p in @("$env:APPDATA\ComfyUI", "$env:LOCALAPPDATA\ComfyUI")) {
    if (Test-Path -LiteralPath $p) {
        "--- $p"
        Get-ChildItem -LiteralPath $p -Force -Recurse -Depth 1 -EA SilentlyContinue |
            Select-Object -First 20 | ForEach-Object { '    {0}' -f $_.FullName }
    }
}

"`n=== which arg / bat is running 8188? check recent cmd history in registry ==="
$k = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU'
if (Test-Path $k) { (Get-ItemProperty $k).PSObject.Properties | Where-Object { $_.Name -notmatch '^PS' } | ForEach-Object { '  {0} = {1}' -f $_.Name, $_.Value } }

"`n=== any .bat at D:\ root or D:\ComfyUI ==="
Get-ChildItem 'D:\ComfyUI' -File -Force -EA SilentlyContinue -Filter '*.bat' | ForEach-Object { '  {0}' -f $_.FullName }
Get-ChildItem 'D:\ComfyUI' -File -Force -EA SilentlyContinue -Filter '*.yaml' | ForEach-Object { '  {0}' -f $_.FullName }
