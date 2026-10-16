# -*- coding: utf-8 -*-
"""锁脸的正确用法实验：以「格N 原图」为底，把脸换成定妆照那张脸。

之前失败的方向（错）：
    把 定妆照 当底图，提示词要求「改成远景」→ Qwen-Image-Edit 保留输入构图，
    九格全变成同一个胸像，景别全塌。

现在试的方向（对）：
    Qwen-Image-Edit 是**编辑**模型 —— 它保持输入结构、按提示词做修改。
    所以要「保持这一格的构图不动，只换脸」：
        底图   = 该格自己的原图（构图 / 景别 / 姿态 / 光影都对）
        参考图 = 凌霜定妆照（提供身份）
        提示词 = 明确要求「构图不变，只换脸」

    python _换脸试.py 7            试第 7 格
    python _换脸试.py 1 5 7        试三格
"""
import os
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 引擎  # noqa: E402

戏目录 = os.path.join(根, "作品", "试镜")
定妆照 = os.path.join(根, "assets", "角色", "凌霜.png")

提示词 = (
    "保持这张图的构图、景别、人物姿态、机位、光影、色调、背景完全不变，"
    "只把人物的面部替换成第二张参考图里的那张脸：银白长发、紫色杏眼、冷白皮、"
    "左眼下有一颗小痣。电影写实，冷蓝低饱和，硬光长阴影。"
    "不要改变画面尺寸，不要改变镜头远近，不要重新构图。"
)


def 跑(格号):
    原图 = os.path.join(戏目录, f"01_格{格号}.png")
    if not os.path.exists(原图):
        return {"格": 格号, "ok": False, "错": f"没有 {原图}"}
    if not os.path.exists(定妆照):
        return {"格": 格号, "ok": False, "错": f"没有定妆照 {定妆照}"}

    存 = os.path.join(根, "作品", f"换脸_格{格号}.png")
    t = time.time()
    try:
        r = 引擎.文生图(
            提示词,
            种子=1735946766,
            宽=1344, 高=768,
            步数=20,
            模板="qwen_edit",
            参考图=[原图, 定妆照],      # ← 顺序关键：第一张是底图，第二张是身份源
            前缀=f"换脸{格号}",
            存到=存,
        )
        return {"格": 格号, "ok": os.path.exists(存), "路": 存,
                "秒": round(time.time() - t, 1),
                "挂": r.get("挂了几张")}
    except Exception as e:
        return {"格": 格号, "ok": False, "错": f"{type(e).__name__}: {str(e)[:200]}"}


def main():
    格们 = [int(x) for x in sys.argv[1:]] or [7]
    好 = 败 = 0
    for n in 格们:
        果 = 跑(n)
        if 果.get("ok"):
            print(f"  格{n}  ✓ {os.path.basename(果['路'])}  "
                  f"{os.path.getsize(果['路'])/1024:.0f} KB  {果['秒']} 秒  挂{果['挂']}张",
                  flush=True)
            好 += 1
        else:
            print(f"  格{n}  ✗ {果.get('错')}", flush=True)
            败 += 1
    print(f"\n▶ 换脸实验：成功 {好}　失败 {败}")
    return 0 if 败 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
