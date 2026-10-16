# -*- coding: utf-8 -*-
"""把《楚子航》这部片子的真实数字一次量出来 —— 给「这片子是怎么做出来的」那份汇报用。
原则：每一个数字都从磁盘上读，不许我从脑子里写。
"""
import glob, json, os, re, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

def 读(p):
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else ""

print("=" * 62)
print("《楚子航》真实数字")
print("=" * 62)

# 剧本
剧 = 读(os.path.join(目, "剧本.md"))
print("\n[剧本] %s" % os.path.join(目, "剧本.md"))
print("   字数 %d" % len(剧))

# 九宫格
格f = os.path.join(目, "02-九宫格.md")
格 = 读(格f)
格号 = sorted(set(int(m) for m in re.findall(r"格\s*(\d+)\s*[：:｜|]", 格)) | set(int(m) for m in re.findall(r"^###?\s*格\s*(\d+)", 格, re.M)))
print("\n[拆格] %s" % 格f)
print("   文件 %d 字节　识别到格号 %d 个：%s" % (len(格), len(格号), 格号[:40]))

# 动态提示词
动f = os.path.join(目, "04-动态提示词.md")
动 = 读(动f)
段行 = re.findall(r"^\s*-\s*动作\s*[：:]", 动, re.M)
print("\n[动态提示词] %s" % 动f)
print("   文件 %d 字节　「- 动作：」行 %d 条" % (len(动), len(段行)))

# 锚图 / 中间帧
图f = glob.glob(os.path.join(目, "图", "*.png")) + glob.glob(os.path.join(目, "图", "*.jpg"))
锚 = [p for p in 图f if "锚" in os.path.basename(p) or re.match(r"^\d+_格\d+", os.path.basename(p))]
中 = [p for p in 图f if "中间" in os.path.basename(p)]
print("\n[出图] 目录 %s" % os.path.join(目, "图"))
print("   总图 %d 张；其中中间帧 %d 张" % (len(图f), len(中)))

# 子镜
子 = sorted(glob.glob(os.path.join(目, "子镜", "*.mp4")))
对 = []
for p in 子:
    m = re.match(r"^格(\d+)_(\d+)\.mp4$", os.path.basename(p))
    if m:
        对.append((int(m.group(1)), int(m.group(2)), p))
print("\n[子镜] 目录 %s" % os.path.join(目, "子镜"))
print("   mp4 %d 个（其中符合 格N_M 命名 %d 个）" % (len(子), len(对)))
有格 = sorted(set(g for g, _, _ in 对))
print("   已出的格：%d 个 %s" % (len(有格), 有格))
缺 = [(g, s) for g in range(1, 33) for s in range(1, 5) if (g, s) not in [(a, b) for a, b, _ in 对]]
print("   还缺 %d 段：%s" % (len(缺), 缺[:20]))

# 一段的时长（抽 3 个量）
print("\n[一段多长] 抽样量（ffprobe）")
for p in (对[0][2] if 对 else None, 对[len(对)//2][2] if 对 else None, 对[-1][2] if 对 else None):
    if not p:
        continue
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", p], capture_output=True, text=True, timeout=30)
        s = (r.stdout or "").strip()
        print("   %-16s %s 秒  %d 字节" % (os.path.basename(p), s, os.path.getsize(p)))
    except Exception as e:
        print("   %s 量不了：%s" % (os.path.basename(p), e))

# 配音
表 = json.load(open(os.path.join(目, "配音", "_配音表.json"), encoding="utf-8"))
配 = 表.get("配音") or []
print("\n[配音] %d 句　合计 %.2f 秒" % (len(配), sum(float(x.get("秒") or 0) for x in 配)))

# 字幕
srt = glob.glob(os.path.join(目, "*.srt"))
print("\n[字幕] %s" % (srt or "（还没有 .srt）"))
for p in srt:
    t = 读(p)
    n = len(re.findall(r"^\d+\s*$", t, re.M))
    print("   %s　%d 条" % (os.path.basename(p), n))

# 成片
for p in glob.glob(os.path.join(目, "*.mp4")):
    print("\n[成片] %s  %d 字节  %s" % (os.path.basename(p), os.path.getsize(p),
                                       __import__("datetime").datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M:%S")))
