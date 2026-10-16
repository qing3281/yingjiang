#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_远端体温.py —— 看两台机器现在有多累。

用法：
    python _远端体温.py            看两台
    python _远端体温.py 远         只看远端
    python _远端体温.py 本         只看本机
    python _远端体温.py --能跑吗    只回一行「远=行/不行 本=行/不行」，给别的脚本判断用

由来（AGENTS.md 第 0.8 条）：
    用户 2026-10-15 原话：「远端都是主力……你想办法尽力压榨，别给我压榨坏了，
    实时监控它的机器温度状态就行。本机的话凡是要稍微留点余地……
    如果说你压榨太狠了，本机的话你这个任务会卡死。」

红线：
    远端 GPU < 83°C（80 开始歇）、显存留 ≥1 GB
    本机 内存留 ≥2 GB
"""
import os, re, subprocess, sys, time

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

远端红线_温度 = 83
远端红线_温度_警告 = 80
远端红线_显存留 = 1.0 * 2**30
本机红线_内存留 = 2.0 * 2**30

SSH = '776bjta'


def GB(n):
    return n / 2**30


# ---------------------------------------------------------------- 本机
def 看本机():
    """不依赖 psutil（本机 venv 里不一定有），全走 PowerShell CIM。"""
    出 = {}
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "$o=Get-CimInstance Win32_OperatingSystem;"
             "'{0}|{1}' -f $o.TotalVisibleMemorySize,$o.FreePhysicalMemory"],
            capture_output=True, text=True, timeout=30)
        总, 闲 = (int(x) for x in r.stdout.strip().split('|'))
        出['内存总'] = 总 * 1024
        出['内存闲'] = 闲 * 1024
    except Exception as e:
        出['错'] = f'内存读不到: {e}'
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"],
            capture_output=True, text=True, timeout=30)
        出['CPU%'] = float(r.stdout.strip())
    except Exception:
        出['CPU%'] = None
    return 出


# ---------------------------------------------------------------- 远端
def 看远端():
    """
    一次 ssh 拿全：显卡 + 内存 + CPU 负载。

    坑（2026-10-15 踩过）：
      1. 远端默认 stdout 是 GBK，本机按 utf-8 解就炸 UnicodeDecodeError —— 所以
         ① 远端脚本里只输出 ASCII；② 本地 errors='replace' 兜底。
      2. 远端脚本里再套 PowerShell 的引号转义会炸 —— 内存改用 ctypes 直接问系统。
    """
    code = (
        "import ctypes, ctypes.wintypes, subprocess\n"
        "class MS(ctypes.Structure):\n"
        "    _fields_=[('dwLength',ctypes.c_ulong),('dwMemoryLoad',ctypes.c_ulong),\n"
        "              ('ullTotalPhys',ctypes.c_ulonglong),('ullAvailPhys',ctypes.c_ulonglong),\n"
        "              ('ullTotalPageFile',ctypes.c_ulonglong),('ullAvailPageFile',ctypes.c_ulonglong),\n"
        "              ('ullTotalVirtual',ctypes.c_ulonglong),('ullAvailVirtual',ctypes.c_ulonglong),\n"
        "              ('ullAvailExtendedVirtual',ctypes.c_ulonglong)]\n"
        "m=MS(); m.dwLength=ctypes.sizeof(MS)\n"
        "ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))\n"
        "print('MEM|%d|%d' % (m.ullTotalPhys, m.ullAvailPhys))\n"
        "try:\n"
        "    o=subprocess.run(['nvidia-smi','--query-gpu=temperature.gpu,utilization.gpu,"
        "memory.used,memory.total,power.draw,power.limit','--format=csv,noheader,nounits'],\n"
        "        capture_output=True, text=True, timeout=20)\n"
        "    print('GPU|' + (o.stdout or o.stderr).strip())\n"
        "except Exception as e:\n"
        "    print('GPU|ERR ' + str(e))\n"
        "try:\n"
        "    o=subprocess.run(['powershell','-NoProfile','-Command',"
        "'(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average'],\n"
        "        capture_output=True, text=True, timeout=20)\n"
        "    print('CPU|' + (o.stdout or '').strip())\n"
        "except Exception:\n"
        "    print('CPU|')\n"
    )
    出 = {}
    try:
        r = subprocess.run(['ssh', SSH, 'python -'], input=code,
                           capture_output=True, text=True, timeout=120,
                           encoding='utf-8', errors='replace')
        文本 = (r.stdout or '') + (r.stderr or '')
    except Exception as e:
        return {'错': f'ssh 连不上: {e}'}

    for 行 in 文本.splitlines():
        if 行.startswith('GPU|'):
            段 = [x.strip() for x in 行[4:].split(',')]
            if len(段) >= 6:
                try:
                    出['温度'] = int(float(段[0]))
                    出['GPU%'] = int(float(段[1]))
                    出['显存用'] = int(float(段[2])) * 2**20
                    出['显存总'] = int(float(段[3])) * 2**20
                    出['功耗'] = float(段[4])
                    出['功耗上限'] = float(段[5])
                except ValueError:
                    pass
        elif 行.startswith('MEM|'):
            段 = 行[4:].split('|')
            if len(段) == 2 and 段[0].strip().isdigit():
                出['内存总'] = int(段[0]) * 1
                出['内存闲'] = int(段[1]) * 1
        elif 行.startswith('CPU|'):
            try:
                出['CPU%'] = float(行[4:].strip())
            except ValueError:
                pass
    if not 出:
        出['错'] = (文本.strip()[:300] or '没拿到任何数据')
    return 出


# ---------------------------------------------------------------- 判
def 判远端(体):
    if '错' in 体:
        return '连不上', [f"远端：{体['错']}"]
    问 = []
    if '温度' in 体:
        if 体['温度'] >= 远端红线_温度:
            问.append(f"★ 温度 {体['温度']}°C ≥ {远端红线_温度}°C —— 停手，等它凉")
        elif 体['温度'] >= 远端红线_温度_警告:
            问.append(f"⚠ 温度 {体['温度']}°C 到 {远端红线_温度_警告} 了 —— 这批跑完歇一会儿")
    if '显存总' in 体:
        剩 = 体['显存总'] - 体['显存用']
        if 剩 < 远端红线_显存留:
            问.append(f"⚠ 显存只剩 {GB(剩):.2f} GB —— 别再加负载")
    if not 问:
        return '能跑', [f"远端：{体.get('温度','?')}°C，显存剩 {GB(体.get('显存总',0)-体.get('显存用',0)):.1f} GB，可以继续压"]
    return ('不行' if any(x.startswith('★') for x in 问) else '能跑'), 问


def 判本机(体):
    if '错' in 体:
        return '连不上', [f"本机：{体['错']}"]
    问 = []
    if '内存闲' in 体:
        剩 = 体['内存闲']
        if 剩 < 本机红线_内存留:
            问.append(f"★ 内存只剩 {GB(剩):.2f} GB < {GB(本机红线_内存留):.0f} GB —— 他要看视频会卡")
        elif 剩 < 2 * 本机红线_内存留:
            问.append(f"⚠ 内存剩 {GB(剩):.2f} GB —— 别在本机跑重活")
    if 体.get('CPU%') and 体['CPU%'] > 85:
        问.append(f"⚠ 本机 CPU {体['CPU%']:.0f}% —— 他在用机器，让一让")
    if not 问:
        return '能跑', [f"本机：内存剩 {GB(体.get('内存闲',0)):.1f} GB，CPU {体.get('CPU%','?')}%"]
    return ('不行' if any(x.startswith('★') for x in 问) else '能跑'), 问


# ---------------------------------------------------------------- 打
def 打(标题, 体):
    条 = []
    if '错' in 体:
        return f"{标题}：{体['错']}"
    if 标题 == '远端':
        条.append(f"GPU   {体.get('温度','?')}°C  跑 {体.get('GPU%','?')}%  "
                  f"显存 {GB(体.get('显存用',0)):.1f}/{GB(体.get('显存总',0)):.1f} GB  "
                  f"功耗 {体.get('功耗','?')}/{体.get('功耗上限','?')} W")
    if '内存总' in 体:
        条.append(f"内存  剩 {GB(体['内存闲']):.1f} / 共 {GB(体['内存总']):.1f} GB"
                  f"    CPU {体.get('CPU%','?')}%")
    return f"{标题}：\n    " + "\n    ".join(条)


def main():
    参 = [a for a in sys.argv[1:]]
    只看 = None
    if '远' in 参:
        只看 = '远'
    if '本' in 参:
        只看 = '本'

    远 = 看远端() if 只看 != '本' else None
    本 = 看本机() if 只看 != '远' else None

    if '--能跑吗' in 参:
        对远 = 判远端(远) if 远 is not None else ('跳过', [])
        对本 = 判本机(本) if 本 is not None else ('跳过', [])
        print(f"远={对远[0]} 本={对本[0]}")
        # 不合格就非零退出，给 shell 判断用
        sys.exit(0 if (对远[0] != '不行' and 对本[0] != '不行') else 1)

    print('=' * 60)
    print(f"两台机器的体温   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print('=' * 60)
    if 远 is not None:
        print(打('远端', 远))
        print()
    if 本 is not None:
        print(打('本机', 本))
        print()

    print('-' * 60)
    if 远 is not None:
        状, 话 = 判远端(远)
        for x in 话:
            print('  ' + x)
    if 本 is not None:
        状, 话 = 判本机(本)
        for x in 话:
            print('  ' + x)
    print('-' * 60)
    print(f"红线：远端 GPU < {远端红线_温度}°C、显存留 ≥{GB(远端红线_显存留):.0f} GB；"
          f"本机内存留 ≥{GB(本机红线_内存留):.0f} GB")


if __name__ == '__main__':
    main()
