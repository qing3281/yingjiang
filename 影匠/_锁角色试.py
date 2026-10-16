# -*- coding: utf-8 -*-
"""③ 锁角色 LoRA 真跑 —— 同一张定妆照、同一个种子、同一句动作，只换挂哪个 LoRA。

要证明的两件事：
  1. 挂上了没（引擎会打印「挂上角色 LoRA：… 接在 X 后面」，挂不上会打印「⚠ … 没挂上」）
  2. 挂上之后脸是不是更稳（三段的 4 帧拼一张图，肉眼比）

用法：python _锁角色试.py            # 三段全跑
      python _锁角色试.py 空          # 只跑不挂的那段
"""
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 导演
import 引擎

这里 = r"D:\DSHworkspace\影匠"
落 = os.path.join(这里, "作品", "_锁角色试验")
os.makedirs(落, exist_ok=True)

源 = os.path.join(这里, "作品", "楚子航", "_定妆照", "楚子航.png")
动作 = ("He stands still in the rain on the bridge deck, breathing; "
        "the rain keeps running down his face, his eyes slowly lift and look straight ahead; "
        "the camera pushes in slowly toward his face.")

三段 = [
    ("空", "", "不挂 LoRA —— 只用模板自带的 turbo 8 步"),
    ("真人", "h3-realism-people-t2v-i2v-r2v.safetensors", "真人质感"),
    ("换人", "h3_character_swap_pro4500_1000.safetensors", "换人"),
]
只要 = (sys.argv[1].strip() if len(sys.argv) > 1 else "")

FFMPEG = 引擎.ffmpeg() if hasattr(引擎, "ffmpeg") else "ffmpeg"

结果 = []
for 名, lora, 说 in 三段:
    if 只要 and 名 != 只要:
        continue
    目标 = os.path.join(落, "锁角色_%s.mp4" % 名)
    if os.path.exists(目标) and os.path.getsize(目标) > 10000:
        print("  ⏭ %s 已在，跳过" % 目标)
        结果.append((名, lora, 说, 目标, 0.0))
        continue
    print("\n  ══ 跑「%s」%s  LoRA=%s ══" % (名, 说, lora or "（不挂）"))
    t = time.time()
    try:
        r = 引擎.图生视频(
            源, 动作,
            种子=431515722,               # 楚子航在角色库里的固定种子
            帧数=124, 帧率=24, 宽=832, 高=480,
            模板="minimax_h3_i2v",
            前缀="影匠/_锁角色试验",
            存到=目标,
            角色LoRA=lora,
            报=lambda s: print("     ", s),
        )
    except Exception as e:
        print("     ✗ 失败：%s: %s" % (type(e).__name__, e))
        结果.append((名, lora, 说, "", time.time() - t))
        continue
    秒 = time.time() - t
    print("     ✓ %s  %.1f 秒  %.1f MB" % (os.path.basename(r["路"]),
                                         秒, os.path.getsize(r["路"]) / 1048576))
    结果.append((名, lora, 说, r["路"], 秒))

print("\n  ════ 汇总 ════")
for 名, lora, 说, 路, 秒 in 结果:
    print("  %-4s %-46s %-52s %.1f 秒" % (名, lora or "（不挂）",
                                           os.path.basename(路) if 路 else "✗ 没出", 秒))
with io.open(os.path.join(落, "_结果.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump([{"名": a, "LoRA": b, "说": c, "路": d, "秒": round(e, 1)}
               for a, b, c, d, e in 结果], f, ensure_ascii=False, indent=2)
print("  →", os.path.join(落, "_结果.json"))
