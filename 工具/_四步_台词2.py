# -*- coding: utf-8 -*-
import importlib.util, io, sys
sys.stdout.reconfigure(encoding="utf-8")
def 装(名, 路):
    sp = importlib.util.spec_from_file_location(名, 路)
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
编 = 装("编", r"D:\DSHworkspace\影匠\编剧.py")
根 = r"D:\DSHworkspace\影匠\作品\_剧本试验"
本 = io.open(根 + r"\楚子航_四步.md", encoding="utf-8").read()
补 = ("耶梦加得（那条龙）应该会说话 —— 它是龙王，不是野兽。"
      "给它 2–3 句，要冷、要短、要居高临下，比如「你哥哥也是这么砍的」这种。"
      "不要让楚子航一个人自说自话。台词总数仍不超过 12 句。")
r = 编.第四步_台词(本, 补=补)
io.open(根 + r"\楚子航_四步.md", "w", encoding="utf-8", newline="\n").write(r["文"])
print("  ✓ 重写台词", len(r["文"]), "字符")
查 = 编.自检(r["文"])
print("  自检：", "过 ✓" if 查["过"] else "没过")
for x in 查["问"]: print("     ⚠", x)
i = r["文"].find("## 台词")
print(r["文"][i:i+1200])
