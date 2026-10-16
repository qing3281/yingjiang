# =====================================================================
# YingJiang - remote ComfyUI bootstrap, take 3   (ASCII ONLY)
# ---------------------------------------------------------------------
# What take 1 and 2 got wrong, so take 3 does not repeat them:
#
#   1. The ComfyUI zip unpacks to a "ComfyUI-master\" SUBFOLDER. Take 1
#      and 2 both checked for <root>\ComfyUI\main.py and reported "no
#      main.py" even though 1296 files had landed -- they were one level
#      down. Take 3 copies the files up instead of assuming.
#
#   2. A venv that is mid-`pip install` cannot be deleted: python.exe is
#      held open, Remove-Item fails with "Permission denied", and you are
#      left with a half-venv that has python.exe but no pip. Take 3 kills
#      the holders, waits for the handle to actually drop, and only then
#      deletes -- and it verifies the delete worked instead of trusting it.
#
#   3. ssh is a bad parent for a 3 GB download. Take 3 is launched by
#      schtasks, so it is owned by the service and cannot be reaped when a
#      connection closes.
#
#   4. download.pytorch.org from CN is a few hundred KB/s. The aliyun
#      wheel mirror is the same bytes at LAN speed.
#
# Runs idempotently: re-running after a failure picks up where it stopped.
# =====================================================================
$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

$LOG    = 'D:\deploy3.log'
$curl   = 'C:\WINDOWS\system32\curl.exe'
$repo   = 'D:\ComfyUI'
$venv   = "$repo\.venv"
$vpy    = "$venv\Scripts\python.exe"
$syspy  = 'C:\Users\Seele\AppData\Local\Programs\Python\Python312\python.exe'
$tuna   = 'https://pypi.tuna.tsinghua.edu.cn/simple'
$torch  = 'https://download.pytorch.org/whl/cu130'
$shared = 'D:\Comfy-Desktop\ComfyUI-Shared\models'
$stage  = 'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\ComfyUI-master'

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
Note '===== remote deploy take 3 ====='

Step 'kill holders' {
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    ForEach-Object {
      if ($_.CommandLine -like '*pip*' -or $_.CommandLine -like '*ComfyUI*' -or $_.CommandLine -like '*.venv*') {
        Note ('    kill pid ' + $_.ProcessId)
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
      }
    }
  Start-Sleep 5
}

Step 'lay out source' {
  if (-not (Test-Path "$repo\main.py")) {
    if (Test-Path "$stage\main.py") {
      Note '    copying ComfyUI-master\* -> D:\ComfyUI\'
      New-Item -ItemType Directory -Force -Path $repo | Out-Null
      Copy-Item "$stage\*" $repo -Recurse -Force -ErrorAction SilentlyContinue
    } else {
      Note '    !! no staged source found anywhere'
      foreach ($p in @($stage, "$repo\ComfyUI-master")) {
        Note ('    look: ' + $p + ' -> ' + (Test-Path $p))
      }
    }
  } else { Note '    main.py already in place' }
  Note ('    main.py : ' + (Test-Path "$repo\main.py"))
  Note ('    nodes.py: ' + (Test-Path "$repo\nodes.py"))
  Note ('    files   : ' + (Get-ChildItem $repo -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count)

  # ComfyUI desktop keeps the models elsewhere; a standalone tree must be
  # told where they are or it will try to download 240 GB again.
  $yaml = @"
comfyui:
    base_path: $shared
    checkpoints: checkpoints
    diffusion_models: diffusion_models
    loras: loras
    text_encoders: text_encoders
    vae: vae
    upscale_models: upscale_models
    model_patches: model_patches
"@
  $yaml | Out-File -FilePath "$repo\extra_model_paths.yaml" -Encoding ASCII
  Note ('    extra_model_paths.yaml -> shared root exists: ' + (Test-Path $shared))
}

Step 'rebuild venv' {
  if (Test-Path $venv) {
    Remove-Item $venv -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $venv) { Note '    !! still there after delete, retrying once'; Start-Sleep 5; Remove-Item $venv -Recurse -Force -ErrorAction SilentlyContinue }
  }
  Note ('    gone after delete: ' + (-not (Test-Path $venv)))
  & $syspy -m venv $venv 2>&1 | ForEach-Object { Note ('    ' + $_) }
  Note ('    pyvenv.cfg: ' + (Test-Path "$venv\pyvenv.cfg"))
  # ensurepip is what take 2 was missing: a venv with no pip inside it
  if (-not (Test-Path "$venv\Scripts\pip.exe")) {
    Note '    no pip.exe -> running ensurepip'
    & $vpy -m ensurepip --upgrade 2>&1 | Select-Object -Last 4 | ForEach-Object { Note ('    ' + $_) }
  }
  & $vpy -m pip --version 2>&1 | ForEach-Object { Note ('    ' + $_) }
}

Step 'torch cu130 (~3GB)' {
  # 官方 index 实测从这台机器 0.8 秒就通（阿里云那个是裸目录列表，pip 不认）。
  # --extra-index-url 挂清华是为了让 torch 的依赖（sympy/networkx/jinja2 等）
  # 也从国内走，否则光是解析依赖就要绕一大圈。
  & $vpy -m pip install --no-cache-dir torch torchvision torchaudio `
      --index-url $torch --extra-index-url $tuna 2>&1 |
    Select-Object -Last 15 | ForEach-Object { Note ('    ' + $_) }
  & $vpy -c "import torch;print('torch',torch.__version__,'cuda_ok',torch.cuda.is_available(),'cuda',torch.version.cuda)" 2>&1 |
    ForEach-Object { Note ('    ' + $_) }
}

Step 'comfy requirements' {
  if (Test-Path "$repo\requirements.txt") {
    & $vpy -m pip install --no-cache-dir -r "$repo\requirements.txt" -i $tuna 2>&1 |
      Select-Object -Last 15 | ForEach-Object { Note ('    ' + $_) }
  } else { Note '    no requirements.txt' }
}

Step 'health check' {
  & $vpy -c "import sys,torch;print('python',sys.version.split()[0]);print('torch',torch.__version__);print('cuda_ok',torch.cuda.is_available());print('device',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')" 2>&1 |
    ForEach-Object { Note ('    ' + $_) }
  Note ('    main.py: ' + (Test-Path "$repo\main.py"))
}

Note '===== remote deploy take 3 end ====='
