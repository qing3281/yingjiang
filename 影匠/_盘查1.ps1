$ErrorActionPreference = 'Continue'
$根 = 'D:\DSHworkspace\影匠'
Set-Location $根

Write-Output '=== 剧组\ ==='
Get-ChildItem '剧组' -File -ErrorAction SilentlyContinue | ForEach-Object {
    '  {0,-24} {1,9:N0} B' -f $_.Name, $_.Length
}

Write-Output ''
Write-Output '=== 顶层脚本 ==='
Get-ChildItem -File -Filter *.py | Sort-Object Name | ForEach-Object {
    '  {0,-26} {1,9:N0} B' -f $_.Name, $_.Length
}

Write-Output ''
Write-Output '=== 知识\ 里跟剧本/爆款/选题有关的 ==='
Get-ChildItem '知识' -File | Where-Object { $_.Name -match '剧|故事|爆|热点|选题|脚本|文案' } | ForEach-Object {
    '  {0,-28} {1,9:N0} B' -f $_.Name, $_.Length
}

Write-Output ''
Write-Output '=== 哪些 .py 会联网（requests/urlopen/httpx）==='
Get-ChildItem -Recurse -File -Include *.py -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\音色\\|\\_work\\|\\_归档\\' } |
    Select-String -Pattern 'requests\.(get|post)|urlopen|httpx\.' -List -ErrorAction SilentlyContinue |
    Select-Object -First 15 | ForEach-Object {
        '  ' + $_.Path.Replace($根 + '\', '')
    }
