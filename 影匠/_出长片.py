# -*- coding: utf-8 -*-
"""出长片：把 02-九宫格.md 里的任意格数铺成一部成片（图 → 段 → 接）。

和 `_出成片.py` 的区别：`_出成片.py` 只服务「九格」的试镜（动作表硬编码 1..9），
这个脚本从 md 里读**动作**字段，格数不限 —— 3 分钟的片子四五十格也照跑。

用法：
    python _出长片.py 雪线 --图                  # 只出首帧（1344x768）
    python _出长片.py 雪线 --段                  # 只出视频段（用现有首帧）
    python _出长片.py 雪线 --段 --只格 1,2,3      # 只出指定格
    python _出长片.py 雪线 --段 --端点 远端        # 这一段走远端算力
    python _出长片.py 雪线 --拼                  # 只接片
    python _出长片.py 雪线 --全                  # 图 → 段 → 拼

为什么首帧一律走 z_image_turbo：Qwen-Image-Edit 的参考隐变量会把构图一起锁死
（喂胸像定妆照进去，写死「extreme wide shot」它还你一张胸像），分镜一律不用它。
理由和四组实验记在 `知识\\锁脸.md`。
"""
import argparse
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import 导演          # noqa: E402
import 引擎          # noqa: E402
import 角色库        # noqa: E402

根 = os.path.dirname(os.path.abspath(__file__))
种子 = 1735946766
宽, 高 = 1344, 768
帧数 = 73               # 73 帧 @16fps = 4.56 秒
转场 = "交叉溶解"
每段转场 = 0.5


def 读格(md路):
    """从 02-九宫格.md 抠出每格的 (号, 标题, 景别, 机位, 提示词, 动作)。"""
    文 = open(md路, encoding="utf-8").read()
    块 = re.split(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$", 文, flags=re.M)

    def 取(体, 键):
        m = re.search(rf"^-\s*{键}\s*[:：]\s*(.*)$", 体, flags=re.M)
        return m.group(1).strip() if m else ""

    格 = []
    for i in range(1, len(块), 3):
        体 = 块[i + 2] if i + 2 < len(块) else ""
        格.append({
            "号": int(块[i]),
            "标题": 块[i + 1],
            "景别": 取(体, "景别"),
            "机位": 取(体, "机位"),
            "提示词": 取(体, "提示词"),
            "动作": 取(体, "动作"),
        })
    return 格


def 出首帧(戏, 格, 锚, 角名, 报):
    """一格 → 一张 1344x768 首帧图。返回路径。

    ★ 两条实测出来的写法（第一版全错，踩过）：
    1. **景别必须放在最前面**。原来写成 `{锚}。{提示词}，…，{景别}` —— 角色锚点
       一上来就是「young adult, female, long silver-white hair…」，模型直接被拽去画
       肖像，后面写死 `extreme wide shot` 也没用（格1 该是极远景，出成一张大特写）。
       挪到最前，权重最高，框住了再写字。
    2. **远景不能喂全锚点**。大远景里眼睛什么颜色、眼下有没有痣根本看不见，写了只会
       把机位拉近。远景/全景只给「看得见的那几个」：孤身一人、银白长发、黑色长袍、
       高挑清瘦。
    """
    景 = (格["景别"] or "medium shot").strip()
    远 = 景 in ("extreme wide shot", "wide shot")
    # 大远景/远景**一个角色锚点都不喂**（连 `开镜` 内部那份都要断掉）。
    # 实测三版：① 全锚点在句首 → 大特写；② 短锚点「a single lone figure…」→ 一个
    # 大活人加一个远处小人（「两个人」）；③ 锚点整个不写、但 `角色` 参数照给 ——
    # 还是大特写，因为 `开镜` 自己会把 `角色库.多人串(角)` 拼回提示词里。
    # `角色=[]` 才是真的不喂。人物描写交给提示词自己带（远景里本来就只剩轮廓）。
    词 = f"{景}。{格['提示词']}，冷蓝低饱和，电影写实，硬光长阴影"
    t = time.time()
    r = 导演.开镜(词, 风格="cinematic-real", 角色=([], 角名)[not 远], 种子=种子,
                  宽=宽, 高=高, 文件名=f"01_格{格['号']}", 用定妆照=False)
    路 = r.get("路", "")
    报(f"    ✓ 图 {os.path.basename(路)}  {time.time()-t:.1f} 秒")
    return 路


def 出段(戏, 格, 图路, 端点, 报):
    """一张首帧 → 一段视频。返回产物路径。

    踩过的坑：`让镜动` 落盘用 `<图名>.mp4`（= 01_格N.mp4），本机和远端撞名，
    远端跑完会把本机那段覆盖掉（第一版真删过用户三段片）。所以这里先探端点、
    出完立刻改名成 `段\\格N_<端点>.mp4`，绝不留在原地。
    """
    目录 = os.path.join(根, "作品", 戏)
    段目录 = os.path.join(目录, "段")
    os.makedirs(段目录, exist_ok=True)

    旧 = os.path.join(目录, f"{os.path.splitext(os.path.basename(图路))[0]}.mp4")
    旧备份 = None
    if os.path.exists(旧):
        旧备份 = os.path.join(段目录, f"_临时旧_{os.path.basename(旧)}")
        shutil.copyfile(旧, 旧备份)

    t = time.time()
    果 = 导演.让镜动({"路": 图路, "种子": 种子}, 格["动作"],
                      帧数=帧数, 帧宽=宽, 帧高=高, 报=报)
    新 = 果["路"]
    落点 = os.path.join(段目录, f"格{格['号']}_{端点}.mp4")
    shutil.move(新, 落点)
    # 本机那段要是被顶掉了，还原回去
    if 旧备份:
        shutil.move(旧备份, 旧)
    报(f"    ✓ 段 {os.path.basename(落点)}  {time.time()-t:.1f} 秒 "
        f"{os.path.getsize(落点)/1024/1024:.2f} MB")
    return 落点


def 接片(戏, 号表, 报):
    """段目录里的所有段按格号接成一部成片。同一格有两台机器的，本机优先。"""
    目录 = os.path.join(根, "作品", 戏)
    段目录 = os.path.join(目录, "段")
    # 端点优先级：本机 > 远端（本机的画质是基准）
    清单 = []
    用了 = {"本机": 0, "远端": 0}
    for 号 in 号表:
        for 端 in ("本机", "远端"):
            p = os.path.join(段目录, f"格{号}_{端}.mp4")
            if os.path.exists(p):
                清单.append(p)
                用了[端] += 1
                break
        else:
            报(f"  ⚠ 格{号} 没有段，跳过")

    if not 清单:
        报("  ✗ 一段都没有，接不了")
        return None

    单路 = os.path.join(目录, "_清单.txt")
    with open(单路, "w", encoding="utf-8") as f:
        for p in 清单:
            f.write(p + "\n")

    出 = os.path.join(目录, f"《{戏}》成片.mp4")
    报(f"  接 {len(清单)} 段（本机 {用了['本机']} · 远端 {用了['远端']}）→ "
        f"{os.path.basename(出)}")
    try:
        import 视频
        r = 视频.接片(清单路=单路, 转场=转场, 每段=每段转场, 存到=出)
        路 = r.get("路", 出) if isinstance(r, dict) else 出
    except Exception as e:
        报(f"  ⚠ 接片炸了（{type(e).__name__}: {e}），退回硬切 concat")
        import subprocess
        单 = os.path.join(目录, "_硬切.txt")
        with open(单, "w", encoding="utf-8") as f:
            for p in 清单:
                f.write(f"file '{p}'\n")
        路 = os.path.join(目录, f"《{戏}》成片_硬切.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", 单,
                        "-c", "copy", 路], check=True, capture_output=True)

    if os.path.exists(路):
        秒 = 探时长(路)
        报(f"  ✓ 成片 {os.path.basename(路)}  {宽}x{高}  {秒:.2f} 秒  "
            f"{os.path.getsize(路)/1024/1024:.2f} MB")
        return 路
    return None


def 探时长(路):
    import subprocess
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", 路],
            capture_output=True, text=True, errors="replace")
        return float((r.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--图", action="store_true", help="只出首帧")
    ap.add_argument("--段", action="store_true", help="只出视频段")
    ap.add_argument("--拼", action="store_true", help="只接片")
    ap.add_argument("--全", action="store_true", help="图 → 段 → 拼")
    ap.add_argument("--只格", default="", help="逗号分隔的格号")
    ap.add_argument("--端点", default="本机", choices=["本机", "远端"])
    ap.add_argument("--跳过已有", action="store_true", help="已有的段不重出")
    参 = ap.parse_args()

    戏 = 参.戏
    目录 = os.path.join(根, "作品", 戏)
    md路 = os.path.join(目录, "02-九宫格.md")
    if not os.path.exists(md路):
        print(f"✗ 找不到 {md路}")
        return 1

    def 报(s):
        print(s, flush=True)

    格表 = 读格(md路)
    if not 格表:
        print(f"✗ {md路} 里一格都没读到")
        return 1
    号表 = [g["号"] for g in 格表]
    只要 = set()
    if 参.只格:
        只要 = {int(x) for x in 参.只格.replace("，", ",").split(",") if x.strip()}
    要跑 = [g for g in 格表 if not 只要 or g["号"] in 只要]

    角名 = "凌霜"
    角 = 角色库.取(角名)
    if not 角:
        print(f"✗ 角色库里没有『{角名}』")
        return 1
    导演.立戏(戏, 默认风格="cinematic-real", 默认角色=[角名])
    锚 = 角色库.外貌串(角名)["串"]

    报(f"《{戏}》 {len(格表)} 格 · 本次跑 {len(要跑)} 格 · {宽}×{高} · "
        f"{帧数} 帧/格")

    do图 = 参.图 or 参.全
    do段 = 参.段 or 参.全
    do拼 = 参.拼 or 参.全

    if do段 or do拼:
        端点 = "远端" if 参.端点 == "远端" else "本机"
        引擎.换端点(端点)
        在 = 引擎.在线()
        报(f"端点 {在.get('端点')}  在线 {在.get('在线')}  {在.get('显卡','')}")
        if not 在.get("在线"):
            print("✗ 端点不在线")
            return 1

    成 = 败 = 0
    for g in 要跑:
        号 = g["号"]
        图路 = os.path.join(目录, f"01_格{号}.png")
        if do图:
            报(f"  格{号} —— {g['标题']}")
            if not g["提示词"]:
                报("    ✗ md 里没有提示词")
                败 += 1
                continue
            try:
                图路 = 出首帧(戏, g, 锚, 角名, 报)
                成 += 1
            except Exception as e:
                报(f"    ✗ {type(e).__name__}: {e}")
                败 += 1
                continue

        if do段:
            端名 = "远端" if 参.端点 == "远端" else "本机"
            落点 = os.path.join(目录, "段", f"格{号}_{端名}.mp4")
            if 参.跳过已有 and os.path.exists(落点):
                报(f"  格{号} —— 已有段，跳过")
                continue
            if not os.path.exists(图路):
                报(f"  ✗ 格{号}：没有首帧图 {os.path.basename(图路)}")
                败 += 1
                continue
            if not g["动作"]:
                报(f"  ✗ 格{号}：md 里没有『动作：』字段，图生视频没法动")
                败 += 1
                continue
            报(f"  格{号} —— {g['标题']}")
            try:
                出段(戏, g, 图路, 端名, 报)
                成 += 1
            except Exception as e:
                报(f"    ✗ {type(e).__name__}: {e}")
                败 += 1

    if do拼:
        接片(戏, 号表, 报)

    报(f"\n▶ 收工：成功 {成}　失败 {败}")
    return 0 if 败 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
