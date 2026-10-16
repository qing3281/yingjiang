# =====================================================================
# YingJiang - remote ComfyUI bootstrap  (ASCII ONLY - do not add Chinese)
# ---------------------------------------------------------------------
# Why ASCII only: this file is executed by Windows PowerShell 5.1 on a
# zh-CN box. A UTF-8 file WITHOUT BOM gets read as GBK, so every Chinese
# path inside turns into garbage and the script dies on line 1.
# Same reason the log is D:\deploy.log and not a Chinese name.
#
# Why this shape: previous attempts ran over a bare ssh command and their
# output was swallowed by the pipe, so a stall was invisible. This one
# logs every step with start/end and elapsed seconds to D:\deploy.log.
# =====================================================================
$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

$LOG = 'D:\deploy.log'
function Note($m) {
  $line = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  $line | Out-File -FilePath $LOG -Append -Encoding UTF8
}
function Step($name, [scriptblock]$body) {
  Note ('>>> START  ' + $name)
  $t = Get-Date
  try { & $body } catch { Note ('    !! EXCEPTION: ' + $_.Exception.Message) }
  $sec = [math]::Round(((Get-Date) - $t).TotalSeconds, 1)
  Note ('<<< END    ' + $name + '   ' + $sec + ' s')
}

$curl = 'C:\WINDOWS\system32\curl.exe'
$root = 'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI'
$repo = "$root\ComfyUI"
$py   = 'C:\Users\Seele\AppData\Local\Programs\Python\Python312\python.exe'
$tsinghua = 'https://pypi.tuna.tsinghua.edu.cn/simple'

'' | Out-File -FilePath $LOG -Encoding UTF8
Note '===== remote deploy start ====='
Note ('curl   : ' + ((& $curl --version) | Select-Object -First 1))
Note ('python : ' + $py + '   exists=' + (Test-Path $py))

# ---- 1) kill leftover ssh shells from earlier attempts ----------------
Step 'kill orphan powershell' {
  $me = $PID
  Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.ProcessId -ne $me -and $_.CommandLine -like '*EncodedCommand*' } |
    ForEach-Object {
      Note ('    kill pid ' + $_.ProcessId)
      Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# ---- 2) ComfyUI source ------------------------------------------------
Step 'ComfyUI source' {
  $hasSrc = Test-Path "$repo\main.py"
  Note ('    main.py already there: ' + $hasSrc)
  if (-not $hasSrc) {
    $zip = 'D:\comfyui.zip'
    # NOTE repo moved: comfyanonymous/ComfyUI now 301s to Comfy-Org/ComfyUI.
    # Asking a proxy for the OLD name makes it chase a redirect it cannot
    # resume (-C -), and the transfer silently stalls. Always use the new
    # name, and always name the proxy too (gh-proxy.com measured 200 OK).
    $urls = @(
      'https://gh-proxy.com/https://github.com/Comfy-Org/ComfyUI/archive/refs/heads/master.zip',
      'https://ghproxy.net/https://github.com/Comfy-Org/ComfyUI/archive/refs/heads/master.zip',
      'https://ghfast.top/https://github.com/Comfy-Org/ComfyUI/archive/refs/heads/master.zip',
      'https://github.com/Comfy-Org/ComfyUI/archive/refs/heads/master.zip'
    )
    $good = $false
    if ((Test-Path $zip) -and (Get-Item $zip).Length -gt 5MB) { $good = $true; Note '    zip already present, skip download' }
    if (-not $good) {
      foreach ($u in $urls) {
        $host_ = ([uri]$u).Host
        Note ('    try ' + $host_)
        # fresh download each mirror: resume + redirect is what stalled before
        if (Test-Path $zip) { Remove-Item $zip -Force -ErrorAction SilentlyContinue }
        & $curl -L --fail --no-progress-meter --retry 3 --retry-delay 3 --retry-all-errors `
                --connect-timeout 20 --max-time 600 -o $zip $u 2>&1 | Out-Null
        $mb = if (Test-Path $zip) { (Get-Item $zip).Length / 1MB } else { 0 }
        Note ('    -> {0:N1} MB   exit={1}' -f $mb, $LASTEXITCODE)
        if ($mb -gt 5) { break }
      }
    }
    if (-not (Test-Path $zip) -or (Get-Item $zip).Length -lt 5MB) { throw 'all mirrors failed for zip' }

    Note '    extracting (tar.exe) ...'
    $tmp = 'D:\comfyui_x'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    & tar.exe -xf $zip -C $tmp 2>&1 | Out-Null
    Note ('    tar exit=' + $LASTEXITCODE)
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    if (-not $inner) { throw 'nothing extracted' }
    if (Test-Path $repo) { Remove-Item $repo -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    Move-Item $inner.FullName $repo
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
  }
  if (-not (Test-Path "$repo\main.py")) { throw 'still no main.py' }
  Note ('    files: ' + (Get-ChildItem $repo -Recurse -File).Count)
}

# ---- 3) venv ----------------------------------------------------------
Step 'venv' {
  $venv = "$repo\.venv"
  $vpy  = "$venv\Scripts\python.exe"
  if (-not (Test-Path $vpy)) {
    Note '    creating venv ...'
    & $py -m venv $venv 2>&1 | Out-Null
  }
  if (-not (Test-Path $vpy)) { throw 'venv creation failed' }
  Note ('    ' + (& $vpy --version 2>&1))
  & $vpy -m pip install --upgrade pip -q -i $tsinghua 2>&1 | Out-Null
  Note '    pip upgraded'
}

# ---- 4) torch  (RTX 5080 = sm_120 -> needs cu128 or newer) ------------
Step 'torch cu130 (~3 GB, slowest step)' {
  $vpy = "$repo\.venv\Scripts\python.exe"
  $cur = & $vpy -c "import torch;print(torch.__version__)" 2>&1
  if ($LASTEXITCODE -eq 0 -and "$cur" -notmatch 'Error|Traceback') {
    Note ('    already installed: ' + $cur)
  } else {
    & $vpy -m pip install torch torchvision torchaudio `
        --index-url https://download.pytorch.org/whl/cu130 --no-cache-dir 2>&1 |
      Select-String -Pattern 'Downloading|Successfully installed|ERROR' |
      Select-Object -Last 20 |
      ForEach-Object { Note ('      ' + $_.Line) }
  }
  $probe = @'
import torch
print('torch', torch.__version__, 'cuda', torch.version.cuda, 'avail', torch.cuda.is_available())
if torch.cuda.is_available():
    print('gpu', torch.cuda.get_device_name(0), 'cc', torch.cuda.get_device_capability(0))
'@
  $probe | Out-File -FilePath 'D:\_probe.py' -Encoding ASCII
  & $vpy 'D:\_probe.py' 2>&1 | ForEach-Object { Note ('    ' + $_) }
}

# ---- 5) ComfyUI requirements -----------------------------------------
Step 'ComfyUI requirements' {
  $vpy = "$repo\.venv\Scripts\python.exe"
  & $vpy -m pip install -r "$repo\requirements.txt" -q -i $tsinghua 2>&1 |
    Select-String -Pattern 'ERROR|error:' | Select-Object -First 10 |
    ForEach-Object { Note ('      ' + $_.Line) }
  Note '    requirements done'
}

# ---- 6) health check --------------------------------------------------
Step 'health check' {
  $vpy = "$repo\.venv\Scripts\python.exe"
  Note ('    ' + (& $vpy --version 2>&1))
  $mods = @'
mods = ['torch','torchvision','torchaudio','numpy','PIL','aiohttp','yarl',
        'sqlalchemy','einops','transformers','safetensors',
        'comfyui_frontend_package','comfyui_workflow_templates']
for m in mods:
    try:
        __import__(m); print('      OK   ' + m)
    except Exception as e:
        print('      --   ' + m + '  (' + type(e).__name__ + ')')
'@
  $mods | Out-File -FilePath 'D:\_mods.py' -Encoding ASCII
  & $vpy 'D:\_mods.py' 2>&1 | ForEach-Object { Note $_ }
}

Note '===== remote deploy end ====='
