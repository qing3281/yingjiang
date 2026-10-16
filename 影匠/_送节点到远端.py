# -*- coding: utf-8 -*-
"""本机侧：把 21 个 H3 自定义节点包送到远端 ComfyUI。

做法：本机 tar 成一个包（335 MB）→ scp 过去（实测 scp 2.7 MB/s，约 2 分钟）→ 远端解开。

★ 为什么不直接 scp 21 个目录：scp 传目录时符号链接/空目录行为不一致；
   tar 一个包更可控，也只需一次握手。
★ 远端路径含中文「影匠AI」，Windows 的 bsdtar 处理中文没问题，但
   ssh 命令行本身仍是 GBK 控制台 —— 所以解包动作放在远端 .py 里做，不写在 ssh 命令里。
"""
import os
import subprocess
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
远程 = "776bjta"
源 = os.path.join(根, "_网盘整理", "取出",
                  "02_WF整合包_2026.9.28（不含模型）", "Comfyui-WF-2026.8.8",
                  "ComfyUI", "custom_nodes")

节点 = [
    "comfyui-minimax-h3-audio-T8",
    "comfyui-minimax-h3-blockcache-T8",
    "ComfyUI-MiniMaxH3-AVCache-CN",
    "ComfyUI-YCNodes-MiniMax-H3",
    "comfyui-videohelpersuite",
    "comfyui-frame-interpolation",
    "ComfyUI-GIMM-VFI",
    "ComfyUI-VFI",
    "rgthree-comfy",
    "ComfyMath",
    "ComfyUI-EulerDiscreteScheduler",
    "cg-use-everywhere",
    "comfyui-custom-scripts",
    "ComfyUI-Crystools",
    "comfyui-kjnodes",
    "comfyui_essentials",
    "ComfyUI_StringOps",
    "ComfyUI-Various",
    "comfyui-impact-pack",
    "comfyui-impact-subpack",
    "comfyui-inpaint-nodes",
]

压缩包 = os.path.join(根, "_节点包_21个.tar")


def 跑(cmd, 超时=3600, 回显=True):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=超时)
    if 回显 and r.stderr.strip():
        print("    " + r.stderr.strip()[:500])
    return r.returncode, (r.stdout or "")


def main():
    print("=== %s 送 21 个节点包到远端 ===" % time.strftime("%H:%M:%S"))

    if not os.path.isdir(源):
        print("✗ 源目录不存在：%s" % 源)
        return 1

    有 = [n for n in 节点 if os.path.isdir(os.path.join(源, n))]
    print("  源里找到 %d/%d 个包" % (len(有), len(节点)))
    缺 = [n for n in 节点 if n not in 有]
    if 缺:
        print("  缺：%s" % 缺)

    # 1) 打包
    print("\n[1/3] 本机打包 ...")
    if os.path.exists(压缩包):
        os.remove(压缩包)
    码, _ = 跑(["tar", "-cf", 压缩包, "-C", 源] + 有)
    if 码:
        print("✗ tar 失败")
        return 1
    mb = os.path.getsize(压缩包) / 1048576
    print("  ✓ %.1f MB  %s" % (mb, 压缩包))

    # 2) 传
    print("\n[2/3] scp 到远端（%.0f MB，按 2.7 MB/s 约 %.0f 分钟）..." % (mb, mb / 2.7 / 60))
    t0 = time.time()
    码, _ = 跑(["scp", "-q", 压缩包, "%s:C:/Users/Seele/_节点包_21个.tar" % 远程], 超时=7200)
    if 码:
        print("✗ scp 失败")
        return 1
    dt = time.time() - t0
    print("  ✓ 传完 %.0f 秒（%.2f MB/s）" % (dt, mb / dt))

    # 3) 远端解开
    print("\n[3/3] 远端解开 ...")
    远端代码 = r'''# -*- coding: utf-8 -*-
import os
import tarfile
import time

目标 = r"E:\影匠AI\ComfyUI\custom_nodes"
包 = r"C:\Users\Seele\_节点包_21个.tar"

os.makedirs(目标, exist_ok=True)
前 = set(os.listdir(目标))

t0 = time.time()
with tarfile.open(包) as t:
    t.extractall(目标)
后 = set(os.listdir(目标))
新 = sorted(后 - 前)

print("  解开用时 %.1f 秒" % (time.time() - t0))
print("  新增 %d 个：%s" % (len(新), 新))
print("  现在 custom_nodes 共 %d 个目录" % len([d for d in os.listdir(目标)
                                             if os.path.isdir(os.path.join(目标, d))]))

# 复验：最要紧的那个包的 __init__.py 在不在
关键 = os.path.join(目标, "comfyui-minimax-h3-audio-T8", "__init__.py")
print("  关键包 __init__.py：%s" % ("在" if os.path.exists(关键) else "★ 不在"))
'''
    临 = os.path.join(根, "_远端解包.py")
    open(临, "w", encoding="utf-8").write(远端代码)
    跑(["scp", "-q", 临, "%s:C:/Users/Seele/_远端解包.py" % 远程], 超时=300)
    码, 出 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                 "python -X utf8 C:/Users/Seele/_远端解包.py"], 超时=1800)
    print(出)
    return 0 if 码 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
