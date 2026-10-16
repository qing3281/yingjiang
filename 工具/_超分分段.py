# -*- coding: utf-8 -*-
"""_超分分段.py —— 把整条片**切成小段**再超分。

为什么必须分段（2026-10-16 实测到的真因，不是猜的）：
    整条 298.67 秒一次性提交，跑到 **317 秒**时远端报
        `Unable to allocate 14.0 MiB for an array with shape (832, 1472, 3) and data type float32`
    —— 不是显存，是**系统内存**。那个节点（SeedVR2Preprocess → … → SeedVR2PostProcessing）
    把**所有帧**留在内存里，而且 `SeedVR2PostProcessing` 同时吃
    `images`（解出来的）和 `original_resized_images`（放大后的输入）两份：
        7168 帧 × 2 × (1472×832×3×4 字节 = 14.7 MB) ≈ **210 GB**
    远端只有 47.2 GB 内存（提交时 41.4 GB 空闲）→ 必爆。
    20 秒小样（480 帧 ≈ 14 GB）跑得动 —— 所以**按 20 秒切**，一段一段来。

补帧位置也量过了（免得切错地方）：20 秒 480 帧进去、481 帧出来，
    `原[i] vs 超[i]` 的 MAE 一路 5.5–6.0（含最后一帧 479），`原[i] vs 超[i+1]` 反而更大
    → **多出来的那一帧在尾部**，所以合并时按每段的**输入帧数**从头截断是安全的。

用法：
    python _超分分段.py --切            # 切段，打印每段帧数并核对总数
    python _超分分段.py --交            # 逐段传远端 + 提交（全部排进队列）
    python _超分分段.py --收            # 等每段跑完并下载
    python _超分分段.py --合            # 截断 + 拼接 → 一条无声的 2× 片
    python _超分分段.py --看            # 段/提交/下载状态
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import cv2

sys.path.insert(0, r"D:\DSHworkspace")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
sys.stdout.reconfigure(encoding="utf-8")

import _超分 as 超  # noqa: E402   （复用它里面验证过的 送过去 / 提交 / 历史 / 请求）

源 = r"D:\DSHworkspace\影匠\作品\楚子航\片_官方\楚子航_混音.mp4"
家 = r"D:\DSHworkspace\_超分分段"
段目录 = os.path.join(家, "段")
超目录 = os.path.join(家, "超")
账 = os.path.join(家, "段账.json")
远端 = "http://100.127.224.106:8188"
FF = r"D:\DSHworkspace\影匠\_bin\ffmpeg.exe"
每段秒 = 20
倍数 = 2


def 帧数(路):
    c = cv2.VideoCapture(路)
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    c.release()
    return n


def 尺寸(路):
    c = cv2.VideoCapture(路)
    d = (int(c.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), int(c.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
    c.release()
    return d


def 读账():
    if os.path.isfile(账):
        return json.load(open(账, encoding="utf-8"))
    return {"源": 源, "每段秒": 每段秒, "段": []}


def 写账(d):
    os.makedirs(家, exist_ok=True)
    json.dump(d, open(账, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def 切():
    if not os.path.isfile(源):
        raise SystemExit("找不到源片：%s" % 源)
    os.makedirs(段目录, exist_ok=True)
    os.makedirs(超目录, exist_ok=True)
    for n in os.listdir(段目录):
        if n.lower().endswith(".mp4"):
            os.remove(os.path.join(段目录, n))
    总帧 = 帧数(源)
    print("▶ 源 %s　%d 帧" % (os.path.basename(源), 总帧))
    # ★ `-c copy` 只在关键帧上切，所以每段不会正好 480 帧 —— 但**无损**，
    #   而且每段帧数等下自己量出来，合并时按量到的数截断，不靠推算。
    r = subprocess.run(
        [FF, "-y", "-v", "error", "-i", 源,
         "-c", "copy", "-map", "0", "-f", "segment",
         "-segment_time", str(每段秒), "-reset_timestamps", "1",
         os.path.join(段目录, "段%02d.mp4")],
        capture_output=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg 切段失败：" + (r.stderr or b"").decode("utf-8", "replace")[:400])

    段们 = sorted(n for n in os.listdir(段目录) if n.lower().endswith(".mp4"))
    d = 读账()
    d["源"] = 源
    d["源帧数"] = 总帧
    d["每段秒"] = 每段秒
    d["段"] = []
    合 = 0
    print("")
    print("段    文件            帧数    秒     累计")
    print("--  --------------  ------  -----  ------")
    for i, n in enumerate(段们, 1):
        p = os.path.join(段目录, n)
        k = 帧数(p)
        合 += k
        d["段"].append({"号": i, "文件": n, "本机": p, "帧数": k,
                        "字节": os.path.getsize(p), "prompt_id": "", "远端产物": ""})
        print("%2d  %-14s  %6d  %5.2f  %6d" % (i, n, k, k / 24.0, 合))
    写账(d)
    print("")
    print("▶ %d 段，合计 %d 帧（源 %d）" % (len(段们), 合, 总帧))
    if 合 != 总帧:
        print("  ✗ 对不上，别往下走")
        return 1
    print("  ✓ 帧数对上了")
    return 0


def 交():
    d = 读账()
    if not d.get("段"):
        raise SystemExit("先跑 --切")
    for s in d["段"]:
        if s.get("prompt_id"):
            print("  ⏭ 段%02d 已提交（%s）" % (s["号"], s["prompt_id"][:8]))
            continue
        名 = 超.送过去(s["本机"])
        流 = 超.建工作流(名, 倍数, 超.模型_3B, 超.VAE,
                        "SRp%02d" % s["号"], "none", "manual", 21)
        r = 超.提交(流, 远端)
        if "prompt_id" not in r:
            print("  ✗ 段%02d 被拒：" % s["号"])
            超.说错(r)
            return 1
        s["prompt_id"] = r["prompt_id"]
        写账(d)
        print("  ✓ 段%02d（%s，%d 帧）→ %s" % (s["号"], s["文件"], s["帧数"], r["prompt_id"][:8]))
    print("▶ %d 段全部在队列里" % len(d["段"]))
    return 0


def 取产物(e):
    """从 history 的一条里挖出 (文件名, subfolder)。

    ★ 必须只认 `type == "output"` —— 这张图里**节点 1 也有一条 filename 记录**，
    那是 LoadVideo 的**输入**（`段00.mp4`, `type: "input"`）。第一版没分 type，
    挑中了输入那条，拿去 `/view` 下载就 404。
    """
    兜 = None
    for _, o in (e.get("outputs") or {}).items():
        for _, v in o.items():
            组 = v if isinstance(v, list) else [v]
            for it in 组:
                if not (isinstance(it, dict) and it.get("filename")):
                    continue
                if it.get("type") == "output":
                    return it["filename"], it.get("subfolder") or ""
                if 兜 is None:
                    兜 = it
    if 兜:
        return 兜["filename"], 兜.get("subfolder") or ""
    return None, ""


def 收():
    d = 读账()
    os.makedirs(超目录, exist_ok=True)
    待 = [s for s in d["段"] if not s.get("超本机")]
    if not 待:
        print("▶ 全部已下载")
        return 0
    起 = time.time()
    while 待:
        for s in list(待):
            if not s.get("prompt_id"):
                continue
            e = 超.历史(远端).get(s["prompt_id"])
            if not e:
                continue
            st = e.get("status") or {}
            for m in (st.get("messages") or []):
                if m[0] in ("execution_error", "execution_interrupted"):
                    print("  ★ 段%02d %s：" % (s["号"], m[0]))
                    超.说错(m[1])
                    return 1
            if not st.get("completed"):
                continue
            名, sub = 取产物(e)
            if not 名:
                print("  ✗ 段%02d 完成了但找不到产物" % s["号"])
                return 1
            去 = os.path.join(超目录, "段%02d_2x.mp4" % s["号"])
            u = "%s/view?filename=%s&subfolder=%s&type=output" % (
                远端, urllib.parse.quote(名), urllib.parse.quote(sub))
            with urllib.request.urlopen(u, timeout=600) as f, open(去 + ".part", "wb") as g:
                while True:
                    b = f.read(1 << 20)
                    if not b:
                        break
                    g.write(b)
            os.replace(去 + ".part", 去)
            s["远端产物"] = (sub + "/" + 名) if sub else 名
            s["超本机"] = 去
            s["超帧数"] = 帧数(去)
            s["超字节"] = os.path.getsize(去)
            写账(d)
            print("  ✓ 段%02d 落地　输入 %d 帧 → 输出 %d 帧　%.1f MB　[%.0f 分]"
                  % (s["号"], s["帧数"], s["超帧数"], s["超字节"] / 1048576,
                     (time.time() - 起) / 60))
            待.remove(s)
        if 待:
            q = 超.队列(远端)
            print("  …等 %d 段（队列 跑%d/等%d）　已 %.0f 分"
                  % (len(待), len(q.get("queue_running") or []),
                     len(q.get("queue_pending") or []), (time.time() - 起) / 60))
            time.sleep(30)
    print("▶ 全部下载完")
    return 0


def 合(音源="", srt="", 出=""):
    """截断 + 拼接（+ 贴人声 + 原生烧硬字幕），**一次 ffmpeg 编完**。

    为什么不在一次里做完：先拼成无声 2× 再交给 `_超分装配.py` 去贴音轨+烧字，
    视频就要被 H.264 **编两遍**。这里把 `trim → concat → subtitles → 贴音轨`
    串进同一条 filter_complex，只编一遍。
    字幕字号按 `宽/736` 等比放大（复用 `_超分装配.py` 的规矩），
    不是把 736 宽的字拉大 —— 那样字会糊。
    """
    d = 读账()
    缺 = [s for s in d["段"] if not s.get("超本机") or not os.path.isfile(s.get("超本机", ""))]
    if 缺:
        raise SystemExit("还有 %d 段没下载，先跑 --收" % len(缺))
    出 = 出 or os.path.join(家, "官方_2x_无声.mp4")
    命 = [FF, "-y", "-v", "error"]
    for s in d["段"]:
        命 += ["-i", s["超本机"]]
    有音 = bool(音源 and os.path.isfile(音源))
    if 音源 and not 有音:
        raise SystemExit("找不到音源：%s" % 音源)
    if 有音:
        命 += ["-i", 音源]

    链 = []
    for i, s in enumerate(d["段"]):
        链.append("[%d:v]trim=end_frame=%d,setpts=PTS-STARTPTS[v%d]" % (i, s["帧数"], i))
    链.append("".join("[v%d]" % i for i in range(len(d["段"])))
              + "concat=n=%d:v=1:a=0[cc]" % len(d["段"]))
    尾 = "[cc]"
    if srt and os.path.isfile(srt):
        # ★ 这里**不能**按「宽/736」把字号一起放大 —— 第一版就是这么写的，
        #   结果字幕冲出画面左右两边（`_试字号.py` 量出来：FontSize 44 时最长句
        #   占画面 100%、左右贴到 0 和 1467，字被切掉）。
        #   libass 本来就按**画面高度**缩放字号，我再乘一次 = 放大两倍。
        #   定下来的值（`_试字号.py` + `_试边距.py` 两张对照图）：
        #   字号 30 → 最长句占 86%（22 是 63%、34 贴边、44 溢出）；
        #   边距 48 → 字底距画面底 148 px = 18% 高，是最常见的字幕位。
        字号, 边距, 描边 = 30, 48, 4
        宽, _高 = 尺寸(d["段"][0]["超本机"])
        样 = ("FontName=Microsoft YaHei,FontSize=%d,PrimaryColour=&H00FFFFFF,"
              "OutlineColour=&H00000000,BorderStyle=1,Outline=%d,Shadow=1,MarginV=%d"
              % (字号, 描边, 边距))
        esc = srt.replace("\\", "/").replace(":", "\\:")
        链.append("%ssubtitles='%s':force_style='%s'[vv]" % (尾, esc, 样))
        尾 = "[vv]"
        print("▶ 字幕固定字号：FontSize=%d MarginV=%d Outline=%d（画面 %d 宽；量过不溢出）"
              % (字号, 边距, 描边, 宽))
    if 尾 == "[cc]":
        链.append("[cc]null[vv]")
        尾 = "[vv]"

    命 += ["-filter_complex", ";".join(链), "-map", 尾]
    命 += ["-map", "%d:a:0" % len(d["段"])] if 有音 else []
    命 += ["-shortest"] if 有音 else []
    命 += ["-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p"]
    命 += ["-c:a", "aac", "-b:a", "192k"] if 有音 else []
    命 += [出]

    print("▶ 拼接 %d 段（每段按输入帧数截断）%s → %s"
          % (len(d["段"]), "＋贴人声＋烧硬字幕" if 有音 else "", 出))
    r = subprocess.run(命, capture_output=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg 拼接失败：" + (r.stderr or b"").decode("utf-8", "replace")[:800])
    应 = sum(s["帧数"] for s in d["段"])
    得 = 帧数(出)
    print("   应有 %d 帧，实得 %d 帧　%.1f MB" % (应, 得, os.path.getsize(出) / 1048576))
    if 得 != 应:
        print("  ✗ 帧数对不上")
        return 1
    if 有音:
        有 = subprocess.run([FF, "-hide_banner", "-i", 出], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
        if not any("Audio" in l for l in (有.stderr or "").splitlines()):
            print("  ✗ 产物没有音轨")
            return 1
        print("  ✓ 有音轨")
    print("  ✓ 帧数对上了")
    return 0


def 看():
    d = 读账()
    if not d.get("段"):
        print("还没切段")
        return 0
    print("段   文件            帧数   提交        超帧数  下载")
    for s in d["段"]:
        print("%2d  %-14s  %5d  %-10s  %5s  %s"
              % (s["号"], s["文件"], s["帧数"], (s.get("prompt_id") or "—")[:8],
                 s.get("超帧数") or "—", "✓" if s.get("超本机") else "—"))
    print("源帧数 %s　段合计 %d" % (d.get("源帧数"), sum(s["帧数"] for s in d["段"])))
    return 0


def 主():
    参 = argparse.ArgumentParser()
    for k in ("切", "交", "收", "合", "看"):
        参.add_argument("--" + k, action="store_true")
    参.add_argument("--音源", default=r"D:\DSHworkspace\影匠\作品\楚子航\片_官方\楚子航_混音.mp4")
    参.add_argument("--srt", default=r"D:\DSHworkspace\影匠\作品\楚子航\片_官方\台词.srt")
    参.add_argument("--出", default="")
    a = 参.parse_args()
    if a.切:
        return 切()
    if a.交:
        return 交()
    if a.收:
        return 收()
    if a.合:
        return 合(a.音源, a.srt, a.出)
    return 看()


if __name__ == "__main__":
    sys.exit(主())
