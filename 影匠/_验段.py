# -*- coding: utf-8 -*-
"""逐段验证：时长/分辨率/帧率/能不能解码。段坏了要在这里拦住，不能等接完片才发现。

用法：
    python _验段.py 雪线
    python _验段.py 雪线 --要帧 73 --要宽 1344 --要高 768
"""
import argparse
import importlib.util
import os
import sys

根 = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("视频", os.path.join(根, "视频.py"))
视频 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(视频)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--要宽", type=int, default=1344)
    ap.add_argument("--要高", type=int, default=768)
    ap.add_argument("--要帧", type=int, default=73)
    ap.add_argument("--容差帧", type=int, default=3)
    参 = ap.parse_args()

    d = os.path.join(根, "作品", 参.戏, "段")
    if not os.path.isdir(d):
        print(f"✗ 没有 {d}")
        return 1

    好, 坏 = [], []
    for f in sorted(os.listdir(d)):
        if not f.endswith(".mp4"):
            continue
        p = os.path.join(d, f)
        try:
            s = 视频.探视频(p)
        except Exception as e:
            print(f"  ✗ {f}  探不动：{e}")
            坏.append(f)
            continue
        帧 = round(s["秒"] * s["帧率"])
        嫌 = []
        if s["宽"] != 参.要宽 or s["高"] != 参.要高:
            嫌.append(f"尺寸 {s['宽']}×{s['高']}")
        if abs(帧 - 参.要帧) > 参.容差帧:
            嫌.append(f"帧数 {帧}（要 {参.要帧}）")
        if s["秒"] < 1.0:
            嫌.append(f"只有 {s['秒']:.2f} 秒")
        if 嫌:
            print(f"  ✗ {f}  {'；'.join(嫌)}")
            坏.append(f)
        else:
            好.append(f)

    print(f"\n好 {len(好)} 段　坏 {len(坏)} 段" + (f"　坏的是 {坏}" if 坏 else ""))
    return 1 if 坏 else 0


if __name__ == "__main__":
    sys.exit(main())
