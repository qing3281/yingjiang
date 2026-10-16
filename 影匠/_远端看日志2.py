# -*- coding: utf-8 -*-
import os
import re

for 名, p in [("stdout", r"C:\Users\Seele\_comfyui_r.log"),
              ("stderr", r"C:\Users\Seele\_comfyui_re.log")]:
    print("\n########## %s  %s ##########" % (名, p))
    if not os.path.exists(p):
        print("  （不存在）")
        continue
    t = open(p, "rb").read().decode("utf-8", "replace")
    # 去掉 ANSI 颜色
    t = re.sub(r"\x1b\[[0-9;]*m", "", t)
    print("  大小 %d 字节" % len(t))
    print("--- 尾 4000 字 ---")
    print(t[-4000:])
    print("--- 出现过的异常行 ---")
    for l in t.splitlines():
        if any(k in l for k in ("Traceback", "Error", "error", "Exception",
                                "IMPORT FAILED", "Cannot", "assert")):
            print("  " + l.strip()[:200])
