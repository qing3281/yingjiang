# -*- coding: utf-8 -*-
r"""看/拉远端 ComfyUI 的产出。

## ★ 为什么单独一个文件，不直接在 PowerShell 里敲

踩了两层坑，都在这一个文件里绕开：

1. **远端的 ssh 落到的 shell 是 PowerShell**，不是 cmd、也不是 bash。
   所以 `ls -1 xxx | grep yyy || true` 会被远端 PowerShell 自己报 `|| 不是有效分隔符`。
2. **中文路径经 本机PowerShell → ssh → 远端PowerShell 这条链会被吃成乱码**
   （`影匠AI` 变成 `Ӱ��AI`）。所以远端命令里**不能出现中文**。

绕法：把远端那条 PowerShell 命令编成 **UTF-16LE 的 base64**，用 `-EncodedCommand` 送进去。
base64 是纯 ASCII，整条链上一个字节都不会被动。

用法：
    python _看远端.py                看远端 output/ 最新的几条
    python _看远端.py --名 觉醒开头12s_1440p_00001_.mp4     拉回本机
"""
import base64
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

别名 = "776bjta"
远输出 = "E:" + chr(92) + "影匠AI" + chr(92) + "ComfyUI" + chr(92) + "output"
本地目录 = r"D:\DSHworkspace\影匠\作品\_超分试验"


def 远端跑(ps, 超时=180):
    """把一段 PowerShell 命令送到远端执行，返回 (返回码, 标准输出, 标准错误)。

    ★ 输出也会乱码：远端 PowerShell 按**本机代码页（GBK）**往外写字节，
      这边按 UTF-8 解就把「觉醒」解成「���ѿ�」。
      两头都堵上：远端先把 OutputEncoding 设成 UTF-8；这边解不出来再退回 GBK。
    """
    头 = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
          "$OutputEncoding=[Text.Encoding]::UTF8; ")
    b64 = base64.b64encode((头 + ps).encode("utf-16-le")).decode("ascii")
    r = subprocess.run(["ssh", 别名, "powershell", "-NoProfile", "-EncodedCommand", b64],
                       capture_output=True, timeout=超时)
    原 = r.stdout or b""

    def 解(b):
        try:
            return b.decode("utf-8")
        except UnicodeDecodeError:
            return b.decode("gbk", "replace")

    return r.returncode, 解(原), 解(r.stderr or b"")


def 主():
    if "--名" in sys.argv:
        名 = sys.argv[sys.argv.index("--名") + 1]
        远 = f"{别名}:{远输出}/{名}"
        本 = os.path.join(本地目录, 名)
        print(f"  拉：{远}\n   → {本}")
        r = subprocess.run(["scp", "-q", 远, 本], capture_output=True, timeout=7200)
        if r.returncode != 0 or not os.path.isfile(本):
            print("  ✗ 失败：" + (r.stderr or b"").decode("utf-8", "replace")[:400])
            return 1
        print(f"  ✓ {本}　{os.path.getsize(本):,} B")
        return 0

    ps = (f'$d = "{远输出}"; '
          'Get-ChildItem -LiteralPath $d -File | '
          'Sort-Object LastWriteTime -Descending | '
          'Select-Object -First 12 | '
          'ForEach-Object { "{0}  {1:N0} B  {2:MM-dd HH:mm}" -f $_.Name, $_.Length, $_.LastWriteTime }')
    rc, out, err = 远端跑(ps)
    print(f"  远端 output/ 最新 12 个（rc={rc}）：")
    for s in out.splitlines():
        if s.strip():
            print("    " + s.strip())
    if not out.strip():
        print("    （空的）" + (err[:300] if err else ""))
    return 0


if __name__ == "__main__":
    sys.exit(主())
