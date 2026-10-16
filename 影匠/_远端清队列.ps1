# 远端 ComfyUI：打断当前 prompt + 清空队列，然后报告状态。纯 ASCII，避免代码页坑。
$ErrorActionPreference = 'Continue'
function J($u, $m) {
    try {
        if ($m -eq 'Post') { return Invoke-RestMethod -Method Post $u -TimeoutSec 10 }
        return Invoke-RestMethod $u -TimeoutSec 10
    } catch { return $null }
}
Write-Output "--- before ---"
$q = J 'http://127.0.0.1:8188/queue' 'Get'
if ($q) { Write-Output ("running=" + $q.queue_running.Count + " pending=" + $q.queue_pending.Count) }

J 'http://127.0.0.1:8188/interrupt' 'Post' | Out-Null
Start-Sleep -Seconds 2
J 'http://127.0.0.1:8188/queue' 'Post' | Out-Null   # 空 body = 清队列
Start-Sleep -Seconds 2

Write-Output "--- after ---"
$q2 = J 'http://127.0.0.1:8188/queue' 'Get'
if ($q2) { Write-Output ("running=" + $q2.queue_running.Count + " pending=" + $q2.queue_pending.Count) }
