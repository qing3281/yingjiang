# -*- coding: utf-8 -*-
"""_修归档嵌套.py —— 把搬家时套深了一层的归档拉平，并修引用
用法：python _修归档嵌套.py            干跑
      python _修归档嵌套.py --真跑
"""
import os, sys, re, shutil
sys.stdout.reconfigure(encoding='utf-8')

根 = r'D:\DSHworkspace'
归 = os.path.join(根, '记忆', '归档')
内 = os.path.join(归, '归档')          # ← 套深的那一层
真跑 = '--真跑' in sys.argv


def 人(b):
    for u in ('B', 'KB', 'MB', 'GB'):
        if b < 1024:
            return '%.1f %s' % (b, u)
        b /= 1024.0
    return '%.1f TB' % b


def 大(p):
    n = s = 0
    for b, _d, fs in os.walk(p):
        for f in fs:
            try:
                s += os.path.getsize(os.path.join(b, f)); n += 1
            except OSError:
                pass
    return n, s


print('=' * 100)
print('修归档嵌套　%s' % ('真跑' if 真跑 else '干跑'))
print('  归档根 %s' % 归)
print('  套深层 %s' % 内)

# ── ① 把 记忆\归档\归档\* 拉平到 记忆\归档\* ─────────────────
print('\n① 拉平 %s 的孩子往上提一层' % 内)
if not os.path.isdir(内):
    print('   （没有这一层，跳过）')
else:
    for x in sorted(os.listdir(内)):
        源 = os.path.join(内, x)
        目标 = os.path.join(归, x)
        if os.path.exists(目标):
            print('   ★ 重名，跳过：%s（%s 已存在）' % (x, 目标))
            continue
        if 真跑:
            try:
                shutil.move(源, 目标)
                print('   ✓ %s → %s' % (x, 目标))
            except (PermissionError, OSError) as e:
                print('   · 跳过 %s（%s）' % (x, type(e).__name__))
        else:
            print('   · %s → %s' % (x, 目标))
    if 真跑 and os.path.isdir(内) and not os.listdir(内):
        os.rmdir(内); print('   ✓ 删掉空壳 %s' % 内)
    elif 真跑 and os.path.isdir(内):
        print('   ★ %s 还剩 %d 项，没删' % (内, len(os.listdir(内))))

# ── ② 搬家前 里那个自我嵌套的副本 ─────────────────────────────
套 = os.path.join(归, '搬家前', '记忆', '归档', '搬家前')
print('\n② 搬前备份里的自我嵌套副本')
if os.path.isdir(套):
    n, s = 大(套)
    print('   %s　%d 个 / %s' % (套, n, 人(s)))
    print('   ★ 是「备份里的备份」（我跑了两遍搬家程序留下的残影），**不删** ——')
    print('     硬红线 1：删任何东西之前先给他核对。列在这里让他自己决定。')
else:
    print('   （没有，跳过）')

# ── ③ 修 _重建归档总表.py 里写死的 _归档 路径 ─────────────────
print('\n③ 修 _重建归档总表.py 里写死的路径')
p = os.path.join(根, '工具', '_重建归档总表.py')
t = open(p, encoding='utf-8').read()
改 = [
    ('归 = os.path.join(根, "_归档")', '归 = os.path.join(根, "记忆", "归档")'),
    ('产物 `_归档\\\\_归档总表.md`', '产物 `记忆\\\\归档\\\\_归档总表.md`'),
    ('`_归档\\` 里到底躺着什么', '`记忆\\归档\\` 里到底躺着什么'),
    ("Get-ChildItem 'D:\\\\DSHworkspace\\\\_归档'", "Get-ChildItem 'D:\\\\DSHworkspace\\\\记忆\\\\归档'"),
]
有没有改 = False
for 旧, 新 in 改:
    if 旧 in t:
        t = t.replace(旧, 新); 有没有改 = True
        print('   ✓ 换掉：%s' % 旧[:60])
    else:
        print('   · 没找到（可能已经改过）：%s' % 旧[:60])
if 有没有改 and 真跑:
    open(p, 'w', encoding='utf-8').write(t)
    print('   ✓ 写回 %s' % p)
elif 有没有改:
    print('   （干跑，没写）')

# ── ④ 修 AGENTS.md 里的坏链 用户画像.md ──────────────────────
print('\n④ 修 AGENTS.md 里的坏链')
a = os.path.join(根, 'AGENTS.md')
ta = open(a, encoding='utf-8').read()
if '[`用户画像.md`](用户画像.md)' in ta:
    ta = ta.replace('[`用户画像.md`](用户画像.md)', '[`用户画像.md`](记忆/用户画像.md)')
    print('   ✓ [`用户画像.md`](用户画像.md) → (记忆/用户画像.md)')
elif '(记忆/用户画像.md)' in ta:
    print('   · 已经是对的')
else:
    m = re.search(r'\[[^\]]*用户画像[^\]]*\]\(([^)]+)\)', ta)
    print('   ★ 没找到标准写法，手动看：%r' % (m.group(0) if m else '没有'))
if 真跑 and '(记忆/用户画像.md)' in ta:
    open(a, 'w', encoding='utf-8').write(ta)

print('\n' + '=' * 100)
