# -*- coding: utf-8 -*-
"""验「配音批量那条路」—— `_守成片2.py` 第①步就是它，不验就是拿整片赌。

为什么只配 3 句：真正要证明的是**批量这条路**（角色映射 → IndexTTS → 存成真 WAV
→ 写字幕）不炸，不是把 32 句现在就跑完（那会跟出片线抢本机显存）。

判据：
  ① 退出码 0
  ② 3 句都回了结果、且 `错` 是空
  ③ 每个文件头 4 字节是 RIFF（ComfyUI 的 SaveAudio 只存 FLAC，要真 WAV 得转）
  ④ 角色解析里「映射命中」= 3、「没解析出来」= 空 → 四个角色的音色真的进表了
"""
import sys
import os
import json
import importlib.util

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

出 = r"D:\DSHworkspace\_试配音批"


def 主():
    print("═" * 66)
    spec = importlib.util.spec_from_file_location("_yjpy", r"D:\DSHworkspace\影匠\配音.py")
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    表 = [
        {"序号": 1, "台词": "就是这里？", "角色": "夏弥", "语言": "ZH"},
        {"序号": 2, "台词": "站台尽头有东西。", "角色": "楚子航", "语言": "ZH"},
        {"序号": 5, "台词": "他是我哥哥，大地与山之王。", "角色": "夏弥", "语言": "ZH"},
    ]
    print("── 批量配 3 句（角色名走 角色映射.json）──")
    果 = P.批量(表, 输出目录=出, 保留显存=True, 写字幕=True, 要真WAV=True, 报=print)

    解析 = 果.get("角色解析", {})
    print("角色解析：%s" % json.dumps(解析, ensure_ascii=False))

    好 = 0
    for x in 果.get("配音", []):
        路 = x.get("路") or ""
        头 = b""
        if 路 and os.path.isfile(路):
            with open(路, "rb") as f:
                头 = f.read(4)
        print("  #%s  %-10s  %6s 秒  %s  头=%s  错=%s"
              % (x.get("序号"), x.get("音色") or "", x.get("秒"), os.path.basename(路),
                 头.decode("latin1"), x.get("错") or "")
              )
        if 路 and os.path.isfile(路) and 头 == b"RIFF" and not x.get("错"):
            好 += 1

    print("\n判据① 退出码：这条命令本身跑到这儿 = 没抛异常")
    print("判据② 3 句都回、且无错：%s" % ("✓" if 好 == 3 else "✗ 只 %d/3" % 好))
    print("判据③ 头 4 字节 RIFF：%s" % ("✓" if 好 == 3 else "✗"))
    print("判据④ 角色映射命中 3、没解析出来为空：%s"
          % ("✓" if 解析.get("映射命中") == 3 and not 解析.get("没解析出来") else "✗"))
    print("总时长 %s 秒　目录 %s" % (果.get("总时长"), 果.get("目录")))
    print("srt：%s" % 果.get("srt"))
    return 0 if 好 == 3 else 1


if __name__ == "__main__":
    sys.exit(主())
