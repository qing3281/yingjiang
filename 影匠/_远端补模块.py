# -*- coding: utf-8 -*-
import subprocess

Py = r"E:\影匠AI\ComfyUI\.venv\Scripts\python.exe"
包 = ["omegaconf", "segment-anything", "dill", "chardet", "triton-windows"]
r = subprocess.run([Py, "-m", "pip", "install", "-q", "-i",
                    "https://pypi.tuna.tsinghua.edu.cn/simple"] + 包,
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=2400)
print("  pip 退出码 %d" % r.returncode)
尾 = ((r.stderr or "") + (r.stdout or "")).strip()
print("  " + (尾[-800:].replace("\n", "\n  ") if 尾 else "（无输出）"))
