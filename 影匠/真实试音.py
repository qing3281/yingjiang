# -*- coding: utf-8 -*-
"""
真实试音.py —— 让「一段文本 + 一个音色」真的出一个 wav。

这是 影匠 配音链路的**端到端验收脚本**，不模拟、不跳过：
它调 配音.合成()，让本机 ComfyUI 真跑 IndexTTS-2.5 推理，把 wav 落到 作品\\配音\\。

用法：
    python 真实试音.py                      # 用默认台词 + 默认音色（凌霜 A 组第一首选）
    python 真实试音.py "台词"                # 换台词
    python 真实试音.py "台词" "音色名"        # 换台词 + 换音色
    python 真实试音.py "台词" "音色名" --语速 0.9 --语言 ZH
    python 真实试音.py --列候选              # 只列出凌霜候选音色，不合成

退出码：0 = 真出了 wav；3 = 合成失败（人话原因在最后）；1 = 参数错。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
import traceback
from pathlib import Path

这里 = Path(__file__).resolve().parent

# 默认台词 —— Lead 定的凌霜台词（8 字，清冷、克制，与片子调子一致）
默认台词 = "雪落无声，剑亦无声。"
默认音色 = "女-常规-清冷无情-2-1"   # 旧写法，仅作后备；正常走 凌霜候选.json 的 A 组第 1 个

# 凌霜候选的唯一真相源是 音色\凌霜候选.json —— 每条都做过真实解码核验
# （soundfile.read 拿到 秒/采样率/声道/rms/峰/削波，判定「✓可用」才算数）。
# 这里**不再手写一份清单**：手写的会跟库漂移，而且我第一版就凭印象写错过名字
# （写了「女-常规-冷漠-1-1」这种东西，库里根本没有）。
候选文件 = 这里 / "音色" / "凌霜候选.json"
默认相对 = "男女——情绪分类\\女-常规-清冷无情-2-1.wav"   # A 组第 1 个 = 首选


def 读候选() -> list[dict]:
    if not 候选文件.is_file():
        return []
    import json
    库 = json.loads(候选文件.read_text(encoding="utf-8"))
    出 = []
    for c in 库.get("候选", []):
        出.append({
            "组": c.get("组", ""),
            "相对": c.get("相对", ""),
            "名字": Path(str(c.get("相对", ""))).stem,
            "秒": c.get("秒"),
            "采样率": c.get("采样率"),
            "声道": c.get("声道"),
            "rms": c.get("rms"),
            "峰": c.get("峰"),
            "削波": c.get("削波"),
            "判定": c.get("判定", ""),
            "理由": c.get("理由", ""),
        })
    return 出


def 装配音():
    """按路径加载 配音.py。模块名含中文，直接 import 可能失败 —— 用 importlib 按文件路径装。"""
    路 = 这里 / "配音.py"
    if not 路.is_file():
        raise FileNotFoundError(f"找不到 {路}")
    规 = importlib.util.spec_from_file_location("影匠配音", 路)
    模 = importlib.util.module_from_spec(规)
    sys.modules["影匠配音"] = 模
    规.loader.exec_module(模)
    return 模


def 列候选(配音) -> int:
    候 = 读候选()
    if not 候:
        print(f"✗ 读不到候选清单：{候选文件}")
        return 1
    print(f"凌霜候选（真相源：{候选文件}）")
    print(f"{'#':>2} {'组':2} {'名字':32s} {'秒':>7} {'Hz':>6} {'rms':>6} {'峰':>6} {'削波':>6} {'判定':6} 说明")
    print("-" * 132)
    for i, c in enumerate(候, 1):
        尺 = lambda v, f="{:.2f}": (f.format(v) if isinstance(v, (int, float)) else "—")  # noqa: E731
        print(f"{i:>2} {c['组']:2} {c['名字'][:31]:32s} {尺(c['秒']):>7} "
              f"{str(c['采样率'] or '—'):>6} {尺(c['rms'], '{:.3f}'):>6} {尺(c['峰'], '{:.3f}'):>6} "
              f"{尺(c['削波'], '{:.3f}'):>6} {c['判定']:6} {c['理由'][:40]}")
        # 顺带核对：这条现在还能不能按路径点出来（名字改了/文件挪了都会在这里露出来）
        try:
            参 = 配音.参考音频(c["相对"])
            记 = "✓按路径可点" if Path(参["路径"]).is_file() else "✗文件不在"
        except Exception as e:  # noqa: BLE001
            记 = f"✗ {type(e).__name__}: {str(e)[:50]}"
        print(f"{'':>2} {'':2} └─ {记}  {c['相对']}")
    return 0


def main() -> int:
    参 = sys.argv[1:]

    if "--列候选" in 参 or "--候选" in 参:
        配音 = 装配音()
        return 列候选(配音)

    文 = 默认台词
    音 = None
    语 = "ZH"
    速 = 1.0
    第几条 = None
    上限 = 1800.0

    位 = []
    i = 0
    while i < len(参):
        if 参[i] == "--语速" and i + 1 < len(参):
            速 = float(参[i + 1]); i += 2
        elif 参[i] == "--语言" and i + 1 < len(参):
            语 = 参[i + 1]; i += 2
        elif 参[i] == "--第" and i + 1 < len(参):
            第几条 = int(参[i + 1]); i += 2
        elif 参[i] == "--上限秒" and i + 1 < len(参):
            上限 = float(参[i + 1]); i += 2
        elif 参[i].startswith("--"):
            i += 1
        else:
            位.append(参[i]); i += 1

    if 位:
        文 = 位[0]
    if len(位) > 1:
        音 = 位[1]

    if 音 is None:
        候 = 读候选()
        if 第几条 is not None:
            if not (1 <= 第几条 <= len(候)):
                print(f"✗ --第 只支持 1..{len(候)}")
                return 1
            音 = 候[第几条 - 1]["相对"]
        else:
            音 = 候[0]["相对"] if 候 else 默认相对

    配音 = 装配音()

    print("=" * 108)
    print("影匠 · 真实试音（端到端，真跑 ComfyUI/IndexTTS-2.5）")
    print("=" * 108)
    print(f"  台词    ：{文}")
    print(f"  音色    ：{音}")
    print(f"  语言    ：{语}    语速：{速}")
    print(f"  ComfyUI ：{配音.COMFY}    上限：{上限:.0f} 秒")
    print()

    # ① 体检：缺什么直接说人话，别等 ComfyUI 报一串堆栈
    检 = 配音.体检()
    print(f"  体检    ：{'能跑 ✓' if 检['能跑'] else '不能跑 ✗'}")
    for 行 in 检["报告"]:
        print(f"            {行}")
    if not 检["能跑"]:
        print("\n[失败] 体检没过，先补齐上面缺的东西。")
        return 3

    # ② 参考音频：确认文件真在盘上、时长合不合适
    考 = 配音.参考音频(音)
    print(f"\n  参考音频：{考['名字']}")
    print(f"            {考['路径']}")
    print(f"            {考['秒']} 秒 · {考.get('采样率')} Hz · {考.get('声道')} 声道 · {考.get('大类')}")
    if 考.get("标签"):
        print(f"            标签：{考['标签']}")
    for t in 考["提示"]:
        print(f"            {t}")

    出 = 这里 / "作品" / "配音"
    出.mkdir(parents=True, exist_ok=True)
    名 = f"试音_{考['名字']}_{time.strftime('%H%M%S')}.wav"
    目标 = 出 / 名

    # ③ 真合成
    print(f"\n  开始合成 → {目标}")
    print("  （第一次跑要加载 ~9 GB 权重，几十秒到几分钟都正常；卡住不报错才是问题）")
    始 = time.time()
    try:
        果 = 配音.合成(文, 音, 语言=语, 语速=速, 存到=目标,
                      上限秒=上限,
                     报=lambda m: print(f"    [{time.time() - 始:6.1f}s] {m}"))
    except Exception as e:  # noqa: BLE001
        print(f"\n[失败] 合成没跑通（用时 {time.time() - 始:.1f}s）：")
        print(f"  {type(e).__name__}: {e}")
        if os.environ.get("影匠_堆栈"):
            traceback.print_exc()
        else:
            print("  （要完整堆栈：设 影匠_堆栈=1 再跑）")
        return 3

    路 = Path(果["路"])
    大小 = 路.stat().st_size if 路.is_file() else 0

    print("\n" + "=" * 108)
    print("  ✓ 真出音频了")
    print("=" * 108)
    print(f"  文件    ：{路}")
    print(f"  字节    ：{大小:,}")
    print(f"  时长    ：{果['秒']} 秒")
    print(f"  实际音色：{果['音色']}")
    print(f"  参考音频：{果['参考']}")
    print(f"  种子    ：{果['种子']}")
    print(f"  ComfyUI 耗时：{果['耗时']} 秒")
    print(f"  墙钟    ：{time.time() - 始:.1f} 秒")
    if 果.get("字幕"):
        print(f"  字幕    ：{str(果['字幕'])[:200]}")
    for t in 果["提示"]:
        print(f"  {t}")

    净字 = len([c for c in 文 if not c.isspace() and c not in "，。！？、；：""''（）《》…—·"])
    if 果["秒"]:
        print(f"\n  语速自检：{净字} 净字 / {果['秒']:.2f} 秒 = {净字 / 果['秒']:.2f} 字每秒"
              f"（中文自然语速约 4–6 字/秒）")

    # ④ 证据落盘：把这次运行写进 作品\配音\ 旁边的清单，方便复核
    证 = 出 / "试音记录.jsonl"
    import json
    with 证.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "时间": time.strftime("%Y-%m-%d %H:%M:%S"),
            "文本": 文, "音色请求": 音, "实际音色": 果["音色"],
            "参考": 果["参考"], "语言": 语, "语速": 速,
            "文件": str(路), "字节": 大小, "秒": 果["秒"],
            "ComfyUI耗时": 果["耗时"], "墙钟": round(time.time() - 始, 2),
            "体检": 检["能跑"],
        }, ensure_ascii=False) + "\n")
    print(f"\n  证据追加到：{证}")
    return 0 if 大小 > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
