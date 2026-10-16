# -*- coding: utf-8 -*-
"""扫网盘 —— 先弄清楚「里面到底有什么有用的」，再谈删。

用户 2026-10-15 02:10 的原话（最重要的一句）：

    最大的优先级是要获得里面有用的东西，要不然我花这么多时间下这么东西过来
    是拿给你慢慢删的吗？

所以这个脚本**不删任何东西**，只回答三个问题：
    ① 网盘里有哪些**能直接进我们工作流**的东西（模型 / 工作流 / 提示词 / 教程）
    ② 哪些是**我已经有了的副本**（按文件名+大小比对，不哈希，太快了）
    ③ 哪些是**跟我们完全不搭**的（游戏、软件安装包等）

用法：
    python _扫网盘.py              # 全扫，写到 _网盘清单.md
    python _扫网盘.py --顶 40       # 只打前 40 行
"""
import os, sys, re, json, hashlib, collections

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
网盘 = r"D:\DSHworkspace\素材\网盘"
本机模型根 = [r"D:\ComfyUI\models", r"D:\DSHworkspace\影匠", r"D:\DSHworkspace\素材\本地AI"]
出 = r"D:\DSHworkspace\_网盘清单.md"

# ── 什么算「能进工作流」 ──────────────────────────────────────────
模型后缀 = {'.safetensors', '.ckpt', '.pt', '.pth', '.bin', '.gguf', '.onnx', '.pkl'}
工作流后缀 = {'.json'}
文档后缀 = {'.md', '.txt', '.pdf', '.docx', '.doc', '.rtf', '.html', '.htm'}
表格后缀 = {'.csv', '.xlsx', '.xls'}
图后缀 = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff'}
视后缀 = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.ts', '.m4v'}
音后缀 = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
软后缀 = {'.exe', '.msi', '.zip', '.7z', '.rar', '.tar', '.gz', '.iso', '.apk'}
码后缀 = {'.py', '.js', '.ts', '.sh', '.ps1', '.bat', '.cmd', '.yml', '.yaml', '.toml', '.ini', '.cfg'}

def 类(fn):
    e = os.path.splitext(fn)[1].lower()
    if e in 模型后缀: return '模型'
    if e in 工作流后缀: return '工作流'
    if e in 文档后缀: return '文档'
    if e in 表格后缀: return '表格'
    if e in 图后缀: return '图片'
    if e in 视后缀: return '视频'
    if e in 音后缀: return '音频'
    if e in 软后缀: return '压缩包/软件'
    if e in 码后缀: return '代码'
    return '其他'

def GB(n): return n / 2**30


def 建本机索引():
    """本机已有文件的 (小写文件名, 大小) 集合 —— 用来判「重复」"""
    索 = set()
    名索 = collections.defaultdict(list)
    for 根 in 本机模型根:
        if not os.path.isdir(根):
            continue
        for dp, dns, fns in os.walk(根):
            for fn in fns:
                try:
                    sz = os.path.getsize(os.path.join(dp, fn))
                except OSError:
                    continue
                索.add((fn.lower(), sz))
                名索[fn.lower()].append(sz)
    return 索, 名索


def 主():
    打 = 40
    if '--顶' in sys.argv:
        i = sys.argv.index('--顶')
        if i + 1 < len(sys.argv) and sys.argv[i+1].isdigit():
            打 = int(sys.argv[i+1])

    print("建本机索引……", flush=True)
    本机, 名索 = 建本机索引()
    print(f"  本机已有 {len(本机):,} 个文件\n", flush=True)

    print("扫网盘……", flush=True)
    条 = []
    for dp, dns, fns in os.walk(网盘):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            条.append((st.st_size, p, 类(fn), fn, st.st_nlink))
    print(f"  共 {len(条):,} 个文件，{GB(sum(x[0] for x in 条)):.1f} GiB（逻辑）\n", flush=True)

    # 分类汇总
    汇 = collections.defaultdict(lambda: [0, 0])
    for sz, p, k, fn, nl in 条:
        汇[k][0] += 1
        汇[k][1] += sz

    L = []
    L.append("# 网盘清单（`_扫网盘.py` 生成，只读，没删任何东西）\n")
    L.append(f"共 **{len(条):,}** 个文件 / **{GB(sum(x[0] for x in 条)):.1f} GiB**（逻辑，含硬链重复）\n")

    L.append("\n## 一、按类型\n")
    L.append("| 类型 | 文件数 | 大小 |")
    L.append("|---|---:|---:|")
    for k, (c, s) in sorted(汇.items(), key=lambda x: -x[1][1]):
        L.append(f"| {k} | {c:,} | {GB(s):.2f} GiB |")

    # 重复判定
    重 = [x for x in 条 if (x[3].lower(), x[0]) in 本机]
    非重 = [x for x in 条 if (x[3].lower(), x[0]) not in 本机]
    同名不同大小 = [x for x in 条 if x[3].lower() in 名索
                    and (x[3].lower(), x[0]) not in 本机]

    L.append(f"\n## 二、重复情况\n")
    L.append(f"- **本机已有完全一样的**（同名同大小）：{len(重):,} 个 / {GB(sum(x[0] for x in 重)):.2f} GiB")
    L.append(f"- **本机没有的**：{len(非重):,} 个 / {GB(sum(x[0] for x in 非重)):.2f} GiB")
    L.append(f"- **同名但大小不同**（可能是不同版本，要人工看）：{len(同名不同大小):,} 个 / {GB(sum(x[0] for x in 同名不同大小)):.2f} GiB")

    # ★ 有价值的东西：本机没有的模型 / 工作流 / 文档
    for 类名, 标题 in (('模型', '三、**本机没有的模型**（这些才是要抢救的）'),
                       ('工作流', '四、**工作流 JSON**'),
                       ('文档', '五、**文档 / 提示词 / 教程**')):
        这 = sorted([x for x in 条 if x[2] == 类名 and (x[3].lower(), x[0]) not in 本机],
                    key=lambda x: -x[0])
        L.append(f"\n## {标题}　共 {len(这):,} 个 / {GB(sum(x[0] for x in 这)):.2f} GiB\n")
        if 类名 == '文档':
            for sz, p, k, fn, nl in 这[:300]:
                L.append(f"- `{p}`")
        else:
            L.append("| 大小 | 文件 |")
            L.append("|---|---|")
            for sz, p, k, fn, nl in 这[:300]:
                L.append(f"| {GB(sz):.2f} GiB | `{p}` |")
            if len(这) > 300:
                L.append(f"\n… 还有 {len(这)-300} 个")

    # 跟我们不搭的
    不搭 = sorted([x for x in 条 if x[2] in ('压缩包/软件', '视频', '音频', '其他')],
                  key=lambda x: -x[0])
    L.append(f"\n## 六、看起来跟我们不搭的　共 {len(不搭):,} 个 / {GB(sum(x[0] for x in 不搭)):.2f} GiB\n")
    L.append("| 大小 | 类型 | 文件 |")
    L.append("|---|---|---|")
    for sz, p, k, fn, nl in 不搭[:120]:
        L.append(f"| {GB(sz):.2f} GiB | {k} | `{p}` |")

    # 按顶层整合包分组
    L.append("\n## 七、按顶层目录分组（看是哪个整合包带来的）\n")
    L.append("| 目录 | 文件数 | 大小 |")
    L.append("|---|---:|---:|")
    组 = collections.defaultdict(lambda: [0, 0])
    for sz, p, k, fn, nl in 条:
        相 = os.path.relpath(p, 网盘)
        顶 = 相.split(os.sep)[0]
        if os.sep not in 相:
            顶 = '(根目录散文件)'
        组[顶][0] += 1
        组[顶][1] += sz
    for 顶, (c, s) in sorted(组.items(), key=lambda x: -x[1][1]):
        L.append(f"| `{顶}` | {c:,} | {GB(s):.2f} GiB |")

    with open(出, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    print(f"\n写到 {出}（{os.path.getsize(出)/1024:.0f} KB）\n")

    # 屏幕上也打一份精简的
    for i, l in enumerate(L[:打]):
        print(l)


if __name__ == '__main__':
    主()
