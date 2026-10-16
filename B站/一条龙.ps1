# 一条龙 —— 情报 → 选题 → 出片 → 审片 →（你点头后）投稿
#
#   .\一条龙.ps1 -脚本 D:\...\它记得.json         # 出片 + 生成审核页，然后停下等你表态
#   .\一条龙.ps1 -脚本 D:\...\它记得.json -投稿    # 只有已签字放行才真的投
#   .\一条龙.ps1 -只情报                          # 只更新热榜日报和片单
#   .\一条龙.ps1 -只选题                          # 只重算本周片单
#   .\一条龙.ps1 -脚本 x.json -跳过有声           # 先看画面节奏（有声镜头要 21 分钟一支）
#   .\一条龙.ps1 -脚本 x.json -出图线 qwen        # 换成写实 CG 那条出图线
#
# 设计原则（用户明确要求）：东西做完先落盘、给人看过、人点头才谈上传。
# 所以投稿那段有两道锁：① 落盘的 _审批.json 必须是「通过」 ② 还得显式 -投稿。
# 缺任何一道都停在第 3 段，只把审核页推到你面前。

[CmdletBinding()]
param(
    [string]$脚本,
    [string]$线 = '14b',
    [ValidateSet('zimage','qwen')][string]$出图线 = 'zimage',
    [switch]$投稿,
    [string]$定时发布时间,
    [switch]$只情报,
    [switch]$只选题,
    [switch]$跳过动态,
    [switch]$跳过有声,        # MiniMax 一支 21 分钟，太慢时先让有声镜头退化成静帧
    [switch]$只合成          # 图已定稿，不重新出图（换动态线重跑时用这个）
)

$ErrorActionPreference = 'Stop'
$B站 = $PSScriptRoot
$制作 = Join-Path $B站 '制作'
$PY = 'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe'

function 段($t) { Write-Host "`n$('=' * 64)`n  $t`n$('=' * 64)" -ForegroundColor Cyan }

if (-not (Test-Path $PY)) { throw "找不到 Python：$PY" }

# ---------- 1. 情报 ----------
if (-not $只选题) {
    段 '1/5  抓热榜情报'
    $日 = & (Join-Path $B站 'run_daily.ps1')
}

# ---------- 2. 选题 ----------
if ($只情报) { 段 '完成：情报已更新'; exit 0 }

段 '2/5  重算本周片单'
& $PY (Join-Path $B站 '选题决策.py') 2>&1 | ForEach-Object { "  $_" }

if ($只选题) { 段 '完成：片单已更新'; exit 0 }

# ---------- 3. 出片 ----------
if (-not $脚本) {
    Write-Host "`n没给 -脚本，流水线到此为止。" -ForegroundColor Yellow
    Write-Host "看片单挑一个题材，写好脚本.json 后再跑："
    Write-Host "  .\一条龙.ps1 -脚本 <你的脚本.json>        # 出片，然后生成审核页停下"
    Write-Host "  .\一条龙.ps1 -脚本 <你的脚本.json> -投稿   # 你签字放行之后，才真的发"
    exit 0
}
if (-not (Test-Path $脚本)) { throw "找不到脚本文件：$脚本" }

段 "3/5  出片（出图线 $出图线，动态线 $线）"
$出片参数 = @((Join-Path $制作 '出片.py'), $脚本, '--线', $线, '--出图线', $出图线)
if ($跳过动态) { $出片参数 += '--跳过动态' }
if ($跳过有声) { $出片参数 += '--跳过有声' }
if ($只合成)   { $出片参数 += '--只合成' }
& $PY @出片参数 2>&1 | ForEach-Object { "  $_" }
if ($LASTEXITCODE -ne 0) { throw "出片失败，退出码 $LASTEXITCODE" }

# ---------- 4. 审片（默认停在这里） ----------
$脚本名 = [IO.Path]::GetFileNameWithoutExtension($脚本)
$成片目录 = Join-Path $B站 "成片\$脚本名"
$信息 = Join-Path $成片目录 '投稿信息.json'
$审批 = Join-Path $成片目录 '_审批.json'
$审片 = Join-Path $制作 '审片.py'

if (-not (Test-Path $信息)) { throw "出片没生成投稿信息：$信息" }

# 每次出片后都重新生成审核页（内容会随成片变），并把它打开
段 '4/5  生成审核页'
& $PY $审片 $成片目录 2>&1 | ForEach-Object { "  $_" }

if (-not $投稿) {
    段 '停下等你表态'
    Write-Host "  成片     $成片目录" -ForegroundColor Green
    Write-Host "  审核页   $成片目录\审核.html"
    Write-Host ""
    Write-Host "  看完《$脚本名》后，二选一：" -ForegroundColor Yellow
    Write-Host "    放行  & `"$PY`" `"$审片`" `"$成片目录`" --通过 -备注 `"可以投`""
    Write-Host "    打回  & `"$PY`" `"$审片`" `"$成片目录`" --打回 -备注 `"<哪里不对>`""
    Write-Host ""
    Write-Host "  放行之后再跑一次加 -投稿 才会真的发出去。"
    exit 0
}

# ---------- 5. 投稿（需要已签字 + 显式 -投稿） ----------
段 '5/5  投稿'
& $PY (Join-Path $制作 '投稿.py') $信息
$码 = $LASTEXITCODE
if ($码 -eq 2) {
    Write-Host "`n  没签字，没投。" -ForegroundColor Yellow
    exit 0
}
if ($码 -ne 0) { throw "投稿失败，退出码 $码" }

段 '完成'
Write-Host "  成片     $成片目录"
Write-Host "  投稿信息 $信息"
if (Test-Path $审批) {
    $审 = Get-Content $审批 -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "  审批     $($审.状态)  $($审.时间)  $($审.备注)"
}
