# -*- coding: utf-8 -*-
"""_补经验32.py —— 把「大扫除 + 写交接」这一轮的教训追加进经验库（只追加，不覆盖）。

为什么写成脚本而不是命令行：经验条目里有中文、引号、反引号，
塞进 pwsh 字符串会被剥掉（AGENTS.md 第 0.05 条，犯过 6 次以上）。
"""
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\记忆\经验\流程与脚本.md"
条 = [
    "- 2026-10-16 大扫除必须先立两份白名单（`_活工具.txt` 活工具 + `_保命清单.txt` 磁盘上真存在的脚本），"
    "**白名单外的文件一个都不许删只许挪**；白名单本身用「被谁 import / 被谁调」反推，不许手写。"
    " → 判据：跑完 `python _大扫除.py`（干跑）后，逐条核白名单里的文件**没有一个**出现在清单里。",

    "- 2026-10-16 `PermissionError: [WinError 32] 另一个程序正在使用此文件` 是「文件被占用」，不是「权限不够」。"
    "长任务的 `.log`、DSH 的启动输出、ComfyUI 的 `.err.log` 在跑的时候一定被占。"
    " → 判据：挪/删的 `except` 里必须 catch `(PermissionError, OSError)`，"
    "**打印「跳过（占用中）」并把清单那一行重写成「跳过」**，不许整批中断。",

    "- 2026-10-16 `_归档` 优于删除：这次删的只有**明确可再生**的东西（分段超分的中间件 703 MB、`__pycache__`、0 字节文件），"
    "其余 703 个文件全部 `shutil.move` 到 `_归档\\` 下分好类。"
    " → 判据：清单里每一行的「为什么」要能独立成立（「补经验时自动备的旧版」可以，「没用」不行）—— 硬红线 1。",

    "- 2026-10-16 交接文档里出现的**每一个绝对路径都要能被一条命令逐条验**。"
    "本次写 `check_交接.py`：正则从 md 里刮出全部盘符路径，逐个 `os.path.exists`，"
    "刮不到就报「找不到」。同时留一张「不验但要写清理由」的表（如远端 `E:\\影匠AI` 本机当然没有）。"
    " → 判据：`python check_交接.py` 退 0 且报「全对」；41/41 通过。"
    "★ 注意刮路径时要把尾部的 `'` `\"` `:` 一起剥掉，否则会报 10 条假缺失。",

    "- 2026-10-16 这台机器**没有 pwsh，只有 Windows PowerShell 5.1**，而 5.1 按 ANSI/GBK 读 `.ps1`。"
    " → 判据：凡要用 PowerShell 跑带中文的脚本，一律让 **Python 写成 `utf-8-sig`（带 BOM）** 再 `powershell -File` 跑；"
    "现成做法见 `_建桌面2.py`。",

    "- 2026-10-16 `ssh` 传远端命令会被本地 PowerShell 先拆一遍（`ssh 776bjta 'free -m'` 报 `free 不是 cmdlet`）。"
    " → 判据：查远端一律走 ComfyUI 自己的 HTTP（`/system_stats` 内存显存温度 / `/queue` / `/history` / `/internal/logs/raw`），"
    "**不要在 pwsh 里拼远端命令字符串**。",

    "- 2026-10-16 后台 job 的 Python stdout 是**块缓冲** —— `job_output` 长时间只回「(no new output)」，看着像卡死其实在跑。"
    " → 判据：监控超过 1 分钟的长任务，去读它自己写的日志文件或远端的 `/queue`，别拿 `job_output` 当进度条。",
]


def 主():
    if not os.path.isfile(目):
        print("✗ 找不到 %s" % 目)
        return 1
    前 = os.path.getsize(目)
    备 = 目 + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(目, 备)
    with open(目, "a", encoding="utf-8") as f:
        f.write("\n")
        for s in 条:
            f.write(s + "\n")
    后 = os.path.getsize(目)
    print("✓ %s" % 目)
    print("  备份 → %s（%d B）" % (备, 前))
    print("  追加 %d 条　%d → %d 字节（+%d）" % (len(条), 前, 后, 后 - 前))
    return 0


if __name__ == "__main__":
    raise SystemExit(主())
