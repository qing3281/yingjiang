# -*- coding: utf-8 -*-
"""凌霜音色候选 —— 精选 + 真实音频核验。
凌霜：女、青年、银发紫眼、冷面剑客。要 清冷/沉静/御姐/飒，不要甜腻。
本脚本对每个候选做真实解码，报出 时长/采样率/声道/RMS/削波，并判定能否当 IndexTTS 参考音色。
"""
import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

原声 = r'D:\DSHworkspace\影匠\音色\原声'

# ── 精选候选：路径相对 原声；每一行给「为什么」 ──────────────────
候选 = [
    # ===== A 组：冷艳/清冷 直接命中（最贴凌霜）=====
    (r'男女——情绪分类\女-常规-清冷无情-2-1.wav', 'A', '文件名直写「清冷无情」——这是库里唯一明确标注「无情」的女声，和冷面剑客最贴'),
    (r'男女——情绪分类\女-冷艳、师姐、妩媚.wav', 'A', '「冷艳+师姐」，自带师门前辈的距离感'),
    (r'逗哥音色整理合集\角色扮演\冰山女王.wav', 'A', '「冰山女王」——冷到极致的角色音'),
    (r'新增更多优质音色\更多\冷艳成熟的妩媚御姐女声.mp3', 'A', '库内唯二被标「高冷」的条目之一（气质=高冷,优雅）'),
    (r'voices_export\voices\高冷慵懒御姐\高冷慵懒的性感御姐女声.mp3', 'A', '气质=高冷,慵懒；慵懒感可给凌霜的「不屑」留余地'),

    # ===== B 组：御姐/清冷 备选 =====
    (r'智声整理音色\热门音色\女-温柔、冷酷、亦正亦邪.wav', 'B', '「冷酷+亦正亦邪」——如果剧本里凌霜有立场反转，这条最贴'),
    (r'智声整理音色\热门音色\若霁黎（性感御姐）.wav', 'B', '干净御姐，无甜味'),
    (r'智声整理音色\热门音色\御姐.wav', 'B', '音色库自带的标准御姐，基准参照'),
    (r'逗哥音色整理合集\角色扮演\知性御姐.wav', 'B', '知性>性感，冷而不艳，适合克制表演'),
    (r'智声整理音色\老年\女-平和、冷静、师太.wav', 'B', '「冷静+师太」；年龄偏大，若凌霜走师尊/掌门路线可用'),
]

py = sys.executable
try:
    import soundfile as sf
    print('解码后端: soundfile', sf.__version__)
except Exception as e:
    sf = None
    print('soundfile 不可用:', e)

try:
    import numpy as np
except Exception:
    np = None

结果 = []
print()
print('=' * 118)
print('凌霜音色候选 —— 真实解码核验')
print('=' * 118)
print(f"{'组':2s} {'时长':>7s} {'采样率':>7s} {'声道':>4s} {'RMS':>7s} {'峰值':>6s} {'削波%':>6s}  {'判定':4s} 文件")
print('-' * 118)

for 相对, 组, 理由 in 候选:
    全 = os.path.join(原声, 相对)
    存在 = os.path.isfile(全)
    行 = {'组': 组, '相对': 相对, '全路径': 全, '理由': 理由, '存在': 存在}
    if not 存在:
        print(f"{组:2s} {'——':>7s} {'——':>7s} {'——':>4s} {'——':>7s} {'——':>6s} {'——':>6s}  {'缺失':4s} {相对}")
        行['判定'] = '文件缺失'
        结果.append(行)
        continue
    大小 = os.path.getsize(全)
    行['字节'] = 大小
    try:
        if sf is not None:
            数据, sr = sf.read(全, always_2d=True)
            秒 = len(数据) / sr
            声道 = 数据.shape[1]
            rms = float((数据 ** 2).mean() ** 0.5) if np is not None else 0.0
            峰 = float(abs(数据).max()) if np is not None else 0.0
            削 = float((abs(数据) > 0.99).mean() * 100) if np is not None else 0.0
        else:
            raise RuntimeError('no sf')
    except Exception as e:
        # mp3 回退：走 ComfyUI 的 torchaudio
        行['解码错误'] = str(e)[:80]
        秒 = sr = 声道 = rms = 峰 = 削 = None
    行.update({'秒': 秒, '采样率': sr, '声道': 声道, 'rms': rms, '峰': 峰, '削波': 削, 'MB': 大小 / 1048576})

    # 判定：IndexTTS 参考音色的硬性可用性
    判定 = []
    if 秒 is not None:
        if 秒 < 3:
            判定.append('偏短<3s')
        elif 秒 > 20:
            判定.append('偏长>20s')
        if sr and sr < 16000:
            判定.append('采样率低')
        if rms is not None and rms < 0.01:
            判定.append('音量过低')
        if 削 is not None and 削 > 0.1:
            判定.append('削波')
    else:
        判定.append('未解码')
    判 = '✓可用' if not 判定 else ','.join(判定)

    def f(v, fmt):
        return format(v, fmt) if isinstance(v, (int, float)) else '——'
    print(f"{组:2s} {f(秒,'7.2f')} {f(sr,'7d')} {f(声道,'4d')} {f(rms,'7.4f')} {f(峰,'6.3f')} {f(削,'6.2f')}  {判:4s} {相对}")
    行['判定'] = 判
    结果.append(行)

print()
print('=' * 118)
print('推荐理由 + 绝对路径')
print('=' * 118)
for i, 行 in enumerate(结果, 1):
    print(f"\n{i:2d}. [{行['组']}] {行['判定']}")
    print(f"    路径: {行['全路径']}")
    if 行.get('MB'):
        print(f"    规格: {行['MB']:.2f} MB / {行.get('秒') and round(行['秒'],2)}s / {行.get('采样率')}Hz / {行.get('声道')}ch")
    print(f"    理由: {行['理由']}")

# 落盘 JSON，给 配音.py / 影匠 后续用
输出 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '音色', '凌霜候选.json')
with open(输出, 'w', encoding='utf-8') as f:
    json.dump({'角色': '凌霜', '人设': '女 / 青年 / 银发紫眼 / 冷面剑客',
               '候选': 结果}, f, ensure_ascii=False, indent=2)
print(f"\n已落盘: {输出}")
