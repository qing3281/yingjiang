# -*- coding: utf-8 -*-
"""收尾：① 追加这次搬家的经验 ② 核三份入口文档里的链接和路径 ③ 清掉工具目录里的临时件
用法：python _收尾.py            （干跑）
      python _收尾.py --真跑
"""
import os, sys, re, shutil, datetime
sys.stdout.reconfigure(encoding='utf-8')

根 = r'D:\DSHworkspace'
工具 = os.path.join(根, '工具')
记忆 = os.path.join(根, '记忆')
真跑 = '--真跑' in sys.argv

print('=' * 100)
print('收尾　%s' % ('真跑' if 真跑 else '干跑'))

# ── ① 追加经验 ────────────────────────────────────────────────
经验 = os.path.join(记忆, '经验', '流程与脚本.md')
日期 = datetime.date.today().strftime('%Y-%m-%d')
条 = [
 ('把根目录文件搬进文件夹时，光改文本引用不够 —— 还有一类脚本拿 `__file__` 的上一层当工作区根，'
  '一搬进子目录它就把子目录当成根了。',
  '搬家前先扫一遍 `os.path.dirname(os.path.abspath(__file__))`，凡是拿它当根的都要补一层。实测 187 个脚本里 20 个要补。'),
 ('脚本里写死的绝对路径要全树替换，不是只替换被搬的那几个文件。',
  '`_搬家.py` 扫全树文本文件，482 条映射改了 354 个文件；改之前每个都先备份。'),
 ('Windows 下 `os.rename` 一个几百 GB 的目录会报 `WinError 5 拒绝访问`，不是权限问题。',
  '改成逐个孩子 rename（354 GB 的 `网盘` 目录 111/111 成功），或先建新目录再搬。'),
 ('`PermissionError: [WinError 32] 另一个程序正在使用此文件` 是「被占用」不是「权限不够」——'
  'ComfyUI / DSH 开着句柄，脚本没 catch 就整个崩在中间。',
  '所有 `os.rename` / `os.remove` / `shutil.move` 都要包 try/except (PermissionError, OSError)，打「跳过（占用中）」并继续。'),
 ('整理工具自己的白名单文件也会被它自己「整理」掉。',
  '`_大扫除.py` 把 `_活工具.txt` / `_保命清单.txt` 当成 `.txt` 调试残留挪走了；再跑一次白名单就是空的，那时候它会把活工具也挪走。→ 白名单文件要显式加进保命集，缺了要打警告。'),
 ('清单类文件写成覆盖模式，一次重跑就没了。',
  '`_清理清单.md` 用 `open(..., "w")`，重跑一次干跑就把真跑那 979 行冲了。→ 每次写带时间戳的副本，只有真跑才覆盖权威那份。'),
 ('搬完家必须去点一次桌面图标 —— 搬完之后 `.lnk` 的目标可能全指到了旧路径。',
  '`_修桌面指向.py` 解引用 39 个 `.lnk`，搬完发现 4 个坏了。'),
 ('核交接文档时，把路径从散文里用正则刮出来一个一个 `os.path.exists`。',
  '`check_交接.py` 刮出 42 条绝对路径、41 条在磁盘上、1 条是远端路径不验。从散文里刮路径时必须先把尾部标点剥掉（句号/逗号/右括号/冒号/星号/引号），不做就会报 10 条假缺失。'),
]
新 = ['', '---', '', '## %s 搬家与交接（2026-10-16）' % 日期, '']
for 教训, 判据 in 条:
    新.append('- %s %s → 判据：%s' % (日期, 教训, 判据))
块 = '\n'.join(新) + '\n'
print('\n① 往 %s 追加 %d 条' % (经验, len(条)))
if 真跑:
    备份 = 经验 + '.bak-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy2(经验, 备份)
    with open(经验, 'a', encoding='utf-8') as f:
        f.write(块)
    print('   ✓ 追加完（%d → %d 字节），备份 %s' % (os.path.getsize(备份), os.path.getsize(经验), os.path.basename(备份)))
else:
    print('   （干跑，没写）')

# ── ② 核三份入口文档 ─────────────────────────────────────────
print('\n② 核入口文档里的链接与路径')
要核 = ['AGENTS.md', '交接.md', '目录说明.md']
坏 = []
for 名 in 要核:
    p = os.path.join(根, 名)
    if not os.path.exists(p):
        print('   ★ %s 不在！' % 名); 坏.append((名, '文件本身不在')); continue
    t = open(p, encoding='utf-8').read()
    # markdown 链接 [文字](目标)
    链接 = re.findall(r'\[[^\]]*\]\(([^)]+)\)', t)
    # 反引号 / 行内的盘符路径
    路径 = re.findall(r'([A-Za-z]:\\[^\s`\'"，。、）)]+)', t)
    坏链 = []
    for L in 链接:
        if L.startswith('http'):
            continue
        q = os.path.normpath(os.path.join(根, L))
        if not os.path.exists(q):
            坏链.append(L)
    坏路 = []
    占位 = 0
    for q in set(路径):
        q = q.rstrip('。，、）):：*\'"')
        if q.lower().startswith('e:\\'):
            continue          # 远端路径，不验
        # ★ 通配/占位不是坏路径 —— 不排除的话每次都会「报 5 条坏路」，
        #   数字一虚报，真人就会开始无视这个检查（假判据的另一种形状）。
        if any(c in q for c in ('*', '<', '...', '{')):
            占位 += 1
            continue
        if not os.path.exists(q):
            坏路.append(q)
    print('   %-14s 链接 %2d 条（坏 %d）　盘符路径 %2d 条（不在磁盘 %d，通配占位 %d）'
          % (名, len(链接), len(坏链), len(set(路径)), len(坏路), 占位))
    for x in 坏链: print('        ★ 坏链：%s' % x)
    for x in 坏路[:12]: print('        ★ 没有：%s' % x)
    if 坏链: 坏.append((名, '链接'))
    if 坏路: 坏.append((名, '路径'))

# ── ③ 清工具目录里的临时件 ───────────────────────────────────
print('\n③ 工具目录里的临时件')
临时 = []
for b, ds, fs in os.walk(工具):
    if '__pycache__' in b:
        continue
    for d in list(ds):
        if d == '__pycache__':
            临时.append(('目录', os.path.join(b, d)))
    for f in fs:
        if f.endswith(('.tmp', '.part', '.crdownload')) or f.startswith('~$') or '临时' in f and f.endswith('.ps1'):
            临时.append(('文件', os.path.join(b, f)))
for 类, p in 临时:
    print('   %s  %s' % (类, p))
print('   共 %d 项' % len(临时))
if 真跑:
    for 类, p in 临时:
        try:
            shutil.rmtree(p) if 类 == '目录' else os.remove(p)
        except (PermissionError, OSError) as e:
            print('   · 跳过 %s（%s）' % (os.path.basename(p), type(e).__name__))
    print('   ✓ 清完')

print('\n' + '=' * 100)
print('结论：坏链/坏路径 %d 项' % len(坏))
