# -*- coding: utf-8 -*-
"""
_压缩台账.py —— 压缩红线 + 压缩台账，两个都是量出来的，不靠我记。

为什么要它：
  · 用户 m20016：「你得保证你自己的压缩也能起到这个压缩的效果，你不能你的效果还比
    DSH 自带的还差了。」→ 所以我得知道自己压了多少、什么时候压的、压掉了多少。
  · 用户 m20438：「你得确保自己做了这个事儿。」→ 承诺不算数，得有东西替我查。

判据从哪来（★ 关键）：会话存档里每条 assistant/message 都带 usage：
    inputTokens    = 这一轮新进上下文的 token
    cacheReadTokens= 这一轮从缓存读回来的 token
    两个加起来 ≈ 这一轮喂进去的全部上下文
所以把一整场的 (input+cache) 按 seq 排成一条曲线，**每次曲线掉下来 = 发生过一次压缩**。
这是 DSH 自己记的，我改不了，所以能当证据。

实测（2026-10-15 02:30，本场 session-3129c57c）：
    5,817 个点，读完整场 0.4 秒
    历史最高 782,362 token
    ★ 一共 105 次掉下来（其中带「COMPRESSION CONFLICTS」的原生压缩是少数）
    典型掉落位置 110K~230K，单次砍掉 5 万~19 万

用法：
    python _压缩台账.py              只打当前段位（快，_开工.py 用这个）
    python _压缩台账.py --扫          扫全部场次，写台账
    python _压缩台账.py --看          打台账最近 20 条
    python _压缩台账.py --场 <id>     只看一场
"""
import os, io, re, sys, json, glob, time
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

会话根 = r"D:\DSH\home\sessions\--D-DSHworkspace--"
台账路 = os.path.join(os.path.dirname(os.path.abspath(__file__)), r"记忆\压缩台账.jsonl")

# ★ 红线（单位：token）。按上面实测的掉落分布定的：
#   大多数压缩发生在 110K~230K 之间，所以 120K 就要开始留意，180K 必须动手。
黄线 = 120_000
红线 = 180_000

重_in    = re.compile(r'"inputTokens":(\d+)')
重_cache = re.compile(r'"cacheReadTokens":(\d+)')
重_seq   = re.compile(r'"seq":(\d+)')
重_时    = re.compile(r'"time":(\d{13})')


def 读轨迹(存档路):
    """读一场的上下文曲线。返回 [(seq, 新, 缓存, 总)]"""
    try:
        import zstandard
    except ImportError:
        return []
    if not os.path.exists(存档路):
        return []
    轨 = []
    d = zstandard.ZstdDecompressor()
    try:
        with open(存档路, "rb") as fh:
            with d.stream_reader(fh) as r:
                for line in io.TextIOWrapper(r, encoding="utf-8"):
                    if '"usage"' not in line:
                        continue
                    m1 = 重_in.search(line); m2 = 重_cache.search(line)
                    if not (m1 and m2):
                        continue
                    i = int(m1.group(1)); c = int(m2.group(1)); n = i + c
                    if n <= 0:
                        continue
                    m3 = 重_seq.search(line)
                    轨.append((int(m3.group(1)) if m3 else 0, i, c, n))
    except Exception:
        return []
    return 轨


def 找压缩(轨):
    """曲线掉下来 >=30% 就算一次压缩。返回 [(seq, 前, 后)]"""
    出 = []; 前 = 0
    for seq, i, c, n in 轨:
        if 前 and n < 前 * 0.7:
            出.append((seq, 前, n))
        前 = n
    return 出


def 找场():
    """所有场次，按修改时间倒序。返回 [(id, 存档路, mtime)]"""
    出 = []
    for p in glob.glob(os.path.join(会话根, "*")):
        f = os.path.join(p, "session.v4.jsonl.zstd")
        if os.path.exists(f):
            出.append((os.path.basename(p), f, os.path.getmtime(f)))
    return sorted(出, key=lambda x: x[2], reverse=True)


def 当前段位():
    """最新那一场的当前上下文。返回 dict 或 None。
    ★ 只认「正在长」的场：最近 5 分钟动过，或者是最大的那一场。"""
    场s = 找场()
    if not 场s:
        return None
    大 = max(场s, key=lambda x: os.path.getsize(x[1]))
    现在 = time.time()
    选 = None
    for 名, 路, mt in 场s:
        if now_ok(mt, 现在) and os.path.getsize(路) > 500_000:
            选 = (名, 路, mt); break
    if 选 is None:
        选 = 大
    名, 路, mt = 选
    轨 = 读轨迹(路)
    if not 轨:
        return None
    return {"场": 名, "路": 路, "时": mt, "当前": 轨[-1][3],
            "最高": max(t[3] for t in 轨), "点数": len(轨),
            "压缩次数": len(找压缩(轨))}


def now_ok(mt, 现在):
    return (现在 - mt) < 300


def 段位话(信):
    """把段位说成人话。返回 (等级, 一行字)"""
    if not 信:
        return "?", "读不到当前段位（存档为空或 zstandard 没装）"
    n = 信["当前"]
    if n >= 红线:
        级 = "✗"
        话 = (f"★ 红线！当前 {n:,} token，已过 {红线:,}。**这一轮必须压缩**，"
              f"不然 DSH 自带压缩会自己动手，压完原文就取不回来了。")
    elif n >= 黄线:
        级 = "⚠"
        话 = (f"当前 {n:,} token，过了黄线 {黄线:,}。"
              f"**这一轮做完就压**，别等它自己动手。")
    else:
        级 = "✓"
        话 = f"当前 {n:,} token，离黄线 {黄线:,} 还差 {黄线-n:,}。"
    话 += (f"（本场最高到过 {信['最高']:,}，已经掉下来 {信['压缩次数']} 次）")
    return 级, 话


def 写台账():
    """扫全部场次，把每一次压缩记成一行。按 (场, seq) 去重，只追加。"""
    旧 = set()
    if os.path.exists(台账路):
        for ln in io.open(台账路, encoding="utf-8"):
            try:
                o = json.loads(ln)
                旧.add((o.get("场"), o.get("seq")))
            except Exception:
                pass
    新 = []
    for 名, 路, mt in 找场():
        for seq, 前, 后 in 找压缩(读轨迹(路)):
            if (名, seq) in 旧:
                continue
            新.append({"场": 名, "seq": seq,
                       "时": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt)),
                       "压前": 前, "压后": 后, "砍掉": 前 - 后})
    新.sort(key=lambda o: (o["时"], o["seq"]))
    os.makedirs(os.path.dirname(台账路), exist_ok=True)
    with io.open(台账路, "a", encoding="utf-8") as f:
        for o in 新:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    return 新


def 看台账(条=20):
    if not os.path.exists(台账路):
        return []
    rows = []
    for ln in io.open(台账路, encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    return rows[-条:]


def 总账():
    rows = 看台账(10 ** 9)
    if not rows:
        return None
    return {"次数": len(rows), "砍掉合计": sum(r.get("砍掉", 0) for r in rows),
            "最早": rows[0].get("时"), "最晚": rows[-1].get("时"),
            "涉及场次": len(set(r.get("场") for r in rows))}


def 主():
    a = sys.argv[1:]
    if not a:
        _, 话 = 段位话(当前段位())
        print(话)
        return
    if a[0] == "--扫":
        print("扫全部场次（这要读几十个存档，可能要一会儿）…")
        t0 = time.time()
        新 = 写台账()
        print(f"  用了 {time.time()-t0:.1f} 秒，新记 {len(新)} 次压缩")
        账 = 总账()
        if 账:
            print(f"  台账一共 {账['次数']} 次，砍掉合计 {账['砍掉合计']:,} token")
            print(f"  涉及 {账['涉及场次']} 场，{账['最早']} → {账['最晚']}")
        return
    if a[0] == "--看":
        for r in 看台账(20):
            print(f"  {r['时']}  seq={r['seq']:<7} {r['压前']:>9,} → {r['压后']:>8,}"
                  f"  砍掉 {r['砍掉']:>8,}   {r['场'][:30]}")
        return
    if a[0] == "--场" and len(a) > 1:
        名 = a[1]
        路 = os.path.join(会话根, 名, "session.v4.jsonl.zstd")
        轨 = 读轨迹(路)
        print(f"{名}：{len(轨)} 个点，{len(找压缩(轨))} 次压缩")
        for seq, 前, 后 in 找压缩(轨)[-20:]:
            print(f"  seq={seq:<7} {前:>9,} → {后:>8,}  （砍掉 {前-后:,}）")
        return
    print(__doc__)


if __name__ == "__main__":
    主()
