# -*- coding: utf-8 -*-
"""《觉醒》总装：74 格 → 接片 → 头尾卡 → 配音混音 → 烧字幕 → 报规格。

    python _成片_觉醒.py                一路做完
    python _成片_觉醒.py --到 接片       只做到某一步
    python _成片_觉醒.py --查            只报每一步的完成情况，什么都不做

## 步骤链

1. **查段**   74 个 `作品\\觉醒\\段\\格N_本机.mp4` 齐不齐，每格时长是不是 4.4583
2. **接片**   `_拼长片.py 觉醒 --每段秒 4.4583 --转场吃 0.5` → `片\\_成片.mp4`
3. **头尾**   `_加头尾_觉醒.py` 头卡 4.0 秒 + 尾卡 5.0 秒 → `片\\_成片_带头尾.mp4`
4. **配音**   `_配台词_觉醒.py` 出的 64 句 + `_轴.json` → `_配片.py` 混音
5. **字幕**   `_烧字幕.py` 把 `配音\\台词.srt` 烧进画面（硬字幕）
6. **报规格** 时长 / 分辨率 / 帧率 / 音轨 / 大小

**★ 第 4 步的「配音」只是把 `_配台词_觉醒.py` 已经合成好的 wav 混进去**，
**它不会自己合成台词**。整条链的起手式是：

    python _配台词_觉醒.py --头 4.0      # 先合成 64 句 wav + 排轴 + 出 SRT（慢，要 GPU）
    python _成片_觉醒.py --到 字幕        # 再接片 → 头尾 → 混音 → 烧字幕

`_盯到齐就跑.py --真跑` 就是把这两条按顺序串起来的那个守候脚本。

**为什么头卡是 4.0 秒**：`_配台词_觉醒.py` 的默认 `--头 4.0`。
两者必须一致，否则所有台词会整体错位 —— `--头` 改了两边都要改。
"""
import argparse
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FF = os.path.join(根, "_bin", "ffmpeg.exe")
戏 = "觉醒"
段夹 = os.path.join(根, "作品", 戏, "段")
片夹 = os.path.join(根, "作品", 戏, "片")
配夹 = os.path.join(根, "作品", 戏, "配音")

每格秒 = 107 / 24.0
转场吃 = 0.5
头秒 = 4.0
尾秒 = 5.0

步骤 = ["查段", "接片", "头尾", "配音", "字幕", "报规格"]


def 跑(cmd, 报, 要=None):
    报(f"$ {' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd))}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=根)
    尾 = (r.stdout or "").strip().splitlines()
    for 线 in 尾[-14:]:
        报("  " + 线)
    if r.returncode != 0:
        报(f"  ✗ 退出码 {r.returncode}")
        for 线 in ((r.stderr or "").strip().splitlines()[-8:]):
            报("  ! " + 线)
    if 要 and not os.path.exists(要):
        报(f"  ✗ 该出的文件没出来：{要}")
        return False
    return r.returncode == 0


def 探规格(路):
    r = subprocess.run([FF, "-i", 路], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    e = r.stderr or ""
    果 = {}
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", e)
    if m:
        果["秒"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Video:\s*(\w+).*?(\d{2,5})x(\d{2,5}).*?([\d.]+) fps", e)
    if m:
        果["编码"] = m.group(1); 果["宽"] = int(m.group(2))
        果["高"] = int(m.group(3)); 果["帧率"] = float(m.group(4))
    m = re.search(r"Audio:\s*(\w+)", e)
    果["有音频"] = bool(m)
    if m:
        果["音频编码"] = m.group(1)
        m2 = re.search(r"Audio:.*?(\d+) Hz,\s*(\w+)", e)
        if m2:
            果["采样"] = int(m2.group(1)); 果["声道"] = m2.group(2)
    return 果


def 过时(出, *入们):
    """这一步该不该重跑。

    ★ 2026-10-14 踩的坑：以前只判「产物在不在」（`not os.path.exists(出)`）。
    那天换掉了 8 格段文件、跑 `--重接`，**接片重跑了，头尾没重跑** ——
    因为 `_成片_带头尾.mp4` 还在，于是配音、字幕全都接在**一个半小时前的旧片**上，
    最后交出去的成片里那 8 格根本没换。

    判据要量的必须是「这一步的产物是不是这一步的输出来的」。
    所以：产物不存在、或者**比任何一个输入都旧**，就要重跑。
    """
    if not os.path.exists(出):
        return True, "产物不在"
    出时 = os.path.getmtime(出)
    for 入 in 入们:
        if 入 is None or not os.path.exists(入):
            continue
        if os.path.isdir(入):
            内 = [os.path.join(入, f) for f in os.listdir(入)
                  if f.lower().endswith((".mp4", ".json", ".srt", ".wav"))]
            if not 内:
                continue
            新 = max(os.path.getmtime(f) for f in 内)
            名 = os.path.basename(入.rstrip("\\/")) + "\\"
        else:
            新, 名 = os.path.getmtime(入), os.path.basename(入)
        if 新 > 出时 + 1e-6:
            return True, f"输入 {名} 比产物新 {新 - 出时:.0f} 秒"
    return False, "比输入新"


def 查段(报):
    if not os.path.isdir(段夹):
        报(f"  ✗ 没有 {os.path.relpath(段夹, 根)}")
        return False
    # ★ 两条线都要认：`格N_本机.mp4` 和 `格N_远端.mp4`。
    #   只认 `_本机` 的话，双线跑完后这里会报「缺 41–74」把总装挡死 ——
    #   而 `_拼长片.py` 那边是两条线都收的，两边判据不一致。
    #   同一格两条线都出了就挑文件大的（码率高，细节多），与 `_拼长片.py` 一致。
    有 = {}
    for f in os.listdir(段夹):
        m = re.match(r"格(\d+)_(本机|远端)\.mp4$", f)
        if not m:
            continue
        号 = int(m.group(1))
        路 = os.path.join(段夹, f)
        if 号 not in 有 or os.path.getsize(路) > os.path.getsize(有[号][0]):
            有[号] = (路, m.group(2))
    缺 = [i for i in range(1, 75) if i not in 有]
    本 = sum(1 for v in 有.values() if v[1] == "本机")
    远 = sum(1 for v in 有.values() if v[1] == "远端")
    报(f"  段：{len(有)}/74（本机 {本} / 远端 {远}）"
       + (f"　缺 {缺[:10]}{'…' if len(缺) > 10 else ''}" if 缺 else "　齐 ✓"))
    if 缺:
        return False
    # 时长核对（抽 3 格，别 74 个都 ffprobe）
    坏 = []
    for i in (1, 37, 74):
        规 = 探规格(有[i][0])
        s = 规.get("秒", 0)
        if abs(s - 每格秒) > 0.05:
            坏.append(f"格{i}={s}s")
    报(f"  时长抽查：{'、'.join(坏) + ' ✗ 不是 4.4583' if 坏 else '4.4583 秒 ✓'}")
    return not 坏


def main():
    ap = argparse.ArgumentParser()
    # ★ 这个位置参数是后加的。`_盯到齐就跑.py` 里写的是
    #   `_成片_觉醒.py 觉醒 --到 字幕`（带戏名），而这里本来没有位置参数 ——
    #   argparse 遇到多余的位置参数会直接 exit 2，**最后一步总装会静默地不跑**。
    #   两个调用风格都留着：不带就默认「觉醒」，带了就必须对得上。
    ap.add_argument("戏名", nargs="?", default=戏,
                    help=f"默认「{戏}」；本脚本目前只支持这一个")
    ap.add_argument("--到", default="报规格", choices=步骤)
    ap.add_argument("--查", action="store_true")
    ap.add_argument("--重接", action="store_true", help="已接好的也重接")
    参 = ap.parse_args()

    if 参.戏名 != 戏:
        print(f"✗ 这个脚本只支持《{戏}》，不认识「{参.戏名}」")
        return 2

    报 = lambda s: print(s, flush=True)
    止 = 步骤.index(参.到)

    def 该做(名):
        return (not 参.查) and 步骤.index(名) <= 止

    报("═" * 62)
    报(f"《{戏}》总装　{os.path.dirname(根)}")
    报("═" * 62)

    报("\n【1 查段】")
    if not 查段(报):
        if 止 == 0:
            return 1
        报("  ⚠ 段不齐，后面的步骤照样跑（结果一定不对，只用来验证管线）")

    接好 = os.path.join(片夹, "_成片.mp4")
    报("\n【2 接片】")
    该接, 为何接 = 过时(接好, 段夹)
    if 该做("接片") and (参.重接 or 该接):
        报(f"  （{ '--重接 强制' if 参.重接 else 为何接 }）")
        if not 跑([PY, "-X", "utf8", "_拼长片.py", 戏, "--每段秒", f"{每格秒:.4f}",
                   "--转场吃", str(转场吃), "--片名", "_成片.mp4"], 报, 要=接好):
            return 1
    else:
        报(f"  {'跳过' if not 该做('接片') else '已有且最新'} {os.path.relpath(接好, 根)}")

    带好 = os.path.join(片夹, "_成片_带头尾.mp4")
    报("\n【3 头尾】")
    该头, 为何头 = 过时(带好, 接好)
    if 该做("头尾") and (参.重接 or 该头):
        报(f"  （{ '--重接 强制' if 参.重接 else 为何头 }）")
        if not 跑([PY, "-X", "utf8", "_加头尾_觉醒.py", 接好, "--出", 带好,
                   "--头秒", str(头秒), "--尾秒", str(尾秒)], 报, 要=带好):
            return 1
    else:
        报(f"  {'跳过' if not 该做('头尾') else '已有且最新'} {os.path.relpath(带好, 根)}")

    报("\n【4 配音】")
    有配 = os.path.join(配夹, "_轴.json")
    if not os.path.exists(有配):
        报(f"  ✗ 没有 {os.path.relpath(有配, 根)}　先跑 _配台词_觉醒.py")
        return 1
    srt = os.path.join(配夹, "台词.srt")
    报(f"  轴表 ✓　SRT {'✓' if os.path.exists(srt) else '✗'}")
    有声 = os.path.join(片夹, "_成片_带头尾_有声.mp4")
    if 该做("配音"):
        该配, 为何配 = 过时(有声, 带好, 有配)
        if 参.重接 or 该配:
            报(f"  （{ '--重接 强制' if 参.重接 else 为何配 }）")
            if not 跑([PY, "-X", "utf8", "_配片.py", 戏, "--片", "_成片_带头尾.mp4",
                       "--每段秒", f"{每格秒:.4f}", "--转场吃", str(转场吃)], 报):
                return 1
            if not os.path.exists(有声):
                # `_配片.py` 的命名是「干_有声尾」
                可能 = [f for f in os.listdir(片夹) if "有声" in f]
                报(f"  ⚠ 没看到 {os.path.basename(有声)}，片夹里有声的：{可能}")
                if not 可能:
                    return 1
                有声 = os.path.join(片夹, 可能[0])
        else:
            报(f"  已有且最新 {os.path.relpath(有声, 根)}")
    else:
        报(f"  跳过（--到 {参.到}）")

    报("\n【5 字幕】")
    带字 = os.path.join(片夹, "_成片_觉醒_字幕.mp4")
    if 该做("字幕"):
        if not os.path.exists(srt):
            报("  ✗ 没有 SRT")
            return 1
        该字, 为何字 = 过时(带字, 有声, srt)
        if 参.重接 or 该字:
            报(f"  （{ '--重接 强制' if 参.重接 else 为何字 }）")
            if not 跑([PY, "-X", "utf8", "_烧字幕.py", 有声, "--srt", srt,
                       "--出", 带字, "--字号", "26", "--边距", "26"], 报, 要=带字):
                return 1
        else:
            报(f"  已有且最新 {os.path.relpath(带字, 根)}")
    else:
        报(f"  跳过（--到 {参.到}）")

    报("\n【6 报规格】")
    # ★ 收尾审一遍：每个产物是不是真的比它的输入新。
    #   这一步就是用来抓「步骤报了 ✓ 其实没干活」的（2026-10-14 就是这么翻车的）。
    链 = [("接片", 接好, [段夹]), ("带头尾", 带好, [接好]),
          ("有声", 有声, [带好, 有配]), ("带字幕", 带字, [有声, srt])]
    不新鲜 = []
    for 名, 出, 入们 in 链:
        if not os.path.exists(出):
            不新鲜.append(f"{名} 产物不在")
            continue
        陈, 因 = 过时(出, *入们)
        if 陈:
            不新鲜.append(f"{名}：{因}")
    if 不新鲜:
        报("  ✗✗ 有步骤没跟上，这份成片不可信：")
        for s in 不新鲜:
            报("       " + s)
        return 2
    报("  ✓ 链条新鲜度：每一步的产物都比它的输入新")

    for 名, 路 in (("接片", 接好), ("带头尾", 带好), ("有声", 有声), ("带字幕", 带字)):
        if os.path.exists(路):
            规 = 探规格(路)
            报(f"  {名:<6} {规.get('秒', 0):>7.2f}s  "
               f"{规.get('宽', '?')}×{规.get('高', '?')} @{规.get('帧率', '?')}fps  "
               f"{规.get('编码', '?')}  音={规.get('音频编码', '无')} "
               f"{规.get('采样', '?')}Hz {规.get('声道', '?')}  "
               f"{os.path.getsize(路)/1048576:.2f} MB")
        else:
            报(f"  {名:<6} （还没有）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
