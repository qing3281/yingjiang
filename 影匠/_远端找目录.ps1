$ErrorActionPreference = 'Continue'
Write-Host '=== find ComfyUI on remote ==='
$roots = @('C:\', 'D:\', 'E:\')
foreach ($r in $roots) {
  Get-ChildItem $r -Directory -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match 'Comfy|comfy'
  } | ForEach-Object { Write-Host ('  ' + $_.FullName) }
}
Write-Host ''
Write-Host '=== processes with ComfyUI in cmdline ==='
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
  $cl = $_.CommandLine
  if ($cl) { Write-Host ('  PID {0}  {1}' -f $_.ProcessId, $cl.Substring(0, [Math]::Min(200, $cl.Length))) }
}
Write-Host ''
Write-Host '=== look for models dirs ==='
foreach ($r in @('C:\', 'D:\', 'E:\')) {
  Get-ChildItem $r -Directory -Filter 'models' -Recurse -Depth 3 -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'Comfy' } |
    Select-Object -First 5 | ForEach-Object { Write-Host ('  ' + $_.FullName) }
}
