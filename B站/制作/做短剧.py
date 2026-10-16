# -*- coding: utf-8 -*-
"""做短剧.py —— 把「剧本.json」一路做成带对白、字幕、BGM 的成片。

跟 出片.py 的区别：
  出片.py 只管画面（静帧运镜 / Wan 动态镜头），镜头时长是写死的。
  做短剧.py 多一层「声音优先」：先按台词把配音合成出来，**用配音的实际长度反推每个镜头该停多久**，
  再把旁白按精确时间点铺回成片。短剧的节奏是台词定的，不是拍脑袋定 4 秒。

流程：
  1) 收集剧本里所有 `说` 字段 → 调 配音生成.py（IndexTTS-2）批量出 wav
  2) 用 wav 长度算每个镜头的 `秒`（= 台词长 + 前留白 + 后留白，且有下限）
  3) 把算好的时长写回一份派生剧本，交给 出片.py 出图/动态/合成（画面 + 字幕）
  4) 按镜头累计时间算出旁白表（每句的绝对起点），调 配音.py 把对白和 BGM 混上去

用法：
  python 做短剧.py 剧本.json
  python 做短剧.py 剧本.json --只配音          # 只跑 TTS，听一遍台词
  python 做短剧.py 剧本.json --跳过配音        # 复用已有 wav，只重算时长并出片
  python 做短剧.py 剧本.json --出图线 qwen --线 14b
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

本目录 = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
配音生成器 = os.path.join(本目录, "配音生成.py")
出片器 = os.path.join(本目录, "出片.py")
混音器 = os.path.join(本目录, "配音.py")
# IndexTTS-2 装在 D:\tts（B站 这个中文目录名会让 kaldifst/sentencepiece 打不开文件，
# 所以那边做了 junction；跑 TTS 必须用 D:\tts 下的解释器）
TTS_PY = r"D:\tts\venv\Scripts\python.exe"

# 台词前后的留白：前面留一点让观众看清画面，后面留一点让情绪落地
前留白 = 0.45
后留白 = 0.75
最短镜 = 1.6          # 没台词的镜头也别短于这个
最长镜 = 12.0         # 防止某句特别长把节奏拖垮


def 报(*a):
    print(*a, flush=True)


def 读时长(路: str) -> float:
    """任意媒体文件的时长（秒）。

    ⚠ 不能只看音频流：Wan 出来的动态镜头是**没有音轨**的 mp4，
    只读 streams.audio 会返回 0，把整条时间轴算塌（实测旁白因此提前 24 秒）。
    """
    import av
    with av.open(路) as c:
        if c.duration:
            return float(c.duration / 1000000.0)
        最长 = 0.0
        for s in c.streams:
            if s.duration is not None and s.time_base is not None:
                最长 = max(最长, float(s.duration * s.time_base))
        return 最长


def 读实际时长(输出目录, 镜头表, 时长表):
    """每个镜头在成片里真正占多长。

    静帧镜头严格等于计划的秒数；动态/有声镜头是生成出来的媒体，多长就是多长。
    """
    实际 = []
    for i, (镜, 计) in enumerate(zip(镜头表, 时长表), 1):
        for 子目录 in ("动", "声"):
            路 = os.path.join(输出目录, 子目录, f"{i:02d}.mp4")
            if os.path.isfile(路) and os.path.getsize(路) > 10000:
                try:
                    实际.append(round(读时长(路), 4))
                except Exception:
                    实际.append(计)
                break
        else:
            实际.append(计)
    return 实际


def 出配音(剧本, 输出目录):
    说目录 = os.path.join(输出目录, "说")
    os.makedirs(说目录, exist_ok=True)

    台词 = []
    归属 = {}          # 台词文件 → 镜头序号
    for i, 镜 in enumerate(剧本["镜头"], 1):
        话 = (镜.get("说") or "").strip()
        if not 话:
            continue
        文件名 = f"{i:03d}.wav"
        项 = {"文本": 话, "文件": 文件名}
        if 镜.get("参考"):
            项["参考"] = 镜["参考"]
        if 镜.get("情绪"):
            项["情绪"] = 镜["情绪"]
        台词.append(项)
        归属[文件名] = i

    if not 台词:
        报("剧本里没有 `说` 字段，这活儿该交给 出片.py")
        return {}

    台词本 = os.path.join(输出目录, "_台词本.json")
    with open(台词本, "w", encoding="utf-8") as f:
        json.dump(台词, f, ensure_ascii=False, indent=2)

    if not os.path.isfile(TTS_PY):
        报(f"❌ 找不到 TTS 解释器 {TTS_PY}")
        sys.exit(1)

    报(f"\n配音：{len(台词)} 句 → {说目录}")
    cmd = [TTS_PY, 配音生成器, "--脚本", 台词本, "--输出目录", 说目录]
    if 剧本.get("参考"):
        cmd += ["--参考", 剧本["参考"]]
    if 剧本.get("情绪模式"):
        cmd += ["--情绪模式"]
    子 = subprocess.run(cmd, capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    for 行 in (子.stdout or "").strip().splitlines():
        if 行.strip():
            报("   " + 行.strip())
    if 子.returncode != 0:
        报("❌ 配音失败：")
        报((子.stderr or "")[-2000:])
        sys.exit(1)

    结果 = {}
    for 文件名, i in 归属.items():
        路 = os.path.join(说目录, 文件名)
        if os.path.isfile(路) and os.path.getsize(路) > 1000:
            结果[i] = 路
        else:
            报(f"   ⚠ 镜头 {i} 的配音没出来：{路}")
    return 结果


def 算时长(剧本, 配音表):
    """用配音实际长度反推每个镜头该停多久，返回 (新镜头表, 每镜秒数表)。"""
    镜头表 = 剧本["镜头"]
    全局每张 = float(剧本.get("每张秒", 3.5))
    时长表 = []
    for i, 镜 in enumerate(镜头表, 1):
        指定 = 镜.get("秒")
        音路 = 配音表.get(i)
        if 音路:
            需 = 读时长(音路) + 前留白 + 后留白
            需 = max(需, 最短镜)
            if 指定 is not None:
                需 = max(需, float(指定))      # 写了 `秒` 就当它是下限
        else:
            需 = float(指定) if 指定 is not None else 全局每张
        需 = min(需, 最长镜)
        时长表.append(round(需, 3))
    return 时长表


def main():
    ap = argparse.ArgumentParser(
        description="剧本 → 配音 → 出图 → 合成 → 混音（一站式做短剧）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("剧本", nargs="?", help="剧本 json 路径")
    ap.add_argument("--只配音", action="store_true", help="只跑 TTS，不出片")
    ap.add_argument("--跳过配音", action="store_true", help="复用已有 wav（改了画面想重出时用）")
    ap.add_argument("--跳过混音", action="store_true", help="只出无声画面")
    ap.add_argument("--出图线", choices=["zimage", "qwen"], default=None)
    ap.add_argument("--线", choices=["5b", "14b"], default=None)
    ap.add_argument("--跳过动态", action="store_true")
    ap.add_argument("--跳过有声", action="store_true")
    ap.add_argument("--只合成", action="store_true")
    ap.add_argument("--示例", action="store_true", help="打印一个剧本样例")
    args = ap.parse_args()

    if args.示例 or not args.剧本:
        print(json.dumps(示例剧本, ensure_ascii=False, indent=2))
        return

    with open(args.剧本, encoding="utf-8") as f:
        剧本 = json.load(f)

    标题 = 剧本.get("标题", "短剧")
    输出目录 = 剧本.get("输出目录") or os.path.join(os.path.dirname(os.path.abspath(args.剧本)), 标题)
    os.makedirs(输出目录, exist_ok=True)
    镜头表 = 剧本["镜头"]

    报(f"《{标题}》 {len(镜头表)} 个镜头")
    报(f"输出 {输出目录}")

    # ---------- 1) 配音 ----------
    说目录 = os.path.join(输出目录, "说")
    配音表 = {}
    if args.跳过配音:
        for i, 镜 in enumerate(镜头表, 1):
            if (镜.get("说") or "").strip():
                路 = os.path.join(说目录, f"{i:03d}.wav")
                if os.path.isfile(路):
                    配音表[i] = 路
        报(f"\n复用已有配音 {len(配音表)} 句")
    else:
        配音表 = 出配音(剧本, 输出目录)
        if args.只配音:
            报(f"\n✅ 配音好了，先去听一遍：{说目录}")
            return

    # ---------- 2) 按配音长度算镜头时长 ----------
    时长表 = 算时长(剧本, 配音表)
    总时长 = sum(时长表) - float(剧本.get("转场秒", 0.6)) * max(0, len(时长表) - 1)
    报(f"\n镜头时长（按台词长度算）")
    for i, (镜, 秒) in enumerate(zip(镜头表, 时长表), 1):
        话 = (镜.get("说") or "").strip()
        音 = f"配音 {读时长(配音表[i]):.2f}s" if i in 配音表 else "无台词"
        报(f"   {i:02d}  {秒:>6.2f}s  {音:<12}  {话[:26] or 镜['提示词'][:26]}")
    报(f"   预计成片 {总时长:.1f}s = {int(总时长//60)}分{总时长%60:.0f}秒")

    # ---------- 3) 派生剧本交给 出片.py ----------
    派生 = dict(剧本)
    派生["镜头"] = [dict(镜, 秒=秒) for 镜, 秒 in zip(镜头表, 时长表)]
    # 画面这一层不加 BGM（BGM 留到混音那步统一加，免得加两遍）
    派生.pop("BGM", None)
    派生["输出目录"] = 输出目录
    派生路径 = os.path.join(输出目录, "_派生剧本.json")
    with open(派生路径, "w", encoding="utf-8") as f:
        json.dump(派生, f, ensure_ascii=False, indent=2)

    cmd = [PY, 出片器, 派生路径]
    if args.出图线:
        cmd += ["--出图线", args.出图线]
    if args.线:
        cmd += ["--线", args.线]
    if args.跳过动态:
        cmd += ["--跳过动态"]
    if args.跳过有声:
        cmd += ["--跳过有声"]
    if args.只合成:
        cmd += ["--只合成"]
    cmd += ["--不释放显存"]
    报("")
    子 = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace")
    if 子.returncode != 0:
        报("❌ 出片失败")
        sys.exit(1)

    无声片 = os.path.join(输出目录, f"{标题}.mp4")
    if not os.path.isfile(无声片):
        报(f"❌ 没找到成片 {无声片}")
        sys.exit(1)

    # ---------- 4) 混音：把每句台词铺到它的镜头上 ----------
    if args.跳过混音 or not 配音表:
        if not 配音表:
            报("\n没有台词，跳过混音")
        报(f"\n✅ 成片（无声）{无声片}")
        return

    # 每个镜头的起点 = 前面所有镜头时长之和 - 转场累计（转场时两镜重叠）
    #
    # ⚠ 这里必须用「实际」时长，不能用上面的计划时长：
    #   动态镜头交给 Wan 之后，出来多长就是多长（计划 9 秒可能只有 4.8 秒），
    #   静帧镜头才严格按计划的秒数走。拿计划值算旁白表，第一个动态镜头之后的
    #   每一句都会偏晚，而且误差累积（实测 24 镜累计偏了 10.6 秒）。
    实际表 = 读实际时长(输出目录, 镜头表, 时长表)
    偏差 = sum(b - a for a, b in zip(时长表, 实际表))
    if abs(偏差) > 0.05:
        报(f"\n⚠ 实际时长与计划差 {偏差:+.2f}s（动态镜头以 Wan 实际出片长度为准）")
        for i, (计, 实) in enumerate(zip(时长表, 实际表), 1):
            if abs(计 - 实) > 0.05:
                报(f"   镜头 {i:02d}  计划 {计:.2f}s  实际 {实:.2f}s")

    转场 = float(剧本.get("转场秒", 0.6))
    旁白表 = []
    走 = 0.0
    for i, 秒 in enumerate(实际表, 1):
        if i in 配音表:
            旁白表.append({
                "文件": 配音表[i].replace("\\", "/"),
                "起始": round(走 + 前留白, 3),
                "镜头": i,
            })
        走 += 秒 - (转场 if i < len(时长表) else 0.0)

    旁白表路径 = os.path.join(输出目录, "_旁白表.json")
    with open(旁白表路径, "w", encoding="utf-8") as f:
        json.dump(旁白表, f, ensure_ascii=False, indent=2)

    有声片 = os.path.join(输出目录, f"{标题}_有声.mp4")
    混音 = [PY, 混音器, "--视频", 无声片, "--旁白表", 旁白表路径,
            "--输出", 有声片, "--旁白音量", str(剧本.get("旁白音量", 1.0))]
    bgm = 剧本.get("BGM")
    if bgm and os.path.isfile(bgm):
        混音 += ["--bgm", bgm, "--bgm音量", str(剧本.get("BGM音量", 0.16))]
    elif bgm:
        报(f"⚠ 找不到 BGM，跳过：{bgm}")

    报("")
    子 = subprocess.run(混音, text=True, encoding="utf-8", errors="replace")
    if 子.returncode != 0:
        报("❌ 混音失败")
        sys.exit(1)

    报(f"\n{'='*60}")
    报(f"✅ 有声成片 {有声片}")
    报(f"   {os.path.getsize(有声片)/1024/1024:.1f} MB  {总时长:.1f}s")
    报(f"\n下一步是审片：")
    报(f"   python 审片.py \"{输出目录}\"")


示例剧本 = {
    "标题": "今天别开门",
    "画布": "1920x1080",
    "转场秒": 0.6,
    "每张秒": 3.5,
    "风格前缀": "cinematic film still, night, moody low-key lighting, cold cyan and sodium-orange palette, 35mm film grain, ",
    "角色": "a lone tired man in his thirties, short black hair, grey hoodie under a dark jacket, gaunt face, ",
    "BGM": "D:\\DSHworkspace\\B站\\素材\\BGM\\flatwound_-_The_Long_Goodbye.mp3",
    "BGM音量": 0.16,
    "出图线": "zimage",
    "镜头": [
        {"提示词": "walking up a dim stairwell, hand on the railing",
         "说": "今天也别开门。", "字幕": "今天也别开门。", "运镜": "推近"},
        {"提示词": "a folded note taped to the door, close up",
         "说": "第七天了。", "字幕": "第七天。", "运镜": "右到左"},
        {"提示词": "standing in a dark hallway, seen from behind",
         "字幕": "", "运镜": "静止", "动态": 3.0},
    ],
}


if __name__ == "__main__":
    main()
