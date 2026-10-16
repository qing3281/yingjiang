# -*- coding: utf-8 -*-
"""H3 为什么把提示词画成字幕，以及哪种写法能治好。

## 现象

格55 的提示词开头是一句裸中文：

    周执伸手指着册子上的一行，内门执事点了一下头……

出来的画面底部有字，而且**跟着提示词走**：
0.3 秒「周执伸子册」、2.2 秒「内门执事了一下」。
格56 更狠：中文一层（我的字幕）+ **英文一层**（「The orie the Witk syat of anheut overs.」）。

## 假设

H3 见过大量带字幕的视频。**一个孤零零的中文句子 = 一条字幕** ——
这是它的先验。所以问题不在「中文」，在**「裸句 + 开头」这个形状**。

三条路各试一次，同图同种子同参数，只换提示词的写法：

    A 现状     「{动作}。环境：{光}。A continuous cinematic shot. …」
    B 英文在前  「A continuous cinematic scene with no text… {动作}。Lighting: {光}。…」
    C 中文当字段「Scene brief (the bracketed text is a production note, NOT on-screen
                  text): [action: {动作}] [lighting: {光}]. …」

判据：**画面底部 22% 那一条里有没有清晰文字**（人眼看底部条拼图）。

★ 工作流直接复用 `_出H3.py` 的 `建图()` —— 第一版自己手写了一份，
  漏了 RandomNoise / BasicGuider / SamplerCustomAdvanced 三个节点，
  而且 `av_latent` 该接 `["7", 1]` 不是 `["7", 0]`，
  服务端报 `return_type_mismatch: av_latent, received_type(MODEL) mismatch input_type(LATENT)`。
  **能复用就别重写。**
"""
import argparse
import importlib.util
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

根 = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")

# ── 把 _出H3.py 当模块加载（文件名以 _ 开头、又不是合法标识符，只能走 spec）
_spec = importlib.util.spec_from_file_location("出H3", os.path.join(根, "_出H3.py"))
H3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H3)


def 跑(词, 图, 号, 服务="http://127.0.0.1:8188", 前缀="字幕试验", 等待=900):
    图名 = H3.传图(服务, 图)
    图 = H3.建图(图名, 词, 号, H3.种子 + 号 * 1009, f"{前缀}_{号}")
    import json
    体 = json.dumps({"prompt": 图, "client_id": "字幕试验"}).encode()
    请 = urllib.request.Request(服务 + "/prompt", data=体,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(请, timeout=120) as 回:
            号p = json.loads(回.read())["prompt_id"]
    except urllib.error.HTTPError as e:
        print("    ✗ 服务端拒收：" + e.read().decode("utf-8", "replace")[:400])
        return None
    t0 = time.time()
    while time.time() - t0 < 等待:
        with urllib.request.urlopen(f"{服务}/history/{号p}", timeout=60) as 回:
            历 = json.loads(回.read())
        if 号p in 历:
            for 节 in 历[号p].get("outputs", {}).values():
                for f in 节.get("gifs", []) + 节.get("videos", []):
                    路 = os.path.join(r"D:\Comfy-Desktop\ComfyUI-Shared\output",
                                      f.get("subfolder", ""), f["filename"])
                    if os.path.isfile(路):
                        print(f"    ✓ {time.time() - t0:.0f} 秒  {os.path.basename(路)}")
                        return 路
            print("    ✗ 历史里有，但没找到输出文件")
            return None
        time.sleep(5)
    print("    ✗ 超时")
    return None


def 底部条(片, 出, 带=0.22, 时刻=2.2):
    subprocess.run([FFMPEG, "-y", "-ss", str(时刻), "-i", 片,
                    "-vf", f"crop=iw:ih*{带:.2f}:0:ih*(1-{带:.2f})",
                    "-frames:v", "1", 出], capture_output=True)
    return os.path.isfile(出)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--格", type=int, default=55)
    ap.add_argument("--端点", default="本机")
    参 = ap.parse_args()
    n = 参.格
    服务 = H3.端点(参.端点)

    文 = open(os.path.join(根, "作品", "觉醒", "02-九宫格.md"), encoding="utf-8").read()
    块 = re.split(r"^##\s*格\s*(\d+)\s*(?:——|--|—)\s*(.+?)\s*$", 文, flags=re.M)
    m = {int(块[i]): 块[i + 2] for i in range(1, len(块) - 1, 3)}
    t = m[n]
    动作 = re.search(r"\*\*动作\*\*[：:]\s*(.+?)(?:\n|$)", t).group(1).strip()
    光 = re.search(r"\*\*光色\*\*[：:]\s*(.+?)(?:\n|$)", t).group(1).strip()
    图 = os.path.join(根, "作品", "觉醒", f"01_格{n}.png")

    尾 = ("Preserve facial identity and natural skin texture. Keep the same person, "
          "the same clothing and the same location as the reference image. "
          "Natural ambient sound matching the scene; no dialogue.")

    写法 = {
        "A-现状": f"{动作}。环境：{光}。A continuous cinematic shot. {尾}",
        "B-英文在前": (f"A continuous cinematic scene with no text, captions or subtitles "
                    f"anywhere in frame. {动作}。Lighting: {光}。{尾}"),
        "C-中文当字段": (
            f"Scene brief (the bracketed text is a production note, NOT on-screen text): "
            f"[action: {动作}] [lighting: {光}]. Render it as a clean live-action shot "
            f"whose frame contains no writing of any kind. {尾}"),
    }

    print("=" * 78)
    print(f"  提示词写法试验 —— 格{n}　端点 {参.端点}")
    print("=" * 78)
    print(f"  动作：{动作[:80]}")
    print(f"  光色：{光[:80]}")
    print(f"  图：{图}　存在={os.path.isfile(图)}")
    print()

    成 = []
    for i, (名, 词) in enumerate(写法.items(), 1):
        print(f"  ── {名}")
        print(f"     提示词：{词[:100]}…")
        片 = 跑(词, 图, n * 10 + i, 服务=服务)
        if not 片:
            continue
        条 = os.path.join(根, "作品", "觉醒", f"_试字幕_格{n}_{名}.png")
        if 底部条(片, 条):
            成.append((名, 条))

    if not 成:
        print("\n  ✗ 一条都没跑出来")
        return 1

    from PIL import Image, ImageDraw
    图s = [(名, Image.open(条).convert("RGB")) for 名, 条 in 成]
    W = 1280
    条高 = [int(im.height * W / im.width) for _, im in 图s]
    H = sum(h + 26 for h in 条高)
    版 = Image.new("RGB", (W, H), (10, 10, 10))
    笔 = ImageDraw.Draw(版)
    y = 0
    for (名, im), h in zip(图s, 条高):
        版.paste(im.resize((W, h), Image.LANCZOS), (0, y + 26))
        笔.text((8, y + 6), 名, fill=(255, 220, 80))
        y += h + 26
    出 = os.path.join(根, "作品", "觉醒", f"_试字幕_格{n}_对比.png")
    版.save(出)
    print(f"\n  ✓ {出}")
    print(f"     {版.width}×{版.height}　从上到下：" + " / ".join(名 for 名, _ in 图s))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
