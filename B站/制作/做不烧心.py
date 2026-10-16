# -*- coding: utf-8 -*-
"""《不烧心》30 镜总调度 —— 剧本 → 首帧 → 动态 → 成片。

用户 m03366：「角色出全以后，就继续生成视频吧……用本地的，尽量少用 token」

## 流水线

```
不烧心_剧本.md
   ↓ 解析（本文件 读剧本）
30 个镜头（布景/人物/动作/台词/表情/字幕）
   ↓ 出首帧（出图_纯文本.py，Qwen-Image 2512，40 步）
     【画风锁 + 出场角色的形象锁 + 布景 + 动作 + 表情 + 构图】
   ↓ 动态（MiniMax H3 fl2va 768p 4步 + turbo LoRA，本地）
     【台词写进提示词，模型对口型 + 自带音频】
   ↓ 合成（视频拼接.py / 配音.py）
```

## 用法

```bash
python 做不烧心.py --出首帧                 # 30 张首帧
python 做不烧心.py --出首帧 --只 1 2 3      # 只出指定镜
python 做不烧心.py --出动态                 # 30 条动态（慢，约 75 分钟）
python 做不烧心.py --出动态 --只 1          # 单镜试
python 做不烧心.py --列                     # 只解析剧本，看解析对不对
```

产物：
- 首帧 `D:\\DSHworkspace\\B站\\成片\\不烧心\\镜\\NN_首帧.png`
- 动态 `D:\\DSHworkspace\\B站\\成片\\不烧心\\镜\\NN_动态.mp4`
- 提示词留档 `D:\\DSHworkspace\\B站\\成片\\不烧心\\镜\\提示词.json`
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

from PIL import Image

from 出3D定妆 import 画风锁, 角色表
from 出图_纯文本 import 跑 as 纯文本跑

剧本 = r"D:\DSHworkspace\B站\制作\不烧心_剧本.md"
出根 = r"D:\DSHworkspace\B站\成片\不烧心\镜"

# 首帧尺寸：MiniMax fl2va 吃 16:9 的 768p，1536×864 正好
首帧宽, 首帧高 = 1536, 864

# 剧本里的人物名 → 角色表的键。一镜可能有多个人。
人物键 = {
    "DeepSeek 鲸鱼娘": ["deepseek"],
    "DeepSeek": ["deepseek"],
    "鲸鱼娘": ["deepseek"],          # 镜 10 的「人物」字段只写了「鲸鱼娘」
    "GPT 龙娘": ["gpt"],
    "GPT": ["gpt"],
    "Claude 娘": ["claude"],
    "Claude": ["claude"],
    "豆包娘": ["doubao_b"],      # 出场即「吃了白饭」的胖版；镜 11 是刚端碗，还没吃
    "Kimi 娘": ["kimi"],
    "GLM 娘": ["glm"],
    "千问娘": ["qwen"],
}
# 镜 11 豆包刚端碗、还没吃，用「前」
豆包前镜 = {11}

# 景别：剧本没写，按镜头内容给一个。避免全片一个机位。
景别 = {
    1: "大远景，街道全景，无人",
    2: "中景，侧面，火光从下方打上来",
    3: "大特写，只拍墙上飞转的电表铜盘",
    4: "中近景，过肩，桌面占画面下半",
    5: "中景，仰拍门框上的木牌",
    6: "中景，人群围成半圈",
    7: "中景，仰拍门口挂招牌",
    8: "近景，正脸，碗占画面下半",
    9: "中景，锅台前",
    10: "全景，队伍从铺子门口排到街尾",
    11: "中景，长桌边",
    12: "中近景，回头，背景是对门空铺",
    13: "近景，正脸",
    14: "特写，额头与头顶",
    15: "中近景，斜侧",
    16: "中景，马扎上",
    17: "中近景，扶着墙",
    18: "大远景，整条街的群像",
    19: "中景，趴在碗堆上",
    20: "中景，人群背对镜头指着铺子里",
    21: "中景，窗边，侧逆光",
    22: "中景，两人对坐，过肩",
    23: "近景，正脸，午后斜光",
    24: "中景，柜台前",
    25: "中景，提灯，三个木箱在前景",
    26: "中景，后门口，光柱",
    27: "中近景，背对镜头然后转身",
    28: "中景，门口",
    29: "中景，队伍第一人抬头",
    30: "大远景，清晨薄雾，背影走远",
}


def 读剧本(路: str) -> list[dict]:
    """把 不烧心_剧本.md 解析成 [{号, 标题, 布景, 人物, 动作, 台词, 表情, 声音, 字幕}]"""
    with open(路, encoding="utf-8") as f:
        行们 = f.read().splitlines()

    镜们: list[dict] = []
    当前 = None
    字段 = ("布景", "人物", "动作", "台词", "表情", "声音", "字幕")

    for 行 in 行们:
        m = re.match(r"^###\s*镜\s*(\d+)\s*[　\s]*(.*)$", 行.strip())
        if m:
            if 当前:
                镜们.append(当前)
            当前 = {"号": int(m.group(1)), "标题": m.group(2).strip()}
            continue
        if 当前 is None:
            continue
        mm = re.match(r"^-\s*\*\*(%s)\*\*[：:]\s*(.*)$" % "|".join(字段), 行.strip())
        if mm:
            当前[mm.group(1)] = mm.group(2).strip()
            continue
        # 「人物」那行可能是 `- **人物**：GPT 龙娘 + 群众`
        if 行.strip().startswith("## "):
            镜们.append(当前)
            当前 = None
    if 当前:
        镜们.append(当前)

    镜们.sort(key=lambda x: x["号"])
    return 镜们


def 挑角色(镜: dict) -> list[str]:
    人 = 镜.get("人物", "") or ""
    if "无" == 人.strip():
        return []
    键们: list[str] = []
    for 名, ks in 人物键.items():
        if 名 in 人:
            for k in ks:
                if k not in 键们:
                    键们.append(k)
    # 镜 11 的豆包是「还没吃」那版
    if 镜["号"] in 豆包前镜 and "doubao_b" in 键们:
        键们[键们.index("doubao_b")] = "doubao_a"
    # 剧本里写「群众」时不要硬塞 AI 娘
    return 键们


def 造提示词(镜: dict) -> tuple[str, str]:
    """返回 (正向, 负向)"""
    键们 = 挑角色(镜)
    有脸 = bool(键们)

    角色段 = ""
    for i, k in enumerate(键们):
        c = 角色表[k]
        角色段 += f"\n【角色 {i+1}：{c['名']} —— 逐条照做，不许改设计】{c['词']}"

    群众段 = ""
    if "群众" in (镜.get("人物") or ""):
        群众段 = ("\n【群众】几个穿粗布衣裳的普通人，路人脸，不抢镜，"
                  "不要画成动漫角色。")

    台词 = 镜.get("台词", "") or ""
    字幕 = 镜.get("字幕", "") or ""

    正 = (
        f"【任务】画出 3D 卡通渲染动画《不烧心》的第 {镜['号']:02d} 个镜头的一帧。\n\n"
        f"【镜头】{景别.get(镜['号'], '中景')}\n"
        f"【场景】算力街 —— 一条中国青石板老街，两边是木结构的老铺子，"
        f"门口挂褪色红灯笼。{镜.get('布景','')}\n"
        f"【这一镜在发生什么】{镜.get('动作','')}\n"
        f"【表情】{镜.get('表情','') or '自然'}\n"
        f"{角色段}{群众段}\n\n"
        f"【画面要求】横向 16:9 构图，像动画的一帧，不是设定图不是三视图不是分格。"
        f"画面里只有这一镜该有的人，不要多画。"
        f"**画面上绝对不要出现任何文字、字幕、招牌上的字、水印、签名、边框。**\n\n"
        f"{画风锁}"
    )
    负 = ("文字, 字幕, 招牌文字, 水印, 签名, 边框, logo, 分格, 拼图, 三视图, 设定表, "
          "多个同一角色, 写实, 照片, 真人, 阴暗, 暗沉, 低饱和, 血腥, 恐怖, 畸形, 多手多脚")
    return 正, 负


def 出首帧(镜: dict, 种子: int) -> str | None:
    p = os.path.join(出根, f"{镜['号']:02d}_首帧.png")
    if os.path.isfile(p):
        print(f"  ↷ 已有，跳过")
        return p
    正, 负 = 造提示词(镜)
    print(f"  画风锁+{len(挑角色(镜))}个角色，{首帧宽}×{首帧高}")
    r = 纯文本跑(正, 种子=种子, 宽=首帧宽, 高=首帧高, 负面=负)
    if not r:
        return None
    Image.open(r).convert("RGB").save(p)
    print(f"  ✓ {p}")
    return p


def 提台词(原: str) -> str:
    """从剧本的「台词」字段里把真正要说出口的那句抠出来。

    `**「一个 token 一个价。不还价。」**`              → 一个 token 一个价。不还价。
    `（群众七嘴八舌）「这也太贵了」「用不起用不起」`      → 这也太贵了 用不起用不起
    `（梦话）**「我去吃饭……测完告诉我就行……」**`      → 我去吃饭……测完告诉我就行……
    没有引号就整句去掉括号备注。
    """
    if not 原:
        return ""
    句 = re.findall(r"[「『\"]([^」』\"]+)[」』\"]", 原)
    if 句:
        return " ".join(s.strip() for s in 句 if s.strip())
    # 没引号：去掉 markdown 加粗和（）备注
    s = re.sub(r"\*\*", "", 原)
    s = re.sub(r"（[^）]*）|\([^)]*\)", "", s)
    s = s.strip(" 。，、:：")
    # ★ 坑：剧本里表示「这一镜没人说话」写的是「无」，别把它当台词喂给模型
    if s.strip(" 。，、:：（）()…—–-") in ("无", "無", "none", "None", "N/A"):
        return ""
    return s


def 造动态提示词(镜: dict) -> str:
    """给 MiniMax 的动作描述。

    ★ 必须**全英文**。MiniMax H3 fl2va 会把提示词里能读的中文念出来——
      第一版直接把剧本的中文「动作」字段拼进 `Action: ...`，结果每条音轨都是
      「动作旁白 + 台词」两条声音叠在一起（Whisper 转写第一条出来就是
      「空镜 只有风把地上的纸吹过」）。所以动作/表情一律走 `动态词表.py`
      的英文，中文字符只允许出现在台词的引号里。
    """
    from 动态词表 import 取动态词
    动作, 表情 = 取动态词(镜["号"])
    动作 = 动作 or "almost still, only very subtle natural motion"
    # ★ 坑②：**提示词要短**。整套提示词都会被模型当「要念的内容」看，
    #   写「Shot 04 of a short drama.」「Keep the character design and art style
    #   exactly as in the first frame.」这种话，遇到台词本来就短的镜头
    #   （比如镜 04 只有「……涨。」一个字），模型就拿这些英文去填时间，
    #   Whisper 转写出来是一串毫不相干的音。只留「动作 + 表情」。
    段 = [动作]
    if 表情:
        段.append(表情)
    return " ".join(段)


def 造主体(镜: dict) -> str:
    """这一镜里有谁 —— 直接报角色名，让 MiniMax 知道该看见什么、不该加什么。"""
    import re as _re
    from 出3D定妆 import 角色表
    名表 = {"deepseek": "the chibi blue-haired whale girl (DeepSeek)",
            "gpt": "the tall white dragon girl (GPT)",
            "claude": "the orange-haired girl (Claude)",
            "doubao": "the chubby dark-haired girl (Doubao)",
            "kimi": "the silver-haired cat-eared girl (Kimi)",
            "glm": "the black-haired fox-eared girl (GLM)",
            "qwen": "the light-purple braided girl (Qwen)"}
    # 优先按剧本里写明的「角色」字段；没写就从台词/动作里猜名字
    原 = " ".join(str(镜.get(k, "")) for k in ("角色", "人物", "台词", "动作", "画面"))
    有 = [名表[k] for k, n in (("gpt", "GPT"), ("deepseek", "DeepSeek"),
                               ("claude", "Claude"), ("doubao", "豆包"),
                               ("kimi", "Kimi"), ("glm", "GLM"), ("qwen", "千问"))
           if n in 原]
    # 剧本里常写「角色 1：GPT 龙娘」这种编号写法，上面已经覆盖
    return "; ".join(dict.fromkeys(有))


def 出动态(镜: dict, 种子: int) -> str | None:
    from MiniMax动态 import 出动态 as 跑

    首帧 = os.path.join(出根, f"{镜['号']:02d}_首帧.png")
    动态 = os.path.join(出根, f"{镜['号']:02d}_动态.mp4")
    if not os.path.isfile(首帧):
        print(f"  ❌ 缺首帧，先跑 --出首帧")
        return None
    台词 = 提台词(镜.get("台词", ""))
    print(f"  台词：「{台词 or '（无）'}」")
    return 跑(首帧, 造动态提示词(镜), 台词, 动态, 种子=种子, 主体=造主体(镜))


def main() -> int:
    ap = argparse.ArgumentParser(description="《不烧心》30 镜总调度")
    ap.add_argument("--出首帧", action="store_true")
    ap.add_argument("--出动态", action="store_true")
    ap.add_argument("--只", nargs="*", type=int, default=[])
    ap.add_argument("--种子", type=int, default=5001)
    ap.add_argument("--列", action="store_true")
    a = ap.parse_args()

    镜们 = 读剧本(剧本)
    print(f"从 {剧本} 解析出 {len(镜们)} 个镜头")
    if not 镜们:
        print("✗ 一个都没解析出来，检查剧本格式")
        return 1

    if a.列:
        for j in 镜们:
            ks = 挑角色(j)
            print(f"  镜 {j['号']:02d}  {j.get('标题','')[:22]:<24} "
                  f"[{'/'.join(ks) or '空镜'}] 台词:{(j.get('台词') or '无')[:26]}")
        return 0

    os.makedirs(出根, exist_ok=True)
    要 = [j for j in 镜们 if (not a.只) or (j["号"] in a.只)]

    # 提示词留档，方便事后复查 / 改词重跑
    存 = {j["号"]: 造提示词(j) for j in 镜们}
    with open(os.path.join(出根, "提示词.json"), "w", encoding="utf-8") as f:
        json.dump({str(k): {"正向": v[0], "负向": v[1]} for k, v in 存.items()},
                  f, ensure_ascii=False, indent=2)
    print(f"✓ 提示词留档 → {os.path.join(出根, '提示词.json')}")

    if a.出首帧:
        t0 = time.time()
        成 = 0
        for i, j in enumerate(要):
            print(f"\n[{i+1}/{len(要)}] 镜 {j['号']:02d}  {j.get('标题','')}")
            if 出首帧(j, a.种子 + j["号"] * 7):
                成 += 1
        用时 = time.time() - t0
        print(f"\n✅ 首帧 {成}/{len(要)} 张，用时 {用时:.0f} 秒（{用时/max(成,1):.0f} 秒/张）")
        return 0 if 成 == len(要) else 1

    if a.出动态:
        from MiniMax动态 import 活着

        if not 活着():
            print("❌ ComfyUI 没响应（先跑 启动ComfyUI.py）")
            return 1
        t0 = time.time()
        成 = 0
        for i, j in enumerate(要):
            print(f"\n[{i+1}/{len(要)}] 镜 {j['号']:02d}  {j.get('标题','')}")
            if 出动态(j, a.种子 + j["号"] * 7):
                成 += 1
            # 每镜之后查一次健康：后台任务被掐的教训
            if not 活着():
                print("❌ ComfyUI 掉线了，停下来")
                break
        用时 = time.time() - t0
        print(f"\n✅ 动态 {成}/{len(要)} 条，用时 {用时:.0f} 秒（{用时/max(成,1):.0f} 秒/条）")
        return 0 if 成 == len(要) else 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
