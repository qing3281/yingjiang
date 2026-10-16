# -*- coding: utf-8 -*-
"""奥丁重写 + 超分链路验证。

## 奥丁第一版失败的诊断
提示词里写「暗**金**色甲胄……甲面泛着潮湿的金属**冷光**」→ 出来的是
游戏 CG 里的金色板甲 Boss：饱和度过高、甲片崭新反光、像 MMORPG 装备。
「金」这个字把模型拉进了「fantasy armor」的先验。

第二版改法：
  1. 把「金」从材质描述里拿掉，改成「**氧化发黑的青铜与铁**」，
     金色**只留在那只瞳孔上** —— 让「金」这个信息只承担一个语义
  2. 加「甲胄破旧、有划痕与锈迹、被雨水冲刷出暗色水痕」
  3. 加「不是奇幻铠甲、不是游戏装备、不是超级英雄」进负面
  4. 明确写「他是**人形**，不是机器也不是雕像」
  5. 八足马这一版单独出一张，别和神挤在同一帧里抢戏

## 超分验证
RealESRGAN_x4plus / Remacri / NMKD-Siax 已下到
D:\\Comfy-Desktop\\ComfyUI-Shared\\models\\upscale_models\\
这里测：1344×768 → 2688×1536（2 倍）的实际画质与耗时。

跑法：
  python 龙族试验2.py --奥丁        # 重出奥丁 + 八足马
  python 龙族试验2.py --超分        # 超分链路测试
  python 龙族试验2.py --全          # 都跑
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

试验根 = r"D:\DSHworkspace\B站\成片\龙族\试验"
超分根 = r"D:\DSHworkspace\B站\成片\龙族\超分试验"

宽, 高 = 1344, 768

# 复用 龙族试验.py 的画风锁，但把「奇幻铠甲」逐条否掉
from 龙族试验 import 画风锁 as 基础画风锁  # noqa: E402

画风锁 = 基础画风锁 + (
    "**这不是奇幻作品，不是游戏，不是超级英雄电影。**"
    "画面里出现的任何铠甲都必须是**氧化发黑的青铜与铁**，"
    "布满划痕、凹痕、锈斑和干涸的暗色水痕，被暴雨冲刷了千百年，"
    "**绝不是崭新的、反光的、饱和的金色板甲**。"
    "他是**人形**，不是机器、不是雕像、不是机甲。"
)

负面 = (
    "动漫, 动画, 插画, 漫画, 手绘, 绘本, 赛璐璐, 平涂, 卡通, Q版, 大头身, "
    "3D渲染, CG, 游戏画面, 游戏装备, 奇幻铠甲, 超级英雄, 机甲, 机器人, 雕像, "
    "概念图, 设定图, 塑料感, 玩具感, 蜡像, 崭新反光, 高饱和, 金色板甲, "
    "矮小, 儿童体型, 头大身子小, 大眼睛, 简笔, "
    "文字, 字幕, 水印, 签名, logo, 边框, 车牌, 分格, 拼图, 多视图, "
    "畸形, 多手多脚, 手指错乱, 两个头, 六条腿, 十条腿, "
    "模糊, 低分辨率, 过曝, 死黑, 噪点"
)

新增: dict[str, str] = {
    "03b_奥丁": (
        "电影剧照，大远景，强烈仰拍，从下往上。暴雨夜的封闭高架路上，"
        "一个巨大的身影矗立在浓雾与白光之中，他高得不像人，"
        "画面被他占据了上方的三分之二，而画面最下方只有一辆黑色轿车的车顶。"
        "他穿着**氧化发黑的青铜与铁**打造的重甲，甲片层层相叠、布满划痕与凹痕、"
        "缝隙里是暗红色的锈斑，雨水顺着甲缝往下淌、在甲面冲出暗色的水痕，"
        "整副甲胄没有一点反光，只是潮湿、沉重、冰冷。"
        "他戴着一顶遮住上半张脸的铁面，铁面本身也是锈蚀的黑铁。"
        "铁面之下唯一露出的那只瞳孔是**纯金色**的，像两盏巨灯，"
        "在雨幕里投出两道金色的光柱——整个画面里只有这一处是金色的。"
        "他右手垂着一支弯曲的长矛，矛身是暗色木质，矛尖是哑光的铁，"
        "矛的弧线像流星划过天空的轨迹。"
        "他身后披着一件暗蓝色的、被雨水浸透的厚重风氅，"
        "风氅被狂风吹得向一侧翻卷、边缘在雨里模糊成一片。"
        "四周的雨异常地大，雨丝在他身边形成一圈环流的白雾。"
        "乌云压得极低，云层内部有闪电在闪。"
        + 画风锁
    ),
    "05b_八足马": (
        "电影剧照，大远景，强烈仰拍，从马腿之间往上看。暴雨夜的封闭高架路上，"
        "一匹巨大到不像话的骏马立在浓雾中，它的肩高超过三米，"
        "画面里只能看见它的身体和腿，看不见全身。"
        "它的毛色是苍白的、近乎灰白，被雨水打湿后贴在身上、"
        "肌肉的轮廓在湿毛下清晰可见。"
        "它披挂着金属错花的沉重甲胄，甲片是**氧化发黑的铁与青铜**、"
        "布满划痕与锈迹，用暗色的皮带勒在马身上，雨水顺着甲片往下淌。"
        "它有**八条腿**，像重型起重机用来稳定车身的液压支架一样"
        "以不同的角度撑在地面上，暗金色的马掌深深踩进沥青路面，"
        "把路面翻开一个又一个伤口，碎石被踩得崩起来、悬在半空。"
        "它的马脸上戴着金属面罩，面罩的鼻孔位置正喷出细碎的、"
        "噼啪作响的电光火花，照亮了它下颌的轮廓。"
        "它的眼睛是暗红色的，瞳孔是一条竖线。"
        "整个画面被暴雨、浓雾和它脚下飞溅的碎石填满。"
        + 画风锁
    ),
}


def 出奥丁() -> int:
    import 出图_纯文本 as 图
    from PIL import Image

    os.makedirs(试验根, exist_ok=True)
    清单 = [(k, v) for k, v in 新增.items() if not os.path.isfile(os.path.join(试验根, f"{k}.png"))]
    if not 清单:
        print("奥丁/八足马都已有。")
    for i, (名, 词) in enumerate(清单, 1):
        print(f"[{i}/{len(清单)}] {名}   提示词 {len(词)} 字符")
        t1 = time.time()
        r = 图.跑(词, 种子=7800 + i * 211, 宽=宽, 高=高, 负面=负面, 静默=True)
        if not r:
            print("   ✗ 失败")
            continue
        p = os.path.join(试验根, f"{名}.png")
        Image.open(r).convert("RGB").save(p)
        print(f"   ✓ {time.time()-t1:.0f} 秒 → {p}")
    return 0


def 超分() -> int:
    """用 ComfyUI 的 UpscaleModelLoader + ImageUpscaleWithModel 把一张图放大 2 倍。"""
    import json
    import shutil
    import urllib.request

    from PIL import Image

    COMFY = "http://127.0.0.1:8188"
    os.makedirs(超分根, exist_ok=True)

    源图 = os.path.join(试验根, "01_楚子航.png")
    if not os.path.isfile(源图):
        print("✗ 找不到测试源图", 源图)
        return 1

    # 先上传到 ComfyUI
    def 上传(p: str) -> str:
        边界 = "----DSH边界"
        名 = os.path.basename(p)
        with open(p, "rb") as f:
            数据 = f.read()
        体 = (
            f"--{边界}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{名}\"\r\n"
            f"Content-Type: image/png\r\n\r\n".encode()
            + 数据
            + f"\r\n--{边界}--\r\n".encode()
        )
        req = urllib.request.Request(
            COMFY + "/upload/image", data=体,
            headers={"Content-Type": f"multipart/form-data; boundary={边界}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())["name"]

    已上传 = 上传(源图)
    print(f"  已上传 {已上传}")

    for 模型 in ("4x_foolhardy_Remacri.pth", "RealESRGAN_x4plus.pth", "4x_NMKD-Siax_200k.pth"):
        出 = os.path.join(超分根, f"{os.path.splitext(模型)[0]}.png")
        if os.path.isfile(出):
            print(f"  ↷ {模型} 已有"); continue
        wf = {
            "1": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": 模型}},
            "2": {"class_type": "LoadImage", "inputs": {"image": 已上传, "upload": "image"}},
            "3": {"class_type": "ImageUpscaleWithModel",
                  "inputs": {"upscale_model": ["1", 0], "image": ["2", 0]}},
            # 4 倍会到 5376×3072，太大；缩到 2 倍（2688×1536）看质量
            "4": {"class_type": "ImageScale",
                  "inputs": {"image": ["3", 0], "upscale_method": "lanczos",
                             "width": 宽 * 2, "height": 高 * 2, "crop": "disabled"}},
            "5": {"class_type": "SaveImage",
                  "inputs": {"images": ["4", 0], "filename_prefix": f"UP_{模型[:14]}"}},
        }
        req = urllib.request.Request(
            COMFY + "/api/prompt", data=json.dumps({"prompt": wf}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            pid = json.loads(r.read().decode())["prompt_id"]

        t0 = time.time()
        while True:
            time.sleep(2)
            with urllib.request.urlopen(f"{COMFY}/api/history/{pid}", timeout=30) as r:
                h = json.loads(r.read().decode())
            if pid in h:
                e = h[pid]
                if e.get("outputs"):
                    图 = None
                    for _, o in e["outputs"].items():
                        if o.get("images"):
                            图 = o["images"][0]
                    if 图:
                        src = os.path.join(r"D:\Comfy-Desktop\ComfyUI-Shared\output",
                                           str(图.get("subfolder") or ""), 图["filename"])
                        shutil.copyfile(src, 出)
                        im = Image.open(出)
                        print(f"  ✅ {模型}  {time.time()-t0:.0f} 秒  → {im.size}")
                        break
                if e.get("status", {}).get("status_str") == "error":
                    print(f"  ✗ {模型} 出错:", json.dumps(e.get("status"), ensure_ascii=False)[:300])
                    break
            if time.time() - t0 > 600:
                print(f"  ✗ {模型} 超时"); break
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--奥丁", action="store_true")
    ap.add_argument("--超分", action="store_true")
    ap.add_argument("--全", action="store_true")
    a = ap.parse_args()
    if a.全 or (not a.奥丁 and not a.超分):
        a.奥丁 = a.超分 = True
    if a.奥丁:
        print("=" * 70); print("奥丁 v2 + 八足马"); print("=" * 70)
        出奥丁()
    if a.超分:
        print(); print("=" * 70); print("超分链路"); print("=" * 70)
        超分()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
