# -*- coding: utf-8 -*-
"""接尾：等本机把 1-40 跑完，本机接着跑尾巴几格（远端同时只跑到某个格为止）。

为什么要有这个脚本（2026-10-14 18:52 的调度算术）：
  本机 管 1-40，还剩 14 格 × 171.9 秒 → 19:27 收工
  远端 管 41-74，还剩 26 格 × 175.8 秒 → 20:03 收工
  **本机从 19:27 到 20:03 会空转 36 分钟**（约 12 格）= 白等。
  重新分配成「本机 20 格 + 远端 20 格」：
      本机 = 27-40（14）+ 69-74（6）→ 57.3 分钟 → 19:44
      远端 = 49-68（20）        → 58.6 分钟 → 19:46
  两边几乎同时收工，**省 17 分钟**。

判据：本机最后要出的是 `格40_本机.mp4`。它一出现，1-40 就跑完了。
      （不能用「进程在不在」判 —— `_出H3.py` 出完最后一格还会补日志、跑收尾。）
"""
import os
import subprocess
import sys
import time

根 = os.path.dirname(os.path.abspath(__file__))
段 = os.path.join(根, "作品", "觉醒", "段")
尾格 = [69, 70, 71, 72, 73, 74]
哨兵 = os.path.join(段, "格40_本机.mp4")
日志 = os.path.join(根, "作品", "觉醒", "_H3日志_本机_尾巴.txt")


def 已有(n: int) -> bool:
    p = os.path.join(段, f"格{n}_本机.mp4")
    return os.path.exists(p) and os.path.getsize(p) > 100_000


def main():
    最长 = 5400          # 最多等 90 分钟
    起 = time.time()
    print(f"=== 接尾守候：等 {os.path.basename(哨兵)} 出现 ===", flush=True)

    while time.time() - 起 < 最长:
        if os.path.exists(哨兵) and os.path.getsize(哨兵) > 100_000:
            print(f"  ✓ 1-40 跑完了（{time.strftime('%H:%M:%S')}）", flush=True)
            break
        已 = sum(1 for n in range(1, 41) if 已有(n))
        print(f"  {time.strftime('%H:%M:%S')}  1-40 已有 {已}/40", flush=True)
        time.sleep(120)
    else:
        print("  ✗ 等超时，放弃接尾", flush=True)
        return 1

    # 尾巴这几格可能远端已经抢跑了，跳掉已存在的
    要跑 = [n for n in 尾格 if not 已有(n)]
    if not 要跑:
        print("  ✓ 尾巴 6 格已经有了，不用跑", flush=True)
        return 0

    print(f"\n=== {time.strftime('%H:%M:%S')}  本机接尾巴：格 {要跑} ===", flush=True)
    py = sys.executable
    参 = [py, "-X", "utf8", "-u", os.path.join(根, "_出H3.py"), "觉醒",
          "--只格", ",".join(str(n) for n in 要跑), "--端点", "本机"]
    with open(日志, "w", encoding="utf-8") as f:
        f.write(" ".join(参) + "\n")
        f.flush()
        r = subprocess.run(参, stdout=f, stderr=subprocess.STDOUT, cwd=根)
    print(f"  退出码 {r.returncode}", flush=True)
    return r.returncode


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
