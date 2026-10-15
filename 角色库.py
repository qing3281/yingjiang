# -*- coding: utf-8 -*-
"""
影匠 · 角色库  —— 角色一致性
================================================================
核心问题：同一个角色出现在 20 个镜头里，怎么保证是同一张脸、同一身衣服？

四层锁定（从弱到强，可叠加）：

  第 1 层 · 文字锚定   每镜都拼同一段「外貌串」，一个字不改
  第 2 层 · 种子锁定   同一个 seed 让底模的随机性收敛到同一个解
  第 3 层 · 定妆照     先用角色卡生成一张「官方定妆照」，存进 assets/
  第 4 层 · 参考图注入 后续镜头把定妆照当参考图喂回去（需要参考图节点）

本机 ComfyUI 装了 IPAdapter / 参考图类节点时走第 4 层，
没装就退到第 3 层（文字 + 种子），实战效果已经够用。

用法：
    from 角色库 import 建, 取, 外貌串, 定妆
    建("凌霜", 性别="女", 年龄="青年", 发="银白长发披肩",
        眼="紫色瞳", 服="黑色修身长袍，银色云纹刺绣", 特征="左眼下有一颗小痣")
    外貌串("凌霜")            -> 拼进提示词的那段
    定妆("凌霜", "cinematic-real")   -> 出一张定妆照存盘
"""

import json
import os
import re
import hashlib

根 = os.path.dirname(os.path.abspath(__file__))
角色文件 = os.path.join(根, "角色库.json")
定妆目录 = os.path.join(根, "assets", "角色")

角色表 = {}
已载 = False


# ============================================================
# 存取
# ============================================================

def _载():
    global 角色表, 已载
    if 已载:
        return
    已载 = True
    if os.path.exists(角色文件):
        try:
            with open(角色文件, "r", encoding="utf-8") as f:
                角色表 = json.load(f)
        except Exception:
            角色表 = {}


def _存():
    _载()
    os.makedirs(os.path.dirname(角色文件), exist_ok=True)
    with open(角色文件, "w", encoding="utf-8") as f:
        json.dump(角色表, f, ensure_ascii=False, indent=2)


# ============================================================
# 建角色
# ============================================================

def 建(名, 性别="", 年龄="", 发="", 眼="", 肤="", 服="", 特征="",
       体态="", 种子=None, 备注="", **额外):
    """
    登记一个角色。所有外貌字段都会拼进「外貌串」，之后每一镜都复用它。

    参数（都能留空，填得越细越稳）：
      名    角色名（唯一键）
      性别  "男" / "女" / "不明"
      年龄  "少年" / "青年" / "中年" / "老年"
      发    发型发色，例如 "银白长发披肩"
      眼    瞳色眼型，例如 "紫色杏眼"
      肤    肤色，例如 "冷白皮"
      服    常服，例如 "黑色修身长袍，银色云纹刺绣"
      特征  记认点，例如 "左眼下有一颗小痣"（**最重要，一致性靠它**）
      体态  高矮胖瘦，例如 "高挑清瘦"
      种子  固定随机种子；不给就按名字自动算一个
      额外  任意补充键值，会一起拼进外貌串
    """
    _载()
    if 种子 is None:
        # 用名字算一个稳定的种子 —— 同一个名字永远是同一个数
        种子 = int(hashlib.md5(名.encode("utf-8")).hexdigest()[:8], 16) % 2147483647

    r = {
        "名": 名, "性别": 性别, "年龄": 年龄, "发": 发, "眼": 眼, "肤": 肤,
        "服": 服, "特征": 特征, "体态": 体态, "种子": 种子, "备注": 备注,
        "定妆照": "",
    }
    r.update(额外)
    角色表[名] = r
    _存()
    return r


def 取(名):
    _载()
    return 角色表.get(名)


def 全部():
    _载()
    return list(角色表.keys())


def 删(名):
    _载()
    角色表.pop(名, None)
    _存()


def 改(名, **字段):
    _载()
    if 名 not in 角色表:
        return None
    角色表[名].update(字段)
    _存()
    return 角色表[名]


# ============================================================
# ★ 核心：外貌串
# ============================================================

# 中文外貌词 -> 英文提示词。提示词里英文更稳。
_性别 = {"男": "male", "女": "female", "不明": "androgynous"}
_年龄 = {
    "少年": "teenage, youthful", "青年": "young adult, in their twenties",
    "中年": "middle-aged", "老年": "elderly, aged",
}

# ============================================================
# 中英词典 —— 外貌词直接写英文也可以，会原样保留
# ============================================================
# 提示词里英文更稳，所以中文描述会被翻译过去。
# 词典命中不了的字会被**丢掉并报警**（不静默糊过去）。
# 想加词：角色库.加词({"词": "english"})  或直接改这里。

_词典 = {
    # ---- 发 ----
    "银白长发披肩": "long silver-white hair falling past shoulders",
    "银白长发": "long silver-white hair",
    "银白短发": "short silver-white hair",
    "银白": "silver-white",
    "长发披肩": "long hair falling past shoulders",
    "长发": "long hair",
    "中长发": "medium-length hair",
    "短发": "short hair",
    "马尾": "ponytail",
    "双马尾": "twin tails",
    "丸子头": "hair bun",
    "黑长直": "long straight black hair",
    "黑发": "black hair",
    "金发": "blonde hair",
    "红发": "red hair",
    "棕发": "brown hair",
    "灰发": "grey hair",
    "白发": "white hair",
    "卷发": "curly hair",
    "直发": "straight hair",
    "齐刘海": "blunt bangs",
    "刘海": "bangs",
    "发髻": "updo",
    # ---- 眼 ----
    "紫色杏眼": "violet almond-shaped eyes",
    "紫色瞳":  "violet eyes", "紫瞳": "violet eyes",
    "金色瞳":  "golden eyes", "金瞳": "golden eyes",
    "赤色瞳":  "crimson eyes", "赤瞳": "crimson eyes", "红瞳": "red eyes",
    "蓝色瞳":  "blue eyes",   "蓝瞳": "blue eyes",
    "绿色瞳":  "green eyes",  "绿瞳": "green eyes",
    "琥珀瞳":  "amber eyes",  "灰瞳": "grey eyes",
    "异色瞳":  "heterochromia",
    "杏眼": "almond-shaped eyes", "丹凤眼": "phoenix eyes",
    "桃花眼": "peach-blossom eyes", "狐狸眼": "fox-like eyes",
    "大眼": "large eyes", "细眼": "narrow eyes",
    # ---- 肤 ----
    "冷白皮": "fair cool-toned skin",
    "白皙": "fair skin", "苍白": "pale skin",
    "小麦色": "tanned skin", "古铜色": "bronze skin",
    "蜜色": "honey-toned skin",
    # ---- 体态 ----
    "高挑清瘦": "tall and slender",
    "高挑": "tall", "清瘦": "slender",
    "娇小": "petite", "丰满": "curvy",
    "健壮": "muscular", "魁梧": "burly",
    "纤瘦": "slim",
    # ---- 服 ----
    "黑色修身长袍": "fitted black robe",
    "白色长袍": "white robe",
    "长袍": "robe",
    "修身": "fitted",
    "宽大": "loose-fitting",
    "银色云纹": "silver cloud patterns",
    "云纹": "cloud pattern",
    "刺绣": "embroidered",
    "银色": "silver",
    "金色": "gold",
    "黑色": "black", "白色": "white", "红色": "red", "蓝色": "blue",
    "披风": "cape", "斗篷": "cloak", "铠甲": "armor",
    "和服": "kimono", "汉服": "hanfu", "西装": "suit",
    "连衣裙": "dress", "制服": "uniform", "大衣": "coat",
    "围巾": "scarf", "手套": "gloves", "腰带": "belt",
    "靴子": "boots", "长靴": "tall boots",
    # ---- 特征 ----
    "左眼下有一颗小痣": "small beauty mark below the left eye",
    "右眼下有一颗小痣": "small beauty mark below the right eye",
    "小痣": "small beauty mark",
    "刀疤": "knife scar", "疤痕": "scar",
    "耳环": "earrings", "项圈": "choker", "项链": "necklace",
    "眼镜": "glasses", "面具": "mask",
}


def 加词(表):
    """运行时给词典加词：角色库.加词({"某个词": "some phrase"})"""
    _词典.update(表)
    return len(_词典)


# 中文标点 -> 切段的分隔符
_切 = re.compile(r"[，,、;；/|·]+")
_汉字 = re.compile(r"[\u4e00-\u9fff]+")


def _译(词, 报=None):
    """
    中文外貌描述 -> 英文提示词。

    规则（按优先级）：
      1. 整串命中词典      -> 直接用
      2. 按中文标点切段，每段先试整段命中
      3. 段内「最长词优先」替换
      4. 替换完还有中文残留 -> **报警并丢掉**（绝不混进提示词里）
    已经是英文的段落原样保留。
    """
    if not 词:
        return ""
    词 = str(词).strip()
    if not 词:
        return ""
    if 词 in _词典:
        return _词典[词]

    果段, 未译 = [], []
    for s in (x.strip() for x in _切.split(词)):
        if not s:
            continue
        if s in _词典:
            果段.append(_词典[s])
            continue
        # 段内最长词优先（两侧补空格，免得英文单词粘成一坨）
        r = s
        for c in sorted(_词典, key=len, reverse=True):
            if c in r:
                r = r.replace(c, " " + _词典[c] + " ")
        剩 = _汉字.findall(r)
        if 剩:
            未译.append(f"{s}（没译出：{'、'.join(剩)}）")
            r = _汉字.sub(" ", r)                 # 中文字符丢掉
        r = re.sub(r"[（(][^)）]*[)）]", " ", r)   # 丢掉括号残渣
        r = re.sub(r"\s*[,;]\s*", ", ", r)
        r = re.sub(r"\s{2,}", " ", r).strip(" ,，;；")
        if r:
            果段.append(r)

    if 未译:
        讯 = "⚠ 词典缺词，这些描述**没有**进提示词：" + "；".join(未译) + \
             "　→ 补词：角色库.加词({'中文': 'english'})"
        if 报:
            报(讯)
        else:
            print(讯)

    return ", ".join(果段)


def 外貌串(名, 带种子=False):
    """
    生成拼进提示词的角色串。**这是锁定一致性的关键** ——
    同一角色的每一镜都用这同一段文字，一个字都不能改。
    """
    _载()
    r = 角色表.get(名)
    if not r:
        return {"串": "", "种子": None, "错": f"没有这个角色：{名}"}

    段 = []
    if r.get("年龄"):
        段.append(_年龄.get(r["年龄"], r["年龄"]))
    if r.get("性别"):
        段.append(_性别.get(r["性别"], r["性别"]))
    if r.get("体态"):
        段.append(_译(r["体态"]))
    if r.get("发"):
        段.append(_译(r["发"]))
    if r.get("眼"):
        段.append(_译(r["眼"]))
    if r.get("肤"):
        段.append(_译(r["肤"]))
    if r.get("服"):
        段.append(_译(r["服"]))
    if r.get("特征"):
        段.append(_译(r["特征"]))
    for k, v in r.items():
        if k not in ("名", "性别", "年龄", "发", "眼", "肤", "服", "特征",
                     "体态", "种子", "备注", "定妆照") and v:
            段.append(_译(str(v)))

    串 = ", ".join(x for x in 段 if x)
    果 = {"串": 串, "种子": r["种子"], "名": 名}
    if 带种子:
        果["带种子串"] = f"({名}: {串})" if 串 else ""
    return 果


def 多人串(名单, 分隔=" | "):
    """多角色同框：把几个角色的外貌串拼起来"""
    段 = []
    for 名 in 名单:
        a = 外貌串(名)
        if a.get("串"):
            段.append(f"{名}({a['串']})")
    return 分隔.join(段)


# ============================================================
# 定妆照
# ============================================================

def 定妆提示词(名, 风格键="cinematic-real", 景别="portrait"):
    """生成角色定妆照的提示词（正面、中性表情、干净背景 —— 便于之后复用）"""
    from 风格库 import 编译 as 风格编译
    a = 外貌串(名)
    中性 = "neutral expression, facing camera, character reference sheet, plain grey background, even lighting, full body visible" if 景别 == "全身" \
        else "neutral expression, facing camera, head and shoulders portrait, plain grey background, even studio lighting"
    正 = 风格编译(风格键, 额外=f"{a['串']}, {中性}")
    return 正


def 定妆照路径(名):
    _载()
    os.makedirs(定妆目录, exist_ok=True)
    return os.path.join(定妆目录, f"{名}.png")


def 记定妆(名, 路径):
    """把出好的定妆照记进角色卡（之后每镜都能引用它）"""
    _载()
    if 名 in 角色表:
        角色表[名]["定妆照"] = 路径
        _存()
    return 角色表.get(名)


# ============================================================
# 导出 / 导入
# ============================================================

def 导出(路径):
    _载()
    with open(路径, "w", encoding="utf-8") as f:
        json.dump(角色表, f, ensure_ascii=False, indent=2)
    return 路径


def 打印():
    _载()
    if not 角色表:
        print("\n（角色库空的）\n")
        return
    print(f"\n{'角色':<10} {'种子':<12} {'外貌串':<60}")
    print("-" * 92)
    for 名 in 角色表:
        a = 外貌串(名)
        串 = a["串"]
        print(f"{名:<10} {a['种子']:<12} {(串[:56] + '…') if len(串) > 56 else 串}")
    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        名 = sys.argv[1]
        a = 外貌串(名)
        if a.get("错"):
            print(a["错"])
        else:
            print(f"\n【{名}】种子 {a['种子']}\n{a['串']}\n")
    else:
        打印()
