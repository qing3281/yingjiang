# -*- coding: utf-8 -*-
"""给长片配音：按格号把台词铺到时间轴上，合成、混音、写字幕。

和 `_配成片.py` 的区别：段长和格数不再写死（那版钉死 3.06 秒 / 9 格），
3 分钟的片子 45 格 × 4.56 秒也照跑。

时间轴的算法跟剪辑层对齐：
    第 N 格的起点 = (N-1) × (每段秒 − 转场吃)
    总时长       = 格数 × 每段秒 − (格数−1) × 转场吃
45 格 × 4.56 − 44 × 0.5 = 183.2 秒 = 3:03。

用法：
    python _配长片.py 雪线                       # 合成 + 混音
    python _配长片.py 雪线 --只合成               # 只为调试台词，不动视频
    python _配长片.py 雪线 --片 "《雪线》成片.mp4"
"""
import argparse
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 配音  # noqa: E402

FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")

# ── 台词表 ──
# 七句，全压在拐点上（剧本 `作品\雪线\剧本.md` 那张表）。其余交给画面和雪。
# `谁` 决定用谁的音色：凌霜 = 角色映射表里的那支；旁白 = 音色库里那支解说女声。
# `偏` 是在本格内的偏移秒数 —— 卡在动作发生之后，不要一进画面就说话。
#
# ★ 2026-10-15 加了第 2 句「没有例外。」——
#   起因是量出来一条：全片的高潮台词「那就没有例外。」落在 151.12s / 182.98s = **82.6%**，
#   而它转的那个词「例外」在此之前**一次都没出现过**。观众到 2:31 才第一次听见「例外」，
#   前面两个半小时（片中时间）看的是一个追、一个跑、一张脸 —— 不知道规矩是什么，
#   所以最后那一剑看着像突然的。
#   《磨刀》讲清了，是因为它的核心矛盾在第 46 秒 / 183 秒 = **25%** 就由人物当面说出来。
#   加这一句，把「例外」这个词提到 **格8 @ 28.4 秒 = 15.5%**，
#   她说的是自己的规矩，最后那句就变成了「她把这规矩用在自己身上」——
#   提前 2 分 3 秒把结尾那一剑的必然性交到观众手里，一个字的情节都没多加。
台词表 = [
    {"格":  1, "偏": 0.6, "谁": "旁白", "文本": "雪线以北，不许有活物。", "情感": "Neutral"},
    {"格":  8, "偏": 0.7, "谁": "凌霜", "文本": "没有例外。",           "情感": "Neutral"},
    {"格": 11, "偏": 0.8, "谁": "凌霜", "文本": "十年了。",             "情感": "Neutral"},
    {"格": 21, "偏": 0.6, "谁": "凌霜", "文本": "站住。",               "情感": "Neutral"},
    {"格": 31, "偏": 1.2, "谁": "凌霜", "文本": "……是我。",            "情感": "Neutral"},
    {"格": 38, "偏": 0.9, "谁": "凌霜", "文本": "那就没有例外。",       "情感": "Neutral"},
    {"格": 45, "偏": 1.4, "谁": "旁白", "文本": "雪线以北，不许有活物。", "情感": "Neutral"},
]

旁白音色 = "磁性御姐音，影视解说气场全开"


def 时(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def 视频时长(路):
    r = subprocess.run([FFMPEG, "-i", 路], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        return 999.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--只合成", action="store_true")
    ap.add_argument("--无底噪", action="store_true")
    ap.add_argument("--每段秒", type=float, default=4.56)
    ap.add_argument("--转场吃", type=float, default=0.5)
    ap.add_argument("--片", default="")
    参 = ap.parse_args()

    def 报(s):
        print(s, flush=True)

    步长 = 参.每段秒 - 参.转场吃
    出目录 = os.path.join(根, "作品", 参.戏, "配音")
    os.makedirs(出目录, exist_ok=True)

    凌霜音, 源 = 配音.角色定音色("凌霜")
    报(f"凌霜音色：{凌霜音}（来源 {源}）")
    报(f"旁白音色：{旁白音色}")
    报(f"时间轴：每段 {参.每段秒}s · 转场吃 {参.转场吃}s · 步长 {步长}s")

    报("\n══ 合成台词 ══")
    段们 = []
    for i, 条 in enumerate(台词表, 1):
        起 = round((条["格"] - 1) * 步长 + 条["偏"], 3)
        存 = os.path.join(出目录, f"台词{i}_{条['谁']}.wav")
        音色 = 凌霜音 if 条["谁"] == "凌霜" else 旁白音色
        报(f"  [{i}] 格{条['格']} @{起}s [{条['谁']}] 「{条['文本']}」")
        if 参.只合成 and os.path.exists(存):
            报(f"      复用 {os.path.basename(存)}")
        else:
            r = 配音.合成(条["文本"], 音色=音色, 情感=条.get("情感"),
                          存到=存, 报=lambda s: None)
            if not r or not os.path.exists(存):
                报("      ✗ 合成没出文件")
                continue
            报(f"      ✓ {os.path.getsize(存)/1024:.0f} KB  "
               f"{r.get('ComfyUI耗时', r.get('耗时', '?'))} 秒")
        段们.append({"路": 存, "起": 起, "文本": 条["文本"], "格": 条["格"], "谁": 条["谁"]})

    if not 段们:
        报("✗ 一句都没成")
        return 1

    srt = []
    for i, s in enumerate(段们, 1):
        d = len(s["文本"]) / 4.5 + 0.5
        srt.append(f"{i}\n{时(s['起'])} --> {时(s['起'] + d)}\n{s['文本']}\n")
    srt路 = os.path.join(出目录, "_台词.srt")
    open(srt路, "w", encoding="utf-8").write("\n".join(srt))
    报(f"  字幕：{srt路}")

    if 参.只合成:
        return 0

    # ── 混音 ──
    片名 = 参.片
    if not 片名:
        候选 = [f for f in os.listdir(os.path.join(根, "作品", 参.戏, "片"))
                if f.endswith(".mp4") and "有声" not in f] \
               if os.path.isdir(os.path.join(根, "作品", 参.戏, "片")) else []
        if not 候选:
            报("✗ 片\\ 下没有成片，先跑 --拼")
            return 1
        片名 = sorted(候选, key=lambda f: -os.path.getsize(
            os.path.join(根, "作品", 参.戏, "片", f)))[0]
        报(f"  自动选中成片：{片名}")

    片 = os.path.join(根, "作品", 参.戏, "片", 片名)
    if not os.path.exists(片):
        报(f"✗ 找不到 {片}")
        return 1

    干, 尾 = os.path.splitext(片名)
    出 = os.path.join(根, "作品", 参.戏, "片", f"{干}_有声{尾}")

    报("\n══ 混音 ══")
    输入 = [FFMPEG, "-y", "-i", 片]
    链, idx = [], 1
    for i, s in enumerate(段们):
        输入 += ["-i", s["路"]]
        毫 = int(s["起"] * 1000)
        # 台词文件后缀写 .wav 其实是 FLAC —— ffmpeg 按魔数认，不用管后缀
        链.append(f"[{idx}:a]adelay={毫}|{毫},volume=1.0[v{i}]")
        idx += 1
    滤 = ";".join(链)
    滤 += f";{''.join(f'[v{i}]' for i in range(len(段们)))}" \
          f"amix=inputs={len(段们)}:duration=longest:normalize=0[人声]"

    总 = 视频时长(片)
    if not 参.无底噪:
        # 风雪底噪：棕噪过带通压得很低，长度跟着片子走
        滤 += (f";anoisesrc=color=brown:amplitude=0.35:duration={总 + 5:.1f}[噪];"
               "[噪]highpass=f=180,lowpass=f=1400,volume=0.055[风]")
        滤 += ";[人声][风]amix=inputs=2:duration=first:normalize=0[混]"
        末 = "[混]"
    else:
        末 = "[人声]"
    滤 += f";{末}alimiter=limit=0.95,apad[aout]"

    # ⚠ 不能加 -shortest：它把**画面**裁到音频长度（踩过，成片从 23.56 秒被砍成 18.65）。
    cmd = 输入 + ["-filter_complex", 滤, "-map", "0:v", "-map", "[aout]",
                  "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                  "-t", f"{总}", 出]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(出):
        报(f"  ✗ 混音失败：{(r.stderr or '')[-700:]}")
        return 1

    报(f"\n✓ 有声成片：{出}")
    报(f"  {视频时长(出):.2f} 秒  {os.path.getsize(出)/1048576:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
