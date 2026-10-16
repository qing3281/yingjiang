# -*- coding: utf-8 -*-
r"""在远端那台机器上跑 PowerShell，把结果原样带回来。

★ 为什么要有这个文件（踩了三次才想明白）
  远端登录进去是 **Windows PowerShell 5.1**，不是 cmd。于是我在本机写
  `ssh 776bjta "<命令>"` 的时候，那条命令要穿过 **两层解析器**：
  本机 PowerShell 先啃一遍（吃掉引号、展开 `$`、有时把 `|` 接走），
  远端 PowerShell 再啃一遍。实测三次翻车：
    ① `dir /b ... & echo ===`  → 本机报 `AmpersandNotAllowed`
    ② `Where-Object { $_.Name -eq "upscale_models" }` → 引号没了，ParserError
    ③ `ForEach-Object { $_.Name + ... }` → 变成 `\.Name`，MissingArgument
  **只要有两个解析器，就不要把命令拼成字符串。**

★ 做法：把命令转成 **UTF-16LE Base64**，走 `powershell -EncodedCommand`。
  Base64 里只有 `A-Za-z0-9+/=`，**两层解析器都无从下手**。顺带解决了中文。

用法：
    python _远端.py "Get-ChildItem D:\\ -Directory | Select-Object -ExpandProperty Name"
    python _远端.py --找 upscale_models      # 在 D:\\ 下按名字找目录
    python _远端.py --模型                   # 远端 ComfyUI 的模型家底
    python _远端.py --文件 <远端路径>         # 列一个目录（带大小）
"""
import base64
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

主机 = os.environ.get("影匠远端", "776bjta")
默认根 = os.environ.get("影匠远端根", "D:\\Comfy-Desktop\\ComfyUI-Installs\\ComfyUI\\ComfyUI")


def 跑(命令, 超时=240):
    """把 PowerShell 命令 Base64 一下丢给远端，绕开所有引号层。

    ★ 还要在开头强制把远端的输出编码改成 UTF-8 ——
      远端是中文 Windows，PowerShell 默认往管道里吐 **GBK**，
      本机按 UTF-8 解就是 `��� from Զ��`。两边都要说 UTF-8 才对得上。
    """
    头 = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;$OutputEncoding=[Text.Encoding]::UTF8;"
    壳 = ("powershell -NoProfile -EncodedCommand "
          + base64.b64encode((头 + 命令).encode("utf-16-le")).decode())
    p = subprocess.run(["ssh", 主机, 壳], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=超时)
    出 = ((p.stdout or "") + (p.stderr or "")).strip()
    # 砍掉 PowerShell 的 CLIXML 噪声（远端每跑一次都会带一段进度流）
    if "#< CLIXML" in 出:
        出 = 出.split("#< CLIXML")[0].strip()
    return p.returncode, 出


def 列目录(路):
    c = (f"if (Test-Path -LiteralPath '{路}') {{ "
         f"Get-ChildItem -LiteralPath '{路}' | ForEach-Object {{ "
         f"$n=$_.Name; $s=if($_.PSIsContainer){{'<目录>'}}else{{[string][math]::Round($_.Length/1MB,1)+' MB'}}; "
         f"\"$n`t$s\" }} }} else {{ '不存在：{路}' }}")
    return 跑(c)


def 找(名字, 根="D:\\"):
    c = (f"Get-ChildItem -LiteralPath '{根}' -Directory -Recurse -Depth 5 "
         f"-ErrorAction SilentlyContinue | "
         f"Where-Object {{ $_.Name -like '*{名字}*' }} | "
         f"Select-Object -ExpandProperty FullName")
    return 跑(c, 超时=600)


def 模型():
    c = ("$b = Get-ChildItem -LiteralPath 'D:\\' -Directory -Recurse -Depth 4 "
         "-ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'models' } | "
         "Select-Object -ExpandProperty FullName; "
         "foreach ($m in $b) { \"=== $m ===\"; "
         "Get-ChildItem -LiteralPath $m -Directory -ErrorAction SilentlyContinue | "
         "ForEach-Object { $c=(Get-ChildItem -LiteralPath $_.FullName -File -ErrorAction SilentlyContinue).Count; "
         "\"  \" + $_.Name + \"`t$c 个文件\" } }")
    return 跑(c, 超时=600)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        raise SystemExit(0)
    if a[0] == "--找":
        rc, s = 找(a[1], a[2] if len(a) > 2 else "D:\\")
    elif a[0] == "--模型":
        rc, s = 模型()
    elif a[0] == "--文件":
        rc, s = 列目录(a[1])
    else:
        rc, s = 跑(" ".join(a))
    print(s or "（没有输出）")
    if rc:
        print(f"\n[退出码 {rc}]")
