# -*- coding: utf-8 -*-
"""建桌面快捷方式 —— 用户不想记网址。

用户 2026-10-15 01:20 原话：

    我不是特别喜欢这样的一个小的网站……那么假如哪天我把这个网址给忘了呢，好麻烦呀。
    你能不能用点别的方式？比如说能在桌面上给我建个快捷方式也好，或者是什么别的什么也行。

跑一次就行，以后改名字/加台子再跑。

    python _建快捷方式.py
"""
import io
import os
import subprocess
import sys

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

台 = [
    ("记忆台", "记忆",
     "记忆台 —— 我说过的话 / 我翻过哪些文件 / 踩过的坑 / 攒的经验", 13),
    ("影匠控制台", "影匠",
     "影匠控制台 —— 两台机器的温度/显存 + 起活停活 + 进度 + 成片（能操作）", 116),
]


def 桌面():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "[Environment]::GetFolderPath('Desktop')"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def 写启动器(名, 参):
    """★ cmd.exe 按 GBK 解码，必须存 GBK —— 存 UTF-8 中文会乱码。"""
    cmd = os.path.join(根, "%s.cmd" % 名)
    文 = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "title {名}\r\n"
        "cd /d {根}\r\n"
        '"{py}" -X utf8 -u _开台.py {参}\r\n'
        "if errorlevel 1 pause\r\n"
    ).format(名=名, 根=根, py=PY, 参=参)
    with io.open(cmd, "w", encoding="gbk", newline="") as f:
        f.write(文)
    return cmd


def 建快捷方式(壳, 目标, 工作目录, 说明, 图标号):
    """用 PowerShell 的 WScript.Shell 建 .lnk。

    ★ 这版是写成文件跑的，不是 -Command 内联 ——
      内联时 PowerShell 的 $ 变量会被外层 shell 吃掉，报
      「An expression was expected after '('」。
    """
    脚本 = os.path.join(根, "_建快捷方式.ps1")
    文 = (
        "$w = New-Object -ComObject WScript.Shell\n"
        "$s = $w.CreateShortcut('{壳}')\n"
        "$s.TargetPath = '{目标}'\n"
        "$s.WorkingDirectory = '{工}'\n"
        "$s.Description = '{说明}'\n"
        "$s.IconLocation = \"$env:SystemRoot\\System32\\shell32.dll,{图}\"\n"
        "$s.Save()\n"
    ).format(壳=壳, 目标=目标, 工=工作目录, 说明=说明, 图=图标号)
    with io.open(脚本, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(文)
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", 脚本],
                       capture_output=True, text=True)
    os.remove(脚本)
    return os.path.isfile(壳), (r.stdout + r.stderr).strip()


def main():
    桌 = 桌面()
    if not os.path.isdir(桌):
        print("  ✗ 找不到桌面：%s" % 桌)
        return 1
    print("  桌面：%s" % 桌)
    print()
    好 = 0
    for 名, 参, 说明, 图 in 台:
        cmd = 写启动器(名, 参)
        with io.open(cmd, encoding="gbk") as f:
            回 = f.read()
        okc = 名 in 回 and "开台.py" in 回
        print("  %s %s  %d B" % ("✓" if okc else "✗", cmd, os.path.getsize(cmd)))

        壳 = os.path.join(桌, "%s.lnk" % 名)
        ok, 日 = 建快捷方式(壳, cmd, 根, 说明, 图)
        if ok:
            print("    ✓ 桌面：%s  %d B" % (壳, os.path.getsize(壳)))
            好 += 1
        else:
            print("    ✗ 快捷方式失败：%s" % 日[:300])
    print()
    print("  %d / %d 建好了" % (好, len(台)))
    return 0 if 好 == len(台) else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
