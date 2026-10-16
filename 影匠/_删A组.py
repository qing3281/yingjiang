# -*- coding: utf-8 -*-
"""删网盘 A 组。**默认干跑，一个字节都不动。**

用 `--真删` 才动手。用法：

    python _删A组.py                 # 干跑：只打印要删什么、能省多少
    python _删A组.py --真删           # 真删 A 组
    python _删A组.py --真删 --带C组    # 真删 A 组 + 两个空壳目录树

## 为什么写这个脚本而不是直接 Remove-Item

硬规矩第 1 条：删任何东西之前先给用户核对。所以这里有两道闸：

1. **干跑默认开**。不传 `--真删` 就只打印，不碰盘。
2. **删前逐条打印「解析出来的绝对路径」**。
   必须自己先看一眼那几行 —— `...\\ComfyUI-aki\\models` 和
   `...\\ComfyUI-aki\\models_backup` 只差三个字符，删错一个就是 76 GB。

## 为什么「目录大小」和「真能省」是两个数

`ComfyUI-aki\\models` 目录有 **76.55 GB**，但真删只省 **11.72 GB** ——
里面 5 个 H3 大文件已经硬链到 `D:\\Comfy-Desktop\\ComfyUI-Shared\\models` 在用的那份，
**同一个 inode，删了这个路径一个字节都不释放**（详情见 `_复核A组.py`）。
所以脚本的判据是 **`st_nlink == 1` 才计入「能省」**，不是拿目录大小相加。

## 删完必须对账

删完再量一次 D 盘空闲，拿「实际省」和「预计省」比。
差得多就说明：要么有别的进程在写盘，要么哪条路径认错了。
**打完 ✓ 不等于量过** —— 这是「假判据族」里最常见的一条。
"""
import argparse
import os
import shutil
import sys

盘 = r"D:\DSHworkspace\素材\网盘"

# A 组：按核对清单，四条路径
#
# 第三项用「只删自由文件」模式，理由：
#   `aki\models` 目录看着 76.55 GB，但里面 5 个 H3 大文件（25.28 + 19.53 + 14.61
#   + 4.85 + 0.56 GB）**已经硬链到本机在用的那份**，同一个 inode。
#   删掉这些路径**一个字节都不释放**，却会让网盘这边少一份可打开的路径。
#   所以这一条**只删 `st_nlink == 1` 的文件**（就是那批 SD1.5），
#   硬链的一律留着 —— 留着不花空间，删了也不省空间，那就别动它。
#   ★ 名字叫「只删 SD1.5 那部分」就必须真的只删那部分。标签和动作对不上
#     是造成误删的头号原因（见 `知识\假判据族.md`）。
A组 = [
    ("aki 四个旧版压缩包", os.path.join(盘, r"下载\ComfyUI-aki\旧版本"), "整删"),
    ("aki v3.2 本体压缩包", os.path.join(盘, r"下载\ComfyUI-aki\ComfyUI-aki-v3.2.7z"), "整删"),
    ("aki models（只删 SD1.5 自由文件，硬链留着）",
     os.path.join(盘, r"下载\ComfyUI-aki\models"), "只删自由文件"),
    ("九月整合包 7z（内容已解压取出）",
     os.path.join(盘, r"下载\3.九月整合包（minimax+qwen2.1+自由姿势)\Comfyui-WF-整合包-不含模型-2026.9.28.7z"),
     "整删"),
]

# C 组：空壳目录树，删了不省空间，只为目录清爽
C组 = [
    ("1.MINIMAX打斗专篇（内容已取走）", os.path.join(盘, r"下载\1.MINIMAX打斗专篇")),
    ("【Work-Fisher】纯净版整合包（内容已取走）", os.path.join(盘, r"下载\【Work-Fisher】纯净版整合包（只包含MINIMAX-H3）")),
]

# SD1.5 里不删的（这些是 11 个 ControlNet + anything-v5 + flux-ae —— 其实都在 models 里，
# 整个 models 目录一起删。留着这个常量是为了说明「它不是硬链、删了真省」。）


def 量空闲() -> float:
    import ctypes
    free = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p("D:\\"), None, None, ctypes.pointer(free))
    return free.value / 2**30


def 扫(路: str):
    """返回 (文件数, 名义字节, 真能省字节, 硬链清单)"""
    if not os.path.exists(路):
        return None
    文s = []
    if os.path.isfile(路):
        文s = [路]
    else:
        for 底, _, fs in os.walk(路):
            for f in fs:
                文s.append(os.path.join(底, f))
    名义 = 真省 = 0
    硬 = []
    for p in 文s:
        try:
            st = os.stat(p)
        except OSError:
            continue
        名义 += st.st_size
        if st.st_nlink > 1:
            硬.append((p, st.st_size, st.st_nlink))
        else:
            真省 += st.st_size
    return len(文s), 名义, 真省, 硬


def 打印一条(名: str, 路: str):
    r = 扫(路)
    if r is None:
        print(f"  ✗ {名}\n      路径不存在：{路}")
        return 0.0
    数, 名义, 真省, 硬 = r
    print(f"\n  ── {名}")
    print(f"     ★ 解析出来的绝对路径：{os.path.abspath(路)}")
    print(f"     文件 {数} 个　目录看着 {名义 / 2**30:.2f} GB"
          f"　**删了真能省 {真省 / 2**30:.2f} GB**")
    if 硬:
        print(f"     里面有 {len(硬)} 个硬链（删了不省空间），最大的三个：")
        for p, sz, nl in sorted(硬, key=lambda t: -t[1])[:3]:
            print(f"       {sz / 2**30:7.2f} GB  nlink={nl}  {os.path.basename(p)}")
    return 真省


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--真删", action="store_true", help="不传就是干跑")
    ap.add_argument("--带C组", action="store_true", help="连两个空壳目录树一起删")
    ap.add_argument("--只C组", action="store_true", help="只删空壳目录树")
    参 = ap.parse_args()

    print("=" * 78)
    print("  删网盘 A 组" + ("（★ 真删）" if 参.真删 else "（干跑：一个字节都不动）"))
    print("=" * 78)

    前 = 量空闲()
    print(f"\n  D 盘空闲（动手前）：{前:.2f} GB")

    清单 = []
    if not 参.只C组:
        清单 += [("A", 名, 路, 法) for 名, 路, 法 in A组]
    if 参.带C组 or 参.只C组:
        清单 += [("C", 名, 路, "整删") for 名, 路 in C组]

    print(f"\n{'─' * 78}\n  第一步：逐条核对（★ 先看这几行路径对不对）\n{'─' * 78}")
    预计 = 0.0
    for _, 名, 路, _法 in 清单:
        预计 += 打印一条(名, 路)

    print(f"\n{'─' * 78}")
    print(f"  预计能省：{预计 / 2**30:.2f} GB")
    print(f"{'─' * 78}")

    if not 参.真删:
        print("\n  这是干跑。确认上面路径都对，加 --真删 才动手。\n")
        return 0

    print(f"\n{'─' * 78}\n  第二步：真删\n{'─' * 78}")
    删了 = 0
    留了硬链 = 0
    for 组, 名, 路, 法 in 清单:
        绝 = os.path.abspath(路)
        # 最后一道闸：路径必须在网盘树下，且必须是那几条核对过的
        if not 绝.startswith(os.path.abspath(盘) + os.sep):
            print(f"  ✗ 拒绝：{绝} 不在 {盘} 下")
            continue
        if not os.path.exists(绝):
            print(f"  – 已经不在：{名}")
            continue
        try:
            if 法 == "只删自由文件":
                # ★ 只动 st_nlink == 1 的：硬链删了不省空间，留着也不花空间，
                #   而留着能让网盘这边照样打得开，所以一个都不碰。
                n自由 = n硬 = 0
                for 底, _, fs in os.walk(绝):
                    for f in fs:
                        p = os.path.join(底, f)
                        try:
                            if os.stat(p).st_nlink > 1:
                                n硬 += 1
                                continue
                        except OSError:
                            continue
                        os.remove(p)
                        n自由 += 1
                # 清掉空目录（自底向上）
                for 底, ds, _ in os.walk(绝, topdown=False):
                    for d in ds:
                        try:
                            os.rmdir(os.path.join(底, d))
                        except OSError:
                            pass
                留了硬链 += n硬
                print(f"  ✓ 删了：{名}　→　删掉 {n自由} 个自由文件，**留下 {n硬} 个硬链没动**")
            else:
                if os.path.isfile(绝):
                    os.remove(绝)
                else:
                    shutil.rmtree(绝)
                print(f"  ✓ 删了：{名}")
            删了 += 1
        except OSError as e:
            print(f"  ✗ 删不动 {名}：{e}")

    # 第三步：对账
    import time
    time.sleep(3)
    后 = 量空闲()
    实际 = 后 - 前
    print(f"\n{'─' * 78}\n  第三步：对账\n{'─' * 78}")
    print(f"  动了 {删了} 条" + (f"（另有 {留了硬链} 个硬链按计划没动）" if 留了硬链 else ""))
    print(f"  D 盘空闲：{前:.2f} GB → {后:.2f} GB　**实际省了 {实际:.2f} GB**")
    print(f"  预计能省 {预计 / 2**30:.2f} GB　实际省 {实际:.2f} GB")
    if 实际 >= 预计 / 2**30 * 0.9:
        print("  ✓ 对得上")
    else:
        print("  ⚠ 差得多 —— 可能还有别的进程在写盘，或者哪条路径认错了。别急着说成功。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
