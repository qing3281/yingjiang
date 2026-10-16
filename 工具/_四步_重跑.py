# -*- coding: utf-8 -*-
"""四步 + 自检回喂重跑（带上下游联动）。"""
import io, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 编剧

戏名 = "楚子航耶梦加得"
素材 = ("楚子航（师兄，用刀，跑得快，右手缠着绷带）在雨夜的跨江大桥上，"
        "拦下了龙王耶梦加得 —— 就是当年吞掉他全家的那条龙。他只有一次机会。")
套路, 分钟, 人数, 秒 = "起承转合", 3, 2, 180
出 = r"D:\DSHworkspace\影匠\作品\_剧本试验\楚子航_四步.md"
段 = {}

def 归谁(t):
    if "场" in t or "变化" in t: return 3
    if "台词" in t or "广播剧" in t or "说话" in t: return 4
    if "人物" in t or "识别特征" in t or "性格" in t: return 2
    return 1

def 跑步(n, 补=""):
    t = time.time()
    if n == 1:   r = 编剧.第一步_梗概(素材, 套路, 分钟=分钟, 人数=人数, 补=补)
    elif n == 2: r = 编剧.第二步_人物(段[1]["文"], 人数, 补=补)
    elif n == 3: r = 编剧.第三步_分场(段[1]["文"], 段[2]["文"], 套路, 秒, 补=补)
    else:        r = 编剧.第四步_台词(段[3]["文"], 补=补)
    if not r.get("ok"): return None
    段[n] = r
    print("   ✓ 第 %d 步　%5.1f 秒　%5d 字符%s" % (n, time.time()-t, len(r["文"]),
          ("　← 回喂：" + 补[:36]) if 补 else ""))
    return r

def 拼(): return 编剧.拼成一本(戏名, 段[1]["文"], 段[2]["文"], 段[3]["文"], 段[4]["文"])

步1补 = ("主角就叫「楚子航」，龙就叫「耶梦加得」，不要改名。"
        "结局不能是他放弃 —— 他是来杀龙的，最后一刀必须砍中，龙必须死。"
        "可以付出代价（右手废了、刀弯了），但不能空手走开。")
步4补 = ("耶梦加得（那条龙）要说话 —— 它是龙王不是野兽。给它 2–3 句，冷、短、居高临下。"
        "不要让楚子航一个人自说自话。台词总数不超过 12 句。")

print("══ 第一遍 ══")
for n in (1, 2, 3, 4):
    if not 跑步(n, 补={1: 步1补, 4: 步4补}.get(n, "")):
        print("   ✗ 第 %d 步失败" % n); raise SystemExit(1)

for 轮 in range(1, 5):
    本 = 拼(); 查 = 编剧.自检(本)
    print("\n══ 第 %d 遍自检：%s ══" % (轮, "过 ✓" if 查["过"] else "没过（%d 条）" % len(查["问题"])))
    for x in 查["问题"]: print("   ⚠ " + x)
    if 查["过"]: break
    哪 = 归谁(查["问题"][0])
    同 = [x for x in 查["问题"] if 归谁(x) == 哪]
    print("   → 回喂给第 %d 步" % 哪)
    if not 跑步(哪, 补="；".join(同)): print("   ✗ 重跑失败"); break
    for n in range(哪 + 1, 5):
        print("   （上游动了，第 %d 步跟着重跑）" % n)
        if not 跑步(n): break

本 = 拼()
io.open(出, "w", encoding="utf-8", newline="\n").write(本)
查 = 编剧.自检(本)
print("\n── 最终：%s ──　写盘 %d 字节" % ("过 ✓" if 查["过"] else "没过", os.path.getsize(出)))
for k, v in 查["数字"].items(): print("   %-14s %s" % (k, v))
for x in 查["问题"]: print("   ⚠ " + x)
