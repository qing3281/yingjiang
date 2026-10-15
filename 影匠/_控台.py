# -*- coding: utf-8 -*-
r"""影匠控制台 —— 把「只能看」变成「能动手」。

## 为什么要另起一个

原来的 `_监工.py`（8791）是**只读**的：能看到首帧、段、成片、日志，但一个按钮都没有。
用户 2026-10-15 说得很直白：

> 「我能操控影匠自己生成视频吗？还是所有都得靠你？」

又说：

> 「我希望它是一个正式的软件，或者至少要比现在一个简单网页更规范的一个东西，
>   能够包含我之前提到的各类的复杂的功能。」

那个「各类的复杂功能」里，最要紧的一条就是**他自己能按**。

## 它比监工台多了什么

| | `_监工.py`（只读台） | `_控台.py`（本文件） |
|---|---|---|
| 看首帧/段/成片 | ✓ | ✓（文件路由是同一套） |
| 看两台机器的显存/内存/温度 | ✗ | **✓ 本机 + 远端 RTX5080** |
| 看两边的 ComfyUI 队列 | ✗ | **✓** |
| **起活**（出首帧 / 出段 / 配音 / 成片 / 超分） | ✗ | **✓ 真起子进程** |
| **停活** | ✗ | **✓ 真杀进程树** |
| 看正在跑的那个活的实时日志 | ✗ | **✓ 边跑边刷** |

## 安全边界（这是个本机服务，不能做成万能执行器）

1. **脚本白名单**：只能跑 `任务表` 里写死的那几个脚本，路径由本文件拼，**不接受任意命令**
2. **参数白名单**：戏名必须是 `作品\` 下真实存在的目录；格号只允许数字和逗号；端点只允许「本机/远端」
3. **文件路由**：沿用只读台那一套（工作区内 + 后缀白名单 + realpath 前缀校验），防目录穿越
4. 只听 `127.0.0.1`

## 用法

    python _控台.py                  # 起在 127.0.0.1:8791，自动开浏览器
    python _控台.py --口 8791 --不开

启动器：`python _开台.py 影匠`（没起就起、起了就开浏览器）。
桌面快捷方式「影匠控制台」指的也是这个口。
"""
import argparse
import ctypes
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _看片 as 看片
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

根 = os.path.dirname(os.path.abspath(__file__))
作品 = os.path.join(根, "作品")
本机Python = sys.executable
打包了 = bool(getattr(sys, "frozen", False))

if 打包了:
    # ★ 打包成 exe 之后有两件事会**静默地**变坏，必须在这儿掰回来：
    #   ① `__file__` 指向 PyInstaller 解出来的临时目录（`_MEIPASS`），
    #      不是 exe 所在的目录 —— 照着它去找 `作品\` 会找到临时目录里去，
    #      于是「一部戏都没有」，看着像整个软件坏了。
    #   ② `sys.executable` 是 **exe 自己**。拿它去跑 `_出H3.py`，
    #      等于再开一个控制台，参数全被当成它自己的命令行 —— 也不报错。
    根 = os.path.dirname(os.path.abspath(sys.executable))
    作品 = os.path.join(根, "作品")
    资源 = getattr(sys, "_MEIPASS", 根)
    if 资源 not in sys.path:
        sys.path.insert(0, 资源)

    def _找真Python():
        """exe 自己不能当解释器用，得去找一个真的 python.exe。"""
        候选 = [
            r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe",
            os.path.join(根, "python.exe"),
            os.path.join(根, "..", "python", "python.exe"),
        ]
        import shutil as _sh
        w = _sh.which("python") or _sh.which("py")
        if w:
            候选.append(w)
        for c in 候选:
            if c and os.path.isfile(c):
                return os.path.abspath(c)
        return None

    本机Python = _找真Python()

允许后缀 = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".gif"}
远端 = "100.127.224.106:8188"
远端主机 = "776bjta"


# ═════════════════════════ 一、两台机器的体检 ═════════════════════════

class 内存状态(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def 取内存():
    m = 内存状态()
    m.dwLength = ctypes.sizeof(内存状态)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return {"总": m.ullTotalPhys, "闲": m.ullAvailPhys, "用率": m.dwMemoryLoad}


def 取队列(址, 超时=4):
    try:
        q = json.load(urllib.request.urlopen(f"http://{址}/queue", timeout=超时))
        return {"跑": len(q.get("queue_running") or []),
                "等": len(q.get("queue_pending") or []), "活": True}
    except Exception as e:
        return {"跑": 0, "等": 0, "活": False, "错": f"{type(e).__name__}"}


# ═════════════════════════ ComfyUI 官方接口（用户 ⑤：能调官方 API）═════════════════════
#
# 用户 2026-10-15 的任务单 P1 第 ⑤ 条：
#   「双机监控可安装小程序 v1 —— 本机 + 远端 RTX5080 的显存/内存/进度，
#     **能调 ComfyUI 官方 API** 也能让 **agent 接管**」
# 还说过四次「**要能自己操作**，只读页面不算」。
#
# 所以这一块**不是只读**：能打断、能清队列、能送任务、能删队列里的一项。
# 走的是 ComfyUI 自己的 HTTP 接口（`/queue` `/interrupt` `/history` `/system_stats`
# `/prompt` `/object_info`），**不碰它的内部状态文件** —— 这样它升级了也不会坏。

机 = {"本机": "127.0.0.1:8188", "远端": 远端}


def _机址(名):
    return 机.get(名 or "本机")


def Comfy取(名, 面, 超时=6):
    """读 ComfyUI 的一个官方接口。面 ∈ queue / history / system_stats / object_info。

    ★ 两个面天生巨大，**不能原样丢给浏览器**（2026-10-15 实测）：
      `object_info` 3.8 MB（四千多种节点）、`history` 639 KB（每跑完一次就长一截）。
      这不是「优化」，是**不裁就点不动**：4 MB 的 JSON 塞进 <pre> 浏览器会卡死。
      所以这两个面只回**摘要**：object_info 回节点名表，history 回最近 20 条的名字。
      要明细自己做 ComfyUI 那边的活 —— 这个页面不负责当 JSON 浏览器。
    """
    址 = _机址(名)
    if not 址:
        return {"活": False, "错": f"没有这台机器：{名}"}
    try:
        r = urllib.request.urlopen(f"http://{址}/{面}", timeout=超时)
        数 = json.load(r)
    except Exception as e:
        return {"活": False, "面": 面, "错": f"{type(e).__name__}: {e}"}

    if 面 == "object_info":
        名们 = sorted(数.keys()) if isinstance(数, dict) else []
        return {"活": True, "面": 面, "裁过": True,
                "说": f"{len(名们)} 种节点（完整表 3.8 MB，这里只列名字）",
                "节点名": 名们}
    if 面 == "history":
        条 = list((数 or {}).items())[-20:]
        出 = []
        for 号, v in 条:
            状 = (v.get("status") or {}).get("status_str") or ""
            出.append({"任务号": 号[:8], "状态": 状,
                       "完成": bool((v.get("status") or {}).get("completed"))})
        return {"活": True, "面": 面, "裁过": True,
                "说": f"一共 {len(数 or {})} 条记录，这里是最近 {len(出)} 条",
                "最近": 出}
    return {"活": True, "面": 面, "数据": 数}


def Comfy做(名, 动作, 体):
    """写操作。**只做 ComfyUI 官方那几个**，不做任何自创的。"""
    址 = _机址(名)
    if not 址:
        return {"ok": False, "错": f"没有这台机器：{名}"}
    try:
        if 动作 == "打断":                       # POST /interrupt
            urllib.request.urlopen(urllib.request.Request(
                f"http://{址}/interrupt", data=b"", method="POST"), timeout=8).read()
            return {"ok": True, "说": f"{名} ComfyUI 已打断当前任务"}

        if 动作 == "清待办":                     # POST /queue {"clear": true} —— 只清等着的
            urllib.request.urlopen(urllib.request.Request(
                f"http://{址}/queue",
                data=json.dumps({"clear": True}).encode(), method="POST",
                headers={"Content-Type": "application/json"}), timeout=8).read()
            return {"ok": True, "说": f"{名} 的等待队列已清空（正在跑的那个不动）"}

        if 动作 == "删项":                       # POST /queue {"delete": [id]}
            项 = 体.get("项")
            if 项 is None:
                return {"ok": False, "错": "删项要给出队列号"}
            urllib.request.urlopen(urllib.request.Request(
                f"http://{址}/queue",
                data=json.dumps({"delete": [str(项)]}).encode(), method="POST",
                headers={"Content-Type": "application/json"}), timeout=8).read()
            return {"ok": True, "说": f"{名} 队列里的 {项} 已删"}

        if 动作 == "送任务":                     # POST /prompt
            图 = 体.get("图")
            if not isinstance(图, dict):
                return {"ok": False, "错": "送任务要给出一个 workflow 对象（图）"}
            r = urllib.request.urlopen(urllib.request.Request(
                f"http://{址}/prompt",
                data=json.dumps({"prompt": 图}).encode(), method="POST",
                headers={"Content-Type": "application/json"}), timeout=20)
            回 = json.load(r)
            return {"ok": bool(回.get("prompt_id")), "说": f"{名} 已收下",
                    "任务号": 回.get("prompt_id"), "回": 回}

        return {"ok": False, "错": f"不认这个动作：{动作}（只有 打断 / 清待办 / 删项 / 送任务）"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "错": f"ComfyUI 回了 {e.code}：{(e.read() or b'')[:200].decode('utf-8', 'replace')}"}
    except Exception as e:
        return {"ok": False, "错": f"{type(e).__name__}: {e}"}


# ── 让 agent 接管（用户 ⑤ 的后半句）─────────────────────────────────────
#
# 他在软件上按一下「这件事我不管了，让 agent 来」，就落一行到 `_等Agent.md`；
# `_开工.py` 每次开工打出来。**不给软件直接开 agent 的后门** —— 软件只负责
# 「把话说到纸上」，怎么干、干不干，仍然由我这一侧决定，他能看见。

# ★ 这份「等 agent 接管」的单子放**工作区根**，不放 `影匠\`。
#   2026-10-15 08:45 踩到：`根` 在 .py 下是 `影匠\`（按 __file__），
#   在 exe 下是 `影匠\`（按 sys.executable）—— 两边一样，但都不是
#   `_开工.py` 待的那个地方。结果我在 `D:\DSHworkspace\` 下怎么找都找不到，
#   还以为没写进去（其实写进 `影匠\_等Agent.md` 了）。
#   **判据：一个文件如果是要给别人看的，它待的地方得由「谁来看」决定，
#   不是由「谁写的」决定。** 看它的是 `_开工.py`，`_开工.py` 在根上。
def _等Agent在哪():
    父 = os.path.dirname(根)
    for d in (父, 根):
        if os.path.isfile(os.path.join(d, "_开工.py")):
            return os.path.join(d, "_等Agent.md")
    return os.path.join(父, "_等Agent.md")


等Agent路 = _等Agent在哪()


def 接管加(事, 为什么, 要什么):
    import io as _io
    from datetime import datetime as _dt
    有 = os.path.isfile(等Agent路)
    with _io.open(等Agent路, "a", encoding="utf-8", newline="\n") as f:
        if not 有:
            f.write("# 等 agent 接管的\n\n"
                    "> 用户 2026-10-15 任务单 ⑤：「…**也能让 agent 接管**」。\n"
                    "> 他在影匠控制台上按一下，就落一行到这里；`_开工.py` 每次开工打出来。\n"
                    "> **不给软件直接开 agent 的后门** —— 软件只负责把话说到纸上。\n\n"
                    "| 什么时候 | 什么事 | 为什么难 | 要 agent 做什么 | 状态 |\n|---|---|---|---|---|\n")
        f.write(f"| {_dt.now().strftime('%m-%d %H:%M')} | {事} | {为什么} | {要什么} | ⬜ 没接 |\n")
    return {"ok": True, "说": "已经写进 `_等Agent.md`，我下次开工就会看到"}


def 接管读():
    import io as _io
    import re as _re
    if not os.path.isfile(等Agent路):
        return []
    出 = []
    for 线 in _io.open(等Agent路, encoding="utf-8").read().splitlines():
        if 线.startswith("| ") and not 线.startswith("| 什么时候"):
            出.append([x.strip() for x in 线.strip("|").split("|")])
    return 出



def 取本机显卡():
    """nvidia-smi 查得到就查，查不到就认了（本机可能没独显或驱动没装）。"""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not r.stdout.strip():
            return None
        p = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"温": int(float(p[0])), "用": int(float(p[1])),
                "显存用": int(float(p[2])), "显存总": int(float(p[3])),
                "瓦": round(float(p[4]))}
    except Exception:
        return None


# 远端那段脚本**必须全是 ASCII** —— 中文经 PowerShell→ssh→cmd→python 这条链会被
# mangle 成乱码，然后 python 报语法错，看起来像「远端挂了」，其实只是编码。
# 这个坑我踩过不止一次（见 记忆\经验\流程与脚本.md）。
远端探针 = r'''
import json, ctypes, subprocess, urllib.request
o = {}
try:
    r = subprocess.run(["nvidia-smi",
        "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw",
        "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=12)
    p = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
    o["gpu"] = {"t": int(float(p[0])), "u": int(float(p[1])),
                "vu": int(float(p[2])), "vt": int(float(p[3])), "w": round(float(p[4]))}
except Exception as e:
    o["gpu_err"] = type(e).__name__ + ":" + str(e)[:60]
class M(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
try:
    m = M(); m.dwLength = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    o["mem"] = {"load": m.dwMemoryLoad, "total": m.ullTotalPhys, "avail": m.ullAvailPhys}
except Exception as e:
    o["mem_err"] = type(e).__name__
try:
    q = json.load(urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=6))
    o["q"] = {"run": len(q.get("queue_running") or []),
              "pend": len(q.get("queue_pending") or [])}
except Exception as e:
    o["q_err"] = type(e).__name__
try:
    fr = ctypes.c_ulonglong(0); tt = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p("E:\\"), None, ctypes.byref(tt), ctypes.byref(fr))
    o["disk"] = {"free": fr.value, "total": tt.value}
except Exception as e:
    o["disk_err"] = type(e).__name__
print(json.dumps(o))
'''

_远缓存 = {"t": 0, "d": None}
_远锁 = threading.Lock()


def 取远端(强制=False):
    """ssh 一次约 1-2 秒，所以缓存 8 秒 —— 页面刷新比这个快也没用。"""
    with _远锁:
        if not 强制 and _远缓存["d"] is not None and time.time() - _远缓存["t"] < 8:
            return _远缓存["d"]
    d = {"活": False}
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", 远端主机, "python -"],
            input=远端探针, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace")
        行 = [x for x in (r.stdout or "").splitlines() if x.strip().startswith("{")]
        if 行:
            z = json.loads(行[-1])
            g = z.get("gpu") or {}
            m = z.get("mem") or {}
            q = z.get("q") or {}
            k = z.get("disk") or {}
            d = {"活": True,
                 "温": g.get("t"), "用": g.get("u"),
                 "显存用": g.get("vu"), "显存总": g.get("vt"), "瓦": g.get("w"),
                 "内存用率": m.get("load"), "内存总": m.get("total"), "内存闲": m.get("avail"),
                 "队列跑": q.get("run", 0), "队列等": q.get("pend", 0),
                 "E剩": k.get("free"), "E总": k.get("total"),
                 "错": z.get("gpu_err") or z.get("q_err") or z.get("disk_err")}
        else:
            d = {"活": False, "错": (r.stderr or "没有输出").strip()[:200]}
    except Exception as e:
        d = {"活": False, "错": f"{type(e).__name__}: {e}"[:200]}
    with _远锁:
        _远缓存["t"], _远缓存["d"] = time.time(), d
    return d


# ═════════════════════════ 二、能起哪些活（白名单） ═════════════════════════

def _戏目录(戏):
    """只在 作品\\ 下的真实目录里选，防注入。"""
    if not re.fullmatch(r"[\w\u4e00-\u9fff\-]{1,20}", 戏 or ""):
        return None
    p = os.path.join(作品, 戏)
    return p if os.path.isdir(p) else None


def _格(格):
    """只允许 数字 与 逗号。"""
    if not 格:
        return []
    if not re.fullmatch(r"\d{1,3}(,\d{1,3})*", 格):
        return None
    return 格.split(",")


片单缓存 = {"时": 0.0, "表": None}


def 片单(戏=None):
    """作品目录下能拿去超分的片子（段 / 片 / _超分试验），新改的排前面。"""
    import time as _t
    if 片单缓存["表"] is not None and _t.time() - 片单缓存["时"] < 20:
        return 片单缓存["表"]
    出 = []
    for 戏名 in ([戏] if 戏 else 列戏()):
        戏目 = os.path.join(根, "作品", 戏名)
        for 子 in ("段", "片", "_超分试验"):
            子目 = os.path.join(戏目, 子)
            if not os.path.isdir(子目):
                continue
            for f in os.listdir(子目):
                if not f.lower().endswith((".mp4", ".mov")):
                    continue
                p = os.path.join(子目, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                出.append({"名": "%s / %s / %s" % (戏名, 子, f), "路": p,
                          "大小": st.st_size, "改": int(st.st_mtime)})
    出.sort(key=lambda x: -x["改"])
    出 = 出[:80]
    片单缓存.update({"时": _t.time(), "表": 出})
    return 出


def _真片(路):
    """只认作品目录里真实存在的视频文件 —— 不接受的路径一律拒掉。"""
    try:
        p = os.path.realpath(路)
    except Exception:
        return False
    if not os.path.isfile(p) or not p.lower().endswith((".mp4", ".mov")):
        return False
    try:
        return p.startswith(os.path.realpath(os.path.join(根, "作品")) + os.sep)
    except Exception:
        return False


def _盖(戏, 格=None, 端=None):
    """把「戏/格/端」拼成脚本尾巴。格是 None 表示不加，端是 None 表示不加。"""
    a = [戏]
    if 格:
        a += ["--只格", ",".join(格)]
    if 端:
        a += ["--端点", 端]
    return a


def 烧字幕参(戏):
    r"""给 `_烧字幕.py` 拼参数。

    ★ 两个坑，都是实测踩出来的：
      ① `_烧字幕.py` **收的是视频路径，不是戏名** —— 写 `["雪线"]` 它会去找一个
         叫「雪线」的文件，报「没找到」。
      ② 不传 `--srt` 它会自己猜，猜不到就报「没找到 srt」。
    命名规矩（后期链条统一）：成品在 `作品\<戏>\片\《<戏>》成片_有声_字幕.mp4`，
    字幕在 `作品\<戏>\配音\_台词.srt`。目录不存在就把参数原样给出去让脚本自己报错，
    总比在这儿猜一个不存在的路径好。
    """
    作 = os.path.join(根, "作品", 戏)
    片 = os.path.join(作, "片", f"《{戏}》成片_有声.mp4")
    出 = os.path.join(作, "片", f"《{戏}》成片_有声_字幕.mp4")
    srt = os.path.join(作, "配音", "_台词.srt")
    return [片, "--srt", srt, "--出", 出]


class _吐流:
    """把 `print()` 的输出接到控制台的日志缓冲上。

    `_出H3.main()` 是**原样搬过来**跑的（AGENTS.md 第 0 条：能整段搬就整段搬），
    它只会 print，所以这里必须装成一个能当 `sys.stdout` 用的东西。
    """

    def __init__(self, 吐):
        self.吐 = 吐

    def write(self, s):
        if s and s.strip():
            self.吐(s.rstrip("\n"))
        return len(s)

    def flush(self):
        pass

    def isatty(self):
        return False


def _直调出段(戏, 格s, 端点, 吐):
    """★ P1⑥：在控制台**这个进程里**出段，不再 `subprocess.Popen` 一个 `_出H3.py`。

    用户 2026-10-15 原话：「你以后生成的这些内容不要每次都写一个 python 脚本……
    把这个工作台这个视频生成的这个软件搭好之后，以后就避免了这样子的复杂的
    每一次一个单独的脚本的效果。」

    做法是**整段搬**：`importlib` 把 `_出H3.py` 当模块导进来，临时换掉
    `sys.argv`（它有 argparse）和 `sys.stdout`（它靠 print 报进度），直接调它的
    `main()`。这样生成逻辑一份、两处用（脚本还能单独跑，软件里也能跑），
    没有第二份实现要维护。
    """
    import importlib
    if 根 not in sys.path:
        sys.path.insert(0, 根)
    出H3 = importlib.import_module("_出H3")

    旧argv, 旧out = sys.argv, sys.stdout
    参数 = ["_出H3.py", 戏, "--端点", 端点]
    if 格s:
        参数 += ["--只格", ",".join(str(x) for x in 格s)]
    sys.argv = 参数
    sys.stdout = _吐流(吐)
    try:
        吐(f"▸ 直调 {戏} / {端点} / 格 {格s or '全部'}")
        出H3.main()
    finally:
        sys.stdout = 旧out
        sys.argv = 旧argv


# ═════════════════ 三、剧组：一部戏卡在哪、往下推、新建一部 ═════════════════
#
# ★ 为什么要这一段 —— 用户 2026-10-15 08:44 的原话：
#     「我看不出来你这个控制台和我说的有什么很大的关联，好像差别挺大的呀。」
#   他问的是对的。病根是：`影匠\剧组.py`（67 KB：判阶段 / 派活 / 卡门 / 收尾）和
#   `导演.py`（立戏 / 定角 / 开镜 / 让镜动）**早就写好了**，四份模板
#   （`模板\节拍拆解.md` 等）也在，可这个控制台**一个都不接** ——
#   它只会跑旧片子的后期三步。于是一台「控制台」只能看旧垃圾，**不能新建一部戏**。
#
# 做法是**整段搬**：`importlib` 把 `剧组.py` 当模块导进来，直接调它的
# `扫状态()` / `判断下一步()` / `_门顺序` —— **不写第二份实现**。
# 页面上的「现在该干什么」和命令行跑出来的是同一句话，不可能对不上。

_剧组 = {"模": None, "错": ""}


def 取剧组():
    """把 剧组.py 当模块导进来（只导一次）。导不动就把原因记下来，别抛。"""
    if _剧组["模"] is not None or _剧组["错"]:
        return _剧组["模"]
    try:
        import importlib
        if 根 not in sys.path:
            sys.path.insert(0, 根)
        _剧组["模"] = importlib.import_module("剧组")
    except Exception as e:
        _剧组["错"] = f"{type(e).__name__}: {e}"
    return _剧组["模"]


def 剧组一览():
    """每一部戏：七个阶段门的灯 + 现在该干什么 + 产物齐不齐。只读，不碰 ComfyUI。"""
    模 = 取剧组()
    if 模 is None:
        return {"ok": False, "错": f"剧组.py 导不进来：{_剧组['错']}"}
    出 = []
    for 戏 in 列戏():
        try:
            状 = 模.扫状态(戏)
            门 = []
            for 键 in 模._门顺序:
                结 = 状["审"].get(键) or "无"
                门.append({"键": 键, "名": 模._规格[键]["名"],
                           "结果": 结, "过": 结 == "PASS"})
            出.append({
                "戏": 戏,
                "门": 门,
                "下一步": 模.判断下一步(状),
                "格数": 状["格数"], "图数": len(状["图们"]),
                "四格数": 状["四格数"], "四图数": len(状["四图们"]),
                "动格数": 状["动格数"], "片数": len(状["片们"]),
                "文件": {k: bool(v) for k, v in 状["有"].items()},
            })
        except Exception as e:
            出.append({"戏": 戏, "错": f"{type(e).__name__}: {e}"})
    return {"ok": True, "戏们": 出, "门槛": list(模._门顺序)}


# 剧本.md 的骨架。★ 「一句话故事」是他给的那一句，一个字都不改地放进去 ——
#   分镜师下游就靠它拆节拍，我在这儿润色等于替他改戏。
剧本骨架 = """\
# 剧本 · {戏}

> 这一份是**给人看的**，不是给机器看的。一句话讲清发生了什么事就行。

## 一句话故事

{一句话}

## 主要人物

（谁、多大年纪、什么身份、身上有什么一眼能认出来的东西）

## 分场

（这场戏在哪儿、谁在场、发生了什么变化。按「变化」分场，不是按台词分。）
"""


def 新建戏(戏名, 一句话):
    """建 作品\\<戏名>\\ 并写 剧本.md。戏名要过 _戏目录 的同一套白名单。

    ★ 已存在就**不覆盖** —— 剧本是他/分镜师写的东西，建戏按钮不该把它抹掉。
    """
    if not re.fullmatch(r"[\w\u4e00-\u9fff\-]{1,20}", 戏名 or ""):
        return {"ok": False, "错": "戏名只能是中文/字母/数字/横线，1–20 个字"}
    if not (一句话 or "").strip():
        return {"ok": False, "错": "一句话故事不能空 —— 空的剧本下游拆不出节拍"}
    目录 = os.path.join(作品, 戏名)
    已有 = os.path.isdir(目录)
    os.makedirs(目录, exist_ok=True)
    本 = os.path.join(目录, "剧本.md")
    if os.path.exists(本):
        return {"ok": False, "已存在": True,
                "错": f"《{戏名}》已经有 剧本.md 了，我没动它（要改请直接改文件）",
                "目录": 目录}
    with io.open(本, "w", encoding="utf-8", newline="\n") as f:
        f.write(剧本骨架.format(戏=戏名, 一句话=一句话.strip()))
    return {"ok": True, "目录": 目录, "剧本": 本, "新目录": not 已有,
            "说": f"建好《{戏名}》，剧本.md 写好了。下一步：派【分镜师】做①节拍拆解"}


任务表 = {
    # ── ★ 剧组流水线：这七条就是 `python 剧组.py …` 本身 ──
    #   不另写实现，页面上按的按钮和命令行敲的是同一条命令。
    "剧组·检查": {
        "脚本": "剧组.py", "剧组": True,
        "说": "看这部戏七个阶段门的灯、产物齐不齐、现在该干什么",
        "参": lambda o: ["检查", o["戏"]],
    },
    "剧组·出图": {
        "脚本": "剧组.py", "剧组": True,
        "说": "出九宫格首帧 `01_格N.png`（本机 3.7 秒一张）",
        "参": lambda o: ["出图", o["戏"]] + (["--重做"] if o.get("重做") else []) + o["闸"],
    },
    "剧组·出图四宫格": {
        "脚本": "剧组.py", "剧组": True,
        "说": "每个锚点展开 4 格，出 `03_锚N格M.png`",
        "参": lambda o: ["出图四宫格", o["戏"]] + (["--重做"] if o.get("重做") else []) + o["闸"],
    },
    "剧组·出片": {
        "脚本": "剧组.py", "剧组": True,
        "说": "出四宫格的动态段 `04_锚N格M.mp4`",
        "参": lambda o: ["出片", o["戏"]] + (["--重做"] if o.get("重做") else []) + o["闸"],
    },
    "剧组·拼图": {
        "脚本": "剧组.py", "剧组": True,
        "说": "把九宫格拼成一张 `_看片表.png`",
        "参": lambda o: ["拼图", o["戏"]],
    },
    "剧组·进度": {
        "脚本": "剧组.py", "剧组": True,
        "说": "写档案 `剧集进度.md`（审片几轮、返工几次、渲染多久）",
        "参": lambda o: ["进度", o["戏"]],
    },
    "剧组·全部": {
        "脚本": "剧组.py", "剧组": True,
        "说": "★ 一步到底 —— 它自己判阶段、自己卡门，缺哪份 md 就停在哪一步",
        "参": lambda o: ["全部", o["戏"]] + (["--强跑"] if o.get("强跑") else []) + o["闸"],
    },
    "出首帧": {
        "脚本": "_出片.py",
        "说": "按九宫格出首帧图（`01_格N.png`）",
        "参": lambda o: _盖(o["戏"], o["格"]) + ["--图"],
    },
    "出段·本机": {
        "脚本": "_出H3.py",
        "说": "本机显卡出视频段",
        "参": lambda o: _盖(o["戏"], o["格"], "本机"),
    },
    "出段·远端": {
        "脚本": "_出H3.py",
        "说": "远端 RTX5080 出视频段（主力）",
        "参": lambda o: _盖(o["戏"], o["格"], "远端"),
    },
    "配音·觉醒": {
        "脚本": "_配台词_觉醒.py",
        "说": "★ 只对《觉醒》—— 按 74 格台词表合成配音（用 `_配台词_觉醒.py`）",
        "参": lambda o: [],
    },
    "总装·觉醒": {
        "脚本": "_成片_觉醒.py",
        "说": "★ 只对《觉醒》—— 接片 → 头尾 → 混音 → 烧字幕（一条命令到底）",
        "参": lambda o: [o["戏"]],
    },
    # ── ★ P1⑥：另外三部戏（磨刀 / 雪线 / 试镜）走的是「后期三步」，
    #    以前软件里**一个按钮都没有** —— 只能在命令行敲。
    #    用户要的是「不用每一次都写一个 python 脚本」，所以这三步也搬进任务表。
    "拼长片（磨刀/雪线/试镜）": {
        "脚本": "_拼长片.py",
        "说": "把 `段\\` 里的散段按九宫格拼成整片（交叉溶解 4.56 秒/格）",
        "参": lambda o: [o["戏"]],
    },
    "配长片（磨刀/雪线/试镜）": {
        "脚本": "_配长片.py",
        "说": "按台词表合成配音并混进长片（**台词表是写死的，改词要改这个脚本**）",
        "参": lambda o: [o["戏"]],
    },
    "烧字幕（磨刀/雪线/试镜）": {
        "脚本": "_烧字幕.py",
        "说": "★ 收的是**视频路径**不是戏名；字幕用 `配音\\_台词.srt`",
        "参": lambda o: 烧字幕参(o["戏"]),
    },
    "超分": {
        # ★ 这个脚本**不在 `影匠\` 下**，在工作区根 `D:\DSHworkspace\_超分.py`。
        #   写 `"_超分.py"` 会让 `os.path.join(根, "_超分.py")` 指到一个不存在的
        #   文件 —— 按了「开始」只会弹一句「脚本不在」。写相对路径才对。
        "脚本": r"..\_超分.py",
        "说": "SeedVR2 2× 超分（远端跑，挑下面那个片）",
        # ★ `_超分.py` 认本机路径会自己传过去（远端已有同名的就不重传）
        "参": lambda o: ["--跑", "--倍数", str(o.get("倍数") or 2),
                       "--文件", o["片"]] if o.get("片") else ["--跑"],
    },
    # ── ★ P1⑥：这一类活**没有脚本文件**，就在控制台进程里直调 ComfyUI ──
    "直调·出段（远端）": {
        "类": "直调",
        "说": "★ 软件内部直调 ComfyUI 出段 —— 不起 python 脚本（远端 RTX5080）",
        "干": lambda o, 吐: _直调出段(o["戏"], o["格"], "远端", 吐),
    },
    "直调·出段（本机）": {
        "类": "直调",
        "说": "★ 软件内部直调 ComfyUI 出段 —— 不起 python 脚本（本机显卡）",
        "干": lambda o, 吐: _直调出段(o["戏"], o["格"], "本机", 吐),
    },
}


def 查任务表():
    r"""开工先自查：任务表里写的脚本文件是不是真的都在？

    ★ 为什么要这么一条：`超分` 写 `"_超分.py"` 而那个文件在工作区根、
    不在 `影匠\` 下 —— 页面上一切正常，只有**按了「开始」的那一刻**才弹
    「脚本不在」。这类错「看得见的地方全绿、真要用的地方是坏的」，
    必须在开工时自己先喊出来。
    """
    毛病 = []
    for 名, t in 任务表.items():
        if t.get("类") == "直调":
            if "脚本" in t:
                毛病.append(f"{名}：直调类不该有「脚本」字段")
            if not callable(t.get("干")):
                毛病.append(f"{名}：直调类没有可调用的「干」")
            continue
        脚 = t.get("脚本")
        if not 脚:
            毛病.append(f"{名}：既不是直调类，也没写「脚本」")
        elif not os.path.isfile(os.path.join(根, 脚)):
            毛病.append(f"{名}：脚本不在 {os.path.normpath(os.path.join(根, 脚))}")
        if not callable(t.get("参")):
            毛病.append(f"{名}：没有可调用的「参」")
    return 毛病


_格线 = re.compile(r"\[(\d+)\s*/\s*(\d+)\]")
_秒线 = re.compile(r"([\d.]+)\s*秒")


def 读格进度(行):
    """从日志里读「第几格 / 共几格」，用来算进度百分比。

    日志长这样（`_出H3.py` 和 `_出片.py` 都这么打）：
        [1/6] ✓ 格17 179.8 秒  0.96 MB  窗台上的阿棠
        [2/6] ✓ 格18 175.2 秒  2.00 MB  合上册子

    ★ 为什么进度要自己从日志里抠，而不用 ComfyUI 的 WebSocket：
    进度条的「一格」是**用户能看懂的单位**（还差几格），而 ComfyUI 的
    `progress` 是采样步（8 步里的第 3 步），对用户没有意义 —— 他关心的是
    「还要几分钟」。同一份日志里已经有每格的真实耗时，用它算剩余最准。

    返回 `(完成格数, 总格数, 最近一格耗时秒)`；读不出来就是 `(0, 0, None)`。
    """
    完 = 总 = 0
    秒 = None
    for s in 行:
        m = _格线.search(s)
        if m:
            i, n = int(m.group(1)), int(m.group(2))
            总 = max(总, n)
            if i <= n:
                完 = max(完, i)
        if "✓" in s:
            mm = _秒线.search(s)
            if mm:
                try:
                    秒 = float(mm.group(1))
                except ValueError:
                    pass
    return 完, 总, 秒


def 加进度(d, 行):
    """往快照里补上「格完 / 格总 / 格秒 / 预计剩秒」。"""
    完, 总, 秒 = 读格进度(行)
    d["格完"], d["格总"], d["格秒"] = 完, 总, 秒
    d["预计剩秒"] = None
    if 总 and 秒 and 完 < 总:
        d["预计剩秒"] = int(秒 * (总 - 完))
    elif 总 and 完 >= 总:
        d["预计剩秒"] = 0
    return d


class 活:
    """一个正在跑的子进程 + 它的输出缓冲。"""
    def __init__(self, 名, 脚本, 参数):
        self.名 = 名
        self.脚本 = 脚本
        self.参数 = 参数
        self.起 = time.time()
        self.行 = []
        self.锁 = threading.Lock()
        self.码 = None
        self.进程 = subprocess.Popen(
            [本机Python, "-X", "utf8", "-u", 脚本] + 参数,
            cwd=根, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        threading.Thread(target=self._读, daemon=True).start()

    def _读(self):
        try:
            for s in self.进程.stdout:
                with self.锁:
                    self.行.append(s.rstrip("\n"))
                    if len(self.行) > 600:
                        del self.行[:200]
        except Exception:
            pass
        self.码 = self.进程.wait()

    def 还活着(self):
        return self.进程.poll() is None

    def 快照(self, 尾=60):
        with self.锁:
            尾行 = self.行[-尾:]
            return 加进度({"名": self.名, "脚本": self.脚本, "参数": self.参数,
                           "起": time.strftime("%H:%M:%S", time.localtime(self.起)),
                           "跑秒": int(time.time() - self.起), "在跑": self.还活着(),
                           "退出码": self.码, "行": 尾行}, self.行)

    def 停(self):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.进程.pid)],
                               capture_output=True, timeout=15)
            else:
                self.进程.terminate()
        except Exception:
            try:
                self.进程.kill()
            except Exception:
                pass


class 直调活:
    """不起子进程 —— 直接在这个进程里调 `影匠\\引擎.py`（ComfyUI 的官方 HTTP 接口）。

    用户 2026-10-15 的原话：「你以后生成的这些内容不要每次都写一个 python 脚本，
    我看着就问题很大，效率又低，效果也不好。把这个工作台这个视频生成的这个软件
    搭好之后，以后就避免了这样子的复杂的每一次一个单独的脚本的效果。」

    ★ 所以这一类活**没有脚本文件**、没有子进程、没有命令行参数拼接 ——
    它就是一个函数，跑完把结果写回作品目录。
    """

    def __init__(self, 名, 干, 说=None):
        self.名 = 名
        self.脚本 = "（直调 影匠\\引擎.py · 无脚本文件）"
        self.参数 = []
        self.说 = 说 or ""
        self.起 = time.time()
        self.行 = []
        self.锁 = threading.Lock()
        self.码 = None
        self._活 = True
        self._干 = 干
        threading.Thread(target=self._跑, daemon=True).start()

    def _吐(self, s):
        with self.锁:
            for 行 in str(s).splitlines() or [""]:
                self.行.append(行)
            if len(self.行) > 600:
                del self.行[:200]

    def _跑(self):
        try:
            self._干(self._吐)
            self._吐("✓ 干完了")
            self.码 = 0
        except Exception as e:
            import traceback
            self._吐(f"✗ {type(e).__name__}: {e}")
            for s in traceback.format_exc().splitlines()[-8:]:
                self._吐("    " + s)
            self.码 = 1
        finally:
            self._活 = False

    def 还活着(self):
        return self._活

    def 快照(self, 尾=60):
        with self.锁:
            尾行 = self.行[-尾:]
            return 加进度({"名": self.名, "脚本": self.脚本, "参数": self.参数, "说": self.说,
                           "起": time.strftime("%H:%M:%S", time.localtime(self.起)),
                           "跑秒": int(time.time() - self.起), "在跑": self.还活着(),
                           "退出码": self.码, "行": 尾行}, self.行)

    def 停(self):
        """直调的活没法从外面杀（它跑在自己的线程里）。

        能做的只有**不再等它**：把在跑标记清掉，让界面能起下一个活；
        真正在远端 ComfyUI 里排队的那份，用「清队列」去停。
        """
        self._活 = False
        self._吐("⚠ 直调的活停不了线程本身；已在远端排队的用「清队列」清掉。")


现在 = {"活": None}
现在锁 = threading.Lock()


# ── 本机 ComfyUI 是可以从这儿点起来的，不然按了「开始」只会得到一个莫名的失败 ──
本机Comfy = {
    "目录": r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI",
    "口": 8188,
    "python": r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe",
}


def 本机Comfy活着():
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{本机Comfy['口']}/queue", timeout=3)
        return True
    except Exception:
        return False


def 起本机Comfy():
    if 本机Comfy活着():
        return {"ok": True, "说": "本机 ComfyUI 本来就在跑"}
    if not os.path.isfile(本机Comfy["python"]) or not os.path.isfile(
            os.path.join(本机Comfy["目录"], "main.py")):
        return {"ok": False, "错": "找不到本机 ComfyUI 的 main.py 或它的 python"}
    try:
        # 独立进程组 + 不挂在本服务上：控台关掉它也应该继续活着
        subprocess.Popen(
            [本机Comfy["python"], "-X", "utf8", "-u", "main.py",
             "--port", str(本机Comfy["口"]), "--listen", "127.0.0.1"],
            cwd=本机Comfy["目录"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            creationflags=(getattr(subprocess, "DETACHED_PROCESS", 0)
                           | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)))
    except Exception as e:
        return {"ok": False, "错": f"{type(e).__name__}: {e}"}
    return {"ok": True, "说": "已发启动命令 —— ComfyUI 起来要 20~60 秒（它要扫模型目录），下面那个灯会自己变绿"}



# ═════════════════════════ 三、生产进度 ═════════════════════════

def 扫进度(戏):
    戏目 = _戏目录(戏)
    if not 戏目:
        return {}
    格数 = len(glob.glob(os.path.join(戏目, "01_格*.png")))
    段 = {}
    for p in glob.glob(os.path.join(戏目, "段", "*.mp4")):
        m = re.match(r"^格(\d+)_(本机|远端)\.mp4$", os.path.basename(p))
        if m:
            段.setdefault(int(m.group(1)), {})[m.group(2)] = round(os.path.getsize(p) / 1048576, 2)

    台词目 = os.path.join(戏目, "配音")
    wav = len([p for p in glob.glob(os.path.join(台词目, "*.wav"))
               if re.match(r"^\d+_格", os.path.basename(p))])
    片 = []
    for p in glob.glob(os.path.join(戏目, "片", "*.mp4")):
        片.append({"名": os.path.basename(p), "mb": round(os.path.getsize(p) / 1048576, 2),
                   "改": time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))})
    片.sort(key=lambda d: -d["mb"])

    九宫格 = os.path.join(戏目, "02-九宫格.md")
    格题 = {}
    if os.path.isfile(九宫格):
        try:
            文 = open(九宫格, encoding="utf-8", errors="replace").read()
            for m in re.finditer(r"^\s*格\s*(\d+)[^\n]*\n((?:\s*[-*|].*\n)+)", 文, re.M):
                格题[int(m.group(1))] = m.group(2).strip()[:160]
        except Exception:
            pass

    return {"首帧": 格数, "段本机": sum(1 for v in 段.values() if "本机" in v),
            "段远端": sum(1 for v in 段.values() if "远端" in v),
            "段齐": sum(1 for v in 段.values() if len(v) == 2),
            "配音": wav, "片": 片[:12], "片总": len(片), "格题": 格题}


def _是戏(目):
    """一个目录算不算「一部戏」。

    ★ 2026-10-15 03:00 踩的坑：只按「是个目录」来列，会把 `接口自测` 这种
      我建来试接口的空目录也列进去，而且它按拼音排在最前面 —— 页面默认选中它，
      于是「进度」全是 0、「超分哪一条」显示「没有 mp4」，看着像坏了。
      判据：有首帧图（`01_格N.png`）或者有台词表，才算一部戏。
    """
    try:
        里 = os.listdir(目)
    except OSError:
        return False
    for f in 里:
        if re.match(r"^01_格\d+\.png$", f):
            return True
    return os.path.isfile(os.path.join(目, "03-台词.md"))


def 列戏():
    """作品\\ 下真正的戏。有多格的那几部排前面（排头那个是页面默认选中的）。"""
    if not os.path.isdir(作品):
        return []
    真 = []
    for d in os.listdir(作品):
        目 = os.path.join(作品, d)
        if not os.path.isdir(目) or d.startswith("_"):
            continue
        if not _是戏(目):
            continue
        try:
            格数 = len([f for f in os.listdir(目) if re.match(r"^01_格\d+\.png$", f)])
        except OSError:
            格数 = 0
        真.append((格数, d))
    真.sort(key=lambda x: (-x[0], x[1]))
    return [d for _, d in 真]


# ═════════════════════════ 四、页面 ═════════════════════════

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0f1115;color:#e6e8ee;
     font:14px/1.6 -apple-system,"Microsoft YaHei",system-ui,sans-serif}
a{color:#7cb7ff;text-decoration:none} a:hover{text-decoration:underline}
.顶{position:sticky;top:0;z-index:9;background:#151922;border-bottom:1px solid #262c3a;
    padding:12px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.顶 h1{margin:0;font-size:17px;font-weight:600}
.壳{max-width:1500px;margin:0 auto;padding:18px 20px 60px}
.排{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.卡{background:#171b25;border:1px solid #262c3a;border-radius:10px;padding:14px 16px;margin-bottom:14px}
.卡 h2{margin:0 0 10px;font-size:14px;color:#9fb0cc;font-weight:600;letter-spacing:.4px}
.机{display:flex;align-items:baseline;gap:8px;margin-bottom:8px}
.机 b{font-size:15px}
.灯{width:9px;height:9px;border-radius:50%;display:inline-block}
.绿{background:#3ddc84;box-shadow:0 0 7px #3ddc84}
.红{background:#ff5b5b;box-shadow:0 0 7px #ff5b5b}
.灰{background:#5a6376}
.数{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:9px;margin-top:6px}
.数 div{background:#12161f;border-radius:7px;padding:7px 9px}
.数 span{display:block;color:#7c8798;font-size:11px}
.数 b{font-size:16px;font-weight:600;font-variant-numeric:tabular-nums}
.条{height:7px;background:#12161f;border-radius:4px;overflow:hidden;margin-top:6px}
.条 i{display:block;height:100%;background:linear-gradient(90deg,#3ddc84,#f5c542,#ff5b5b)}
.钮{display:inline-block;background:#22304a;border:1px solid #33507d;color:#cfe2ff;
     padding:7px 14px;border-radius:7px;cursor:pointer;font-size:13px;margin:3px 5px 3px 0}
.钮:hover{background:#2b3f63}
.钮.主{background:#1d6b40;border-color:#2c9c5e;color:#d6ffe6}
.钮.主:hover{background:#248050}
.钮.危{background:#6b1d1d;border-color:#9c2c2c;color:#ffd6d6}
.钮.危:hover{background:#802424}
.钮[disabled]{opacity:.35;cursor:not-allowed}
input,select{background:#12161f;border:1px solid #2b3242;color:#e6e8ee;
     border-radius:6px;padding:6px 9px;font-size:13px;font-family:inherit}
pre{background:#0b0e14;border:1px solid #202634;border-radius:8px;padding:11px 13px;
    overflow:auto;max-height:420px;margin:0;font-size:12px;line-height:1.5}
.行{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}
.小{color:#7c8798;font-size:12px}
/* ── 看片：给他的那一半。原来整个页面只有我的进度数，他要看的是片子本身 ── */
.人脸{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:14px}
.人脸 figure{margin:0;background:#12161f;border:1px solid #232a38;border-radius:9px;overflow:hidden}
.人脸 img{display:block;width:100%;aspect-ratio:1/1;object-fit:cover;background:#0d1017}
.人脸 figcaption{padding:7px 10px;font-size:13px;color:#dfe7f5}
.脸签{padding:0 10px 9px;font-size:11px;color:#7c8798}
.台词表{width:100%;border-collapse:collapse;font-size:13px}
.台词表 td{padding:6px 8px;border-bottom:1px solid #1e2530;vertical-align:top}
.台词表 tr:hover td{background:#1a2029}
.台词表 .t{color:#8fa3c0;font-variant-numeric:tabular-nums;white-space:nowrap;width:64px}
.台词表 .w{color:#e8c07d;white-space:nowrap;width:74px}
.格墙{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:8px;margin-top:12px}
.格块{background:#12161f;border:1px solid #232a38;border-radius:8px;padding:8px;cursor:pointer}
.格块:hover{border-color:#3d5478;background:#182031}
.格块 .n{font-size:11px;color:#8fa3c0;font-variant-numeric:tabular-nums}
.格块 .ti{font-size:13px;color:#e7edf8;margin:3px 0 4px;line-height:1.3}
.格块 .ju{font-size:11px;color:#6d7a8c}
.格块 .ci{font-size:11px;color:#e8c07d;margin-top:4px;line-height:1.35}
.格块.有片{border-color:#2c5c3f}
.格块.有片 .n::after{content:" ●";color:#3fbf72}
.看片签{display:flex;gap:6px;margin:10px 0 0;flex-wrap:wrap}
.签{background:#1c2431;border:1px solid #2b3546;border-radius:16px;padding:4px 12px;font-size:12px;cursor:pointer;color:#9fb0cc}
.签.亮{background:#22304a;border-color:#33507d;color:#cfe2ff}
.片框{width:100%;max-width:720px;border-radius:8px;background:#000}
.tag{display:inline-block;background:#22304a;border-radius:5px;padding:1px 7px;
     font-size:11px;color:#a9c4ea;margin-left:6px}
.片{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:10px}
.片 a{display:block;background:#12161f;border-radius:8px;padding:8px 10px;color:#cfe2ff}
.吉{color:#3ddc84} .凶{color:#ff5b5b} .警{color:#f5c542}
"""

页 = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>影匠控制台</title><style>__CSS__</style></head><body>
<div class="顶"><h1>影匠控制台</h1>
  <span class="小">戏</span>
  <select id="戏">__戏选项__</select>
  <span id="端点灯"></span>
  <span style="flex:1"></span>
  <span class="小" id="刷新时"></span>
</div>
<div class="壳">
  <div class="排">
    <div class="卡"><h2>本机</h2><div id="本机"></div></div>
    <div class="卡"><h2>远端（主力算力）</h2><div id="远端"></div></div>
  </div>

  <div class="卡"><h2>正在跑</h2><div id="在跑"></div></div>

  <!-- ★ 用户 2026-10-15 08:44：「我看不出来你这个控制台和我说的有什么很大的关联，
       好像差别挺大的呀。」—— 对。以前这里只有旧片子的后期三步，**不能新建一部戏**。
       现在把 剧组.py 的阶段门整段搬上来：一部戏卡在哪、下一步该干什么、按哪个钮往下推。 -->
  <div class="卡"><h2>剧组流水线 —— 这部戏卡在哪、下一步干什么</h2>
    <div class="小">下面每一个钮，按的就是 <code>python 剧组.py …</code> 本身（不另写实现）。
      灯的意思是：<span class="吉">✓ 过审了</span> ·
      <span style="color:#e5534b">✗ 审过没过</span> ·
      <span class="小">— 还没审</span></div>
    <div class="行">
      <select id="jc戏" onchange="jc画()"></select>
      <span class="钮" onclick="jc刷()">重新扫</span>
      <label class="小"><input type="checkbox" id="jc空跑"> 空跑（只解析、不渲染）</label>
      <label class="小"><input type="checkbox" id="jc强跑"> 强跑（无视卡门硬闯）</label>
      <span class="小" id="jc错"></span>
    </div>
    <div id="jc门" class="行"></div>
    <div class="行" id="jc下"></div>
    <div class="行" id="jc钮"></div>
  </div>

  <div class="卡"><h2>新建一部戏</h2>
    <div class="小">写一句话就行 —— 建目录、写 <code>剧本.md</code> 都由这儿开个头。
      已经有的戏**不会被动**（要改直接改文件）。</div>
    <div class="行">
      <input id="np名" placeholder="戏名，如 雪线前传" style="width:200px">
      <input id="np话" placeholder="一句话故事，如 守了十年雪线的刀客，发现要杀的人是自己" style="width:560px">
      <button class="钮 主" onclick="np建()">建戏 + 写剧本</button>
      <span class="小" id="np说"></span>
    </div>
  </div>

  <!-- ★ 用户 2026-10-15 任务单 ⑤：「能调 ComfyUI 官方 API 也能让 agent 接管」。
       他说过四次「要能自己操作，只读页面不算」—— 所以下面这些是**真的能按**的，
       走的是 ComfyUI 自己的 HTTP 接口，不碰它的内部状态文件。 -->
  <div class="卡"><h2>ComfyUI 官方接口（本机 / 远端都能调）</h2>
    <div class="行">
      <span class="小">调哪台</span>
      <select id="cf机"><option>本机</option><option>远端</option></select>
      <button class="钮" onclick="cf读('queue')">队列明细</button>
      <button class="钮" onclick="cf读('history')">最近跑完的</button>
      <button class="钮" onclick="cf读('system_stats')">系统信息</button>
      <button class="钮" onclick="cf读('object_info')">节点表</button>
      <span style="flex:1"></span>
      <button class="钮 危" onclick="cf做('打断')">打断</button>
      <button class="钮 危" onclick="cf做('清待办')">清等待队列</button>
    </div>
    <div class="小" id="cf说"></div>
    <div id="cf果" style="max-height:340px;overflow:auto"></div>
  </div>

  <div class="卡"><h2>这件事让 agent 接管</h2>
    <div class="小">软件不开 agent 的后门 —— 它只负责把话说到纸上（<code>_等Agent.md</code>），
      我下次开工就会看到，你不用再复述一遍。</div>
    <div class="行"><input id="ag事" placeholder="什么事（如：这条片子越看越不对）" style="width:300px">
      <input id="ag为" placeholder="为什么难 / 卡在哪" style="width:300px"></div>
    <div class="行"><input id="ag要" placeholder="要 agent 做什么" style="width:520px">
      <button class="钮 主" onclick="ag交()">交给 agent</button>
      <span class="小" id="ag说"></span></div>
    <div id="ag单" class="小"></div>
  </div>

  <div class="卡"><h2>起一个活</h2>
    <div class="行">
      <select id="任务">__任务选项__</select>
      <input id="格" placeholder="只跑哪几格，如 12,13,56（留空=全部）" style="width:280px">
      <button class="钮 主" onclick="起()">开始</button>
      <span class="小" id="起错"></span>
    </div>
    <div class="行" id="直调行" style="display:none">
      <span class="吉">★ 软件内部直调</span>
      <span class="小">这条活<b>不起 python 脚本、不建子进程</b> ——
        控制台直接跟 ComfyUI 说话，进度实时回这儿。</span>
    </div>
    <div class="行" id="片行" style="display:none">
      <span class="小">超分哪一条</span>
      <select id="片" style="min-width:520px"></select>
      <span class="小" id="片说"></span>
    </div>
    <div class="小" id="任说"></div>
  </div>

  <div class="卡" id="看片卡"><h2>这一部戏 —— 人物 · 台词 · 逐格（点开就能看）</h2>
    <div class="行" id="看片头"></div>
    <div id="看片身"></div>
  </div>

  <div class="卡"><h2>进度</h2><div id="进度"></div></div>
  <div class="卡"><h2>成片</h2><div id="成片"></div></div>
</div>
<script>
let 戏 = new URLSearchParams(location.search).get('戏') || '__戏__';
const $ = (i) => document.getElementById(i);
$('戏').value = 戏;
$('戏').onchange = () => { 戏 = $('戏').value;
  history.replaceState(null,'','/?戏='+encodeURIComponent(戏)); 刷(); };

function 条(用, 总){
  const p = 总 ? Math.min(100, 用/总*100) : 0;
  return '<div class="条"><i style="width:'+p+'%"></i></div>';
}
function 机(d, 是远){
  if(!d.活) return '<div class="机"><span class="灯 红"></span><b>'+(是远?'远端':'本机')+'连不上</b></div>'
    + '<div class="小">'+((d.错||'')).replace(/</g,'&lt;')+'</div>';
  let h = '<div class="机"><span class="灯 绿"></span><b>在线</b>'
    + (d.温!=null ? '<span class="小">显卡 '+d.温+'°C '+(d.温>=80?'<span class="凶">（到 80 该歇了）</span>':'')+'</span>' : '')
    + '</div>';
  // ★ 本机 ComfyUI 没起的时候必须说清楚 —— 不然按「开始」只会得到一个莫名的失败。
  if(d.Comfy活 === false){
    h += '<div class="机"><span class="灯 红"></span><b class="凶">本机 ComfyUI 没在跑</b>'
       + '<span style="flex:1"></span>'
       + '<button class="钮 主" onclick="起Comfy()">启动本机 ComfyUI</button></div>'
       + '<div class="小">端口 '+d.Comfy口+' 连不上。出首帧、本机出段都要它。</div>';
  }
  h += '<div class="数">';
  if(d.温!=null) h += '<div><span>显卡温度</span><b class="'+(d.温>=80?'凶':'')+'">'+d.温+'<small>°C</small></b></div>';
  if(d.用!=null) h += '<div><span>显卡占用</span><b>'+d.用+'<small>%</small></b></div>';
  if(d.瓦!=null) h += '<div><span>功耗</span><b>'+d.瓦+'<small>W</small></b></div>';
  if(d.显存总) h += '<div><span>显存</span><b>'+(d.显存用/1024).toFixed(1)+'<small>/'+(d.显存总/1024).toFixed(1)+'G</small></b></div>';
  // ★ 这里两个面板的数字来源不一样，必须分开算 —— 2026-10-15 08:45 实测：
  //   远端那台给我的是 `内存用率`（已经是百分数 56），本机给的是 `内存总/内存闲`。
  //   写成 `(1-闲/总).toFixed(0)` 少了 ×100，**本机永远显示 0%**（实际 34%）。
  //   屏幕上写着一个错的数，比不写更坏 —— 他会照这个数判断「机器还空不空」。
  if(d.内存用率!=null) h += '<div><span>内存</span><b>'+d.内存用率+'<small>%</small></b></div>';
  else if(d.内存总) h += '<div><span>内存</span><b>'+Math.round((1-d.内存闲/d.内存总)*100)+'<small>% 用 · 剩 '+Math.round(d.内存闲/2**30)+'G</small></b></div>';
  if(d.队列跑!=null) h += '<div><span>ComfyUI 队列</span><b>'+d.队列跑+'<small>跑 '+d.队列等+' 等</small></b></div>';
  if(d.E总) h += '<div><span>E 盘剩</span><b>'+Math.round(d.E剩/2**30)+'<small>G</small></b></div>';
  h += '</div>';
  if(d.显存总) h += 条(d.显存用, d.显存总);
  if(d.内存总) h += 条(d.内存总-d.内存闲, d.内存总);
  return h;
}
function 起Comfy(){
  fetch('/api/comfyup', {method:'POST'}).then(r=>r.json()).then(j=>{
    alert(j.ok ? j.说 : ('✗ ' + j.错));
    setTimeout(刷, 3000);
  });
}
function 起(){
  const 格 = $('格').value.trim();
  const 片 = ($('片行').style.display === 'none') ? '' : ($('片').value || '');
  $('起错').textContent = '';
  if(($('任务').value||'').indexOf('超分') >= 0 && !片){
    $('起错').textContent = '✗ 先挑一条片子'; return;
  }
  fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({任务:$('任务').value, 戏:戏, 格:格, 片:片})})
   .then(r=>r.json()).then(j=>{ if(!j.ok) $('起错').textContent = '✗ ' + j.错; 刷(); });
}
function 停(){ fetch('/api/stop',{method:'POST'}).then(()=>setTimeout(刷,600)); }

// ── 剧组流水线 ────────────────────────────────────────────────────
// ★ 数据全部来自 /api/juchu —— 后端把 剧组.py 的 扫状态()/判断下一步() 整段搬过来，
//   页面上**不自己算「下一步是什么」**。两处各算一份，早晚会分叉，
//   到时候页面上说的和命令行做的不是一回事，比没有还坏。
let jc数据 = [], jc满 = false;
function jc刷(){
  fetch('/api/juchu').then(r=>r.json()).then(j=>{
    if(!j.ok){ $('jc错').innerHTML = '<span class="凶">✗ '+(j.错||'').replace(/</g,'&lt;')+'</span>'; return; }
    $('jc错').textContent = '';
    jc数据 = j.戏们 || [];
    const 选 = $('jc戏'), 旧 = 选.value;
    if(!jc满){
      选.innerHTML = jc数据.map(x=>'<option>'+x.戏+'</option>').join('');
      jc满 = true;
      if(旧) 选.value = 旧;
    }
    jc画();
  }).catch(e=>{ $('jc错').innerHTML = '<span class="凶">✗ '+e+'</span>'; });
}
function jc画(){
  const x = jc数据.find(y=>y.戏 === $('jc戏').value);
  if(!x){ $('jc门').innerHTML=''; $('jc下').textContent=''; $('jc钮').innerHTML=''; return; }
  if(x.错){ $('jc门').innerHTML = '<span class="凶">✗ '+x.错+'</span>'; return; }
  $('jc门').innerHTML = x.门.map(g=>{
    const 色 = g.过 ? '吉' : (g.结果==='FAIL' ? '凶' : '小');
    const 记 = g.过 ? '✓' : (g.结果==='FAIL' ? '✗' : '—');
    return '<span class="'+色+'" style="margin-right:14px">'+记+' '+g.名+'</span>';
  }).join('');
  let 数 = '';
  if(x.格数) 数 += '　九宫格图 '+x.图数+'/'+x.格数;
  if(x.四格数) 数 += '　四宫格图 '+x.四图数+'/'+x.四格数;
  if(x.动格数) 数 += '　片 '+x.片数+'/'+x.动格数;
  $('jc下').innerHTML = '<span class="小">现在该干：</span> '+(x.下一步||'')+'<span class="小">'+数+'</span>';
  const 钮 = ['检查','出图','出图四宫格','出片','拼图','进度','全部'];
  $('jc钮').innerHTML = 钮.map(名=>
    '<button class="钮'+(名==='全部'?' 主':'')+'" onclick="jc推(\''+名+'\')">'+名+'</button>'
  ).join('');
}
function jc推(名){
  $('jc错').textContent = '正在起：剧组·' + 名 + ' …';
  fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({任务:'剧组·'+名, 戏:$('jc戏').value,
      空跑:$('jc空跑').checked, 强跑:$('jc强跑').checked})})
   .then(r=>r.json()).then(j=>{
     if(!j.ok){ $('jc错').innerHTML = '<span class="凶">✗ '+j.错+'</span>'; return; }
     $('jc错').textContent = '✓ 起来了：剧组·' + 名; 刷();
   });
}
function np建(){
  const 名 = $('np名').value.trim(), 话 = $('np话').value.trim();
  $('np说').textContent = '';
  if(!名 || !话){ $('np说').innerHTML = '<span class="凶">✗ 戏名和一句话故事都要填</span>'; return; }
  fetch('/api/newplay', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({戏:名, 一句话:话})})
   .then(r=>r.json()).then(j=>{
     if(!j.ok){ $('np说').innerHTML = '<span class="凶">✗ '+j.错+'</span>'; return; }
     $('np说').innerHTML = '<span class="吉">✓ '+j.说+'</span><br><span class="小">'+j.剧本+'</span>';
     jc满 = false; jc刷(); 刷();
   });
}

// ── ComfyUI 官方接口 ──────────────────────────────────────────────
// ★ 只读面走 GET /api/comfy，写面走 POST。**全部转发给 ComfyUI 自己**，
//   这里不做任何「猜」或「代替」—— 它回什么就显示什么，包括错误。
function cf读(面){
  const 机 = $('cf机').value;
  $('cf说').textContent = '正在问 ' + 机 + ' 的 /' + 面 + ' …';
  fetch('/api/comfy?机='+encodeURIComponent(机)+'&面='+encodeURIComponent(面))
   .then(r=>r.json()).then(j=>{
     if(!j.活){ $('cf说').innerHTML = '<span class="凶">✗ '+((j.错||'连不上')).replace(/</g,'&lt;')+'</span>';
                $('cf果').innerHTML = ''; return; }
     let 概 = '';
     if(面==='queue'){
       const 跑 = (j.数据.queue_running||[]).length, 等 = (j.数据.queue_pending||[]).length;
       概 = '正在跑 '+跑+' 个，等着 '+等+' 个';
     } else if(面==='history'){
       概 = j.说 || (Object.keys(j.数据||{}).length + ' 条记录');
     } else if(面==='system_stats'){
       const d = (j.数据.system||{}), 显 = (j.数据.devices||[])[0]||{};
       概 = (d.comfyui_version?('ComfyUI '+d.comfyui_version+'　'):'')
          + (显.name?('显卡 '+显.name+'　'):'')
          + (显.vram_total?('显存 '+Math.round(显.vram_total/2**30)+'G'):'');
     } else if(面==='object_info'){
       概 = j.说 || (Object.keys(j.数据||{}).length + ' 种节点');
     }
     $('cf说').textContent = 机 + ' /' + 面 + '　' + 概;
     const 给 = j.裁过 ? (j.节点名 || j.最近 || j) : j.数据;
     $('cf果').innerHTML = '<pre style="max-height:320px">'
       + JSON.stringify(给, null, 1).replace(/</g,'&lt;').slice(0, 20000) + '</pre>';
   }).catch(e=>{ $('cf说').innerHTML = '<span class="凶">✗ '+e+'</span>'; });
}
function cf做(动作){
  const 机 = $('cf机').value;
  if(!confirm(机 + '：' + 动作 + '？')) return;
  fetch('/api/comfy',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({机:机, 动作:动作})})
   .then(r=>r.json()).then(j=>{
     $('cf说').innerHTML = j.ok ? ('<span class="吉">✓ '+j.说+'</span>')
                                : ('<span class="凶">✗ '+((j.错||'')).replace(/</g,'&lt;')+'</span>');
     setTimeout(()=>cf读('queue'), 800); 刷();
   });
}
function ag交(){
  const 事 = $('ag事').value.trim(), 为 = $('ag为').value.trim(), 要 = $('ag要').value.trim();
  if(!事){ $('ag说').textContent = '✗ 先说是什么事'; return; }
  fetch('/api/接管',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({事:事, 为什么:为, 要:要})})
   .then(r=>r.json()).then(j=>{
     $('ag说').innerHTML = j.ok ? '<span class="吉">✓ '+j.说+'</span>'
                                : '<span class="凶">✗ '+j.错+'</span>';
     if(j.ok){ $('ag事').value=''; $('ag为').value=''; $('ag要').value=''; }
     ag刷();
   });
}
function ag刷(){
  fetch('/api/接管').then(r=>r.json()).then(j=>{
    const 行 = j.行||[];
    $('ag单').innerHTML = 行.length
      ? ('已经交给 agent 的 '+行.length+' 件：<br>' + 行.map(x =>
          '· <b>'+x[1]+'</b>　<span class="小">'+x[0]+'　'+x[4]+'</span>').join('<br>'))
      : '还没有交给 agent 的事。';
  }).catch(()=>{});
}

async function 刷(){
  let d;
  try { d = await (await fetch('/api/state?戏='+encodeURIComponent(戏))).json(); }
  catch(e){ return; }
  $('本机').innerHTML = 机(d.本机, false);
  $('远端').innerHTML = 机(d.远端, true);
  $('端点灯').innerHTML = (d.本机.活&&d.远端.活)
    ? '<span class="灯 绿"></span> <span class="小">两端都在</span>'
    : '<span class="灯" style="background:#f5c542"></span> <span class="小">有一端不通</span>';

  const p = d.在跑;
  if(p){
    // ★ 进度条：一格 = 一个镜头。用户关心的是「还差几格、还要几分钟」，
    //   不是 ComfyUI 那种「8 步里的第 3 步」。数字全从日志的 `[i/N] ✓ … 秒`
    //   里抠出来（服务端 `读格进度`），所以它跟日志永远对得上。
    let 条 = '';
    if(p.格总 > 0){
      const 完 = p.格完||0, 百 = Math.round(100*完/p.格总);
      const 剩 = p.预计剩秒;
      const 剩文 = (剩===null||剩===undefined) ? '还算不出还要多久'
                 : (剩<=0 ? '收尾了' : '预计还要 '+Math.floor(剩/60)+' 分 '+(剩%60)+' 秒');
      条 = '<div style="display:flex;align-items:center;gap:10px;margin:8px 0 4px">'
         + '<span class="小" style="white-space:nowrap">格 '+完+' / '+p.格总+'</span>'
         + '<div style="flex:1;height:8px;background:#1b2230;border-radius:5px;overflow:hidden">'
         + '<div style="width:'+百+'%;height:100%;background:linear-gradient(90deg,#3ddc84,#f5c542);transition:width .4s"></div>'
         + '</div>'
         + '<span class="小" style="white-space:nowrap">'+百+'%　'+剩文+'</span></div>';
    }
    $('在跑').innerHTML =
      '<div class="机"><span class="灯 '+(p.在跑?'绿':'灰')+'"></span><b>'+p.名+'</b>'
      + '<span class="tag">'+p.脚本+' '+p.参数.join(' ')+'</span>'
      + '<span class="小">起于 '+p.起+' · 已跑 '+Math.floor(p.跑秒/60)+' 分 '+(p.跑秒%60)+' 秒</span>'
      + '<span style="flex:1"></span>'
      + '<button class="钮 危" onclick="停()" '+(p.在跑?'':'disabled')+'>停</button></div>'
      + 条
      + '<pre>'+p.行.join('\\n').replace(/</g,'&lt;')+'</pre>';
  } else {
    $('在跑').innerHTML = '<div class="小">现在没有活。挑一个按「开始」。</div>';
  }

  const g = d.进度 || {};
  $('进度').innerHTML = '<div class="数">'
    + '<div><span>首帧</span><b>'+(g.首帧||0)+'</b></div>'
    + '<div><span>段·本机</span><b>'+(g.段本机||0)+'</b></div>'
    + '<div><span>段·远端</span><b>'+(g.段远端||0)+'</b></div>'
    + '<div><span>段齐（两条线都有）</span><b>'+(g.段齐||0)+'</b></div>'
    + '<div><span>配音</span><b>'+(g.配音||0)+'</b></div>'
    + '<div><span>成片</span><b>'+(g.片总||0)+'</b></div></div>';

  $('成片').innerHTML = (g.片&&g.片.length)
    ? '<div class="小" style="margin-bottom:8px">共 '+(g.片总||g.片.length)+' 个，这里是最新的 '
      + g.片.length + ' 个：</div><div class="片">' + g.片.map(f =>
        '<a href="/f?p='+encodeURIComponent('作品/'+戏+'/片/'+f.名)+'" target="_blank">'
        + f.名 + '<span class="小" style="display:block">' + f.mb + ' MB · ' + f.改 + '</span></a>').join('') + '</div>'
    : '<div class="小">还没有成片。</div>';

  $('任说').textContent = d.任说 || '';
  $('刷新时').textContent = '刷新于 ' + new Date().toLocaleTimeString('zh-CN');
}
ag刷();
$('任务').onchange = () => {
  $('任说').textContent = ''; $('起错').textContent = '';
  看任务(); 刷();
};
function 看任务(){
  const 任 = $('任务').value || '';
  const 是超分 = 任.indexOf('超分') >= 0;
  const 是直调 = 任.indexOf('直调') >= 0;
  $('片行').style.display = 是超分 ? '' : 'none';
  $('直调行').style.display = 是直调 ? '' : 'none';
  if(是超分) 拉片单();
}
function 拉片单(){
  fetch('/api/clips?戏=' + encodeURIComponent(戏)).then(r=>r.json()).then(j=>{
    const s = $('片');
    if(!j.片 || !j.片.length){ s.innerHTML = '<option value="">（作品目录里没有 mp4）</option>'; return; }
    s.innerHTML = j.片.map(p =>
      '<option value="'+p.路.replace(/"/g,'&quot;')+'">'+p.名+'　'+(p.大小/1048576).toFixed(1)+' MB</option>'
    ).join('');
    $('片说').textContent = j.片.length + ' 条可选';
  }).catch(e => { $('片说').textContent = '拉片单失败：' + e; });
}
// ── 看片：他的那一半 ─────────────────────────────────────────────
// 用户 2026-10-15 08:55：「这个控台我能自己看到里面的剧本，能看到里面的台词，
// 看到里面的两个人物形象……我现在只能看到你所生成的进度，这叫这对吗？」
// → 所以这一块**不显示任何我自己的进度数**，只放片子本身。
let 看片数据 = null, 看片签 = '人物形象';
function 换签(s){ 看片签 = s; 画看片(); }

function 拉看片(){
  fetch('/api/kanban?戏=' + encodeURIComponent(戏)).then(r=>r.json()).then(j=>{
    看片数据 = j;
    if(j.错){ $('看片身').innerHTML = '<div class="小 凶">读不出这一部戏：' + j.错 + '</div>'; return; }
    画看片();
  }).catch(e => { $('看片身').innerHTML = '<div class="小 凶">拉不到：' + e + '</div>'; });
}

function 画看片(){
  const j = 看片数据;
  if(!j) return;
  const esc = s => (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;');
  const f = p => '/f?p=' + encodeURIComponent(p);

  // 头一行：这一部戏的概览 + 整部剧本的入口
  let 头 = '<span class="小">《' + esc(j.戏) + '》　' + j.格数 + ' 格 · '
    + (j.秒/60).toFixed(1) + ' 分钟 · ' + j.有词的格 + ' 格有台词 · 人物 '
    + (j.人物||[]).length + ' 个</span><span style="flex:1"></span>';
  if(j.剧本页) 头 += '<a class="钮 主" href="' + f(j.剧本页) + '" target="_blank">读整部剧本 →</a>';
  $('看片头').innerHTML = 头;

  const 签们 = [
    ['人物形象', (j.人物||[]).length + ' 个'],
    ['台词', (j.格||[]).filter(g=>g.词&&g.词.length).length + ' 格'],
    ['逐格', j.格数 + ' 格'],
    ['成片', (j.成片||[]).length + ' 个']
  ];
  let h = '<div class="看片签">' + 签们.map(([n,c]) =>
    '<span class="签' + (看片签===n?' 亮':'') + '" onclick="换签(\\'' + n + '\\')">'
    + n + ' <span class="小">' + c + '</span></span>').join('') + '</div>';

  if(看片签 === '人物形象'){
    h += (j.人物&&j.人物.length)
      ? '<div class="人脸" style="margin-top:12px">' + j.人物.map(p =>
          '<figure><img src="' + f(p.图) + '" loading="lazy" alt="' + esc(p.名) + '">'
          + '<figcaption>' + esc(p.名) + '</figcaption>'
          + '<div class="脸签">定妆照 · 正面半身 + 正面全身</div></figure>').join('') + '</div>'
      : '<div class="小" style="margin-top:10px">这一部戏还没有定妆照。</div>';
  }

  if(看片签 === '台词'){
    const 有词 = (j.格||[]).filter(g => g.词 && g.词.length);
    h += 有词.length
      ? '<div class="小" style="margin:10px 0 6px">来源：' + esc(j.台词来源) + '　顶上那一行是它在片子里的时刻</div>'
        + '<table class="台词表">' + 有词.map(g =>
            g.词.map((w,i) => '<tr>'
              + '<td class="t">' + (i===0 ? g.时刻 : '') + '</td>'
              + '<td class="w">' + (i===0 ? '格' + g.号 : '') + '</td>'
              + '<td class="w">' + esc(w[0]||'旁白') + '</td>'
              + '<td>' + esc(w[1]) + '</td></tr>').join('')).join('') + '</table>'
      : '<div class="小" style="margin-top:10px">这一部戏没有台词。</div>';
  }

  if(看片签 === '逐格'){
    h += '<div class="小" style="margin-top:10px">每一格就是镜头里的一个画面。'
       + '<b>带绿点的是已经出好片子了的</b> —— 点一下就在下面放。</div>'
       + '<div class="格墙">' + (j.格||[]).map(g => {
          const 有片 = g.片 && g.片.length;
          const 词 = (g.词&&g.词.length)
            ? '<div class="ci">' + g.词.map(w => esc((w[0]?w[0]+'：':'') + w[1])).join('<br>') + '</div>' : '';
          return '<div class="格块' + (有片?' 有片':'') + '" onclick="'
            + (有片 ? '放格(\\'' + encodeURIComponent(g.片[0].路) + '\\',\\'格' + g.号 + ' ' + esc(g.题).replace(/'/g,'') + '\\')' : '')
            + '"><div class="n">格' + g.号 + '　' + g.时刻 + '</div>'
            + '<div class="ti">' + esc(g.题) + '</div>'
            + '<div class="ju">' + esc(g.景别) + '</div>' + 词 + '</div>';
        }).join('') + '</div>'
       + '<div id="格播" style="margin-top:14px"></div>';
  }

  if(看片签 === '成片'){
    h += (j.成片&&j.成片.length)
      ? '<div style="margin-top:12px"><video class="片框" controls preload="metadata" src="'
        + f(j.成片[0].路) + '"></video>'
        + '<div class="小" style="margin-top:6px">' + esc(j.成片[0].名) + '　'
        + (j.成片[0].大小/1048576).toFixed(1) + ' MB　（这是最新的一条）</div>'
        + '<div class="看片签">' + j.成片.map((x,i) =>
            '<a class="签' + (i===0?' 亮':'') + '" href="' + f(x.路) + '" target="_blank">'
            + esc(x.名) + '</a>').join('') + '</div></div>'
      : '<div class="小" style="margin-top:10px">还没有成片。</div>';
  }

  $('看片身').innerHTML = h;
}

function 放格(路, 名){
  $('格播').innerHTML = '<div class="小" style="margin-bottom:6px">' + 名 + '　'
    + '<a href="/f?p=' + 路 + '" target="_blank">单独开一页</a></div>'
    + '<video class="片框" controls autoplay preload="metadata" src="/f?p=' + 路 + '"></video>';
  $('格播').scrollIntoView({behavior:'smooth', block:'nearest'});
}

拉看片();

// 支持 ?任=超分 直接选好某个任务（也方便我自己截图核对页面）
const 想任 = new URLSearchParams(location.search).get('任');
if(想任){ for(const o of $('任务').options){ if(o.value === 想任){ $('任务').value = 想任; break; } } }
刷(); setInterval(刷, 4000); 看任务();
</script></body></html>
"""


def 渲():
    戏 = 现在.get("戏") or (列戏() or ["觉醒"])[0]
    opts = "".join(f'<option value="{d}"{" selected" if d == 戏 else ""}>{d}</option>' for d in 列戏())
    任 = "".join(f'<option value="{k}">{k}</option>' for k in 任务表)
    # ★ 这里不能用 % 拼字符串 —— 页面的 CSS/JS 里全是 `width:50%` 这种字面百分号，
    #   `页 % (...)` 会直接 TypeError: not enough arguments for format string。
    #   改用具名占位符替换（2026-10-15 02:55 踩的坑）。
    return (页.replace("__CSS__", CSS)
             .replace("__戏选项__", opts)
             .replace("__任务选项__", 任)
             .replace("__戏__", 戏))


# ═════════════════════════ 五、HTTP ═════════════════════════

class 手(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _发(self, 码, 体, 型="text/html; charset=utf-8"):
        if isinstance(体, str):
            体 = 体.encode("utf-8")
        self.send_response(码)
        self.send_header("Content-Type", 型)
        self.send_header("Content-Length", str(len(体)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(体)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _JSON(self, o, 码=200):
        self._发(码, json.dumps(o, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)

        if u.path == "/":
            self._发(200, 渲())
            return

        # ★ 路由名一律用 ASCII。中文路由经 PowerShell / curl / fetch 一转就会变成
        #   percent-encoded 或 GBK 字节，服务端收到时已经不是同一个字符串了
        #   （实测 `?戏=觉醒` 从 PowerShell 打过来直接 404）。参数值可以带中文。
        if u.path == "/api/state":
            戏 = (q.get("戏") or ["觉醒"])[0]
            现在["戏"] = 戏
            with 现在锁:
                p = 现在["活"].快照() if 现在["活"] else None
            本机 = {"活": True, "内存总": None, "内存闲": None, "队列跑": None, "队列等": None}
            m = 取内存()
            本机.update({"内存总": m["总"], "内存闲": m["闲"]})
            g = 取本机显卡()
            if g:
                本机.update({"温": g["温"], "用": g["用"], "显存用": g["显存用"],
                             "显存总": g["显存总"], "瓦": g["瓦"]})
            qq = 取队列("127.0.0.1:8188", 超时=2)
            本机.update({"队列跑": qq["跑"], "队列等": qq["等"], "Comfy活": qq["活"]})
            本机["Comfy口"] = 本机Comfy["口"]
            try:
                pr = 扫进度(戏)
            except Exception as e:
                pr = {"错": f"{type(e).__name__}: {e}"}
            self._JSON({"本机": 本机, "远端": 取远端(), "在跑": p, "进度": pr,
                        "任说": 任务表.get((q.get("任务") or [""])[0], {}).get("说", "")})
            return

        if u.path == "/api/clips":
            戏 = (q.get("戏") or [""])[0]
            return self._JSON({"片": 片单(戏)})

        # ★ 剧组：每一部戏卡在哪、现在该干什么。整段搬 剧组.py，不写第二份实现。
        if u.path == "/api/juchu":
            try:
                return self._JSON(剧组一览())
            except Exception as e:
                return self._JSON({"ok": False, "错": f"{type(e).__name__}: {e}"})

        # ComfyUI 官方接口的只读面：`/api/comfy?machine=本机&face=queue`
        # ★ 查询串的**键名**必须是 ASCII（值可以带中文）—— 2026-10-15 08:20 实测：
        #   键名写成 `机=` / `面=` 时，Python 客户端拼 URL 直接
        #   `UnicodeEncodeError: 'ascii' codec can't encode character '\u673a'`；
        #   PowerShell 那边则是把中文转成别的字节，服务端收到已经不是同一个键。
        #   跟第 1226 行那条注释是同一个病：**路由和参数名一律 ASCII，中文只放进值里**。
        #   为兼容起见，中文键仍然认。
        if u.path == "/api/comfy":
            return self._JSON(Comfy取((q.get("machine") or q.get("机") or ["本机"])[0],
                                      (q.get("face") or q.get("面") or ["queue"])[0]))

        if u.path in ("/api/handoff", "/api/接管"):
            return self._JSON({"行": 接管读()})

        # ★ 给他的那一半：人物形象 / 台词 / 逐格。
        #   路由名 ASCII，戏名走参数值（中文可以）—— 理由见上面 1226 行那段。
        if u.path == "/api/kanban":
            戏 = (q.get("戏") or q.get("x") or ["觉醒"])[0]
            try:
                return self._JSON(看片.一部(戏))
            except Exception as e:
                return self._JSON({"错": f"{type(e).__name__}: {e}", "戏": 戏,
                                   "人物": [], "格": [], "成片": [], "剧本页": ""})

        if u.path == "/f":
            相 = (q.get("p") or [""])[0]
            if not 相:
                self._发(400, b"no p")
                return
            绝 = os.path.realpath(os.path.join(根, 相))
            if not 绝.startswith(os.path.realpath(根) + os.sep) or \
                    os.path.splitext(绝)[1].lower() not in 允许后缀 or not os.path.isfile(绝):
                self._发(403, b"forbidden")
                return
            型 = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                  ".webp": "image/webp", ".gif": "image/gif", ".mp4": "video/mp4"}[
                os.path.splitext(绝)[1].lower()]
            self.send_response(200)
            self.send_header("Content-Type", 型)
            self.send_header("Content-Length", str(os.path.getsize(绝)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                with open(绝, "rb") as f:
                    shutil.copyfileobj(f, self.wfile, 1 << 20)
            except (BrokenPipeError, ConnectionAbortedError):
                pass
            return

        self._发(404, b"not found")

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            体 = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            体 = {}

        if u.path == "/api/stop":
            with 现在锁:
                if 现在["活"] and 现在["活"].还活着():
                    现在["活"].停()
                    return self._JSON({"ok": True, "说": "已发停止信号"})
            return self._JSON({"ok": False, "错": "没有在跑的活"})

        if u.path == "/api/comfyup":
            return self._JSON(起本机Comfy())

        # ComfyUI 官方接口的写面：打断 / 清待办 / 删项 / 送任务
        # ★ 键名同样收 ASCII 和中文两套（理由见 do_GET 里那段注释）
        if u.path == "/api/comfy":
            return self._JSON(Comfy做(体.get("machine") or 体.get("机") or "本机",
                                      体.get("action") or 体.get("动作") or "", 体))

        # 让 agent 接管：软件只负责把话说到纸上
        if u.path in ("/api/handoff", "/api/接管"):
            return self._JSON(接管加((体.get("what") or 体.get("事") or "").strip(),
                                    (体.get("why") or 体.get("为什么") or "").strip(),
                                    (体.get("want") or 体.get("要") or "").strip()))

        # ★ 新建一部戏：建目录 + 写 剧本.md 骨架。已存在就不动它。
        if u.path in ("/api/newplay", "/api/新建戏"):
            return self._JSON(新建戏((体.get("戏") or "").strip(),
                                    (体.get("一句话") or 体.get("story") or "").strip()))

        if u.path == "/api/run":
            名 = 体.get("任务") or ""
            戏 = 体.get("戏") or ""
            格 = (体.get("格") or "").strip()
            片 = (体.get("片") or "").strip()
            if 名 not in 任务表:
                return self._JSON({"ok": False, "错": f"没有这个任务：{名}"})
            if not _戏目录(戏):
                return self._JSON({"ok": False, "错": f"作品目录里没有《{戏}》"})
            格s = _格(格)
            if 格s is None:
                return self._JSON({"ok": False, "错": "格号只能是数字和逗号，如 12,13,56"})
            # ★ 片必须是作品目录里真实存在的文件 —— 不接受任意路径
            if 片 and not _真片(片):
                return self._JSON({"ok": False, "错": f"这个片不在作品目录里：{片}"})
            with 现在锁:
                if 现在["活"] and 现在["活"].还活着():
                    return self._JSON({"ok": False,
                                       "错": f"已经在跑「{现在['活'].名}」，先停它"})
                t = 任务表[名]
                # ★ 剧组那几条多两个开关：--空跑（只解析不渲染）/ --强跑（无视卡门硬闯）
                #   它们拼进命令行，所以只接受 True/False，不接受任意字符串。
                闸 = []
                if t.get("剧组"):
                    if 体.get("空跑"):
                        闸.append("--空跑")
                    if 体.get("强跑"):
                        闸.append("--强跑")
                o = {"戏": 戏, "格": 格s, "片": 片, "倍数": 体.get("倍数"),
                     "重做": bool(体.get("重做")), "强跑": bool(体.get("强跑")), "闸": 闸}
                try:
                    if t.get("类") == "直调":
                        # ★ 不建子进程、不拼命令行 —— 就在控制台这个进程里把活干完
                        现在["活"] = 直调活(名, lambda 吐: t["干"](o, 吐), t.get("说", ""))
                    else:
                        脚本 = os.path.join(根, t["脚本"])
                        if not os.path.isfile(脚本):
                            return self._JSON({"ok": False, "错": f"脚本不在：{t['脚本']}"})
                        if not 本机Python:
                            # ★ 打包成 exe 之后，exe 自己不能当解释器用；
                            #   找不到真的 python.exe 就得说清楚，不能让用户
                            #   按了「开始」只看到一个莫名的失败。
                            return self._JSON({"ok": False,
                                "错": "这条活要另起一个 python 脚本来跑，但这台机器上没找到 "
                                      "python.exe。改用名字里带「直调」的活 —— 那些在当前"
                                      "进程里直接跑，不需要解释器。"})
                        现在["活"] = 活(名, 脚本, t["参"](o))
                except Exception as e:
                    return self._JSON({"ok": False, "错": f"{type(e).__name__}: {e}"})
            return self._JSON({"ok": True, "说": f"起了「{名}」"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--口", type=int, default=8791)
    ap.add_argument("--不开", action="store_true")
    参 = ap.parse_args()

    戏目 = 列戏()
    if not 戏目:
        print(f"  ✗ 作品\\ 下没有戏　（根 = {根}）")
        print(f"    打包成 exe 之后，exe 必须摆在 `作品\\` 的同一个目录里。")
        return 1

    # ★ 开工自查：任务表里写的脚本到底在不在（详见 查任务表 的注释）
    毛病 = 查任务表()
    if 毛病:
        print("  ✗ 任务表有问题，这些活按了「开始」也是坏的：")
        for m in 毛病:
            print(f"      · {m}")
        return 1

    srv = ThreadingHTTPServer(("127.0.0.1", 参.口), 手)
    址 = f"http://127.0.0.1:{参.口}/"
    print(f"  影匠控制台 → {址}")
    print(f"  根：{根}{'　（打包运行）' if 打包了 else ''}")
    print(f"  戏：{'、'.join(戏目)}")
    print(f"  能起的活：{'、'.join(任务表)}")
    print(f"  另起脚本用的解释器：{本机Python or '（没找到 —— 只有「直调」那一类活能用）'}")
    print(f"  Ctrl+C 停")
    if not 参.不开:
        def 开():
            time.sleep(0.6)
            try:
                os.startfile(址)
            except Exception:
                pass
        threading.Thread(target=开, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        with 现在锁:
            if 现在["活"] and 现在["活"].还活着():
                print("  停掉在跑的活…")
                现在["活"].停()
    return 0


if __name__ == "__main__":
    sys.exit(main())
