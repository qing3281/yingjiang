# -*- coding: utf-8 -*-
"""给成片配台词 + 风雪底噪。

    python _配成片.py 试镜                合成台词、垫底噪、混进成片
    python _配成片.py 试镜 --只合成        台词已在，只重混
    python _配成片.py 试镜 --无底噪        只要台词

产物：
    作品\\<戏>\\配音\\台词N_*.wav          每句台词（IndexTTS 出的，后缀是 .wav 但其实是 FLAC）
    作品\\<戏>\\配音\\_台词.srt            字幕
    作品\\<戏>\\片\\_成片_有声.mp4         带声音的成片

时间轴怎么算的：
    每段 3.06 秒，段间交叉溶解吃掉 0.5 秒 →
    第 N 段的起点 = (N-1) × (3.06 - 0.5) = (N-1) × 2.56 秒
"""
import argparse
import json
import os
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 配音  # noqa: E402

FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")
每段秒 = 3.06
转场吃 = 0.5
步长 = 每段秒 - 转场吃


def 段起点(格号):
    return round((格号 - 1) * 步长, 3)


# 台词表：卡在哪一格、说什么、什么情绪。
# 写作要求跟九宫格一致 —— 冷、短、不解释。
台词表 = [
    {"格": 2, "偏": 0.35, "文本": "雪落了三天。没有人来过。", "情感": "Neutral"},
    {"格": 4, "偏": 0.30, "文本": "我等的不是雪停。", "情感": "Neutral"},
    {"格": 6, "偏": 0.20, "文本": "是出鞘的那一刻。", "情感": "Neutral"},
    {"格": 8, "偏": 0.10, "文本": "剑出。雪止。", "情感": "Neutral"},
]


def 合成台词(戏, 音色, 报, 只合成):
    出目录 = os.path.join(根, "作品", 戏, "配音")
    os.makedirs(出目录, exist_ok=True)

    段们 = []
    for i, 条 in enumerate(台词表, 1):
        起 = 段起点(条["格"]) + 条.get("偏", 0)
        存 = os.path.join(出目录, f"台词{i}.wav")
        if 只合成 and os.path.exists(存):
            报(f"  [{i}] 复用 {os.path.basename(存)}")
        else:
            报(f"  [{i}] 格{条['格']} @{起}s  「{条['文本']}」")
            r = 配音.合成(条["文本"], 音色=音色, 情感=条.get("情感"),
                          存到=存, 报=lambda s: None)
            if not r or not os.path.exists(存):
                报(f"      ✗ 合成没出文件")
                continue
            报(f"      ✓ {os.path.getsize(存)/1024:.0f} KB  "
               f"{r.get('ComfyUI耗时', r.get('耗时', '?'))} 秒")
        段们.append({"路": 存, "起": 起, "文本": 条["文本"], "格": 条["格"]})

    # 字幕
    srt = []
    for i, s in enumerate(段们, 1):
        # 估时长：中文自然语速取 4.5 字/秒，再加 0.4 秒尾巴
        d = len(s["文本"]) / 4.5 + 0.4
        a, b = s["起"], s["起"] + d
        srt.append(f"{i}\n{_时(a)} --> {_时(b)}\n{s['文本']}\n")
    srt路 = os.path.join(出目录, "_台词.srt")
    with open(srt路, "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    报(f"  字幕：{srt路}")
    return 段们


def _时(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def 视频时长(路):
    """问 ffmpeg 要视频长度（秒）。拿不到就退回一个够大的数，宁可长不可短。"""
    import re
    r = subprocess.run([FFMPEG, "-i", 路], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        return 999.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def 混音(戏, 段们, 有声, 底噪, 报, 片名="_成片.mp4"):
    片 = os.path.join(根, "作品", 戏, "片", 片名)
    if not os.path.exists(片):
        报(f"  ✗ 找不到成片 {片}")
        return None

    # 输出名跟着输入名走：_成片.mp4 → _成片_有声.mp4
    #                        _成片_双线.mp4 → _成片_双线_有声.mp4
    # 写死 _成片_有声.mp4 会把双线那次的结果覆盖掉（错一次就够了）。
    干, 尾 = os.path.splitext(片名)
    出 = os.path.join(根, "作品", 戏, "片", f"{干}_有声{尾}")
    输入 = [FFMPEG, "-y", "-i", 片]
    链 = []
    idx = 1
    for i, s in enumerate(段们):
        输入 += ["-i", s["路"]]
        # 台词文件后缀是 .wav 其实是 FLAC —— ffmpeg 按魔数认，不用管后缀
        链.append(f"[{idx}:a]adelay={int(s['起']*1000)}|{int(s['起']*1000)},"
                  f"volume=1.0[v{i}]")
        idx += 1

    混合源 = "".join(f"[v{i}]" for i in range(len(段们)))
    滤 = ";".join(链)
    滤 += f";{混合源}amix=inputs={len(段们)}:duration=longest:normalize=0[人声]"

    if 底噪:
        # 风雪底噪：白噪过带通，再压得很低
        滤 += (";anoisesrc=color=brown:amplitude=0.35:duration=60[噪];"
               "[噪]highpass=f=180,lowpass=f=1400,volume=0.055[风]")
        滤 += ";[人声][风]amix=inputs=2:duration=first:normalize=0[混]"
        末 = "[混]"
    else:
        末 = "[人声]"

    滤 += f";{末}alimiter=limit=0.95,apad[aout]"

    # ⚠ 不能加 -shortest：它会把**画面**裁到音频长度。
    # 第一版就踩了 —— 成片从 23.56 秒被砍成 18.65 秒，最后三格直接没了。
    # 画面是主体，音频要跟着画面走：apad 把音轨补到无限长，容器按视频长度收。
    cmd = 输入 + ["-filter_complex", 滤, "-map", "0:v", "-map", "[aout]",
                  "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                  "-t", f"{视频时长(片)}", 出]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(出):
        报(f"  ✗ 混音失败：{(r.stderr or '')[-500:]}")
        return None
    return 出


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--只合成", action="store_true")
    ap.add_argument("--无底噪", action="store_true")
    ap.add_argument("--音色", default="")
    ap.add_argument("--片", default="_成片.mp4", help="要配音的那条片（片\\ 下的文件名）")
    参 = ap.parse_args()

    def 报(s):
        print(s, flush=True)

    音色 = 参.音色
    if not 音色:
        音色, 源 = 配音.角色定音色("凌霜")
        报(f"音色：{音色}（来源 {源}）")

    报("\n══ 合成台词 ══")
    段们 = 合成台词(参.戏, 音色, 报, 参.只合成)
    if not 段们:
        报("✗ 一句都没成")
        return 1

    报("\n══ 混音 ══")
    出 = 混音(参.戏, 段们, None, not 参.无底噪, 报, 片名=参.片)
    if not 出:
        return 1

    r = subprocess.run([FFMPEG, "-i", 出], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    import re
    秒 = re.search(r"Duration:\s*(\S+),", r.stderr or "")
    报(f"\n✓ 有声成片：{出}")
    报(f"  {秒.group(1) if 秒 else '?'}  {os.path.getsize(出)/1048576:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
