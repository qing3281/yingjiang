# -*- coding: utf-8 -*-
"""《觉醒》两条线的进度 —— 一眼看清「哪几格出了、还缺哪几格、还要多久」。

★ 为什么要单独写：之前用 `Get-ChildItem 段\\*.mp4 | Sort-Object` 数，
  两条线的文件混在一个目录里（`格41_远端.mp4` 和 `格1_本机.mp4`），
  按修改时间排出来的「平均间隔」把两条线混成一条，算出 82 秒/格（假快 ——
  真实是每边各 170 秒上下）。**把两边分开算，再各算各的间隔。**
"""
import io
import os
import re
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
段 = os.path.join(根, "作品", "觉醒", "段")
总要 = 74
# ★ 18:50 重新分配过：本机 1-40 跑完后接 69-74，远端改成只跑 49-68。
#   为什么（调度算术）：原方案本机 19:27 收工、远端 20:03 收工，本机空转 36 分钟。
#   改成「本机 20 格 + 远端 20 格」→ 两边 19:44 / 19:46 几乎同时收工，省 17 分钟。
#   41-48 已由远端出过；49-68 归远端；69-74 归本机（见 _接尾_觉醒.py）。
本机管 = set(range(1, 41)) | set(range(69, 75))    # 1..40 + 69..74
远端管 = set(range(41, 69))                        # 41..68

模 = re.compile(r"^格(\d+)_(本机|远端)\.mp4$")

条 = {"本机": {}, "远端": {}}
for 名 in os.listdir(段):
    m = 模.match(名)
    if not m:
        continue
    号 = int(m.group(1))
    条[m.group(2)][号] = os.path.getmtime(os.path.join(段, 名))

print(f"\n=== 《觉醒》两条线　{time.strftime('%H:%M:%S')} ===")
总出 = 0
for 谁, 管 in (("本机", 本机管), ("远端", 远端管)):
    有 = 条[谁]
    总出 += len(有)
    缺 = sorted(管 - set(有))
    # 按号排好算相邻间隔（只算同一台机器自己的）
    号s = sorted(有)
    次 = [有[号s[i]] - 有[号s[i - 1]] for i in range(1, len(号s))]
    近 = 次[-6:] if 次 else []
    平 = (sum(近) / len(近)) if 近 else 0
    还 = (len(缺) * 平) if 平 else 0
    print(f"\n  【{谁}】{len(有)}/{len(管)} 格　管 格{sorted(管)[0]}–{sorted(管)[-1]}")
    if 有:
        print(f"    已出：{号s[0]}..{号s[-1]}　（缺 {len(缺)} 格）")
        新 = max(有, key=lambda k: 有[k])
        print(f"    最新：格{新}  {time.strftime('%H:%M:%S', time.localtime(有[新]))}")
    if 平:
        print(f"    每格 {平:.1f} 秒　→ 剩 {len(缺)} 格还要 {还/60:.0f} 分钟"
              f"　→ 预计 {time.strftime('%H:%M', time.localtime(time.time() + 还))}")
    if 缺 and len(缺) <= 12:
        print(f"    缺：{缺}")
    elif 缺:
        print(f"    缺：{缺[:6]} … {缺[-3:]}")

# 两边合起来 = 所有已出的格（总装要的是 74 个都有）
全部有 = set(条["本机"]) | set(条["远端"])
缺总 = sorted(set(range(1, 75)) - 全部有)
print(f"\n  ── 合计 {len(全部有)}/74")
if 缺总:
    print(f"  ── 总管还缺 {len(缺总)} 格：{缺总[:10]}{' …' if len(缺总) > 10 else ''}")
else:
    print("  ── ✓ 74 格齐了，可以总装")

# 顺带核一下规格（抽最新的一个）
if 全部有:
    谁 = "本机" if 条["本机"] else "远端"
    号 = max(条[谁], key=lambda k: 条[谁][k])
    路 = os.path.join(段, f"格{号}_{谁}.mp4")
    import subprocess
    FF = os.path.join(根, "_bin", "ffmpeg.exe")
    r = subprocess.run([FF, "-i", 路], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for 行 in (r.stderr or "").splitlines():
        if "Duration:" in 行 or "Stream #" in 行:
            print("  " + 行.strip())
    print()
