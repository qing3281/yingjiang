# -*- coding: utf-8 -*-
"""从音色库里挑「凌霜」能用的音色候选。
凌霜：女、青年、银发紫眼、冷面剑客 → 要 清冷 / 沉静 / 御姐 / 飒，不要甜腻。
用法：python _挑音色.py
"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

库 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '音色', '音色库.json')
d = json.load(open(库, encoding='utf-8'))
a = d['音频']
print(f"音色库 {len(a)} 条\n")

# ── 气质维度打分 ───────────────────────────────────────────
冷 = ['高冷', '清冷', '冷艳', '冷淡', '冰', '御姐', '飒', '女侠', '剑', '武', '沉静', '沉', '静', '稳', '冷']
甜 = ['甜美', '甜', '萌', '萝莉', '娇', '可爱', '活泼', '阳光', '欢快']
成熟 = ['成熟', '御姐', '知性', '优雅', '大气', '娘', 'queen', '女王']


def 打分(x):
    blob = (x.get('名字', '') + ' ' + x.get('文件名', '') + ' ' +
            x.get('子类', '') + ' ' + x.get('大类', '') + ' ' +
            ' '.join(x.get('气质', [])) + ' ' + ' '.join(x.get('用途', [])))
    lo = blob.lower()
    s = 0
    for k in 冷:
        if k in blob or k.lower() in lo:
            s += 2
    for k in 甜:
        s -= 3
    for k in 成熟:
        s += 2
    # 女声加分
    if '女' in x.get('性别', []):
        s += 3
    if '男' in x.get('性别', []):
        s -= 5
    # 时长：IndexTTS 参考音色 3~15 秒最合适
    t = x.get('秒') or 0
    if 3 <= t <= 15:
        s += 2
    elif t < 1.5 or t > 40:
        s -= 4
    # 采样率越高越好
    sr = x.get('采样率') or 0
    if sr >= 32000:
        s += 1
    # 英语音色不利（凌霜要说中文）
    if '英语' in x.get('语言', []):
        s -= 2
    if '方言' in x.get('语言', []):
        s -= 2
    return s


for x in a:
    x['_分'] = 打分(x)

排 = sorted(a, key=lambda x: -x['_分'])

print("=" * 100)
print("候选（按气质分数排序，前 40）")
print("=" * 100)
for x in 排[:40]:
    t = x.get('秒')
    暖 = f"{t:.1f}s" if isinstance(t, (int, float)) else "?"
    print(f"[{x['_分']:>4}] {x['名字'][:46]:46s} {暖:>7s} {str(x.get('采样率') or '?'):>6s}Hz "
          f"气质={','.join(x.get('气质', [])) or '-':12s} 性别={','.join(x.get('性别', [])) or '-':4s} "
          f"龄={','.join(x.get('年龄', [])) or '-':4s} 类={x.get('大类', '')[:12]}")
    print(f"        {x['路径']}")

print()
print("=" * 100)
print("冷/静 关键词直接命中（不管分数）")
print("=" * 100)
n = 0
for x in a:
    blob = x.get('名字', '') + ' ' + x.get('文件名', '') + ' ' + ' '.join(x.get('气质', []))
    if any(k in blob for k in ['高冷', '清冷', '冷艳', '冷淡', '御姐', '冰', '飒', '女侠']) and '男' not in x.get('性别', []):
        n += 1
        if n <= 30:
            t = x.get('秒')
            暖 = f"{t:.1f}s" if isinstance(t, (int, float)) else "?"
            print(f"  {x['名字'][:50]:50s} {暖:>7s} {str(x.get('采样率') or '?'):>6s}Hz {x['路径']}")
print(f"  ... 共 {n} 条")
