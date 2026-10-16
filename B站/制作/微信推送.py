# -*- coding: utf-8 -*-
"""微信推送 —— 把剧本 / 图片 / 视频发到用户手机上。

用户 m03366：「我之后要上班了，我需要你通过微信给我发剧本，图片，视频这些东西」

## 为什么选企业微信群机器人

对比过的几条路：

| 方案 | 能发图片 | 能发视频 | 需要什么 | 缺点 |
|---|---|---|---|---|
| **企业微信群机器人** ✅ | ✅ | ✅（当文件发） | 一个 webhook URL | 只能发不能收 |
| 企业微信自建应用 | ✅ | ✅ | corpid+secret+agentid | 收消息要公网回调 |
| WxPusher 极简推送 | 只能挂外链 | ❌ | 扫个码拿 SPT | 图片要公网 URL |
| WxPusher 微信 ClawBot | ❌ | ❌ | 装 App + 绑定 | 24h 只能收 10 条 |

群机器人只要**一个 URL**，就能发文本 / markdown / 图片（base64 内嵌，≤2MB）/ 文件（含 mp4，≤20MB）。
再在企业微信后台开「微信插件」，消息就直接落到**微信**里 —— 这就是用户要的效果。

## 配置

第一次用之前，把 webhook 填进 `D:\\DSHworkspace\\B站\\制作\\微信配置.json`：

```json
{
  "企业微信机器人": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key",
  "wxpusher_spt": "",
  "默认发件": "企业微信机器人"
}
```

`微信配置.json` 不进 git、不打印出来。

## 命令行

```bash
python 微信推送.py --文本 "今天出片 30 镜"
python 微信推送.py --md "# 进度\\n- 出图 12/30"
python 微信推送.py --图 D:\\path\\a.png
python 微信推送.py --文件 D:\\path\\成片.mp4
python 微信推送.py --测
```
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import sys
import urllib.parse
import urllib.request

配置路 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "微信配置.json")

图片上限 = 2 * 1024 * 1024          # 企业微信 image 消息 base64 上限 2MB
文件上限 = 20 * 1024 * 1024         # 群机器人 upload_media 上限 20MB


def 读配置() -> dict:
    if not os.path.isfile(配置路):
        return {}
    try:
        with open(配置路, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠ 配置读不动：{e}")
        return {}


def 存配置(c: dict) -> None:
    with open(配置路, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    print(f"✓ 配置写到 {配置路}")


def _post(url: str, 数据: dict | None = None, 原始: bytes | None = None,
          头: dict | None = None, 超时=60) -> dict:
    if 原始 is not None:
        body = 原始
    else:
        body = json.dumps(数据, ensure_ascii=False).encode("utf-8")
        头 = {"Content-Type": "application/json", **(头 or {})}
    req = urllib.request.Request(url, data=body, headers=头 or {})
    with urllib.request.urlopen(req, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


# ────────────────────────── 企业微信群机器人 ──────────────────────────

def 企微_webhook() -> str | None:
    c = 读配置()
    w = (c.get("企业微信机器人") or "").strip()
    if not w or "你的key" in w:
        return None
    return w


def 企微发(负载: dict, 静默=False) -> bool:
    w = 企微_webhook()
    if not w:
        print("❌ 还没配企业微信机器人 webhook（见 微信配置.json）")
        return False
    try:
        r = _post(w, 负载)
    except Exception as e:
        print(f"❌ 发送失败：{e}")
        return False
    ok = r.get("errcode") == 0
    if not 静默:
        print(("✓ 已发送" if ok else f"❌ {r}"))
    return ok


def 企微_文本(内容: str, 提到所有人=False, 静默=False) -> bool:
    t = {"content": 内容}
    if 提到所有人:
        t["mentioned_list"] = ["@all"]
    return 企微发({"msgtype": "text", "text": t}, 静默)


def 企微_md(内容: str, 静默=False) -> bool:
    return 企微发({"msgtype": "markdown", "markdown": {"content": 内容}}, 静默)


def 企微_图(路: str, 静默=False) -> bool:
    if not os.path.isfile(路):
        print(f"❌ 没有这个文件：{路}")
        return False
    n = os.path.getsize(路)
    if n > 图片上限:
        print(f"⚠ 图 {n/1048576:.1f}MB 超过 2MB 上限，自动降级成文件发送")
        return 企微_文件(路, 静默)
    with open(路, "rb") as f:
        原始 = f.read()
    return 企微发({
        "msgtype": "image",
        "image": {
            "base64": base64.b64encode(原始).decode(),
            "md5": hashlib.md5(原始).hexdigest(),
        },
    }, 静默)


def 企微_文件(路: str, 静默=False) -> bool:
    """群机器人的 upload_media 只认 type=file；mp4 也当文件发，微信里点开就能播。"""
    w = 企微_webhook()
    if not w:
        print("❌ 还没配企业微信机器人 webhook")
        return False
    if not os.path.isfile(路):
        print(f"❌ 没有这个文件：{路}")
        return False
    n = os.path.getsize(路)
    if n > 文件上限:
        print(f"❌ 文件 {n/1048576:.1f}MB 超过 20MB 上限，发不了")
        return False

    名 = os.path.basename(路)
    边 = "----dsh" + hashlib.md5(os.urandom(16)).hexdigest()[:16]
    类型 = mimetypes.guess_type(名)[0] or "application/octet-stream"
    with open(路, "rb") as f:
        内容 = f.read()

    体 = b""
    体 += f"--{边}\r\n".encode()
    体 += f'Content-Disposition: form-data; name="media"; filename="{名}"\r\n'.encode()
    体 += f"Content-Type: {类型}\r\n\r\n".encode()
    体 += 内容
    体 += f"\r\n--{边}--\r\n".encode()

    上传 = w.replace("/webhook/send?", "/webhook/upload_media?") + "&type=file"
    try:
        r = _post(上传, 原始=体,
                  头={"Content-Type": f"multipart/form-data; boundary={边}"}, 超时=300)
    except Exception as e:
        print(f"❌ 上传失败：{e}")
        return False
    if r.get("errcode") != 0:
        print(f"❌ 上传被拒：{r}")
        return False
    return 企微发({"msgtype": "file", "file": {"media_id": r["media_id"]}}, 静默)


# ────────────────────────── WxPusher（备用通道） ──────────────────────────

def wx_spt() -> str | None:
    c = 读配置()
    s = (c.get("wxpusher_spt") or "").strip()
    return s or None


def wx发(内容: str, 类型=2, 摘要="", 静默=False) -> bool:
    """类型 1=纯文本 2=HTML 3=markdown。WxPusher 只能发文字/HTML，图片要挂外链。"""
    s = wx_spt()
    if not s:
        print("❌ 还没配 wxpusher_spt")
        return False
    负载 = {"content": 内容, "contentType": 类型,
            "summary": 摘要 or 内容[:60], "verifyPayType": 0}
    try:
        r = _post(f"https://wxpusher.zjiecode.com/api/send/message/simple-push?spt={s}",
                  负载)
    except Exception as e:
        print(f"❌ 发送失败：{e}")
        return False
    ok = r.get("code") == 1000
    if not 静默:
        print("✓ 已发送" if ok else f"❌ {r}")
    return ok


# ────────────────────────── 统一入口 ──────────────────────────

def 发(内容: str, 图: list[str] | None = None, 文件: list[str] | None = None,
      静默=False) -> bool:
    """一条龙：先发文字，再发图，最后发文件。走企微；没配就退到 WxPusher。"""
    成 = True
    if 内容:
        if 企微_webhook():
            成 &= 企微_md(内容, 静默)
        elif wx_spt():
            成 &= wx发(内容.replace("\n", "<br/>"), 2, 静默=静默)
        else:
            print("❌ 两个通道都没配")
            成 = False
    for p in (图 or []):
        if not (企微_webhook() and 企微_图(p, 静默)):
            成 = False
    for p in (文件 or []):
        if not (企微_webhook() and 企微_文件(p, 静默)):
            成 = False
    return 成


def main() -> int:
    ap = argparse.ArgumentParser(description="把东西推到微信")
    ap.add_argument("--文本")
    ap.add_argument("--md")
    ap.add_argument("--图", nargs="*", default=[])
    ap.add_argument("--文件", nargs="*", default=[])
    ap.add_argument("--设机器人", help="写入企业微信机器人 webhook")
    ap.add_argument("--设SPT", help="写入 wxpusher SPT")
    ap.add_argument("--测", action="store_true", help="查配置 + 发一条测试")
    a = ap.parse_args()

    if a.设机器人 or a.设SPT:
        c = 读配置()
        if a.设机器人:
            c["企业微信机器人"] = a.设机器人.strip()
        if a.设SPT:
            c["wxpusher_spt"] = a.设SPT.strip()
        存配置(c)
        return 0

    if a.测:
        c = 读配置()
        print("配置文件 :", 配置路, "（存在" if os.path.isfile(配置路) else "（不存在")
        w = c.get("企业微信机器人", "")
        print("企微机器人:", (w[:60] + "…") if w else "（没配）")
        print("WxPusher :", "（配了）" if c.get("wxpusher_spt") else "（没配）")
        if not (企微_webhook() or wx_spt()):
            print("\n两个通道都没配 —— 按 微信配置.md 里的步骤做一遍再来。")
            return 1
        return 0 if 发("**《不烧心》推送通道测试**\n机器人已接通，后面剧本、图片、视频都走这里。") else 1

    if a.文本:
        return 0 if 企微_文本(a.文本) else 1
    if a.md:
        return 0 if 企微_md(a.md) else 1
    if a.图:
        return 0 if all(企微_图(p) for p in a.图) else 1
    if a.文件:
        return 0 if all(企微_文件(p) for p in a.文件) else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
