import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
d = r"D:\DSHworkspace\影匠\作品\楚子航"
names = ["01-节拍拆解.md", "02-九宫格.md", "03-四宫格.md", "04-动态提示词.md"]
for n in names:
    p = os.path.join(d, n)
    b = open(p, "rb").read()
    t = b.decode("utf-8")
    print(f"{n}  bytes={len(b)}  chars={len(t)}  lines={t.count(chr(10))+1}")
    # 格N 标题
    ge = re.findall(r"## 格(\d+) —— ", t)
    if ge:
        nums = [int(x) for x in ge]
        print("   格:", len(nums), "首个", nums[0], "末个", nums[-1],
              "连续" if nums == list(range(1, len(nums)+1)) else "★断号")
    print("   格出现次数:", len(re.findall(r"格\d+", t)))
print()
# 否定词扫描（只扫提示词行）
bad = ["不要", "没有", "无字", "别", "不能", "不会", "不再", "不许", "非", "莫", "勿", "未"]
for n in names:
    t = open(os.path.join(d, n), encoding="utf-8").read()
    hits = []
    for i, ln in enumerate(t.split("\n"), 1):
        if "提示词" in ln or "动作：" in ln:
            for w in bad:
                if w in ln:
                    hits.append((i, w, ln[:60]))
    print(n, "提示词/动作 行否定词命中:", len(hits))
    for h in hits:
        print("   ", h)
