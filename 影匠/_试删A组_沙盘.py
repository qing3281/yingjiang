# -*- coding: utf-8 -*-
"""在沙盘里真跑一遍「只删自由文件」那段逻辑，证明它删对了。

## 为什么要这个

`_删A组.py` 的 `--真删` 里有一段从来没被执行过的代码：
`aki\\models` 那一条走「只删 `st_nlink == 1` 的文件」。

这是**唯一一条会「删一部分、留一部分」的路径** —— 也是最容易删多的一条。
36 GB 的破坏性动作之前，光「读一遍看着对」不算验过：
本项目已经栽过七次「判据说 OK 但什么都没量」（`知识\\假判据族.md`）。

## 沙盘怎么搭

照抄真实结构。`aki\\models` 里实际长这样：

    models\\
      unet\\anything-v5.safetensors        ← 自由文件（SD1.5，该删）
      controlnet\\control_v11p_sd15_*.safetensors  ← 自由文件（该删）
      text_encoders\\qwen3vl_32b_*.safetensors      ← 硬链到在用的那份（**不该删**）
      vae\\flux-ae.safetensors              ← 硬链（不该删）

沙盘在临时目录里搭一份一模一样的，其中「在用的那份」建在**外面**
（模拟 `D:\\Comfy-Desktop\\ComfyUI-Shared\\models`），
然后逐个判据验。

## 判据（四条，缺一条就不算过）

1. 该删的自由文件**真的没了**
2. 不该删的硬链文件**还在**，而且 `st_ino` 和外面那份**还是同一个**
3. 外面那份（在用的）**内容读出来一字不差**
4. 空目录被收掉，但**装了硬链的目录还在**
"""
import hashlib
import os
import shutil
import sys
import tempfile

OK = "OK"
FAIL = "FAIL"


def 填(p: str, 内容: bytes):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(内容)


def 指纹(p: str) -> str:
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def main():
    根 = tempfile.mkdtemp(prefix="删A组沙盘_")
    try:
        在用 = os.path.join(根, "ComfyUI-Shared", "models")
        aki = os.path.join(根, "网盘", "下载", "ComfyUI-aki", "models")

        # ── 外面「在用的那份」（硬链的另一头，必须活下来）
        内容 = {}
        for 相, sz in [("text_encoders/qwen3vl_32b_int8_convrot.safetensors", 300 * 1024),
                       ("vae/flux-ae.safetensors", 200 * 1024),
                       ("diffusion_models/minimax_h3_fl2va_int8_convrot.safetensors", 400 * 1024)]:
            数据 = os.urandom(sz)
            内容[相] = 数据
            填(os.path.join(在用, 相.replace("/", os.sep)), 数据)

        # ── aki\models：硬链三条 + 自由文件若干（模拟 SD1.5）
        for 相 in 内容:
            目标 = os.path.join(aki, 相.replace("/", os.sep))
            os.makedirs(os.path.dirname(目标), exist_ok=True)
            os.link(os.path.join(在用, 相.replace("/", os.sep)), 目标)

        自由 = []
        for 名, sz in [("unet/anything-v5.safetensors", 500 * 1024),
                       ("controlnet/control_v11p_sd15_canny.safetensors", 100 * 1024),
                       ("controlnet/control_v11p_sd15_openpose.safetensors", 100 * 1024),
                       ("controlnet/control_v11f1p_sd15_depth.safetensors", 100 * 1024)]:
            目标 = os.path.join(aki, 名.replace("/", os.sep))
            填(目标, os.urandom(sz))
            自由.append(目标)

        print("=" * 74)
        print("  沙盘已搭好")
        print("=" * 74)
        print(f"  在用的那份：{在用}")
        print(f"  aki\\models：{aki}")

        def 数(路):
            自 = 硬 = 0
            for 底, _, fs in os.walk(路):
                for f in fs:
                    p = os.path.join(底, f)
                    if os.stat(p).st_nlink > 1:
                        硬 += 1
                    else:
                        自 += 1
            return 自, 硬

        前自, 前硬 = 数(aki)
        print(f"\n  动手前：自由 {前自} 个 / 硬链 {前硬} 个")

        # ── ★★★ 这是从 _删A组.py 里逐字抄过来的那段
        n自由 = n硬 = 0
        for 底, _, fs in os.walk(aki):
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
        for 底, ds, _ in os.walk(aki, topdown=False):
            for d in ds:
                try:
                    os.rmdir(os.path.join(底, d))
                except OSError:
                    pass
        # ─────────────────────────────────────────────

        print(f"  跑完那段：删了 {n自由} 个自由文件，留下 {n硬} 个硬链")
        print()
        过 = 0
        总 = 0

        # 判据 1：自由文件真的没了
        总 += 1
        剩 = [p for p in 自由 if os.path.exists(p)]
        if not 剩 and n自由 == len(自由):
            print(f"  [{OK}] 判据1  该删的 {len(自由)} 个自由文件全删了")
            过 += 1
        else:
            print(f"  [{FAIL}] 判据1  还剩 {len(剩)} 个自由文件没删：{剩}")

        # 判据 2：硬链还在，且 ino 还指着外面那份
        总 += 1
        坏 = []
        for 相 in 内容:
            内 = os.path.join(aki, 相.replace("/", os.sep))
            外 = os.path.join(在用, 相.replace("/", os.sep))
            if not os.path.exists(内):
                坏.append((相, "网盘这边被删了"))
            elif os.stat(内).st_ino != os.stat(外).st_ino:
                坏.append((相, "ino 不一致"))
        if not 坏 and n硬 == len(内容):
            print(f"  [{OK}] 判据2  {len(内容)} 个硬链一个没动，ino 还是同一个")
            过 += 1
        else:
            print(f"  [{FAIL}] 判据2  {坏}")

        # 判据 3：外面那份内容一字不差
        总 += 1
        坏 = []
        for 相, 数据 in 内容.items():
            外 = os.path.join(在用, 相.replace("/", os.sep))
            if not os.path.exists(外) or open(外, "rb").read() != 数据:
                坏.append(相)
        if not 坏:
            print(f"  [{OK}] 判据3  外面「在用的那份」{len(内容)} 个文件内容原样")
            过 += 1
        else:
            print(f"  [{FAIL}] 判据3  外面那份坏了：{坏}")

        # 判据 4：空目录收了，装硬链的目录还在
        总 += 1
        装硬链的 = [os.path.join(aki, d) for d in ("text_encoders", "vae", "diffusion_models")]
        空的该没 = [os.path.join(aki, "unet"), os.path.join(aki, "controlnet")]
        还在 = [d for d in 装硬链的 if os.path.isdir(d)]
        没收 = [d for d in 空的该没 if os.path.isdir(d)]
        if len(还在) == len(装硬链的) and not 没收:
            print(f"  [{OK}] 判据4  装了硬链的 {len(还在)} 个目录还在，空的 {len(空的该没)} 个收掉了")
            过 += 1
        else:
            print(f"  [{FAIL}] 判据4  该在的 {还在} / 没收掉的空目录 {没收}")

        print()
        print("=" * 74)
        if 过 == 总:
            print(f"  ★ {过}/{总} 全过 —— 「只删自由文件」这段逻辑可以放心跑")
            print("=" * 74)
            return 0
        print(f"  ✗ 只过了 {过}/{总} —— 别跑 --真删")
        print("=" * 74)
        return 1
    finally:
        shutil.rmtree(根, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
