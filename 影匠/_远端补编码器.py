# -*- coding: utf-8 -*-
"""本机侧：①远端补下 int8 版文本编码器（和本机逐字节同款）②重启远端 ComfyUI ③复验节点。

★ 为什么要补：远端刚才下的 `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` 是 **15.69 GB 的 nvfp4 4 位**版，
   而本机工作流用的是 `qwen3vl_32b_minimax_h3_int8_convrot.safetensors`（**25.28 GiB 的 int8**）。
   用户硬规矩第 2 条：**效果必须由本机决定**。两边必须同一份权重，否则质量对比无意义。
"""
import os
import subprocess
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
远程 = "776bjta"


def 跑(cmd, 超时=7200):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=超时)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


补下代码 = r'''# -*- coding: utf-8 -*-
import os
import time

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
DEST = r"E:\影匠AI\ComfyUI-Shared\models"
REPO = "Comfy-Org/MiniMax-H3"
名字 = "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
目标 = os.path.join(DEST, "text_encoders", 名字)

if os.path.exists(目标) and os.path.getsize(目标) > 1e10:
    print("  已有 %.2f GB" % (os.path.getsize(目标) / 1e9))
else:
    from huggingface_hub import hf_hub_download
    t0 = time.time()
    p = hf_hub_download(repo_id=REPO, filename="text_encoders/" + 名字, local_dir=DEST)
    dt = max(0.001, time.time() - t0)
    g = os.path.getsize(p) / 1e9
    print("  完成 %.2f GB  %.1f 分  %.1f MB/s" % (g, dt / 60, g * 1000 / dt))
'''

重启代码 = r'''# -*- coding: utf-8 -*-
"""远端：杀掉旧 ComfyUI 进程，用原来的命令行重启（脱离父进程）。"""
import json
import os
import subprocess
import sys
import time
import urllib.request

基础 = r"E:\影匠AI\ComfyUI"

# 1) 找现在在跑的 ComfyUI 进程及其命令行
ps = r"""
$p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object { $_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*ComfyUI*' }
$p | ForEach-Object { "$($_.ProcessId)|$($_.CommandLine)" }
"""
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, timeout=120)
文本 = (r.stdout or b"").decode("gbk", "replace").strip()

行 = [l for l in 文本.splitlines() if "|" in l]
print("    找到 %d 个 ComfyUI 进程" % len(行))
命令行 = None
for l in 行:
    pid, _, cmd = l.partition("|")
    print("      PID %s" % pid.strip())
    print("        %s" % cmd.strip()[:220])
    if "main.py" in cmd:
        命令行 = cmd.strip()

if not 命令行:
    # 没找到就用默认的
    py = os.path.join(基础, ".venv", "Scripts", "python.exe")
    命令行 = '"%s" main.py --listen 0.0.0.0 --port 8188' % py
    print("    （没找到，用默认命令行）")

# 2) 杀掉
for l in 行:
    pid = l.split("|")[0].strip()
    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    print("    杀掉 PID %s" % pid)
time.sleep(4)

# 3) 重启（脱离）
DETACHED = 0x00000008 | 0x00000200
日志 = open(r"C:\Users\Seele\_comfyui_r.log", "wb")
p = subprocess.Popen(命令行, cwd=基础, stdout=日志, stderr=subprocess.STDOUT,
                     creationflags=DETACHED, shell=True)
print("    新进程 PID %d" % p.pid)

# 4) 等它起来
好了 = False
for i in range(60):
    time.sleep(5)
    try:
        d = json.load(urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=10))
        好了 = True
        print("    ComfyUI 起来了（等了 %d 秒）" % ((i + 1) * 5))
        break
    except Exception:
        pass

if not 好了:
    print("    ★ 90 秒还没起来，看日志：C:\\Users\\Seele\\_comfyui_r.log")
    sys.exit(1)
'''


def main():
    print("=== %s 远端补编码器 + 重启 ===" % time.strftime("%H:%M:%S"))

    print("\n[1/2] 补下 int8 文本编码器（25.28 GiB，按 184 MB/s 约 2.5 分钟）...")
    t = os.path.join(根, "_远端补下.py")
    open(t, "w", encoding="utf-8").write(补下代码)
    跑(["scp", "-q", t, "%s:C:/Users/Seele/_远端补下.py" % 远程], 超时=300)
    码, 出 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                 "python -X utf8 C:/Users/Seele/_远端补下.py"], 超时=3600)
    print(出.strip())
    if 码:
        print("  ★ 补下失败，先不重启")
        return 1

    print("\n[2/2] 重启远端 ComfyUI ...")
    t = os.path.join(根, "_远端重启.py")
    open(t, "w", encoding="utf-8").write(重启代码)
    跑(["scp", "-q", t, "%s:C:/Users/Seele/_远端重启.py" % 远程], 超时=300)
    码, 出 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                 "python -X utf8 C:/Users/Seele/_远端重启.py"], 超时=900)
    print(出.strip())
    return 0 if 码 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
