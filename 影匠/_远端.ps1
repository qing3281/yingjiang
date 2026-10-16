# 在远端跑一段 PowerShell：命令走 base64(UTF-16LE)，彻底避开引号套娃
# 用法：.\_远端.ps1 -命令 'Get-Date'        或      .\_远端.ps1 -文件 .\某脚本.ps1
param(
  [string]$命令 = '',
  [string]$文件 = '',
  [string]$主机 = '776bjta'
)
$ErrorActionPreference = 'Stop'

if ($文件) { $命令 = Get-Content -LiteralPath $文件 -Raw -Encoding UTF8 }
if (-not $命令) { throw '要给 -命令 或 -文件' }

# 外面套一层：把输出编码锁成 UTF8，免得中文回来变问号
$全套 = @"
`$ErrorActionPreference='Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
`$OutputEncoding = [Text.Encoding]::UTF8
$命令
"@

$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($全套))
ssh -o ConnectTimeout=25 -o ServerAliveInterval=15 $主机 "powershell -NoProfile -EncodedCommand $b64" 2>&1
