# -*- coding: utf-8 -*-
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
