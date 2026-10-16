$ErrorActionPreference = 'Continue'
$OutputEncoding = [Text.Encoding]::UTF8
Write-Host '=== remote internet ==='
$urls = @(
  'https://huggingface.co',
  'https://hf-mirror.com',
  'https://www.modelscope.cn',
  'https://mirrors.aliyun.com'
)
foreach ($u in $urls) {
  try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $x = Invoke-WebRequest -Uri $u -Method Head -TimeoutSec 15 -UseBasicParsing
    $sw.Stop()
    Write-Host ('  {0}  HTTP {1}  {2:N2}s' -f $u, $x.StatusCode, $sw.Elapsed.TotalSeconds)
  } catch {
    Write-Host ('  {0}  FAIL: {1}' -f $u, $_.Exception.Message)
  }
}

Write-Host ''
Write-Host '=== tools ==='
foreach ($c in @('python', 'python3', 'py', 'curl.exe', 'hf', 'aria2c', 'git', 'huggingface-cli')) {
  $p = Get-Command $c -ErrorAction SilentlyContinue
  if ($p) { Write-Host ('  OK  {0}  {1}' -f $c, $p.Source) } else { Write-Host ('  --  {0}' -f $c) }
}

Write-Host ''
Write-Host '=== disks ==='
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } | ForEach-Object {
  Write-Host ('  {0}:  used {1:N1} GB  free {2:N1} GB' -f $_.Name, ($_.Used / 1GB), ($_.Free / 1GB))
}

Write-Host ''
Write-Host '=== ComfyUI model dirs ==='
$cands = @('E:\ComfyUI-Shared\models', 'D:\ComfyUI-Shared\models', 'C:\ComfyUI-Shared\models')
$hit = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($hit) {
  Write-Host "  $hit"
  Get-ChildItem $hit -Directory | ForEach-Object {
    $n = (Get-ChildItem $_.FullName -File -Recurse -ErrorAction SilentlyContinue).Count
    Write-Host ('    {0}  {1} files' -f $_.Name, $n)
  }
} else {
  Write-Host '  ComfyUI-Shared\models NOT FOUND'
}

Write-Host ''
Write-Host '=== ComfyUI process / port ==='
$p = Get-Process python -ErrorAction SilentlyContinue
if ($p) { $p | Select-Object -First 3 | ForEach-Object { Write-Host ('  python PID {0}  {1:N0} MB' -f $_.Id, ($_.WorkingSet64/1MB)) } }
$c = Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue
if ($c) { Write-Host '  port 8188 LISTEN' } else { Write-Host '  port 8188 not listening' }
