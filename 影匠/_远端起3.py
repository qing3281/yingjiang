# -*- coding: utf-8 -*-
"""本机侧：用计划任务起远端 ComfyUI（修正版）。

★ 上一版把 .cmd 用 `Set-Content -Encoding ASCII` 写 —— **ASCII 编码会把「影匠AI」变成 `?`**，
   .cmd 里的路径就全废了，日志里那串 `????????????` 就是证据。
★ 这一版：**.cmd 在本机写好（用系统 ANSI = GBK 编码），scp 过去**，远端只管 schtasks 指过去。
★ 用计划任务而不是 Start-Process：ssh 断线会收走它的子进程，而计划任务由任务计划服务托管。
"""
import os
import subprocess
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
远程 = "776bjta"

CMD = (
    "@echo off\r\n"
    "cd /d \"E:\\影匠AI\\ComfyUI\"\r\n"
    "\"E:\\影匠AI\\ComfyUI\\.venv\\Scripts\\python.exe\" -X utf8 main.py "
    "--port 8188 --listen 0.0.0.0 "
    "--extra-model-paths-config \"E:\\影匠AI\\ComfyUI\\extra_model_paths.yaml\" "
    "> \"C:\\Users\\Seele\\_comfyui_r.log\" 2>&1\r\n"
)

PS1 = r'''$ErrorActionPreference = 'Continue'

# 杀掉现有
$旧 = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object { $_.CommandLine -like '*main.py*' }
Write-Output "旧 main.py 进程 $($旧.Count) 个"
foreach ($p in $旧) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3

# 确认 .cmd 内容没坏（中文路径要能看见「影匠AI」）
$cmd路 = 'C:\Users\Seele\_start_comfy.cmd'
if (Test-Path $cmd路) {
    Write-Output "--- .cmd 内容 ---"
    Get-Content $cmd路 -Encoding Default | ForEach-Object { Write-Output "  $_" }
} else {
    Write-Output "★ .cmd 不存在"
}

schtasks /Delete /TN "ComfyUI_H3" /F 2>&1 | Out-Null
schtasks /Create /TN "ComfyUI_H3" /TR "$cmd路" /SC ONCE /ST 23:59 /F /RL HIGHEST 2>&1 | Out-Null
Write-Output "建任务退出码 $LASTEXITCODE"
schtasks /Run /TN "ComfyUI_H3" 2>&1 | Out-Null
Write-Output "已触发"

$好了 = $false
for ($i = 1; $i -le 72; $i++) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 8 -UseBasicParsing
        if ($r.StatusCode -eq 200) { Write-Output "★ 起来了，等了 $($i*5) 秒"; $好了 = $true; break }
    } catch { }
}
if (-not $好了) {
    Write-Output "★ 没起来，日志尾："
    $p = 'C:\Users\Seele\_comfyui_r.log'
    if (Test-Path $p) { Get-Content $p -Tail 25 -Encoding UTF8 }
}
Write-Output "--- netstat 8188 ---"
netstat -ano | Select-String '8188'
'''


def 跑(cmd, 超时=900):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=超时)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    print("=== %s 计划任务起远端 ComfyUI（修正版）===" % time.strftime("%H:%M:%S"))

    # .cmd 用 GBK（系统 ANSI）写，中文路径才不会被 ? 掉
    cmd本地 = os.path.join(根, "_start_comfy.cmd")
    with open(cmd本地, "wb") as f:
        f.write(CMD.encode("gbk"))

    ps本地 = os.path.join(根, "_远端起3.ps1")
    with open(ps本地, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(PS1)

    跑(["scp", "-q", cmd本地, "%s:C:/Users/Seele/_start_comfy.cmd" % 远程], 超时=300)
    跑(["scp", "-q", ps本地, "%s:C:/Users/Seele/_远端起3.ps1" % 远程], 超时=300)
    print("  已上传 .cmd 和 .ps1")

    码, 出 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                 "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Seele/_远端起3.ps1"],
                超时=900)
    print(出)

    import json
    import urllib.request
    print("\n--- 从本机 HTTP 打远端 ---")
    for k in range(5):
        try:
            d = json.load(urllib.request.urlopen(
                "http://100.127.224.106:8188/system_stats", timeout=10))
            print("  ✓ 在线 %s  ← 双线通了" % d["system"]["comfyui_version"])
            return 0
        except Exception as e:
            print("  第 %d 次：%s" % (k + 1, e))
            time.sleep(4)
    return 1


if __name__ == "__main__":
    sys.exit(main())
