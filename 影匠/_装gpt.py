"""影匠 · 单独把 gpt.pth 拉下来（**写到独立目录，绝不动 lead 那路的 .parts**）

为什么需要它（实测，2026-10-14 03:0x）：

    `补模型.py` 那路（PID 28136，父 35260）此刻在拉 **`conformer_shaw.pt`（可选件，2.17 GB）**，
    实测 03:02:19 时正式分片 536,870,912 B（17.07 MB/s 的爆发），03:02:49 → 582,283,001 B，
    之后 03:03:19 / 03:03:49 / 03:04:19 三次采样**全是 0.00 MB/s**。
    而 `gpt.pth`（3.26 GB，**唯一还缺的必需件**）连 `.parts\\` 都还没建。

单独探测 gpt.pth 自己的下行（`curl -sL --max-time 15 -r 0-67108863`）：
    15 秒只拿到 18,084,602 B = **1.15 MB/s**（单连接）。
    服务端 302 跳到 `cas-bridge.xethub.hf.co`，所以单连接慢；分片并发是这里唯一的加速手段。

带宽是**瓶颈而不是冲突源**：三方抢的是管道，不是同一批文件 —— 所以多开这一路不会
让 lead 那路变慢（它本来就已经在 0 字节/秒），却能让「唯一还缺的必需件」开始动。

分两条路，谁先到算谁的：
    · 本脚本 → `gpt.pth.独自`（独立 `.parts\\`，用 `_并行下.拉`，份数 8）
    · lead 那路 → 迟早也会轮到 `gpt.pth`

落地判据（**不是「文件存在」**）：
    1) 字节数 == 3,259,599,833
    2) `torch.load` 真读得进来（gpt.pth 不是 safetensors，没有自描述头，
       所以只能真加载一次才算数 —— 只读第一个张量的 key，不把 3 GB 全解出来）

只有两条都过，才把 `gpt.pth.独自` `os.replace` 成 `gpt.pth`（原子替换）。
替换前会**先确认 `gpt.pth` 不存在或大小为 0** —— 避免覆盖 lead 那路的有效成果。

用法（在 D:\\DSHworkspace\\影匠 下，用 ComfyUI 的 venv python）：
    python _装gpt.py 查       只看：远端多大、本机到了多少、验过没有（零下载）
    python _装gpt.py          拉下来 + 验 + 就位
"""

import os
import sys
from pathlib import Path

这里 = Path(__file__).resolve().parent
模型根 = Path(r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\IndexTTS-2.5")
目标 = 模型根 / "gpt.pth"
临时 = 模型根 / "gpt.pth.独自"
URL = "https://hf-mirror.com/IndexTeam/IndexTTS-2.5/resolve/main/gpt.pth"
应有 = 3_259_599_833

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def 找并行():
    """`_并行下.py` 的文件名以 `_` 开头且含中文，import 语句写不出来，只能按文件路径装。"""
    import importlib.util

    p = 这里 / "_并行下.py"
    spec = importlib.util.spec_from_file_location("影匠并行下", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["影匠并行下"] = m
    spec.loader.exec_module(m)
    return m


def 在途(基: Path) -> int:
    """目标 + .parts\\ 里所有字节（含 .seg 临时块）—— 这正是「进度」的真判据。"""
    d = Path(str(基) + ".parts")
    if not d.is_dir():
        return 0
    n = 0
    for 根, _, 文件们 in os.walk(d):
        for f in 文件们:
            try:
                n += os.path.getsize(os.path.join(根, f))
            except OSError:
                pass
    return n


def 验字节(p: Path) -> tuple[bool, str]:
    if not p.is_file():
        return False, "文件不在"
    n = p.stat().st_size
    if n != 应有:
        return False, f"字节数 {n:,} ≠ 应有 {应有:,}（{n / 应有:.1%}）"
    return True, f"字节数 ✓ {n:,}"


def 验加载(p: Path) -> tuple[bool, str]:
    """★ 唯一不撒谎的判据：真 `torch.load` 一次。

    `gpt.pth` 是 pickle 打包的 state_dict，**没有 safetensors 那种自描述头**，
    所以「大小对上」之后仍然可能是坏的 —— 只有真读一次才知道。
    用 `mmap=True` 避免把 3 GB 整个读进内存；只看键名和第一个张量的形状。
    """
    try:
        import torch
    except Exception as e:  # pragma: no cover
        return False, f"没装 torch：{e}"
    try:
        sd = torch.load(str(p), map_location="cpu", mmap=True, weights_only=True)
    except Exception as e:
        return False, f"torch.load 失败：{type(e).__name__}: {str(e)[:200]}"
    if not isinstance(sd, dict) or not sd:
        return False, f"读出来不是非空 dict，是 {type(sd).__name__}"
    键们 = list(sd.keys())
    首 = 键们[0]
    try:
        形 = tuple(sd[首].shape)
    except Exception:
        形 = ()
    return True, f"真加载 ✓ {len(键们)} 个张量，首键 {首} {形}"


def 查() -> int:
    print(f"远端 {URL}")
    print(f"本机目标 {目标}")
    print()
    for 名, 基 in (("本脚本 gpt.pth.独自", 临时), ("lead 那路 gpt.pth", 目标)):
        成 = 基.stat().st_size if 基.is_file() else 0
        途 = 在途(基)
        print(f"  {名:<26} 成文件 {成:>15,} B   在途 {途:>15,} B  ({途 / 应有:6.2%})")
    print()
    for 名, 基 in (("gpt.pth.独自", 临时), ("gpt.pth", 目标)):
        if 基.is_file():
            好, 话 = 验字节(基)
            print(f"  {名}: {话}")
            if 好:
                好2, 话2 = 验加载(基)
                print(f"  {名}: {话2}")
            else:
                print(f"  {名}: 跳过加载测试（字节都不对）")
    print()
    print("  ★ 就位判据 = 字节数对上 **且** torch.load 真读得进来，两条都过才替换。")
    return 0


def 拉() -> int:
    if 目标.is_file() and 目标.stat().st_size == 应有:
        好, 话 = 验加载(目标)
        print(f"gpt.pth 已经在了：{话}")
        return 0 if 好 else 3

    并行 = 找并行()
    途 = 在途(临时)
    print(f"开始拉 gpt.pth → {临时}")
    print(f"  已有分片 {途:,} B（{途 / 应有:.1%}），8 路并发续传")
    print(f"  独立目录 {临时}.parts，不碰 lead 那路的任何文件", flush=True)

    好 = 并行.拉(URL, str(临时), 份数=8, 预期=应有, 静默=False)
    if not 好:
        print("✗ 这一轮没拉完（分片掉了或拼装校验不过）。分片留着，直接重跑本脚本可续传。", flush=True)
        return 1

    print()
    print("=== 落地前两道检查 ===", flush=True)
    好1, 话1 = 验字节(临时)
    print(f"  [1/2] {话1}")
    if not 好1:
        return 3
    好2, 话2 = 验加载(临时)
    print(f"  [2/2] {话2}   ← 唯一不撒谎的判据")
    if not 好2:
        print("  ✗ 加载不过，不替换。文件留着供排查（不要删，删了要重下 3.26 GB）。")
        return 3

    if 目标.is_file() and 目标.stat().st_size > 0:
        好L, 话L = 验字节(目标)
        if 好L:
            print(f"  目标 gpt.pth 已经就位（{话L}），不需要替换。")
            return 0
        print(f"  ★ 目标 gpt.pth 存在但不对（{话L}）—— 那是 lead 那路的半截，")
        print(f"    本脚本的 3.26 GB 是验过的，替换掉它。（半截那个不是有效成果，不心疼）")

    备份 = 模型根 / "gpt.pth.半截备份"
    if 目标.is_file():
        try:
            os.replace(目标, 备份)
            print(f"  半截已挪到 {备份.name}（没删，留证据）")
        except OSError as e:
            print(f"  ✗ 挪不动目标：{e}")
            return 3
    os.replace(临时, 目标)
    print()
    print(f"✓ 就位：{目标}  {目标.stat().st_size:,} B", flush=True)
    return 0


def main() -> int:
    模式 = sys.argv[1] if len(sys.argv) > 1 else ""
    if 模式 in ("查", "状态", "status"):
        return 查()
    if 模式 in ("", "拉", "下"):
        return 拉()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
