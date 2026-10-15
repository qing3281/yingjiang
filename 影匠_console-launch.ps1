# ══════════════════════════════════════════════════════════════════════════
#  「影匠控制台」的启动逻辑。桌面快捷方式 → 影匠控制台.cmd → 这个文件。
#
#  ★ 为什么逻辑在这而不在 .cmd 里：**cmd.exe 是按 OEM 代码页解析 .cmd 文件的**。
#    2026-10-15 08:35 实测：把带中文的 `echo` 和跨行 `^` 续行写进 .cmd，
#    双击之后满屏 `'xx' is not recognized as an internal or external command`
#    —— 中文被拆成了半条命令，**启动器自己先坏了**。
#    PowerShell 认 UTF-8 BOM，所以中文逻辑一律放这儿，.cmd 里只留 ASCII。
#
#  ★ 为什么不能无脑用已经跑着的那个：桌面那个图标以前指向 exe，
#    而 exe 里冻着一份打包当时的 _控台.py（现在这份是 03:30 的）。
#    我改了 .py，**exe 一个字都不会变** —— 你双击打开的还是旧页面。
#    所以这里要认版本：新版的判据是 `/api/comfy` 这个接口在不在。
# ══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = 'SilentlyContinue'
$根 = 'D:\DSHworkspace'
$PY = 'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe'
$址 = 'http://127.0.0.1:8791/'

function 活着 {
    try { Invoke-WebRequest $址 -UseBasicParsing -TimeoutSec 3 | Out-Null; return $true }
    catch { return $false }
}
function 是新版 {
    try {
        Invoke-WebRequest ($址 + 'api/comfy?machine=x&face=queue') -UseBasicParsing -TimeoutSec 6 | Out-Null
        return $true
    } catch { return $false }
}
function 有活在跑 {
    try {
        $s = (Invoke-WebRequest ($址 + 'api/state') -UseBasicParsing -TimeoutSec 6).Content | ConvertFrom-Json
        return [bool]$s.在跑
    } catch { return $true }   # 读不到就当成有活 —— 宁可不起，也不误杀
}

if (活着) {
    if (是新版) { Start-Process $址; exit 0 }

    Write-Host '  8791 上那个是旧版控制台。'
    if (有活在跑) {
        Write-Host '  它正在跑活 —— 这次不换它，等它跑完再双击一次。'
        Start-Process $址
        exit 0
    }
    Write-Host '  手上没有活在跑，换掉它。'
    # ★ 打包出来的 exe 是**两个进程**（外壳 3212 → 真身 19872，父子关系）。
    #   只杀正在监听的那个，外壳会把它再拉起来 —— 2026-10-15 08:40 实测：
    #   杀完 8791 上还是旧版，白折腾一趟。所以按**名字**把这一家子全清掉，
    #   再补一刀杀监听者（防的是没走 exe、直接跑 .py 起的那个）。
    Get-Process '影匠控制台' | ForEach-Object { Stop-Process -Id $_.Id -Force }
    Start-Sleep -Seconds 2
    Get-NetTCPConnection -LocalPort 8791 -State Listen |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
    Start-Sleep -Seconds 3
}

if (Test-Path $PY) {
    Write-Host '  起「影匠控制台」（跑磁盘上的 _控台.py，我改一行就生效）…'
    Start-Process -FilePath $PY -ArgumentList '-X', 'utf8', '-u', "$根\影匠\_控台.py", '--口', '8791' `
        -WorkingDirectory $根 -WindowStyle Minimized
} else {
    Write-Host '  这台机器没有 python，起打包好的 exe…'
    Start-Process "$根\影匠\影匠控制台.exe"
}

# 等它把端口听起来 —— 实测要 8~18 秒。太早开浏览器会看到「打不开」，
# 然后你会以为是我做坏了。
for ($i = 0; $i -lt 60; $i++) {
    if (活着) { break }
    Start-Sleep -Milliseconds 700
}
if (活着) { Start-Process $址 } else { Write-Host '  ✗ 60 秒还没起来，看看 _控台起不来.log' }
