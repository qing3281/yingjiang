r"""把「影匠控制台」打成一个能双击就跑的 exe（P1⑤：可安装的小程序 v1）。

★ 打包之后有两件事会**静默地**变坏，`_控台.py` 里已经掰回来了：
   ① `__file__` 变成 PyInstaller 的临时目录 → `作品\` 找不着 → 「一部戏都没有」
   ② `sys.executable` 变成 exe 自己 → 拿它去跑 `_出H3.py` 只会再开一个控制台
   所以 exe 认 `sys.executable` 所在目录当根，另外去找真的 python.exe。

**直调那一类活不需要任何外部 python** —— `_出H3.py` / `引擎.py` 被 `--add-data`
打进了 exe，`importlib` 直接从解包目录导。这正是 P1⑥ 那条路的额外好处。
"""
import ast
import os
import shutil
import subprocess
import sys

工 = r"D:\DSHworkspace"
源 = os.path.join(工, "影匠", "_控台.py")
打 = os.path.join(工, "_打包")
装 = os.path.join(打, "装")

# 打进去的 .py —— **只打直调那条路真正 import 的**。
# `_出H3.py` 和 `引擎.py` 只用到标准库（argparse/json/os/re/urllib/uuid…），
# 所以 `--onefile` 打包之后，「直调·出段」这一类活在**完全没有 python 的机器上**
# 也能跑。其余的活（出首帧 / 配音 / 成片 / 超分）是另起子进程跑磁盘上的 .py，
# 那些文件本来就得在工作区里待着，打进来没用。
带 = ["_出H3.py", "引擎.py"]


def 顶层import(路):
    """一个 .py 里顶层 import 了哪些**标准库**模块。

    ★ 为什么必须算这一下：PyInstaller 只顺着**入口文件**（`_控台.py`）的
    import 图找依赖。`--add-data` 进去的那几个 .py 它**不分析** —— 于是
    `_出H3.py` 里的 `import uuid` 没被打进去。exe 起来、页面全绿、按了
    「开始」才炸 `ModuleNotFoundError: No module named 'uuid'`。
    （2026-10-15 实测踩到：打包后第一条直调就炸在这儿。）
    """
    出 = set()
    try:
        树 = ast.parse(open(路, encoding="utf-8").read())
    except Exception:
        return 出
    for n in ast.walk(树):
        if isinstance(n, ast.Import):
            for a in n.names:
                出.add(a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            if n.level == 0 and n.module:
                出.add(n.module.split(".")[0])
    return 出 & set(sys.stdlib_module_names)


要补 = set()
for f in 带:
    路 = os.path.join(工, "影匠", f)
    if os.path.isfile(路):
        要补 |= 顶层import(路)
要补 -= 顶层import(源)
print(f"  ★ 要额外手塞进去的（入口没 import、但打进去的 .py 要用）：{'、'.join(sorted(要补)) or '（无）'}")

命令 = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--onefile",
    "--console",
    "--name", "影匠控制台",
    "--distpath", os.path.join(打, "dist"),
    "--workpath", os.path.join(打, "build"),
    "--specpath", 打,
    # 别把 ComfyUI 那一大堆包卷进来
    "--exclude-module", "torch",
    "--exclude-module", "numpy",
    "--exclude-module", "PIL",
    "--exclude-module", "cv2",
    "--exclude-module", "transformers",
    "--exclude-module", "tkinter",
]
for m in sorted(要补):
    命令 += ["--hidden-import", m]
for f in 带:
    路 = os.path.join(工, "影匠", f)
    if os.path.isfile(路):
        命令 += ["--add-data", f"{路}{os.pathsep}."]
    else:
        print(f"  ! 缺文件，不打进去：{路}")
命令.append(源)


def 干():
    os.makedirs(打, exist_ok=True)
    print("  " + " ".join(命令[:8]) + " …\n")
    r = subprocess.run(命令, cwd=打, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(r.stdout[-3000:] if r.stdout else "")
    if r.returncode != 0:
        print("  ✗ 打包失败\n", (r.stderr or "")[-3000:])
        return 1

    exe = os.path.join(打, "dist", "影匠控制台.exe")
    if not os.path.isfile(exe):
        print(f"  ✗ 没生成 {exe}")
        return 1
    mb = os.path.getsize(exe) / 1048576
    print(f"\n  ✓ {exe}　{mb:.1f} MB")

    # 装到 影匠\ 下 —— exe 要跟 `作品\` 在同一个目录，它才认得出戏
    os.makedirs(装, exist_ok=True)
    到 = os.path.join(装, "影匠控制台.exe")
    shutil.copy2(exe, 到)
    print(f"  ✓ 装到 {到}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(干())
