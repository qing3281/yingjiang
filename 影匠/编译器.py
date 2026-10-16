# -*- coding: utf-8 -*-
"""
影匠 · 提示词编译器（照飞彩 FEICAI-Studio 复刻）
=================================================

接口（对齐 导演.py / 引擎.py 的「模块级函数 + 中文名」风格）：

    编译.整体(设定, 自定义预设=None) -> str
    编译.单格(景别, 主体与动作, 环境, 时间光照, 风格标签, 排除词, 描述, 宫格) -> dict
    编译.宫格(数量, 主题, ...) -> list
    编译.检查(提示词, 只要问题=False) -> list

    python 编译器.py 自测     # exit 0，打印 通过/失败/没测
    python 编译器.py 演示
    python 编译器.py 词表

证据（全部来自飞彩解包产物，逐字提取，不是推测）：
  D:\\DSHworkspace\\网盘\\_飞彩解包\\Win\\.next\\static\\chunks\\9490-a7bad63d9cae38d9.js
      模块 32047 —— 四张词表 + 查找器（$U/Qb/bC/ev/fF/wd）
      模块 70308 —— buildStylePrompt(压缩名 ec) / 渲染类型表 m / 族裔表 h / 23 风格预设 g
  D:\\DSHworkspace\\网盘\\_飞彩解包\\Win\\.next\\static\\chunks\\210-5385ca9119171eec.js
      # 镜头类型参考 表（11 种景别，逐字）
  D:\\DSHworkspace\\网盘\\_飞彩解包\\Win\\9宫格分镜Gem.txt / 4宫格分镜Gem.txt / 25宫格分镜Gem.txt
      六段公式、C1-C8、宫格规范、NO-TEXT 铁律
  D:\\DSHworkspace\\网盘\\_飞彩解包\\Win\\.next\\static\\chunks\\210-...js（模块 1079）
      ⛔ STRICT NO-TEXT RULE 英文原文

唯一红线：不碰 .next\\static\\chunks\\9876543210-*.js（加密包），不伪造设备指纹。
"""

import json
import os
import re
import sys

_根 = os.path.dirname(os.path.abspath(__file__))
if _根 not in sys.path:
    sys.path.insert(0, _根)

__all__ = [
    "编译", "整体", "单格", "宫格", "检查", "自测",
    "视觉风格表", "画质表", "镜头光效表", "光影氛围表", "渲染类型表", "族裔表", "预设表", "景别表",
    "元指令模式", "扫描元指令", "洗元指令",
]


def _装模块(文件名, 别名):
    """
    载入影匠既有模块（只读，绝不改它们）。
    中文文件名在部分环境直接 import 会失败，所以先试 import，再退回按路径载入。
    —— 这一段与 一致性.py:53 的写法完全一致，照抄。
    """
    try:
        return __import__(别名), ""
    except Exception as e1:
        pass
    try:
        import importlib.util
        p = os.path.join(_根, 文件名)
        if not os.path.isfile(p):
            return None, "文件不存在：" + p
        spec = importlib.util.spec_from_file_location("_影匠_" + 别名, p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        return m, ""
    except Exception as e2:
        return None, "import 失败(%r)；按路径载入失败(%r)" % (e1, e2)


# ============================================================================
# 一、词表（飞彩模块 32047 + 70308 逐字提取）
# ============================================================================

#: 视觉风格表 —— 飞彩 32047 变量 i（8 种，查找器 $U）
视觉风格表 = [
    {"id": "cinematic-realism", "icon": "🎬", "label": "电影写实", "subtitle": "真人实拍质感",
     "keywords": "cinematic realism, photorealistic, film grain, natural skin texture, lifelike"},
    {"id": "anime", "icon": "🌸", "label": "日系动漫", "subtitle": "赛璐璐/新海诚",
     "keywords": "anime style, cel shading, vibrant colors, detailed backgrounds, Japanese animation"},
    {"id": "3d-render", "icon": "🧊", "label": "3D 渲染", "subtitle": "皮克斯/CG 质感",
     "keywords": "3D render, Pixar style, smooth shading, volumetric lighting, CGI quality"},
    {"id": "oil-painting", "icon": "🖌️", "label": "油画风格", "subtitle": "古典绘画质感",
     "keywords": "oil painting style, classical art, textured brushstrokes, rich color palette, fine art"},
    {"id": "watercolor", "icon": "🎨", "label": "水彩插画", "subtitle": "水彩晕染质感",
     "keywords": "watercolor illustration, soft washes, fluid edges, pastel tones, delicate"},
    {"id": "comic", "icon": "💥", "label": "漫画风格", "subtitle": "美漫/港漫线条",
     "keywords": "comic book style, bold outlines, halftone dots, dynamic composition, graphic novel"},
    {"id": "ink-wash", "icon": "🏔️", "label": "国风水墨", "subtitle": "中国水墨画意境",
     "keywords": "Chinese ink wash painting, sumi-e, splashed ink, traditional brushwork, ethereal landscape"},
    {"id": "cyberpunk", "icon": "🌆", "label": "赛博朋克", "subtitle": "霓虹/未来都市",
     "keywords": "cyberpunk aesthetic, neon lights, dark futuristic city, holographic, high-tech low-life"},
]

#: 画质表 —— 飞彩 32047 变量 n（3 档，查找器 bC，回落 n[0]）
画质表 = [
    {"id": "cinematic", "label": "影院级", "resolution": "4K",
     "keywords": "ultra high definition, 4K UHD, cinematic quality, sharp details, professional color grading"},
    {"id": "broadcast", "label": "广播级", "resolution": "2K",
     "keywords": "high definition, 2K, broadcast quality, clear details, balanced sharpness"},
    {"id": "web", "label": "网络级", "resolution": "1K",
     "keywords": "standard definition, 1080p, web quality, optimized for streaming"},
]

#: 镜头光效表 —— 飞彩 32047 变量 a（8 种，多选，查找器 ev 逗号拼接）
镜头光效表 = [
    {"id": "shallow-dof", "label": "浅景深",
     "keywords": "shallow depth of field, bokeh background, subject isolation, soft out-of-focus areas"},
    {"id": "film-grain", "label": "胶片颗粒",
     "keywords": "film grain, analog film texture, 35mm film look, photochemical noise"},
    {"id": "lens-flare", "label": "镜头光晕",
     "keywords": "lens flare, anamorphic flare, light streaks, sun flare"},
    {"id": "motion-blur", "label": "运动模糊",
     "keywords": "motion blur, speed lines, dynamic movement, directional blur"},
    {"id": "vignette", "label": "暗角",
     "keywords": "vignette, darkened edges, center focus, cinematic framing"},
    {"id": "tilt-shift", "label": "移轴",
     "keywords": "tilt-shift effect, miniature look, selective focus plane, toy-like perspective"},
    {"id": "anamorphic", "label": "变形宽银幕",
     "keywords": "anamorphic lens, oval bokeh, horizontal lens flare, widescreen cinematic"},
    {"id": "chromatic", "label": "色散",
     "keywords": "chromatic aberration, color fringing, RGB split, prismatic effect"},
]

#: 光影氛围表 —— 飞彩 32047 变量 o（8 种，单选；auto 的 keywords 是空串，故 buildStylePrompt 不输出该行）
光影氛围表 = [
    {"id": "auto", "icon": "🤖", "label": "自动", "subtitle": "AI 按剧情判断", "keywords": ""},
    {"id": "golden-hour", "icon": "🌅", "label": "黄金时刻", "subtitle": "日出日落暖光",
     "keywords": "golden hour lighting, warm sunlight, long soft shadows, amber glow"},
    {"id": "blue-hour", "icon": "🌊", "label": "蓝调时刻", "subtitle": "黎明/黄昏冷色",
     "keywords": "blue hour, cool ambient light, twilight tones, serene atmosphere"},
    {"id": "high-key", "icon": "☀️", "label": "高调明亮", "subtitle": "明亮均匀光线",
     "keywords": "high-key lighting, bright and even, minimal shadows, clean white light"},
    {"id": "low-key", "icon": "🌑", "label": "低调暗黑", "subtitle": "强烈明暗对比",
     "keywords": "low-key lighting, dramatic shadows, chiaroscuro, high contrast, moody"},
    {"id": "neon", "icon": "💜", "label": "霓虹灯光", "subtitle": "都市霓虹色彩",
     "keywords": "neon lighting, colorful neon glow, urban night, electric purple and cyan"},
    {"id": "candlelight", "icon": "🕯️", "label": "烛光暖调", "subtitle": "温暖柔和烛光",
     "keywords": "candlelight, warm flickering light, intimate atmosphere, soft orange glow"},
    {"id": "moonlight", "icon": "🌙", "label": "月光冷调", "subtitle": "银色月光笼罩",
     "keywords": "moonlight, cool silver light, night scene, ethereal lunar glow"},
]

#: 渲染类型表 —— 飞彩 70308 变量 m（5 项，导出名 Pf，查找器 KK=y）。auto 的 keywords 是空串。
#: 注意：任务书与 知识\\提示词编译.md 说「渲染类型与视觉风格共用 8 词表」—— 产物里不是这样，
#: 渲染类型是这 5 项，视觉风格是上面那 8 项。见 知识\\编译器.md「与飞彩的逐条对应」。
渲染类型表 = [
    {"id": "auto", "icon": "🤖", "label": "自动", "keywords": ""},
    {"id": "3d-cg", "icon": "🧊", "label": "3D CG",
     "keywords": "3D CG rendering, volumetric lighting, smooth shading, ray tracing quality"},
    {"id": "2d-illustration", "icon": "🖌️", "label": "2D插画",
     "keywords": "2D illustration, hand-drawn style, flat color shading, clean linework"},
    {"id": "photorealistic", "icon": "📸", "label": "真人实拍",
     "keywords": "photorealistic, live-action photography, natural skin texture, real-world lighting"},
    {"id": "digital-painting", "icon": "🎨", "label": "数字绘画",
     "keywords": "digital painting, textured brushstrokes, painterly style, rich color blending"},
]

#: 族裔/市场表 —— 飞彩 70308 变量 h（导出名 Mb）
族裔表 = [
    {"id": "asian", "label": "东亚", "icon": "🌸"},
    {"id": "japan_korea", "label": "日韩系", "icon": "✨"},
    {"id": "western", "label": "欧美", "icon": "🗽"},
    {"id": "mixed", "label": "多元", "icon": "🌐"},
    {"id": "none", "label": "不限", "icon": "◌"},
]

#: 23 种风格预设 —— 飞彩 70308 变量 g（导出名 xi），字段 id/label/emoji/keywords/prompt。
#: prompt 就是飞彩的中文风格描述（风格提示词.json 里缺这个字段）。
预设表 = [
    {"id": "3d-xianxia", "label": "3D国漫仙侠", "emoji": "🐉",
     "keywords": "Chinese 3D animation, CG rendering, xianxia fantasy, gilded gold and crimson accents, ice blue and purple haze palette, ethereal oriental atmosphere, magical particle effects, volumetric lighting",
     "prompt": "3D国漫CG渲染，玄幻仙侠风，鎏金、绯红、冰蓝、紫霞色调，东方仙气华丽感"},
    {"id": "cyberpunk", "label": "赛博朋克", "emoji": "🌃",
     "keywords": "cyberpunk aesthetic, neon-lit dark sci-fi, electric blue and magenta palette, chrome silver accents, holographic reflections, wet surface reflections, high-tech dystopian atmosphere",
     "prompt": "赛博朋克霓虹光影，电光蓝、品红、铬银色调，潮湿阴暗科技感"},
    {"id": "anime-cel", "label": "日系赛璐璐", "emoji": "🌸",
     "keywords": "Japanese anime cel shading, Kyoto Animation quality, warm orange and sakura pink palette, sky blue and silver tones, detailed hand-drawn look, soft light bloom, delicate emotional expressions",
     "prompt": "日系赛璐璐手绘动画感，暖橘、樱粉、天空蓝色调，清新治愈电影质感"},
    {"id": "dark-gothic", "label": "暗黑哥特", "emoji": "🦇",
     "keywords": "dark gothic fantasy, Soulsborne aesthetic, abyss black and blood red palette, rusted copper and ghost green, heavy fog atmosphere, dramatic chiaroscuro lighting, epic dark tone",
     "prompt": "暗黑哥特魂系油画质感，深渊黑、血红、锈铜色调，压抑沉重史诗感"},
    {"id": "ghibli", "label": "吉卜力田园", "emoji": "🍃",
     "keywords": "Studio Ghibli watercolor style, hand-painted pastoral, grass green and wheat gold palette, sky blue and cloud white, warm sunlight through canopy, gentle breeze movement, cozy magical atmosphere",
     "prompt": "吉卜力水彩手绘田园风，草绿、麦金、天蓝色调，温暖质朴奇幻感"},
    {"id": "marvel-dc", "label": "美漫超英", "emoji": "⚡",
     "keywords": "Marvel DC superhero, comic book inspired style, steel gray and justice blue palette, flame red and thunder gold, dynamic action poses, energy effects, blockbuster epic tone",
     "prompt": "美漫超英电影级CG，钢铁灰、正义蓝、烈焰红色调，热血大片质感"},
    {"id": "pixel-retro", "label": "像素复古", "emoji": "👾",
     "keywords": "pixel art, 16-bit retro game style, high saturation primary colors, gem blue and bright yellow, crisp pixel grid rendering, nostalgic 8-bit aesthetic, charming sprite design",
     "prompt": "16bit像素复古游戏风，高饱和红、宝石蓝、亮黄色调，怀旧精致感"},
    {"id": "ink-wash", "label": "墨韵国风", "emoji": "🎨",
     "keywords": "Chinese ink wash painting, sumi-e brushwork, gongbi and splashed ink fusion, ink black and rice paper white, vermillion red and mineral blue accents, generous negative space, ethereal misty atmosphere",
     "prompt": "中国水墨工笔泼墨结合，墨黑、宣白、朱砂红色调，空灵写意东方气韵"},
    {"id": "steampunk", "label": "蒸汽朋克", "emoji": "⚙️",
     "keywords": "steampunk Victorian industrial aesthetic, brass and steam machinery, antique bronze and rust orange palette, deep brown tones, riveted leather textures, clockwork mechanical details, retro-industrial romanticism",
     "prompt": "蒸汽朋克维多利亚工业美学，古铜金、铁锈橙、深棕色调，复古厚重工业感"},
    {"id": "disney-3d", "label": "迪士尼3D", "emoji": "✨",
     "keywords": "Disney Pixar 3D animation, cartoon rendering, candy pink and sky blue palette, sunshine yellow and mint green, exaggerated expressive characters, sparkle and magic dust effects, cheerful fairy tale atmosphere",
     "prompt": "迪士尼皮克斯3D卡通渲染，糖果粉、天空蓝、阳光黄色调，欢快梦幻童话感"},
    {"id": "ukiyoe", "label": "浮世绘和风", "emoji": "🌊",
     "keywords": "ukiyo-e Japanese woodblock print style, flat composition with bold outlines, indigo blue and vermillion red palette, decorative cloud patterns, gold leaf accents, dramatic kabuki-inspired poses, classic elegance",
     "prompt": "浮世绘日本版画，平面构图粗线条，靛蓝、朱红、藤黄色调，古朴典雅戏剧感"},
    {"id": "oil-painting", "label": "古典油画", "emoji": "🖼️",
     "keywords": "classical oil painting, Renaissance master brushwork, Rembrandt lighting, deep brown and dark gold palette, crimson and ivory white, rich impasto texture, Tyndall light effect, fine art museum quality",
     "prompt": "古典油画文艺复兴笔触，深棕、暗金、猩红色调，厚重写实艺术殿堂感"},
    {"id": "cyberpunk-anime", "label": "赛博日漫", "emoji": "🤖",
     "keywords": "cyberpunk anime fusion, Ghost in the Shell and Akira style, deep purple and electric blue palette, fluorescent orange and dark silver, glitch art effects, holographic UI overlays, mechanical details",
     "prompt": "赛博朋克日系动画，深紫、电光蓝、荧光橙色调，硬核科幻日式细腻美学"},
    {"id": "wuxia-realistic", "label": "写实武侠", "emoji": "⚔️",
     "keywords": "realistic Chinese wuxia, cinematic CG rendering, ink teal and maple red palette, smoke gray and moonlight white, flowing robes and sharp martial arts action, epic sweeping atmosphere, classical Chinese warrior aesthetic",
     "prompt": "写实武侠电影级CG，墨青、枫红、烟灰、月白色调，大气磅礴江湖意境"},
    {"id": "vintage-film", "label": "复古胶片", "emoji": "📽️",
     "keywords": "vintage analog film, Kodak Fuji film stock tones, warm yellow and faded cyan palette, caramel brown and cream white, film grain texture, lens flare, slight overexposure, nostalgic soft atmosphere",
     "prompt": "复古胶片柯达富士色调，暖黄、褪色青、焦糖棕色调，温柔怀旧文艺感"},
    {"id": "horror-thriller", "label": "惊悚恐怖", "emoji": "👻",
     "keywords": "horror thriller, dark low-key lighting, pitch black and pale white palette, putrid green and dark red, flickering light effects, heavy vignette, creeping fog, oppressive claustrophobic atmosphere",
     "prompt": "恐怖惊悚暗调摄影，漆黑、惨白、腐绿、暗红色调，窒息压抑悬念感"},
    {"id": "sci-fi-epic", "label": "史诗科幻", "emoji": "🚀",
     "keywords": "epic science fiction, cinematic CG rendering, space black and plasma blue palette, engine orange and titanium silver, massive scale composition, particle beam effects, hard sci-fi realism",
     "prompt": "史诗科幻星际大片级CG，星空黑、等离子蓝、引擎橙色调，宏大硬科幻质感"},
    {"id": "dreamy-pastel", "label": "梦幻柔彩", "emoji": "🦄",
     "keywords": "dreamy pastel illustration, soft focus ethereal glow, lavender purple and peach pink palette, cream yellow and mint blue, stardust particle effects, watercolor diffusion, healing romantic atmosphere",
     "prompt": "梦幻柔彩柔焦朦胧，薰衣草紫、蜜桃粉、奶油黄色调，温柔治愈浪漫感"},
    {"id": "korean-webtoon", "label": "韩漫唯美", "emoji": "🎎",
     "keywords": "Korean webtoon semi-realistic illustration, soft glow and smooth shading, rose pink and moonlight blue palette, champagne gold and mist gray, bokeh background blur, backlit hair glow, romantic K-drama atmosphere",
     "prompt": "韩漫唯美半写实插画，玫瑰粉、月光蓝、香槟金色调，唯美浪漫韩剧氛围"},
    {"id": "nolan-epic", "label": "诺兰大片", "emoji": "🎬",
     "keywords": "Christopher Nolan cinematic style, IMAX film photography, steel blue and concrete gray palette, deep ocean ink and glacier white, practical effects realism, restrained intense atmosphere, cerebral epic tone",
     "prompt": "诺兰IMAX胶片级摄影，钢蓝、混凝土灰、冰川白色调，冷峻严肃史诗厚重感"},
    {"id": "post-apocalypse", "label": "末日废土", "emoji": "🏜️",
     "keywords": "post-apocalyptic wasteland, Mad Max desert aesthetic, gritty grain texture, dust yellow and rust red palette, charred black and faded khaki, sandstorm haze, desolate savage atmosphere",
     "prompt": "末日废土荒漠美学，沙尘黄、铁锈红、焦黑色调，苍凉狂野生存感"},
    {"id": "zombie-apocalypse", "label": "丧尸末世", "emoji": "🧟",
     "keywords": "zombie apocalypse, Walking Dead style, oppressive desolation, decay green and blood red palette, haze gray and bone white, blood mist effects, flashlight beams in darkness, desperate survival atmosphere",
     "prompt": "丧尸末世写实恐怖，腐败绿、凝血红、阴霾灰色调，紧张绝望末世求生感"},
    {"id": "urban-realistic", "label": "都市写实", "emoji": "🏙️",
     "keywords": "urban realistic photography, modern city natural and artificial light mix, neon purple and streetlamp warm yellow palette, deep sky blue and asphalt gray, rain bokeh effects, long exposure light trails, cinematic urban atmosphere",
     "prompt": "都市写实现代城市摄影级，霓虹紫、路灯暖黄、天幕深蓝色调，真实细腻电影感"},
]

#: 景别表 —— 飞彩 210 chunk「# 镜头类型参考」表，逐字 11 行
景别表 = [
    {"英文": "Extreme wide shot", "中文": "大远景", "用途": "展示环境全貌"},
    {"英文": "Wide shot", "中文": "远景", "用途": "人物与环境关系"},
    {"英文": "Full shot", "中文": "全景", "用途": "人物全身"},
    {"英文": "Medium shot", "中文": "中景", "用途": "对话交流"},
    {"英文": "Medium close-up", "中文": "中近景", "用途": "表情+上半身"},
    {"英文": "Close-up", "中文": "特写", "用途": "面部表情"},
    {"英文": "Extreme close-up", "中文": "大特写", "用途": "眼睛/手部等细节"},
    {"英文": "Over-the-shoulder", "中文": "过肩镜头", "用途": "对话视角"},
    {"英文": "Low angle", "中文": "仰拍", "用途": "权威/压迫感"},
    {"英文": "High angle", "中文": "俯拍", "用途": "渺小/脆弱感"},
    {"英文": "Dutch angle", "中文": "倾斜镜头", "用途": "不安/紧张"},
]

#: 时间/光照 中文 → 英文（对应 Gem 里「清晨微光、正午烈日、黄昏金光、深夜月光」那一句）
时间英译 = {
    "清晨微光": "dawn soft light", "清晨": "early morning light", "黎明": "dawn light", "破晓": "first light of dawn",
    "正午烈日": "harsh noon sunlight", "正午": "harsh noon sunlight", "中午": "midday sunlight",
    "黄昏金光": "sunset golden hour", "黄昏": "dusk golden light", "傍晚": "dusk golden light",
    "日落": "sunset golden hour", "日出": "sunrise light",
    "深夜月光": "midnight blue moonlight", "深夜": "midnight blue moonlight", "夜晚": "night scene with cool moonlight",
    "月夜": "silvery moonlight", "满月": "full moonlight",
    "阴天": "overcast diffused light", "雨天": "rainy diffused light", "雪天": "snowy cold light",
    "薄雾": "misty diffused light", "室内夜灯": "warm indoor lamplight",
}

#: 宫格规范 —— 飞彩 Gemini生图专用Gem.txt「宫格规范」段
宫格规范 = {
    4: {"布局": "2行×2列", "板型": "Sequence Board 序列板",
        "节奏": ["引入", "发展", "转折", "余韵"],
        "说明": "九宫格中某一格的 4 格展开",
        "景别要求": "必须至少两种不同景别",
        "描述字数": (10, 20)},
    9: {"布局": "3行×3列", "板型": "Beat Board 节拍板",
        "节奏": ["建立", "建立", "升级", "升级", "升级", "高潮", "高潮", "收束", "收束"],
        "说明": "一段剧情（约1集/1章节）的 9 个关键瞬间",
        "景别要求": "至少 1 远景 + 3 中景 + 2 特写 + 3 自由",
        "描述字数": (30, 50)},
    25: {"布局": "5行×5列", "板型": "完整细致分镜",
         "节奏": ["起", "承", "转", "合", "余韵"] * 5,
         "说明": "一段长剧情的 25 个关键画面，起承转合的多次循环",
         "景别要求": "追求最大化景别多样性",
         "描述字数": (10, 20)},
}

#: 九宫格景别配额：1 大远景 + 3 中景 + 2 特写 + 3 自由，且相邻不同（避开 QC2「连续 3 个相同景别」）
_景别_9 = [
    "Extreme wide shot",     # 大远景（配额 1 远景）
    "Medium shot",           # 中景（1/3）
    "Close-up",              # 特写（1/2）
    "Medium shot",           # 中景（2/3）
    "Over-the-shoulder",     # 自由（1/3）
    "Low angle",             # 自由（2/3）
    "Extreme close-up",      # 特写（2/2）
    "Medium shot",           # 中景（3/3）
    "High angle",            # 自由（3/3）
]
#: 四宫格：四种不同景别（满足「至少两种」）
_景别_4 = ["Wide shot", "Medium shot", "Close-up", "Full shot"]
#: 25 宫格：11 项景别池以步长 3 轮转 —— 25 格覆盖全部 11 种，相邻必不同
_景别池_25 = [x["英文"] for x in 景别表]
_景别_25 = [_景别池_25[(i * 3) % len(_景别池_25)] for i in range(25)]

#: 节拍 → 英文（宫格在没给英文分段时用它拼 prompt_text）
节拍英文 = {
    "建立": "establishing moment", "升级": "escalating conflict", "高潮": "climactic peak", "收束": "quiet resolution",
    "引入": "introduction", "发展": "development", "转折": "turning point", "余韵": "aftermath",
    "起": "opening beat", "承": "developing beat", "转": "turning beat", "合": "closing beat",
}

#: 节拍 → 情绪强度（QC3 节奏呼吸用）
节拍强度 = {"建立": 1, "升级": 2, "高潮": 3, "收束": 1,
            "引入": 1, "发展": 2, "转折": 3, "余韵": 1,
            "起": 1, "承": 2, "转": 3, "合": 1}


# ============================================================================
# 二、C5 / C6：元指令（会被图像模型渲染成画面里的文字，必须清掉）
# ============================================================================

#: 飞彩 210 chunk 的翻译规则第 4 条自己会往末尾加 `no timecode, no subtitles`，
#: 而同一套 Gem 的 C5 又明令禁止 —— 飞彩新旧两版冲突。影匠按 C5/C6 执行：一律清掉。
元指令模式 = [
    re.compile(r"\bno\s+(time\s*code|timecode|subtitles?|captions?|text|words?|letters?|numbers?|"
               r"watermarks?|logos?|signatures?|typography|labels?|speech\s*bubbles?)\b", re.I),
    re.compile(r"\b(?:without|free\s+of|avoid|excluding)\s+(?:any\s+)?(?:text|words?|letters?|numbers?|"
               r"subtitles?|captions?|watermarks?|logos?|typography)\b", re.I),
    re.compile(r"\b(?:time\s*code|timecode|watermark|subtitle|caption|typography|speech\s*bubble)\b", re.I),
    re.compile(r"\b(?:shot|frame|panel|scene|grid)\s*#?\s*\d+\b", re.I),
    re.compile(r"\b(?:s|f)\s*\d+\s*[:：]"),
    re.compile(r"\b(?:in|at)\s+the\s+(?:top|bottom|upper|lower)[- ](?:left|right)\s+corner\b", re.I),
    re.compile(r"\b(?:top|bottom|upper|lower)[- ](?:left|right)\s+corner\b", re.I),
    re.compile(r"(左上角|右上角|左下角|右下角|画面角落|角标|水印|字幕|时间码|分镜\s*\d+|序号标注|画面文字)"),
    re.compile(r"分镜\s*[XxＸ]"),
]

#: 会被模型画进画面的「文字类」词（检查器额外扫这些）
文字污染词 = [
    "no timecode", "no subtitles", "no subtitle", "no text", "no watermark", "no caption", "no words",
    "speech bubble", "typography", "watermark", "subtitle", "caption",
    "top-left corner", "top-right corner", "bottom-left corner", "bottom-right corner",
    "in the corner", "分镜", "左上角", "右上角", "左下角", "右下角", "水印", "字幕", "时间码", "序号标注",
]


def 扫描元指令(文本):
    """扫描文本里命中的元指令（C5/C6 违禁片段），返回去重后的命中列表。"""
    s = str(文本 or "")
    命中 = []
    for 模 in 元指令模式:
        命中.extend(m.group(0).strip() for m in 模.finditer(s) if m.group(0).strip())
    出 = []
    for x in 命中:
        if x.lower() not in [y.lower() for y in 出]:
            出.append(x)
    return 出


def 洗元指令(文本):
    """把元指令从文本里删掉，返回清理后的文本。"""
    s = str(文本 or "")
    for 模 in 元指令模式:
        s = 模.sub(" ", s)
    s = re.sub(r"\s*[,，、;；]\s*(?=[,，、;；])", "", s)
    s = re.sub(r"^[\s,，、;；]+|[\s,，、;；]+$", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


# ============================================================================
# 三、查找器（对应飞彩模块 32047 / 70308 的导出函数，逐个对齐）
# ============================================================================

def _键(字典, *候选, **kw):
    """从 dict 里按候选键取值（英文键 / 中文键都认，大小写不敏感）。"""
    默认 = kw.get("默认")
    if not isinstance(字典, dict):
        return 默认
    for k in 候选:
        if k in 字典 and 字典[k] is not None:
            return 字典[k]
    小写 = {}
    for k, v in 字典.items():
        try:
            小写[str(k).lower()] = v
        except Exception:
            continue
    for k in 候选:
        v = 小写.get(str(k).lower())
        if v is not None:
            return v
    return 默认


def _列表(值):
    """把 None / dict / list / 标量统一成 list[dict]。"""
    if 值 is None:
        return []
    if isinstance(值, dict):
        出 = []
        for k, v in 值.items():
            if isinstance(v, dict):
                项 = dict(v)
                项.setdefault("name", k)
            else:
                项 = {"name": k, "description": v}
            出.append(项)
        return 出
    if isinstance(值, (list, tuple)):
        return [x if isinstance(x, dict) else {"name": str(x)} for x in 值]
    return [{"name": str(值)}]


def _取视觉风格(id_):
    """飞彩 $U = s：i.find(t=>t.id===e)"""
    return next((x for x in 视觉风格表 if x["id"] == id_), None)


def _取画质(id_):
    """飞彩 bC = l：n.find(t=>t.id===e) || n[0] —— 找不到回落第 1 档"""
    return next((x for x in 画质表 if x["id"] == id_), 画质表[0])


def _取光影(id_):
    """飞彩 wd = c：o.find(t=>t.id===e)"""
    return next((x for x in 光影氛围表 if x["id"] == id_), None)


def _取镜头光效(ids):
    """飞彩 ev = d：map(id→keywords).filter(Boolean).join(', ')"""
    词 = [_取镜头光效项(i) for i in (ids or [])]
    return ", ".join(x["keywords"] for x in 词 if x and x.get("keywords"))


def _取镜头光效项(id_):
    return next((x for x in 镜头光效表 if x["id"] == id_), None)


def _取渲染类型(id_):
    """
    飞彩 KK = y：m.find(t=>t.id===e) —— 只查 5 项渲染类型表。
    影匠额外兜底：若传入的是 8 项视觉风格表的 id（任务书说「两表共用」），
    也认，按视觉风格表的 keywords 输出，避免上游传错就直接丢字段。
    """
    if not id_:
        return None
    r = next((x for x in 渲染类型表 if x["id"] == id_), None)
    if r:
        return r
    v = _取视觉风格(id_)
    if v:
        return {"id": v["id"], "icon": v.get("icon", ""), "label": v["label"], "keywords": v["keywords"],
                "_来自": "视觉风格表兜底"}
    return None


def _分辨率转画质(分辨率):
    """飞彩 fF = u：4K→cinematic / 2K→broadcast / 1K→web，其它一律 cinematic"""
    return {"4K": "cinematic", "2K": "broadcast", "1K": "web"}.get(str(分辨率 or "4K").upper(), "cinematic")


def _取预设(id_, 自定义=None):
    """
    飞彩 N = p(e,t=[])：内置 23 种先查，再退回自定义预设。
        let r=g.find(t=>t.id===e); return r||t.find(t=>t.id===e)
    ⚠ 任务书与 知识\\提示词编译.md §1.3 都写「自定义预设优先」，产物里是内置优先。
      影匠照产物实现；自定义预设仍然生效（只是同名时内置赢）。
    """
    if not id_:
        return None
    r = next((x for x in 预设表 if x["id"] == id_), None)
    if r:
        return r
    for x in (自定义 or []):
        if isinstance(x, dict) and _键(x, "id", "编号", "键", 默认="") == id_:
            return {
                "id": id_,
                "label": _键(x, "label", "名称", "中文", 默认=id_),
                "emoji": _键(x, "emoji", "图标", 默认=""),
                "keywords": _键(x, "keywords", "提示词", "英文", 默认=""),
                "prompt": _键(x, "prompt", "描述", "中文描述", 默认=""),
            }
    return None


def _景别中文(英文):
    x = next((r for r in 景别表 if r["英文"].lower() == str(英文 or "").strip().lower()), None)
    return x["中文"] if x else str(英文 or "")


# ============================================================================
# 四、小工具
# ============================================================================

def _有中文(s):
    return bool(re.search(r"[\u3400-\u9fff]", str(s or "")))


def _词数(s):
    """英文词数：按字母/数字开头的 token 计（'over-the-shoulder' 算 1 词，与英文直觉一致）。"""
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-\.]*", str(s or "")))


def _字数(s):
    """非空白字符数（中文按字计）。"""
    return len(re.sub(r"\s+", "", str(s or "")))


def _截断(s, 上限):
    """飞彩 i(e)：e.length>150 ? e.slice(0,150)+'…' : e"""
    s = str(s or "")
    return s[:上限] + "…" if len(s) > 上限 else s


def _扁平(v):
    """
    列表/元组渲染成顿号串，其余原样 str()。
    风格库.py 的「配色」是 list（如 ['#1c2430', ...]），直接 %s 会把 Python repr
    泄进提示词里（实测踩过：'- 色调：[\\'#1c2430\\', ...]'），所以在拼中文清单前一律过这一道。
    """
    if v is None:
        return ""
    if isinstance(v, (list, tuple, set)):
        return "、".join(str(x) for x in v if str(x).strip())
    return str(v)


def _时间英文(时间光照):
    """中文时间/光照 → 英文短语；已经是英文就原样返回。"""
    s = str(时间光照 or "").strip()
    if not s:
        return ""
    if not _有中文(s):
        return s
    if s in 时间英译:
        return 时间英译[s]
    for k, v in 时间英译.items():
        if k in s:
            return v
    return s  # 认不出来就原样返回，交给 检查() 的 C8 报错，不静默编造


def _清排除词(排除词):
    """
    六段公式的第 6 段。飞彩 §4.5 的反向原则：这一段的正确用法是「写画面里**不要出现**的物件」
    （without any cape, cloak, helmet, wings），而**不是**写 no text / no subtitles 这类元指令。
    返回 (清理后可用的排除词, 被剥掉的元指令列表)。
    """
    if not 排除词:
        return "", []
    命中 = 扫描元指令(排除词)
    干净 = 洗元指令(排除词)
    if not 干净:
        return "", 命中
    if re.match(r"^(without|no\b|exclude|except)\b", 干净, re.I):
        return 干净, 命中
    return "without any " + 干净, 命中


def _描述字数带(宫格):
    return 宫格规范.get(宫格, {}).get("描述字数", (1, 30))


# ============================================================================
# 五、编译器本体
# ============================================================================

class _编译器:
    """提示词编译器。模块级实例 `编译` 就是它的唯一门面。"""

    版本 = "1.0"

    # ---------------------------------------------------------------- 整体 --
    def 整体(self, 设定=None, 自定义预设=None):
        """
        对应飞彩 buildStylePrompt（模块 70308，压缩名 ec）。逐行输出顺序即规格：

            【角色一致性要求 - 所有画面中同一角色外观必须严格保持一致】
            - 名(#id)：描述              ← 超 150 字截断
            【场景一致性要求】            ← subType == "scene-view" 的条目跳过
            【道具一致性要求】
            【整体风格要求】
            - 画幅：
            - Render type: <中文label> — <英文keywords>     ← auto 或无 keywords 则不输出
            - 画质：<中文label> (<分辨率>)
            - 画质要求：<英文keywords>
            - 视觉风格：<中文label> — <英文keywords>
            - 光影氛围：<中文label> — <英文keywords>        ← auto 的 keywords 是空串，故不输出
            - 镜头效果：<中文label, 中文label> — <英文keywords 逗号拼接>
            - Style preset: <中文label> — <英文keywords>
            - 预设风格：<中文label> — <中文描述>
            - 时代/世界观背景：
            - 补充：

        优先级（照产物）：内置 23 种预设 > 自定义预设 > 参考图识别 stylePrompt > 手填 artStyle/colorPalette。
        注意这是 else-if 链：一旦命中 stylePreset，后面的参考图/手填分支整段不走。
        """
        设定 = 设定 if isinstance(设定, dict) else {}

        # -- 兼容两种调用：设定{characters/scenes/props/style} 或直接把风格字段放顶层
        风格 = _键(设定, "style", "风格设置", "风格参数")
        if not isinstance(风格, dict) or not 风格:
            顶层风格键 = ("画幅", "aspectRatio", "渲染类型", "renderType", "画质", "resolution",
                          "视觉风格", "visualStyle", "光影氛围", "lightingMood", "镜头效果", "lensEffects",
                          "风格预设", "stylePreset", "参考图风格", "stylePrompt", "时代背景", "timeSetting")
            if any(k in 设定 for k in 顶层风格键):
                风格 = 设定
            else:
                风格 = 风格 if isinstance(风格, dict) else {}

        角色 = _列表(_键(设定, "characters", "角色", "角色列表", "人物", 默认=[]))
        场景 = _列表(_键(设定, "scenes", "场景", "场景列表", 默认=[]))
        道具 = _列表(_键(设定, "props", "道具", "道具列表", 默认=[]))

        行 = []

        if 角色:
            行.append("【角色一致性要求 - 所有画面中同一角色外观必须严格保持一致】")
            for i, 项 in enumerate(角色, 1):
                名, 号, 描 = self._条目(项, i)
                行.append("- %s(#%s)：%s" % (名, 号, _截断(描, 150)))

        if 场景:
            行.append("\n【场景一致性要求】")
            for i, 项 in enumerate(场景, 1):
                子类 = _键(项, "subType", "子类型", "类型", 默认="")
                if 子类 == "scene-view":      # 飞彩：场景多角度视图不进一致性清单
                    continue
                名, 号, 描 = self._条目(项, i)
                行.append("- %s(#%s)：%s" % (名, 号, _截断(描, 150)))

        if 道具:
            行.append("\n【道具一致性要求】")
            for i, 项 in enumerate(道具, 1):
                名, 号, 描 = self._条目(项, i)
                行.append("- %s(#%s)：%s" % (名, 号, _截断(描, 150)))

        行.append("\n【整体风格要求】")
        画幅 = _键(风格, "画幅", "aspectRatio", "比例", 默认="16:9") or "16:9"
        行.append("- 画幅：%s" % 画幅)

        渲染 = _取渲染类型(_键(风格, "渲染类型", "renderType", 默认=""))
        if 渲染 and 渲染["id"] != "auto" and 渲染.get("keywords"):
            行.append("- Render type: %s — %s" % (渲染["label"], 渲染["keywords"]))

        画质 = _取画质(_分辨率转画质(_键(风格, "画质", "分辨率", "resolution", 默认="4K")))
        行.append("- 画质：%s (%s)" % (画质["label"], 画质["resolution"]))
        if 画质.get("keywords"):
            行.append("- 画质要求：%s" % 画质["keywords"])

        视觉 = _取视觉风格(_键(风格, "视觉风格", "visualStyle", 默认=""))
        if 视觉:
            行.append("- 视觉风格：%s — %s" % (视觉["label"], 视觉["keywords"]))

        光影 = _取光影(_键(风格, "光影氛围", "lightingMood", 默认=""))
        if 光影 and 光影.get("keywords"):        # auto → keywords 空串 → 不输出（照产物）
            行.append("- 光影氛围：%s — %s" % (光影["label"], 光影["keywords"]))

        效果 = _键(风格, "镜头效果", "lensEffects", 默认=[]) or []
        if isinstance(效果, str):
            效果 = [x.strip() for x in re.split(r"[,，、]", 效果) if x.strip()]
        效果词 = _取镜头光效(效果)
        if 效果词:
            标签 = ", ".join((_取镜头光效项(x) or {}).get("label", x) for x in 效果)
            行.append("- 镜头效果：%s — %s" % (标签, 效果词))

        预设id = _键(风格, "风格预设", "stylePreset", "预设", 默认="")
        预设 = _取预设(预设id, 自定义预设)
        if 预设:
            if 预设.get("keywords"):
                行.append("- Style preset: %s — %s" % (预设["label"], 预设["keywords"]))
            if 预设.get("prompt"):
                行.append("- 预设风格：%s — %s" % (预设["label"], 预设["prompt"]))
        else:
            参考 = _键(风格, "参考图风格", "stylePrompt", 默认="")
            if 参考:
                try:
                    识别 = json.loads(参考) if isinstance(参考, str) else dict(参考)
                    映射 = [("artStyle", "参考图画风"), ("colorPalette", "参考图色调"),
                            ("styleKeywords", "参考图关键词"), ("mood", "参考图氛围")]
                    for k, 中文 in 映射:
                        v = _扁平(识别.get(k))
                        if v:
                            行.append("- %s：%s" % (中文, v))
                except Exception:
                    行.append("- AI识别风格：%s" % _扁平(参考))
            else:
                画风 = _扁平(_键(风格, "画风", "artStyle", 默认=""))
                色调 = _扁平(_键(风格, "色调", "colorPalette", 默认=""))
                if 画风:
                    行.append("- 画风：%s" % 画风)
                if 色调:
                    行.append("- 色调：%s" % 色调)

        时代 = _扁平(_键(风格, "时代背景", "时代/世界观背景", "timeSetting", 默认=""))
        if 时代:
            行.append("- 时代/世界观背景：%s" % 时代)

        补充 = _扁平(_键(风格, "补充", "additionalNotes", 默认=""))
        if 补充:
            行.append("- 补充：%s" % 补充)

        return "\n".join(行)

    @staticmethod
    def _条目(项, 序号):
        名 = _键(项, "name", "名称", "名", "中文名", "角色名", "场景名", 默认="")
        号 = _键(项, "id", "编号", "ID", "序号", 默认="")
        描 = _键(项, "description", "描述", "外观", "设定", "特征", "简介", 默认="")
        return (str(名 or ("未命名%d" % 序号)), str(号 or 序号), str(描 or ""))

    # ---------------------------------------------------------------- 单格 --
    def 单格(self, 景别="Medium shot", 主体与动作="", 环境="", 时间光照="", 风格标签="",
            排除词="", 描述="", 宫格=9, 限词=True):
        """
        六段公式（飞彩三份 Gem 完全一致）：

            [景别] + [主体与动作] + [环境] + [时间/光照] + [风格标签] + [排除词]

        返回 dict：
            description   中文，供分镜面板显示（九宫格 30-50 字；四宫格/25宫格 10-20 字）
            time_setting  英文时间/光照短语，且必须出现在 prompt_text 里（C8）
            prompt_text   英文，逗号分隔的关键词短语，25 词 ±5（C3），硬上限 40 词（H9）
            + 景别/景别中文/词数/描述字数/排除词/被剥离/警告 等诊断字段

        中文段一律不写进 prompt_text（C4「英文提示词不写中文」）；含中文的英文段会被剔除并在
        「警告」里点名，绝不静默。
        """
        警告 = []
        被剥离 = []

        # 1) 先过 C5/C6：任何一段里都不许留元指令
        段 = {}
        for 名, 值 in (("景别", 景别), ("主体与动作", 主体与动作), ("环境", 环境),
                       ("时间光照", 时间光照), ("风格标签", 风格标签)):
            if 值 and 扫描元指令(值):
                被剥离.extend(扫描元指令(值))
            段[名] = 洗元指令(值)

        段["景别"] = 段["景别"] or "Medium shot"
        段["时间光照"] = _时间英文(段["时间光照"])

        排除, 排除剥离 = _清排除词(排除词)
        被剥离.extend(排除剥离)

        # 2) 英文 prompt_text：只收英文段
        英文段 = []
        中文段 = []
        for 名 in ("景别", "主体与动作", "环境", "时间光照", "风格标签"):
            v = 段[名]
            if not v:
                continue
            if _有中文(v):
                中文段.append("%s=%s" % (名, v))
                continue
            英文段.append(v)
        if 中文段:
            警告.append("含中文段已从英文 prompt_text 剔除：" + "；".join(中文段))

        txt = ", ".join(英文段)
        if 排除:
            txt = (txt + ", " + 排除).strip(", ")

        # 3) C3/H9 词数锁
        if 限词:
            if _词数(txt) > 30 and 段["环境"] and not _有中文(段["环境"]):
                txt = ", ".join([x for x in 英文段 if x != 段["环境"]])
                if 排除:
                    txt = (txt + ", " + 排除).strip(", ")
                警告.append("超 30 词，已按公式顺序丢掉 [环境] 段")
            标签词 = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-\.]*", 段["风格标签"])
            if _词数(txt) > 30 and len(标签词) > 5:
                短标签 = " ".join(标签词[:5])
                txt = re.sub(re.escape(段["风格标签"]), 短标签, txt)
                警告.append("仍超 30 词，[风格标签] 已截到 5 词")
            if _词数(txt) > 40:                      # H9 硬上限
                词 = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-\.]*", txt)
                txt = ", ".join(词[:40])
                警告.append("触发 H9 硬上限，prompt_text 截到 40 词")

        n = _词数(txt)
        if n > 30:
            警告.append("prompt_text 偏长（%d 词 > 30）" % n)
        elif n < 20 and n > 0:
            警告.append("prompt_text 偏短（%d 词 < 20）" % n)

        # 4) description（中文）
        低, 高 = _描述字数带(宫格)
        描 = str(描述 or "").strip()
        if 描 and 扫描元指令(描):
            被剥离.extend(扫描元指令(描))
            描 = 洗元指令(描)
        if not 描:
            骨架 = [_景别中文(段["景别"])]
            主体中文 = 段["主体与动作"] if _有中文(段["主体与动作"]) else ""
            if 主体中文:
                骨架.append(主体中文)
            elif 段["主体与动作"]:
                骨架.append(段["主体与动作"])
            if 段["环境"] and _有中文(段["环境"]):
                骨架.append(段["环境"])
            描 = "，".join(骨架)
        # 中文之间不留空格（飞彩 description 是紧凑中文），但拉丁词之间的空格要留住，
        # 否则「特写，Ye Yun glares」会被压成「特写，YeYunglares」（实测踩过）。
        描 = re.sub(r"(?<=[\u3400-\u9fff，、。！？：；（）《》“”])\s+", "", 描)
        描 = re.sub(r"\s+(?=[\u3400-\u9fff，、。！？：；（）《》“”])", "", 描)
        描 = re.sub(r"\s+", " ", 描).strip()
        if _字数(描) > 高:
            描 = 描[:高 - 1] + "…"
            警告.append("description 超 %d 字，已截断" % 高)
        elif _字数(描) < 低 and 低 > 1:
            警告.append("description 偏短（%d 字 < %d）" % (_字数(描), 低))

        return {
            "description": 描,
            "time_setting": 段["时间光照"],
            "prompt_text": txt,
            "景别": 段["景别"],
            "景别中文": _景别中文(段["景别"]),
            "词数": n,
            "描述字数": _字数(描),
            "排除词": 排除,
            "被剥离": 被剥离,
            "警告": 警告,
        }

    # ---------------------------------------------------------------- 宫格 --
    def 宫格(self, 数量=9, 主题="", 主体英文="", 环境="", 时间光照="", 风格标签="",
            排除词="", 分段描述=None, 分段英文=None, 分段环境=None, 分段时间=None):
        """
        宫格节奏 + 景别配额，逐格产出 单格() 的结果。

            9  → Beat Board 节拍板  建立(1-2) → 升级(3-5) → 高潮(6-7) → 收束(8-9)
                 景别配额：1 大远景 + 3 中景 + 2 特写 + 3 自由
            4  → Sequence Board 序列板  引入(1) → 发展(2) → 转折/高潮(3) → 余韵(4)
                 景别：至少两种不同
            25 → 完整细致分镜  起承转合 × 5 轮（对应 5行×5列），追求最大化景别多样性

        返回 list[dict]，每项在 单格() 的字段上再加 格 / 节拍 / 节奏段 / 轮。
        主题 只做中文兜底；英文 prompt_text 由 主体英文 / 分段英文 / 风格标签 撑起来。
        """
        数量 = int(数量)
        if 数量 not in 宫格规范:
            raise ValueError("影匠只支持 4 / 9 / 25 宫格（飞彩 C2 同此），收到：%r" % (数量,))

        规范 = 宫格规范[数量]
        节奏 = 规范["节奏"]
        景别 = {4: _景别_4, 9: _景别_9, 25: _景别_25}[数量]

        出 = []
        for i in range(数量):
            节拍 = 节奏[i]
            轮 = (i // 5) + 1 if 数量 == 25 else 1
            描述 = (分段描述[i] if 分段描述 and i < len(分段描述) else "")
            if not 描述:
                描述 = ("%s，%s" % (主题, 节拍)) if 主题 else ""
            英 = (分段英文[i] if 分段英文 and i < len(分段英文) else "")
            if not 英:
                英 = 主体英文 or 节拍英文.get(节拍, "")
            环 = (分段环境[i] if 分段环境 and i < len(分段环境) else 环境)
            时 = (分段时间[i] if 分段时间 and i < len(分段时间) else 时间光照)

            格 = self.单格(景别=景别[i], 主体与动作=英, 环境=环, 时间光照=时,
                           风格标签=风格标签, 排除词=排除词, 描述=描述, 宫格=数量)
            格.update({"格": i + 1, "节拍": 节拍, "节奏段": 节拍, "轮": 轮,
                       "景别要求": 规范["景别要求"], "板型": 规范["板型"]})
            出.append(格)
        return 出

    # ------------------------------------------------------- 身份锁（附赠） --
    @staticmethod
    def 身份锁(角色名=""):
        """
        飞彩两条身份锁英文原文（模块 70308 变量 c 与函数 d），逐字。
        c 给「第一张参考图就是角色定妆照」用；d 给「补充身份参考」用。
        """
        主 = ("[IDENTITY LOCK]\nThe FIRST reference image is the user-provided character reference. "
              "You MUST preserve EXACTLY: facial features (eye shape, nose, mouth, jaw), skin tone, "
              "hair color, hair style. Render the subject in our standardized three-view specification "
              "format but DO NOT invent or alter any facial feature. Treat this reference as the identity "
              "source of truth.")
        if not 角色名:
            return 主
        return ("【🔒 IDENTITY LOCK · %s】This is a supplemental identity reference. You MUST preserve "
                "EXACTLY: facial features (eye shape, nose, mouth, jaw), skin tone, hair color, and hair "
                "style. Render in our standardized three-view format but DO NOT invent or alter any facial "
                "feature. When a parent turnaround is also attached, keep its composition and layout "
                "unchanged." % 角色名)

    # 无文字铁律（飞彩模块 1079 函数 h，逐字）
    无文字铁律 = ("\n\n⛔ STRICT NO-TEXT RULE: Do NOT render any text, words, letters, numbers, dialogue, "
                  "speech bubbles, captions, subtitles, labels, watermarks, or typography of any kind in the "
                  "image. Quoted dialogue in descriptions is acting direction only — convey it through facial "
                  "expressions and body language, NEVER as visible text. Output pure visual artwork with zero "
                  "written content.")

    # ---------------------------------------------------------------- 检查 --
    def 检查(self, 提示词, 只要问题=False):
        """
        约束检查器：H1-H10 / C1-C8 / QC1-QC10，共 28 条。

        入参可以是：
            str                        单条 prompt_text（无结构 → 结构类规则记「没测」）
            dict                       单格（含 prompt_text/description/景别/time_setting…）
            {"shots":[...]}            飞彩的宫格 JSON
            list[dict]                 镜头数组

        返回 list[dict]：{"编号","级别","名称","结果","说明","位置"}
        结果 ∈ {"通过","失败","没测"} —— 「没测」是 honest 状态：缺字段就不假装通过。
        只要问题=True 时只返回 失败 / 没测 的行。
        """
        结构 = self._规整(提示词)
        镜头 = 结构["shots"]
        条 = []
        条.extend(self._查H(结构, 镜头))
        条.extend(self._查C(结构, 镜头))
        条.extend(self._查QC(结构, 镜头))
        if 只要问题:
            return [x for x in 条 if x["结果"] != "通过"]
        return 条

    @staticmethod
    def _规整(提示词):
        if isinstance(提示词, str):
            return {"raw": 提示词, "有结构": False, "shots": [{"prompt_text": 提示词}],
                    "布局": "", "关键情节点": []}
        if isinstance(提示词, dict):
            if isinstance(提示词.get("shots"), list):
                return {"raw": "", "有结构": True, "shots": 提示词["shots"],
                        "布局": _键(提示词, "grid_layout", "布局", 默认=""),
                        "关键情节点": _键(提示词, "关键情节点", "keyPoints", 默认=[]) or []}
            return {"raw": "", "有结构": True, "shots": [提示词],
                    "布局": "", "关键情节点": []}
        if isinstance(提示词, (list, tuple)):
            return {"raw": "", "有结构": True, "shots": list(提示词),
                    "布局": "", "关键情节点": []}
        raise TypeError("检查() 只吃 str / dict / list，收到：%r" % type(提示词))

    @staticmethod
    def _行(编号, 级别, 名称, 结果, 说明="", 位置=0):
        return {"编号": 编号, "级别": 级别, "名称": 名称, "结果": 结果, "说明": 说明, "位置": 位置}

    # ---- H1-H10
    def _查H(self, 结构, 镜头):
        出 = []
        文本s = [str(_键(s, "prompt_text", "提示词", 默认="") or "") for s in 镜头]
        整体文 = "\n".join(文本s)
        全部文 = 整体文 + "\n" + "\n".join(str(_键(s, "description", "描述", 默认="") or "") for s in 镜头)

        # H1 严禁文字/序号/时间码/字幕
        命中 = []
        for i, t in enumerate(文本s, 1):
            h = [w for w in 文字污染词 if w.lower() in t.lower()]
            if h:
                命中.append("第 %d 格：%s" % (i, "、".join(h)))
        出.append(self._行("H1", "硬约束", "画面内不得有文字/序号/时间码/字幕", "失败" if 命中 else "通过",
                          "；".join(命中), 0))

        # H2 无意义句式
        废话 = ["a scene showing", "there is a", "an image of", "this is a", "depicts a",
                "画面展示", "这是一张", "图中是"]
        命中 = ["第 %d 格：%s" % (i, w) for i, t in enumerate(文本s, 1) for w in 废话 if w in t.lower()]
        出.append(self._行("H2", "硬约束", "禁用 A scene showing / There is a 等句式",
                          "失败" if 命中 else "通过", "；".join(命中), 0))

        # H3 空洞描述
        空 = ["戏剧性的场景", "美丽的画面", "震撼的画面", "精彩瞬间", "唯美画面",
              "dramatic scene", "beautiful scene", "stunning image", "epic scene", "amazing scene"]
        命中 = ["第 %d 格：%s" % (i, w) for i, t in enumerate(文本s, 1) for w in 空 if w in t.lower()]
        命中 += ["第 %d 格 description：%s" % (i, w) for i, s in enumerate(镜头, 1)
                 for w in 空 if w in str(_键(s, "description", "描述", 默认="") or "").lower()]
        出.append(self._行("H3", "硬约束", "禁止空洞描述", "失败" if 命中 else "通过", "；".join(命中), 0))

        # H4 JSON 模式下不得有 markdown/解释
        if not 结构["有结构"]:
            出.append(self._行("H4", "硬约束", "JSON 模式只输出 JSON", "没测", "入参是裸字符串，无法判定是否 JSON 模式"))
        else:
            bad = "```" in 结构["raw"] if 结构["raw"] else False
            出.append(self._行("H4", "硬约束", "JSON 模式只输出 JSON", "失败" if bad else "通过",
                              "检测到 markdown 代码块标记" if bad else ""))

        # H5 每格一个视觉焦点（需要结构化字段，否则没测）
        焦点 = [_键(s, "焦点数", "focusCount", 默认=None) for s in 镜头]
        if all(x is None for x in 焦点):
            出.append(self._行("H5", "硬约束", "每格有且仅有一个视觉焦点", "没测",
                              "镜头里没有『焦点数』字段；单靠 prompt_text 无法可靠数焦点，不猜"))
        else:
            坏 = ["第 %d 格：焦点数 %s" % (i, x) for i, x in enumerate(焦点, 1) if x is not None and int(x) != 1]
            出.append(self._行("H5", "硬约束", "每格有且仅有一个视觉焦点", "失败" if 坏 else "通过", "；".join(坏)))

        # H6 运动元素 ≤ 3
        运动词 = ["walk", "walks", "walking", "run", "runs", "running", "turn", "turns", "turning",
                 "jump", "jumps", "jumping", "fall", "falls", "falling", "fly", "flies", "flying",
                 "drive", "drives", "driving", "fight", "fights", "fighting", "dance", "dances", "dancing",
                 "reach", "reaches", "reaching", "raise", "raises", "raising", "swing", "swings", "swinging",
                 "throw", "throws", "throwing", "sprint", "sprints", "sprinting", "ride", "rides", "riding",
                 "explode", "explodes", "exploding", "spin", "spins", "spinning", "kneel", "kneels", "kneeling",
                 "climb", "climbs", "climbing", "runs toward", "turns away"]
        坏 = []
        for i, t in enumerate(文本s, 1):
            low = re.sub(r"motion blur|speed lines|dynamic movement|directional blur", "", t.lower())
            数 = sum(1 for w in 运动词 if re.search(r"\b" + re.escape(w) + r"\b", low))
            if 数 > 3:
                坏.append("第 %d 格：%d 个运动元素" % (i, 数))
        出.append(self._行("H6", "硬约束", "单画面不超过 3 个运动元素", "失败" if 坏 else "通过", "；".join(坏)))

        # H7 风格标签必须来自参考图
        参考 = [_键(s, "参考图风格标签", "referenceStyleTags", 默认=None) for s in 镜头]
        if all(x is None for x in 参考):
            出.append(self._行("H7", "硬约束", "风格标签必须取自参考图，不得臆造", "没测",
                              "镜头里没有『参考图风格标签』字段，无从比对"))
        else:
            风格味 = ("style", "realism", "render", "painting", "anime", "cinematic",
                    "watercolor", "comic", "cyberpunk", "ink", "oil", "ghibli", "pixel")
            坏 = []
            for i, s in enumerate(镜头, 1):
                allow = 参考[i - 1]
                if allow is None:
                    continue
                allow = [str(a).strip().lower() for a in allow]
                for 段 in [x.strip() for x in re.split(r"[,，]", 文本s[i - 1].lower()) if x.strip()]:
                    if any(段 in a or a in 段 for a in allow):
                        continue
                    if any(k in 段 for k in 风格味):
                        坏.append("第 %d 格：%s 不在参考图标签里" % (i, 段))
            出.append(self._行("H7", "硬约束", "风格标签必须取自参考图，不得臆造",
                              "失败" if 坏 else "通过", "；".join(坏)))

        # H8 description 不超过上限（按宫格数取字数带：9 宫格 30-50，其余 ≤30）
        低, 高 = _描述字数带(len(镜头) if len(镜头) in 宫格规范 else 9)
        bad = []
        for i, s in enumerate(镜头, 1):
            描 = str(_键(s, "description", "描述", 默认="") or "")
            if 描 and _字数(描) > 高:
                bad.append("第 %d 格：%d 字 > %d" % (i, _字数(描), 高))
        出.append(self._行("H8", "硬约束", "中文 description 不超过上限（九宫格版 30-50）",
                          "失败" if bad else "通过", "；".join(bad)))

        # H9 prompt_text 不超过 40 词
        bad = ["第 %d 格：%d 词" % (i, _词数(t)) for i, t in enumerate(文本s, 1) if _词数(t) > 40]
        出.append(self._行("H9", "硬约束", "英文 prompt_text 不超过 40 词", "失败" if bad else "通过", "；".join(bad)))

        # H10 NSFW
        nsfw = ["nude", "nudity", "naked", "nsfw", "porn", "explicit sex", "genital",
                "裸体", "色情", "露点", "全裸"]
        命中 = ["第 %d 格：%s" % (i, w) for i, t in enumerate(文本s, 1) for w in nsfw if w in t.lower()]
        出.append(self._行("H10", "硬约束", "不得包含 NSFW 内容", "失败" if 命中 else "通过", "；".join(命中)))
        return 出

    # ---- C1-C8
    def _查C(self, 结构, 镜头):
        出 = []
        n = len(镜头)
        文本s = [str(_键(s, "prompt_text", "提示词", 默认="") or "") for s in 镜头]

        # C1 标准 JSON
        if not 结构["有结构"]:
            出.append(self._行("C1", "约束", "标准 JSON，无 Markdown 废话", "没测", "入参是裸字符串"))
        else:
            bad = bool(结构["raw"]) and "```" in 结构["raw"]
            出.append(self._行("C1", "约束", "标准 JSON，无 Markdown 废话", "失败" if bad else "通过",
                              "检测到 ``` 代码块" if bad else ""))

        # C2 shots 必须是 4 / 9 / 25
        if not 结构["有结构"]:
            出.append(self._行("C2", "约束", "shots 数组必须是 4 / 9 / 25 个", "没测", "入参是裸字符串"))
        elif n not in (4, 9, 25):
            出.append(self._行("C2", "约束", "shots 数组必须是 4 / 9 / 25 个", "失败", "实际 %d 个" % n))
        else:
            布局 = str(结构["布局"] or "")
            期望 = {"2x2": 4, "3x3": 9, "5x5": 25}.get(布局.replace("×", "x").replace(" ", ""))
            if 期望 and 期望 != n:
                出.append(self._行("C2", "约束", "shots 数组必须是 4 / 9 / 25 个", "失败",
                                  "布局 %s 应为 %d 格，实际 %d" % (布局, 期望, n)))
            else:
                出.append(self._行("C2", "约束", "shots 数组必须是 4 / 9 / 25 个", "通过", "%d 格" % n))

        # C3 25 词 ±5
        if any(not t for t in 文本s):
            出.append(self._行("C3", "约束", "每个 prompt_text 约 25 词（±5）", "没测", "有镜头缺 prompt_text"))
        else:
            bad = ["第 %d 格：%d 词" % (i, _词数(t)) for i, t in enumerate(文本s, 1)
                   if not (20 <= _词数(t) <= 30)]
            出.append(self._行("C3", "约束", "每个 prompt_text 约 25 词（±5）", "失败" if bad else "通过", "；".join(bad)))

        # C4 无长难句 / 无意义句式
        废话 = ["a scene showing", "there is a", "an image of", "this is a"]
        bad = ["第 %d 格：%s" % (i, w) for i, t in enumerate(文本s, 1) for w in 废话 if w in t.lower()]
        for i, t in enumerate(文本s, 1):
            for 句 in re.split(r"[.;。；]", t):
                if _词数(句) > 25:
                    bad.append("第 %d 格：单句 %d 词" % (i, _词数(句)))
        出.append(self._行("C4", "约束", "禁用长难句与无意义句式", "失败" if bad else "通过", "；".join(bad)))

        # C5 纯视觉原则（硬）
        命中 = []
        for i, s in enumerate(镜头, 1):
            h = 扫描元指令(文本s[i - 1])
            if h:
                命中.append("第 %d 格：%s" % (i, "、".join(h)))
        出.append(self._行("C5", "约束", "纯视觉原则：prompt_text 内不得有指令性文字",
                          "失败" if 命中 else "通过", "；".join(命中[:6])))

        # C6 去水印（硬）
        坏2 = []
        for i, t in enumerate(文本s, 1):
            if re.search(r"\b(shot|frame|panel|scene)\s*#?\s*\d+", t, re.I) or re.search(r"(分镜\s*\d+|角标|序号)", t):
                坏2.append("第 %d 格" % i)
        出.append(self._行("C6", "约束", "去水印：不得有分镜编号/角落标记/序号标注",
                          "失败" if 坏2 else "通过", "；".join(坏2)))

        # C7 description 必须是中文
        缺 = [i for i, s in enumerate(镜头, 1) if not str(_键(s, "description", "描述", 默认="") or "").strip()]
        if len(缺) == len(镜头):
            出.append(self._行("C7", "约束", "description 必须为中文且简明", "没测", "所有镜头都没有 description"))
        else:
            bad = ["第 %d 格：非中文" % i for i, s in enumerate(镜头, 1)
                   if str(_键(s, "description", "描述", 默认="") or "").strip()
                   and not _有中文(_键(s, "description", "描述", 默认=""))]
            低, 高 = _描述字数带(n if n in 宫格规范 else 9)
            for i, s in enumerate(镜头, 1):
                描 = str(_键(s, "description", "描述", 默认="") or "").strip()
                if 描 and not (低 <= _字数(描) <= 高):
                    bad.append("第 %d 格：%d 字（应 %d-%d）" % (i, _字数(描), 低, 高))
            出.append(self._行("C7", "约束", "description 必须为中文且简明", "失败" if bad else "通过", "；".join(bad)))

        # C8 time_setting 英文且融入 prompt_text
        缺 = [i for i, s in enumerate(镜头, 1) if not str(_键(s, "time_setting", "时间设置", 默认="") or "").strip()]
        if len(缺) == len(镜头):
            出.append(self._行("C8", "约束", "time_setting 必须英文且融入 prompt_text", "没测", "所有镜头都没有 time_setting"))
        else:
            bad = []
            for i, s in enumerate(镜头, 1):
                ts = str(_键(s, "time_setting", "时间设置", 默认="") or "").strip()
                if not ts:
                    bad.append("第 %d 格：缺 time_setting" % i)
                    continue
                if _有中文(ts):
                    bad.append("第 %d 格：time_setting 含中文（%s）" % (i, ts))
                if ts.lower() not in 文本s[i - 1].lower():
                    bad.append("第 %d 格：time_setting 未融入 prompt_text" % i)
            出.append(self._行("C8", "约束", "time_setting 必须英文且融入 prompt_text", "失败" if bad else "通过", "；".join(bad)))
        return 出

    # ---- QC1-QC10
    def _查QC(self, 结构, 镜头):
        出 = []
        n = len(镜头)
        文本s = [str(_键(s, "prompt_text", "提示词", 默认="") or "") for s in 镜头]

        # QC1 叙事连贯
        段 = [_键(s, "节奏段", "节拍", "beat", 默认="") for s in 镜头]
        if not any(段):
            出.append(self._行("QC1", "自检", "叙事连贯性：是否讲完一个完整故事弧", "没测",
                              "镜头里没有『节奏段/节拍』字段，判断不了弧线"))
        else:
            missing = [i for i, d in enumerate(段, 1) if not d]
            种 = len(set(x for x in 段 if x))
            需要 = {4: 3, 9: 4, 25: 3}.get(n, 3)
            if missing:
                出.append(self._行("QC1", "自检", "叙事连贯性：是否讲完一个完整故事弧", "没测",
                                  "第 %s 格缺节奏段" % missing))
            elif 种 < 需要:
                出.append(self._行("QC1", "自检", "叙事连贯性：是否讲完一个完整故事弧", "失败",
                                  "只有 %d 种节奏段，至少需要 %d 种" % (种, 需要)))
            else:
                出.append(self._行("QC1", "自检", "叙事连贯性：是否讲完一个完整故事弧", "通过", "%d 种节奏段" % 种))

        # QC2 景别多样性
        景 = [_键(s, "景别", "shot_type", 默认="") for s in 镜头]
        if not any(景):
            出.append(self._行("QC2", "自检", "景别多样性：不得连续 3 个相同景别", "没测", "镜头里没有『景别』字段"))
        else:
            坏 = []
            for i in range(len(景) - 2):
                if 景[i] and 景[i] == 景[i + 1] == 景[i + 2]:
                    坏.append("第 %d-%d 格连续相同（%s）" % (i + 1, i + 3, 景[i]))
            出.append(self._行("QC2", "自检", "景别多样性：不得连续 3 个相同景别", "失败" if 坏 else "通过", "；".join(坏)))

        # QC3 节奏呼吸
        if not any(段):
            出.append(self._行("QC3", "自检", "节奏呼吸：紧张与舒缓交替", "没测", "缺节奏段，无法判断强度曲线"))
        else:
            强 = [节拍强度.get(str(x), 0) for x in 段]
            上升 = any(强[i + 1] > 强[i] for i in range(len(强) - 1))
            下降 = any(强[i + 1] < 强[i] for i in range(len(强) - 1))
            if not 上升 and not 下降:
                出.append(self._行("QC3", "自检", "节奏呼吸：紧张与舒缓交替", "失败", "强度曲线是平的"))
            elif not 下降:
                出.append(self._行("QC3", "自检", "节奏呼吸：紧张与舒缓交替", "失败", "一直往上顶，没有回落"))
            else:
                出.append(self._行("QC3", "自检", "节奏呼吸：紧张与舒缓交替", "通过", "强度 %s" % 强))

        # QC4 角色一致
        档案 = [_键(s, "角色档案", "characters", 默认=None) for s in 镜头]
        if all(x is None for x in 档案):
            出.append(self._行("QC4", "自检", "角色一致：同一角色跨格外貌一致", "没测", "镜头里没有『角色档案』字段"))
        else:
            合并 = {}
            坏 = []
            for i, d in enumerate(档案, 1):
                if not isinstance(d, dict):
                    continue
                for k, v in d.items():
                    if k in 合并 and str(合并[k]) != str(v):
                        坏.append("角色 %s：第 %d 格与前面不一致" % (k, i))
                    合并.setdefault(k, v)
            出.append(self._行("QC4", "自检", "角色一致：同一角色跨格外貌一致", "失败" if 坏 else "通过", "；".join(坏)))

        # QC5 光影逻辑（同场景光源方向一致）
        场景 = [_键(s, "场景", "scene", 默认="") for s in 镜头]
        if not any(场景):
            出.append(self._行("QC5", "自检", "光影逻辑：同场景光源方向一致", "没测",
                              "镜头里没有『场景』字段，分不出「同场景」；且飞彩允许不同分镜用不同时间/光照"))
        else:
            组 = {}
            for i, s in enumerate(镜头):
                组.setdefault(场景[i], set()).add(str(_键(s, "time_setting", "时间设置", 默认="") or ""))
            坏 = ["场景 %s：光照 %s" % (k, "、".join(sorted(v))) for k, v in 组.items() if len(v) > 1]
            出.append(self._行("QC5", "自检", "光影逻辑：同场景光源方向一致", "失败" if 坏 else "通过", "；".join(坏)))

        # QC6 情绪弧线
        情 = [_键(s, "情绪", "emotion", 默认="") for s in 镜头]
        if not any(情):
            出.append(self._行("QC6", "自检", "情绪弧线：首尾有明确感情变化", "没测", "镜头里没有『情绪』字段"))
        else:
            有 = [x for x in 情 if x]
            if len(set(有)) < 2:
                出.append(self._行("QC6", "自检", "情绪弧线：首尾有明确感情变化", "失败", "情绪没有变化"))
            elif 有[0] == 有[-1]:
                出.append(self._行("QC6", "自检", "情绪弧线：首尾有明确感情变化", "失败",
                                  "首尾情绪都是 %s" % 有[0]))
            else:
                出.append(self._行("QC6", "自检", "情绪弧线：首尾有明确感情变化", "通过", "%s → %s" % (有[0], 有[-1])))

        # QC7 信息完整
        点 = 结构["关键情节点"]
        if not 点:
            出.append(self._行("QC7", "自检", "信息完整：关键情节点都被覆盖", "没测", "没有给『关键情节点』清单"))
        else:
            全部 = "\n".join(文本s) + "\n" + "\n".join(str(_键(s, "description", "描述", 默认="") or "") for s in 镜头)
            漏 = [str(p) for p in 点 if str(p) not in 全部]
            出.append(self._行("QC7", "自检", "信息完整：关键情节点都被覆盖", "失败" if 漏 else "通过",
                              "漏掉：%s" % "、".join(漏)))

        # QC8 风格统一
        签名 = self._风格签名()
        if not 签名:
            出.append(self._行("QC8", "自检", "风格统一：所有格属于同一风格体系", "没测", "词表为空"))
        else:
            命中 = []
            for t in 文本s:
                low = t.lower()
                中 = [名 for 名, 词 in 签名 if sum(1 for w in 词 if w in low) >= 2]
                命中.append(中)
            并 = set()
            for x in 命中:
                并.update(x)
            if len(并) > 1:
                出.append(self._行("QC8", "自检", "风格统一：所有格属于同一风格体系", "失败",
                                  "同时命中多套风格：%s" % "、".join(sorted(并))))
            elif not 并:
                出.append(self._行("QC8", "自检", "风格统一：所有格属于同一风格体系", "没测",
                                  "没有任何一格能匹配到已知风格签名（可能是自定义/参考图风格）"))
            else:
                出.append(self._行("QC8", "自检", "风格统一：所有格属于同一风格体系", "通过", "命中「%s」" % list(并)[0]))

        # QC9 无废话
        bad = []
        for i, t in enumerate(文本s, 1):
            if _词数(t) < 5:
                bad.append("第 %d 格：只有 %d 词，没有有效叙事信息" % (i, _词数(t)))
            if not re.search(r"[A-Za-z]{3,}", t):
                bad.append("第 %d 格：prompt_text 里没有实质英文内容" % i)
        出.append(self._行("QC9", "自检", "无废话：每个镜头都有明确叙事目的", "失败" if bad else "通过", "；".join(bad)))

        # QC10 无文字污染
        命中 = []
        for i, t in enumerate(文本s, 1):
            h = [w for w in 文字污染词 if w.lower() in t.lower()]
            if h:
                命中.append("第 %d 格：%s" % (i, "、".join(h)))
        出.append(self._行("QC10", "自检", "无文字污染：画面不含文字/编号/水印", "失败" if 命中 else "通过", "；".join(命中)))
        return 出

    @staticmethod
    def _风格签名():
        """每个预设抽「只属于它自己」的关键词，避免 3d-xianxia 与 3d-cg 互相串味。"""
        全部 = []
        for p in 预设表:
            词 = [w.strip().lower() for w in p["keywords"].split(",") if w.strip()]
            全部.append([p["label"], 词])
        频 = {}
        for _, 词 in 全部:
            for w in 词:
                频[w] = 频.get(w, 0) + 1
        出 = []
        for 名, 词 in 全部:
            独 = [w for w in 词 if 频.get(w) == 1]
            if 独:
                出.append((名, 独))
        return 出

    # ------------------------------------------------------------ 结果统计 --
    @staticmethod
    def 摘要(结果列表):
        d = {"通过": 0, "失败": 0, "没测": 0}
        for x in 结果列表:
            d[x["结果"]] = d.get(x["结果"], 0) + 1
        return d

    # -------------------------------------------------------- 与既有模块互通 --
    @staticmethod
    def 从风格库(键):
        """
        把 风格库.py 的风格条目翻成 整体() 认得的设定 dict，方便 导演.py / 引擎.py 直接接。
        （风格库的键名与飞彩 23 风格预设**不是**同一套，这里只做字段搬运，不做映射。）
        """
        风格库, 错 = _装模块("风格库.py", "风格库")
        if 风格库 is None:
            raise RuntimeError("装不上 风格库.py：" + 错)
        风 = 风格库.取(键)
        if not 风:
            raise KeyError("风格库 里没有：%s" % 键)
        return {"style": {
            "画幅": "16:9",
            "画质": _键(风, "画质", 默认="4K"),
            "视觉风格": "",
            "光影氛围": "",
            "镜头效果": [],
            "风格预设": "",
            "画风": _键(风, "风格", 默认=""),
            "色调": _键(风, "配色", 默认=""),
            "补充": _键(风, "光线", 默认=""),
        }}


#: 模块级门面
编译 = _编译器()

#: 模块级别名（导演.py / 引擎.py 那种「直接 from 编译器 import 整体」也能用）
整体 = 编译.整体
单格 = 编译.单格
宫格 = 编译.宫格
检查 = 编译.检查


# ============================================================================
# 六、自测
# ============================================================================

def _样例设定():
    return {
        "characters": [
            {"id": "C1", "name": "叶云", "description": "十九岁少年，剑眉星目，玄色劲装，束发银冠"},
            {"id": "C2", "name": "苏晚", "description": "青衣女子，长发及腰，眉心一点朱砂"},
        ],
        "scenes": [
            {"id": "S1", "name": "断魂崖", "description": "万丈绝壁，云雾翻涌，崖顶一株枯松"},
            {"id": "S1v", "name": "断魂崖·多角度", "subType": "scene-view", "description": "四视图，不应出现在清单里"},
        ],
        "props": [{"id": "P1", "name": "青锋剑", "description": "三尺青锋，剑身有细密雷纹"}],
        "style": {
            "aspectRatio": "16:9",
            "renderType": "3d-cg",
            "resolution": "4K",
            "visualStyle": "cinematic-realism",
            "lightingMood": "auto",
            "lensEffects": ["shallow-dof", "film-grain"],
            "stylePreset": "3d-xianxia",
            "timeSetting": "东方玄幻架空",
            "additionalNotes": "全片保持冷调高对比",
        },
    }


_英文样例 = [
    "Ye Yun draws his long sword slowly at the cliff edge",
    "Su Wan steps back with widened eyes and parted lips",
    "the blade ignites with blue lightning and rising sparks",
    "storm clouds churn above the broken peak at dusk",
    "Ye Yun lunges forward in a low stance and strikes",
    "Su Wan raises both hands to shield her pale face",
    "the sword strike splits the ancient pine in two",
    "embers drift down through the cold mist and settle",
    "the two stand apart in the settling cold silence",
]

# 与 _英文样例 同序的中文 description，每格 30-50 字（对齐 Gem 九宫格 C7 字数带）
_中文样例 = [
    "断魂崖顶狂风呼啸，叶云拔剑出鞘，玄色衣袍翻飞，眼神冷冽，杀气逼人",
    "苏晚后退半步，睁大双眼望着断魂崖边那道剑光，指尖微微发颤，呼吸急促",
    "青锋剑骤然爆出幽蓝雷光，电弧顺着剑脊游走，照亮半张侧脸，映出冷光",
    "乌云在断裂的山脊上方翻涌，断魂崖投下巨大的阴影，雷声由远及近，风势更急",
    "叶云压低身形向前突进，长剑横扫，衣摆被气流撕开，脚下碎石飞溅",
    "苏晚双手抬起护住苍白的面颊，发丝被剑气吹得向后飞散，眼角泛红",
    "剑锋劈开崖顶那株古松，木屑与松针在冷雾中炸开，断口整齐如镜，余势未消",
    "火星顺着风势缓缓落下，穿过冷雾，落在焦黑的岩石上，明灭不定，旋即熄灭",
    "两人在断魂崖顶相隔数丈默然对立，风停在剑锋之间，谁都没有先动，只剩呼吸声",
]


def 自测():
    """真跑真测。返回进程退出码：全通过 0，有失败 1。"""
    计 = {"通过": 0, "失败": 0, "没测": 0}
    失败明细 = []

    def 记(名, 条件, 说明=""):
        计["通过" if 条件 else "失败"] += 1
        if not 条件:
            失败明细.append("%s —— %s" % (名, 说明))
        return 条件

    print("=" * 72)
    print("影匠 · 提示词编译器 自测")
    print("=" * 72)

    # ---------------- 0. 模块装载
    风格库, 错 = _装模块("风格库.py", "风格库")
    记("_装模块(风格库.py)", 风格库 is not None, 错)
    一致性, 错2 = _装模块("一致性.py", "一致性")
    记("_装模块(一致性.py)", 一致性 is not None, 错2)

    # ---------------- 1. 词表规模（与飞彩模块 32047 / 70308 逐条对齐）
    print("\n[1] 词表规模")
    记("视觉风格表 8 条", len(视觉风格表) == 8, "实际 %d" % len(视觉风格表))
    记("画质表 3 条", len(画质表) == 3, "实际 %d" % len(画质表))
    记("镜头光效表 8 条", len(镜头光效表) == 8, "实际 %d" % len(镜头光效表))
    记("光影氛围表 8 条", len(光影氛围表) == 8, "实际 %d" % len(光影氛围表))
    记("渲染类型表 5 条", len(渲染类型表) == 5, "实际 %d" % len(渲染类型表))
    记("族裔表 5 条", len(族裔表) == 5, "实际 %d" % len(族裔表))
    记("预设表 23 条", len(预设表) == 23, "实际 %d" % len(预设表))
    记("景别表 11 条", len(景别表) == 11, "实际 %d" % len(景别表))
    记("光影氛围 auto 的 keywords 是空串", 光影氛围表[0]["id"] == "auto" and 光影氛围表[0]["keywords"] == "")

    # ---------------- 2. 查找器语义
    print("[2] 查找器（对齐飞彩 $U / bC / wd / ev / fF / p / y）")
    记("$U 命中", (_取视觉风格("cyberpunk") or {}).get("label") == "赛博朋克")
    记("$U 未命中返回 None", _取视觉风格("不存在") is None)
    记("bC 回落第 1 档", _取画质("不存在")["id"] == "cinematic")
    记("wd auto 命中且 keywords 为空", (_取光影("auto") or {}).get("keywords") == "")
    记("ev 逗号拼接 keywords",
      _取镜头光效(["shallow-dof", "film-grain"]).startswith("shallow depth of field, bokeh background")
      and _取镜头光效(["shallow-dof", "film-grain"]).endswith("photochemical noise"))
    记("ev 空输入返回空串", _取镜头光效([]) == "")
    记("fF 4K→cinematic", _分辨率转画质("4K") == "cinematic")
    记("fF 2K→broadcast", _分辨率转画质("2K") == "broadcast")
    记("fF 1K→web", _分辨率转画质("1K") == "web")
    记("fF 缺省→cinematic", _分辨率转画质("") == "cinematic")
    记("y 渲染类型命中 3d-cg", (_取渲染类型("3d-cg") or {}).get("label") == "3D CG")
    记("y 对 auto 返回 auto", (_取渲染类型("auto") or {}).get("id") == "auto")
    记("p 内置优先（照产物，非任务书）", (_取预设("3d-xianxia") or {}).get("label") == "3D国漫仙侠")
    记("p 自定义兜底", (_取预设("my-preset", [{"id": "my-preset", "label": "我的风格", "keywords": "my style",
                                            "prompt": "我的中文描述"}]) or {}).get("label") == "我的风格")

    # ---------------- 3. 整体()
    print("[3] 编译.整体 —— 顺序 / 前缀 / 截断 / else-if 链")
    文 = 编译.整体(_样例设定())
    print("-" * 72)
    print(文)
    print("-" * 72)
    行s = 文.split("\n")
    记("首行是角色一致性标题", 行s[0] == "【角色一致性要求 - 所有画面中同一角色外观必须严格保持一致】")
    记("角色行格式 - 名(#id)：描述", "- 叶云(#C1)：十九岁少年，剑眉星目，玄色劲装，束发银冠" in 文)
    记("场景 section 存在", "\n【场景一致性要求】" in 文)
    记("scene-view 子类型被跳过", "断魂崖·多角度" not in 文)
    记("道具 section 存在", "\n【道具一致性要求】" in 文 and "- 青锋剑(#P1)：" in 文)
    记("整体风格 section 存在", "\n【整体风格要求】" in 文)
    记("- 画幅：16:9", "- 画幅：16:9" in 文)
    记("- Render type: 3D CG — <keywords>",
      "- Render type: 3D CG — 3D CG rendering, volumetric lighting, smooth shading, ray tracing quality" in 文)
    记("- 画质：影院级 (4K)", "- 画质：影院级 (4K)" in 文)
    记("- 画质要求：<keywords>", "- 画质要求：ultra high definition, 4K UHD" in 文)
    记("- 视觉风格：电影写实 — <keywords>",
      "- 视觉风格：电影写实 — cinematic realism, photorealistic, film grain, natural skin texture, lifelike" in 文)
    记("lightingMood=auto 不输出光影行", "- 光影氛围：" not in 文)
    记("- 镜头效果：浅景深, 胶片颗粒 — <合并keywords>",
      "- 镜头效果：浅景深, 胶片颗粒 — shallow depth of field, bokeh background, subject isolation, "
      "soft out-of-focus areas, film grain, analog film texture, 35mm film look, photochemical noise" in 文)
    记("- Style preset: 在 - 预设风格：之前",
      0 <= 文.find("- Style preset:") < 文.find("- 预设风格："))
    记("- Style preset: 3D国漫仙侠 — <keywords>", "- Style preset: 3D国漫仙侠 — Chinese 3D animation" in 文)
    记("- 预设风格：3D国漫仙侠 — <中文描述>",
      "- 预设风格：3D国漫仙侠 — 3D国漫CG渲染，玄幻仙侠风，鎏金、绯红、冰蓝、紫霞色调，东方仙气华丽感" in 文)
    记("- 时代/世界观背景：东方玄幻架空", "- 时代/世界观背景：东方玄幻架空" in 文)
    记("- 补充：全片保持冷调高对比", "- 补充：全片保持冷调高对比" in 文)

    长 = "很" * 200
    文2 = 编译.整体({"characters": [{"id": "C9", "name": "长描述", "description": 长}], "style": {}})
    记("角色描述超 150 字截断且带 …", ("很" * 150 + "…") in 文2 and ("很" * 151) not in 文2)

    文3 = 编译.整体({"style": {"stylePreset": "3d-xianxia",
                            "stylePrompt": '{"artStyle":"油画","colorPalette":"暖橙","styleKeywords":"oil","mood":"暖"}'}})
    记("命中 stylePreset 后 else-if 不再走参考图分支", "参考图画风" not in 文3 and "- 画风：" not in 文3)

    文4 = 编译.整体({"style": {"stylePrompt": '{"artStyle":"水彩","colorPalette":"冷蓝","styleKeywords":"watercolor","mood":"静谧"}'}})
    记("无预设时走参考图 JSON 分支", "- 参考图画风：水彩" in 文4 and "- 参考图色调：冷蓝" in 文4)

    文5 = 编译.整体({"style": {"stylePrompt": "就是一段非 JSON 文本"}})
    记("stylePrompt 解析失败退化为 AI识别风格", "- AI识别风格：就是一段非 JSON 文本" in 文5)

    文6 = 编译.整体({"style": {"artStyle": "赛璐璐", "colorPalette": "樱粉"}})
    记("手填画风/色调分支", "- 画风：赛璐璐" in 文6 and "- 色调：樱粉" in 文6)

    文7 = 编译.整体({"style": {"renderType": "auto"}})
    记("renderType=auto 不输出 Render type 行", "Render type" not in 文7)

    文8 = 编译.整体({"style": {"resolution": "1K"}})
    记("resolution=1K → 网络级 (1K)", "- 画质：网络级 (1K)" in 文8)

    # ---------------- 4. 单格()
    print("[4] 编译.单格 —— 六段公式 / 双语分工 / C5-C6")
    格 = 编译.单格("Medium shot", "Ye Yun draws his sword", "misty cliff edge", "dawn soft light",
                 "cinematic realism, volumetric lighting", 描述="叶云在崖边拔剑")
    print(json.dumps(格, ensure_ascii=False, indent=1))
    记("prompt_text 六段逗号拼接",
      格["prompt_text"] == "Medium shot, Ye Yun draws his sword, misty cliff edge, dawn soft light, "
                           "cinematic realism, volumetric lighting")
    记("time_setting 英文", 格["time_setting"] == "dawn soft light")
    记("time_setting 融入 prompt_text", 格["time_setting"] in 格["prompt_text"])
    记("description 是中文", _有中文(格["description"]) and 格["description"] == "叶云在崖边拔剑")

    格2 = 编译.单格("Close-up", "苏晚回眸", 描述="")
    记("中文段被剔出英文 prompt_text 并记警告",
      "苏晚" not in 格2["prompt_text"] and any("剔除" in w for w in 格2["警告"]))

    格3 = 编译.单格("Medium shot", "Ye Yun stands", "cliff edge",
                  "sunset golden hour", "cinematic realism",
                  排除词="no subtitles, no timecode", 描述="叶云独立崖边")
    记("C5/C6：排除词里的元指令被剥掉", "no subtitles" not in 格3["prompt_text"] and "timecode" not in 格3["prompt_text"])
    记("被剥离列表有记录", len(格3["被剥离"]) >= 2)

    格4 = 编译.单格("Medium shot", "Ye Yun stands", "cliff edge", "sunset golden hour",
                  "cinematic realism", 排除词="cape, cloak, helmet")
    记("物件型排除词保留为 without any …", 格4["prompt_text"].endswith("without any cape, cloak, helmet"))

    格5 = 编译.单格("Medium shot", "one two three four five six seven eight nine ten eleven twelve "
                  "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty",
                  "env", "dawn light", "a b c d e f")
    记("限词：超 30 词先丢 [环境] 段", "env" not in 格5["prompt_text"] and _词数(格5["prompt_text"]) <= 30,
      "词数=%d" % _词数(格5["prompt_text"]))

    格6 = 编译.单格("Wide shot", " ".join("w%02d" % i for i in range(40)),
                  " ".join("e%02d" % i for i in range(20)), "dawn light", "x y z")
    记("H9 硬上限 40 词", _词数(格6["prompt_text"]) <= 40, "词数=%d" % _词数(格6["prompt_text"]))

    for 量, 限 in ((9, 50), (4, 20), (25, 20)):
        g = 编译.单格("Medium shot", "Ye Yun stands", 描述="测" * 99, 宫格=量)
        记("description %d 宫格上限 %d 字" % (量, 限), _字数(g["description"]) <= 限)

    # ---------------- 5. 宫格()
    print("[5] 编译.宫格 —— 节奏 / 景别配额")
    九 = 编译.宫格(9, "断魂崖决战", 主体英文="", 环境="misty broken peak", 时间光照="dusk golden light",
                风格标签="cinematic realism, volumetric lighting", 分段英文=_英文样例,
                分段描述=_中文样例)
    记("九宫格 9 格", len(九) == 9)
    记("九宫格节奏 建立/升级/高潮/收束",
      [x["节奏段"] for x in 九] == ["建立", "建立", "升级", "升级", "升级", "高潮", "高潮", "收束", "收束"])
    景9 = [x["景别"] for x in 九]
    记("九宫格景别配额 1 远景", sum(1 for s in 景9 if s == "Extreme wide shot") == 1)
    记("九宫格景别配额 3 中景", sum(1 for s in 景9 if s == "Medium shot") == 3)
    记("九宫格景别配额 2 特写", sum(1 for s in 景9 if s in ("Close-up", "Extreme close-up")) == 2)
    记("九宫格景别配额 3 自由", sum(1 for s in 景9 if s in ("Over-the-shoulder", "Low angle", "High angle")) == 3)
    记("九宫格无连续 3 个相同景别", not any(景9[i] == 景9[i + 1] == 景9[i + 2] for i in range(7)))

    四 = 编译.宫格(4, "推开木门", 时间光照="dawn soft light", 风格标签="cinematic realism",
                分段英文=["Ye Yun pushes the wooden door open", "the door creaks inward",
                        "a dark hall opens before him", "dust floats in the doorway light"])
    记("四宫格 4 格", len(四) == 4)
    记("四宫格节奏 引入/发展/转折/余韵", [x["节奏段"] for x in 四] == ["引入", "发展", "转折", "余韵"])
    记("四宫格至少两种景别", len(set(x["景别"] for x in 四)) >= 2)

    二五 = 编译.宫格(25, "长夜行军", 时间光照="midnight blue moonlight", 风格标签="epic science fiction")
    记("25 宫格 25 格", len(二五) == 25)
    记("25 宫格 5 轮起承转合", [x["节拍"] for x in 二五[:5]] == ["起", "承", "转", "合", "余韵"] and 二五[-1]["轮"] == 5)
    记("25 宫格景别多样性 ≥ 8 种", len(set(x["景别"] for x in 二五)) >= 8)
    记("25 宫格无相邻重复景别", all(二五[i]["景别"] != 二五[i + 1]["景别"] for i in range(24)))

    try:
        编译.宫格(7, "非法")
        记("宫格数量非 4/9/25 报错", False, "没报错")
    except ValueError:
        记("宫格数量非 4/9/25 报错", True)

    # ---------------- 6. 检查()
    print("[6] 编译.检查 —— H1-H10 / C1-C8 / QC1-QC10")
    合规 = {"shots": [dict(x, 情绪=("平静" if i < 5 else "决绝"), 场景="断魂崖",
                        角色档案={"叶云": "十九岁少年，玄色劲装"}) for i, x in enumerate(九)],
           "grid_layout": "3x3", "关键情节点": ["断魂崖", "拔剑"]}
    结 = 编译.检查(合规)
    摘 = 编译.摘要(结)
    print("合规九宫格：%s" % 摘)
    for x in 结:
        if x["结果"] != "通过":
            print("   [%s] %s %s %s" % (x["结果"], x["编号"], x["名称"], x["说明"]))
    记("检查() 返回 28 条", len(结) == 28, "实际 %d" % len(结))
    记("合规九宫格 0 失败", 摘["失败"] == 0, json.dumps(摘, ensure_ascii=False))
    计["通过"] += 摘["通过"]
    计["没测"] += 摘["没测"]

    脏 = 编译.检查([{"prompt_text": "Medium shot, Ye Yun draws his sword, cliff edge, dawn light, "
                                "cinematic realism, no subtitles, no timecode, 分镜1 in the top-left corner",
                  "description": "叶云拔剑",
                  "time_setting": "dawn light"}])
    脏摘 = 编译.摘要(脏)
    编号s = [x["编号"] for x in 脏 if x["结果"] == "失败"]
    print("含元指令样例：%s  失败项=%s" % (脏摘, 编号s))
    记("C5 抓到 no subtitles / no timecode", "C5" in 编号s)
    记("C6 抓到元指令", "C6" in 编号s)
    记("H1 抓到文字污染", "H1" in 编号s)
    记("QC10 抓到文字污染", "QC10" in 编号s)
    # 脏样例的「失败」是**故意制造**的预期结果，已由上面 4 条断言逐条核对，
    # 不再计入自测失败——否则自测永远 exit 1，等于没有退出码。
    print("   （脏样例的 %d 条失败是故意制造的预期结果）" % 脏摘["失败"])
    计["通过"] += 脏摘["通过"]
    计["没测"] += 脏摘["没测"]

    裸 = 编译.检查("Medium shot, a lone swordsman on a cliff")
    裸摘 = 编译.摘要(裸)
    print("裸字符串样例：%s" % 裸摘)
    记("裸字符串 → 结构类规则记「没测」而不是假装通过", 裸摘["没测"] >= 5, json.dumps(裸摘, ensure_ascii=False))
    记("裸字符串仍然做词数检查（偏短 → C3 失败）", 裸摘["失败"] >= 1)
    print("   （裸字符串样例的 %d 条失败是预期结果：C3 词数偏短）" % 裸摘["失败"])
    计["通过"] += 裸摘["通过"]
    计["没测"] += 裸摘["没测"]

    记("只要问题=True 只回失败/没测", all(x["结果"] != "通过" for x in 编译.检查(合规, 只要问题=True)))

    # ---------------- 7. 身份锁 / 无文字铁律
    print("[7] 身份锁 / 无文字铁律（飞彩原文）")
    锁 = 编译.身份锁()
    记("主身份锁含 IDENTITY LOCK", "[IDENTITY LOCK]" in 锁 and "identity source of truth" in 锁)
    锁2 = 编译.身份锁("叶云")
    记("补充身份锁带角色名", "【🔒 IDENTITY LOCK · 叶云】" in 锁2 and "parent turnaround" in 锁2)
    记("无文字铁律逐字", "STRICT NO-TEXT RULE" in 编译.无文字铁律 and "zero written content" in 编译.无文字铁律)

    # ---------------- 8. 回归：真跑时踩到过、已修的两个 bug
    print("[8] 回归（这两个 bug 是接 风格库.py 真跑时暴露的）")
    编号全集 = [x["编号"] for x in 结]
    应集 = (["H%d" % i for i in range(1, 11)] + ["C%d" % i for i in range(1, 9)]
           + ["QC%d" % i for i in range(1, 11)])
    记("检查() 规则集恰好是 H1-H10 + C1-C8 + QC1-QC10", 编号全集 == 应集,
      "多=%s 少=%s" % (sorted(set(编号全集) - set(应集)), sorted(set(应集) - set(编号全集))))

    设_风格库 = 编译.从风格库("cinematic-real")
    文_色 = 编译.整体(设_风格库)
    记("从风格库()：list 配色渲染成顿号串，不泄 Python repr",
      "- 色调：#1c2430、" in 文_色 and "['#" not in 文_色)
    记("从风格库()：英文画风进「- 画风：」行", "ARRI Alexa" in 文_色)
    记("从风格库()：色板不再以 repr 形式出现", "[\\'#" not in 文_色 and '"#' not in 文_色)
    记("description 回落时拉丁词之间保留空格",
      " " in 编译.单格("Close-up", "Ye Yun glares")["description"],
      编译.单格("Close-up", "Ye Yun glares")["description"])

    # ---------------- 汇总
    print("\n" + "=" * 72)
    print("自测结果：通过 %d / 失败 %d / 没测 %d" % (计["通过"], 计["失败"], 计["没测"]))
    if 失败明细:
        print("-" * 72)
        for x in 失败明细:
            print("失败：" + x)
    print("=" * 72)
    return 0 if 计["失败"] == 0 else 1


def 演示():
    """跑一遍最小链路，人看的。"""
    print("—— 整体 ——")
    print(编译.整体(_样例设定()))
    print("\n—— 九宫格 ——")
    for 格 in 编译.宫格(9, "断魂崖决战", 环境="misty broken peak", 时间光照="dusk golden light",
                     风格标签="cinematic realism, volumetric lighting", 分段英文=_英文样例,
                     分段描述=_中文样例):
        print("%d. [%s|%s] %s" % (格["格"], 格["节奏段"], 格["景别中文"], 格["description"]))
        print("    %s" % 格["prompt_text"])
    print("\n—— 检查 ——")
    for x in 编译.检查("Medium shot, Ye Yun draws his sword, cliff edge, no subtitles", 只要问题=True):
        print("[%s] %s %s —— %s" % (x["结果"], x["编号"], x["名称"], x["说明"]))


def 打印词表():
    for 名, 表 in (("视觉风格表", 视觉风格表), ("画质表", 画质表), ("镜头光效表", 镜头光效表),
                 ("光影氛围表", 光影氛围表), ("渲染类型表", 渲染类型表), ("族裔表", 族裔表),
                 ("预设表", 预设表), ("景别表", 景别表)):
        print("== %s（%d 条）" % (名, len(表)))
        for x in 表:
            print("   " + json.dumps(x, ensure_ascii=False))
        print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    参 = sys.argv[1:]
    if not 参 or 参[0] in ("自测", "test", "--自测", "-t"):
        sys.exit(自测())
    if 参[0] == "演示":
        演示()
        sys.exit(0)
    if 参[0] == "词表":
        打印词表()
        sys.exit(0)
    if 参[0] in ("帮助", "help", "-h", "--help"):
        print(__doc__ or "")
        print("用法：python 编译器.py [自测|演示|词表]")
        print("  自测（缺省）  跑全部断言，通过/失败/没测 三计数，有失败则 exit 1")
        print("  演示          打印一遍最小链路，人看的")
        print("  词表          打印八张词表全部条目")
        sys.exit(0)
    print("用法：python 编译器.py [自测|演示|词表]")
    sys.exit(2)
