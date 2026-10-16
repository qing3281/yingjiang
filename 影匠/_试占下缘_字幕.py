# -*- coding: utf-8 -*-
"""测「占住画面下缘」能不能治住模型画字幕。

## 为什么要这一测

格55 / 格56 换了两轮种子（777001、991337）**都有字**，而其它 6 格一换就干净。
看首帧就明白了：

- 格55 首帧：**一大块白桌布占满整个下三分之一** —— 那就是一块现成的字幕板
- 格56 首帧：灰桌面同样空

**字是长在「大片空白浅色横带」上的**，不是随机事件。所以光换种子治不了这两格。

## 这一测改什么

在原有 光色 后面**加一句描述画面下缘有什么东西**，把那条空带填掉。
动的是提示词，不动首帧（首帧已经是对的构图）。

    python _试占下缘_字幕.py 55
    python _试占下缘_字幕.py 55 --两法
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


def 取根():
    return os.path.dirname(os.path.abspath(__file__))


根 = 取根()
FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")

# 两种「占住下缘」的说法：物件型 / 构图型
说法表 = [
    ("物件", "画面下缘被桌沿、墨盒和笔筒占住，那块白布只露出中间一段，"
             "布面上有压痕和落下的影子，没有一处是空的"),
    ("构图", "镜头压低，画面上缘切在人物胸口，下缘是桌沿和桌上的墨盒、笔筒、"
             "摊开的册子，不留空"),
]


def 载出H3():
    路 = os.path.join(根, "_出H3.py")
    规 = importlib.util.spec_from_file_location("_出H3mod", 路)
    m = importlib.util.module_from_spec(规)
    规.loader.exec_module(m)
    return m


def 等它出(服务, 号p, 出, 端点):
    """照抄 _出H3.py 的等待 + 取回逻辑（远端走 HTTP /view）。"""
    for _ in range(1440):
        time.sleep(5)
        h = json.load(urllib.request.urlopen(f"{服务}/history/{号p}", timeout=30))
        if 号p not in h:
            continue
        st = h[号p].get("status", {})
        if st.get("status_str") != "success":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print(f"       ✗ 执行错 {json.dumps(m[1], ensure_ascii=False)[:400]}")
            return False
        for _, o in h[号p].get("outputs", {}).items():
            for f in (o.get("gifs") or []):
                子 = f.get("subfolder", "")
                if 端点 == "远端":
                    链接 = (f"{服务}/view?filename={urllib.request.quote(f['filename'])}"
                            f"&subfolder={urllib.request.quote(子)}&type=output")
                    try:
                        with urllib.request.urlopen(链接, timeout=300) as 回, open(出, "wb") as 写:
                            while True:
                                块 = 回.read(1 << 20)
                                if not 块:
                                    break
                                写.write(块)
                        return os.path.getsize(出) > 10000
                    except Exception as e:
                        print(f"       ✗ 下载失败 {type(e).__name__}: {e}")
                        return False
                else:
                    源 = os.path.join(r"D:\Comfy-Desktop\ComfyUI-Shared\output", 子, f["filename"])
                    if os.path.isfile(源):
                        import shutil
                        shutil.move(源, 出)
                        return True
        return False
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("格", type=int)
    ap.add_argument("--两法", action="store_true", help="两种说法各跑一遍（各约 3 分钟）")
    ap.add_argument("--端点", default="本机")
    参 = ap.parse_args()

    H = 载出H3()
    服务 = H.端点(参.端点)
    图 = os.path.join(根, "作品", "觉醒", f"01_格{参.格}.png")
    if not os.path.isfile(图):
        print(f"  ✗ 没有 {图}")
        return 1

    格表 = H.读格("觉醒")
    if 参.格 not in 格表:
        print(f"  ✗ 02-九宫格.md 里没有格{参.格}")
        return 1
    格 = 格表[参.格]
    动, 光 = 格["动作"], 格["光色"]
    print(f"  格{参.格}　{格['题']}")
    print(f"  动作：{动}")
    print(f"  原光色：{光}\n")

    挑 = 说法表 if 参.两法 else 说法表[:1]
    出s = []
    for 名, 加 in 挑:
        词 = (f"{动}。环境：{光}；{加}。"
              "A continuous cinematic shot. Preserve facial identity and natural skin texture. "
              "Keep the same person, the same clothing and the same location as the reference image. "
              "Natural ambient sound matching the scene; no dialogue.")
        print(f"  ── {名}说法（{len(词)} 字）")
        t0 = time.time()
        try:
            名s = H.传图(服务, 图)
            d = H.建图(名s, 词, 参.格, 424242 + 参.格 * 1009, f"占下缘_{参.格}{名}")
            r = urllib.request.Request(f"{服务}/prompt",
                                       data=json.dumps({"prompt": d}).encode(),
                                       headers={"Content-Type": "application/json"})
            try:
                j = json.load(urllib.request.urlopen(r, timeout=180))
            except urllib.error.HTTPError as e:
                print(f"     ✗ POST 被拒 {e.code}：{e.read().decode('utf-8','replace')[:500]}")
                continue
        except Exception as e:
            print(f"     ✗ {type(e).__name__}: {e}")
            continue

        出 = os.path.join(根, "作品", "觉醒", "_重抽", f"格{参.格}_{参.端点}_占{名}.mp4")
        os.makedirs(os.path.dirname(出), exist_ok=True)
        ok = 等它出(服务, j["prompt_id"], 出, 参.端点)
        print(f"     {'✓' if ok else '✗'} {time.time()-t0:.0f} 秒  {os.path.basename(出)}")
        if ok:
            出s.append((名, 出))

    if not 出s:
        print("\n  ✗ 一个都没出")
        return 1

    from PIL import Image, ImageDraw
    临 = os.path.join(根, "作品", "觉醒", "_占条")
    os.makedirs(临, exist_ok=True)
    条s = []
    for 名, p in 出s:
        for j, t in enumerate((1.0, 2.2, 3.2)):
            o = os.path.join(临, f"{名}_{j}.png")
            subprocess.run([FFMPEG, "-y", "-ss", str(t), "-i", p,
                            "-vf", "crop=iw:ih*0.26:0:ih*0.74", "-frames:v", "1", o],
                           capture_output=True)
            if os.path.isfile(o):
                条s.append((名, t, o))
    if not 条s:
        print("  ✗ 抽帧失败")
        return 1
    图s = [Image.open(o).convert("RGB") for _, _, o in 条s]
    W, Hh = 900, int(图s[0].height * 900 / 图s[0].width)
    图s = [im.resize((W, Hh), Image.LANCZOS) for im in 图s]
    列 = 3
    行 = (len(图s) + 列 - 1) // 列
    版 = Image.new("RGB", (W * 列, (Hh + 20) * 行), (8, 8, 8))
    笔 = ImageDraw.Draw(版)
    for i, im in enumerate(图s):
        r, c = divmod(i, 列)
        x, y = c * W, r * (Hh + 20)
        版.paste(im, (x, y))
        笔.text((x + 5, y + Hh + 2), f"{条s[i][0]}·{条s[i][1]}s", fill=(255, 220, 80))
    出图 = os.path.join(根, "作品", "觉醒", f"_占下缘_格{参.格}.png")
    版.save(出图)
    import shutil
    shutil.rmtree(临, ignore_errors=True)
    print(f"\n  ✓ {出图}  {版.width}×{版.height}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
