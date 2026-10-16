# -*- coding: utf-8 -*-
"""体检 `_导出仓库.py`：它要拷的每个源文件，现在还在不在？不在的话搬到哪去了？

只读。为什么写它：`_搬家.py` 把根目录的文件全挪进 `工具\` / `记忆\归档\`，
而 `_导出仓库.py` 里写的是 `os.path.join(工作区, "_开台.py")` 这种**老位置**——
字符串里没有一整条盘符路径，所以我那次的替换表一条都没匹配上，它就静默烂掉了。
**判据：一个「导出脚本」里每个源路径都得能 `os.path.isfile`；缺一个就报出来。**
"""
import importlib.util
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

工作区 = r"D:\DSHworkspace"
脚本 = os.path.join(工作区, "工具", "_导出仓库.py")

# 载入它（有 __main__ 卫，import 不会跑导出）
spec = importlib.util.spec_from_file_location("导出仓库", 脚本)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

图 = getattr(m, "图", {})
件 = getattr(m, "件", {})
装 = m.装
插件源 = m.插件源
插件件 = m.插件件


def 找同名(名字):
    """在工作区里按文件名找（跳过 netdisk / 模型 / 归档里的旧备份）"""
    跳过 = {"网盘", "downloads", "_bin", "node_modules", "__pycache__", "site-packages", ".git"}
    命中 = []
    for 根, 目录们, 文件们 in os.walk(工作区):
        目录们[:] = [d for d in 目录们 if d not in 跳过 and not d.startswith("chromium-")]
        if os.path.basename(根) == "搬家前":
            目录们[:] = []
            continue
        if 名字 in 文件们:
            命中.append(os.path.join(根, 名字))
        if len(命中) >= 6:
            break
    return 命中


print(f"══ `_导出仓库.py` 体检 ══")
print(f"   目标目录（装）：{装}")
print(f"   它在不在：{os.path.isdir(装)}")
print(f"   待导出：代码 {len(件)} 个　图 {len(图)} 个　插件 {len(插件件)} 个\n")

坏 = []
for 类, 表 in (("代码", 件), ("图", 图)):
    print(f"── {类} ──")
    for 到, 源 in 表.items():
        ok = os.path.isfile(源)
        if ok:
            print(f"   ✓ {到:<40} {os.path.getsize(源):>10,} B")
            continue
        命中 = 找同名(os.path.basename(源))
        if 命中:
            print(f"   ✗ 源不在：{源}")
            print(f"     └ 现在可能在：{命中[0]}")
            坏.append((到, 源, 命中[0]))
        else:
            print(f"   ✗✗ 源不在，全工作区也找不到同名：{源}")
            坏.append((到, 源, None))

print(f"\n── 插件源 ──")
print(f"   {插件源}")
print(f"   在不在：{os.path.isdir(插件源)}")

print(f"\n══ 结论：{len(坏)} / {len(件)+len(图)} 个源找不到（脚本现在是坏的）══")
for 到, 源, 新 in 坏:
    print(f"   {到:<40} {源}")
    print(f"   {'':<40} → {新 or '★ 找不到'}")
