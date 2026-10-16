"""影匠 · 真加载探测（**只读，不改任何文件，不下载**）

为什么单独写一个：
    「11 件齐了」只是**纸上**的齐。真正不撒谎的判据只有一条 —— **文件能被读进来**。
    `gpt.pth` / `s2mel.pth` / `codec.pth` 都是 pickle 打包的 state_dict，**没有 safetensors
    那种自描述头**，所以「大小对上」之后仍然可能是坏的（lead 在远端踩过：6 个里 2 个残缺，
    `exists()` 为真、大小非零，一加载才报 `Tensor '...' extends past the end of the file`）。

这个脚本干的事，就是把「能不能读进来」提前到**模型还没下完的时候**就能测：
    对每个已经存在的文件，用 `torch.load(..., mmap=True)` 只读**第 1 个张量**，
    报出「真实张量数 / 首键 / 形状」。读得动 = 文件结构完整；读不动 = 现在就知道。

`mmap=True` 的意义：不把 3 GB 读进内存，只按需映射 —— 所以对正在跑的 ComfyUI
几乎没有压力，可以放心在下载期间跑。**只读**：不写、不删、不替换。

用法（在 D:\\DSHworkspace\\影匠 下，用 ComfyUI 的 venv python）：
    python 探模型.py              探模型目录里所有已存在的 .pth / .pt / .bin
    python 探模型.py gpt.pth      只探指定的几个（可给多个人名/路径片段）
"""

import sys
from pathlib import Path

模型根 = Path(r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\IndexTTS-2.5")


def 探一个(p: Path) -> tuple[str, str]:
    """返回 (判定, 说明)。判定 ∈ {✓, ✗, 跳过}。只读。"""
    if not p.is_file():
        return "跳过", "文件不在"
    import torch

    n = p.stat().st_size
    try:
        sd = torch.load(str(p), map_location="cpu", mmap=True, weights_only=True)
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:160]}"
        # pickle 里带自定义类时 weights_only=True 会被拒 —— 那是「读法不对」，不是「文件坏」
        if "WeightsUnpickler" in msg or "weights_only" in msg or "Unsupported global" in msg:
            try:
                sd = torch.load(str(p), map_location="cpu", mmap=True)
            except Exception as e2:
                return "✗", f"真加载失败（放开 weights_only 也不行）：{type(e2).__name__}: {str(e2)[:160]}"
        else:
            return "✗", f"真加载失败：{msg}"

    if isinstance(sd, dict):
        if not sd:
            return "✗", "读出来是空 dict"
        键们 = list(sd.keys())
        首 = 键们[0]
        try:
            形 = tuple(sd[首].shape)
        except Exception:
            形 = ()
        return "✓", f"{len(键们)} 个张量 · 首键 {首} {形} · mmap 只映射不读全"
    if isinstance(sd, (list, tuple)):
        return "✓", f"{type(sd).__name__}，{len(sd)} 个元素"
    return "✓", f"读出来是 {type(sd).__name__}"


def main() -> int:
    args = sys.argv[1:]
    候选: list[Path] = []
    if args:
        for a in args:
            候选 += [p for p in 模型根.rglob("*") if p.is_file() and a in str(p)]
    else:
        候选 = [p for p in sorted(模型根.rglob("*"))
                if p.is_file() and p.suffix.lower() in (".pth", ".pt", ".bin")]

    if not 候选:
        print("没有可探的文件。")
        return 0

    print(f"模型根 {模型根}")
    print(f"共 {len(候选)} 个文件待探（**只读，不写不删**）")
    print()
    坏 = 0
    for p in 候选:
        判定, 话 = 探一个(p)
        mb = p.stat().st_size / 1024 / 1024 if p.is_file() else 0
        print(f"  [{判定}] {str(p.relative_to(模型根)):<44} {mb:>10,.1f} MB  {话}", flush=True)
        if 判定 == "✗":
            坏 += 1
    print()
    print(f"结论：{len(候选)} 个里 {坏} 个读不进来。")
    print("★ 只有这一关过了，才叫「真齐」—— 大小和 exists() 都不算。")
    return 0 if 坏 == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
