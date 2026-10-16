# ─────────────────────────────────────────────────────────────────────
# 影匠 · 远程机 ComfyUI 部署（托管版：日志落盘，本地轮询）
# ─────────────────────────────────────────────────────────────────────
# 上一版的毛病：走 SSH 直接跑，输出全被 ssh 管道吞着，卡在哪看不见；
# 而且 Invoke-WebRequest 下 zip 又慢又不给进度。这一版：
#   1) 全过程写进 D:\部署.log，本地随时 tail
#   2) 下 zip 用 curl.exe（带断点续传），不用 Invoke-WebRequest
#   3) 每一步都写「开始/结束 + 耗时」，卡住能一眼看出卡在哪步
# ─────────────────────────────────────────────────────────────────────
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$LOG = 'D:\部署.log'
function 记($m) {
  $行 = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  $行 | Out-File -FilePath $LOG -Append -Encoding UTF8
}
function 步($名, [scriptblock]$块) {
  记 ">>> 开始：$名"
  $t = Get-Date
  try { & $块 } catch { 记 "    !! 异常：$($_.Exception.Message)" }
  记 "<<< 结束：$名  用时 $([math]::Round(((Get-Date)-$t).TotalSeconds,1)) 秒"
}

$curl = 'C:\WINDOWS\system32\curl.exe'
$根   = 'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI'
$仓   = "$根\ComfyUI"
$py   = 'C:\Users\Seele\AppData\Local\Programs\Python\Python312\python.exe'
$清华 = 'https://pypi.tuna.tsinghua.edu.cn/simple'

"" | Out-File -FilePath $LOG -Encoding UTF8
记 "===== 远程部署开始 ====="
记 "curl：$((& $curl --version | Select-Object -First 1))"
记 "python：$py  $(if (Test-Path $py) {'在'} else {'不在!'})"

# ── 1) 杀掉上次留下的孤儿 powershell（除了自己）──
步 '清孤儿进程' {
  $我 = $PID
  Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.ProcessId -ne $我 -and $_.CommandLine -like '*EncodedCommand*' } |
    ForEach-Object {
      记 "    杀 PID $($_.ProcessId)"
      Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# ── 2) ComfyUI 源码 ──
步 'ComfyUI 源码' {
  $有源码 = (Test-Path "$仓\main.py")
  记 "    已有 main.py：$有源码"
  if (-not $有源码) {
    $zip = 'D:\_comfyui.zip'
    $候选 = @(
      'https://ghfast.top/https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip',
      'https://gh-proxy.com/https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip',
      'https://github.moeyy.xyz/https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip',
      'https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip'
    )
    foreach ($u in $候选) {
      $名 = ([uri]$u).Host
      记 "    试 $名 …"
      & $curl -L --fail --no-progress-meter --retry 4 --retry-delay 3 --retry-all-errors `
              --connect-timeout 20 --max-time 600 -C - -o $zip $u 2>&1 | Out-Null
      $mb = if (Test-Path $zip) { (Get-Item $zip).Length / 1MB } else { 0 }
      记 ("    -> {0:N1} MB（退出码 {1}）" -f $mb, $LASTEXITCODE)
      if ($mb -gt 5) { break }
    }
    if (-not (Test-Path $zip) -or (Get-Item $zip).Length -lt 5MB) { throw "四个镜像都下不到 zip" }

    记 "    解压 …"
    $tmp = 'D:\_comfyui_x'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $内 = Get-ChildItem $tmp -Directory | Select-Object -First 1
    if (-not $内) { throw "解压出来没有目录" }
    if (Test-Path $仓) { Remove-Item $仓 -Recurse -Force }
    Move-Item $内.FullName $仓
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
  }
  if (-not (Test-Path "$仓\main.py")) { throw "还是没有 main.py" }
  记 "    ComfyUI $((Get-ChildItem $仓 -Recurse -File).Count) 个文件"
}

# ── 3) venv ──
步 'venv' {
  $venv = "$仓\.venv"
  $vpy = "$venv\Scripts\python.exe"
  if (-not (Test-Path $vpy)) {
    记 "    建 venv …"
    & $py -m venv $venv 2>&1 | Out-Null
  }
  if (-not (Test-Path $vpy)) { throw "venv 建不起来" }
  记 "    $(& $vpy --version 2>&1)"
  & $vpy -m pip install --upgrade pip -q -i $清华 2>&1 | Out-Null
  记 "    pip 升级完"
}

# ── 4) torch（5080 是 sm_120，必须 cu128 以上）──
步 'torch cu130（约 3 GB，最慢的一步）' {
  $vpy = "$仓\.venv\Scripts\python.exe"
  $已 = & $vpy -c "import torch;print(torch.__version__)" 2>&1
  if ($LASTEXITCODE -eq 0 -and $已 -notmatch 'Error|Traceback') {
    记 "    已装：$已"
  } else {
    & $vpy -m pip install torch torchvision torchaudio `
        --index-url https://download.pytorch.org/whl/cu130 --no-cache-dir 2>&1 |
      Select-String -Pattern 'Downloading|Successfully installed|ERROR' |
      ForEach-Object { 记 "      $_" }
  }
  $vpy2 = "$仓\.venv\Scripts\python.exe"
  记 "    验证：$(& $vpy2 -c "import torch;print('torch',torch.__version__,'cuda',torch.version.cuda,'可用',torch.cuda.is_available(),'卡',(torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-'))" 2>&1)"
}

# ── 5) ComfyUI 依赖 ──
步 'ComfyUI requirements' {
  $vpy = "$仓\.venv\Scripts\python.exe"
  & $vpy -m pip install -r "$仓\requirements.txt" -q -i $清华 2>&1 |
    Select-String -Pattern 'ERROR|error:' | Select-Object -First 10 |
    ForEach-Object { 记 "      $_" }
  记 "    requirements 装完"
}

# ── 6) 体检：能不能起来 ──
步 '体检' {
  $vpy = "$仓\.venv\Scripts\python.exe"
  记 "    python $(& $vpy --version 2>&1)"
  记 "    关键包："
  & $vpy -c @"
mods = ['torch','torchvision','torchaudio','numpy','PIL','aiohttp','yarl','sqlalchemy','einops','transformers','safetensors','comfyui_frontend_package','comfyui_workflow_templates']
for m in mods:
    try:
        __import__(m); print('      OK  ' + m)
    except Exception as e:
        print('      --  ' + m + '  (' + type(e).__name__ + ')')
"@ 2>&1 | ForEach-Object { 记 $_ }
}

记 "===== 远程部署结束 ====="
