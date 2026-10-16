# -*- coding: utf-8 -*-
"""同提示词同种子，把 qwen_t2i 和 zimage_turbo 各出一张，拼成对比图。

为什么要拼图：只出一张新的，没人能判断它比旧的强在哪 —— 并排才看得见。
"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 引擎

出图目录 = r"D:\DSHworkspace\影匠\作品\_超分试验"
os.makedirs(出图目录, exist_ok=True)

提示词 = ("cinematic film still, photorealistic, an elderly Chinese cobbler in his late sixties "
        "sitting on a low wooden stool at the mouth of a wet stone alley at dusk, grey buzz cut, "
        "deep facial wrinkles, dark grey old-style front-buttoned jacket, blue apron, "
        "a wooden tool box open at his feet, wet flagstones reflecting warm orange sky, "
        "moody side light, shallow depth of field, 35mm lens")
种子 = 952778929

结果 = {}
for 名, 模 in (("zimage_turbo", "zimage_turbo"), ("qwen_t2i", "qwen_t2i")):
    print(f"\n════ {名} ════")
    t0 = time.time()
    try:
        r = 引擎.文生图(提示词, 模板=模, 种子=种子, 宽=1024, 高=1024)
        print(f"  ✓ {r.get('路')}　{r.get('耗时')} 秒")
        结果[名] = r.get("路")
    except Exception as e:
        print(f"  ✗ 挂了：{type(e).__name__}: {e}")
    print(f"     墙钟 {time.time()-t0:.1f} 秒")

print("\n════ 拼对比图 ════")
有 = [(k, v) for k, v in 结果.items() if v and os.path.exists(v)]
if len(有) < 2:
    print(f"  只有 {len(有)} 张出得来，不拼了")
    sys.exit(0)

ff = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
入 = []
for _, 路 in 有:
    入 += ["-i", 路]
滤 = "".join(f"[{i}:v]scale=700:-1[v{i}];" for i in range(len(有)))
滤 += "".join(f"[v{i}]" for i in range(len(有))) + f"hstack=inputs={len(有)}"
出 = os.path.join(出图目录, "对比_出图模型.png")
# ★ 时间戳必须在**跑之前**读 —— 跑完再读，前后必然相等，那个判断永远为真，
#   等于什么都没量（这是「判据说 OK 其实什么都没量」的第 13 次）。
前 = os.path.getmtime(出) if os.path.exists(出) else 0.0
r = subprocess.run([ff, "-y", "-v", "error", *入, "-filter_complex", 滤, "-frames:v", "1", 出],
                   capture_output=True, text=True, errors="replace")
后 = os.path.getmtime(出) if os.path.exists(出) else 0.0
if 后 > 前:
    print(f"  ✓ {出}　{os.path.getsize(出):,} B　（这次写的）")
    print(f"     左边 = {有[0][0]}　右边 = {有[1][0]}")
else:
    print(f"  ✗ 拼图没写成（时间戳没动，这图是上一次的）　ffmpeg: {(r.stderr or '').strip()[:200]}")
