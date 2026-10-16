# -*- coding: utf-8 -*-
"""
写脚本 —— 让本地模型把「选题」写成「分镜脚本」

  选题 + 主题  →  [本地 qwen3.8-27b]  →  脚本.json + 投稿信息.json

为什么要本地模型：这一步是纯文本创作，不占显卡出图时段，而且省钱。
出图前记得先跑 显存让路.ps1 把它卸掉。

用法：
  python 写脚本.py --主题 "山海经神兽落在现代城市" --题材 AI绘画
  python 写脚本.py --主题 "..." --镜头 12 --时长 60 --模型 qwen/qwen3.5-9b
  python 写脚本.py --主题 "..." --只打印
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

LM = os.environ.get("LM_API", "http://127.0.0.1:1234/v1")
# 实测：27B（IQ3_S）在这台机器上单次调用要 400 秒且会把输出预算烧在 thinking 上；
# 9B 快得多，写分镜这种结构化创作够用。想换回来用 --模型 qwen3.8-27b。
默认模型 = "qwen/qwen3.5-9b"

# 从 选题决策.py 实测出来的标题句式杠杆，直接喂给模型当硬约束
标题规则 = """
【标题硬规则（来自 2453 条热榜实测，必须遵守）】
✅ 必须带上官方活动字样（实测 lift 6.13×，单项最大）
✅ 用书名号《》（lift 2.45×）
✅ 用悬念词（lift 2.35×），例如「结果」「没想到」「最后」
✅ 用口语玩梗（lift 2.11×）
❌ 禁止阿拉伯数字 0-9（lift 0.14×，强烈负向）
❌ 禁止「教程」「方法」「怎么」这类方法论词（lift 0.06×，最负向）
❌ 禁止感叹号！（lift 0.52×）
"""

系统提示 = """/no_think
你是一个 B 站 AI 绘画/动画区的内容策划，同时懂 AI 生图的提示词工程。
你写的分镜会被直接喂给 Z-Image-Turbo 文生图模型，所以画面提示词必须是**英文**，
而且要具体到能被画出来：主体、构图、光线、镜头、氛围、材质。

Z-Image 对英文响应最好，中文提示词效果差，所以：
  · 「提示词」字段：英文，逗号分隔的短语，不要整句，不要出现任何文字/logo/水印
  · 「运镜」字段：中文，只能是这四个之一：推近 / 拉远 / 左到右 / 右下左上

不要思考过程，不要解释，直接输出 JSON。"""

用户提示模板 = """请为下面这条 B站 视频写分镜脚本。

题材：{题材}
主题：{主题}
目标时长：{时长} 秒
镜头数：{镜头} 个（每个镜头停留约 {每镜} 秒）
画面风格：{风格}
可挂的官方活动：{活动}

{标题规则}

【分镜节奏要求】
不要 N 个镜头都拍同一个东西。要有节奏：
  第 1 个镜头交代环境/大全景 → 中段推进细节 → 至少一个特写 → 结尾留一个反转或留白
镜头之间要有视觉上的递进，而不是并列。

严格输出这个 JSON 结构（不要加任何其它内容）：
{{
  "标题": "带活动字样、带《》、带悬念词、不含阿拉伯数字和感叹号的中文标题",
  "备选标题": "另一个风格不同的标题",
  "简介": "80-150 字的中文简介，口语一点，结尾自然带一句求三连",
  "tag": ["题材tag", "活动tag", "AI", "AIGC", "原创"],
  "风格前缀": "英文，所有镜头共用的画风/画质前缀，逗号分隔",
  "镜头": [
    {{"提示词": "英文画面描述", "运镜": "推近"}},
    ...
  ]
}}"""


def 取模型表():
    try:
        with urllib.request.urlopen(LM + "/models", timeout=6) as r:
            return [m["id"] for m in json.loads(r.read().decode("utf-8")).get("data", [])]
    except Exception as e:
        print(f"❌ 连不上本地模型服务 ({LM})：{e}")
        print("   请确认 LM Studio 的本地服务器已开启（默认 127.0.0.1:1234）")
        sys.exit(1)


def 对话(模型, 系统, 用户, 温度=0.85, 最大=8192):
    body = {
        "model": 模型,
        "messages": [{"role": "system", "content": 系统}, {"role": "user", "content": 用户}],
        "temperature": 温度,
        "max_tokens": 最大,
        "stream": False,
        # Qwen3 系列默认开 thinking，会把整个输出预算烧在推理上并截断。
        # 两个开关都带上：新的走 chat_template_kwargs，老的认 /no_think 字面量。
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        LM + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    起 = time.time()
    with urllib.request.urlopen(req, timeout=1200) as r:
        数据 = json.loads(r.read().decode("utf-8"))
    耗 = time.time() - 起
    文 = 数据["choices"][0]["message"]["content"]
    用 = 数据.get("usage", {})
    return 文, 耗, 用


def 去思考(文):
    """万一把推理过程也吐出来了，剥掉"""
    文 = re.sub(r" thinking.*?<｜end▁of▁thinking｜>", "", 文, flags=re.S | re.I)
    if "<｜end▁of▁thinking｜>" in 文:
        文 = 文.split("<｜end▁of▁thinking｜>", 1)[1]
    return 文.strip()


def 数据截断(用):
    """输出 token 数顶到上限 = 内容被截断，这种 JSON 一定解析失败"""
    n = 用.get("completion_tokens") or 0
    return f"⚠截断({n})" if n >= 8000 else f"ok({n})"


def 抽JSON(文):
    """模型可能裹 markdown 代码块，或者前后带废话，这里把它抠出来"""
    s = 文.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except Exception:
        pass
    # 退一步：找第一个 { 到最后一个 }
    a, b = s.find("{"), s.rfind("}")
    if a >= 0 and b > a:
        return json.loads(s[a:b + 1])
    raise ValueError("模型没吐出合法 JSON")


def 清理(镜):
    """Z-Image 不懂中文运镜词，统一映射到合成器认的四种"""
    合 = {"推近": "推近", "拉远": "拉远", "左到右": "左到右", "右到左": "右到左",
          "右下左上": "右下左上", "左上右下": "左上右下",
          "zoom in": "推近", "zoom out": "拉远", "pan": "左到右"}
    运 = str(镜.get("运镜", "推近")).strip()
    return {"提示词": str(镜.get("提示词", "")).strip(),
            "运镜": 合.get(运, 合.get(运.lower(), "推近"))}


def 主():
    ap = argparse.ArgumentParser()
    ap.add_argument("--主题", required=True, help="这条视频讲什么")
    ap.add_argument("--题材", default="AI绘画")
    ap.add_argument("--时长", type=float, default=60, help="目标时长（秒）")
    ap.add_argument("--镜头", type=int, default=None, help="镜头数（默认按时长/5 估算）")
    ap.add_argument("--风格", default="电影感写实摄影，体积光，浅景深，胶片颗粒")
    ap.add_argument("--活动", default="AI创作大赛")
    ap.add_argument("--画布", default="1920x1080")
    ap.add_argument("--模型", default=默认模型)
    ap.add_argument("--温度", type=float, default=0.85)
    ap.add_argument("--输出目录", default=None)
    ap.add_argument("--只打印", action="store_true", help="不写文件，只打印")
    ap.add_argument("--重试", type=int, default=2)
    args = ap.parse_args()

    镜头数 = args.镜头 or max(3, round(args.时长 / 5))
    每镜 = round(args.时长 / 镜头数, 1)

    可用 = 取模型表()
    print(f"本地模型服务 {LM}")
    print(f"可用模型: {', '.join(可用)}")
    模型 = args.模型
    if 模型 not in 可用:
        候选 = [m for m in 可用 if "qwen3.8" in m] or [m for m in 可用 if "qwen" in m] or 可用
        模型 = 候选[0]
        print(f"⚠ {args.模型} 不在列表，改用 {模型}")
    print(f"使用 {模型}\n")

    if args.输出目录 is None:
        安全名 = re.sub(r'[\\/:*?"<>|]', "_", args.主题)[:40]
        args.输出目录 = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "成片", 安全名)

    提示 = 用户提示模板.format(
        题材=args.题材, 主题=args.主题, 时长=int(args.时长), 镜头=镜头数,
        每镜=每镜, 风格=args.风格, 活动=args.活动, 标题规则=标题规则)

    print(f"《{args.主题}》  {args.题材}  {int(args.时长)}秒 / {镜头数} 镜头（每镜 {每镜}s）")
    print(f"正在让 {模型} 写分镜 ...")

    结果 = None
    上一次 = None
    for i in range(args.重试 + 1):
        文, 耗, 用 = 对话(模型, 系统提示, 提示, args.温度)
        文 = 去思考(文)
        print(f"  第 {i+1} 次：{耗:.1f}s  "
              f"输入 {用.get('prompt_tokens','?')} / 输出 {用.get('completion_tokens','?')} tokens"
              f"  收尾={数据截断(用)}")
        try:
            结果 = 抽JSON(文)
            break
        except Exception as e:
            上一次 = 文
            print(f"  ⚠ JSON 解析失败：{e}")
            if i < args.重试:
                提示 = 提示 + f"\n\n你上次的输出不是合法 JSON，报错：{e}\n请重新输出，只要 JSON。"

    if 结果 is None:
        print("\n❌ 模型始终没给出合法 JSON，原始输出：")
        print((上一次 or "")[:2000])
        sys.exit(1)

    镜头表 = [清理(x) for x in 结果.get("镜头", []) if x.get("提示词")]
    if not 镜头表:
        print("❌ 模型没给出任何镜头")
        sys.exit(1)

    脚本 = {
        "标题": 结果.get("标题", args.主题),
        "画布": args.画布,
        "每张秒": 每镜,
        "转场秒": 0.8,
        "BGM": None,
        "风格前缀": 结果.get("风格前缀", ""),
        "输出目录": args.输出目录.replace("\\", "/"),
        "镜头": 镜头表,
    }
    投稿 = {
        "标题": 结果.get("标题", args.主题),
        "备选标题": 结果.get("备选标题", ""),
        "简介": 结果.get("简介", ""),
        "tag": 结果.get("tag", []),
        "题材": args.题材,
        "主题": args.主题,
    }

    print(f"\n标题：{投稿['标题']}")
    print(f"备选：{投稿['备选标题']}")
    print(f"tag ：{', '.join(投稿['tag'])}")
    print(f"\n分镜（{len(镜头表)} 个）：")
    for i, s in enumerate(镜头表, 1):
        print(f"  {i:2d}. [{s['运镜']:4s}] {s['提示词'][:88]}")
    print(f"\n风格前缀：{脚本['风格前缀']}")

    if args.只打印:
        print("\n（--只打印，未写文件）")
        return

    os.makedirs(args.输出目录, exist_ok=True)
    脚本路径 = os.path.join(args.输出目录, "脚本.json")
    投稿路径 = os.path.join(args.输出目录, "投稿信息.json")
    with open(脚本路径, "w", encoding="utf-8") as f:
        json.dump(脚本, f, ensure_ascii=False, indent=2)
    with open(投稿路径, "w", encoding="utf-8") as f:
        json.dump(投稿, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {脚本路径}")
    print(f"✅ {投稿路径}")
    print(f"\n下一步：")
    print(f'  python 出片.py "{脚本路径}"')


if __name__ == "__main__":
    主()
