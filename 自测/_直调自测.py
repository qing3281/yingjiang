"""验控制台的「直调」这一路 —— 不起子进程，在控制台进程里把活干完。

★ 为什么要有这个文件：`直调活` 和 `_直调出段` 是我加的新机制，
   「代码看着对」不算数。这里用一个假的 `_出H3` 模块顶上去，真跑一遍，
   看三件事：
     ① `sys.argv` 有没有被摆成 `_出H3` 的 argparse 认的那个样子
     ② `_出H3.main()` 里的 `print()` 有没有真的进到控制台的日志缓冲
     ③ 跑完 `sys.argv` / `sys.stdout` 有没有**还原**（不还原的话，
        控制台自己后面的 print 就全跑进那个缓冲里去了 —— 静默的坏）
"""
import io
import os
import sys
import types
import importlib.util

根 = r"D:\DSHworkspace\影匠"
sys.path.insert(0, 根)

对 = 错 = 0


def 验(名, 条件, 实测=None):
    global 对, 错
    if 条件:
        对 += 1
        print(f"  ✓ {名}")
    else:
        错 += 1
        print(f"  ✗ {名}" + (f"　实测：{实测!r}" if 实测 is not None else ""))


# ── 把控制台整份读进来，但不要它起服务 ──
src = io.open(os.path.join(根, "_控台.py"), encoding="utf-8").read()
ns = {"__name__": "不是主体", "__file__": os.path.join(根, "_控台.py")}
exec(compile(src, "_控台.py", "exec"), ns)
直调活 = ns["直调活"]
_直调出段 = ns["_直调出段"]
_吐流 = ns["_吐流"]
任务表 = ns["任务表"]
查任务表 = ns["查任务表"]
控台根 = ns["根"]          # 控制台自己认的根（用来拼它那份 `脚本` 路径）
print(f"读到控制台 {len(src)} 字符\n")

# ── 假 `_出H3`：记下它看见的 argv，print 几行 ──
看见 = {}


def 假main():
    看见["argv"] = list(sys.argv)
    看见["stdout 类型"] = type(sys.stdout).__name__
    print("端点 远端 http://100.127.224.106:8188　1 格　1280×704 107帧 @24fps　8 步")
    print("  [1/1] ✓ 格17 372.4 秒  7.31 MB  手停在纸上")
    print("")
    print("★ 用时 372 秒 = 6.2 分")


假 = types.ModuleType("_出H3")
假.main = 假main
假.端点 = lambda 名: {"远端": "http://100.127.224.106:8188"}.get(名, "http://127.0.0.1:8188")
sys.modules["_出H3"] = 假

旧argv, 旧out = list(sys.argv), sys.stdout

print("【一】`_直调出段` 本身：argv 摆对了没、输出接住了没")
行 = []
_直调出段("觉醒", [17], "远端", 行.append)
验("假 main 被调到了", "argv" in 看见)
验("argv[0] 是脚本名", 看见.get("argv", [None])[0] == "_出H3.py", 看见.get("argv"))
验("戏在 argv 里", "觉醒" in 看见.get("argv", []), 看见.get("argv"))
验("端点摆成了 --端点 远端",
   "--端点" in 看见.get("argv", []) and
   看见["argv"][看见["argv"].index("--端点") + 1] == "远端", 看见.get("argv"))
验("格摆成了 --只格 17",
   "--只格" in 看见.get("argv", []) and
   看见["argv"][看见["argv"].index("--只格") + 1] == "17", 看见.get("argv"))
验("★ 跑的时候 sys.stdout 被换成了 _吐流", 看见.get("stdout 类型") == "_吐流",
   看见.get("stdout 类型"))
验("假 main print 的内容真的进了缓冲（3 行正文，空行不算）",
   sum(1 for x in 行 if "格17" in x or "用时" in x or "端点 远端" in x) == 3, 行)
验("「▸ 直调」那行在最前面", 行 and 行[0].startswith("▸ 直调"), 行[:1])

print("\n【二】★ 收尾还原：不还原的话控制台自己的 print 会被吞掉")
验("sys.argv 还原了", sys.argv == 旧argv, sys.argv)
验("sys.stdout 还原了", sys.stdout is 旧out, type(sys.stdout).__name__)

print("\n【三】`直调活`：状态机对不对")
日志 = []


def 干(吐):
    吐("第一行")
    吐("第二行")


活 = 直调活("直调·出段（远端）", 干, "说一句")
活._跑()          # 直接同步跑，不靠线程，好断言
验("干完之后 还活着() == False", 活.还活着() is False, 活.还活着())
验("退出码是 0", 活.码 == 0, 活.码)
快 = 活.快照()
验("快照有 说 字段", 快.get("说") == "说一句", 快.get("说"))
验("快照的 脚本 写明没有脚本文件", "无脚本文件" in 快.get("脚本", ""), 快.get("脚本"))
验("快照里能看到输出行", any("第一行" == x for x in 快.get("行", [])), 快.get("行"))
验("跑完打了一行 ✓ 干完了", any("✓ 干完了" in x for x in 快.get("行", [])), None)

print("\n【四】★ 出错的时候：异常不能把线程吞掉，要留下类型和 traceback")
def 会炸(吐):
    raise ValueError("这是故意的")

活2 = 直调活("会炸的活", 会炸)
活2._跑()
快2 = 活2.快照(尾=99)
验("退出码是 1", 活2.码 == 1, 活2.码)
验("说了是什么异常", any("ValueError" in x and "这是故意的" in x for x in 快2["行"]), 快2["行"][:3])
验("带了 traceback（有 File 行）", any(x.strip().startswith("File ") for x in 快2["行"]), None)
验("★ 出错了也不再报「在跑」", 活2.还活着() is False, 活2.还活着())

print("\n【五】任务表：直调的两条没有脚本、干 是函数")
for 名 in ("直调·出段（远端）", "直调·出段（本机）"):
    t = 任务表.get(名)
    验(f"{名} 在任务表里", t is not None)
    验(f"{名} 的 类 = 直调", t and t.get("类") == "直调", t and t.get("类"))
    验(f"{名} 没有 脚本 字段", t is not None and "脚本" not in t, t and t.keys())
    验(f"{名} 的 干 是可调用的", t and callable(t.get("干")))
验("进程类的活仍然有 脚本 字段（没被我改坏）",
   all("脚本" in 任务表[k] for k in ("出首帧", "出段·远端", "配音", "总装成片", "超分")))

print("\n【六】★ 任务表里的脚本文件是不是真的都在")
毛病 = 查任务表()
验("查任务表() 没有挑出毛病", 毛病 == [], 毛病)
for k in ("出首帧", "出段·远端", "出段·本机", "配音", "总装成片", "超分"):
    t = 任务表.get(k)
    if not t or t.get("类") == "直调":
        continue
    路 = os.path.normpath(os.path.join(控台根, t["脚本"]))
    验(f"{k} 的脚本真的在：{os.path.basename(路)}", os.path.isfile(路), 路)

sys.modules.pop("_出H3", None)
print(f"\n{'=' * 46}\n  过 {对}　错 {错}\n{'=' * 46}")
sys.exit(1 if 错 else 0)
