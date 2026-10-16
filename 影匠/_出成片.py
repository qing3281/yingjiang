# -*- coding: utf-8 -*-
"""
出成片 —— 把九宫格图逐格变成视频，再合成一条完整短片。

    python _出成片.py 试镜              出全部九格 + 合成
    python _出成片.py 试镜 --只格 3,4   只出指定格（调试用）
    python _出成片.py 试镜 --只合成      图都齐了，只重新合成

产物：
    作品\<戏>\片\格N.mp4           每格一段
    作品\<戏>\片\_成片.mp4         合成结果
    作品\<戏>\片\_清单.txt         每格的种子/时长/提示词（可复现）
"""
import os
import re
import sys
import json
import time
import shutil
import subprocess

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 导演  # noqa: E402

FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")


# ── 每一格「怎么动」──
# 只写动作，不写「是什么」—— 长相由参考图和提示词管。
# 顺序对应 02-九宫格.md 里的格 1..9。
动作表 = {
    1: "风把地表的雪吹成一道低低的雪雾贴着地面流动，远处那个身影的衣摆被风吹得轻微摆动，镜头极缓慢地向前推",
    2: "她一步一步在没膝的积雪里向前走，银白长发被风吹到身后飘起，长袍下摆在雪地上拖出一道浅浅的痕迹",
    3: "她忽然停住脚步，缓缓抬起头望向远方，风吹动衣摆和袖口，她抬手把额前被雪打湿的一缕头发拨开",
    4: "她的右手缓缓抬起来按在腰间的剑柄上，指节慢慢收紧，风吹动垂在肩上的长发，镜头轻微下压",
    5: "她缓缓闭上眼睛，睫毛上的细雪簌簌落下，胸口缓缓起伏，呼出的白气在面前慢慢散开",
    6: "她缓缓睁开眼睛，紫色瞳孔在冷光里慢慢变亮，眼神从犹豫转成没有退路的冷静，头发丝在脸侧轻轻浮动",
    7: "剑锋缓缓出鞘三寸，冷硬的金属反光横着划过画面，映在剑身上的一只眼睛微微眨动，一线细雪从鞘口带出来",
    8: "她猛地把剑拔出鞘，衣摆被动作带着高高扬起，长发向后飞散，脚边的积雪被震起半人高，碎雪在冷光里炸开成一层白雾",
    9: "她垂着手把剑立在身侧，剑尖几乎点进雪里，长发慢慢落回肩上，衣摆摆动的幅度越来越小，最后静止",
}


def 读格(戏):
    """从 02-九宫格.md 读出格号 → 标题，用来给产物命名。"""
    p = os.path.join(根, "作品", 戏, "02-九宫格.md")
    if not os.path.exists(p):
        return {}
    头 = re.compile(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$")
    表 = {}
    for 行 in open(p, encoding="utf-8"):
        m = 头.match(行)
        if m:
            表[int(m.group(1))] = m.group(2)
    return 表


def 找图(戏, 号):
    """九宫格图在这几个命名里找一个。"""
    d = os.path.join(根, "作品", 戏)
    for 名 in (f"01_格{号}.png", f"格{号}.png", f"0{号}_格{号}.png"):
        p = os.path.join(d, 名)
        if os.path.exists(p):
            return p
    return None


def 出格(戏, 号, 表, 报):
    """一格的图 → 一段视频。返回产物路径，失败返回 None。"""
    图 = 找图(戏, 号)
    if not 图:
        报(f"  ✗ 格{号}：找不到图")
        return None
    标题 = 表.get(号, f"格{号}")
    动 = 动作表.get(号)
    if not 动:
        报(f"  ✗ 格{号}：动作表里没有第 {号} 格")
        return None

    报(f"  格{号} —— {标题}")
    t = time.time()
    try:
        果 = 导演.让镜动({"路": 图, "种子": 1735946766}, 动,
                          帧数=49, 帧宽=帧宽, 帧高=帧高, 报=报)
    except Exception as e:
        报(f"    ✗ {type(e).__name__}: {e}")
        return None
    报(f"    ✓ {os.path.basename(果['路'])}  {time.time()-t:.1f} 秒")
    return 果


转场 = "交叉溶解"      # 段间转场；设为 None 或 "" 就是硬切
每段转场 = 0.5         # 每种软转场吃掉多少秒
帧宽, 帧高 = 832, 480  # 每段的出片尺寸；命令行 --宽/--高 可覆盖


def 合成(戏, 格表, 报):
    """把各格 mp4 按顺序拼成一条。"""
    片目录 = os.path.join(根, "作品", 戏, "片")
    各段 = []
    for 号 in sorted(格表):
        # 让镜动 把 mp4 放在「图片自己所在的目录」（也就是 作品\<戏>\），
        # 不是 片\ 子目录 —— 两处都找，免得再踩一次。
        for 目录 in (片目录, os.path.join(根, "作品", 戏)):
            for 名 in (f"格{号}.mp4", f"01_格{号}.mp4"):
                p = os.path.join(目录, 名)
                if os.path.exists(p):
                    各段.append(p)
                    break
            else:
                continue
            break
    if not 各段:
        报("  ✗ 一段都没出，没法合成")
        return None
    if len(各段) == 1:
        报("  只有一段，直接当成品")
        return 各段[0]

    清单 = os.path.join(片目录, "_concat.txt")
    with open(清单, "w", encoding="utf-8") as f:
        for p in 各段:
            f.write(p + "\n")          # 裸路径，一行一个（视频.接片 认这个格式）

    out = os.path.join(片目录, "_成片.mp4")
    if os.path.exists(out):
        os.remove(out)

    # 走剪辑层：段间加交叉溶解。没有软转场时 视频.接片 自己退回 concat -c copy，不重编码。
    # 转场会吃掉每段 0.5 秒，所以成片比各段之和短 —— 这是对的，不是 bug。
    if 转场:
        报(f"  合成 {len(各段)} 段（转场 {转场} {每段转场}秒）→ {os.path.basename(out)}")
        try:
            import 视频
            r = 视频.接片(清单路=清单, 转场=转场, 每段=每段转场, 存到=out)
            if r and os.path.exists(out):
                return out
            报(f"  ⚠ 接片没出片，退回硬切 concat")
        except Exception as e:
            报(f"  ⚠ 接片炸了（{type(e).__name__}: {e}），退回硬切 concat")

    报(f"  合成 {len(各段)} 段（硬切）→ {os.path.basename(out)}")
    r = subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", 清单, "-c", "copy", out],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(out):
        报(f"  ✗ 合成失败：{(r.stderr or '')[-400:]}")
        return None
    return out


def 探时长(路):
    """问 ffmpeg 要时长和帧数，用来写清单。"""
    r = subprocess.run([FFMPEG, "-i", 路], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    文 = (r.stderr or "")
    秒 = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", 文)
    帧 = re.search(r"(\d+)\s+fps", 文)
    尺寸 = re.search(r"(\d{2,5})x(\d{2,5})", 文)
    d = {}
    if 秒:
        d["秒"] = int(秒.group(1)) * 3600 + int(秒.group(2)) * 60 + float(秒.group(3))
    if 帧:
        d["帧率"] = int(帧.group(1))
    if 尺寸:
        d["尺寸"] = f"{尺寸.group(1)}x{尺寸.group(2)}"
    return d


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    戏 = sys.argv[1]
    参 = sys.argv[2:]

    只合成 = "--只合成" in 参
    只格 = None
    if "--只格" in 参:
        i = 参.index("--只格")
        if i + 1 < len(参):
            只格 = [int(x) for x in re.split(r"[,，\s]+", 参[i + 1]) if x.strip().isdigit()]

    global 转场, 每段转场, 帧宽, 帧高
    for i, a in enumerate(参):
        if a == "--转场" and i + 1 < len(参):
            转场 = 参[i + 1]
        elif a == "--硬切":
            转场 = None
        elif a == "--每段" and i + 1 < len(参):
            try:
                每段转场 = float(参[i + 1])
            except ValueError:
                pass
        elif a == "--宽" and i + 1 < len(参):
            try:
                帧宽 = int(参[i + 1])
            except ValueError:
                pass
        elif a == "--高" and i + 1 < len(参):
            try:
                帧高 = int(参[i + 1])
            except ValueError:
                pass

    def 报(s):
        print(s, flush=True)

    if not os.path.exists(FFMPEG):
        报(f"✗ 找不到 ffmpeg：{FFMPEG}")
        return 2

    格表 = 读格(戏)
    if not 格表:
        报(f"✗ 读不出 {戏} 的格表（作品\\{戏}\\02-九宫格.md）")
        return 2
    报(f"《{戏}》共 {len(格表)} 格：{', '.join(str(k) for k in sorted(格表))}")

    片目录 = os.path.join(根, "作品", 戏, "片")
    os.makedirs(片目录, exist_ok=True)

    清单 = []
    if not 只合成:
        要出 = 只格 if 只格 else sorted(格表)
        报(f"\n══ 出片 {len(要出)} 格 ══")
        t0 = time.time()
        for n, 号 in enumerate(要出, 1):
            报(f"\n[{n}/{len(要出)}]")
            果 = 出格(戏, 号, 格表, 报)
            if 果:
                清单.append({"格": 号, "标题": 格表.get(号, ""),
                             "路": 果["路"], "种子": 果.get("种子"),
                             "提示词": 果.get("提示词", ""),
                             "耗时": 果.get("耗时")})
        报(f"\n出片合计 {time.time()-t0:.1f} 秒")

    报(f"\n══ 合成 ══")
    成 = 合成(戏, 格表, 报)
    if not 成:
        return 1

    信 = 探时长(成)
    报(f"\n✓ 成片：{成}")
    报(f"  {信.get('尺寸','?')}  {信.get('帧率','?')}fps  "
       f"{信.get('秒',0):.2f} 秒  {os.path.getsize(成)/1048576:.2f} MB")

    # 写清单，方便复现
    p = os.path.join(片目录, "_清单.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"《{戏}》成片清单\n")
        f.write(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"成片：{os.path.basename(成)}  {信.get('尺寸','?')} "
                f"{信.get('帧率','?')}fps {信.get('秒',0):.2f}秒\n")
        f.write(f"角色种子：1735946766（凌霜）\n\n")
        for x in 清单:
            f.write(f"格{x['格']} —— {x['标题']}\n")
            f.write(f"  动作：{x['提示词']}\n")
            f.write(f"  种子：{x['种子']}  耗时：{x['耗时']:.1f}秒\n\n")
    报(f"  清单：{p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
