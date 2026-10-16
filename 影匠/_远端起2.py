# -*- coding: utf-8 -*-
"""本机侧：用 **计划任务** 起远端 ComfyUI。

★ 为什么换招：`Start-Process` 起出来的进程是 ssh 会话的子进程，**ssh 一断就被收走**
   —— 日志正好断在节点加载完之后、`Starting server` 之前，而且没有任何报错。
   计划任务（schtasks）由 Windows 任务计划服务托管，**不属于任何 ssh 作业对象**，不会被收走。
"""
import os
import subprocess
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
远程 = "776bjta"

# 远端要跑的一段 .ps1（写成文件传过去，避免 ssh 引号地狱）
PS1 = r'''$ErrorActionPreference = 'Continue'
$基础 = 'E:\影匠AI\ComfyUI'
$py = Join-Path $基础 '.venv\Scripts\python.exe'
$日志 = 'C:\Users\Seele\_comfyui_r.log'

Write-Output "基础目录: $(Test-Path $基础)"
Write-Output "python: $(Test-Path $py)"

# 杀掉现有
$旧 = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object { $_.CommandLine -like '*ComfyUI*main.py*' }
Write-Output "旧进程 $($旧.Count) 个"
foreach ($p in $旧) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3

# 先删旧的计划任务
schtasks /Delete /TN "ComfyUI_H3" /F 2>$null | Out-Null

# 写一个启动用的 .cmd（计划任务里跑 bat 最省事，重定向也简单）
$cmd = @"
@echo off
cd /d "$基础"
"$py" -X utf8 main.py --port 8188 --listen 0.0.0.0 --extra-model-paths-config "$基础\extra_model_paths.yaml" > "$日志" 2>&1
"@
$cmd路 = 'C:\Users\Seele\_start_comfy.cmd'
Set-Content -Path $cmd路 -Value $cmd -Encoding ASCII
Write-Output "写好 $cmd路"

# 建计划任务并立刻跑
schtasks /Create /TN "ComfyUI_H3" /TR "$cmd路" /SC ONCE /ST 23:59 /F /RL HIGHEST | Out-Null
Write-Output "建任务 $LASTEXITCODE"
schtasks /Run /TN "ComfyUI_H3" | Out-Null
Write-Output "已触发"

# 等
$好了 = $false
for ($i = 1; $i -le 72; $i++) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 8 -UseBasicParsing
        if ($r.StatusCode -eq 200) { Write-Output "★ 起来了，等了 $($i*5) 秒"; $好了 = $true; break }
    } catch { }
}
if (-not $好了) {
    Write-Output "★ 没起来"
    $p = 'C:\Users\Seele\_comfyui_r.log'
    if (Test-Path $p) { Get-Content $p -Tail 30 -Encoding UTF8 }
}

# 报告监听
Write-Output "--- netstat 8188 ---"
netstat -ano | Select-String '8188'
'''


def 跑(cmd, 超时=900):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=超时)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    print("=== %s 计划任务起远端 ComfyUI ===" % time.strftime("%H:%M:%S"))

    临 = os.path.join(根, "_远端起2.ps1")
    with open(临, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(PS1)

    跑(["scp", "-q", 临, "%s:C:/Users/Seele/_远端起2.ps1" % 远程], 超时=300)
    码, 出 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                 "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/Seele/_远端起2.ps1"],
                超时=900)
    print(出)

    # 从本机再打一次
    print("\n--- 从本机 HTTP 打远端 ---")
    import json
    import urllib.request
    for k in range(6):
        try:
            d = json.load(urllib.request.urlopen(
                "http://100.127.224.106:8188/system_stats", timeout=10))
            print("  ✓ 在线 %s" % d["system"]["comfyui_version"])
            return 0
        except Exception as e:
            print("  第 %d 次：%s" % (k + 1, e))
            time.sleep(5)
    return 1


if __name__ == "__main__":
    sys.exit(main())
