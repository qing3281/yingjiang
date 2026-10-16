<#
.SYNOPSIS
    把本地视频投稿到 B站（biliup-rs 封装）。

.DESCRIPTION
    走的是 biliup 的「命令行参数投稿」路径（不是 config.yaml 那条路）。
    上传前会校验文件、把将要提交的元数据打印出来让你确认，全过程写日志到 upload.log。
    失败时保留 biliup 的原始报错，不做吞并。

.PARAMETER 视频路径
    一个或多个视频文件的本地路径。多P 就写多个（或传一个数组）。

.PARAMETER 标题
    稿件标题，B站上限 80 字。

.PARAMETER 简介
    稿件简介，B站上限 2000 字。配合 -AI生成声明 时，声明文本会自动加在最前面。

.PARAMETER 标签
    标签，可以写成 "AI动画,AI短片" 一个字符串，也可以写成数组。最多 10 个。

.PARAMETER 分区
    投稿分区 tid（整数）。默认 47 = 动画区 / 短片·手书·配音。
    常用：47 动画-短片·手书·配音 / 27 动画-综合 / 85 影视-短片 / 231 科技-计算机技术

.PARAMETER 封面
    封面图片的本地路径（jpg/png）。不填则投稿后由 B站自动截帧。

.PARAMETER 定时发布时间
    定时投稿时间。支持三种写法：
        "2026-10-20 20:00"   （本地时间）
        "1761000000"         （10 位 Unix 时间戳）
        "+6h" / "+1d"        （从现在起算）
    注意：B站要求定时时间必须比当前时间晚 4 小时以上，否则会被拒。

.PARAMETER AI生成声明
    在简介最前面插入 AI 生成声明（文本见 -AI声明文本）。
    本版 biliup-rs（0.2.4）没有 AI 声明的专用接口参数，所以走简介声明这条路。

.PARAMETER 额外参数
    JSON 字符串，原样透传给 biliup 的 --extra-fields，会平铺进投稿请求体。
    用法示例（字段名请自行核实后再用）：'{"ai_declare":1}'

.PARAMETER 跳过确认
    不打印确认提示、直接投稿（给自动化用）。

.PARAMETER 试运行
    只打印将要执行的命令和元数据，不真的投稿。

.EXAMPLE
    pwsh -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\上传视频.ps1" `
        -视频路径 "D:\成品\第1集.mp4" -标题 "AI短动画 第1集" `
        -简介 "第一集，讲一个机器人醒来。" -标签 "AI动画,AI短片,原创动画" `
        -分区 47 -封面 "D:\成品\封面1.jpg" -AI生成声明

.EXAMPLE
    # 定时到今晚 20:30 发
    .\上传视频.ps1 -视频路径 .\a.mp4 -标题 "测试" -标签 "AI动画" -定时发布时间 "2026-10-20 20:30"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string[]]$视频路径,

    [Parameter(Mandatory = $true)]
    [string]$标题,

    [string]$简介 = '',

    [string[]]$标签 = @(),

    [int]$分区 = 47,

    [string]$封面 = '',

    [string]$定时发布时间 = '',

    [switch]$AI生成声明,
    [string]$AI声明文本 = '【AI生成声明】本视频画面由人工智能（AI）生成，音频与剪辑由人工完成。',

    [ValidateSet('bda2', 'ws', 'qn', 'bldsa', 'tx', 'txa', 'bda', 'alia')]
    [string]$线路 = '',

    [int]$并发数 = 3,

    [ValidateSet('client', 'app', 'web')]
    [string]$提交接口 = 'client',

    [switch]$转载,
    [string]$转载来源 = '',
    [switch]$禁止转载,
    [switch]$开启充电,
    [switch]$关闭评论,
    [switch]$关闭弹幕,
    [switch]$精选评论,

    [string]$空间动态 = '',
    [string]$额外参数 = '',

    [string]$Cookie文件 = '',
    [string]$日志文件 = '',
    [string]$根目录 = '',
    [switch]$跳过确认,
    [switch]$试运行
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

function 写信息($文字) { Write-Host "  $文字" }
function 写好($文字) { Write-Host "  [OK] $文字" -ForegroundColor Green }
function 写警告($文字) { Write-Host "  [!] $文字" -ForegroundColor Yellow }
function 写错误($文字) { Write-Host "  [X] $文字" -ForegroundColor Red }
function 写日志($行) {
    foreach ($l in @($行)) {
        Add-Content -LiteralPath $日志文件 -Value $l -Encoding UTF8
    }
}

$biliup = Join-Path $根目录 'biliup.exe'
if (-not (Test-Path -LiteralPath $biliup)) {
    写错误 "找不到 biliup.exe：$biliup"
    exit 1
}

if (-not $Cookie文件) { $Cookie文件 = Join-Path $根目录 'cookies.json' }
elseif (-not [System.IO.Path]::IsPathRooted($Cookie文件)) { $Cookie文件 = Join-Path $根目录 $Cookie文件 }
$Cookie文件 = [System.IO.Path]::GetFullPath($Cookie文件)

if (-not $日志文件) { $日志文件 = Join-Path $根目录 'upload.log' }
elseif (-not [System.IO.Path]::IsPathRooted($日志文件)) { $日志文件 = Join-Path $根目录 $日志文件 }
$日志文件 = [System.IO.Path]::GetFullPath($日志文件)

Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host '  B站投稿  (biliup-rs)' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan

# ---------------------------------------------------------------- 校验：视频文件
$视频绝对路径 = @()
$问题 = @()
foreach ($p in $视频路径) {
    if ([string]::IsNullOrWhiteSpace($p)) { continue }
    $全路径 = if ([System.IO.Path]::IsPathRooted($p)) { $p } else { Join-Path (Get-Location).Path $p }
    try { $全路径 = [System.IO.Path]::GetFullPath($全路径) } catch { }
    if (-not (Test-Path -LiteralPath $全路径 -PathType Leaf)) {
        $问题 += "视频文件不存在：$全路径"
        continue
    }
    $项 = Get-Item -LiteralPath $全路径
    $后缀 = $项.Extension.ToLower()
    if ($后缀 -notin @('.mp4', '.flv', '.mkv', '.mov', '.avi', '.wmv', '.ts', '.m4v', '.webm')) {
        写警告 "扩展名 $后缀 看起来不像视频，仍会尝试上传：$($项.Name)"
    }
    if ($项.Length -le 0) { $问题 += "视频文件是空的（0 字节）：$全路径" }
    $视频绝对路径 += $项.FullName
}
if ($视频绝对路径.Count -eq 0) { $问题 += '没有提供任何有效的视频文件。' }
if ($问题.Count -gt 0) {
    写错误 '上传前的校验没通过：'
    foreach ($x in $问题) { 写信息 " - $x" }
    Write-Host ''
    exit 1
}

# ---------------------------------------------------------------- 校验：封面
$封面绝对路径 = ''
if ($封面) {
    $封面绝对路径 = if ([System.IO.Path]::IsPathRooted($封面)) { $封面 } else { Join-Path (Get-Location).Path $封面 }
    try { $封面绝对路径 = [System.IO.Path]::GetFullPath($封面绝对路径) } catch { }
    if (-not (Test-Path -LiteralPath $封面绝对路径 -PathType Leaf)) {
        写错误 "封面文件不存在：$封面绝对路径"
        exit 1
    }
    $封 = Get-Item -LiteralPath $封面绝对路径
    if ($封.Extension.ToLower() -notin @('.jpg', '.jpeg', '.png')) {
        写错误 "封面只支持 jpg / png，当前是 $($封.Extension)"
        exit 1
    }
    if ($封.Length -gt 5MB) { 写警告 "封面 $([math]::Round($封.Length/1MB,2)) MB，B站对封面有大小限制，可能被拒。" }
}

# ---------------------------------------------------------------- 校验：标题 / 标签 / 简介
if ([string]::IsNullOrWhiteSpace($标题)) { 写错误 '标题不能为空。'; exit 1 }
if ($标题.Length -gt 80) { 写错误 "标题 $($标题.Length) 字，超过 B站 80 字上限。"; exit 1 }

$标签列表 = @()
foreach ($t in $标签) {
    if ([string]::IsNullOrWhiteSpace($t)) { continue }
    foreach ($片 in ($t -split ',')) {
        $v = $片.Trim()
        if ($v) { $标签列表 += $v }
    }
}
$标签列表 = @($标签列表 | Select-Object -Unique)
if ($标签列表.Count -gt 10) {
    写错误 "标签有 $($标签列表.Count) 个，超过 B站 10 个上限：$($标签列表 -join ', ')"
    exit 1
}
if ($标签列表.Count -eq 0) { 写警告 '没有标签。B站允许，但没标签的稿件很难被推荐。' }

$正文简介 = $简介
if ($AI生成声明) {
    if ($正文简介) { $正文简介 = "$AI声明文本`n$正文简介" } else { $正文简介 = $AI声明文本 }
}
if ($正文简介.Length -gt 2000) { 写警告 "简介 $($正文简介.Length) 字，超过 B站 2000 字上限，可能被截断或被拒。" }
if ($空间动态.Length -gt 233) { 写警告 "空间动态 $($空间动态.Length) 字，超过 B站 233 字上限。" }

# ---------------------------------------------------------------- 校验：定时发布时间
$dtime = ''
if ($定时发布时间) {
    $原值 = $定时发布时间.Trim()
    $目标时刻 = $null

    if ($原值 -match '^\d{10}$') {
        $目标时刻 = [datetime]'1970-01-01T00:00:00Z' + [timespan]::FromSeconds([int64]$原值)
        $目标时刻 = $目标时刻.ToLocalTime()
    }
    elseif ($原值 -match '^\+\s*(\d+)\s*([hmd])$') {
        $n = [int]$Matches[1]
        $单位 = $Matches[2]
        $分钟 = switch ($单位) { 'h' { $n * 60 } 'd' { $n * 1440 } default { $n } }
        $目标时刻 = (Get-Date).AddMinutes($分钟)
    }
    else {
        $格式列表 = @('yyyy-MM-dd HH:mm', 'yyyy-MM-dd HH:mm:ss', 'yyyy/MM/dd HH:mm', 'yyyy/MM/dd HH:mm:ss')
        foreach ($f in $格式列表) {
            try {
                $目标时刻 = [datetime]::ParseExact($原值, $f, [System.Globalization.CultureInfo]::InvariantCulture)
                break
            }
            catch { }
        }
        if (-not $目标时刻) {
            写错误 "看不懂的定时发布时间：'$原值'"
            写信息 '支持："2026-10-20 20:00" / "1761000000"（10位时间戳） / "+6h"'
            exit 1
        }
    }

    $时间戳 = [int64][math]::Floor((($目标时刻.ToUniversalTime()) - [datetime]'1970-01-01T00:00:00Z').TotalSeconds)
    $距今小时 = [math]::Round((($目标时刻 - (Get-Date)).TotalHours), 2)
    if ($时间戳 -lt ((Get-Date).ToUniversalTime() - [datetime]'1970-01-01T00:00:00Z').TotalSeconds + 14400) {
        写错误 "定时发布时间 $($目标时刻.ToString('yyyy-MM-dd HH:mm')) 距现在只有 $距今小时 小时。"
        写信息 'B站要求定时投稿必须晚于当前时间 4 小时以上。想立刻发就不要加 -定时发布时间。'
        exit 1
    }
    $dtime = "$时间戳"
    写信息 "定时发布：$($目标时刻.ToString('yyyy-MM-dd HH:mm:ss'))（时间戳 $dtime，距现在 $距今小时 小时）"
}

# ---------------------------------------------------------------- 组装命令
# 注意：-u 是全局参数，必须放在 upload 子命令【之前】，放后面 clap 会报错。
$实参 = @('-u', $Cookie文件, 'upload')
if ($线路) { $实参 += @('-l', $线路) }
$实参 += @('--limit', "$并发数")
$实参 += @('--submit', $提交接口)
$实参 += @('--copyright', $(if ($转载) { '2' } else { '1' }))
if ($转载来源) { $实参 += @('--source', $转载来源) }
$实参 += @('--tid', "$分区")
if ($封面绝对路径) { $实参 += @('--cover', $封面绝对路径) }
$实参 += @('--title', $标题)
if ($正文简介) { $实参 += @('--desc', $正文简介) }
if ($空间动态) { $实参 += @('--dynamic', $空间动态) }
if ($标签列表.Count -gt 0) { $实参 += @('--tag', ($标签列表 -join ',')) }
if ($dtime) { $实参 += @('--dtime', $dtime) }
if ($禁止转载) { $实参 += @('--no-reprint', '1') }
if ($开启充电) { $实参 += @('--open-elec', '1') }
if ($关闭评论) { $实参 += @('--up-close-reply') }
if ($关闭弹幕) { $实参 += @('--up-close-danmu') }
if ($精选评论) { $实参 += @('--up-selection-reply') }
if ($额外参数) {
    try { $null = $额外参数 | ConvertFrom-Json } catch {
        写错误 "--额外参数 不是合法 JSON：$($_.Exception.Message)"
        exit 1
    }
    $实参 += @('--extra-fields', $额外参数)
}
$实参 += $视频绝对路径

# ---------------------------------------------------------------- 打印元数据
$分区名 = switch ($分区) {
    47 { '动画 / 短片·手书·配音' }
    27 { '动画 / 综合' }
    24 { '动画 / MAD·AMV' }
    25 { '动画 / MMD·3D' }
    85 { '影视 / 短片' }
    231 { '科技 / 计算机技术' }
    230 { '科技 / 软件应用' }
    95 { '科技 / 数码' }
    171 { '游戏 / 电子竞技' }
    default { '(未在内置表里)' }
}

Write-Host ''
Write-Host '  ---------------- 即将提交的投稿信息 ----------------' -ForegroundColor White
写信息 "视频文件 : $($视频绝对路径.Count) 个"
foreach ($v in $视频绝对路径) {
    $s = Get-Item -LiteralPath $v
    写信息 "           $($s.FullName)  ($([math]::Round($s.Length/1MB,2)) MB)"
}
写信息 "标题     : $标题  ($($标题.Length)/80 字)"
写信息 "分区     : $分区  $分区名"
写信息 "标签     : $(if ($标签列表.Count) { $标签列表 -join ', ' } else { '(无)' })  ($($标签列表.Count)/10 个)"
写信息 "封面     : $(if ($封面绝对路径) { $封面绝对路径 } else { '(不传，由 B站自动截帧)' })"
写信息 "定时发布 : $(if ($dtime) { "$定时发布时间 -> $dtime" } else { '(立即投稿)' })"
写信息 "自制/转载: $(if ($转载) { "转载 来源='$转载来源'" } else { '自制(原创)' })"
写信息 "并发/线路: $并发数  $(if ($线路) { $线路 } else { '(自动测速)' })"
if ($AI生成声明) { 写信息 "AI 声明  : 已写入简介开头 -> $AI声明文本" }
if ($额外参数) { 写信息 "extra    : $额外参数" }
写信息 "Cookie   : $Cookie文件"
写信息 "日志     : $日志文件"
Write-Host ''
Write-Host '  简介全文：' -ForegroundColor White
foreach ($行 in ($正文简介 -split "`r?`n")) { Write-Host "    | $行" -ForegroundColor DarkGray }
Write-Host ''
Write-Host '  实际命令：' -ForegroundColor White
Write-Host "    `"$biliup`" $($实参 -join ' ')" -ForegroundColor DarkGray
Write-Host ''

# ---------------------------------------------------------------- 登录信息检查
function Test-登录信息 {
    param([string]$路径)
    if (-not (Test-Path -LiteralPath $路径)) { return $false }
    try { $json = Get-Content -LiteralPath $路径 -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $false }
    if (-not $json.token_info) { return $false }
    if (-not $json.token_info.access_token) { return $false }
    if (-not $json.cookie_info) { return $false }
    return $true
}

if ((-not (Test-登录信息 -路径 $Cookie文件)) -and (-not $试运行)) {
    写错误 "没有可用的登录信息：$Cookie文件"
    写信息 '请先扫码登录：'
    Write-Host '    pwsh -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\登录B站.ps1"' -ForegroundColor DarkGray
    Write-Host ''
    exit 1
}

if ($试运行) {
    写好 '试运行模式：以上信息没问题，但不会真的投稿。'
    Write-Host ''
    exit 0
}

if (-not $跳过确认) {
    $答复 = Read-Host '  确认投稿？(y/N)'
    if ($答复 -notmatch '^(y|Y|yes|YES)$') {
        写信息 '已取消，什么都没提交。'
        Write-Host ''
        exit 0
    }
}

# ---------------------------------------------------------------- 执行投稿
$开始时刻 = Get-Date
Write-Host ''
写信息 '开始上传……（大文件会比较久，进度会实时打印）'
Write-Host ''

$全部输出 = New-Object System.Collections.Generic.List[string]
$先前策略 = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
Push-Location $根目录
try {
    & $biliup @实参 2>&1 | ForEach-Object {
        $文本 = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ }
        foreach ($子行 in ($文本 -split "`r?`n")) {
            if ($子行.Trim().Length -gt 0) {
                $全部输出.Add($子行)
                Write-Host "  $子行"
            }
        }
    }
    $退出码 = $LASTEXITCODE
}
finally {
    Pop-Location
    $ErrorActionPreference = $先前策略
}
if ($null -eq $退出码) { $退出码 = 0 }
$耗时 = [math]::Round(((Get-Date) - $开始时刻).TotalSeconds, 1)

# ---------------------------------------------------------------- 写日志
$输出文本 = ($全部输出 -join "`n")
$bvid = ''
$m = [regex]::Match($输出文本, 'BV[0-9A-Za-z]{10}')
if ($m.Success) { $bvid = $m.Value }

$日志块 = @()
$日志块 += '================================================================'
$日志块 += "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 投稿$(if ($退出码 -eq 0) { '成功' } else { "失败(退出码 $退出码)" })  耗时 ${耗时}s"
$日志块 += "标题    : $标题"
$日志块 += "分区    : $分区 ($分区名)"
$日志块 += "标签    : $($标签列表 -join ',')"
$日志块 += "封面    : $(if ($封面绝对路径) { $封面绝对路径 } else { '(无)' })"
$日志块 += "定时    : $(if ($dtime) { $dtime } else { '(立即)' })"
$日志块 += "AI声明  : $(if ($AI生成声明) { '是' } else { '否' })"
$日志块 += "视频    : $($视频绝对路径 -join ' | ')"
$日志块 += "命令    : `"$biliup`" $($实参 -join ' ')"
if ($bvid) { $日志块 += "BVID    : $bvid" }
$日志块 += '---- biliup 原始输出 ----'
foreach ($l in $全部输出) { $日志块 += $l }
$日志块 += ''

try { 写日志 $日志块 } catch { 写警告 "写日志失败：$($_.Exception.Message)" }

# ---------------------------------------------------------------- 结果
Write-Host ''
if ($退出码 -eq 0) {
    Write-Host '============================================================' -ForegroundColor Green
    写好 '投稿成功！'
    if ($bvid) { 写信息 "BVID：$bvid    https://www.bilibili.com/video/$bvid" }
    写信息 "耗时 ${耗时}s，日志：$日志文件"
    Write-Host '============================================================' -ForegroundColor Green
    Write-Host ''
    exit 0
}

Write-Host '============================================================' -ForegroundColor Red
    写错误 "投稿失败，biliup 退出码：$退出码"
    Write-Host '============================================================' -ForegroundColor Red
Write-Host ''
写信息 'biliup 的原始输出（完整内容也已写入日志，没有被吞掉）：'
Write-Host ''
foreach ($l in $全部输出) { Write-Host "  $l" -ForegroundColor Yellow }
Write-Host ''
写信息 "完整日志：$日志文件"
写信息 '常见排查：登录过期就重跑 登录B站.ps1 -重新登录；网络问题可加 -线路 换线路；'
写信息 '分区/权限问题看上面原始报错里的 message 字段。'
Write-Host ''
exit $退出码
