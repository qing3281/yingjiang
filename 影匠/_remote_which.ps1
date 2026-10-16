$ErrorActionPreference = 'Continue'

"=== WHICH COMFYUI IS THE REAL ONE ==="
foreach ($p in @('D:\ComfyUI', 'D:\Comfy-Desktop\ComfyUI-Installs')) {
    "--- $p"
    if (Test-Path -LiteralPath $p) {
        Get-ChildItem -LiteralPath $p -Force -EA SilentlyContinue |
            Select-Object -First 15 | ForEach-Object {
                '    {0}  {1}' -f $(if ($_.PSIsContainer) { '<DIR> ' } else { '{0,7:N0}' -f $_.Length }), $_.Name
            }
    } else { '    MISSING' }
}

"`n=== main.py / run scripts anywhere on D: ==="
Get-ChildItem 'D:\' -Recurse -Depth 3 -File -Force -EA SilentlyContinue -Include 'main.py', 'run_*.bat', 'run_*.ps1', '*comfy*.bat', '*comfy*.ps1', 'start*.bat' |
    Select-Object -First 25 | ForEach-Object { '  {0,9:N0}  {1}' -f $_.Length, $_.FullName }

"`n=== how is 8188 started? check scheduled tasks + startup ==="
Get-ScheduledTask -EA SilentlyContinue | Where-Object { $_.TaskName -match 'comfy' -or $_.TaskPath -match 'comfy' } |
    ForEach-Object { '  TASK: {0}{1}  {2}' -f $_.TaskPath, $_.TaskName, $_.State }
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup" -Force -EA SilentlyContinue |
    ForEach-Object { '  STARTUP: {0}' -f $_.Name }

"`n=== ComfyUI Desktop config (where it points models) ==="
foreach ($c in @(
    "$env:APPDATA\ComfyUI\config.json",
    "$env:APPDATA\ComfyUI\extra_models_config.yaml",
    "$env:LOCALAPPDATA\Programs\@comfyorgcomfyui-electron\resources\ComfyUI\extra_model_paths.yaml"
)) {
    if (Test-Path -LiteralPath $c) { "--- $c"; Get-Content -LiteralPath $c -Raw -EA SilentlyContinue }
}

"`n=== search extra_model_paths.yaml ==="
Get-ChildItem 'D:\' -Recurse -Depth 4 -File -Force -EA SilentlyContinue -Filter 'extra_model_paths.yaml' |
    ForEach-Object { '  {0}' -f $_.FullName }

"`n=== python environments ==="
Get-ChildItem 'D:\' -Recurse -Depth 4 -File -Force -EA SilentlyContinue -Filter 'python.exe' |
    Select-Object -First 10 | ForEach-Object { '  {0}' -f $_.FullName }
