# -*- coding: utf-8 -*-
"""按《磨刀》01-节拍拆解.md 的锚点表，把四个角色登记进角色库。

锚点串是**全片每一格都要逐字复用**的东西 —— 所以这里写的每个字段
都必须能被 `角色库._译()` 译出来。译不出来的词会被丢掉并报警，
锚点就残了（甲客/乙客第一次就是这个问题：六个描述全被丢掉）。
跑完看输出的报警，有报警就补词再跑。
"""
import sys
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 角色库 as r   # noqa: E402

# 先把这部片子要用的词全补上（词典缺词 = 锚点失效）
r.加词({
    # 沈砚
    "黑发在脑后束成一条低马尾": "black hair tied in a low ponytail at the back",
    "低马尾": "low ponytail",
    "用一根削得极短的竹签别住": "held with a short bamboo pin",
    "竹签": "bamboo pin",
    "浅褐色眼睛": "light brown eyes",
    "浅褐色瞳": "light brown eyes",
    "眼尾略下垂": "slightly downturned outer eye corners",
    "左眉骨上一道细疤": "a thin scar on his left brow bone",
    "从眉中斜到眉尾": "running from the middle of the brow to its tail",
    "细疤": "thin scar",
    "深灰蓝短打": "dark grey-blue short jacket",
    "深灰蓝": "dark grey-blue",
    "外面套一件洗得发白的旧牛皮围裙": "a washed-out old leather apron over it",
    "旧牛皮围裙": "worn leather apron",
    "洗得发白": "washed-out, faded",
    "围裙右腰挂着磨石袋": "a whetstone pouch hanging at the right hip of the apron",
    "磨石袋": "whetstone pouch",
    "右耳一只很小的铜环": "a very small bronze hoop in his right ear",
    "铜环": "bronze hoop",
    # 赵崇武
    "花白短须修得齐整盖住下颌": "a neatly trimmed grey-white short beard covering his jaw",
    "花白短须": "grey-white short beard",
    "修得齐整": "neatly trimmed",
    "盖住下颌": "covering the jaw",
    "浓眉压着一双小眼睛": "thick brows pressing down on small eyes",
    "浓眉": "thick brows",
    "小眼睛": "small eyes",
    "下眼睑松垂": "loose sagging lower eyelids",
    "肩背宽厚微微发福": "broad-shouldered and running slightly to fat",
    "肩背宽厚": "broad-shouldered",
    "微微发福": "slightly heavy-set",
    "深灰官袍": "dark grey official's robe",
    "胸前一块磨旧发暗的银补子": "a worn darkened silver rank badge on the chest",
    "银补子": "silver rank badge",
    "黑纱帽": "black gauze official's cap",
    # 阿七
    "高颧骨": "high cheekbones",
    "右眼比左眼浅一号": "his right eye a shade lighter than the left",
    "面色发青白": "a sickly blue-white complexion",
    "像常年不见太阳": "as if he never sees the sun",
    "深靛蓝军服": "deep indigo military uniform",
    "两臂各扣一道铜护臂": "a bronze armguard buckled on each forearm",
    "铜护臂": "bronze armguards",
    "腰悬一把单刃直刀": "a single-edged straight sabre hanging at his waist",
    "单刃直刀": "single-edged straight sabre",
    "左手自手背起有一道旧刀疤": "an old sabre scar running from the back of his left hand",
    "一直延伸到袖口里": "disappearing up into his sleeve",
    # 阿满
    "黑发在脑后盘成一个小圆髻": "black hair coiled into a small round bun at the back",
    "小圆髻": "small round bun",
    "插一根自己刻的小刀形状骨簪": "pinned with a bone hairpin she carved herself in the shape of a small knife",
    "骨簪": "bone hairpin",
    "圆脸": "round face",
    "右眼角外有两颗并排的小痣": "two small moles side by side at the outer corner of her right eye",
    "两颗并排的小痣": "two small moles side by side",
    "绿布袄子": "green cloth padded jacket",
    "袄子": "padded jacket",
    "外罩一件靛蓝布包头巾": "an indigo cloth head wrap over it",
    "布包头巾": "cloth head wrap",
    "手里总攥着一块拧干的粗布": "always clutching a wrung-out cloth",
    "右手手背上一道横的旧刀疤": "a horizontal old sabre scar on the back of her right hand",
})

人 = [
    dict(名="沈砚", 性别="男", 年龄="青年", 体态="精瘦",
         发="黑发在脑后束成一条低马尾，用一根削得极短的竹签别住",
         眼="浅褐色眼睛，眼尾略下垂", 肤="风吹日晒的皮肤",
         服="深灰蓝短打，外面套一件洗得发白的旧牛皮围裙，围裙右腰挂着磨石袋",
         特征="左眉骨上一道细疤，从眉中斜到眉尾；右耳一只很小的铜环",
         种子=20261014, 备注="磨刀匠，十年前听雪楼最年轻的刀客"),
    dict(名="赵崇武", 性别="男", 年龄="中年", 体态="肩背宽厚微微发福",
         发="花白短发", 眼="浓眉压着一双小眼睛，下眼睑松垂", 肤="古铜色的皮肤",
         服="深灰官袍，胸前一块磨旧发暗的银补子，黑纱帽",
         特征="花白短须修得齐整盖住下颌",
         种子=20261015, 备注="提刑按察使司按察使，十年前带兵围楼的人"),
    dict(名="阿七", 性别="男", 年龄="中年", 体态="精瘦",
         发="短发", 眼="右眼比左眼浅一号", 肤="面色发青白，像常年不见太阳",
         服="深靛蓝军服，两臂各扣一道铜护臂，腰悬一把单刃直刀",
         特征="高颧骨；左手自手背起有一道旧刀疤，一直延伸到袖口里",
         种子=20261016, 备注="参将，听雪楼唯一活下来的同僚，真叛徒"),
    dict(名="阿满", 性别="女", 年龄="青年", 体态="娇小",
         发="黑发在脑后盘成一个小圆髻，插一根自己刻的小刀形状骨簪",
         眼="大眼", 肤="小麦色",
         服="绿布袄子，外罩一件靛蓝布包头巾",
         特征="圆脸；右眼角外有两颗并排的小痣；右手手背上一道横的旧刀疤",
         种子=20261017, 备注="偏院茶铺烧火的，七岁那夜的活人证"),
]

print("=== 登记 ===")
for x in 人:
    r.建(**x)
    print(f"  建 {x['名']}")

print("\n=== 锚点复验（有报警就是词典还缺词）===")
for x in 人:
    a = r.外貌串(x["名"])
    print(f"\n  【{x['名']}】种子 {a.get('种子')}")
    print(f"    {a.get('串','')}")
