import sys, os, re, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 剧组
根 = r"D:\DSHworkspace\影匠\作品\楚子航"
九 = 剧组.解析九宫格(os.path.join(根, "02-九宫格.md"))
卡 = [c["名"] if isinstance(c, dict) else c[0] for c in 九["角色卡"]]
规格 = importlib.util.spec_from_file_location("规约", os.path.join(根, "_写作规约.py"))
规约 = importlib.util.module_from_spec(规格); 规格.loader.exec_module(规约)

公告 = {  # 公共段落：每格都会拼进去，里面不许有人名/人称代词/负面词
 "龙化档": 规约.龙化档, "爆血档": 规约.爆血档, "损伤档": 规约.损伤档,
 "场景": 规约.场景, "场景光": 规约.场景光,
}
for k, v in 九["视觉规范"].items(): 公告["视觉规范." + k] = v
for c in 九["角色卡"]: 公告["角色卡." + (c["名"] if isinstance(c, dict) else c[0])] = c["描述"] if isinstance(c, dict) else c[1]

坏 = []
def 记(类, 哪, 证):
    坏.append((类, 哪, 证))

# ══ 1. 公共段落：人名 / 人称代词 / 负面词 / 被否掉的东西
人名们 = ("楚子航", "夏弥", "路明非", "耶梦加得", "芬里厄")
代词们 = ("他", "她", "它", "他们", "她们")
负面们 = ("没有", "不是", "不再", "不许", "不要", "别 ", "无法", "消失")
忌讳 = ("灯", "尖耳", "骨翼", "黑红", "青绿色", "摄影机", "拱顶", "煤渣", "轨枕", "碎石", "道砟", "蛇形", "上下颚又长又薄")
for 名, 值 in 公告.items():
    文 = 值 if isinstance(值, str) else " ".join(str(x) for x in (值.values() if isinstance(值, dict) else 值))
    for w in 人名们:
        if w in 文: 记("①公共段落里有人名", 名, w)
    for w in 忌讳:
        if w in 文: 记("②公共段落里有忌讳词", 名, w)
    for w in 负面们:
        if w in 文 and 名 not in ("场景光",): 记("③公共段落里有负面词", 名, w)

# ══ 2. 逐格
指代 = ("一个女孩","一个男生","一个男人","一个少年","一个女生","一个身影","一个人","那个女孩","一只小手","一只手")
for g in 九["格们"]:
    号, t = g["号"], g["提示词"]
    位置, 画面 = g.get("位置",""), g.get("画面","")
    名在位置 = [n for n in 卡 if n in 位置]
    名在画面 = [n for n in 卡 if n in 画面]
    # ⓵ 无名指代
    for w in 指代:
        if w in 画面 and 名在位置: 记("④无名指代（会画成两个人）", "格%d" % 号, "%s 在画面里但位置里是%s" % (w, 名在位置))
        if w in 位置 and 名在画面: 记("④无名指代（会画成两个人）", "格%d" % 号, "%s 在位置里但画面里是%s" % (w, 名在画面))
    # ⓶ 位置和画面各描述同一个人一次以上（两个夏弥的另一个来源）
    for n in 卡:
        if n in 位置 and n in 画面 and 号 not in (1,):
            pass  # 同一个人在两段里都点名是允许的（必须同名），不算错
    # ⓷ 比喻
    for w in ("仿佛","宛如","好像","如同","似的","像一","像被","像是"):
        if w in t: 记("⑤比喻（模型画不出来）", "格%d" % 号, w)
    # ⓸ 负面词
    for w in ("没有别人","没有任何","不再","不许","不要"):
        if w in t and w != "没有别人":
            记("⑥负面词", "格%d" % 号, w)
    # ⓹ 忌讳词
    for w in 忌讳:
        if w in t: 记("⑦忌讳词", "格%d" % 号, w)
    # ⓺ 形态档该有有没有
    谁在 = [n for n in ("楚子航","夏弥","路明非") if n in (位置 + 画面)]
    if "夏弥" in 谁在 and g["衣"] and not 规约.龙化档.get(g["衣"]): 记("⑧龙化档缺失", "格%d" % 号, "衣=%s" % g["衣"])
    if "楚子航" in 谁在 and g.get("血") and not 规约.爆血档.get(g["血"]): 记("⑨爆血档缺失", "格%d" % 号, "血=%s" % g["血"])
    # ⓻ 挑角色对不对
    选, 备 = 剧组.挑角色(t, 卡)
    出现 = [n for n in 卡 if n in t]
    if sorted(选) != sorted(出现): 记("⑩挑角色与出现的人不一致", "格%d" % 号, "选=%s 文本里=%s" % (选, 出现))
    if 备: 记("⑪走了「全体角色」兜底档", "格%d" % 号, 备[:30])

print("═" * 70)
if not 坏:
    print("  ✓ 17 条判据全过")
else:
    from collections import defaultdict
    d = defaultdict(list)
    for 类, 哪, 证 in 坏: d[类].append((哪, 证))
    for 类 in sorted(d):
        print("\n【%s】共 %d 处" % (类, len(d[类])))
        for 哪, 证 in d[类][:14]:
            print("    %-8s %s" % (哪, 证))
        if len(d[类]) > 14: print("    …… 还有 %d 处" % (len(d[类]) - 14))
print("\n" + "═" * 70)
print("  合计 %d 处" % len(坏))
