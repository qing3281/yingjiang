# 每日跑一次 B 站选题情报抓取
# 用法： pwsh -File "D:\DSHworkspace\B站\run_daily.ps1"
# 可选： pwsh -File "D:\DSHworkspace\B站\run_daily.ps1" -AnalyzeOnly   # 不抓取，只用已有数据重生成报告

param(
    [switch]$AnalyzeOnly,
    [switch]$Fast,                                   # 快速模式：少抓几页，约 3 分钟
    [string]$Date = (Get-Date -Format 'yyyyMMdd')
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'

$BASE = 'D:\DSHworkspace\B站'
$PY   = Join-Path $BASE 'venv\Scripts\python.exe'
$LOG  = Join-Path $BASE '情报\运行日志.txt'

if (-not (Test-Path $PY)) { throw "找不到 venv python：$PY" }

$argv = @((Join-Path $BASE '抓热榜.py'), '--date', $Date)
if ($AnalyzeOnly) { $argv += '--analyze-only' }
if ($Fast)        { $argv += @('--pages','1','--recent-pages','1','--enrich-top','8','--enrich-recent','5','--enrich-users','25') }

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Add-Content -Path $LOG -Value "[$stamp] 开始 date=$Date analyzeOnly=$($AnalyzeOnly.IsPresent) fast=$($Fast.IsPresent)" -Encoding utf8

& $PY @argv 2>&1 | Tee-Object -FilePath (Join-Path $BASE '情报\_last_run.log')
$code = $LASTEXITCODE

Add-Content -Path $LOG -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 退出码=$code" -Encoding utf8

if ($code -ne 0) { Write-Warning "抓取脚本退出码 $code，详见 情报\_last_run.log" }

$out = Join-Path $BASE "情报\题材分析_$Date.md"
if (Test-Path $out) {
    Write-Host ""
    Write-Host "报告已生成： $out" -ForegroundColor Green
    Write-Host "明细 CSV  ： $(Join-Path $BASE "情报\热榜日报_$Date.csv")" -ForegroundColor Green
} else {
    Write-Warning "没有找到报告文件 $out"
}
exit $code
