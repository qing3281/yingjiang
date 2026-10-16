# -*- coding: utf-8 -*-
"""出子镜 —— 把「首帧 → 中间帧 → 末帧」切成 4 小段，每小段两端都钉死。

## 为什么要这么切（实测，不是设计出来的）

用户 2026-10-16 08:46 的原话：①「根本就没有语音」②「字幕也非常非常少的可怜」
③「你不是要看一下时间吗？」④「一镜里像看图片」⑤「中间视频不能用以前出现过的这些问题」。

根因量出来的：
- 旧路（`_出H3.py`）一格只喂 01_格N.png 一张图、一次生成 107 帧 = 4.46 秒，
  模型要在这 4.46 秒里**凭空演完**整格的跨度（实测首→末像素中位差 40.38）。
  用户让我生成的 96 张中间帧**一张都没进去**（`_出H3.py` 里「中间帧」0 命中）。
- 想把整格拉成 226 帧一次出（32 格 × 226 = 5:01，正好 5 分钟）——
  **实测 OOM**（2026-10-16 10:0x，远端 15.89 GB：已占 12.25 GiB、还差 4.20 GiB）。

## 所以：不一次出整格，改成四小段

一格有 5 个关键帧：`01_格N.png` → `02_中N_1/2/3.png` → `末帧\末_格N.png`
→ 切 4 小段，每段 56 帧 = 2.3333 秒，两端都是**已经生成好的真图**（FL2VA）。
32 格 × 4 段 = 128 段 × 56 帧 = 7168 帧 = **298.7 秒 = 4 分 58.7 秒**。
56 是 17n+5 网格上的合法点（5,22,39,56,73,90,107,124,…），且比 107 短 → 必装得下。

★ 网格这一个数不许改：不在网格上会被节点**悄悄**吸附到下一个点，日志一个字都不报。
   实测过的坑：109 → 被吸到 124。

## 格32 特殊

`末帧` 目录只有 31 张（格32 后面没有下一格了）。所以格32 的第 4 段走 I2VA
（只喂首帧，不喂末帧）—— 和 `_出H3.py` 的老做法一致。

## 用法

    python _出子镜.py 楚子航 --端点 远端 --只镜 1-1,1-2 --跳过已有
    python _出子镜.py 楚子航 --端点 本机 --只格 2,4,6
    python _出子镜.py 楚子航 --端点 远端 --全部 --跳过已有

产物落 `影匠\作品\戏名\子镜\格N_k.mp4`（戏名里不要写反斜杠加尖括号，那是非法转义序列，Python 会报 SyntaxWarning）。
"""
import os
import sys
import json
import time
import shutil
import urllib.parse
import urllib.request
import urllib.error

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)
import _出H3 as H

帧数 = 56                    # ★ 必须落在 17n+5 网格上（见文件头）
帧率 = 24
每段秒 = 帧数 / 帧率         # 56/24 = 2.33333

词尾 = ("One single continuous take. The movement described above happens visibly and "
        "gradually, starting in the first moment and finishing by the last; the pose at the "
        "end of the clip is clearly different from the pose at the start. Keep the same "
        "person, the same clothing and the same location as the reference image, and "
        "preserve facial identity and natural skin texture. "
        "Natural ambient sound matching the scene; no dialogue.")


def 关键帧(目, 号):
    """一格的 5 个关键帧（格32 只有 4 个）。返回 [(序号, 路径), ...]。"""
    列 = [(0, os.path.join(目, "01_格%d.png" % 号))]
    for k in (1, 2, 3):
        列.append((k, os.path.join(目, "02_中%d_%d.png" % (号, k))))
    末 = os.path.join(目, "末帧", "末_格%d.png" % 号)
    if os.path.isfile(末):
        列.append((4, 末))
    return 列


def 子镜表(目):
    """[(号, 段, 首路, 末路 or ""), ...]。段 = 1..4；末路 = "" 表示这一段走 I2VA。"""
    表 = []
    for 号 in range(1, 33):
        列 = 关键帧(目, 号)
        for i in range(len(列) - 1):
            表.append((号, i + 1, 列[i][1], 列[i + 1][1]))
        if len(列) == 4:                      # 格32：最后一小节没有末帧 → I2VA 补满 4 段
            表.append((号, 4, 列[3][1], ""))
    return 表


def 取尾帧(视频, 出图):
    """把一段 mp4 的**最后一帧真的写出来**，当下一段的首帧用。

    ★ 2026-10-16 09:5x 加。用户的原话点破了要害：
      「你上一镜的尾帧内容是下一镜的首帧，不可能会跳」—— 他是对的，
      而我没这么做：我给下一段的首帧喂的是**该走到的关键帧图**，
      不是上一段**真出来的尾帧**。两者差多少？实测接缝 MAE 中位 38.63，
      而正常一帧只动 4.05（9.5 倍）—— 就是每 2.33 秒硬跳一次。
      链起来之后，接缝按定义就是 0。
    """
    import cv2
    if not os.path.isfile(视频):
        return False
    cap = cv2.VideoCapture(视频)
    末 = None
    while True:
        好, f = cap.read()
        if not 好:
            break
        末 = f
    cap.release()
    if 末 is None:
        return False
    os.makedirs(os.path.dirname(出图), exist_ok=True)
    好, buf = cv2.imencode(".png", 末)      # ★ 中文路径下 imwrite 静默失败，必须走 imencode
    if not 好:
        return False
    with open(出图, "wb") as fh:
        fh.write(buf.tobytes())
    return True


def 出段(服务, 端点名, 首路, 末路, 词, 种子值, 前缀, 出):
    首名 = H.传图(服务, 首路)
    末名 = H.传图(服务, 末路) if 末路 else ""
    H.帧数 = 帧数
    图d = H.建图(首名, 词, 0, 种子值, 前缀, 末名)
    # 建图 用模块全局 帧数 填 length；宽/高 也直接用 H 的（不自己传，免得和模型对不上）
    r = urllib.request.Request(f"{服务}/prompt",
                               data=json.dumps({"prompt": 图d}).encode(),
                               headers={"Content-Type": "application/json"})
    try:
        d = json.load(urllib.request.urlopen(r, timeout=180))
    except urllib.error.HTTPError as e:
        体 = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"POST /prompt 被拒 {e.code}：{体[:1200]}") from None
    if d.get("node_errors"):
        raise RuntimeError("节点错误 " + json.dumps(d["node_errors"], ensure_ascii=False)[:400])
    号p = d.get("prompt_id")
    for _ in range(1440):
        time.sleep(5)
        h = json.load(urllib.request.urlopen(f"{服务}/history/{号p}", timeout=30))
        if 号p not in h:
            continue
        st = h[号p].get("status", {})
        if st.get("status_str") != "success":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    raise RuntimeError("执行错 " + json.dumps(m[1], ensure_ascii=False)[:400])
            raise RuntimeError("status=" + str(st.get("status_str")))
        for _, o in h[号p].get("outputs", {}).items():
            for f in (o.get("gifs") or []):
                子 = f.get("subfolder", "")
                if 端点名 == "远端":
                    链接 = (f"{服务}/view?filename={urllib.parse.quote(f['filename'])}"
                            f"&subfolder={urllib.parse.quote(子)}&type=output")
                    with urllib.request.urlopen(链接, timeout=300) as 回, open(出, "wb") as 写:
                        while True:
                            块 = 回.read(1 << 20)
                            if not 块:
                                break
                            写.write(块)
                else:
                    源 = f.get("fullpath") or os.path.join(子, f["filename"])
                    if not os.path.isfile(源):       # 带音轨时 VHS 会给名字加 -audio 后缀
                        夹 = os.path.dirname(源)
                        茎 = os.path.splitext(os.path.basename(f["filename"]))[0].replace("-audio", "")
                        同 = [c for c in (os.listdir(夹) if os.path.isdir(夹) else [])
                               if c.startswith(茎) and c.lower().endswith(".mp4")]
                        if 同:
                            同.sort(key=lambda c: os.path.getmtime(os.path.join(夹, c)))
                            源 = os.path.join(夹, 同[-1])
                    if os.path.isfile(源):
                        shutil.move(源, 出)
                return os.path.getsize(出) > 10000
    raise RuntimeError("等超时（2 小时）")


def 解析(参):
    d = {"端点": "本机", "只镜": "", "只格": "", "全部": False, "跳过已有": False,
         "第4段I2VA": False, "全无末帧": False, "词尾": 词尾, "种子偏移": 0}
    i = 0
    while i < len(参):
        a = 参[i]
        if a == "--第4段I2VA":
            # ★ 2026-10-16 09:2x 加。理由量出来的：
            #   `_备末帧.py` 把「末_格N」定义成 01_格(N+1).png 的逐字节拷贝（原意「把 32 段焊死」）。
            #   于是第 4 小段（中3 → 末）**两端落在两个不同镜头里**，模型被逼着从本格变形到下一格。
            #   实测接缝 MAE：格3_4→格4_1 46.54、格4_4→格5_1 33.86、格1_4→格2_1 24.26，
            #   而段内「正常一帧动多少」只有 6.98（`check_接缝.py`）。
            #   不给末帧 → 它自由收尾在本格里 → 跨格处是一刀干净的硬切。
            d["第4段I2VA"] = True; i += 1
        elif a == "--全无末帧":
            # ★★ 2026-10-16 09:3x 加。**这是对照实验量出来的结论，不是拍脑袋。**
            #
            #   `check_怪帧.py` 扫 23 段，22 段都有「某一帧突然比旁边大几十倍」。
            #   摊开帧看（`_看子镜_格1_1.png` / `_看子镜_格3_2.png`）：
            #       格1_1  f10~f17 两个人慢慢走近，f18 突然跳近一截（单帧差 39.25，旁边只 1.5~3.1）
            #       格3_2  f24~f27 一样，f28 直接跳成近景（单帧差 24.85，旁边只 0.2）
            #
            #   对照实验 `_试I2VA.py`（同首帧、同词、同种子，只去掉末帧）：
            #       FL2VA  中位数 1.59  最大 39.25  倍数 24.7×   ← 中间一刀跳
            #       I2VA   中位数 3.47  最大  5.81  倍数  1.67×  ← 不跳了，而且动得更多（2.2 倍）
            #
            #   对照组：昨晚那批 107 帧的 `段\格N_*.mp4`，**32 段里 27 段（84%）也有同样的跳** ——
            #   所以这不是我这次切法引进来的，是「两头都钉死」这件事本身的代价。
            #
            #   代价：末帧不再钉死 → 相邻两小段之间是**切**不是焊。
            #   但每段的起点仍然是他让我生成的真关键帧，128 张全用上。
            d["全无末帧"] = True; i += 1
        elif a == "--端点":
            d["端点"] = 参[i + 1]; i += 2
        elif a == "--只镜":
            d["只镜"] = 参[i + 1]; i += 2
        elif a == "--只格":
            d["只格"] = 参[i + 1]; i += 2
        elif a == "--全部":
            d["全部"] = True; i += 1
        elif a == "--跳过已有":
            d["跳过已有"] = True; i += 1
        elif a == "--出口":
            # ★ 2026-10-16 11:0x 加。理由：正在跑的生产线已经把 87 段落进 `子镜\`，
            #   我要拿「末帧钉死 + 链式首帧」再试一遍 格3（它只走了 21%，是最差的一格），
            #   但**不能覆盖正在跑的那一版** —— 万一新的更差，旧的还得能拿出来。
            #   所以给它一个独立的出口目录，两边互不碰。
            d["出口"] = 参[i + 1]; i += 2
        elif a == "--种子偏移":
            d["种子偏移"] = int(参[i + 1]); i += 2
        else:
            i += 1
    return d


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    戏 = sys.argv[1]
    参 = 解析(sys.argv[2:])
    目 = os.path.join(根, "作品", 戏)
    if not os.path.isdir(目):
        print(f"✗ 没有这部戏：{目}")
        return 1
    子镜目 = os.path.join(目, "子镜" + 参.get("出口", ""))
    os.makedirs(子镜目, exist_ok=True)
    服务 = H.端点(参["端点"])

    动态 = H.读动态(戏)
    格 = H.读格(戏)

    表 = 子镜表(目)
    if 参["全无末帧"]:
        表 = [(号, 段, 首路, "") for (号, 段, 首路, 末路) in 表]
    elif 参["第4段I2VA"]:
        表 = [(号, 段, 首路, ("" if 段 == 4 else 末路)) for (号, 段, 首路, 末路) in 表]
    if 参["只镜"]:
        要 = set()
        for s in 参["只镜"].split(","):
            s = s.strip().replace(".", "-")
            if "-" in s:
                a, b = s.split("-")
                要.add((int(a), int(b)))
        表 = [x for x in 表 if (x[0], x[1]) in 要]
    elif 参["只格"]:
        要 = {int(x) for x in 参["只格"].split(",") if x.strip()}
        表 = [x for x in 表 if x[0] in 要]
    elif not 参["全部"]:
        print("要么给 --只镜 / --只格，要么给 --全部（不猜你的意思）")
        return 1

    print(f"═══ 出子镜　{戏}　{len(表)} 段 × {帧数} 帧（{每段秒:.4f} 秒）　{参['端点']} ═══")
    print(f"    总时长 {len(表) * 每段秒 / 24 * 24:.1f} 秒 = {len(表) * 每段秒 / 60:.2f} 分")

    t全 = time.time()
    出好数 = 0
    for k, (号, 段, 首路, 末路) in enumerate(表, 1):
        出 = os.path.join(子镜目, "格%d_%d.mp4" % (号, 段))
        if 参["跳过已有"] and os.path.isfile(出) and os.path.getsize(出) > 10000:
            print(f"  [{k}/{len(表)}] · 格{号}_{段} 已有，跳")
            出好数 += 1
            continue
        if not os.path.isfile(首路):
            print(f"  [{k}/{len(表)}] ✗ 格{号}_{段} 首帧不在：{首路}")
            continue
        # ★ 链式首帧：第 2/3/4 段的头，改成上一段**真出来的尾帧**。
        if 段 >= 2:
            上一条 = os.path.join(子镜目, "格%d_%d.mp4" % (号, 段 - 1))
            链首 = os.path.join(子镜目, "_链首", "格%d_%d.png" % (号, 段))
            if not 取尾帧(上一条, 链首):
                print(f"  [{k}/{len(表)}] ✗ 格{号}_{段} 拿不到上一段的尾帧（{上一条}），链断了，跳过")
                continue
            首路 = 链首
        g = 格.get(号, {})
        光 = g.get("光色", "")
        动作 = 动态.get(号) or g.get("动作") or "轻微的自然动作"
        词 = f"{动作}。环境：{光}。{参['词尾']}"
        种子值 = H.种子 + 号 * 1009 + 段 * 13 + 参["种子偏移"]
        前缀 = f"楚子航_子镜_格{号}_{段}"
        t0 = time.time()
        try:
            成 = 出段(服务, 参["端点"], 首路, 末路, 词, 种子值, 前缀, 出)
            mb = os.path.getsize(出) / 1048576 if os.path.isfile(出) else 0
            if 成:
                出好数 += 1
                print(f"  [{k}/{len(表)}] ✓ 格{号}_{段} {time.time()-t0:.1f} 秒  {mb:.2f} MB")
            else:
                print(f"  [{k}/{len(表)}] ✗ 格{号}_{段} 没出")
        except Exception as e:
            print(f"  [{k}/{len(表)}] ✗ 格{号}_{段} {type(e).__name__}: {e}")

    总 = time.time() - t全
    print(f"\n★ {出好数}/{len(表)} 段出来　用时 {总:.0f} 秒 = {总/60:.1f} 分")
    return 0 if 出好数 == len(表) else 1


if __name__ == "__main__":
    sys.exit(main())
