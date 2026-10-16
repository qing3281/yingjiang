# -*- coding: utf-8 -*-
"""开台 —— 双击桌面快捷方式时跑的就是它。

## 为什么要有它

用户 2026-10-15 01:20 的原话：

    我不是说过嘛？我不是特别喜欢这样的一个。一个小的网站或者是一个什么样的方式。
    那么假如哪天我把这个网址给忘了呢，好麻烦呀。
    你能不能用点别的方式？比如说能在桌面上给我建个快捷方式也好，或者是什么别的什么也行。

**他要的是：不记网址，双击就能看。**

所以这个脚本干三件事，而且**每次都干**（不假设服务还活着）：

1. **端口上没人听就起一个**（后台起，不弹黑框）
2. **等它真的能应答**（连打 HTTP，直到 200 或超时 —— 不是 sleep 一个拍脑袋的秒数）
3. **开浏览器**

## 用法

    python _开台.py 记忆      # 记忆台   8792
    python _开台.py 影匠      # 影匠监工台 8791
    python _开台.py 记忆 --不起   # 只看状态，不起服务

★ 教训（写进 `记忆\\经验\\流程与脚本.md`）：**起服务类的验证至少连打 3 次。**
  所以这里等就绪用的是「连续 2 次都 200 才算好」，不是「打过一次就算好」。
"""
import argparse
import io
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 工具\ 的上一级 = 工作区根
PY = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

台 = {
    "记忆": {"口": 8792, "脚本": "_记忆台.py", "名": "记忆台"},
    # 2026-10-15：影匠台从「只读监工」换成「能操作的控台」。
    # 用户原话：「我能操控影匠自己生成视频吗？还是所有都得靠你？」
    # 只读那个还留着（_监工.py），要看得更细时可以单独起。
    "影匠": {"口": 8791, "脚本": os.path.join("影匠", "_控台.py"), "名": "影匠控制台"},
    "监工": {"口": 8793, "脚本": os.path.join("影匠", "_监工.py"),
             "名": "影匠监工台（只读，看细节）", "参": ["--戏", "觉醒"]},
}


def 在听(口):
    import socket
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", 口))
        return True
    except Exception:
        return False
    finally:
        s.close()


def 能应答(口, 超时=15):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api" % 口, timeout=超时) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("哪个", choices=sorted(台))
    ap.add_argument("--不起", action="store_true", help="只报状态，不起服务")
    ap.add_argument("--等", type=int, default=240, help="最多等多少秒")
    参 = ap.parse_args()

    信 = 台[参.哪个]
    口 = 信["口"]
    print("  ══ %s　http://127.0.0.1:%d/" % (信["名"], 口))

    if not 在听(口):
        if 参.不起:
            print("  ✗ 端口上没人听（--不起，不动手）")
            return 1
        if not os.path.isfile(PY):
            print("  ✗ 找不到 python：%s" % PY)
            return 1
        脚本 = os.path.join(根, 信["脚本"])
        if not os.path.isfile(脚本):
            print("  ✗ 找不到脚本：%s" % 脚本)
            return 1
        print("  服务没在跑，起一个……")
        出 = os.path.join(根, "_%s.out.txt" % 信["名"])
        错 = os.path.join(根, "_%s.err.txt" % 信["名"])
        cmd = [PY, "-X", "utf8", "-u", 脚本, "--口", str(口)] + 信.get("参", [])
        subprocess.Popen(cmd, cwd=根, stdout=open(出, "wb"), stderr=open(错, "wb"),
                         creationflags=0x00000008 | 0x08000000)  # DETACHED | NO_WINDOW
    else:
        print("  服务已经在跑。")

    # ── 等就绪：连续 2 次都 200 才算好
    好 = 0
    起 = time.time()
    while time.time() - 起 < 参.等:
        if 能应答(口):
            好 += 1
            if 好 >= 2:
                break
        else:
            好 = 0
        time.sleep(2)
    if 好 < 2:
        print("  ✗ 等了 %d 秒还没就绪，去看 _%s.err.txt" % (参.等, 信["名"]))
        return 1

    址 = "http://127.0.0.1:%d/" % 口
    print("  ✓ 就绪　%s　（%.1f 秒）" % (址, time.time() - 起))

    # ── 开浏览器
    try:
        os.startfile(址)
        print("  ✓ 已经用默认浏览器打开")
    except Exception as e:
        print("  ✗ 开不了浏览器（%s）—— 自己敲这个地址：%s" % (e, 址))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
