<#
.SYNOPSIS
    用 biliup-rs 扫码登录 B站，登录信息保存为 cookies.json。

.DESCRIPTION
    脚本会新开一个命令行窗口运行 `biliup login`，并尝试自动帮你把菜单选中「扫码登录」。
    二维码除了显示在那个窗口里，biliup 还会把它存成 qrcode.png；本脚本会自动打开这张图片，
    用手机 B站客户端扫它即可。

    本脚本不会、也不能替你输入账号密码或替你扫码。

.PARAMETER 重新登录
    已经登录过也强制重新登录（旧的 cookies.json 会先备份）。

.PARAMETER Cookie文件
    登录信息保存路径，默认 <脚本目录>\cookies.json。相对路径按脚本目录解析。

.PARAMETER 超时秒
    等待扫码完成的秒数，默认 300。二维码本身有效期约 180 秒。

.PARAMETER 手动选择
    不自动按方向键，自己在那个人工窗口里用 ↓ 选中「扫码登录」再回车。

.PARAMETER 不打开二维码
    只生成 qrcode.png，不自动弹图片查看器。

.EXAMPLE
    pwsh -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\登录B站.ps1"

.EXAMPLE
    # 换账号 / cookie 失效后重新登录
    .\登录B站.ps1 -重新登录
#>
[CmdletBinding()]
param(
    [switch]$重新登录,
    [string]$Cookie文件 = "",
    [int]$超时秒 = 300,
    [switch]$手动选择,
    [switch]$不打开二维码,
    [string]$根目录 = ""
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- 基础定位
if (-not $根目录) {
    if ($PSScriptRoot -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'biliup.exe'))) {
        $根目录 = $PSScriptRoot
    }
    elseif ($MyInvocation.MyCommand.Path) {
        $根目录 = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    elseif (Test-Path -LiteralPath 'D:\DSHworkspace\B站\biliup.exe') {
        $根目录 = 'D:\DSHworkspace\B站'
    }
    else {
        $根目录 = (Get-Location).Path
    }
}

function 写标题 {
    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Cyan
    Write-Host '  B站扫码登录助手  (biliup-rs)' -ForegroundColor Cyan
    Write-Host '============================================================' -ForegroundColor Cyan
}
function 写信息($文字) { Write-Host "  $文字" }
function 写好($文字)   { Write-Host "  [OK] $文字" -ForegroundColor Green }
function 写警告($文字) { Write-Host "  [!] $文字" -ForegroundColor Yellow }
function 写错误($文字) { Write-Host "  [X] $文字" -ForegroundColor Red }

# 前台窗口标题（用来确认按键确实会送进 biliup 的那个窗口，送错地方很危险）
function Get-前台窗口标题 {
    if (-not ([System.Management.Automation.PSTypeName]'BiliupWin.Api').Type) {
        Add-Type -Namespace BiliupWin -Name Api -MemberDefinition @'
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(System.IntPtr hWnd, System.Text.StringBuilder text, int count);
[DllImport("user32.dll")] public static extern int GetWindowTextLength(System.IntPtr hWnd);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern System.IntPtr FindWindow(string lpClassName, string lpWindowName);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr hWnd);
'@
    }
    $h = [BiliupWin.Api]::GetForegroundWindow()
    $len = [BiliupWin.Api]::GetWindowTextLength($h)
    if ($len -le 0) { return '' }
    $sb = New-Object System.Text.StringBuilder ($len + 2)
    [void][BiliupWin.Api]::GetWindowText($h, $sb, $sb.Capacity)
    return $sb.ToString()
}

# cookies.json 结构校验（字段依据 v0.2.4 源码 credential.rs 的 LoginInfo 结构体）
function Test-登录信息 {
    param([string]$路径)
    if (-not (Test-Path -LiteralPath $路径)) { return $false }
    try {
        $json = Get-Content -LiteralPath $路径 -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch { return $false }
    if (-not $json.token_info) { return $false }
    if (-not $json.token_info.access_token) { return $false }
    if (-not $json.cookie_info) { return $false }
    return $true
}

# ---------------------------------------------------------------- 主流程
写标题

$biliup = Join-Path $根目录 'biliup.exe'
if (-not (Test-Path -LiteralPath $biliup)) {
    写错误 "找不到 biliup.exe：$biliup"
    写信息 '请确认脚本和 biliup.exe 放在同一个目录，或用 -根目录 指定。'
    exit 1
}

if (-not $Cookie文件) { $Cookie文件 = Join-Path $根目录 'cookies.json' }
elseif (-not [System.IO.Path]::IsPathRooted($Cookie文件)) { $Cookie文件 = Join-Path $根目录 $Cookie文件 }
$Cookie文件 = [System.IO.Path]::GetFullPath($Cookie文件)

$版本 = (& $biliup --version 2>&1 | Out-String).Trim()
写信息 "biliup  : $biliup"
写信息 "版本    : $版本"
写信息 "登录信息: $Cookie文件"
Write-Host ''

if ((Test-Path -LiteralPath $Cookie文件) -and -not $重新登录) {
    if (Test-登录信息 -路径 $Cookie文件) {
        写好 '这个账号已经登录过了，不需要重复扫码。'
        写信息 '要换账号或强制重登，请加参数 -重新登录'
        Write-Host ''
        exit 0
    }
    else {
        写警告 '已存在的 cookies.json 结构不完整（可能上次没扫完），继续走登录流程。'
    }
}

if ($重新登录 -and (Test-Path -LiteralPath $Cookie文件)) {
    $备份 = '{0}.bak.{1}' -f $Cookie文件, (Get-Date -Format 'yyyyMMdd-HHmmss')
    Copy-Item -LiteralPath $Cookie文件 -Destination $备份 -Force
    写信息 "旧登录信息已备份到 $备份"
}

# 关键：登录开始前先把旧 cookies.json 挪走（已经备份过或本来就是坏的）。
# 否则当「这一轮登录其实没完成」时，脚本会看到这个残留文件而误报登录成功。
if (Test-Path -LiteralPath $Cookie文件) {
    Remove-Item -LiteralPath $Cookie文件 -Force -ErrorAction SilentlyContinue
}

# biliup 的二维码图片文件名是源码里写死的 "qrcode.png"，落盘位置 = 进程工作目录
$二维码图片 = Join-Path $根目录 'qrcode.png'
Remove-Item -LiteralPath $二维码图片 -Force -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '  马上会弹出一个黑色命令行窗口，里面有 6 个选项：' -ForegroundColor White
Write-Host '      账号密码 / 短信登录 / 扫码登录 / 浏览器登录 / 网页Cookie登录1 / 网页Cookie登录2' -ForegroundColor DarkGray
if ($手动选择) {
    Write-Host '  请在那个窗口里按 ↓ 一下，把光标移到「扫码登录」，再按回车。' -ForegroundColor Yellow
}
else {
    Write-Host '  脚本会尝试自动帮你选中「扫码登录」（自动按下 ↓ 和回车）。' -ForegroundColor Yellow
    Write-Host '  如果那个窗口里光标没停在「扫码登录」，请手动按 ↓ 再按回车。' -ForegroundColor Yellow
}
Write-Host '  选好后窗口里会显示二维码，同时本脚本会弹出二维码图片，手机扫码即可。' -ForegroundColor White
Write-Host '------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host ''

$开始时刻 = Get-Date
$进程 = Start-Process -FilePath $biliup `
    -ArgumentList @('-u', "`"$Cookie文件`"", 'login') `
    -WorkingDirectory $根目录 -PassThru

# 等 dialoguer 菜单画出来（实测 <2 秒时按键会被丢掉，4 秒稳）
Start-Sleep -Seconds 4

if (-not $手动选择) {
    # 前台判断要重试几次：窗口刚弹出时焦点可能还留在调用方的终端上。
    # 只有确认前台窗口标题就是那个 biliup 窗口，才敢发按键 —— 把 ↓/回车 发进别的窗口会很危险。
    $是目标窗口 = $false
    for ($第几次 = 1; $第几次 -le 6; $第几次++) {
        $前台标题 = Get-前台窗口标题
        if (($前台标题 -eq $biliup) -or ($前台标题 -like "$biliup*")) { $是目标窗口 = $true; break }

        # 前台不是它，就按精确标题（Start-Process 让标题 = exe 全路径）把它拎到前台再试
        try {
            $句柄 = [BiliupWin.Api]::FindWindow($null, $biliup)
            if ($句柄 -ne [System.IntPtr]::Zero) {
                [void][BiliupWin.Api]::SetForegroundWindow($句柄)
                Start-Sleep -Milliseconds 600
                $前台标题 = Get-前台窗口标题
                if (($前台标题 -eq $biliup) -or ($前台标题 -like "$biliup*")) { $是目标窗口 = $true; break }
            }
        }
        catch { }
        Start-Sleep -Milliseconds 500
    }

    if ($是目标窗口) {
        try {
            $wsh = New-Object -ComObject WScript.Shell
            Start-Sleep -Milliseconds 1200
            $wsh.SendKeys('{DOWN}')
            Start-Sleep -Milliseconds 1500
            $wsh.SendKeys('{ENTER}')
            写好 '已尝试自动选择「扫码登录」。'
        }
        catch {
            写警告 "自动按键失败（$($_.Exception.Message)），请手动在窗口里按 ↓ 再按回车。"
        }
    }
    else {
        写警告 '没能确认那个窗口在前台，为安全起见没有自动按键。'
        写警告 "请在标题为「$biliup」的窗口里按 ↓ 再按回车选「扫码登录」。"
    }
}

Write-Host ''
写信息 '等待扫码中……（二维码有效期约 180 秒）'

$截止 = (Get-Date).AddSeconds($超时秒)
$图片已开 = $false
while ((Get-Date) -lt $截止) {
    Start-Sleep -Milliseconds 800

    if (-not $图片已开 -and (Test-Path -LiteralPath $二维码图片)) {
        Start-Sleep -Milliseconds 700   # 等文件写完
        $图片已开 = $true
        Write-Host ''
        写好 "二维码已生成：$二维码图片"
        if (-not $不打开二维码) {
            try { Start-Process -FilePath $二维码图片 | Out-Null; 写信息 '已打开二维码图片，请用手机 B站客户端扫它。' }
            catch { 写警告 "自动打开图片失败，请手动打开：$二维码图片" }
        }
        Write-Host ''
    }

    if ($进程.HasExited) { break }
}

$进程.Refresh()

# 三重条件才算成功：biliup 正常退出 + cookies.json 确实是这一轮新写的 + 结构完整。
# （只看文件存不存在会被上一轮残留的文件骗到）
$本轮新写入 = $false
if (Test-Path -LiteralPath $Cookie文件) {
    try {
        $本轮新写入 = ((Get-Item -LiteralPath $Cookie文件).LastWriteTime -ge $开始时刻.AddSeconds(-2))
    }
    catch { $本轮新写入 = $false }
}

Write-Host ''
if ($进程.HasExited -and $进程.ExitCode -eq 0 -and $本轮新写入 -and (Test-登录信息 -路径 $Cookie文件)) {
    $mid = ''
    try { $mid = (Get-Content -LiteralPath $Cookie文件 -Raw -Encoding UTF8 | ConvertFrom-Json).token_info.mid } catch { }
    写好 '登录成功！'
    写信息 "登录信息已保存：$Cookie文件"
    if ($mid) { 写信息 "账号 mid：$mid" }
    if (Test-Path -LiteralPath $二维码图片) { Remove-Item -LiteralPath $二维码图片 -Force -ErrorAction SilentlyContinue }
    Write-Host ''
    写信息 '接下来可以投稿了，例如：'
    Write-Host '    pwsh -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\上传视频.ps1" `' -ForegroundColor DarkGray
    Write-Host '        -视频路径 "D:\成品\第1集.mp4" -标题 "示例标题" -标签 "AI动画,AI短片" -分区 47 -AI生成声明' -ForegroundColor DarkGray
    Write-Host ''
    exit 0
}

if (-not $进程.HasExited) {
    写警告 "等待超时（$超时秒 秒），登录还没完成。"
    写信息 '二维码大概率已经过期了。请手动关掉那个命令行窗口，然后重新运行本脚本。'
    Write-Host ''
    exit 2
}

写错误 "登录没有成功，biliup 退出码：$($进程.ExitCode)"
写信息 '常见原因：选了别的登录方式、二维码过期、网络不通。'
写信息 '重新运行本脚本再试一次即可。'
Write-Host ''
exit 1
