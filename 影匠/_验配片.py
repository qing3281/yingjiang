# -*- coding: utf-8 -*-
"""只验 `_配片.py` 的说话人解析 + 音色映射，不合成（省时间、不抢 GPU）。

`_配片.py` 里「沈砚（少年）」这种带括号的说话人，如果直接拿「沈砚」去查映射，
会命中成年沈砚的音色，而且**不报错** —— 格26 那句十年前的台词就配成了十年后的嗓子。
所以这里逐句把「查表键」打出来看。
"""
import importlib.util
import os
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)


def 装(名):
    spec = importlib.util.spec_from_file_location(名, os.path.join(根, f"{名}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


配片 = 装("_配片")
配音 = 装("配音")

md = os.path.join(根, "作品", "磨刀", "03-台词.md")
表 = 配片.读台词(md, print)
print(f"读到 {len(表)} 句\n")

人 = []
for t in 表:
    if t["谁"] not in 人:
        人.append(t["谁"])

print(f"{'说话人':<12} {'句数':>4}  查表键 → 命中")
print("─" * 92)
坏 = 0
for n in 人:
    键们 = next(t["查"] for t in 表 if t["谁"] == n)
    数 = sum(1 for t in 表 if t["谁"] == n)
    命中, 源 = None, ""
    for k in 键们:
        try:
            色, 源 = 配音.角色定音色(k)
        except Exception:  # noqa: BLE001
            continue
        if not 源:          # 空源 = 没命中映射，只是把输入原样吐回来
            continue
        命中 = (k, 色)
        break
    if 命中:
        k, 色 = 命中
        标 = "✓" if k == 键们[0] else "⚠ 退到了括号外的名字"
        print(f"{n:<12} {数:>4}  {键们} → {k} [{源}] {标}")
        print(f"{'':<12}      {色}")
    else:
        坏 += 1
        print(f"{n:<12} {数:>4}  {键们} → ✗ 一个都没命中")

print(f"\n{len(人)} 个说话人，{坏} 个没解析出来")

# 时间轴预览
步 = 4.56 - 0.5
print(f"\n时间轴（每段 4.56s − 转场 0.5s = 步长 {步}s，成片 {45*4.56 - 44*0.5:.2f}s）：")
for t in 表[:8]:
    起 = (t["格"] - 1) * 步 + 0.7
    print(f"  格{t['格']:>2} @{起:>7.2f}s  [{t['谁']}] {t['文本'][:34]}")
print(f"  … 共 {len(表)} 句")
