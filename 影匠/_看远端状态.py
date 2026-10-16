# -*- coding: utf-8 -*-
"""看远端状态：下载日志、模型目录、ComfyUI 队列。全部走 ssh 一条命令，不做嵌套引号。

教训（2026-10-14）：PowerShell 里 `ssh 主机 "powershell -Command \"...\""` 必炸 ——
外层 PowerShell 先解析内层引号。**正解是写成 .py 文件，让本机 Python subprocess 拼 ssh。**
远端 PowerShell 那一段也尽量短，复杂逻辑一律写成 .ps1 scp 过去。
"""
import subprocess
import sys

主机 = "776bjta"
超时 = 120


def 跑(远端命令: str, 标题: str) -> str:
    print(f"\n{'─' * 62}\n  {标题}\n{'─' * 62}")
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30", 主机, 远端命令],
            capture_output=True, timeout=超时,
        )
    except subprocess.TimeoutExpired:
        print("  ✗ ssh 超时")
        return ""
    out = r.stdout.decode("utf-8", "replace") if r.stdout else ""
    err = r.stderr.decode("utf-8", "replace") if r.stderr else ""
    if out.strip():
        for 行 in out.rstrip().splitlines():
            print("  " + 行)
    if err.strip() and r.returncode != 0:
        print("  [stderr] " + err.strip()[-500:])
    return out


def main():
    # 1) 下载日志尾巴
    跑('powershell -NoProfile -Command "Get-Content C:/Users/Seele/_dl_h3_b.log -Tail 6 -EA SilentlyContinue"',
       "远端下载日志 _dl_h3_b.log")

    # 2) 四个 H3 文件 + LoRA 在不在（用 python 列，避开 PowerShell 的 @{} 引号地狱）
    跑('python -X utf8 -c "'
       'import os;'
       'ds=[(r\'E:\\影匠AI\\ComfyUI-Shared\\models\\diffusion_models\',\'diffusion_models\'),'
       '(r\'E:\\影匠AI\\ComfyUI-Shared\\models\\loras\',\'loras\'),'
       '(r\'E:\\影匠AI\\ComfyUI-Shared\\models\\text_encoders\',\'text_encoders\'),'
       '(r\'E:\\影匠AI\\ComfyUI-Shared\\models\\vae\',\'vae\')];'
       '[print(\'  %-18s %-58s %7.2f GB\'%(t,n,os.path.getsize(os.path.join(d,n))/2**30))'
       ' for d,t in ds if os.path.isdir(d)'
       ' for n in sorted(os.listdir(d)) if \'h3\' in n.lower() or \'qwen3vl\' in n.lower()]"',
       "远端 H3 相关权重")

    # 3) ComfyUI 队列
    跑('python -X utf8 -c "'
       'import json,urllib.request as u;'
       'q=json.load(u.urlopen(\'http://127.0.0.1:8188/queue\',timeout=10));'
       'print(\'  正在跑 %d 个　排队 %d 个\'%(len(q[\'queue_running\']),len(q[\'queue_pending\'])))"',
       "远端 ComfyUI 队列")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
