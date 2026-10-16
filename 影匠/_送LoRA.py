# -*- coding: utf-8 -*-
"""本机侧：把本机的 H3 turbo LoRA 送到远端 loras 目录。

为什么要送：远端 HF 仓库里只有 v1.0，本机用的是 **v1.2**，
版本不同结果就不同 —— 用户规矩是「效果由本机决定」，所以必须送同一个文件。
scp 2.7 MB/s，1.82 GB 约 11 分钟，比 1.8 小时的生成时间小得多。
"""
import os
import subprocess
import sys
import time

远程 = "776bjta"
本机 = r"D:\Comfy-Desktop\ComfyUI-Shared\models\loras"
名 = "minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors"
远端目录 = "E:/影匠AI/ComfyUI-Shared/models/loras"


def main():
    源 = os.path.join(本机, 名)
    if not os.path.exists(源):
        print("✗ 本机没有：%s" % 源)
        d = os.path.dirname(本机)
        if os.path.isdir(本机):
            for f in sorted(os.listdir(本机)):
                if "minimax" in f.lower():
                    print("    隔壁有：%s" % f)
        return 1

    mb = os.path.getsize(源) / 1e6
    print("=== %s  送 LoRA 到远端 ===" % time.strftime("%H:%M:%S"))
    print("  %s  %.1f MB（按 2.7 MB/s 约 %.1f 分钟）" % (名, mb, mb / 2.7 / 60))

    subprocess.run(["ssh", "-o", "ConnectTimeout=20", 远程,
                    'if not exist "E:\\影匠AI\\ComfyUI-Shared\\models\\loras" '
                    'mkdir "E:\\影匠AI\\ComfyUI-Shared\\models\\loras"'],
                   capture_output=True, timeout=120)

    t0 = time.time()
    r = subprocess.run(["scp", "-q", 源, "%s:%s/%s" % (远程, 远端目录, 名)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=3600)
    dt = time.time() - t0
    if r.returncode != 0:
        print("✗ scp 失败：%s" % (r.stderr or "")[:400])
        return 1
    print("  ✓ 传完 %.0f 秒（%.2f MB/s）" % (dt, mb / dt))

    print("\n--- 远端 loras 目录 ---")
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", 远程,
                        "python -X utf8 C:/Users/Seele/_列loras.py"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=200)
    print(r.stdout or r.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
