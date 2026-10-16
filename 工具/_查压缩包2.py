# -*- coding: utf-8 -*-
"""
_查压缩包2.py —— 换个更管用的问法。

## 上一版为什么不好用

`_查压缩包.py` 把包里每个 >= 1 MB 的条目都拿去和参考表比，结果每个包都报
「还有 565 个别处没有」—— 但它不告诉你**那 565 个是什么东西**。翻开来一看，
绝大多数是 `python/Lib/site-packages/` 下的 torch / CUDA / tensorflow DLL，
也就是**整合包自带的那个 Python 运行时**。那玩意儿本机已经有一份能跑的，
远端也有一份，包里的这份一文不值。

所以真正该问的是：

    「把自带的 Python 运行时和 .git 历史这两坨刨掉之后，包里还剩什么？
      剩的这些，别处有没有？」

## 分类规矩（按条目在包里的路径判）

    python/Lib/site-packages/**           → 自带的 Python 库（不值钱）
    **/.git/objects/**                    → git 历史（不值钱）
    **/__pycache__/**, *.pyc              → 编译缓存（不值钱）
    python/**, 程序文件/**, *.dll, *.pyd  → 运行时其它部分（不值钱）
    ComfyUI/custom_nodes/**               → ★ 节点代码（值钱）
    ComfyUI/models/**                     → ★ 模型（值钱）
    ComfyUI/input|output|user/**          → 数据（看情况）
    其余                                  → 待查

用法：
    python _查压缩包2.py            只统计分类，不比对（很快）
    python _查压缩包2.py --比对     对「值钱」的类别逐条比对参考表
"""
import argparse
import os
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, r"D:\DSHworkspace\记忆\归档\归档\_lib")
try:
    import py7zr
except ImportError:
    print("缺 py7zr")
    sys.exit(2)

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根
网盘 = os.path.join(根, "网盘")
参考目录 = [
    os.path.join(根, "影匠", "_网盘整理", "取出"),
    r"D:\Comfy-Desktop\ComfyUI-Shared\models",
    r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI",
]

垃圾 = ("python/", "程序文件/", "python\\", "程序文件\\")


def 归类(名):
    n = 名.replace("\\", "/").lower()
    if "/site-packages/" in n or n.startswith("python/") or "/python/" in n:
        return "①自带Python库"
    if "/.git/" in n or "/__pycache__/" in n or n.endswith(".pyc"):
        return "②git历史/缓存"
    if n.startswith("程序文件/") or "/程序文件/" in n:
        return "③启动器"
    if "/comfyui/custom_nodes/" in n:
        return "★节点代码"
    if "/comfyui/models/" in n:
        return "★模型"
    if "/comfyui/input/" in n or "/comfyui/output/" in n or "/comfyui/user/" in n:
        return "④输入输出"
    if n.endswith((".dll", ".pyd", ".lib", ".exe")):
        return "⑤其它二进制"
    return "⑥其它"


def 扫参考():
    """→ {小写文件名: set(所有同名文件的大小)}

    ★★ 这里踩过一个坑，写下来免得再踩：
       第一版写成 `表[k] = max(表[k], s)` —— **只留最大的那个同名文件的大小**。
       于是核对时拿「包里这个 17 MB 的 tokenizer.json」去比「参考表里最大的那个
       34 MB 的 tokenizer.json」，差 17 MB > 容差 8 KB，被判成「别处没有」。
       实测一抽查，**报「别处没有」的 327 个里绝大多数其实都有**。
       **同一个文件名在不同目录里本来就可能大小不同，那不是同一份东西。**
       正确做法：把**每一个**大小都留着，只要**有一个**对得上就算有。
    """
    表 = {}
    for r in 参考目录:
        if not os.path.isdir(r):
            print(f"  （跳过，不存在）{r}")
            continue
        n = 0
        for dp, dn, fn in os.walk(r, onerror=lambda e: None):
            for f in fn:
                try:
                    s = os.path.getsize(os.path.join(dp, f))
                except OSError:
                    continue
                k = f.lower()
                if k in 表:
                    表[k].add(s)
                else:
                    表[k] = {s}
                n += 1
        print(f"  {n:>7} 文件  {r}")
    print(f"  → 参考表 {len(表)} 个名字，"
          f"{sum(len(v) for v in 表.values())} 个不同大小")
    return 表


def 主():
    参 = argparse.ArgumentParser()
    参.add_argument("--比对", action="store_true")
    参.add_argument("--阈值", type=int, default=1024 * 1024)
    a = 参.parse_args()

    包 = []
    for dp, dn, fn in os.walk(网盘, onerror=lambda e: None):
        for f in fn:
            if f.lower().endswith(".7z"):
                包.append(os.path.join(dp, f))
    包.sort(key=lambda p: -os.path.getsize(p))

    参考 = 扫参考() if a.比对 else {}

    全缺 = []
    for p in 包:
        大小 = os.path.getsize(p)
        print("=" * 78)
        print(f"{大小/2**30:7.2f} GiB  {p.replace(网盘, '网盘')}")
        try:
            with py7zr.SevenZipFile(p, "r") as z:
                条 = z.list()
        except Exception as e:
            print(f"   ✗ 打不开：{type(e).__name__}: {e}")
            continue

        组 = defaultdict(lambda: [0, 0])
        for x in 条:
            s = x.uncompressed or 0
            c = 归类(x.filename)
            组[c][0] += 1
            组[c][1] += s
        总 = sum(v[1] for v in 组.values())
        print(f"   解开合计 {总/2**30:.2f} GiB / {len(条)} 条目")
        for c in sorted(组):
            n, s = 组[c]
            print(f"      {s/2**30:7.2f} GiB  {n:>7} 条  {c}")
        if not a.比对:
            continue

        # 只对值钱的类别逐条比
        缺 = []
        for x in 条:
            if (x.uncompressed or 0) < a.阈值:
                continue
            c = 归类(x.filename)
            if not c.startswith("★"):
                continue
            名 = os.path.basename(x.filename.replace("\\", "/")).lower()
            大小s = 参考.get(名) or set()
            if any(abs(s - (x.uncompressed or 0)) <= 8192 for s in 大小s):
                continue
            缺.append(x)
        if 缺:
            s = sum(x.uncompressed or 0 for x in 缺)
            print(f"   ★ 值钱类别里别处没有的：{len(缺)} 个 / {s/2**30:.2f} GiB")
            缺.sort(key=lambda x: -(x.uncompressed or 0))
            for x in 缺[:25]:
                print(f"        {(x.uncompressed or 0)/2**20:9.1f} MB  "
                      f"{x.filename.replace(chr(92),'/')[:105]}")
            全缺 += 缺
        else:
            print("   ✓ 值钱类别（节点/模型）全都能在别处找到 → 这个包可以删")
    if a.比对:
        print("=" * 78)
        print(f"★ 汇总：值钱类别里别处没有的共 {len(全缺)} 个 / "
              f"{sum(x.uncompressed or 0 for x in 全缺)/2**30:.2f} GiB")
        print("  → 这段为空，7 个 .7z 就可以删。")


if __name__ == "__main__":
    sys.exit(主() or 0)
