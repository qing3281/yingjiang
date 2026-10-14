"""盯一眼影匠控制台里那个活 —— 起活 / 轮询 / 量产物。

用法：
    python _看着活.py 直调·出段（远端） 觉醒 17      # 起一个活并盯到它跑完
    python _看着活.py --就看看                        # 只看现在在跑什么

★ 键名是 `在跑`，不是 `活` —— 我一开始拿 `活` 去读，读到 None，
  就以为「活丢了、控制台出 bug 了」，跑去看进程、看端口、看远端队列，
  折腾了四轮。真相是 /api/state 顶层就是 `在跑`。（`话` 才是单条历史里的键名。）
  **判据：读别人的 JSON 之前先把顶层键打出来，别拿猜的键名去 or {}。**
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

口 = os.environ.get("控台口", "8791")
根 = f"http://127.0.0.1:{口}"


def 取(路):
    with urllib.request.urlopen(根 + 路, timeout=20) as r:
        return json.load(r)


def 状(戏="觉醒"):
    return 取("/api/state?" + urllib.parse.urlencode({"戏": 戏}))


def 看(活, 尾=8):
    名 = (活 or {}).get("名") or "（没有）"
    在跑 = (活 or {}).get("在跑")
    行 = (活 or {}).get("行") or []
    print(f"  ▸ {名}　在跑={在跑}　跑秒={(活 or {}).get('跑秒')}　退出码={(活 or {}).get('退出码')}")
    if 活:
        print(f"    脚本字段：{活.get('脚本')}")
    for s in 行[-尾:]:
        print("      ", s)


def 主():
    if len(sys.argv) >= 2 and sys.argv[1] == "--就看看":
        看(状().get("在跑"))
        return 0

    任 = sys.argv[1] if len(sys.argv) > 1 else "直调·出段（远端）"
    戏 = sys.argv[2] if len(sys.argv) > 2 else "觉醒"
    格 = sys.argv[3] if len(sys.argv) > 3 else "17"

    print(f"  起活前：")
    看(状(戏).get("在跑"))

    体 = json.dumps({"任务": 任, "戏": 戏, "格": 格}).encode()
    r = urllib.request.Request(根 + "/api/run", data=体,
                               headers={"Content-Type": "application/json"})
    print(f"\n  起活回：{json.load(urllib.request.urlopen(r, timeout=30))}\n")

    起 = time.time()
    上次 = ""
    while True:
        time.sleep(5)
        d = 状(戏)
        活 = d.get("在跑")
        if not 活:
            print("  ✗ 起完就没有活了 —— 服务可能重启过")
            return 1
        行 = 活.get("行") or []
        新 = 行[-1] if 行 else ""
        if 新 != 上次:
            print(f"  [{time.time() - 起:6.1f}s] {新}")
            上次 = 新
        if not 活.get("在跑"):
            print()
            看(活, 尾=12)
            print(f"\n  ★ 总共跑了 {time.time() - 起:.0f} 秒，退出码 {活.get('退出码')}")
            return 0 if 活.get("退出码") == 0 else 1
        if time.time() - 起 > 1500:
            print("  ✗ 超过 25 分钟还没完，不盯了")
            return 1


if __name__ == "__main__":
    sys.exit(主())
