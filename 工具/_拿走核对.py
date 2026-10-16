# -*- coding: utf-8 -*-
"""
_拿走核对.py —— 删网盘之前的最后一道闸：**「网盘里每个有用的东西，别处还有吗？」**

## 为什么要有这个

用户 m20215 授权我自主删网盘，**唯一的条件**是「你在删之前，一定要保证将里面有用的
部分都已经给拿走了」。他 10-15 更早就说过更重的一句：

> 「而然后最大的优先级是要获得里面有用的东西，要不然我花这么多时间下这么东西过来
>   是拿给你慢慢删的吗？」

所以「能不能删」不是由我的感觉决定的，是由**这张表**决定的：网盘里的每一个文件，
在下面三个地方之一能不能找到同名的：

  1. 本机模型库   `D:\\Comfy-Desktop\\ComfyUI-Shared\\models`
  2. 远端模型库   `E:\\影匠AI\\ComfyUI-Shared\\models`   （名字清单从 `_远端模型清单.json` 读）
  3. 已取出的    `D:\\DSHworkspace\\影匠\\_网盘整理\\取出`

**找得到的判据**：同名 **且** 大小相等（差 1 KB 以内）。
只对文件大小 >= 阈值的（默认 20 MB）——小文件多是下载脚本、说明、缩略图，不值当。

## 用法

    python _拿走核对.py                只报告
    python _拿走核对.py --阈值 104857600   只看 >= 100 MB 的
    python _拿走核对.py --拉远端        先 ssh 拉一份远端模型名清单再比
"""
import argparse
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根
网盘 = os.path.join(根, "网盘")
取出 = os.path.join(根, "影匠", "_网盘整理", "取出")
本机库 = r"D:\Comfy-Desktop\ComfyUI-Shared\models"
远端清单 = os.path.join(根, "_远端模型清单.json")
SSH = "776bjta"

# 这些后缀才算「模型/可复用的大件」；其余（脚本、说明、缩略图）不参与判定
算数后缀 = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx",
            ".7z", ".zip", ".rar", ".tar", ".gz", ".mp3", ".wav", ".flac",
            ".json", ".yaml", ".yml", ".txt", ".md"}


def 扫(根目录, 最小=0):
    """→ {小写文件名: (完整路径, 大小)}"""
    表 = {}
    for dp, dn, fn in os.walk(根目录, onerror=lambda e: None):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_size < 最小:
                continue
            k = f.lower()
            # 同名取大的那份（有的目录里是空壳）
            if k not in 表 or st.st_size > 表[k][1]:
                表[k] = (p, st.st_size)
    return 表


def 拉远端():
    """让远端把自己的模型库文件名+大小打回来，存成 json。"""
    code = (
        "import os,json,sys\n"
        "sys.stdout.reconfigure(encoding='utf-8')\n"
        "r=r'E:\\影匠AI\\ComfyUI-Shared\\models'\n"
        "o={}\n"
        "for dp,dn,fn in os.walk(r,onerror=lambda e:None):\n"
        "    for f in fn:\n"
        "        p=os.path.join(dp,f)\n"
        "        try: o[f.lower()]=[p,os.path.getsize(p)]\n"
        "        except OSError: pass\n"
        "print(json.dumps(o))\n"
    )
    print(f"  拉远端清单（{SSH}）…")
    r = subprocess.run(["ssh", SSH, "python -"], input=code.encode("utf-8"),
                       capture_output=True, timeout=600)
    文 = r.stdout.decode("utf-8", "replace").strip()
    # ssh 可能带一行欢迎语，只取最后一行合法 json
    for 行 in reversed(文.splitlines()):
        行 = 行.strip()
        if 行.startswith("{"):
            try:
                d = json.loads(行)
            except Exception:
                continue
            with open(远端清单, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            print(f"  ✓ 远端 {len(d)} 个文件 → {远端清单}")
            return d
    print(f"  ✗ 拉不到。stderr={r.stderr.decode('utf-8','replace')[:400]}")
    return {}


def 主():
    参 = argparse.ArgumentParser()
    参.add_argument("--阈值", type=int, default=20 * 1024 * 1024)
    参.add_argument("--拉远端", action="store_true")
    参.add_argument("--只看没有的", action="store_true")
    a = 参.parse_args()

    if a.拉远端:
        拉远端()
    if not os.path.exists(远端清单):
        print(f"  注意：没有 {远端清单}，这一遍先不查远端。"
              f"补一句 `python _拿走核对.py --拉远端`。")
        远 = {}
    else:
        with open(远端清单, encoding="utf-8") as f:
            远 = json.load(f)

    print(f"扫网盘（>= {a.阈值/2**20:.0f} MB）…")
    网 = 扫(网盘, a.阈值)
    print(f"  网盘 {len(网)} 个")
    print(f"扫本机库 {本机库} …")
    本 = 扫(本机库, 0)
    print(f"  本机库 {len(本)} 个")
    print(f"扫已取出的 {取出} …")
    取 = 扫(取出, 0)
    print(f"  取出 {len(取)} 个")
    print(f"远端清单 {len(远)} 个\n")

    def 差(a_, b_):
        return abs(a_ - b_) <= 1024

    别处有, 只有这 = [], []
    for 名, (路, 大小) in sorted(网.items(), key=lambda x: -x[1][1]):
        if 名 in 本 and 差(大小, 本[名][1]):
            别处有.append((名, 大小, "本机库 " + 本[名][0]))
        elif 名 in 取 and 差(大小, 取[名][1]):
            别处有.append((名, 大小, "已取出 " + 取[名][0]))
        elif 名 in 远 and 差(大小, 远[名][1]):
            别处有.append((名, 大小, "远端 " + 远[名][0]))
        else:
            # 大小不符也要说清楚，别把「同名不同物」当成「有」
            备注 = []
            for 标签, 表 in (("本机库", 本), ("已取出", 取), ("远端", 远)):
                if 名 in 表:
                    备注.append(f"{标签}有同名但大小 {表[名][1]/2**30:.3f} GiB ≠ "
                              f"{大小/2**30:.3f} GiB")
            只有这.append((名, 大小, 路, "；".join(备注)))

    print("=" * 78)
    print(f"★ 别处找得到的：{len(别处有)} 个 / "
          f"{sum(x[1] for x in 别处有)/2**30:.2f} GiB")
    if not a.只看没有的:
        for 名, 大小, 哪 in 别处有[:60]:
            print(f"    {大小/2**30:7.2f} GiB  {名[:52]:<52}  {哪[:60]}")
        if len(别处有) > 60:
            print(f"    …… 还有 {len(别处有)-60} 个")
    print()
    print("=" * 78)
    print(f"★★ 别处都没有的（删了就真没了）：{len(只有这)} 个 / "
          f"{sum(x[1] for x in 只有这)/2**30:.2f} GiB")
    for 名, 大小, 路, 备注 in 只有这:
        print(f"    {大小/2**30:7.2f} GiB  {路.replace(网盘, '网盘')}")
        if 备注:
            print(f"                ⚠ {备注}")
    print()
    print("判据：上面那一段为空 → 网盘可以删。不空 → 先把它们搬走再删。")


if __name__ == "__main__":
    sys.exit(主() or 0)
