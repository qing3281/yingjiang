# -*- coding: utf-8 -*-
"""
影匠 · 风格库
================================================================
原创编写。每个风格 = 一套可直接进 ComfyUI 的提示词工程 + 配色 + 光线。

一条风格记录包含:
  键        英文 id，用在文件名和命令行
  中文      中文名
  英文      英文名
  风格      核心风格 token —— 放在提示词最前面（权重最高）
  画质      画质/介质 token
  光线      光线 token
  镜头      推荐镜头/构图，可被分镜覆盖
  负向      这个风格必须排除的东西
  配色      5 色主色板（十六进制），用于 UI 卡片和调色参考
  适用      什么题材用它
  强度      建议 CFG / 风格权重参考

用法:
    from 风格库 import 取, 全部, 编译
    编译("cyberpunk")                 -> 风格 token 串
    编译("cyberpunk", 角色="...")     -> 风格 + 角色
"""

# ============================================================
# 风格定义
# ============================================================

风格表 = {

# ---------- 一、写实与电影 ----------
"cinematic-real": {
    "中文": "电影写实", "英文": "Cinematic Realism",
    "风格": "cinematic film still, photorealistic, shot on ARRI Alexa, 35mm anamorphic lens, natural skin texture with visible pores, subtle film grain",
    "画质": "8k, ultra detailed, professional color grading, HDR",
    "光线": "motivated practical lighting, soft key with gentle falloff, atmospheric haze",
    "镜头": "medium shot, shallow depth of field, f/1.8",
    "负向": "cartoon, anime, illustration, painting, 3d render, plastic skin, oversaturated",
    "配色": ["#1c2430", "#3e5364", "#8a9aa8", "#d9c8b4", "#e8e2d8"],
    "适用": "现代都市、剧情片、人物特写、对话戏",
    "强度": {"cfg": 5.5, "权重": 1.0},
},
"vintage-film": {
    "中文": "复古胶片", "英文": "Vintage Film",
    "风格": "vintage 1970s film photograph, Kodak Portra 400, heavy grain, halation on highlights, slightly faded contrast, warm amber cast",
    "画质": "film scan, dust and scratches, soft focus falloff at edges",
    "光线": "golden hour backlight, lens flare, warm sun through haze",
    "镜头": "wide shot, 28mm, slight vignette",
    "负向": "digital, sharp, clean, modern, hdr, neon, cgi",
    "配色": ["#3a2b1f", "#7d5a3c", "#c49a6c", "#e8d4b0", "#f2e8d5"],
    "适用": "回忆、年代戏、公路、怀旧叙事",
    "强度": {"cfg": 6.0, "权重": 0.9},
},
"urban-real": {
    "中文": "都市写实", "英文": "Urban Realism",
    "风格": "contemporary urban photography, street documentary style, candid composition, realistic city environment, weathered textures",
    "画质": "high resolution, natural color science, mild contrast",
    "光线": "overcast daylight or mixed street lighting, neon sign reflections on wet asphalt",
    "镜头": "35mm, eye level, documentary framing",
    "负向": "fantasy, stylized, cartoon, oversaturated, studio lighting",
    "配色": ["#20242a", "#4a5560", "#7e8a94", "#b8c0c6", "#e4e8ea"],
    "适用": "现代都市、街头、职场、生活流",
    "强度": {"cfg": 5.5, "权重": 1.0},
},
"epic-nolan": {
    "中文": "冷峻史诗", "英文": "Cold Epic",
    "风格": "epic cinematic wide shot, IMAX large format, desaturated steel-blue palette, monumental scale, lone figure against vast architecture, practical effects realism",
    "画质": "70mm imax, immense detail, deep focus",
    "光线": "cold overcast light, hard shadows, muted highlights, no warmth",
    "镜头": "extreme wide shot, low horizon, tiny human in frame",
    "负向": "bright cheerful colors, cartoon, close-up portrait, cozy, warm tone",
    "配色": ["#0d1418", "#1f323d", "#3d5a6b", "#7d95a3", "#c3d0d6"],
    "适用": "科幻、灾难、战争、宏大叙事开场",
    "强度": {"cfg": 5.0, "权重": 1.1},
},
"horror-thriller": {
    "中文": "恐怖惊悚", "英文": "Horror Thriller",
    "风格": "horror film still, oppressive darkness, deep crushed blacks, single cold light source, grainy 16mm, unsettling negative space, something barely visible in shadow",
    "画质": "high contrast, heavy shadow detail loss, desaturated",
    "光线": "single hard light from below or behind, deep shadow, cold blue-green or sickly yellow",
    "镜头": "dutch angle or static wide, long empty corridor composition",
    "负向": "bright, cheerful, colorful, cute, well lit, safe",
    "配色": ["#050708", "#12181a", "#243033", "#3f4f4a", "#7a8a7a"],
    "适用": "恐怖、悬疑、惊悚、心理戏",
    "强度": {"cfg": 5.0, "权重": 1.1},
},
"dark-gothic": {
    "中文": "暗黑哥特", "英文": "Dark Gothic",
    "风格": "dark gothic fantasy, cathedral architecture with towering spires, blood-red and emerald accents against black stone, ornate decay, ravens and ironwork",
    "画质": "highly detailed digital painting, dramatic chiaroscuro",
    "光线": "candlelight and stained glass shafts, deep shadow, red rim light",
    "镜头": "low angle looking up at architecture, symmetrical composition",
    "负向": "bright, pastel, modern, minimal, clean, daylight",
    "配色": ["#0a0508", "#2b0d14", "#5c1a22", "#1e3a2e", "#a8823c"],
    "适用": "奇幻、吸血鬼、宗教恐怖、暗黑童话",
    "强度": {"cfg": 5.5, "权重": 1.0},
},

# ---------- 二、动画与插画 ----------
"ghibli-anime": {
    "中文": "吉卜力动画", "英文": "Ghibli Anime",
    "风格": "Studio Ghibli style anime, hand-painted watercolor background, gentle rounded character design, lush detailed nature, nostalgic warmth, cel shading with soft edges",
    "画质": "anime key visual, clean linework, rich painted backgrounds",
    "光线": "warm afternoon sun, dappled light through leaves, soft bloom",
    "镜头": "medium wide, character small in beautiful environment",
    "负向": "photorealistic, 3d render, dark, gritty, horror, harsh shadows",
    "配色": ["#7fb069", "#a8d5ba", "#f4e9cd", "#8ecae6", "#e8b04b"],
    "适用": "治愈、成长、奇幻冒险、日常",
    "强度": {"cfg": 6.0, "权重": 1.0},
},
"korean-webtoon": {
    "中文": "韩国条漫", "英文": "Korean Webtoon",
    "风格": "Korean webtoon manhwa style, clean digital lineart, glossy rendering, beautiful idealized characters, sparkle highlights in eyes and hair, soft gradient shading",
    "画质": "webtoon illustration, crisp lines, vibrant但smooth colors",
    "光线": "soft diffused beauty lighting, blooming highlights, bokeh sparkles",
    "镜头": "portrait or medium shot, centered, romance drama framing",
    "负向": "rough sketch, gritty, western comic, realistic pores, muted",
    "配色": ["#f7d9e3", "#c9a7e8", "#8fb8e8", "#fdf6f0", "#5a4a6a"],
    "适用": "言情、校园、偶像、情绪特写",
    "强度": {"cfg": 6.0, "权重": 1.0},
},
"comic-us": {
    "中文": "美式漫画", "英文": "American Comic",
    "风格": "american comic book art, bold black ink outlines, halftone dot shading, dynamic anatomy, dramatic foreshortening, primary color palette",
    "画质": "comic panel, high contrast inking, cross-hatching",
    "光线": "hard directional light, deep black shadows, dramatic rim",
    "镜头": "dynamic low angle, action pose, speed lines",
    "负向": "soft shading, pastel, anime, photorealistic, subtle",
    "配色": ["#1a1a1a", "#c9202a", "#f2c230", "#1b4f9c", "#f5f0e6"],
    "适用": "超级英雄、动作、战斗、热血",
    "强度": {"cfg": 6.5, "权重": 1.0},
},
"disney-3d": {
    "中文": "迪士尼3D", "英文": "Disney 3D",
    "风格": "Disney Pixar 3D animation style, stylized appealing character design, large expressive eyes, soft subsurface scattering skin, rounded shapes, cinematic 3d render",
    "画质": "octane render, ray tracing, pristine 3d, 8k",
    "光线": "warm three-point cinematic lighting, soft global illumination, gentle rim",
    "镜头": "medium close-up, eye level, expressive face",
    "负向": "flat 2d, anime lineart, realistic, gritty, ugly, horror",
    "配色": ["#f7b267", "#f25c54", "#4ecdc4", "#ffe66d", "#2e4057"],
    "适用": "合家欢、童话、歌舞、拟人角色",
    "强度": {"cfg": 5.5, "权重": 1.0},
},
"dreamy-pastel": {
    "中文": "梦幻柔彩", "英文": "Dreamy Pastel",
    "风格": "dreamy pastel illustration, soft airbrushed gradients, floating sparkles and petals, ethereal ribbons of light, whimsical fantasy, low contrast haze",
    "画质": "delicate digital painting, soft edges, luminous",
    "光线": "diffused god rays, glowing volumetric haze, no hard shadows",
    "镜头": "wide ethereal composition, floating elements",
    "负向": "harsh contrast, dark, gritty, realistic, sharp lines, horror",
    "配色": ["#f6e2f0", "#dcd0f0", "#c3e0f5", "#fdf3e7", "#b8a8d8"],
    "适用": "梦境、魔法、少女、治愈、MV",
    "强度": {"cfg": 6.0, "权重": 1.0},
},
"watercolor": {
    "中文": "水彩绘本", "英文": "Watercolor Storybook",
    "风格": "children's storybook watercolor illustration, visible paper texture, wet-on-wet bleeding edges, loose expressive brushwork, white paper showing through",
    "画质": "traditional watercolor on cold press paper, 300dpi scan",
    "光线": "flat ambient light, gentle color washes",
    "镜头": "storybook vignette composition, generous white space",
    "负向": "digital, sharp, 3d, photorealistic, hard edges, neon",
    "配色": ["#a8c8e8", "#e8d5a8", "#c8b8d8", "#f5f0e8", "#88a898"],
    "适用": "绘本、童趣、回忆、温情叙事",
    "强度": {"cfg": 6.0, "权重": 1.0},
},
"pixel-retro": {
    "中文": "像素复古", "英文": "Pixel Retro",
    "风格": "16-bit pixel art, limited color palette, crisp pixel clusters, dithering gradients, retro game sprite aesthetic, isometric or side-scroller perspective",
    "画质": "pixel perfect, nearest-neighbor upscale, no antialiasing",
    "光线": "flat game lighting, simple two-tone shading",
    "镜头": "side view or 3/4 top-down game camera",
    "负向": "smooth gradient, photorealistic, blurry, high resolution detail, 3d",
    "配色": ["#1a1c2c", "#5d275d", "#b13e53", "#ef7d57", "#ffcd75"],
    "适用": "复古游戏、轻松搞笑、像素叙事",
    "强度": {"cfg": 6.5, "权重": 1.1},
},
"paper-cut": {
    "中文": "剪纸层叠", "英文": "Layered Paper Cut",
    "风格": "layered paper cutout art, stacked flat shapes with hard drop shadows between layers, craft paper texture, silhouette composition, depth through separation",
    "画质": "handcrafted paper craft, crisp cut edges, matte finish",
    "光线": "raking side light casting long shadows between layers",
    "镜头": "flat-on composition with parallax depth",
    "负向": "gradient, painterly, 3d render, glossy, photorealistic",
    "配色": ["#2b3a4a", "#d95f4a", "#e8b04b", "#f2e8d5", "#7a9e9f"],
    "适用": "寓言、科普、手工感叙事、转场",
    "强度": {"cfg": 6.0, "权重": 1.0},
},
"claymation": {
    "中文": "粘土定格", "英文": "Claymation",
    "风格": "stop-motion claymation, handmade plasticine characters with visible fingerprints, felt and fabric textures, miniature set with practical lighting, tilt-shift depth",
    "画质": "macro photography of miniature set, shallow focus, tactile surface",
    "光线": "warm practical miniature lighting, soft shadows on tiny set",
    "镜头": "low angle miniature camera, shallow depth of field",
    "负向": "cgi, smooth, digital, flat illustration, anime, photorealistic human",
    "配色": ["#e8a87c", "#c38d9e", "#41b3a3", "#f5e6ca", "#6b4f4f"],
    "适用": "童趣、幽默、解说、广告感",
    "强度": {"cfg": 6.0, "权重": 1.0},
},

# ---------- 三、东方与古典 ----------
"ink-wash": {
    "中文": "国风水墨", "英文": "Chinese Ink Wash",
    "风格": "traditional Chinese ink wash painting, xieyi freehand brushwork, flowing brush strokes, generous negative space, misty mountains, subtle ink gradation",
    "画质": "rice paper texture, ink bleeding, seal stamp in corner",
    "光线": "flat misty ambient, no directional light",
    "镜头": "vertical scroll composition, vast empty space",
    "负向": "western, 3d, photorealistic, saturated color, busy detail, anime",
    "配色": ["#0a0a0a", "#3a3a38", "#7a7870", "#c8c4b8", "#f2efe6"],
    "适用": "武侠、古风、禅意、诗词意境",
    "强度": {"cfg": 6.0, "权重": 1.1},
},
"ukiyo-e": {
    "中文": "浮世绘", "英文": "Ukiyo-e",
    "风格": "japanese ukiyo-e woodblock print, flat color planes, bold black keyline outlines, decorative wave and cloud patterns, hokusai style, visible woodgrain",
    "画质": "edo period woodblock print, registration marks, washi paper",
    "光线": "flat graphic lighting, no gradients, pure color fields",
    "镜头": "decorative poster composition, strong diagonal",
    "负向": "3d, photorealistic, gradient shading, western perspective, blur",
    "配色": ["#1a3a5c", "#2e6f8e", "#e8c547", "#d95f3b", "#f5f0e0"],
    "适用": "日本题材、海浪、武士、装饰性画面",
    "强度": {"cfg": 6.0, "权重": 1.1},
},
"xianxia-3d": {
    "中文": "仙侠3D", "英文": "Xianxia 3D",
    "风格": "Chinese xianxia 3d cg, flowing silk robes and long hair in wind, glowing qi energy and floating talismans, celestial mountains and clouds, ornate golden ornaments, highly detailed fantasy cg",
    "画质": "unreal engine 5 cinematic, ray traced, 8k, subsurface scattering",
    "光线": "divine volumetric god rays, glowing aura rim light, magical particle bloom",
    "镜头": "heroic low angle, flowing cape, dynamic floating pose",
    "负向": "modern clothing, western fantasy, realistic photo, flat 2d, dull",
    "配色": ["#0d1b3a", "#2b5fa8", "#8fc8e8", "#e8cfa0", "#f5e8f0"],
    "适用": "仙侠、玄幻、法术对决、飞升",
    "强度": {"cfg": 5.5, "权重": 1.0},
},
"oil-painting": {
    "中文": "古典油画", "英文": "Classical Oil Painting",
    "风格": "classical baroque oil painting, visible impasto brushstrokes, rich glazed layers, dramatic chiaroscuro, rembrandt lighting, museum masterpiece quality",
    "画质": "oil on linen canvas, aged varnish, craquelure, gallery scan",
    "光线": "single dramatic light source from upper left, deep tenebrist shadow",
    "镜头": "three-quarter portrait composition, dark background",
    "负向": "digital, flat, anime, neon, photographic, modern",
    "配色": ["#1a1208", "#4a3018", "#8a6530", "#c8a060", "#e8d5a8"],
    "适用": "历史、贵族、肖像、宗教题材",
    "强度": {"cfg": 5.5, "权重": 1.0},
},

# ---------- 四、科幻与未来 ----------
"cyberpunk": {
    "中文": "赛博朋克", "英文": "Cyberpunk",
    "风格": "cyberpunk cityscape, rain-slicked neon streets, towering holographic advertisements, dense urban verticality, chrome and grime, biotech implants, blade runner atmosphere",
    "画质": "photorealistic cg, volumetric fog, anamorphic lens flare, 8k",
    "光线": "neon magenta and cyan practicals, wet reflections, deep shadow between light pools",
    "镜头": "wide establishing shot, low angle looking up at towers",
    "负向": "daylight, clean, pastoral, medieval, warm cozy, cartoon",
    "配色": ["#0a0a12", "#1b1040", "#ff2a6d", "#05d9e8", "#f5f5f5"],
    "适用": "科幻、反乌托邦、黑客、未来都市",
    "强度": {"cfg": 5.5, "权重": 1.0},
},
"steampunk": {
    "中文": "蒸汽朋克", "英文": "Steampunk",
    "风格": "steampunk victorian machinery, brass gears and copper pipes, riveted iron plates, pressure gauges, steam vents, clockwork automaton, leather and goggles",
    "画质": "highly detailed mechanical illustration, warm metal specular",
    "光线": "warm gaslight and furnace glow, volumetric steam",
    "镜头": "medium shot of contraption, dutch tilt for motion",
    "负向": "modern, digital, neon, plastic, minimalist, sleek",
    "配色": ["#2b1d10", "#6b4a22", "#b8863c", "#d9b070", "#3a5a5a"],
    "适用": "工业幻想、发明家、维多利亚、机械",
    "强度": {"cfg": 6.0, "权重": 1.0},
},
"sci-fi-epic": {
    "中文": "硬核科幻", "英文": "Hard Sci-Fi Epic",
    "风格": "hard science fiction concept art, colossal megastructure, ringworld and dyson swarm, sleek starship hulls, realistic space physics, sense of immense scale",
    "画质": "matte painting, 8k, razor sharp, cinematic concept art",
    "光线": "single distant star as hard key, deep black space, planet bounce light",
    "镜头": "extreme wide, tiny ship against giant structure",
    "负向": "fantasy magic, medieval, cartoon, cozy, warm, cluttered",
    "配色": ["#03050a", "#0d2b45", "#2e6f9e", "#8fc8e8", "#e8f0f5"],
    "适用": "太空歌剧、星际、宏大科幻",
    "强度": {"cfg": 5.0, "权重": 1.1},
},
"wasteland": {
    "中文": "废土末日", "英文": "Post-Apocalyptic Wasteland",
    "风格": "post-apocalyptic wasteland, rusted vehicle wrecks, sand-blasted ruins, makeshift scavenger armor, scorched earth, dust storms, mad max aesthetic",
    "画质": "gritty photorealistic, heavy dust atmosphere, desaturated",
    "光线": "harsh overhead desert sun, blown highlights, orange dust haze",
    "镜头": "wide desert vista with lone figure, heat distortion",
    "负向": "lush green, clean, city, futuristic sleek, cheerful, indoor",
    "配色": ["#3a2a18", "#7a5a32", "#b8925a", "#d9c090", "#8a6a4a"],
    "适用": "末日、生存、荒野、动作",
    "强度": {"cfg": 5.5, "权重": 1.0},
},
"superhero": {
    "中文": "超级英雄", "英文": "Superhero Epic",
    "风格": "modern superhero film cg, heroic silhouette against destruction, glowing energy powers, tactical armored suit with detail, urban devastation, epic stakes",
    "画质": "8k cinematic render, ray traced, high detail costume",
    "光线": "dramatic backlight through smoke, energy glow as key, rim light on hero",
    "镜头": "heroic low angle, cape or energy trailing, dynamic action pose",
    "负向": "mundane, quiet, small scale, cartoon, flat, daylight casual",
    "配色": ["#0a0e1a", "#1e2a4a", "#3a6fd9", "#d93025", "#f0c040"],
    "适用": "超英、异能、大战、热血高潮",
    "强度": {"cfg": 5.5, "权重": 1.0},
},

# ---------- 五、特殊质感 ----------
"lego": {
    "中文": "乐高积木", "英文": "LEGO Brick",
    "风格": "everything built from LEGO bricks, minifigure characters with c-shaped hands, visible stud texture, ABS plastic sheen, molded seams, diorama set",
    "画质": "macro toy photography, crisp plastic specular highlights",
    "光线": "bright even studio lighting, soft shadows on tabletop set",
    "镜头": "eye level with minifigures, tilt-shift miniature depth",
    "负向": "organic, smooth skin, fabric, realistic, painterly, blurry",
    "配色": ["#d01012", "#f2cd37", "#0055bf", "#237841", "#f5f5f5"],
    "适用": "搞笑、科普、品牌、轻松改编",
    "强度": {"cfg": 6.5, "权重": 1.1},
},
"3d-cg-voxel": {
    "中文": "体素方块", "英文": "Voxel Art",
    "风格": "voxel art made of uniform cubes, minecraft-like blocky construction, isometric diorama, chunky pixel-3d aesthetic, everything built from cubes",
    "画质": "clean isometric render, ambient occlusion between blocks, 4k",
    "光线": "soft directional sun with clean shadows, no bloom",
    "镜头": "isometric 3/4 view, floating diorama island",
    "负向": "smooth curve, realistic, painterly, blurry, organic shape",
    "配色": ["#5a9e4a", "#8a6a4a", "#4a90d9", "#e8d060", "#c8c8c8"],
    "适用": "游戏感、轻松、建筑、可爱叙事",
    "强度": {"cfg": 6.5, "权重": 1.1},
},
"infographic": {
    "中文": "信息图", "英文": "Infographic Diagram",
    "风格": "clean modern infographic, flat vector shapes, thin line icons, labeled callout boxes with leader lines, data chart, sans-serif typography, generous white space",
    "画质": "vector, crisp edges, print ready, flat color",
    "光线": "flat even illumination, no shadow",
    "镜头": "straight-on poster layout, grid aligned",
    "负向": "photorealistic, 3d, painterly, textured, hand drawn, dark",
    "配色": ["#ffffff", "#1a1a2e", "#0f9b8e", "#f2a63b", "#e8e8ee"],
    "适用": "科普、说明、教学、数据可视化",
    "强度": {"cfg": 6.0, "权重": 1.0},
},
"noir-bw": {
    "中文": "黑白电影", "英文": "Film Noir B&W",
    "风格": "classic film noir black and white, venetian blind shadows across a face, cigarette smoke curling in hard light, trench coat silhouette, 1940s crime drama",
    "画质": "high contrast monochrome, silver halide grain, deep blacks",
    "光线": "single hard key through blinds, extreme chiaroscuro, no fill",
    "镜头": "low angle menacing framing, dutch tilt",
    "负向": "color, bright, cheerful, soft light, modern, digital clean",
    "配色": ["#000000", "#1a1a1a", "#4a4a4a", "#9a9a9a", "#f5f5f5"],
    "适用": "犯罪、侦探、悬疑、黑色幽默",
    "强度": {"cfg": 5.5, "权重": 1.1},
},
}

# ============================================================
# 通用负向（所有风格共用）
# ============================================================
通用负向 = (
    "lowres, blurry, jpeg artifacts, watermark, signature, text, "
    "extra fingers, fused fingers, extra limbs, deformed hands, "
    "bad anatomy, mutated, disfigured, worst quality, low quality"
)

# ============================================================
# 接口
# ============================================================

def 全部():
    """返回所有风格键"""
    return list(风格表.keys())

def 取(键):
    """取一条风格；支持中文名或英文 id"""
    if 键 in 风格表:
        return 风格表[键]
    for k, v in 风格表.items():
        if v["中文"] == 键 or v["英文"].lower() == 键.lower():
            return v
    return None

def 编译(键, 额外="", 角色="", 镜头=None, 去掉负向=False):
    """
    把一个风格编译成最终正向 / 负向提示词。

    参数:
      键        风格键（中文或英文 id）
      额外      额外追加的正向描述（剧情、动作、场景）
      角色      角色一致性 token（由角色库生成）
      镜头      覆盖默认镜头
      去掉负向  True 则只返回正向
    """
    s = 取(键)
    if s is None:
        return {"正向": 额外, "负向": 通用负向, "错": f"没有这个风格：{键}"}

    段 = [s["风格"], s["画质"]]
    if 角色:
        段.append(角色)
    if 额外:
        段.append(额外)
    段.append(镜头 or s["镜头"])
    段.append(s["光线"])
    正向 = ", ".join(x for x in 段 if x)

    负向 = "" if 去掉负向 else (s["负向"] + ", " + 通用负向)
    return {
        "正向": 正向,
        "负向": 负向,
        "风格": s["中文"],
        "配色": s["配色"],
        "cfg": s["强度"]["cfg"],
    }

def 找(关键词):
    """按关键词模糊搜风格（搜中文名/英文名/适用场景）"""
    果 = []
    for k, v in 风格表.items():
        if (关键词 in v["中文"] or 关键词.lower() in v["英文"].lower()
                or 关键词 in v["适用"]):
            果.append((k, v["中文"], v["适用"]))
    return 果

def 打印全部():
    print(f"\n{'键':<18} {'中文':<10} {'英文':<22} 适用")
    print("-" * 88)
    for k, v in 风格表.items():
        print(f"{k:<18} {v['中文']:<10} {v['英文']:<22} {v['适用']}")
    print(f"\n共 {len(风格表)} 个风格\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        r = 编译(sys.argv[1], 额外=" ".join(sys.argv[2:]))
        print("\n【正向】\n" + r["正向"])
        print("\n【负向】\n" + r["负向"])
        print("\n【配色】" + "  ".join(r["配色"]))
    else:
        打印全部()
