# -*- coding: utf-8 -*-
"""
投稿 —— 读「投稿信息.json」，调 上传视频.ps1 把成片投到 B站

  python 投稿.py 投稿信息.json              # 打印将要提交的内容，等你确认
  python 投稿.py 投稿信息.json --直接投      # 跳过确认
  python 投稿.py 投稿信息.json --试运行      # 只打印命令，不真投
  python 投稿.py --示例                     # 打印一个投稿信息.json 的样子

设计上故意不代你按「确认」：真正的投稿动作必须由人过一眼再放行，
避免流水线自己把半成品发出去。
"""
import argparse
import json
import os
import subprocess
import sys

B站目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
上传脚本 = os.path.join(B站目录, "上传视频.ps1")
审批文件名 = "_审批.json"

示例 = {
    "视频": "D:/DSHworkspace/B站/成片/它记得/它记得_14B.mp4",
    "标题": "AI MV 大赛｜《它记得》：废弃城市里，它还在原地等一个不会回来的人",
    "简介": "它没有等到那个人。\n但它把整座城市，连同那一天的黄昏，一起记了三十年。",
    "标签": ["AI动画", "AI短片", "AIGC", "原创动画"],
    "分区": 27,
    "封面": "D:/DSHworkspace/B站/成片/它记得/封面/封面_它记得_带字.png",
    "AI生成声明": True,
    "定时发布时间": ""
}


def 检查(info):
    """投稿前把能拦的错都拦掉，别等 biliup 报错。"""
    错 = []
    if not os.path.isfile(info.get("视频", "")):
        错.append(f"视频不存在：{info.get('视频')}")
    if not info.get("标题"):
        错.append("标题为空")
    elif len(info["标题"]) > 80:
        错.append(f"标题 {len(info['标题'])} 字，超过 B站 80 字上限")
    简介 = info.get("简介", "")
    if len(简介) > 2000:
        错.append(f"简介 {len(简介)} 字，超过 2000 字上限")
    标签 = info.get("标签", [])
    if len(标签) > 10:
        错.append(f"标签 {len(标签)} 个，超过 10 个上限")
    封面 = info.get("封面", "")
    if 封面 and not os.path.isfile(封面):
        错.append(f"封面不存在：{封面}")
    if 封面 and not 封面.lower().endswith((".jpg", ".jpeg", ".png")):
        错.append(f"封面格式不是 jpg/png：{封面}")
    return 错


def 打印(info):
    print("=" * 68)
    print(f"  视频  {info.get('视频')}")
    try:
        大小 = os.path.getsize(info["视频"]) / 1024 / 1024
        print(f"        {大小:.1f} MB")
    except OSError:
        pass
    print(f"  标题  {info.get('标题')}   （{len(info.get('标题',''))} 字）")
    print(f"  分区  {info.get('分区')}")
    print(f"  标签  {', '.join(info.get('标签') or [])}")
    print(f"  封面  {info.get('封面') or '（无，B站自动截帧）'}")
    print(f"  AI声明 {'是' if info.get('AI生成声明') else '否'}")
    定时 = info.get("定时发布时间")
    if 定时:
        print(f"  定时  {定时}")
    print("  简介  " + "-" * 56)
    for 行 in (info.get("简介") or "").splitlines():
        print(f"        {行}")
    print("=" * 68)


def 查审批(info):
    """成片必须先经过审片签字，否则一律不放行。

    这道闸门是**落盘**的，不是运行时问一句：命令行敲错一个键不会把片子发出去，
    半夜自动跑也不会把半成品发出去。签字只能由人看过片子后显式做：
        python 审片.py <成片目录> --通过 -备注 "可以投"
    """
    视频 = info.get("视频")
    if not 视频:
        return ["投稿信息里没有「视频」字段"]
    目录 = os.path.dirname(os.path.abspath(视频))
    p = os.path.join(目录, 审批文件名)
    if not os.path.isfile(p):
        return [f"这支片子还没审过（缺 {p}）",
                f"先看片：python 审片.py \"{目录}\"",
                f"看完认可：python 审片.py \"{目录}\" --通过 -备注 \"可以投\""]
    try:
        with open(p, encoding="utf-8") as f:
            s = json.load(f)
    except Exception as e:
        return [f"审批文件读不了：{e}"]
    state = s.get("state")
    if state != "通过":
        return [f"这支片子的审批状态是「{state}」，不是「通过」",
                f"备注：{s.get('备注') or '(无)'}"]
    return []


def main():
    ap = argparse.ArgumentParser(description="读投稿信息.json 并投到 B站")
    ap.add_argument("信息", nargs="?", help="投稿信息.json 的路径")
    ap.add_argument("--直接投", action="store_true", help="不询问，直接投")
    ap.add_argument("--试运行", action="store_true", help="只打印将要执行的命令")
    ap.add_argument("--示例", action="store_true", help="打印一个示例")
    a = ap.parse_args()

    if a.示例:
        print(json.dumps(示例, ensure_ascii=False, indent=2))
        return
    if not a.信息:
        ap.error("需要给一个投稿信息.json 的路径（或用 --示例 看格式）")
    if not os.path.isfile(a.信息):
        sys.exit(f"❌ 找不到 {a.信息}")
    if not os.path.isfile(上传脚本):
        sys.exit(f"❌ 找不到上传脚本 {上传脚本}")

    with open(a.信息, encoding="utf-8") as f:
        info = json.load(f)

    错 = 检查(info)
    if 错:
        print("❌ 投稿前检查没通过：")
        for e in 错:
            print("   ·", e)
        sys.exit(1)

    # 审片闸门：没签字，后面的确认和上传都不走
    未审 = 查审批(info)
    if 未审:
        print("🛑 这道片子还没拿到你的签字，不能投。")
        for e in 未审:
            print("   ·", e)
        print("\n（流程是：出片 → 审片 → 你点头 → 才投稿。这一步故意不给绕过的开关。）")
        sys.exit(2)

    打印(info)

    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", 上传脚本,
           "-视频路径", info["视频"],
           "-标题", info["标题"],
           "-分区", str(info.get("分区", 27))]
    if info.get("简介"):
        cmd += ["-简介", info["简介"]]
    if info.get("标签"):
        cmd += ["-标签", ",".join(info["标签"])]
    if info.get("封面"):
        cmd += ["-封面", info["封面"]]
    if info.get("AI生成声明"):
        cmd += ["-AI生成声明"]
    if info.get("定时发布时间"):
        cmd += ["-定时发布时间", str(info["定时发布时间"])]
    if a.直接投:
        cmd += ["-跳过确认"]

    if a.试运行:
        print("\n将要执行：")
        print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return

    if not a.直接投:
        print("\n即将投稿。确认无误请输入 yes（其它任意键放弃）：", end=" ")
        if input().strip().lower() != "yes":
            print("已放弃，没有提交任何东西。")
            return

    print("\n调用上传脚本...\n")
    子 = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace")
    sys.exit(子.returncode)


if __name__ == "__main__":
    main()
