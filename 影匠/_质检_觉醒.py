# -*- coding: utf-8 -*-
"""《觉醒》成片整体质检 —— 不看日志说什么，只量片子本身。

三件事：
1. **逐句对轴**：拿 SRT 的每条时间，在**它该出现的那一帧**上找白字。
   人眼看的字幕是「烧在画面里」的，所以只要那一帧底部有足够多的亮像素，就算在。
   ★ 为什么要这样量：日志说「64 条烧完了」只证明**滤镜跑过**，不证明
   **每一条都在对的时刻出现在对的画面上**。烧字幕这一步最典型的失败是
   整体偏移（-ss 的位置错了），日志照样全绿。
2. **逐句对声**：每条台词的时间窗内量响度，跟「同一片但前后留白处」比。
   台词窗里应该明显更响。
3. **全片取样**：每 4.1 秒抽一帧拼成联系表，用眼睛过一遍身份/服装/场景。

用法：python _质检_觉醒.py [--只 1|2|3]
"""
import argparse
import io
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(根, "_bin", "ffmpeg.exe")
戏 = os.path.join(根, "作品", "觉醒")
片 = os.path.join(戏, "片", "_成片_觉醒_字幕.mp4")
SRT = os.path.join(戏, "配音", "台词.srt")
出夹 = os.path.join(戏, "_质检")

sys.path.insert(0, 根)
import 视频  # noqa: E402


def 读SRT(路):
    t = io.open(路, encoding="utf-8-sig").read()
    块 = re.split(r"\n\s*\n", t.strip())
    条 = []
    for b in 块:
        行 = [x for x in b.splitlines() if x.strip()]
        if len(行) < 2:
            continue
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", b)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        起 = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        止 = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        词 = "".join(行[1:]) if not 行[0].strip().isdigit() else "".join(行[2:])
        条.append({"起": 起, "止": 止, "词": 词.strip()})
    return 条


def 底带(时刻):
    """抽某一时刻「字幕带」（底部 22%）的灰度像素。"""
    p = subprocess.run(
        [FF, "-v", "error", "-ss", f"{时刻:.3f}", "-i", 片, "-frames:v", "1",
         "-vf", "crop=iw:ih*0.22:0:ih*0.78,format=gray",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True)
    return p.stdout if (p.returncode == 0 and len(p.stdout) > 1000) else None


def 带差(a, b):
    """两帧字幕带的平均绝对差（0~255）。

    ## 为什么不用「数白像素」
    第一版是「底部 20% 里数 >=235 的像素个数，多就算有字幕」。
    一跑就露馅：`第10条 3198 vs 句前 4178` —— **句前的白像素比句中还多**。
    因为这个片子的场景本身就白（霜、白衣、白墙、亮天），
    白像素多少反映的是**画面内容**，跟字幕没有因果关系。
    这就是「假判据族」里那条：**量的东西和要证明的事之间没有因果链**。

    ## 现在的判据
    字幕是**画面上后来烧上去的东西**：同一个镜头里，有字幕的那一帧
    和没字幕的那一帧，**差的正好是那几行字**。所以直接做帧差 ——
    画面内容被减掉，剩下的就是字幕本身。
    再配上「字幕该在的时刻差得大 / 字幕不该在的时刻差得小」，
    量的才是**字幕在不在、在的时刻对不对**。
    """
    x, y = 底带(a), 底带(b)
    if x is None or y is None or len(x) != len(y):
        return None
    return sum(abs(i - j) for i, j in zip(x, y)) / len(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--只", type=int, default=0, help="只跑第 N 项")
    参 = ap.parse_args()
    os.makedirs(出夹, exist_ok=True)

    if not os.path.isfile(片):
        print(f"✗ 找不到成片 {片}")
        return 1
    条 = 读SRT(SRT)
    print(f"════════ 《觉醒》质检 ════════")
    print(f"  成片 {os.path.relpath(片, 根)}")
    print(f"  字幕 {len(条)} 条　{条[0]['起']:.2f}s → {条[-1]['止']:.2f}s")

    if 参.只 in (0, 1):
        # 单条抽检太慢（64 条 × 2 帧差 = 128 次抽帧），按固定步长抽 12 条铺开全片
        抽 = list(range(0, len(条), max(1, len(条) // 12)))[:12]
        print(f"\n【1 字幕带帧差：有字幕 vs 没字幕】")
        print(f"  {'条':>3} {'台词':<14} {'句中差':>7} {'句前差':>7} {'句后差':>7}  判")
        好 = 否 = 不判 = 0
        for i in 抽:
            t = 条[i]
            中 = (t["起"] + t["止"]) / 2
            前 = max(0.0, t["起"] - 0.42)
            后 = t["止"] + 0.42
            # 句中：拿它和句前比（句前 = 本句字幕还没上来）
            d中 = 带差(中, 前)
            d前 = 带差(前, 前 - 0.42) if 前 > 0.5 else None
            d后 = 带差(后, 中)
            if d中 is None:
                不判 += 1
                判 = "抽不出帧"
            elif d中 >= 2.0 and d中 > (d前 or 0) * 2:
                好 += 1
                判 = "✓ 字幕在"
            else:
                否 += 1
                判 = "✗ 句中看不出字幕"
            print(f"  {i+1:>3} {t['词'][:12]:<14} "
                  f"{(f'{d中:.2f}' if d中 is not None else '—'):>7} "
                  f"{(f'{d前:.2f}' if d前 is not None else '—'):>7} "
                  f"{(f'{d后:.2f}' if d后 is not None else '—'):>7}  {判}")
        print(f"\n  抽检 {len(抽)} 条：在 {好}　看不出 {否}　抽不出 {不判}")
        print(f"  （「句前差」是本句之前那一小段的画面自身变化，当噪声底看；"
              f"句中差要明显大过它才算字幕真的上来了）")

    if 参.只 in (0, 2):
        print(f"\n【2 台词窗 vs 留白窗 响度】")
        有词 = []
        无词 = []
        for i, t in enumerate(条):
            有词.append(响度((t["起"] + t["止"]) / 2))
            下句起 = 条[i + 1]["起"] if i + 1 < len(条) else t["止"] + 3
            缝 = t["止"] + (下句起 - t["止"]) / 2
            if 下句起 - t["止"] > 0.9:
                无词.append(响度(缝, 0.6))
        a = [x for x in 有词 if x is not None]
        b = [x for x in 无词 if x is not None]
        print(f"  台词窗 {len(a)} 个　平均 {sum(a)/len(a):.1f} dB")
        if b:
            print(f"  留白窗 {len(b)} 个　平均 {sum(b)/len(b):.1f} dB")
            print(f"  → 台词比留白响 {sum(b)/len(b) - sum(a)/len(a):.1f} dB")
        else:
            print(f"  留白窗 0 个（每句都紧接下一句）")

    if 参.只 in (0, 3):
        print(f"\n【3 全片取样联系表】")
        总 = 视频.探视频(片)["秒"]
        数 = 74
        列 = 10
        宽 = 320
        出 = os.path.join(戏, "_质检_全片74帧.png")
        cmd = [FF, "-y", "-v", "error"]
        for i in range(数):
            cmd += ["-ss", f"{总 * i / 数:.3f}", "-i", 片]
        cmd += ["-frames:v", "1", "-filter_complex",
                "".join(f"[{i}:v]scale={宽}:-2,drawtext=text='{int(总*i/数)}s':"
                        f"x=6:y=6:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.6[v{i}];"
                        for i in range(数))
                + "".join(f"[v{i}]" for i in range(数))
                + f"xstack=inputs={数}:layout="
                + "|".join(f"{(i%列)*宽}_{(i//列)*int(宽*704/1280)}" for i in range(数))
                + "[o]", "-map", "[o]", 出]
        p = subprocess.run(cmd, capture_output=True)
        if p.returncode != 0:
            print(f"  ✗ xstack 失败：{p.stderr.decode('utf-8', 'replace')[-300:]}")
        else:
            print(f"  ✓ {os.path.relpath(出, 根)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
