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


任务表 = {
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
    "配音": {
        "脚本": "_配台词_觉醒.py",
        "说": "按台词表合成配音",
        "参": lambda o: [],
    },
    "总装成片": {
        "脚本": "_成片_觉醒.py",
        "说": "接片 → 头尾 → 混音 → 烧字幕",
        "参": lambda o: [o["戏"]],
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
  if(d.内存总) h += '<div><span>内存</span><b>'+(1-d.内存闲/d.内存总).toFixed(0)+'<small>%</small></b></div>';
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
                o = {"戏": 戏, "格": 格s, "片": 片, "倍数": 体.get("倍数")}
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
