# -*- coding: utf-8 -*-
"""本机侧：①补装 4 个缺失模块 ②重启远端 ③从本机 HTTP 复验节点与模型。

缺的模块（从日志里读出来的，不是猜的）：
  omegaconf          → ComfyUI-GIMM-VFI
  segment_anything   → comfyui-impact-pack
  dill               → comfyui-impact-subpack
  chardet            → ComfyUI_StringOps
四个都不是 H3 必需（H3 要的 T8 包已 1.5 秒加载成功），但装上省得日志刷红。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

根 = os.path.dirname(os.path.abspath(__file__))
远程 = "776bjta"
远端 = "http://100.127.224.106:8188"

装 = r'''# -*- coding: utf-8 -*-
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
'''


def 跑(cmd, 超时=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=超时)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def 探(超时=15):
    try:
        return json.load(urllib.request.urlopen(远端 + "/system_stats", timeout=超时))
    except Exception as e:
        return {"_错": str(e)}


def main():
    print("=== %s ===" % time.strftime("%H:%M:%S"))

    print("\n[1/3] 从本机 HTTP 打远端 8188 ...")
    d = 探()
    if "_错" in d:
        print("  ✗ %s" % d["_错"])
        print("  （远端上是起来了的，日志写着 To see the GUI go to: http://0.0.0.0:8188）")
        print("  → 多半是防火墙没放行，下面去掉防火墙规则再试")
        subprocess.run(["ssh", "-o", "ConnectTimeout=20", 远程,
                        'netsh advfirewall firewall add rule name="ComfyUI8188" '
                        'dir=in action=allow protocol=TCP localport=8188'],
                       capture_output=True, text=True, timeout=180)
        time.sleep(2)
        d = 探()
        print("  再试：%s" % ("✓ 在线 %s" % d["system"]["comfyui_version"]
                            if "_错" not in d else "✗ %s" % d["_错"]))
    else:
        print("  ✓ 在线 %s" % d["system"]["comfyui_version"])

    print("\n[2/3] 补装 4 个缺失模块 ...")
    临 = os.path.join(根, "_远端补模块.py")
    open(临, "w", encoding="utf-8").write(装)
    跑(["scp", "-q", 临, "%s:C:/Users/Seele/_远端补模块.py" % 远程], 超时=300)
    码, 出 = 跑(["ssh", "-o", "ConnectTimeout=20", 远程,
                 "python -X utf8 C:/Users/Seele/_远端补模块.py"], 超时=3000)
    print(出.strip())

    print("\n[3/3] 重启远端 + 复验 ...")
    码, 出 = 跑([sys.executable, "-X", "utf8",
                 os.path.join(根, "_远端重启2.py")], 超时=900)
    print(出.strip())

    time.sleep(8)
    d = 探(30)
    if "_错" in d:
        print("\n  ★ 重启后仍打不通：%s" % d["_错"])
        return 1
    print("\n  ✓ 在线 %s" % d["system"]["comfyui_version"])
    o = json.load(urllib.request.urlopen(远端 + "/object_info", timeout=300))
    print("  节点总数 %d" % len(o))
    for n in ["MiniMaxH3AudioConditioningT8", "MiniMaxH3DualClockSamplerT8",
              "MiniMaxH3AVDecodeT8", "MiniMaxH3AVSigmaSameNFERedistributionT8Advanced",
              "VHS_VideoCombine", "LoraLoaderBypassModelOnly"]:
        print("    %-52s %s" % (n, "✓" if n in o else "✗"))
    print("\n  模型：")
    for 类, 键 in [("UNETLoader", "unet_name"), ("CLIPLoader", "clip_name"),
                   ("VAELoader", "vae_name")]:
        try:
            列 = o[类]["input"]["required"][键][0]
            h3 = [x for x in 列 if "minimax" in x.lower() or "qwen3vl" in x.lower()]
            print("    %s：%d 个 H3 相关" % (类, len(h3)))
            for x in h3:
                print("        %s" % x)
        except Exception as e:
            print("    %s 读不到：%s" % (类, e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
