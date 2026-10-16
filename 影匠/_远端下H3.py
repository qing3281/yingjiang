# -*- coding: utf-8 -*-
"""远端自己下载 H3 模型 —— 本机只发指令，不传字节。

用户原话：「你不能给指令到那边，由那边来下载吗，非要传输吗」

做法：本机把 _dl_h3.py 传过去（几 KB），远端自己从 hf-mirror.com 拉
58 GB 模型。远端 E 盘 816 GB 空闲、hf-mirror 实测 HTTP 200 / 0.64s。

用法：
    python _远端下H3.py --探      只探远端下载速度
    python _远端下H3.py          真下（后台跑）
"""
import argparse
import os
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
远程 = "776bjta"
远端家 = "C:/Users/Seele"


def 跑(命令, 超时=3600):
    r = subprocess.run(命令, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=超时)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--探", action="store_true")
    参 = ap.parse_args()

    print("【1】传脚本过去（几 KB）")
    码, 文 = 跑(["scp", "-o", "ConnectTimeout=15",
                os.path.join(根, "_dl_h3_远端.py"), f"{远程}:{远端家}/_dl_h3.py"])
    print(f"  {'✓' if 码 == 0 else '✗ ' + 文[-200:]}")

    print("\n【2】远端环境")
    码, 文 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                'python -c "import sys;print(sys.version);print(sys.executable)"'], 120)
    print("  " + 文.strip().replace("\n", "\n  "))

    print("\n【3】远端模型目录")
    码, 文 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                'python -c "import os;p=r\'E:\\影匠AI\\ComfyUI-Shared\\models\';'
                'print(p, os.path.isdir(p))"'], 120)
    print("  " + 文.strip())

    if 参.探:
        print("\n【4】探速（拿最小的 vae 试）")
        码, 文 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                    f"python -X utf8 {远端家}/_dl_h3.py --probe"], 1800)
        print("  " + 文.strip().replace("\n", "\n  "))
        return 0

    print("\n【4】远端后台下载（58 GB）")
    命令 = (f'python -c "import subprocess,sys;'
            f'p=subprocess.Popen([sys.executable,\'-X\',\'utf8\',r\'{远端家}/_dl_h3.py\'],'
            f'stdout=open(r\'{远端家}/_dl_h3.log\',\'w\'),stderr=subprocess.STDOUT,'
            f'creationflags=0x00000008);print(\'PID\',p.pid)"')
    码, 文 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程, 命令], 120)
    print("  " + 文.strip())
    print(f"\n  日志：远端 {远端家}/_dl_h3.log")
    print(f"  查看：ssh {远程} \"type {远端家}\\_dl_h3.log\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
