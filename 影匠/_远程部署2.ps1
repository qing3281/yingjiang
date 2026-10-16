# =====================================================================
# YingJiang - remote ComfyUI bootstrap, take 2   (ASCII ONLY)
# ---------------------------------------------------------------------
# Why take 2: take 1 died with "No pyvenv.cfg file". Root cause: it made
# the venv at   <root>\.venv   but then ran pip from   <root>\ComfyUI\.venv
# -- two different paths. Both were half-made, neither was usable.
# Here there is exactly ONE venv variable and nothing else invents paths.
#
# Why schtasks: take 1 ran as a child of an ssh session. When the ssh
# session goes away the child can be killed mid-install. A scheduled task
# is owned by the service, not by ssh, so it survives and can be checked
# later from a fresh connection.
#
# Why a mirror for torch: download.pytorch.org from CN moves at a few
# hundred KB/s; the aliyun wheel mirror is the same bytes at LAN speed.
# =====================================================================
$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

$LOG    = 'D:\deploy2.log'
$curl   = 'C:\WINDOWS\system32\curl.exe'
$root   = 'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI'
$repo   = "$root\ComfyUI"
$venv   = "$repo\.venv"
$vpy    = "$venv\Scripts\python.exe"
$syspy  = 'C:\Users\Seele\AppData\Local\Programs\Python\Python312\python.exe'
$tuna   = 'https://pypi.tuna.tsinghua.edu.cn/simple'
$torch  = 'https://mirrors.aliyun.com/pytorch-wheels/cu130'

function Note($m) {
  ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) | Out-File -FilePath $LOG -Append -Encoding UTF8
}
function Step($name, [scriptblock]$body) {
  Note ('>>> START  ' + $name)
  $t = Get-Date
  try { & $body } catch { Note ('    !! EXCEPTION: ' + $_.Exception.Message) }
  Note ('<<< END    ' + $name + '   ' + [math]::Round(((Get-Date) - $t).TotalSeconds,1) + ' s')
}

'' | Out-File -FilePath $LOG -Encoding UTF8
Note '===== remote deploy take 2 ====='

Step 'kill leftovers' {
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*pip install*' } |
    ForEach-Object { Note ('    kill pid ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep 2
}

Step 'rebuild venv' {
  if (Test-Path $venv) { Remove-Item $venv -Recurse -Force -ErrorAction SilentlyContinue }
  & $syspy -m venv $venv 2>&1 | ForEach-Object { Note ('    ' + $_) }
  Note ('    pyvenv.cfg now: ' + (Test-Path "$venv\pyvenv.cfg"))
  Note ('    python.exe now: ' + (Test-Path $vpy))
  & $vpy -m pip install --upgrade pip -i $tuna 2>&1 | Select-Object -Last 3 | ForEach-Object { Note ('    ' + $_) }
}

Step 'torch cu130 (~3GB, from aliyun mirror)' {
  # RTX 5080 is Blackwell sm_120 -- needs cu128 or newer. cu130 is the safe pick.
  & $vpy -m pip install torch torchvision torchaudio --index-url $torch 2>&1 |
    Select-Object -Last 12 | ForEach-Object { Note ('    ' + $_) }
  & $vpy -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.version.cuda)" 2>&1 |
    ForEach-Object { Note ('    ' + $_) }
}

Step 'comfy requirements' {
  if (Test-Path "$repo\requirements.txt") {
    & $vpy -m pip install -r "$repo\requirements.txt" -i $tuna 2>&1 |
      Select-Object -Last 12 | ForEach-Object { Note ('    ' + $_) }
  } else { Note '    no requirements.txt' }
}

Step 'health check' {
  & $vpy -c "import torch,sys;print('python',sys.version.split()[0]);print('torch',torch.__version__);print('cuda_available',torch.cuda.is_available());print('device',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')" 2>&1 |
    ForEach-Object { Note ('    ' + $_) }
  Note ('    repo main.py: ' + (Test-Path "$repo\main.py"))
  $n = (Get-ChildItem $repo -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
  Note ('    repo files  : ' + $n)
}

Note '===== remote deploy take 2 end ====='
