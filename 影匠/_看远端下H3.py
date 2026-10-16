# -*- coding: utf-8 -*-
"""本机侧：查远端 H3 下载进度。

★ 教训：**不要在 PowerShell 里拼 ssh 命令**（多层引号必炸，上面已经炸了三次）。
   用 Python 的 subprocess 拼 argv 列表，一次只发一条 ssh。
   远端要跑的代码写成临时 .py，scp 过去再执行。
"""
import os
import subprocess
import sys
import time

远程 = "776bjta"
本目录 = os.path.dirname(os.path.abspath(__file__))
探针 = os.path.join(本目录, "_远端探针.py")

远端代码 = r'''# -*- coding: utf-8 -*-
import os
import subprocess

要看 = [
    r"E:\影匠AI\ComfyUI-Shared\models",
    r"E:\_dl_tmp",
    r"E:\_dl_probe",
]

print("=== 目录明细 ===")
总 = 0.0
for 根 in 要看:
    if not os.path.isdir(根):
        print("  [无] %s" % 根)
        continue
    print("  [有] %s" % 根)
    for dp, dn, fn in os.walk(根):
        for f in fn:
            if not (f.endswith(".safetensors") or "incomplete" in f):
                continue
            try:
                g = os.path.getsize(os.path.join(dp, f)) / 1e9
            except OSError:
                continue
            总 += g
            print("      %-58s %8.2f GB" % (f[:58], g))

print("\n  合计 %.2f GB / 目标 62.8 GB" % 总)

print("\n=== 进程 ===")
try:
    o = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                       capture_output=True, timeout=30)
    t = (o.stdout or b"").decode("gbk", "replace")
    n = t.count("python.exe")
    print("  python.exe 进程数：%d" % n)
except Exception as e:
    print("  查进程失败：%s" % e)

print("\n=== 日志 ===")
p = r"C:\Users\Seele\_dl_h3.log"
if os.path.exists(p):
    t = open(p, encoding="utf-8", errors="replace").read()
    print("  大小 %d 字节" % len(t))
    print("  " + (t[-1200:].strip().replace("\n", "\n  ") if t.strip() else "（空）"))
else:
    print("  不存在")
'''


def 跑(命令, 超时=180):
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", 远程, 命令],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=超时)
    return (r.stdout or "") + (r.stderr or "")


def main():
    print("=== %s ===" % time.strftime("%H:%M:%S"))

    with open(探针, "w", encoding="utf-8") as f:
        f.write(远端代码)

    r = subprocess.run(["scp", "-q", 探针, "%s:C:/Users/Seele/_远端探针.py" % 远程],
                       capture_output=True, text=True, timeout=120)
    if r.returncode:
        print("scp 失败：%s" % (r.stderr or "")[:300])
        return 1

    print(跑("python -X utf8 C:/Users/Seele/_远端探针.py", 超时=300))
    return 0


if __name__ == "__main__":
    sys.exit(main())
