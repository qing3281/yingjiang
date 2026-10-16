# -*- coding: utf-8 -*-
import io, sys, py_compile
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\DSHworkspace\影匠\编剧.py"
s = io.open(p, encoding="utf-8").read()

旧 = """    句 = []
    空场 = 0
    for b in 场块:
        if "无台词" in b:
            空场 += 1
            continue
        for 行 in b.split("\\n"):
            行 = 行.strip()
            if not 行.startswith(("-", "*")):
                continue
            t = re.sub(r"^[-*]\\s*", "", 行)
            t = re.sub(r"^[^：:]{1,12}[：:]", "", t)      # 去掉「老陈：」
"""
新 = """    句 = []
    空场 = 0
    谁在说 = []          # ★ 记下每一句是谁说的 —— 用来查「有名有姓的人一句都没有」
    for b in 场块:
        if "无台词" in b:
            空场 += 1
            continue
        for 行 in b.split("\\n"):
            行 = 行.strip()
            if not 行.startswith(("-", "*")):
                continue
            t = re.sub(r"^[-*]\\s*", "", 行)
            _m = re.match(r"^([^：:]{1,12})[：:]", t)      # 「老陈：」 → 记下老陈
            if _m:
                谁在说.append(_m.group(1).strip())
            t = re.sub(r"^[^：:]{1,12}[：:]", "", t)      # 去掉「老陈：」
"""
assert 旧 in s, "没找到台词解析那段"
s = s.replace(旧, 新, 1)

锚 = """    if n["场数"] and n["台词句数"] == 0:
        问.append("一句台词都没有（第 4 步可能没跑）")
"""
加 = 锚 + """
    # ★ 有名有姓的人，不能一句都不说 —— 实战踩到：耶梦加得（龙）从头到尾零台词，
    #   自检却报「过」；只看句数的检查量不出「谁没说」。
    #   例外：故意不说话的（哑巴/婴儿/动物/旁白型）就在人物描述里写「不说话」三个字。
    净名 = [re.split(r"[（(]", k)[0].strip() for k in 人]
    哑的 = [k for k in 人 if "不说话" in k]
    句都没 = [a for a in 净名 if a and a not in 谁在说
             and not any(a in x for x in 哑的)]
    n["不说话的"] = 句都没
    if len(净名) >= 2 and 句都没:
        问.append("%s 一句台词都没有 —— 两个人斗了 8 场，对面不能是块石头"
                  "（真不会说话就写在人物描述里加「不说话」三个字）" % "、".join(句都没))
"""
assert 锚 in s, "没找到台词句数判据"
s = s.replace(锚, 加, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
py_compile.compile(p, doraise=True)
print("  ✓ 自检多一条：谁一句都没说")
