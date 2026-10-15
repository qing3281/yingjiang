# -*- coding: utf-8 -*-
"""看片 —— 给控制台供「这一部戏到底讲了什么」的数据。

★ 为什么要有这个（2026-10-15 08:55 用户的原话）：

    「我看了你做的控台。你这个控台和我想象的要求的差别，你觉得一致吗？
      这个控台我能自己看到里面的剧本，能看到里面的台词，看到里面的人物形象。
      这些东西吧，我现在只能看到你所生成的进度，这叫这对吗？」

    他说得对。控台原来只报「段 50 个 / 成片 85 个」这种我自己看的进度数，
    **他要的是能看见片子本身**：人物长什么样、谁在第几秒说了什么、每一格画的是什么。
    进度是给我看的，剧本台词人物是给他看的。**同一个页面里，他的那一半原先整个是空的。**

    这一份只干一件事：把 `影匠\\作品\\<戏>\\` 里的
    `_定妆照\\*.png`（人物形象）、`03-台词.md` / `配音\\_台词.srt`（台词）、
    `02-九宫格.md`（逐格）、`段\\*.mp4`（每一格的片子）读成一份 JSON。

★ 解析四部戏的写法不一样，三条坑都是踩过的（`_出剧本.py` 里也记着）：
    ① 字段有的是 `- **目的**：…`，有的是 `- 目的：…` → 正则要容 `**` 可有可无
    ② `03-台词.md` 里不止一张表（《觉醒》多一张「这一版改了什么」，
       《磨刀》按场分成五张）→ **全部拼起来再去重**，不能只取最大的那张
    ③ SRT 的毫秒分隔符是**逗号**（`00:00:00,600`）不是点 → 不修就一条都匹配不上
"""

import io
import os
import re

作品根 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "作品")
格秒 = 4.56
转场吃 = 0.5
步 = 格秒 - 转场吃          # 4.06 秒


def 戏们():
    if not os.path.isdir(作品根):
        return []
    出 = []
    for 名 in sorted(os.listdir(作品根)):
        目 = os.path.join(作品根, 名)
        if os.path.isdir(目) and os.path.isfile(os.path.join(目, "02-九宫格.md")):
            出.append(名)
    return 出


def _读(戏, *名):
    p = os.path.join(作品根, 戏, *名)
    if os.path.isfile(p):
        try:
            return io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            return ""
    return ""


def _净(s):
    return re.sub(r"\s+", " ", (s or "").replace("**", "").replace("`", "")).strip()


def 人物(戏):
    """人物的形象图。**两条路都要走**：
      · `_定妆照\\*.png` —— 文件名就是角色名（我手写的那几部戏用这条）
      · 剧组流水线跑的戏没有定妆照，形象在 `03_锚N格M.png` 里 ——
        那里拍的就是这两个人，取每个名字**第一次出现**的那张当形象图。
    ★ 只认一条路的后果跟 段片() 一样：新戏的「人物形象」签是空的，
      而他分不出「这部戏没有人物」和「我读错了目录」。
    """
    目 = os.path.join(作品根, 戏, "_定妆照")
    出 = []
    if os.path.isdir(目):
        for f in sorted(os.listdir(目)):
            # ★ 排除 `阿棠_旧.png` 这种留档图 —— 它是过程证据，不是给他看的人物形象
            if f.lower().endswith(".png") and not f.startswith("_") and "_旧" not in f:
                出.append({"名": os.path.splitext(f)[0],
                           "图": f"影匠/作品/{戏}/_定妆照/{f}"})
    if 出:
        return 出

    # 剧组.py 布局：扫九宫格的「人物」字段，每人配第一张有四宫格图的锚点图
    戏目 = os.path.join(作品根, 戏)
    有图 = sorted(f for f in (os.listdir(戏目) if os.path.isdir(戏目) else [])
                  if re.match(r"^03_锚\d+格\d+\.png$", f))
    if not 有图:
        return []
    点名 = []
    九 = _读(戏, "02-九宫格.md")
    # ★★ 人物有两种写法，都要吃：
    #    · `- 人物：老周、小满`（字段式）
    #    · 角色卡：`- 老周：六十七岁的修鞋匠，花白平头…`（**只在「角色卡」这一节里**）
    #    只认字段式的后果：《修鞋》的角色卡写得好好的，人物栏却是空的 ——
    #    而空着跟他「这部戏没人物」看到的是一样的。
    #    ★ 只看「在第一个 `## 格` 之前」还不够：那一段里还有「视觉规范」，
    #      于是 `- 风格：…` `- 色彩光影：…` `- 材质：…` 会被当成三个人名读出来。
    #      **必须认小节标题。**
    在角色卡里 = False
    for 行 in (九 or "").splitlines():
        s = 行.strip()
        m0 = re.match(r"^#{2,3}\s*(.+?)\s*$", s)
        if m0:
            在角色卡里 = ("角色" in m0.group(1)) or ("人物" in m0.group(1))
            continue
        m = re.match(r"^-\s*\*{0,2}(?:人物|角色)\*{0,2}\s*[：:]\s*(.+)$", s)
        if m:
            正文 = m.group(1)
        elif 在角色卡里:
            m2 = re.match(r"^-\s*\*{0,2}([^\s：:*]{1,8})\*{0,2}\s*[：:]\s*(.+)$", s)
            if not m2:
                continue
            正文 = m2.group(1)
        else:
            continue
        for 名 in re.split(r"[、,，/｜|]+", 正文):
            名 = 名.strip().strip("*")
            if 名 and 1 <= len(名) <= 8 and 名 not in 点名:
                点名.append(名)
    for i, 名 in enumerate(点名):
        if i >= len(有图):
            break
        出.append({"名": 名, "图": f"影匠/作品/{戏}/{有图[min(i, len(有图) - 1)]}",
                   "注": "（这一部没有定妆照，这是四宫格里他第一次出现的那张）"})

    # ★★ 最后一条路：`02-九宫格.md` 里没写「人物」字段、也没有四宫格图的戏，
    #    就用**这一部戏真的用到的那几个角色** —— 判据是「名字在九宫格的提示词里出现过」，
    #    不是「角色库里登记过」。★ 一开始我写的是后者，结果每一部新戏都会显示
    #    角色库里**全部 9 个人**（凌霜、沈砚、阿七…），那些是别的戏的演员。
    if not 出:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import 角色库 as _角
            名们 = _角.全部()
            if 名们 and isinstance(名们[0], dict):
                名们 = [x.get("名") for x in 名们]
        except Exception:
            名们 = []
        正文 = (九 or "") + "\n" + "\n".join(os.path.basename(f) for f in 有图)
        用到 = [n for n in 名们 if n and n in 正文]
        if not 用到:
            用到 = []
        图 = (有图[0] if 有图 else
              ("01_格1.png" if os.path.exists(os.path.join(戏目, "01_格1.png")) else None))
        for 名 in 用到:
            if 图:
                出.append({"名": 名, "图": f"影匠/作品/{戏}/{图}",
                           "注": "（这一部没有定妆照，先拿戏里的图占位）"})
    return 出


def 格表(戏):
    """`02-九宫格.md` —— 每一格：第几格、几秒、标题、画面上是什么。"""
    九 = _读(戏, "02-九宫格.md")
    if not 九:
        return []
    f = r"^-\s*\*{{0,2}}{0}\*{{0,2}}\s*[：:]\s*(.+?)$"

    def 取(段, 名):
        m = re.search(f.format(名), 段, re.M)
        return _净(m.group(1)) if m else ""

    出 = []
    for m in re.finditer(r"^##\s*格\s*(\d+)\s*[——\-–]+\s*(.+?)$", 九, re.M):
        号 = int(m.group(1))
        段 = 九[m.end():]
        下 = re.search(r"^## ", 段, re.M)
        段 = 段[:下.start()] if 下 else 段
        s = (号 - 1) * 步
        出.append({"号": 号,
                   "秒": round(s, 1),
                   "时刻": f"{int(s) // 60}:{s % 60:04.1f}",
                   "题": _净(m.group(2)),
                   "景别": 取(段, "景别"),
                   "目的": 取(段, "目的"),
                   "重点": 取(段, "重点")})
    出.sort(key=lambda x: x["号"])
    return 出


def 台词(戏, 格数=0):
    """`03-台词.md` 优先；没有就退回 `配音\\_台词.srt`。返回 {格号: [(谁, 词)]}。"""
    台 = _读(戏, "03-台词.md")
    出 = {}
    _见 = set()          # ★ 去重键：(格号, 说话人, 去掉所有引号括号的文本)
    表s = []
    for m in re.finditer(r"^(\|[^\n]*\|)\s*\n\|[\s\-:|]+\|\s*\n((?:\|[^\n]*\|\s*\n?)+)", 台, re.M):
        头, 身 = m.group(1), m.group(2)
        if "说话人" not in 头 and "角色" not in 头:
            continue
        行s = []
        for l in 身.strip().splitlines():
            c = [x.strip() for x in l.strip().strip("|").split("|")]
            if len(c) >= 3:
                行s.append(c)
        表s.append(行s)
    for c in [r for t in 表s for r in t]:
        mm = re.match(r"^(?:格)?\s*(\d+)$", c[0].replace("*", ""))
        if not mm:
            continue
        号 = int(mm.group(1))
        if not (1 <= 号 <= 999):
            continue
        谁, 说 = _净(c[1]), _净(c[2])
        # ★ 同一句话在两张表里各写一遍是常态（《觉醒》多一张「这一版改了什么」），
        #   而两处的引号写法不一样（`「册子上也没有他。」` vs `册子上也没有他。`）——
        #   所以去重键要**把引号括号一起去掉**，不然同一句会显示两遍。
        键 = (号, 谁, re.sub(r"[「」『』“”\"'（）()【】\[\]]", "", 说))
        if 键 in _见:
            continue
        _见.add(键)
        出.setdefault(号, []).append((谁, 说))
    if 出:
        return 出, f"03-台词.md（{len(表s)} 张表）"

    # ★ SRT：毫秒分隔符是**逗号**，写成点就一条都匹配不上
    # ★★ 名字也不能只认 `配音\_台词.srt` —— 剧组流水线跑的戏把字幕写在戏目录根下，
    #    而且名字是我自己起的（《修鞋》叫 `_口号.srt`）。**只认一个写死的路径，
    #    结果是新戏的「台词」签全空，跟他看到的成片对不上。** 所以按优先级找一批。
    候选 = [os.path.join(作品根, 戏, "配音", "_台词.srt")]
    戏目 = os.path.join(作品根, 戏)
    if os.path.isdir(戏目):
        for f in sorted(os.listdir(戏目)):
            if f.lower().endswith(".srt"):
                候选.append(os.path.join(戏目, f))
    srt = ""
    哪 = ""
    for p in 候选:
        if os.path.exists(p):
            srt = io.open(p, encoding="utf-8-sig", errors="replace").read()
            哪 = os.path.basename(p)
            break
    if not srt:
        return {}, ""
    条 = []
    for m in re.finditer(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)\s*\n(.+?)(?=\n\s*\n|\Z)",
                         srt, re.S):
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
        末 = int(m.group(5)) * 3600 + int(m.group(6)) * 60 + int(m.group(7)) + int(m.group(8)) / 1000
        说 = m.group(9).strip().split("\n")[0]
        说 = re.sub(r"^[^：:]{0,6}[：:]\s*", "", 说).strip()
        if 说:
            条.append((t, 末, 说))
    if not 条:
        return {}, ""

    # ★★ **每一格多少秒，不同片子不一样，不能写死。** 老片一格 4.06 秒（4.56 减去 0.5 转场吃），
    #    剧组流水线出的段是 49 帧 @16fps ≈ 3.06 秒拼起来的，一格差不多 6 秒。
    #    写死 4.06 的后果：新戏的台词**全部挤进第 1 格**（t 都算成格 1）——
    #    这个错看起来很体面（「有台词」和「台词都在第几格」长得一样），所以不会有人报错。
    #    做法：**用字幕自己的跨度当尺子**（最后一条的结束时刻 ÷ 格数），再跟写死的两个候选比，
    #    取分得开的那一个。
    跨 = max(x[1] for x in 条)
    候选步 = []
    # ★ 只有一条字幕时它说明不了「一格几秒」（《修鞋》的 `_口号.srt` 就是一条收尾字幕，
    #   跨度 2 秒 ÷ 5 格 = 0.4 秒 —— 拿它当尺子比不猜还糟）。两条以上才用它。
    if 格数 and 跨 > 0 and len(条) >= 2:
        候选步.append(round(跨 / 格数, 3))
    候选步 += [步, 3.06]
    最好, 最好分, 用了 = None, -1, 步
    for 偏 in (0.0, 4.0):
        for s in 候选步:
            if s <= 0.2:
                continue
            试 = {}
            for t, _末, 说 in 条:
                号 = int(round((t - 偏) / s)) + 1
                试.setdefault(max(1, 号), []).append(("", 说))
            分 = len(试)
            if 分 > 最好分:
                最好, 最好分, 用了 = 试, 分, s
    return 最好, f"{哪}（按时刻反推格子，一格 {用了} 秒）"


def 段片(戏):
    """每一格已经出来的片子。**两种目录布局都要认**：
      · 老布局（我手写的戏）：`段\\格N_本机.mp4` / `段\\格N_远端.mp4`
      · 剧组.py 布局（剧组流水线跑的戏）：`04_锚N格M.mp4` —— 锚点号才是格子号
        （`03-四宫格.md` 里「继承自：格N」的 N）。
    ★ 只认一种布局的后果：新戏在「看片」卡里显示成一片空白，
      而他分不出「这部戏没片子」和「我读错了目录」—— 两个都是空白。
    """
    目 = os.path.join(作品根, 戏, "段")
    出 = {}
    if os.path.isdir(目):
        for f in sorted(os.listdir(目)):
            if not f.lower().endswith(".mp4"):
                continue
            m = re.match(r"^格\s*(\d+)", f)
            if not m:
                continue
            号 = int(m.group(1))
            p = os.path.join(目, f)
            出.setdefault(号, []).append(
                {"名": f, "路": f"影匠/作品/{戏}/段/{f}", "大小": os.path.getsize(p)})

    # 剧组.py 布局：04_锚N格M.mp4 → 挂到「继承自」那一格
    戏目 = os.path.join(作品根, 戏)
    继承 = {}
    p4 = os.path.join(戏目, "03-四宫格.md")
    if os.path.exists(p4):
        try:
            文 = io.open(p4, encoding="utf-8").read()
            锚 = None
            for 行 in 文.splitlines():
                m1 = re.match(r"^##\s*锚点\s*(\d+)", 行.strip())
                if m1:
                    锚 = int(m1.group(1))
                    continue
                m2 = re.match(r"^-\s*继承自\s*[：:]\s*格\s*(\d+)", 行.strip())
                if m2 and 锚 is not None:
                    继承[锚] = int(m2.group(1))
        except Exception:
            pass
    if os.path.isdir(戏目):
        for f in sorted(os.listdir(戏目)):
            if not f.lower().endswith(".mp4"):
                continue
            m = re.match(r"^04_锚(\d+)格(\d+)\.mp4$", f)
            if not m:
                continue
            锚 = int(m.group(1))
            号 = 继承.get(锚, 锚)
            p = os.path.join(戏目, f)
            出.setdefault(号, []).append(
                {"名": f, "路": f"影匠/作品/{戏}/{f}", "大小": os.path.getsize(p)})
    return 出


def 成片(戏):
    目 = os.path.join(作品根, 戏, "片")
    出 = []
    if os.path.isdir(目):
        for f in sorted(os.listdir(目)):
            if f.lower().endswith(".mp4"):
                p = os.path.join(目, f)
                出.append({"名": f, "路": f"影匠/作品/{戏}/片/{f}",
                           "大小": os.path.getsize(p),
                           "改": os.path.getmtime(p)})
    出.sort(key=lambda x: -x["改"])
    return 出


def 剧本页(戏):
    """`_剧本.html` 在不在 —— 那一页才是他读剧本的地方。"""
    p = os.path.join(作品根, 戏, "_剧本.html")
    return f"影匠/作品/{戏}/_剧本.html" if os.path.isfile(p) else ""


def 剧本(戏):
    """`剧本.md` 的原文 —— 挂在看片卡的「剧本」签上直接读。

    ★ 用户 2026-10-15 09:44 原话：「这个控台我能自己看到里面的剧本，能看到里面的台词，
      看到里面的人物形象」——「里面」= 页面里，不是再点一个链接跳出去。
      所以这里回**正文**，不是回路径。上限 60,000 字（再多一个页面也读不完）。
    """
    p = os.path.join(作品根, 戏, "剧本.md")
    if not os.path.isfile(p):
        return {"有": False, "文": "", "字": 0,
                "说": "这一部戏还没有 剧本.md —— 用上面「新建一部戏」建一个，"
                      "或者把写好的 剧本.md 放进 作品\\<戏>\\。"}
    try:
        文 = io.open(p, encoding="utf-8").read()
    except Exception as e:
        return {"有": False, "文": "", "字": 0, "说": f"读不动：{e}"}
    原 = len(文)
    if 原 > 60000:
        文 = 文[:60000] + f"\n\n……（还有 {原 - 60000:,} 字没显示，用上面的按钮开整份）"
    return {"有": True, "文": 文, "字": 原, "说": ""}


def 一部(戏):
    格s = 格表(戏)
    词, 源 = 台词(戏, len(格s))
    seg = 段片(戏)
    有词 = 0
    for g in 格s:
        g["词"] = 词.get(g["号"], [])
        if g["词"]:
            有词 += 1
        g["片"] = seg.get(g["号"], [])
    人 = 人物(戏)
    return {
        "戏": 戏,
        "人物": 人,
        "格": 格s,
        "格数": len(格s),
        "有词的格": 有词,
        "台词来源": 源,
        "成片": 成片(戏)[:6],
        "剧本页": 剧本页(戏),
        "剧本": 剧本(戏),
        # ★ 20 秒的片子写成「0.3 分钟」，他得多算一步才知道有多长。
        #   少于 90 秒就直接报秒。
        "秒": round(len(格s) * 格秒 - max(0, len(格s) - 1) * 转场吃, 1),
        "时长话": (f"{round(len(格s) * 格秒 - max(0, len(格s) - 1) * 转场吃)} 秒"
                 if (len(格s) * 格秒 - max(0, len(格s) - 1) * 转场吃) < 90
                 else f"{(len(格s) * 格秒 - max(0, len(格s) - 1) * 转场吃) / 60:.1f} 分钟"),
    }


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for 戏 in (sys.argv[1:] or 戏们()):
        d = 一部(戏)
        print(f"\n《{戏}》　{d['格数']} 格 · {d['有词的格']} 格有词 · "
              f"{d['秒']} 秒 · 人物 {len(d['人物'])} 个 · 台词来自 {d['台词来源'] or '（没有）'}")
        for p in d["人物"]:
            print(f"    {p['名']}")
        for g in d["格"][:3]:
            w = "／".join(f"{a}{b}" for a, b in g["词"]) or "（没有台词）"
            print(f"    格{g['号']:<3} {g['时刻']:>6}　{g['题']}　[{g['景别']}]　{w}")
        print(f"    成片 {len(d['成片'])} 个　剧本页 {'有' if d['剧本页'] else '没有'}")
