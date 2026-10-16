# -*- coding: utf-8 -*-
"""重启我给他做的那些台，并且**证明起来的是新代码**。

用法：
    python _重启台.py 记忆            # 只重启记忆台
    python _重启台.py 全部            # 三个都重启
    python _重启台.py 记忆 --看        # 只看状态，不重启

★ 为什么要有这个脚本（2026-10-15 08:40 踩的坑）：

    我改了 `_记忆台.py`，然后「杀掉 8792 再起来」，连打 3 次全 HTTP 200，
    就宣布改好了。**其实那 3 次 200 是七点四十五分那个旧进程回的** ——
    我按 `CommandLine -match '8792'` 去杀，没杀到真正的端口持有者；
    新起的两个进程因为端口被占，bind 失败，静静地蹲在旁边。

    **200 只证明「有个东西在答」，不证明「答的是你刚改的那份代码」。**

    所以这里的判据是**两条**，缺一不可：
      ① 端口持有者的**启动时刻**晚于我改过的那些源文件的**最后修改时刻**；
      ② 起来之后连打 3 次 200，且页面里能找到我这次新加的那个字符串。

    这就是 `AGENTS.md` 第 0.05 条第 1 类「判据说 OK 其实什么都没量」的第 12 次 ——
    它换了张脸：以前是「文件没写却说写好了」，这次是「进程没换却说重启了」。
"""

import io
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根

# 台名 -> (端口, 脚本**绝对路径**, 起来之后页面里必须能搜到的串, 额外参数)
# ★ 2026-10-15 10:10 修：以前这里存的是**文件名**，拼的是 `根\文件名` ——
#   而 `_控台.py` 的真身在 `根\影匠\_控台.py`，于是判据① 的 mtime 拿到 1970-01-01、
#   永远通过；8794 的服务也不是 `_依据窗.py`（那是个 tkinter 窗口，还不认 `--口`）。
#   **路径错了不会报错，它只会让判据失效** —— 所以这里改成绝对路径，且起之前先断言文件在。
台表 = {
    "记忆": (8792, r"D:\DSHworkspace\工具\_记忆台.py", "压缩台账", []),
    "影匠": (8791, r"D:\DSHworkspace\影匠\_控台.py", "官方接口", ["--口", "8791"]),
    "依据": (8794, r"D:\DSHworkspace\工具\_依据台.py", "", []),
}

# 起台用的解释器 —— 影匠那边的脚本要 ComfyUI 那个 venv 才导得动依赖
py影匠 = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
py本机 = sys.executable


def 解释器(脚本):
    return py影匠 if os.path.normcase(脚本).startswith(os.path.normcase(r"D:\DSHworkspace\影匠")) else py本机


def 找壳():
    """★ `pwsh` 在 Python 子进程的 PATH 里可能找不到（实测 WinError 2）。
    退回系统自带的 Windows PowerShell 5.1 —— 它一定在。"""
    import shutil
    for 名 in ("pwsh", "powershell"):
        p = shutil.which(名)
        if p:
            return p
    for p in (r"C:\Program Files\PowerShell\7\pwsh.exe",
              r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"):
        if os.path.exists(p):
            return p
    return None


壳 = 找壳()


def 跑(命令):
    if not 壳:
        return ""
    r = subprocess.run([壳, "-NoProfile", "-Command", 命令],
                       capture_output=True, text=True, errors="replace")
    return r.stdout or ""


def 找端口主人(口):
    """谁在听这个端口 —— 返回**全部**持有者。

    ★ 一定要返回全部：Windows 上第二个进程用 SO_REUSEADDR 也能 bind 成功，
      于是同一个端口会有**两个** listening socket，`Select -First 1` 只能看见一个。
      2026-10-15 08:42 实测 8792 上同时挂着 PID 2088（07:45 的旧代码）和 21084
      （08:36 的新代码）—— 杀了一个，**回给你的仍然可能是旧的那个**。
    """
    s = 跑(f"Get-NetTCPConnection -LocalPort {口} -State Listen -EA SilentlyContinue |"
           " Select-Object -Expand OwningProcess")
    出 = []
    for ln in s.strip().splitlines():
        ln = ln.strip()
        if ln.isdigit() and int(ln) not in 出:
            出.append(int(ln))
    return 出


def 进程启动时刻(pid):
    return 跑(f"(Get-Process -Id {pid} -EA SilentlyContinue).StartTime.ToString('yyyy-MM-dd HH:mm:ss')").strip()


def 杀端口主人(口):
    们 = 找端口主人(口)
    for pid in 们:
        跑(f"Stop-Process -Id {pid} -Force -EA SilentlyContinue")
    # 等它们真死
    for _ in range(25):
        time.sleep(0.4)
        if not 找端口主人(口):
            break
    return 们


def 连打(口, 次=3):
    好, 体 = 0, ""
    for _ in range(次):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{口}/", timeout=12) as r:
                if r.status == 200:
                    好 += 1
                    体 = r.read().decode("utf-8", "replace")
        except Exception:
            pass
    return 好, 体


def 源文件最新时刻(脚本):
    # ★ 脚本现在是绝对路径 —— 以前拼 `根\脚本`，路径错了不报错，
    #   只是 mtime 恒为 0，判据① 就变成一个永远为真的空动作。
    return os.path.getmtime(脚本) if os.path.exists(脚本) else 0.0


def 重启(名, 只看=False):
    口, 脚本, 必须含, 参数 = 台表[名]
    print(f"\n【{名}台】口 {口}　脚本 {脚本}")
    if not os.path.exists(脚本):
        print(f"  ✗ 脚本不在：{脚本} —— 先修台表，不然后面的判据全是假的")
        return False
    老 = 找端口主人(口)
    if 老:
        print(f"  现在占着端口的：")
        for pid in 老:
            print(f"      PID {pid}　起于 {进程启动时刻(pid)}")
    else:
        print("  现在没人在听这个端口")

    if 只看:
        return None

    if 老:
        杀 = 杀端口主人(口)
        print(f"  杀掉 {len(杀)} 个 PID {杀}　"
              f"{'✓ 端口腾出来了' if not 找端口主人(口) else '✗ 还占着：' + str(找端口主人(口))}")

    py = 解释器(脚本)
    # ★ 用 subprocess.Popen 而不是 Start-Process，这样死了能看见
    subprocess.Popen([py, "-X", "utf8", 脚本, *参数],
                     cwd=os.path.dirname(脚本),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    time.sleep(7)

    新们 = 找端口主人(口)
    if not 新们:
        print("  ✗ 新进程没起来（端口没人听）")
        return False
    # ★ 端口上挂了不止一个，就说明还有旧的没死干净 —— 这时候「200」不能信
    if len(新们) > 1:
        print(f"  ✗ 端口上还挂着 {len(新们)} 个进程 {新们} —— 没清干净，200 也不能信")
        return False
    新 = 新们[0]
    起 = 进程启动时刻(新)
    print(f"  新的 PID {新}，起于 {起}")

    # ★★ 判据①：端口持有者的启动时刻，必须晚于脚本的最后修改时刻
    源改 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(源文件最新时刻(脚本)))
    好1 = 起 > 源改
    print(f"  ① 起的时刻 {起} {'>' if 好1 else '≤'} 脚本改的时刻 {源改}　{'✓ 跑的是新代码' if 好1 else '✗ 还是旧代码'}")

    # ★★ 判据②：连打 3 次 200，并且页面里有这次新加的东西
    好, 体 = 连打(口)
    print(f"  ② 连打 3 次：{好} 次 200　{len(体.encode('utf-8')):,} B")
    好2 = (好 == 3) and (必须含 == "" or 必须含 in 体)
    if 必须含:
        print(f"     页面里有「{必须含}」= {必须含 in 体}")

    ok = bool(好1 and 好2)
    print(f"  → {'✓ 换成功了' if ok else '✗ 没换成 —— 别看这个页面，它还是旧的'}")
    return ok


def 主():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    名 = a[0] if a else "全部"
    只看 = "--看" in sys.argv

    if 名 == "全部":
        们 = list(台表)
    elif 名 in 台表:
        们 = [名]
    else:
        print(f"  不认识的台名「{名}」，可选：{' / '.join(台表)} / 全部")
        return 1

    好 = []
    for m in 们:
        好.append(重启(m, 只看))

    if not 只看:
        print("\n" + "=" * 46)
        for m, r in zip(们, 好):
            print(f"  {m}台　{'✓ 换成了' if r else '✗ 没换成'}")
    return 0


if __name__ == "__main__":
    sys.exit(主())
