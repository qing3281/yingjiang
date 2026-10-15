"""把「影匠工作台」这套软件导出成一个**能上传 GitHub 的小仓库**。

★ 为什么不能直接 `git init D:\\DSHworkspace`：
   那个目录 **393.83 GiB / 106,131 个文件**（`网盘` 一个就 362 GB）——
   把片子、模型、缓存全塞进 git 是灾难。用户说的是
   「把**软件界面**上传到我的代码仓」，要传的是**代码**，不是素材。

所以这里只挑源码 + 少数几张截图，复制到 `D:\\DSHworkspace\\_GitHub\\影匠工作台\\`，
在那儿 `git init`。**只读源目录、只写目标目录**，不动任何原件。
"""
import os
import shutil
import sys

工作区 = r"D:\DSHworkspace"
装 = os.path.join(工作区, "_GitHub", "影匠工作台")

# ── 要带走的：源码。键是目标里的相对路径，值是源绝对路径 ──
件 = {
    # 影匠 —— 控制台 / 生成 / 后期
    "影匠/_控台.py": os.path.join(工作区, "影匠", "_控台.py"),
    "影匠/_监工.py": os.path.join(工作区, "影匠", "_监工.py"),
    "影匠/引擎.py": os.path.join(工作区, "影匠", "引擎.py"),
    "影匠/_出H3.py": os.path.join(工作区, "影匠", "_出H3.py"),
    "影匠/_出片.py": os.path.join(工作区, "影匠", "_出片.py"),
    # 后期链条：拼段 → 配音 → 烧字幕。这三步是「改一句话就能重出一条片子」的那条路
    "影匠/_拼长片.py": os.path.join(工作区, "影匠", "_拼长片.py"),
    "影匠/_配长片.py": os.path.join(工作区, "影匠", "_配长片.py"),
    "影匠/_烧字幕.py": os.path.join(工作区, "影匠", "_烧字幕.py"),
    # 诊断与出图工具
    "影匠/_出定妆照.py": os.path.join(工作区, "影匠", "_出定妆照.py"),
    "_量动作语气.py": os.path.join(工作区, "_量动作语气.py"),
    "影匠/_超分.py": os.path.join(工作区, "_超分.py"),
    "影匠/_成片_觉醒.py": os.path.join(工作区, "影匠", "_成片_觉醒.py"),
    "影匠/_配台词_觉醒.py": os.path.join(工作区, "影匠", "_配台词_觉醒.py"),
    "影匠/_量运动.py": os.path.join(工作区, "影匠", "_量运动.py"),
    # 工作区的「台」（用户桌面上的三个图标背后就是它们）
    "台/_依据台.py": os.path.join(工作区, "_依据台.py"),
    "台/_依据窗.py": os.path.join(工作区, "_依据窗.py"),
    "台/_依据图.py": os.path.join(工作区, "_依据图.py"),
    "台/_记忆台.py": os.path.join(工作区, "_记忆台.py"),
    "台/_开台.py": os.path.join(工作区, "_开台.py"),
    "台/_开工.py": os.path.join(工作区, "_开工.py"),
    # 自测
    "自测/_插件自测.mjs": os.path.join(工作区, "_插件自测.mjs"),
    "自测/_直调自测.py": os.path.join(工作区, "_直调自测.py"),
    "自测/_看着活.py": os.path.join(工作区, "_看着活.py"),
    # 打包（P1⑤：把控制台打成双击就开的 exe）
    "打包/_打包控制台.py": os.path.join(工作区, "_打包控制台.py"),
    "打包/影匠控制台.cmd": os.path.join(工作区, "影匠控制台.cmd"),
    "打包/说明.md": os.path.join(工作区, "_打包", "说明.md"),
    # 仓库与界面草图（P1⑦ / P2-2）
    "_推仓库.py": os.path.join(工作区, "_推仓库.py"),
    "_导出仓库.py": os.path.join(工作区, "_导出仓库.py"),
    "界面草图.html": os.path.join(工作区, "_界面草图.html"),
    # 验收页（用户双击桌面上的「验收」就开这一个）
    "_验收.py": os.path.join(工作区, "_验收.py"),
    # 剧本生成器：把四份给机器看的 md 抽成一条人能读的线
    "_出剧本.py": os.path.join(工作区, "_出剧本.py"),
    # 查假字幕 / 拼对比图 —— 这两条是「判据」本身，值得跟着代码走
    "_查假字幕.py": os.path.join(工作区, "_查假字幕.py"),
    "_拼运动差图.py": os.path.join(工作区, "_拼运动差图.py"),
    "_拼超分对比mp4.py": os.path.join(工作区, "_拼超分对比mp4.py"),
    "_拼定妆照.py": os.path.join(工作区, "_拼定妆照.py"),
    "_核台账.py": os.path.join(工作区, "_核台账.py"),
    "_用户原话.py": os.path.join(工作区, "_用户原话.py"),
    # ★ 用户 2026-10-15 09:44 原话「这个控台我能自己看到里面的剧本，能看到里面的台词，
    #   看到里面的人物形象」—— 这一份就是给他看的东西，必须跟着仓库走
    "_看片.py": os.path.join(工作区, "影匠", "_看片.py"),
    # 换服务那件事（起新版 = 杀干净 + 端口主人启动时刻 > 源码 mtime + 连打 3 次）
    "_重启台.py": os.path.join(工作区, "_重启台.py"),
    "_验控台2.py": os.path.join(工作区, "_验控台2.py"),
    "影匠_console-launch.ps1": os.path.join(工作区, "_console-launch.ps1"),
    # ★ 回答用户 02:06「记住你前面出现过的所有问题，我不想再看见了」的那道闸
    "_找复发.py": os.path.join(工作区, "_找复发.py"),
    # ★ 量「尾帧到底落没落在指定的那张图上」的那把尺子
    "验证_首尾帧落点.py": os.path.join(工作区, "_验尾帧落点.py"),
    # 它数出来的结果（犯过两次以上的病）—— 是数据不是代码，但值得一起带走
    "记忆_模式.md": os.path.join(工作区, "记忆", "模式.md"),
    # 飞彩 × 影匠 × ComfyUI 三合一的对照清单
    "知识_两边一起用.md": os.path.join(工作区, "影匠", "知识", "两边一起用.md"),
    "minimax_h3_flf2v.json": os.path.join(工作区, "影匠", "模板", "minimax_h3_flf2v.json"),
    "minimax_h3_r2v.json": os.path.join(工作区, "影匠", "模板", "minimax_h3_r2v.json"),
    # ★ 读 safetensors 文件头算「这个模型下完了没有」—— 本机就有个缺 0.72 GB 的
    "查模型完整.py": os.path.join(工作区, "_查模型完整.py"),
    # ★ 台账 #13/#14「提示词先给我看」「正式生成前必须把内容给我审核」——
    #   说了四遍都没成为动作，于是给它一个**位置**：这张表 + 这个增删查工具。
    "_候你点头.py": os.path.join(工作区, "_候你点头.py"),
    "_待你点头.md": os.path.join(工作区, "_待你点头.md"),
}

# ── DSH 客户端插件（挂右侧栏那个页签） ──
插件源 = r"D:\DSH\home\profiles\desktop\node_modules\dsh-yingjiang-panel"
插件件 = ["package.json", "cordis.patch.yml",
          os.path.join("lib", "index.js"), os.path.join("lib", "client.js")]

# ── 截图 ──
图 = {
    "截图/控制台_直调.png": os.path.join(工作区, "_归档", "截图", "控制台_直调.png"),
    "截图/控制台_exe.png": os.path.join(工作区, "_归档", "截图", "控制台_exe.png"),
    "截图/控制台_进度条.png": os.path.join(工作区, "_归档", "截图", "控制台_进度条.png"),
    "截图/界面草图.png": os.path.join(工作区, "_归档", "截图", "界面草图.png"),
    "截图/依据窗_内容.png": os.path.join(工作区, "_归档", "截图", "依据窗_内容.png"),
    "截图/对比_觉醒格17.png": os.path.join(工作区, "影匠", "作品", "_超分试验", "对比_觉醒格17.png"),
}

忽略 = shutil.ignore_patterns("__pycache__", "*.pyc", ".git")


def 干():
    写在 = 缺了 = 0
    os.makedirs(装, exist_ok=True)

    for 到, 源 in 件.items():
        路 = os.path.join(装, 到.replace("/", os.sep))
        os.makedirs(os.path.dirname(路), exist_ok=True)
        if os.path.isfile(源):
            shutil.copy2(源, 路)
            print(f"  ✓ {到}　{os.path.getsize(源):,} B")
            写在 += 1
        else:
            print(f"  ✗ 源不在：{源}")
            缺了 += 1

    for 到, 源 in 图.items():
        路 = os.path.join(装, 到.replace("/", os.sep))
        os.makedirs(os.path.dirname(路), exist_ok=True)
        if os.path.isfile(源):
            shutil.copy2(源, 路)
            print(f"  ✓ {到}　{os.path.getsize(源):,} B")
            写在 += 1
        else:
            print(f"  ✗ 图不在：{源}")
            缺了 += 1

    print()
    for 一 in 插件件:
        源 = os.path.join(插件源, 一)
        路 = os.path.join(装, "dsh-插件", "dsh-yingjiang-panel", 一)
        os.makedirs(os.path.dirname(路), exist_ok=True)
        if os.path.isfile(源):
            shutil.copy2(源, 路)
            print(f"  ✓ dsh-插件/dsh-yingjiang-panel/{一}　{os.path.getsize(源):,} B")
            写在 += 1
        else:
            print(f"  ✗ 插件文件不在：{源}")
            缺了 += 1

    总 = 0
    for 根, _, 们 in os.walk(装):
        for f in 们:
            总 += os.path.getsize(os.path.join(根, f))
    print(f"\n  ★ 装到 {装}")
    print(f"    写 {写在} 个　缺 {缺了} 个　合计 {总 / 1024:.0f} KiB")
    return 1 if 缺了 else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(干())
