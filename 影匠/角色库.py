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
    "男性": "male", "长盖住": "long, covering",
    # ★ 2026-10-16 凌晨补：角色卡里描述体格/比例/服装的词（57 条）
    "成年男性": "adult male",
    "成年女性": "adult woman",
    "成年": "adult",
    "身高一米八": "1.8 meters tall",
    "身高一米七二": "1.72 meters tall",
    "身高一米七五": "1.75 meters tall",
    "身高一米九": "1.9 meters tall",
    "肩宽腰细": "broad shoulders and a narrow waist",
    "头身比": "head-to-body ratio",
    "是正常成年人比例": "is the normal adult proportion",
    "头不大": "the head is not large",
    "头": "head",
    "长度约等于肩宽": "its length is about the shoulder width",
    "三分之二": "two thirds",
    "短碎发": "short choppy hair",
    "偏分": "side-parted",
    "深": "dark",
    "眉毛平直": "straight eyebrows",
    "眉毛": "eyebrows",
    "鼻梁": "the bridge of the nose",
    "高": "high",
    "直": "straight",
    "清楚": "clearly defined",
    "鹅蛋脸": "oval face",
    "颧骨平": "flat cheekbones",
    "颧骨": "cheekbones",
    "披在背后": "falling down her back",
    "发尾到腰": "the ends reach her waist",
    "眼睛": "eyes",
    "大": "large",
    "薄": "thin",
    "眼尾微微往下垂": "the outer corners droop slightly",
    "眼尾往下垂": "the outer corners droop",
    "耳朵尖而长": "long pointed ears",
    "耳朵上缘向后上方拉出一个两厘米": "the upper rim of each ear pulls back and up two centimeters",
    "尖角": "a pointed tip",
    "双眼皮": "double eyelids",
    "脸圆": "a round face",
    "鼻头": "the tip of the nose",
    "圆": "round",
    "皮肤偏黄": "yellowish skin",
    "嘴唇": "lips",
    "嘴角往上": "the corners of the mouth turned up",
    "皮革": "leather",
    "长度到膝盖": "knee-length",
    "双排扣": "double-breasted",
    "肩上有": "on the shoulders there are",
    "铆钉": "studs",
    "里面": "underneath",
    "窄领带": "a narrow tie",
    "手上戴白手套": "wearing white gloves",
    "左手握一把带鞘": "his left hand grips a sheathed",
    "日本刀": "Japanese sword",
    "刀鞘": "scabbard",
    "暗红色": "dark red",
    "青绿色吊带长裙": "a teal-green slip dress",
    "丝绸面料": "silk fabric",
    "裙摆到脚踝": "the hem reaches her ankles",
    "肩带": "the shoulder straps",
    "细": "thin",
    "墨绿色连帽外套": "a dark green hooded jacket",
    "拉链敞": "the zipper open",
    "黑长裤": "black trousers",
    "长裤": "trousers",
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

    # ---- 2026-10-15 补：做新戏《修鞋》时 空跑 报出来的缺词 ----
    #   规矩：**只描述它是什么**（别提「不要」），一个词一个英文串，最长词优先。
    #   加词的时候顺手把同一族都补上 —— 只补这一个角色用到的那几个，
    #   下一部戏还会缺同一族里别的词。
    # 年龄 / 职业
    "六十七岁": "sixty-seven years old",
    "六十七岁的修鞋匠": "sixty-seven-year-old cobbler",
    "修鞋匠": "cobbler", "鞋匠": "cobbler",
    "老人": "old man", "老头": "old man", "老太太": "old woman",
    "女孩": "young girl", "小男孩": "little boy", "小男孩": "little boy",
    # 发
    "平头": "buzz cut", "花白平头": "grey buzz cut",
    "花白": "grizzled grey", "花白头发": "grizzled grey hair",
    "短头发": "short hair", "歪辫": "lopsided braids",
    "短头发扎两个歪辫": "short hair in two lopsided braids",
    "两个歪辫": "two lopsided braids",
    # 脸 / 肤
    "很深的脸部皱纹": "deep facial wrinkles",
    "皱纹": "wrinkles", "很深的皱纹": "deep wrinkles",
    # 服
    "深灰对襟旧褂子": "dark grey old-style front-buttoned jacket",
    "对襟旧褂子": "old-style front-buttoned jacket",
    "对襟褂子": "front-buttoned jacket",
    "蓝布褂子": "blue cloth jacket",
    "深灰": "dark grey", "深蓝": "dark blue", "藏青": "navy",
    "围裙": "apron", "蓝色围裙": "blue apron",
    "左膝盖上有一块深色补丁": "a dark patch on the left knee",
    "有一块深色补丁": "a dark patch",
    "深色补丁": "dark patch", "补丁": "patch",
    "洗得发白的红毛衣": "faded red sweater",
    "发白的红毛衣": "faded red sweater",
    "红毛衣": "red sweater", "毛衣": "sweater",
    "发白的": "faded", "洗得发白": "washed-out faded",
    "蓝色棉裤": "blue cotton trousers",
    "棉裤": "cotton trousers", "棉袄": "cotton-padded jacket",
    "布鞋": "cloth shoes", "胶鞋": "rubber shoes",
    "鞋底开了口": "the sole is split open",
    # 体态
    "瘦": "thin", "清瘦": "slender", "高挑清瘦": "tall and slender",
    "背有点驼": "slightly hunched back", "驼背": "hunched back",
    "有点驼": "slightly hunched",
    # 特征
    "左手拇指有一道旧疤": "an old scar on the left thumb",
    "左手拇指有一道": "an old scar on the left thumb",
    "旧疤": "old scar", "有一道旧疤": "has an old scar",

    # ---- 兜底虚词：它们本身没有画面含义，留着只会让「缺词」报警一直响 ----
    #   ★ 一定放在最后 —— _译() 是「最长词优先」，长词先匹配，剩下的「的」才落到这里。
    "左脚那只": "left", "右脚那只": "right", "那只": "that", "这只": "this",
    "瘦小": "small and thin",
    "的": "", "了": "", "着": "", "很": "", "有点": "slightly",
    "发梢": "hair tips",
    "略乱": "slightly messy",
    "发梢有点长": "slightly long hair tips",
    "脸型偏长": "slightly long face shape",
    "下颌线": "jawline",
    "下颌线很柔和": "soft jawline",
    "柔和": "soft",
    "绿色外套": "green jacket",
    "长裤": "trousers",
    "黑色长裤": "black trousers",
    "白球鞋": "white sneakers",
    "两只手插在裤袋里": "both hands in trouser pockets",
    "肩膀垮着": "slumped shoulders",
    "没精神": "listless",
    "整个人站得很没精神": "standing listlessly",
    "皮肤偏白": "fair skin",
    "眼型偏圆": "round eye shape",
    "深棕色的": "dark brown",
    "两只眼睛是深棕色的": "dark brown eyes",
    "眼型": "eye shape",
    "深棕色": "dark brown",
    "二十岁成年女性": "20-year-old adult woman",
    "头身比是正常成年人比例": "normal adult head-to-body ratio",
    "头的长度约等于肩宽的三分之二": "head length about two thirds of shoulder width",
    "琥珀棕色眼睛": "amber-brown eyes",
    "眼睛很大": "large eyes",
    "两只耳朵是普通的圆耳朵": "two ordinary rounded ears",
    "耳垂很小": "small earlobes",
    "鼻梁很直": "straight nose bridge",
    "嘴唇很薄": "thin lips",
    "肩带很细": "thin shoulder straps",
    "黑色窄领带": "black slim necktie",
    "左手握一把带鞘的日本刀": "holding a sheathed Japanese katana in the left hand",
    "刀鞘暗红色": "dark red scabbard",
    "白色小臂绷带": "white forearm bandage",
    "十八岁男性": "18-year-old male",
    "刘海有点长盖住眉毛": "bangs a little long covering the eyebrows",
    "鼻头有点圆": "slightly rounded nose tip",
    "拉链敞着": "zipper open",
    "里面白衬衫": "white shirt underneath",
    "十八岁成年男性": "18-year-old adult male",
    "黑色短碎发": "short black choppy hair",
    "刘海偏分": "side-parted bangs",
    "深褐色眼睛": "dark brown eyes",
    "鼻梁很高": "high nose bridge",
    "下颌线清楚": "defined jawline",
    "黑色皮革长风衣": "black leather long trench coat",
    "肩上有银色铆钉": "silver studs on the shoulders",
}

# ============================================================
# 武侠词包 —— 为多角色古装片补的
# ============================================================
# 为什么要一次补这么多：`_译()` 的规矩是**译不出来就丢掉并报警**。
# 第一次做多角色测试（`_技术验证.py`）时，两个角色的锚点串里
# 「矮壮敦实 / 灰白短发贴着头皮 / 细长鹰眼 / 深灰色粗布短打 / 腰缠麻绳 /
# 右脸一道从眉骨到下巴的旧疤」**全部被丢掉了** —— 提示词里只剩
# `middle-aged, male, bronze skin`。也就是说**角色锚点其实是失效的**，
# 上一条片子能锁住脸，是因为凌霜的那几个词刚好在词典里。
# 锚点串是每一镜都要复用的东西，词典不全 = 一致性靠运气。
_词典.update({
    # ---- 发（形）----
    "灰白短发贴着头皮": "close-cropped grey-white hair",
    "灰白短发": "short grey-white hair",
    "灰白": "grey-white",
    "花白短发": "short grizzled hair",
    "花白": "grizzled, greying",
    "贴着头皮": "close-cropped",
    "乌黑高马尾束到脑后": "jet-black hair in a high ponytail tied at the back",
    "乌黑高马尾": "jet-black high ponytail",
    "乌黑长发": "long jet-black hair",
    "乌黑": "jet-black",
    "高马尾": "high ponytail",
    "束发": "hair tied up", "散发": "loose hair",
    "披散": "hanging loose", "两鬓斑白": "greying at the temples",
    "花白胡须": "grizzled beard", "络腮胡": "full beard",
    "短须": "short beard", "无须": "clean-shaven",
    "发带": "headband", "包头巾": "cloth head wrap",
    "半束发": "half-tied hair", "编发": "braided hair",
    "额前碎发": "stray strands over the forehead",
    # ---- 眼（形）----
    "细长鹰眼": "narrow eagle-like eyes",
    "鹰眼": "eagle-like eyes",
    "大而圆的褐色眼睛": "large round brown eyes",
    "褐色眼睛": "brown eyes", "褐色瞳": "brown eyes",
    "黑色眼睛": "dark eyes",
    "三角眼": "triangular eyes", "眯眼": "narrow squinting eyes",
    "上挑眼尾": "upturned outer eye corners",
    "眼下一片青黑": "dark circles under the eyes",
    "眼神锐利": "sharp piercing gaze",
    # ---- 肤 ----
    "古铜色的皮肤": "bronze skin",
    "风吹日晒的皮肤": "weathered skin",
    "粗糙": "rough-textured", "细嫩": "smooth",
    # ---- 体态 ----
    "矮壮敦实": "short and stocky, heavily built",
    "矮壮": "short and stocky",
    "敦实": "heavily built",
    "纤细高挑": "tall and slender",
    "纤细": "slender", "修长": "long-limbed",
    "虎背熊腰": "broad-shouldered and thick-set",
    "精瘦": "lean and wiry",
    "颀长": "tall and slim", "瘦削": "gaunt",
    "微微驼背": "slightly hunched",
    "跛脚": "limping", "右腿微跛": "slight limp in the right leg",
    "挺直": "upright posture",
    # ---- 服（古装/武侠）----
    "深灰色粗布短打": "dark grey coarse cloth short jacket",
    "灰色粗布短打": "grey coarse cloth short jacket",
    "粗布短打": "coarse cloth short jacket",
    "短打": "short jacket",
    "月白色窄袖劲装": "pale moon-white narrow-sleeved martial outfit",
    "白色窄袖劲装": "white narrow-sleeved martial outfit",
    "窄袖劲装": "narrow-sleeved martial outfit",
    "劲装": "martial outfit",
    "玄色官袍": "black official's robe",
    "官袍": "official's robe",
    "青色长衫": "blue-grey long gown",
    "长衫": "long scholar's gown",
    "杏色布衣": "apricot-coloured cloth dress",
    "布衣": "plain cloth clothes",
    "麻衣": "hemp garment",
    "粗布": "coarse cloth",
    "羊皮袄": "sheepskin jacket",
    "蓑衣": "straw rain cape",
    "斗笠": "conical straw hat",
    "腰缠麻绳": "hemp rope wound around the waist",
    "麻绳": "hemp rope",
    "腰束银扣皮带": "silver-buckled leather belt at the waist",
    "皮带": "leather belt",
    "束腰": "cinched waist", "宽腰带": "wide sash",
    "护腕": "bracers", "铁护腕": "iron bracers",
    "布绑腿": "cloth leg wraps", "绑腿": "leg wraps",
    "草鞋": "straw sandals", "布鞋": "cloth shoes",
    "皂靴": "black boots", "皮靴": "leather boots",
    "披甲": "wearing armour", "铁甲": "iron armour",
    "锦袍": "brocade robe", "蟒袍": "python-robe (high official)",
    "罩衫": "outer smock", "坎肩": "sleeveless jacket",
    "衲衣": "patched monk's robe", "僧袍": "monk's robe",
    "道袍": "Taoist robe", "头巾": "headscarf",
    "背着一把刀": "carrying a sabre on his back",
    "背着一把没有鞘的刀": "carrying an unsheathed sabre on his back",
    "腰间别着一把刀": "a sabre tucked at his waist",
    "提着一把刀": "holding a sabre in one hand",
    "拄着一根木杖": "leaning on a wooden staff",
    "木杖": "wooden staff",
    # ---- 特征 ----
    "右脸一道从眉骨到下巴的旧疤": "an old scar running from his right brow to his jaw",
    "从眉骨到下巴的旧疤": "an old scar from brow to jaw",
    "旧疤": "old scar", "刀疤脸": "scarred face",
    "左耳挂一枚银环": "a silver hoop in her left ear",
    "银环": "silver hoop", "耳洞": "pierced ears",
    "少了一根手指": "missing a finger",
    "断眉": "a split eyebrow",
    "左眼下有一颗小痣": "small beauty mark below the left eye",
    "眉心有一颗红痣": "a red mole between the brows",
    "纹身": "tattoo", "刺青": "tattoo",
    "满脸风霜": "a weather-beaten face",
    "嘴唇干裂": "chapped lips",
    "指节粗大": "thick knuckles",
    "手掌有厚茧": "calloused palms",
    "脖颈一道勒痕": "a ligature mark on the neck",
    # ---- 情绪 / 神态（写提示词用，不进锚点也可以）----
    "面无表情": "expressionless",
    "冷笑": "a cold smirk", "苦笑": "a bitter smile",
    "咬牙": "teeth clenched", "怒目": "glaring",
    "垂眼": "eyes lowered", "闭眼": "eyes closed",
    # ---- 场景零件（古装）----
    "灰瓦屋顶": "grey tiled roofs",
    "木格窗": "wooden lattice windows",
    "白墙": "whitewashed walls",
    "酒旗": "a tavern banner hanging outside",
    "红灯笼": "red lanterns",
    "纸窗": "paper windows",
    "土墙": "earthen wall",
    "青石板路": "flagstone road",
    "木廊柱": "wooden veranda pillars",
    "屏风": "folding screen",
    "八仙桌": "square wooden table",
    "长凳": "wooden bench",
    "柜台": "wooden counter",
    "香炉": "incense burner",
    "供桌": "altar table",
    "牌位": "ancestral tablets",
    "祠堂": "ancestral hall",
    "衙门": "magistrate's office",
    "城墙": "city wall",
    "牌坊": "memorial archway",
    "渡口": "river ferry crossing",
    "乌篷船": "a covered river boat",
    "驿站": "post station",
    "镖局": "escort agency",
    "药铺": "herbal medicine shop",
    "当铺": "pawnshop",
    "铁匠铺": "blacksmith's forge",
    "灯笼": "paper lantern",
    "火把": "torch",
    "油灯": "oil lamp",
    "烛台": "candlestick",
    "马厩": "stable",
    "轿子": "sedan chair",
    "旌旗": "banners",
    "卷宗": "case files", "血书": "a letter written in blood",
    "蓑衣斗笠": "straw cape and conical hat",

    # ---- 《磨刀》四个角色的锚点词 ----
    # ★ 教训：这些词一开始是写在 `_立角色_磨刀.py` 里 `角色库.加词({...})` 的。
    # `加词()` 只改**当前进程**的 `_词典`，不落盘 —— 角色卡写进了
    # `角色库.json`（持久），词典却随进程消失。后果是「建角色那次锚点是全的，
    # 之后任何一次跑出来的锚点都缺词」，而且缺得**不报错**（只在带 报= 的
    # 时候才打印一行警告）。锚点串是每一格都复用的东西，这种静默降级会
    # 让整部片子的一致性慢慢烂掉。**要持久就写在这里。**
    "黑发在脑后束成一条低马尾": "black hair tied in a low ponytail at the back",
    "低马尾": "low ponytail",
    "用一根削得极短的竹签别住": "held with a short bamboo pin",
    "竹签": "bamboo pin",
    "浅褐色眼睛": "light brown eyes", "浅褐色瞳": "light brown eyes",
    "眼尾略下垂": "slightly downturned outer eye corners",
    "左眉骨上一道细疤": "a thin scar on his left brow bone",
    "从眉中斜到眉尾": "running from the middle of the brow to its tail",
    "细疤": "thin scar",
    "深灰蓝短打": "dark grey-blue short jacket", "深灰蓝": "dark grey-blue",
    "外面套一件洗得发白的旧牛皮围裙": "a washed-out old leather apron over it",
    "旧牛皮围裙": "worn leather apron", "洗得发白": "washed-out, faded",
    "围裙右腰挂着磨石袋": "a whetstone pouch hanging at the right hip of the apron",
    "磨石袋": "whetstone pouch",
    "右耳一只很小的铜环": "a very small bronze hoop in his right ear",
    "铜环": "bronze hoop",
    "花白短须修得齐整盖住下颌": "a neatly trimmed grey-white short beard covering his jaw",
    "花白短须": "grey-white short beard", "修得齐整": "neatly trimmed",
    "盖住下颌": "covering the jaw",
    "浓眉压着一双小眼睛": "thick brows pressing down on small eyes",
    "浓眉": "thick brows", "小眼睛": "small eyes",
    "下眼睑松垂": "loose sagging lower eyelids",
    "肩背宽厚微微发福": "broad-shouldered and running slightly to fat",
    "肩背宽厚": "broad-shouldered", "微微发福": "slightly heavy-set",
    "深灰官袍": "dark grey official's robe",
    "胸前一块磨旧发暗的银补子": "a worn darkened silver rank badge on the chest",
    "银补子": "silver rank badge", "黑纱帽": "black gauze official's cap",
    "高颧骨": "high cheekbones",
    "右眼比左眼浅一号": "his right eye a shade lighter than the left",
    "面色发青白": "a sickly blue-white complexion",
    "像常年不见太阳": "as if he never sees the sun",
    # ★ 「军服」这个词不能直译成 military uniform —— 实测模型会画成民国军官制服
    # （立领 + 肩章 + 铜扣 + 皮带），完全不是古代武将。必须把「古代」钉进串里，
    # 再把现代制服的三个特征（肩章/领章/铜扣）显式排除掉。
    "深靛蓝军服": ("deep indigo ancient Chinese military robe, crossed collar, "
                "cloth sash at the waist, no epaulettes, no collar tabs, no metal buttons"),
    "两臂各扣一道铜护臂": "a bronze armguard buckled on each forearm",
    "铜护臂": "bronze armguards",
    "腰悬一把单刃直刀": "a single-edged straight sabre hanging at his waist",
    "单刃直刀": "single-edged straight sabre",
    "左手自手背起有一道旧刀疤": "an old sabre scar running from the back of his left hand",
    "一直延伸到袖口里": "disappearing up into his sleeve",
    "黑发在脑后盘成一个小圆髻": "black hair coiled into a small round bun at the back",
    "小圆髻": "small round bun",
    "插一根自己刻的小刀形状骨簪": "pinned with a bone hairpin she carved herself in the shape of a small knife",
    "骨簪": "bone hairpin",
    "圆脸": "round face",
    "右眼角外有两颗并排的小痣": "two small moles side by side at the outer corner of her right eye",
    "两颗并排的小痣": "two small moles side by side",
    "绿布袄子": "green cloth padded jacket", "袄子": "padded jacket",
    "外罩一件靛蓝布包头巾": "an indigo cloth head wrap over it",
    "布包头巾": "cloth head wrap",
    "手里总攥着一块拧干的粗布": "always clutching a wrung-out cloth",
    "右手手背上一道横的旧刀疤": "a horizontal old sabre scar on the back of her right hand",
    # ---- 《磨刀》场景词 ----
    "渡口": "river ferry crossing", "木棚": "wooden shed",
    "风灯": "wind lantern", "油纸伞": "oil-paper umbrella",
    "黑油纸伞": "black oil-paper umbrella",
    "磨刀石": "whetstone", "磨石": "whetstone",
    "没有开刃的长刀": "an unsharpened long sabre",
    "未开刃": "unsharpened", "刃口": "the edge of the blade",
    "官靴": "official's boots", "铜牌": "bronze token",
    "提刑按察使司": "the provincial surveillance commission",
    "二更鼓": "the second night-watch drum",
    "官袍领口": "the collar of an official's robe",
    "名册": "a name register", "朱笔": "a vermilion brush",
    "朱笔圈住": "circled in vermilion ink",
    "门洞": "gateway arch", "偏院": "side courtyard",
    "茶铺": "teahouse", "茶烟": "steam off the tea",
    "长明灯": "an ever-burning lamp", "火折子": "a tinder stick",
    "柴房": "firewood shed", "门槛": "threshold",
    "军服": "military uniform", "护臂": "armguard",
    "弯刀": "curved sabre", "刀尖": "the tip of the sabre",
    "按下刀": "lowering the sabre", "刀停在半空": "the sabre stopped in mid-air",
    "刀背": "the back of the blade", "刀柄": "the hilt",
    "泥水": "muddy water", "雨水": "rainwater",
    "木牌": "wooden signboard", "匾额": "horizontal plaque",

    # ---- 《楚子航·耶梦加得》两个角色的锚点词（2026-10-15 补）----
    # ★ 为什么补：`剧组.py 出图四宫格 楚子航` 跑完 32 张，每张都刷了一屏
    #   「⚠ 词典缺词，这些描述**没有**进提示词」—— 角色卡里写的东西
    #   （疤、绷带、竖瞳、爪子）**一个字都没进提示词**，模型当然画不出来。
    #   这是第 424 行那条教训的复发：新戏建角色时不补词，锚点串就是残的。
    "楚": "Chu Zihang", "楚子航": "Chu Zihang",
    "耶梦加得": "Jormungand",
    "二十一岁": "twenty-one years old",
    "黑色短发": "short black hair",
    "被雨淋透贴在额头上": "soaked by rain and plastered flat to his forehead",
    "雨淋透": "soaked by rain",
    "右眼下方一道两厘米长的旧疤": "an old two-centimetre scar below his right eye",
    "右眼下方": "below his right eye", "两厘米长的旧疤": "a two-centimetre old scar",
    "旧疤": "old scar",
    "嘴角有干掉的血痕": "a dried bloodstain at the corner of his mouth",
    "干掉的血痕": "dried bloodstain", "血痕": "bloodstain",
    "脸上全是雨水": "rainwater all over his face",
    "黑色校服外套": "a black school uniform jacket",
    "校服外套": "school uniform jacket", "校服": "school uniform",
    "左袖口撕裂到肘部": "its left cuff torn up to the elbow",
    "袖口撕裂": "torn cuff", "撕裂到肘部": "torn up to the elbow",
    "右手从手背到手腕缠着白色绷带": "a white bandage wrapped from the back of his right hand to his wrist",
    "右手手背到手腕": "the back of his right hand to his wrist",
    "缠着白色绷带": "wrapped in a white bandage", "白绷带": "white bandage",
    "绷带": "bandage",
    "绷带被雨泡成灰色": "the bandage soaked grey by the rain",
    "泡成灰色": "soaked grey",
    "绷带头从手腕垂下来一截随动作甩动": "a loose end of the bandage hanging off his wrist and swinging as he moves",
    "垂下来一截": "hanging down a length", "随动作甩动": "swinging with his movement",
    "右手握刀": "gripping a knife in his right hand", "握刀": "gripping a knife",
    "刀脱手": "the knife flying out of his hand",
    "金色长发垂到腰": "long blond hair falling to his waist",
    "金色长发": "long blond hair", "垂到腰": "falling to the waist",
    "一根都没湿": "not a single strand wet",
    "金色竖瞳": "vertical golden pupils", "竖瞳": "vertical pupils",
    "白皮肤": "pale skin",
    "嘴裂到耳根": "his mouth split back to his ears",
    "牙齿是三角形": "triangular teeth",
    "黑色长风衣": "a long black trench coat", "长风衣": "long trench coat",
    "风衣下摆是鳞片": "scales along the hem of the coat",
    "风衣下摆": "the hem of the coat", "鳞片": "scales",
    "嘴里叼着一块带卡塞尔学院银色徽章的蓝色校服布":
        "a strip of blue school-uniform cloth bearing a silver Cassell College crest clamped in his mouth",
    "卡塞尔学院": "Cassell College", "银色徽章": "silver crest", "校服布": "school-uniform cloth",
    "龙王人形": "the dragon king in human form",
    "脚是爪子": "his feet are claws", "爪子": "claws",
    "踩在桥面上留出三道白痕": "leaving three white gouges on the bridge deck",
    "三道白痕": "three white gouges",
    # ---- 《楚子航》场景 / 道具词 ----
    "跨江大桥": "a river bridge", "雨夜": "a rainy night",
    "桥面": "the bridge deck", "桥的另一头": "the far end of the bridge",
    "钠灯": "sodium lamps", "灯带": "a run of lights",
    "湿沥青": "wet asphalt", "金色的血": "golden blood",

    # ==== 《楚子航·夏弥》按原著重做（2026-10-15 16:0x）====
    # ★ 为什么补：上面那一块（509 行起）是**我照着自己编的剧情**写的词典 ——
    #   耶梦加得被我写成了「金发男、竖瞳、爪子踩桥面」，全是假的。
    #   真设定：耶梦加得 = 夏弥，一个**女孩**，卡塞尔学院一年级新生；
    #   战场不在跨江大桥，在**北京地铁深处的尼伯龙根**；
    #   她才是被楚子航用**昂热的折刀**贯穿心脏的那一个。
    #   判据：`python _验词.py` 打印的英文串里**一个中文字符都不许剩**。
    # ---- 楚子航（原著相貌原文）----
    "楚子航": "Chu Zihang",
    "二十岁": "twenty years old",
    "典型的中国脸": "a classic Chinese face",
    "一头毫不驯服的黑色短发": "an unruly mop of black hair",
    "前额开阔": "a broad forehead",
    "眉宇漆黑挺拔": "dark, straight, strongly drawn brows",
    "睫毛整齐": "neat eyelashes",
    "鼻梁挺直": "a straight nose bridge",
    "脸部线条明晰": "sharply defined facial lines",
    "黄金瞳": "golden pupils", "黄金色的眼睛": "golden eyes",
    "自己发亮": "glowing on their own",
    # ★ 定妆照实测：只写「黄金瞳自己发亮」六个字，模型画出来是深棕眼睛。
    #   要把这一对眼睛写成**整张脸上最亮的东西**才画得出来（见 `_出定妆照.py` 的 改词）。
    "两只眼睛是纯金色的": "his two eyes are pure gold",
    "纯金色的": "pure gold-coloured",
    "虹膜和瞳孔整个都是熔金一样的亮金色":
        "both iris and pupil a bright molten-gold colour",
    "熔金一样的亮金色": "a bright molten-gold colour",
    "虹膜": "iris", "瞳孔": "pupil", "眼白干净": "clean whites of the eyes",
    "睫毛根根清楚": "every eyelash distinct",
    "是他整张脸上最亮、最显眼的地方":
        "the brightest, most eye-catching thing on his whole face",
    "在影棚平光下也自己发着光": "glowing on their own even under flat studio light",
    "自己发着光": "glowing on their own",
    "眼神平静地直视镜头": "gazing calmly straight into the lens",
    "没有表情": "with no expression at all",
    "黑色长款风衣": "a long black trench coat",
    "白衬衫": "a white shirt", "黑领带": "a black necktie",
    "白纱布": "white gauze",
    "黑鞘长刀": "a long knife in a black sheath",
    "反握": "held in a reverse grip",
    "银色折刀": "a small silver folding knife",
    "铜钥匙": "a brass key", "风铃": "a wind chime",
    "宿舍窗台": "the dormitory windowsill",
    "窗外的光": "the light outside the window",
    # ---- 夏弥 / 耶梦加得（原著相貌原文）----
    "夏弥": "Xia Mi", "耶梦加得": "Jormungand",
    "十八岁": "eighteen years old",
    "浅棕色长发": "light-brown long hair",
    "高高扎起的马尾": "a high ponytail",
    "蓬松的刘海像一团雾": "fluffy bangs like a bank of mist",
    "皮肤白得透光": "skin so pale it lets the light through",
    "眼睛很亮": "bright eyes", "睫毛很长": "very long eyelashes",
    "脸颊有点婴儿肥": "a little baby fat in her cheeks",
    "嘴角有一颗小虎牙": "a small fang at one corner of her mouth",
    "额头正中间裂开一道细缝": "a thin crack splitting open in the centre of her forehead",
    "缝里透出金色的光": "golden light shining out of the crack",
    "深色校服外套": "a dark school-uniform jacket",
    "短裙": "a pleated skirt", "校徽色的小领带": "a small crest-coloured tie",
    "两只手都空着": "both hands empty at her sides",
    "影子比人长三倍": "a shadow three times taller than she is",
    "长着角和尾巴": "with horns and a tail",
    "贴在地铁墙上": "cast flat on the subway wall",
    # ---- 北京地铁尼伯龙根（场景）----
    "北京地铁隧道": "a Beijing subway tunnel",
    "地铁隧道": "a subway tunnel", "地铁站台": "a subway platform",
    "应急灯": "emergency lights", "一亮一灭": "blinking on and off",
    "隧道深处": "deep inside the tunnel", "隧道地面": "the tunnel floor",
    "隧道里的潮气": "the damp air of the tunnel",
    "两排红色应急灯": "two rows of red emergency lights",
    "地铁的风": "the wind pushed along by the subway",
    "尼伯龙根": "Nibelungen",
    "混凝土站台": "a concrete platform",
    "铁轨": "the rails", "铁轨上的锈": "rust on the rails",
})

# ★ 2026-10-15 晚：《楚子航夏弥》定妆卡用的词，一次补齐。
# 病根：`剧组.py 出图` **不拿定妆卡当参考图** —— 它把 02-九宫格.md 的「角色卡」中文描述
# 逐词翻成英文再拼进提示词。**词典里没有的词会被整段丢掉**（只在屏幕上打一行告警）。
# 实测夏弥的描述里「浅棕色 / 半扎 / 水手领 / 百褶裙 / 缎带 / 琥珀 / 中筒袜 / 小皮鞋 /
# 蝴蝶结 / 虎牙 / 长鬓发」一个都没有 → 32 格里的夏弥根本不是我定下来的那个人。
# **这条管线里，词典就是「人物形象」本身。**
# 注意：`加词()` 只改内存、**不落盘**；要让 `出图`（另起进程）吃到词，必须写在这个字面量里。
_词典.update({
    # ── 夏弥 · 头发 ───────────────────────────────────────
    "浅棕色": "light ash-brown",
    "亚麻灰棕": "flaxen ash-brown",
    "半扎": "half-up half-down hairstyle",
    "在脑后松松地收成一束": "gathered loosely into one bundle at the back of the head",
    "缎带": "satin ribbon",
    "宝蓝色缎带": "royal blue satin ribbon",
    "缎带系成蝴蝶结": "tied into a bow with a satin ribbon",
    "蝴蝶结": "bow",
    "宝蓝色蝴蝶结": "royal blue bow",
    "缎带蝴蝶结": "ribbon bow",
    "蓬松的刘海": "fluffy bangs",
    "额前蓬松的刘海": "fluffy bangs across the forehead",
    "长鬓发": "long side locks",
    "两侧各有一绺长鬓发垂到胸前面": "one long side lock falling down each side of her face to the front of her chest",
    "其余长发全部散着垂到腰下": "the rest of her long hair hangs loose all the way below her waist",
    "发尾松松地打着卷": "the ends loosely curled",
    "虎牙": "a small fang tooth",
    "小虎牙": "a small fang tooth",
    "琥珀棕色": "amber-brown",
    "琥珀棕色的眼睛": "amber-brown eyes",
    "眼睛很大很圆": "very large round eyes",
    "双眼皮线": "a clear double-eyelid crease",

    # ── 夏弥 · 衣服 ───────────────────────────────────────
    "水手领": "sailor collar",
    "水手领上衣": "sailor-collar top",
    "深蓝色的水手领": "dark navy sailor collar",
    "领边滚两道白线": "trimmed with two white stripes along the edge",
    "背心裙": "pinafore dress",
    "棕色背心裙": "brown pinafore dress",
    "格纹": "plaid",
    "棕色格纹": "brown plaid",
    "棕色格纹百褶裙": "brown plaid pleated skirt",
    "中筒袜": "crew socks",
    "白中筒袜": "white crew socks",
    "小皮鞋": "leather loafers",
    "棕色小皮鞋": "brown leather loafers",
    "校徽": "school crest",

    # ── 夏弥 · 身材 ───────────────────────────────────────
    "个子高": "tall",
    "骨架舒展": "long-limbed and loosely built",
    "腿很长": "very long legs",
    "腿又长又直": "long straight legs",
    "身材修长": "slender and tall",
    "头身比": "head-to-body ratio",
    "七头身": "seven-heads-tall proportions",
    "成年女性": "adult woman",
    "大学生": "university student",

    # ── 楚子航 · 补充 ─────────────────────────────────────
    "刘海短短地停在眉毛上面": "short bangs stopping just above the eyebrows",
    "两只眼睛都露出来": "both eyes fully visible",
    "脸型偏短": "a rather short face",
    "下颌收得利落": "a cleanly tapered jawline",
    "下巴短而方": "a short square chin",
    "眼型细长": "long narrow eyes",
    "上眼睑压得很低": "heavy low upper eyelids",
    "深蓝色的中短头发": "dark blue medium-short hair",
    "深蓝色": "dark blue",
    "藏青蓝": "navy blue",
    "黑色皮风衣": "black leather trench coat",
    "金属圆扣": "round metal buttons",
    "银灰色金属圆扣": "silver-grey round metal buttons",
    "宽翻领": "wide lapels",
    "领子内侧深蓝": "dark blue lining inside the collar",
    "深蓝黑色的领带": "dark navy-black necktie",
    "结打得很松": "tied loosely",
    "黑色皮手套": "black leather gloves",
    "护腕": "wrist guard",
    "黑鞘长刀": "a long sword in a black scabbard",
    "白纱布": "white gauze bandage",
    "缠着一圈白纱布": "wrapped with a loop of white gauze",
    "金色眼睛": "golden eyes",
    "金黄色的眼睛": "bright golden-yellow eyes",

    # ── 场景 / 道具 ───────────────────────────────────────
    "地铁隧道": "subway tunnel",
    "北京地铁站": "Beijing subway station",
    "站台": "platform",
    "隧道": "tunnel",
    "积水": "standing water",
    "应急灯": "emergency light",
    "荧光灯管": "fluorescent tube",
    "白瓷砖": "white tiles",
    "水磨石": "terrazzo",
    "拱顶": "vaulted ceiling",
    "灰白色": "off-white",
    "铜钥匙": "brass key",
    "老式铜钥匙": "an old-fashioned brass key",
    "风铃": "wind chime",
    "铜片": "brass plates",
    "窗台": "windowsill",
    "宿舍": "dormitory room",
    "黑鳞": "black scales",
    "鳞片": "scales",
    "折刀": "folding knife",
    "银色折刀": "silver folding knife",
    "爪子": "claws",
    # 洗完角色卡之后又发现的漏词
    "脑后松松地收成一束": "gathered loosely into one bundle at the back of the head",
    "用一根": "with a",
    "一根": "a",
    "系成蝴蝶结": "tied into a bow",
})


def 加词(表):
    """运行时给词典加词：角色库.加词({"某个词": "some phrase"})"""
    _词典.update(表)
    return len(_词典)


# 中文标点 -> 切段的分隔符
_切 = re.compile(r"[，,、;；/|·]+")
_汉字 = re.compile(r"[\u4e00-\u9fff]+")


_词典.update({
    # ── 楚子航的头发：用户说「后边的头发好稀疏」────
    "发量很多": "thick hair with lots of volume",
    "头发很厚": "thick heavy hair",
    "后脑勺的头发也很饱满": "full voluminous hair at the back of the head",
    # ── 夏弥的半龙形态（这段剧情里她有【人形】和【半龙】两种）────
    "额头正中裂开一道细缝": "a thin crack opening down the exact center of her forehead",
    "缝里透出金色的光": "golden light glowing out of the crack",
    "额角长出一对向后弯的黑色小角": "a pair of small black horns curving backwards from her temples",
    "角的根部有一圈黑色的鳞片": "a ring of black scales around the base of each horn",
    "耳朵变尖": "her ears grown long and sharply pointed",
    "脖子两侧浮出一片片黑鳞": "patches of black scales surfacing on both sides of her neck",
    "小臂上浮出黑鳞": "black scales surfacing along her forearms",
    "手指变长": "her fingers grown longer",
    "指甲变成黑色的尖爪": "her nails turned into sharp black claws",
    "哑光的黑鳞": "matte black scales",
})

_词典.update({
    # ── 楚子航那条卡刷出来之后暴露的缺词 ─────────────────────
    "发量很多很厚": "thick heavy hair with lots of volume",
    "很厚": "thick",
    "略显凌乱": "slightly messy",
    "两只眼睛都是金黄色的": "both eyes are bright golden yellow",
    "皮肤很白": "very pale skin",
    "脸型偏短": "a rather short face",
    "下巴短而方": "a short square chin",
    "下颌收得利落": "a sharply defined jawline",
    "两只手都戴着黑色皮手套": "black leather gloves on both hands",
    "黑色皮手套": "black leather gloves",
    "里面是白衬衫": "a white shirt underneath",
    "脖子上一条深蓝黑色的领带": "a deep navy-black necktie",
    "领带结打得很松": "a loosely knotted tie",
    "左手腕上一个黑色护腕": "a black wrist guard on his left wrist",
    "印着绿色的学号": "printed with a green student number",
    "右手边一把黑鞘长刀": "a black-sheathed long sword at his right side",
    "右手缠着一圈白纱布": "his right hand wrapped in one loop of white gauze",
    "手背到手腕缠着白纱布": "white gauze wrapped from the back of his hand to his wrist",
    # ── 夏弥那条卡 ────────────────────────────────────────────
    "脑后松松收成一束": "gathered loosely into one bundle at the back of her head",
    "用一根宝蓝色缎带系成蝴蝶结": "tied into a bow with a royal-blue ribbon",
    "额前蓬松的刘海": "fluffy bangs over her forehead",
    "皮肤白得透光": "skin so fair it looks translucent",
    "眼睛很大很圆": "very large round eyes",
    "睫毛很长": "very long eyelashes",
    "嘴角有一颗小虎牙": "one small fang at the corner of her mouth",
    "两侧各有一绺长鬓发": "one long lock of hair down each side of her face",
})

_词典.update({
    "深蓝色的水手领上衣": "a deep navy-blue sailor-collar blouse",
    "胸口一个宝蓝色蝴蝶结": "a royal-blue bow at her chest",
    "宝蓝色蝴蝶结": "a royal-blue bow",
    "宝蓝色缎带": "a royal-blue ribbon",
})

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
