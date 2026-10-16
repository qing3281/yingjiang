# -*- coding: utf-8 -*-
r"""★ 真因不在提示词，在 **`动作` 字段自己就写着「不动」**。

线索：翻《雪线》最冻的那几格的 `动作`：
- 格34「两个点面对面立在画面中央，风把四周的雪面吹出极缓慢的波纹…」
- 格9 「那个小黑点在脚印尽头**停下**…」
- 格11「她嘴唇微微张开又合上…**其余不动**」
- 格14「那个极小的黑点**几乎不动**、只在原位上轻微地颤…」
- 格41「那张脸**连一丝颤动都没有**…」
- 格36「那只垂在身侧的手手指**微微**蜷了一下又松开…」

**这些句子本身就是在要求「别动」。** 把这种句子当成动作描述送给出片模型，
出来当然静 —— 那正是它被要求做的事。

这个脚本把两部片子的 `动作` 字段都扫一遍，数「否定/静止」词和「程度很轻」词，
再看它们和运动量对不对得上。

用法：python _量动作语气.py 雪线
      python _量动作语气.py 觉醒
"""
import io
import os
import re
import statistics as st
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

PY = sys.executable
量运动 = r"D:\DSHworkspace\影匠\_量运动.py"
作品 = r"D:\DSHworkspace\影匠\作品"

# 「要求别动」的词 / 「要求很轻」的词
停 = ["不动", "没动", "没有动", "几乎不", "纹丝不动", "停住", "停下", "站定", "没有变",
      "没有离开", "连一丝", "没有任何", "极缓慢", "极慢", "几乎没有", "一动不动"]
轻 = ["微微", "极缓慢", "极轻", "很轻", "轻轻", "几乎", "缓慢地", "一点点"]

戏 = (sys.argv[1] if len(sys.argv) > 1 else "雪线").strip()
路 = os.path.join(作品, 戏, "02-九宫格.md")
if not os.path.isfile(路):
    print(f"  ✗ 没有 {路}")
    sys.exit(1)

r = subprocess.run([PY, "-X", "utf8", 量运动, 戏, "--去噪", "3"],
                   capture_output=True, text=True, errors="replace",
                   env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
动 = {}
for 线 in (r.stdout or "").splitlines():
    m = re.match(r"\s*(\d+)\s+([\d.]+)\s+(.+?)\s+(\S+\.mp4)\s*$", 线)
    if m:
        动[int(m.group(1))] = float(m.group(2))

全 = io.open(路, encoding="utf-8").read()
块 = re.split(r"\n##\s*格(\d+)\s*——", 全)
格 = {}
for i in range(1, len(块), 2):
    格[int(块[i])] = 块[i + 1]


def 取(文, 名):
    m = re.search(rf"-\s*\*{{0,2}}{名}\*{{0,2}}：(.*?)(?=\n-\s*\*{{0,2}}\S+?\*{{0,2}}：|\Z)", 文, re.S)
    return m.group(1).strip().replace("\n", " ") if m else ""


甲 = []   # 动作里有「停住/不动」的
乙 = []   # 只有「微微/极缓慢」的
丙 = []   # 干净的
for 号 in sorted(格):
    if 号 not in 动:
        continue
    a = 取(格[号], "动作")
    if any(w in a for w in 停):
        甲.append((号, 动[号], a))
    elif any(w in a for w in 轻):
        乙.append((号, 动[号], a))
    else:
        丙.append((号, 动[号], a))

def 报(名, 组):
    if not 组:
        print(f"  {名}：0 格")
        return
    vs = [v for _, v, _ in 组]
    print(f"  {名}：{len(组)} 格　运动量中位 {st.median(vs):.3f}　"
          f"最小 {min(vs):.3f}　最大 {max(vs):.3f}　"
          f"其中 <0.2 的 {sum(1 for v in vs if v < 0.2)} 格"
          f"（{100 * sum(1 for v in vs if v < 0.2) / len(vs):.0f}%）")

print(f"  《{戏}》共 {len(动)} 格有运动量")
print()
报("甲　动作里写着「停住 / 不动 / 没有变」", 甲)
报("乙　动作里只有「微微 / 极缓慢」", 乙)
报("丙　动作里没有减速词", 丙)
# ── 按景别分开看 ──────────────────────────────────────────────
# ★ 为什么必须分开：一张脸的特写本来就该静，「两个人朝对方走」才该动。
#   把 45 格混成一个中位数，等于拿体温计去量身高 —— 2026-10-15 07:55 才补上这一段。
景 = {}
for 号 in sorted(格):
    if 号 in 动:
        景[号] = 取(格[号], "景别").split("（")[0].strip() or "（没写）"

分组 = {}
for 号, s in 景.items():
    分组.setdefault(s, []).append(动[号])

print("  ── 按景别分开看（这才是有靶子的数）──")
print(f"  {'景别':<18}{'格数':>5}{'中位':>9}{'最低':>9}{'最高':>9}{'<0.2':>7}")
for s, vs in sorted(分组.items(), key=lambda kv: -st.median(kv[1])):
    n低 = sum(1 for v in vs if v < 0.2)
    print(f"  {s:<18}{len(vs):>5}{st.median(vs):>9.3f}{min(vs):>9.3f}{max(vs):>9.3f}{n低:>7}")

print()
print("  ★ 怎么看这张表：**同景别之间比**。「极特写」全是 0.1–0.3 是正常的；")
print("    「全景 / 远景」也掉到 0.2 才是真的冻住了 —— 那才是要改的。")
print()

print("  ── 低于 0.2 的格子逐条 ──")
for 名, 组 in (("甲　动作里写着「停住 / 不动 / 没有变」", 甲),
               ("乙　动作里只有「微微 / 极缓慢」", 乙),
               ("丙　动作里没有减速词", 丙)):
    if not 组:
        continue
    低 = [x for x in 组 if x[1] < 0.2]
    if not 低:
        print(f"  ── {名}：没有 < 0.2 的格子 ──")
        continue
    print(f"  ── {名}：{len(低)} 格 < 0.2（按运动量升序）──")
    for 号, v, a in sorted(低, key=lambda x: x[1]):
        print(f"   格{号:<3} {v:>6.3f}　{a[:78]}")
    print()

# ── ★ 数不许单独出门 ────────────────────────────────────────
# 2026-10-15 08:05 的教训：拿「<0.2」当「冻住了」的证据，准备再改一轮，
# 先看了一眼首尾帧 —— 6 格里有 5 格是真在动的（雪原上一颗小黑点走十米，
# 缩到 160 像素宽之后像素变不了几个）。**数是筛子，图才是判据。**
低全部 = sorted([x for x in (甲 + 乙 + 丙) if x[1] < 0.2], key=lambda x: x[1])
if 低全部:
    号串 = ",".join(str(x[0]) for x in 低全部)
    print(f"  ★ 上面 {len(低全部)} 格 < 0.2 —— **这只说明「像素变得少」，不等于「冻住了」。**")
    print(f"    这个数把片缩到 160 像素宽再比帧差：**主体越小，数越低**，")
    print(f"    远景里一个人走动也可能量出 0.1。**动手改之前必须先看首尾帧：**")
    print()
    print(f"      python D:\\DSHworkspace\\_看首尾帧.py {戏} {号串}")
    print()
    print(f"    看完再决定改哪几格。**别拿这个数当「冻住了」的证据。**")
