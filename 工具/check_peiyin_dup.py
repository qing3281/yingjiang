# -*- coding: utf-8 -*-
"""查「不同台词配出来同一段音频」。
为什么：`_配音表.json` 里 #8 和 #9 的字节数、秒数一模一样（65068 B / 1.474 秒），
但 #8 是夏弥「别松开。」、#9 是路明非「小心！」—— 不同的人、不同的字数。
这种「看着正常、其实两句同一段声音」的错，只有比对内容哈希才抓得住。
"""
import hashlib, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航\配音"
果 = json.load(open(os.path.join(目, "_配音表.json"), encoding="utf-8"))
表 = 果.get("配音") or []

print("序号  文件                                   md5前10     秒      台词")
见 = {}
for it in sorted(表, key=lambda x: x.get("序号", 0)):
    p = it.get("路") or ""
    h = hashlib.md5(open(p, "rb").read()).hexdigest()[:10] if os.path.isfile(p) else "(缺)"
    t = (it.get("文本") or "")[:16]
    print("  #%-3s %-36s %s %7s  %s" % (it.get("序号"), os.path.basename(p), h, it.get("秒"), t))
    见.setdefault(h, []).append(it.get("序号"))

print()
撞 = [(h, v) for h, v in 见.items() if len(v) > 1 and h != "(缺)"]
print("★ 内容相同的 wav 组数：%d" % len(撞))
for h, v in 撞:
    print("   %s -> 序号 %s" % (h, sorted(v)))
    for 号 in sorted(v):
        it = [x for x in 表 if x.get("序号") == 号][0]
        print("        #%s  角色=%-6s  文本=%s" % (号, it.get("角色") or it.get("音色"), it.get("文本")))
sys.exit(0 if not 撞 else 1)
