# -*- coding: utf-8 -*-
"""在远端跑一段视频 —— 验证「两条线一起出片」。

    python _远端出片.py 试镜 8               在远端出第 8 格
    python _远端出片.py 试镜 8 9 --本机       用本机跑（对照）

远端要先起 ComfyUI 并 --listen 0.0.0.0，否则 100.127.224.106:8188 连不上。
"""
import argparse
import os
import shutil
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 引擎  # noqa: E402
import 导演  # noqa: E402

# 从 _出成片.py 拿同一张动作表，保证两边跑的是同一套指令
sys.path.insert(0, 根)
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("_出成片", os.path.join(根, "_出成片.py"))
_出成片 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_出成片)
动作表 = _出成片.动作表


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("格", nargs="+", type=int)
    ap.add_argument("--本机", action="store_true")
    ap.add_argument("--宽", type=int, default=1344)
    ap.add_argument("--高", type=int, default=768)
    参 = ap.parse_args()

    def 报(s):
        print(s, flush=True)

    端点 = "本机" if 参.本机 else "远端"
    try:
        r = 引擎.换端点(端点)
    except Exception as e:
        报(f"✗ 换端点失败：{e}")
        return 2
    报(f"端点：{r}")

    在 = 引擎.在线()
    报(f"在线：{在}")
    if not 在.get("在线"):
        报("✗ 对面 ComfyUI 没起来，先起它")
        return 2

    # 远端模型齐不齐 —— 用引擎自己的校验（它认端点，不会拿本机磁盘瞎判）
    报("\n══ 模型校验（远端）══")
    for t in ("wan22_i2v", "zimage_turbo"):
        缺 = 引擎.模板缺什么(t)
        报(f"  {t}: {'✓ 齐' if not 缺 else '缺 → ' + '; '.join(缺)}")

    戏目录 = os.path.join(根, "作品", 参.戏)
    导演.立戏(参.戏, 默认风格="cinematic-real", 默认角色=["凌霜"])

    成 = 败 = 0
    for 号 in 参.格:
        图 = os.path.join(戏目录, f"01_格{号}.png")
        if not os.path.exists(图):
            报(f"  格{号}：✗ 本机找不到 {图}")
            败 += 1
            continue
        动 = 动作表.get(号, "")
        报(f"\n  格{号}  {动[:40]}…")
        # ★ 先把本机那一段保下来再跑。
        # 让镜动 落盘用的名字是 <图名>.mp4，也就是 01_格N.mp4 —— 跟本机出片撞名。
        # 上一版直接 os.replace 走它，把本机 格1/5/8 三段真删了（犯过一次，别再犯）。
        本机段 = os.path.join(戏目录, f"01_格{号}.mp4")
        if os.path.exists(本机段):
            保 = os.path.join(戏目录, f"_本机_格{号}.mp4")
            if not os.path.exists(保):
                shutil.copyfile(本机段, 保)
                报(f"    （本机那一段已备份成 {os.path.basename(保)}）")
        t = time.time()
        try:
            果 = 导演.让镜动({"路": 图, "种子": 1735946766}, 动,
                              帧数=49, 帧宽=参.宽, 帧高=参.高, 报=lambda s: None)
            秒 = time.time() - t
            路 = 果.get("路", "")
            if os.path.exists(路):
                新 = os.path.join(戏目录, f"_远端_格{号}.mp4")
                os.replace(路, 新)
                报(f"    ✓ {os.path.basename(新)}  {os.path.getsize(新)/1024:.0f} KB  "
                   f"{秒:.1f} 秒")
                成 += 1
            else:
                报(f"    ✗ 没落盘：{路}")
                败 += 1
        except Exception as e:
            报(f"    ✗ {type(e).__name__}: {str(e)[:300]}")
            败 += 1

    报(f"\n▶ 远端出片：成功 {成}　失败 {败}")
    return 0 if 败 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
