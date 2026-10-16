# -*- coding: utf-8 -*-
"""验 `_守成片.py` → `寄邮件.py` 那条命令行**真的能把多行正文和反斜杠路径送过去**。

## 为什么值得单独测

`_守成片.py` 的 `发信()` 是这么调的：

    subprocess.run([PY, "-X", "utf8", 寄邮件,
                    "--主题", ...,
                    "--正文", "\\n".join(正文),      # ← 多行
                    "--大附件", 成片])              # ← D:\\… 一串反斜杠

这条路我**一次都没跑通过**。它要是把正文送坏了，用户收到的邮件正文就是乱码；
它要是把附件路径送坏了，`寄邮件.py` 找不到文件就不会发。

而 `寄邮件.py` **没有 dry-run 开关**，真跑一次就是真发一封信 —— 所以不能拿它试。
换成**拿本脚本自己当靶子**：父进程用一模一样的形状去起子进程，子进程把收到的
`--正文` 和 `--大附件` 原样打出来，和发出去的那一份逐字节比。
"""
import os
import subprocess
import sys

正文 = ("第一行\n"
      "第二行 含空格\n"
      "  成片：D:\\DSHworkspace\\影匠\\作品\\楚子航\\片\\楚子航_成片_字幕.mp4\n"
      "  验片：D:\\DSHworkspace\\影匠\\作品\\楚子航\\片\\_验帧\n"
      "—— 引号 \" 和 & ^ 这些也得活着")
路径 = "D:\\DSHworkspace\\影匠\\作品\\楚子航\\片\\楚子航_成片_字幕.mp4"


def 子():
    a = sys.argv
    i = a.index("--正文")
    got正文 = a[i + 1]
    j = a.index("--大附件")
    got路径 = a[j + 1]
    好 = True
    if got正文 != 正文:
        好 = False
        print("  ✗ 正文对不上")
        print("    发出 = " + repr(正文))
        print("    收到 = " + repr(got正文))
    else:
        print("  ✓ 正文 %d 字节，含 %d 个换行，逐字节一致"
              % (len(got正文.encode("utf-8")), got正文.count("\n")))
    if got路径 != 路径:
        好 = False
        print("  ✗ 附件路径对不上：发出 %r 收到 %r" % (路径, got路径))
    else:
        print("  ✓ 附件路径反斜杠活着：%s" % got路径)
    print("  子进程 argv 共 %d 项" % len(a))
    return 0 if 好 else 1


def 父():
    cmd = [sys.executable, "-X", "utf8", os.path.abspath(__file__), "--子",
           "--主题", "《楚子航》成片（2.38 分）—— 有一条要跟你说",
           "--正文", 正文,
           "--大附件", 路径]
    print("  用和 _守成片.py 发信() 一模一样的形状起子进程：")
    r = subprocess.run(cmd, capture_output=True)
    print(r.stdout.decode("utf-8", "replace").rstrip())
    if r.stderr:
        print("  stderr: " + r.stderr.decode("utf-8", "replace")[-400:])
    print("  子进程退出码 = %d" % r.returncode)
    return r.returncode


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--子" in sys.argv:
        sys.exit(子())
    print("── check_argv：多行正文 + 反斜杠路径 能不能活着穿过 subprocess ──")
    sys.exit(父())
