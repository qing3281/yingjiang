# -*- coding: utf-8 -*-
"""重摇后 30 秒里的镜 01 与镜 08（运镜失控的两条）。

## 为什么要单独写这个脚本

这两条的问题都在**运镜句**上，而词表里的句子是跨多行拼接的字符串，
直接在源码上做文本替换很容易踩空。这里改成**在内存里替换整条词表项**，
改完立刻跑，不动磁盘上的词表文件（词表保持「已知能跑通」的状态）。

## 两条各修什么

- **镜 01**：原写法「从车顶一路向上摇」→ 模型真的摇过了头，最后停在奥丁的胸甲特写上，
  轿车和一圈黑影全出画。改成**明确写终点**：「摇到胸口就停，他的头始终被画面上沿切掉，
  轿车和黑衣人在画面下三分之一里从头留到尾」。
- **镜 08**：原写法只说「跟着倒车的车甩」，模型自作主张推近到奥丁身上，
  而且奥丁当场退化成**一个金甲健美裸男**。改成**把车锁死在画面里**：
  「车占住画面左半边、整条镜头不许离开」。

用法：`python 重摇后30秒_01_08.py`
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 龙族后30秒词表 as 词

镜根 = r"D:\DSHworkspace\B站\成片\龙族_后30秒\镜"
首帧根 = r"D:\DSHworkspace\B站\成片\龙族_后30秒\首帧"

# ── 镜 01 的新运镜句 ──────────────────────────────────────────────
镜01_新运镜 = (
    "The camera begins low, pressed almost against the wet roof of the black "
    "sedan, then tilts up with large amplitude at fast speed, sweeping from the "
    "car roof up the god's body - and it stops at his chest. His head stays cut "
    "off by the top edge of the frame the whole time. The black sedan and the "
    "ring of black-robed figures stay visible in the lower third of the picture "
    "from the first frame to the last. "
)

# ── 镜 08 的新运镜句 ──────────────────────────────────────────────
镜08_新运镜 = (
    "The camera whips left with large amplitude at fast speed, staying locked "
    "onto the reversing car. The car fills the left half of the frame and never "
    "leaves it for a single frame; the god stays a small distant silhouette in "
    "the right half and is never approached. The background tears into long "
    "horizontal bands of motion blur. "
)


def 换运镜(旧: str, 新: str) -> str:
    """把一条词表项开头的运镜句换成新的。运镜句 = 第一段以 '. ' 收尾的话。"""
    止 = 旧.find(". ") + 2
    return 新 + 旧[止:]


def main() -> int:
    词.词表[1] = 换运镜(词.词表[1], 镜01_新运镜)
    词.词表[8] = 换运镜(词.词表[8], 镜08_新运镜)
    print(f"镜01 → {len(词.词表[1])} 字符")
    print(f"镜08 → {len(词.词表[8])} 字符")

    from MiniMax动态 import 出动态 as 跑

    for 号 in (1, 8):
        首 = os.path.join(首帧根, f"{号:02d}_首帧.png")
        出 = os.path.join(镜根, f"{号:02d}_动态.mp4")
        if not os.path.isfile(首):
            print(f"  ❌ 缺首帧 {首}")
            continue
        print(f"\n[{号}/2] 镜 {号:02d} 重摇")
        r = 跑(首, 词.词表[号], "", 出, 种子=617 + 号 * 137, 主体="")
        print(f"  → {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
