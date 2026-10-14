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
print()
print("  ── 甲组逐条（这些就是「被要求别动」的格子）──")
for 号, v, a in sorted(甲, key=lambda x: x[1]):
    print(f"   格{号:<3} {v:>6.3f}　{a[:78]}")
