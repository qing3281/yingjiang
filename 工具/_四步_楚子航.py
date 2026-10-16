# -*- coding: utf-8 -*-
"""四步剧本 + 自检回喂重跑。楚子航 · 耶梦加得（3 分钟 · 战斗）
★ 病名要说给模型听，重跑才不是抽奖（第三步第一次只分了 4 场，重跑还是 4 场）。"""
import io, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 编剧

戏名 = "楚子航耶梦加得"
素材 = ("楚子航（师兄，用刀，跑得快，右手缠着绷带）在雨夜的跨江大桥上，"
        "拦下了龙王耶梦加得 —— 就是当年吞掉他全家的那条龙。他只有一次机会。")
套路 = "起承转合"
分钟, 人数, 秒 = 3, 2, 180
出 = os.path.join(r"D:\DSHworkspace\影匠\作品\_剧本试验", "楚子航_四步.md")

# 病名 → 该重跑哪一步
def 归谁(问题):
    t = 问题
    if "场" in t or "变化" in t: return 3
    if "台词" in t or "广播剧" in t: return 4
    if "人物" in t or "识别特征" in t or "性格" in t: return 2
    return 1

段, 用 = {}, {}

def 跑步(n, 补=""):
    t = time.time()
    if n == 1:
        段["梗概"] = 编剧.第一步_梗概(素材, 套路, 分钟=分钟, 人数=人数, 补=补)
        r = 段["梗概"]; 用["套路"] = r.get("套路", 套路)
    elif n == 2:
        r = 段["人物"] = 编剧.第二步_人物(段["梗概"]["文"], 人数, 补=补)
    elif n == 3:
        r = 段["分场"] = 编剧.第三步_分场(段["梗概"]["文"], 段["人物"]["文"], 套路, 秒, 补=补)
    else:
        r = 段["台词"] = 编剧.第四步_台词(段["分场"]["文"], 补=补)
    if not r.get("ok"):
        return None
    段["_%d" % n] = r["文"]
    print("   ✓ 第 %d 步　%5.1f 秒　%5d 字符%s" % (n, time.time()-t, len(r["文"]),
          ("　← 回喂重跑：" + 补[:40]) if 补 else ""))
    return r

def 拼():
    return 编剧.拼成一本(戏名, 段["_1"], 段["_2"], 段["_3"], 段["_4"])

print("══ 第一遍 ══")
# ★ 上一版结局是「他放弃追击、空手走开」—— 那不是战斗片该有的收尾。病名说给模型听。
病 = ("上一版结局是主角把刀插回桥面、转身走开，放弃了 —— 这不行。"
      "他是来杀这条龙的，最后一刀必须砍中它，龙必须死。"
      "可以让他付出代价（右手不能用了、刀断了、他自己也重伤），但他不能空手走开。"
      "落点要落在「龙死了 + 他付出了什么」上。")
for n in (1, 2, 3, 4):
    if not 跑步(n, 补=病 if n == 1 else ""): print("   ✗ 第 %d 步失败" % n); raise SystemExit

for 轮 in range(1, 5):
    本 = 拼(); 查 = 编剧.自检(本)
    print()
    print("══ 第 %d 遍自检：%s ══" % (轮, "过 ✓" if 查["过"] else "没过（%d 条）" % len(查["问题"])))
    for x in 查["问题"]: print("   ⚠ " + x)
    if 查["过"]:
        break
    # 按病归步，一次只回喂一条最靠前的
    改哪步 = 归谁(查["问题"][0])
    同 = [x for x in 查["问题"] if 归谁(x) == 改哪步]
    print("   → 回喂给第 %d 步重跑" % 改哪步)
    if not 跑步(改哪步, 补="；".join(同)):
        print("   ✗ 重跑失败"); break
    if 改哪步 == 1 and 用.get("套路"):
        套路 = 用["套路"]
    # 上游改了，下游要跟着重跑
    for n in range(改哪步 + 1, 5):
        print("   （上游动了，第 %d 步跟着重跑）" % n)
        if not 跑步(n): break

本 = 拼()
io.open(出, "w", encoding="utf-8", newline=chr(10)).write(本)
查 = 编剧.自检(本)
print()
print("── 最终：%s ──" % ("过 ✓" if 查["过"] else "没过"))
for k, v in 查["数字"].items(): print("   %-14s %s" % (k, v))
for x in 查["问题"]: print("   ⚠ " + x)
print("   写盘", 出, os.path.getsize(出), "字节")
print()
print("════════ 梗概 ════════"); print(段["_1"])
print("════════ 人物 ════════"); print(段["_2"])
print("════════ 分场 ════════"); print(段["_3"])
