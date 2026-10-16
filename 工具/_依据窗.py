# -*- coding: utf-8 -*-
"""
依据窗 —— 「依据台」的常驻小窗，钉在桌面右上角，一直浮在最上面。

为什么不用浏览器开：Edge 的 --app 窗口是 Chromium 自己在管 z 序，
从外部用 SetWindowPos 钉置顶会被它改回去（实测钉 20 次一次都没立住）。
所以这里用 tkinter 自己画一个窗口 —— 置顶、位置、字体全在我手里。

数据从哪来：本机 `_依据台.py`（8794）的 /api/now。
它读的是 DSH 自己写在会话存档里的 tool/call 记录 —— 我改不了，所以能当证据。

跑法：
    python _依据窗.py            开（已经开着就顶到最前）
    python _依据窗.py --关       关掉
    python _依据窗.py --看       只报状态
    python _依据窗.py --一次     不开窗，把这一轮打一遍就退出
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

口 = 8794
台址 = f"http://127.0.0.1:{口}/"
接口 = f"{台址}api/now"
主页 = r"D:\DSHworkspace\工具\_依据台.py"
PY = sys.executable

宽, 高 = 392, 1000
边距 = 40

底色 = "#12141a"
正字 = "#dfe3ea"
淡字 = "#7d8698"
亮字 = "#eaf0fa"
标色 = "#9fb0c9"
坏色 = "#ff7b72"
警色 = "#ffb35c"
径色 = "#c7d0de"
名色 = "#8fd0ff"
类色 = {"读": "#5fe0a0", "写": "#ffb35c", "跑": "#c79bff", "查": "#5fd0e0", "其它": "#9aa4b5"}

字体 = "Microsoft YaHei UI"
等宽 = "Consolas"


# ─────────────────────── 取数 ───────────────────────
def 取数(超时=4.0):
    try:
        with urllib.request.urlopen(接口, timeout=超时) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return {"坏": f"{type(e).__name__}: {e}"}


def 台在跑(重试=3, 超时=2.5):
    """连打几次才算「没在跑」。

    2026-10-15 修：原来只打一次、2 秒超时，结果出现过「服务明明 HTTP 200，
    --看 却报没在跑」——一次瞬时慢就能伪造出「没在跑」这种假状态。
    现在重试 3 次，并把最后一次的错误留住，好让「真没起」和「刚才卡了一下」区分开。
    """
    末次 = None
    for i in range(重试):
        try:
            with urllib.request.urlopen(台址, timeout=超时) as r:
                if r.status == 200:
                    return True
                末次 = f"HTTP {r.status}"
        except Exception as e:
            末次 = f"{type(e).__name__}: {e}"
        if i < 重试 - 1:
            time.sleep(0.6)
    台在跑.末次错 = 末次
    return False


台在跑.末次错 = None


def 起台():
    if 台在跑():
        return True
    DETACHED = 0x00000008 | 0x00000200
    subprocess.Popen(
        [PY, "-X", "utf8", 主页],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, creationflags=DETACHED, close_fds=True,
    )
    for _ in range(8):  # 判据：连打，不是 sleep 固定秒数
        time.sleep(0.7)
        if 台在跑():
            return True
    return False


def 时刻(t):
    if not t:
        return ""
    try:
        return time.strftime("%H:%M:%S", time.localtime(t / 1000))
    except Exception:
        return ""


# ─────────────────────── 画 ───────────────────────
def 备标签(文):
    文.tag_configure("正", foreground=正字, font=(字体, 9))
    文.tag_configure("淡", foreground=淡字, font=(字体, 8))
    文.tag_configure("亮", foreground=亮字, font=(字体, 13, "bold"))
    文.tag_configure("标", foreground=标色, font=(字体, 9, "bold"))
    文.tag_configure("坏", foreground=坏色, font=(字体, 9))
    文.tag_configure("警", foreground=警色, font=(字体, 9))
    文.tag_configure("径", foreground=径色, font=(等宽, 8))
    文.tag_configure("名", foreground=名色, font=(等宽, 8))
    文.tag_configure("钟", foreground="#5d6675", font=(等宽, 8))
    for k, v in 类色.items():
        文.tag_configure("类" + k, foreground=v, font=(字体, 8, "bold"))


def 画(文, 数):
    文.configure(state="normal")
    文.delete("1.0", "end")

    if 数.get("坏"):
        文.insert("end", "\n 看不了\n\n", "标")
        文.insert("end", f" {数['坏']}\n", "坏")
        文.insert("end", "\n DSH 存档可能在别的地方，或者 _依据台.py 没起。\n", "淡")
        文.configure(state="disabled")
        return

    工 = 数.get("工具") or []
    读 = 数.get("读过") or []
    类 = 数.get("按类") or {}
    空 = 数.get("空转") or 0
    段 = max(1, 数.get("推理段") or 1)
    每段 = 空 / 段

    文.insert("end", f" {数.get('会话','')[:8]}", "淡")
    文.insert("end", f"   更新 {time.strftime('%H:%M:%S')}\n\n", "钟")

    # 一行大数：工具 / 文件 / 空转
    文.insert("end", f" {len(工)}", "亮")
    文.insert("end", " 次工具   ", "淡")
    文.insert("end", f"{len(读)}", "亮")
    文.insert("end", " 份文件\n", "淡")

    文.insert("end", f" 读 {类.get('读',0)}  ·  写 {类.get('写',0)}  ·  "
                     f"跑 {类.get('跑',0)}  ·  查 {类.get('查',0)}  ·  "
                     f"轮 {数.get('轮',0)}\n", "淡")

    标 = "警" if 每段 < 5 else "坏"
    文.insert("end", " 空转 ", "淡")
    文.insert("end", f"{空}", 标 if 每段 >= 0.5 else "正")
    文.insert("end", f" 次（每段 {每段:.1f}）", "淡")
    文.insert("end", "  ✓ 达标\n\n" if 每段 < 0.5 else "  ✗ 超标\n\n", "淡")

    def 头(字):
        文.insert("end", f" {字}\n", "标")
        文.insert("end", " " + "─" * 44 + "\n", "淡")

    头("我读过哪些文件")
    if not 读:
        文.insert("end", " 这一轮还没读过文件。\n", "淡")
    for x in list(reversed(读))[:40]:
        文.insert("end", f" {x.get('名',''):<10}", "名")
        文.insert("end", f" {(x.get('目') or '')[:120]}\n", "径")
    文.insert("end", "\n")

    头("全部动作（最近 60 次）")
    if not 工:
        文.insert("end", " 还没有动作。\n", "淡")
    for x in list(reversed(工))[:60]:
        k = x.get("类", "其它")
        文.insert("end", f" {k}", "类" + k)
        文.insert("end", f" {x.get('名','')[:14]:<14}", "名")
        文.insert("end", f" {时刻(x.get('时'))}", "钟")
        目 = (x.get("目") or "").strip()
        if 目:
            文.insert("end", f"\n   {目[:150]}\n", "径")
        else:
            文.insert("end", "\n")

    文.insert("end", "\n DSH 自己记的 tool/call，我改不了。\n", "淡")
    文.configure(state="disabled")


# ─────────────────────── 窗 ───────────────────────
def 开窗():
    import tkinter as tk

    根 = tk.Tk()
    根.title("依据")
    根.configure(bg=底色)
    根.attributes("-topmost", True)
    根.geometry(f"{宽}x{高}+{根.winfo_screenwidth()-宽-边距}+{边距}")
    根.minsize(300, 300)

    顶 = tk.Frame(根, bg="#171a21", height=34)
    顶.pack(fill="x", side="top")
    顶.pack_propagate(False)
    tk.Label(顶, text="依据", bg="#171a21", fg=亮字,
             font=(字体, 10, "bold")).pack(side="left", padx=(10, 6))
    tk.Label(顶, text="这一轮读了哪些文件 · 做了什么", bg="#171a21", fg=淡字,
             font=(字体, 8)).pack(side="left")
    状 = tk.Label(顶, text="", bg="#171a21", fg=淡字, font=(字体, 8))
    状.pack(side="right", padx=8)

    框 = tk.Frame(根, bg=底色)
    框.pack(fill="both", expand=True)
    卷 = tk.Scrollbar(框, orient="vertical")
    卷.pack(side="right", fill="y")
    文 = tk.Text(框, bg=底色, fg=正字, bd=0, highlightthickness=0,
                 wrap="word", padx=8, pady=6, yscrollcommand=卷.set,
                 insertbackground=正字, spacing1=1, spacing3=1)
    文.pack(side="left", fill="both", expand=True)
    卷.config(command=文.yview)
    备标签(文)

    状2 = {"停": False, "次": 0}

    def 刷(快=False):
        if 状2["停"]:
            return
        数 = 取数()
        画(文, 数)
        状.config(text=time.strftime("%H:%M:%S"))
        状2["次"] += 1
        根.after(int(4000 if not 快 else 1500), 刷)

    def 关():
        状2["停"] = True
        try:
            根.destroy()
        except Exception:
            pass

    根.protocol("WM_DELETE_WINDOW", 关)
    根.bind("<Escape>", lambda e: 关())
    根.bind("<F5>", lambda e: 刷(True))

    # 每次刷新顺手把置顶再立一次（别的程序抢焦点后会掉）
    def 守顶():
        if 状2["停"]:
            return
        try:
            根.attributes("-topmost", True)
        except Exception:
            pass
        根.after(3000, 守顶)

    刷(True)
    守顶()
    根.mainloop()
    return 0


def 窗况():
    """现在有没有一个依据窗在跑（靠命令行认，不靠窗口标题）。"""
    出 = []
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get",
             "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, errors="replace", timeout=15,
        )
    except Exception:
        # 新版 Windows 没有 wmic 了，退回到 PowerShell
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                 "Select-Object ProcessId,CommandLine | ConvertTo-Csv -NoTypeInformation"],
                capture_output=True, text=True, errors="replace", timeout=20,
            )
        except Exception:
            return 出
    for 行 in (r.stdout or "").splitlines():
        if "_依据窗.py" in 行 and "--一次" not in 行:
            出.append(行.strip()[:160])
    return 出


def 主():
    if "--一次" in sys.argv:
        数 = 取数()
        if 数.get("坏"):
            print("  ✗", 数["坏"])
            return 1
        print(f"  会话 {数.get('会话','')[:8]}   工具 {len(数.get('工具') or [])} 次   "
              f"文件 {len(数.get('读过') or [])} 份   空转 {数.get('空转')} 次")
        for x in (数.get("读过") or [])[-12:]:
            print(f"    {x.get('名',''):<10} {(x.get('目') or '')[:100]}")
        return 0

    if "--看" in sys.argv:
        活 = 台在跑()
        尾 = "" if 活 else f"（连打 3 次都不通，末次：{台在跑.末次错}）"
        print(f"  依据台 http://127.0.0.1:{口}/  {'在跑' if 活 else '没在跑'}{尾}")
        在 = 窗况()
        print(f"  依据窗 {'在跑：' + 在[0] if 在 else '没开'}")
        return 0

    if "--关" in sys.argv:
        n = 0
        for 行 in 窗况():
            段 = [x for x in 行.replace('"', "").split(",") if x.strip()]
            pid = None
            for s in reversed(段):
                if s.strip().isdigit():
                    pid = int(s.strip())
                    break
            if pid:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True)
                n += 1
        print(f"  关了 {n} 个依据窗")
        return 0

    已 = 窗况()
    if 已:
        print("  依据窗已经开着了（要重开就先 --关）")
        return 0

    if not 起台():
        print("  ✗ 依据台起不来。先手动跑一下看看报什么：")
        print(f"      {PY} -X utf8 {主页}")
        return 1
    print(f"  ✓ 依据台在跑 http://127.0.0.1:{口}/")

    开窗()
    return 0


if __name__ == "__main__":
    sys.exit(主())
