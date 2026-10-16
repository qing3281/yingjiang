# -*- coding: utf-8 -*-
"""
_查压缩包.py —— 回答一句很具体的话：**「把这 7 个 .7z 删了，里面还有没有东西是别处没有的？」**

## 为什么不能用「文件名对不对得上」来判断

`_拿走核对.py` 是按**文件名**比的，所以它会把 `Comfyui-WF-2026.8.8.7z` 判成「别处都没有」
—— 因为别处当然没有这个 .7z，别处有的是**它解出来的东西**。这一层得拆开看：
不看压缩包本身，看**包里的每一个条目**。

## 判据

把一个包里的条目名全列出来（名字里的目录分隔统一成 `/`，取**相对路径的末两段**），
然后问：这个条目在下面这些地方找得到同名的吗？

  · `影匠\\_网盘整理\\取出\\`（已经解出来的）
  · `D:\\Comfy-Desktop\\ComfyUI-Installs\\ComfyUI\\ComfyUI\\`（本机 ComfyUI 安装）
  · `D:\\Comfy-Desktop\\ComfyUI-Shared\\models\\`（本机模型库）

**只对「解开来之后 >= 阈值」的条目较真**（默认 1 MB）—— 几百 KB 以下的
`__pycache__`、`.gitignore`、README 之类丢了也不心疼，全列出来反而看不清重点。

用法：
    python _查压缩包.py --列            只列包里的条目数和总解压大小（便宜）
    python _查压缩包.py                全查，打印「删了就真没了」的条目
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, r"D:\DSHworkspace\记忆\归档\归档\_lib")
try:
    import py7zr
except ImportError:
    print("缺 py7zr。装："
          r"pip install --target D:\DSHworkspace\记忆\归档\归档\_lib py7zr")
    sys.exit(2)

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根
网盘 = os.path.join(根, "网盘")
参考 = [
    os.path.join(根, "影匠", "_网盘整理", "取出"),
    r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI",
    r"D:\Comfy-Desktop\ComfyUI-Shared\models",
]


def 扫参考():
    """→ {小写文件名: 最大大小}"""
    表 = {}
    for r in 参考:
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
                if k not in 表 or s > 表[k]:
                    表[k] = s
                n += 1
        print(f"  {n:>7} 文件  {r}")
    return 表


def 找包():
    出 = []
    for dp, dn, fn in os.walk(网盘, onerror=lambda e: None):
        for f in fn:
            if f.lower().endswith((".7z", ".zip", ".rar")):
                出.append(os.path.join(dp, f))
    return sorted(出, key=lambda p: -os.path.getsize(p))


def 看一个(路, 参考, 阈值, 只列):
    大小 = os.path.getsize(路)
    print("=" * 78)
    print(f"{大小/2**30:7.2f} GiB  {路.replace(网盘, '网盘')}")
    try:
        with py7zr.SevenZipFile(路, "r") as z:
            条 = z.list()
    except Exception as e:
        print(f"   ✗ 打不开：{type(e).__name__}: {e}")
        return None, None
    总 = sum(x.uncompressed or 0 for x in 条)
    大条 = [x for x in 条 if (x.uncompressed or 0) >= 阈值]
    print(f"   条目 {len(条)} 个，解开合计 {总/2**30:.2f} GiB；"
          f"其中 >= {阈值/2**20:.0f} MB 的 {len(大条)} 个")
    if 只列:
        最大 = sorted(大条, key=lambda x: -(x.uncompressed or 0))[:15]
        for x in 最大:
            print(f"      {(x.uncompressed or 0)/2**20:9.1f} MB  {x.filename}")
        return None, 总
    没有 = []
    for x in 大条:
        名 = os.path.basename(x.filename.replace("\\", "/")).lower()
        if not 名:
            continue
        if 名 in 参考 and abs(参考[名] - (x.uncompressed or 0)) <= 4096:
            continue
        没有.append(x)
    if not 没有:
        print("   ✓ 大条目全都能在别处找到同名同大小的 → **这个包可以删**")
        return 0, 总
    s = sum(x.uncompressed or 0 for x in 没有)
    print(f"   ★ 别处没有的 {len(没有)} 个 / {s/2**30:.2f} GiB：")
    没有.sort(key=lambda x: -(x.uncompressed or 0))
    for x in 没有[:40]:
        print(f"      {(x.uncompressed or 0)/2**20:9.1f} MB  "
              f"{x.filename.replace(chr(92), '/')[:110]}")
    if len(没有) > 40:
        print(f"      …… 还有 {len(没有)-40} 个")
    return len(没有), 总


def 主():
    参 = argparse.ArgumentParser()
    参.add_argument("--列", action="store_true", help="只列条目数和大小")
    参.add_argument("--阈值", type=int, default=1024 * 1024)
    参.add_argument("--只查", default=None, help="只查文件名里含这个字的包")
    a = 参.parse_args()

    包 = 找包()
    if a.只查:
        包 = [p for p in 包 if a.只查 in p]
    print(f"网盘里 {len(包)} 个压缩包，合计 "
          f"{sum(os.path.getsize(p) for p in 包)/2**30:.2f} GiB\n")
    if not a.列:
        print("扫参考目录：")
        参考 = 扫参考()
        print(f"  参考表 {len(参考)} 个名字\n")

    总缺 = 0
    总解 = 0
    for p in 包:
        n, t = 看一个(p, 参考 if not a.列 else {}, a.阈值, a.列)
        if n:
            总缺 += n
        if t:
            总解 += t
    print("=" * 78)
    if a.列:
        print(f"全部解开合计 {总解/2**30:.2f} GiB")
    else:
        print(f"★ 一句话结论："
              f"{'全部包的大条目都能在别处找到 → 包可以删' if 总缺 == 0 else f'还有 {总缺} 个大条目别处没有，删之前要先拿出来'}")


if __name__ == "__main__":
    sys.exit(主() or 0)
