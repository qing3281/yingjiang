# -*- coding: utf-8 -*-
"""长镜头实测：362 帧（15.08 秒）一条到底 vs 124 帧（5.17 秒）。

要回答的问题：
  1. 362 帧到底要多久？（旧笔记说「30 分钟没跑完 4 步」，步数本来就是 4）
  2. 显存/内存峰值多少？会不会 OOM？
  3. 是否需要更大的虚拟内存？

顺带监控：每 10 秒记一次进程内存与显存。
"""
from __future__ import annotations
import json, os, sys, time, threading, urllib.request

sys.path.insert(0, r"D:\DSHworkspace\B站\制作")
from MiniMax动态 import 出动态, 活着, 腾地方

首帧 = r"D:\DSHworkspace\B站\成片\龙族_后30秒\首帧\05_首帧.png"
出根 = r"D:\DSHworkspace\B站\成片\长镜头试验"
os.makedirs(出根, exist_ok=True)

# 提示词用 Work-Fisher 的中文逐秒轴（已验证运动量最高）
提示词 = """电影剧照，暴雨夜的高架快速路。一个穿黑风衣的男人独自站在路中央。

0.0-1.5s｜他压低下盘，长刀横在身前，雨水被刀气推开，在他脚下形成一个干燥的圆。
1.5-3.5s｜暗金色的弧形光线从画面上方斜切下来，他一连三次侧身闪避，每次都把刀锋迎上去，金属相撞处炸出成片橘色火星。
3.5-5.5s｜他整个身体腾空翻滚，风衣在雨里甩成一片黑色的扇面，第三道弧光贴着他的背擦过，在沥青上犁出一道焦痕。
5.5-8.0s｜他双脚落地，鞋底在积水里踏出一圈白浪，顺势向前滑出两米，刀尖拖在地上拉出一串火星。
8.0-11.0s｜弧光突然变密，从四面八方同时压来。他原地急速旋身，长刀划出一整个完整的圆，把每一道弧光都挡在身外，撞击声连成一片。
11.0-13.5s｜他单膝跪地，刀撑着地面，喘着粗气，抬头死死盯着画面上方看不见的对手方向。
13.5-15.0s｜他缓缓站直，风衣下摆还在滴水，画面渐渐被雨幕填满。

运镜规则：镜头全程贴在湿沥青面上，从男人的左侧方大幅快速低角度环绕，绕到他背后再绕回来，全程保持他全身在画面下三分之二，幅度大、速度快，不许有任何静止。

音频：持续的暴雨声、刀锋划破空气的尖啸、金属撞击的脆响、鞋底砸在积水里的闷响、粗重的呼吸。无对白，无旁白，无音乐。"""

条 = [
    (124, "S_124帧.mp4"),
    (362, "S_362帧.mp4"),
]

监控 = {"跑": True, "峰内存": 0.0, "峰显存": 0, "样本": []}

def 采():
    import ctypes
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    while 监控["跑"]:
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=5)
            s = json.loads(r.read())
            显 = s["devices"][0]
            用 = (显["vram_total"] - 显["vram_free"]) / 1073741824
            监控["峰显存"] = max(监控["峰显存"], 用)
        except Exception:
            pass
        # 全系统提交量
        try:
            import subprocess
            o = subprocess.run(["powershell", "-NoProfile", "-Command",
                "$os=Get-CimInstance Win32_OperatingSystem; '{0} {1}' -f $os.TotalVirtualMemorySize, $os.FreeVirtualMemory"],
                capture_output=True, text=True, timeout=15).stdout.split()
            提交 = (int(o[0]) - int(o[1])) / 1048576
            监控["峰内存"] = max(监控["峰内存"], 提交)
            监控["样本"].append((time.strftime('%H:%M:%S'), round(提交,1), round(监控['峰显存'],1)))
        except Exception:
            pass
        time.sleep(10)

t = threading.Thread(target=采, daemon=True); t.start()

for 帧数, 名 in 条:
    出 = os.path.join(出根, 名)
    print(f"\n{'='*66}\n{帧数} 帧（{帧数/24:.2f} 秒）→ {名}\n{'='*66}")
    t0 = time.time()
    r = 出动态(首帧, 提示词, "", 出, 帧=帧数, 种子=7711, 超时秒=7200, 放行中文=True)
    耗 = time.time() - t0
    if r and os.path.isfile(r):
        大 = os.path.getsize(r)/1048576
        print(f"  ✅ {耗:.0f} 秒（{耗/60:.1f} 分）  {大:.1f} MB")
        print(f"     每秒视频耗时 {耗/(帧数/24):.1f} 秒")
    else:
        print(f"  ❌ 失败，耗时 {耗:.0f} 秒")

监控["跑"] = False
time.sleep(1)
print(f"\n{'='*66}")
print(f"峰值提交内存 {监控['峰内存']:.1f} GB   峰值显存 {监控['峰显存']:.2f} GB")
print("内存采样（每 10 秒）：")
for s in 监控["样本"][::6]:
    print(f"   {s[0]}  提交 {s[1]:6.1f} GB   显存 {s[2]:5.2f} GB")
