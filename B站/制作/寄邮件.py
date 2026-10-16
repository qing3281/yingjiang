# -*- coding: utf-8 -*-
"""把剧本 / 图片 / 视频寄到 QQ 邮箱（或者任何支持 SMTP 的邮箱）。

为什么走邮件：不用管理员权限、不用改防火墙、不在家也能收。
QQ 邮箱单封 50 MB，超了就自动拆包或者压一版手机版。

配置：D:\\DSHworkspace\\B站\\制作\\邮件配置.json
    {
      "发件邮箱": "你的QQ号@qq.com",
      "授权码": "在 mail.qq.com 设置里开的那个 16 位码",
      "收件邮箱": "发到哪（不填就发给自己）"
    }

用法：
    python 寄邮件.py --测
    python 寄邮件.py --主题 "不烧心 成片" --正文 "见附件" --附件 <文件或目录> ...
    python 寄邮件.py --主题 "今日进度" --md <markdown文件> --附件 <图> --手机版 <大视频>
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import smtplib
import ssl
import sys
import time
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

制作 = os.path.dirname(os.path.abspath(__file__))
配置路 = os.path.join(制作, "邮件配置.json")
临时 = r"D:\DSHworkspace\_邮件临时"
上限 = 48 * 1024 * 1024        # QQ 单封 50 MB，留 2 MB 余量给编码膨胀
手机版长边 = 960
手机版码率 = "700k"

SMTP = {
    "qq.com":    ("smtp.qq.com", 465),
    "163.com":   ("smtp.163.com", 465),
    "126.com":   ("smtp.126.com", 465),
    "foxmail.com": ("smtp.qq.com", 465),
    "gmail.com": ("smtp.gmail.com", 465),
    "outlook.com": ("smtp.office365.com", 587),
}


def 读配置() -> dict:
    if not os.path.isfile(配置路):
        return {}
    with open(配置路, encoding="utf-8") as f:
        return json.load(f)


def 存配置(发件: str, 授权码: str, 收件: str = ""):
    os.makedirs(制作, exist_ok=True)
    with open(配置路, "w", encoding="utf-8") as f:
        json.dump({"发件邮箱": 发件, "授权码": 授权码,
                   "收件邮箱": 收件 or 发件}, f, ensure_ascii=False, indent=2)
    print(f"✅ 配置已写入 {配置路}")


def 服务器(发件: str) -> tuple[str, int]:
    域名 = 发件.split("@")[-1].lower()
    if 域名 not in SMTP:
        raise SystemExit(f"✗ 不认识的邮箱域名 {域名}；支持的：{'、'.join(SMTP)}")
    return SMTP[域名]


def 人读(字节: int) -> str:
    for 单 in ("B", "KB", "MB", "GB"):
        if 字节 < 1024:
            return f"{字节:.0f} {单}"
        字节 /= 1024
    return f"{字节:.1f} TB"


def 压手机版(路: str) -> str:
    """把大视频压成能塞进邮件的一版（720p 上下、低码率）。"""
    import av
    os.makedirs(临时, exist_ok=True)
    出 = os.path.join(临时, os.path.splitext(os.path.basename(路))[0] + "_手机版.mp4")
    with av.open(路) as i, av.open(出, "w", format="mp4") as o:
        iv = i.streams.video[0]
        ia = i.streams.audio[0] if i.streams.audio else None
        比 = min(1.0, 手机版长边 / max(iv.codec_context.width, iv.codec_context.height))
        宽 = int(iv.codec_context.width * 比) // 2 * 2
        高 = int(iv.codec_context.height * 比) // 2 * 2
        ov = o.add_stream("libx264", rate=iv.average_rate)
        ov.width, ov.height, ov.pix_fmt = 宽, 高, "yuv420p"
        ov.options = {"crf": "30", "preset": "veryfast", "maxrate": 手机版码率,
                      "bufsize": "1400k", "movflags": "+faststart"}
        oa = None
        if ia is not None:
            oa = o.add_stream("aac", rate=ia.codec_context.sample_rate or 44100)
            oa.bit_rate = 96000
        # 一次解全部流、按键分发。分开 i.decode(iv) / i.decode(ia) 会把
        # 交错在视频包里的音频包丢掉（PyAV 只解指定流、其余直接丢），
        # 上一版就是这么把音轨压没的。
        n = 0
        for 包 in i.decode():
            if 包.__class__.__name__ == "AudioFrame":
                if oa is None:
                    continue
                for p in oa.encode(包):
                    o.mux(p)
                continue
            帧 = 包.reformat(宽, 高, "yuv420p")
            for p in ov.encode(帧):
                o.mux(p)
            n += 1
        for p in ov.encode():
            o.mux(p)
        if oa is not None:
            for p in oa.encode():
                o.mux(p)
        if n == 0:
            raise RuntimeError("视频解不出帧")
    尺寸 = os.path.getsize(出)
    print(f"  ✓ 手机版 {os.path.basename(出)}  {人读(尺寸)}  {宽}×{高}")
    return 出


def 挑附件(附件: list[str], 自动压: bool = True) -> tuple[list[str], list[str]]:
    """返回 (直接发的, 太大的)。太大的先试着压手机版。"""
    可以, 超了 = [], []
    for p in 附件:
        if not os.path.isfile(p):
            print(f"  ✗ 找不到 {p}")
            continue
        if os.path.getsize(p) <= 上限:
            可以.append(p)
            continue
        if 自动压 and p.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
            print(f"  ⚠ {os.path.basename(p)} {人读(os.path.getsize(p))} 超了，压一版手机版")
            try:
                小 = 压手机版(p)
                if os.path.getsize(小) <= 上限:
                    可以.append(小)
                else:
                    超了.append(小)
            except Exception as e:
                print(f"  ✗ 压失败：{type(e).__name__}: {e}")
                超了.append(p)
        else:
            超了.append(p)
    return 可以, 超了


def 发(主题: str, 正文: str = "", 附件: list[str] | None = None,
      内嵌图: list[str] | None = None, 是HTML: bool = False,
      收件: str = "", 静默: bool = False) -> bool:
    附件 = 附件 or []
    内嵌图 = 内嵌图 or []
    c = 读配置()
    发件 = c.get("发件邮箱", "")
    码 = c.get("授权码", "")
    if not 发件 or not 码:
        print("✗ 还没配置。先跑：python 寄邮件.py --设 <你的QQ邮箱> <授权码>")
        return False
    收 = 收件 or c.get("收件邮箱") or 发件

    根 = MIMEMultipart("related") if 内嵌图 else MIMEMultipart()
    根["Subject"] = Header(主题, "utf-8")
    # QQ 的 SMTP 卡 RFC5322：From 的显示名不能是裸中文，必须走 RFC2047 编码，
    # 否则直接 550 "The From header is missing or invalid"。
    根["From"] = f"{Header('不烧心流水线', 'utf-8').encode()} <{发件}>"
    根["To"] = f"{Header('我', 'utf-8').encode()} <{收}>" if 收 != 发件 else 发件
    根["Date"] = __import__("email.utils", fromlist=["utils"]).formatdate(localtime=True)
    根["Message-ID"] = __import__("email.utils", fromlist=["utils"]).make_msgid(domain=发件.split("@")[-1])

    体 = MIMEMultipart("alternative")
    体.attach(MIMEText(正文, "html" if 是HTML else "plain", "utf-8"))
    根.attach(体)

    for i, p in enumerate(内嵌图, 1):
        if not os.path.isfile(p):
            continue
        with open(p, "rb") as f:
            im = MIMEImage(f.read())
        im.add_header("Content-ID", f"<img{i}>")
        im.add_header("Content-Disposition", "inline",
                      filename=("utf-8", "", os.path.basename(p)))
        根.attach(im)

    for p in 附件:
        if not os.path.isfile(p):
            print(f"  ✗ 找不到 {p}")
            continue
        类型, _ = mimetypes.guess_type(p)
        主, 次 = (类型 or "application/octet-stream").split("/", 1)
        块 = MIMEBase(主, 次)
        with open(p, "rb") as f:
            块.set_payload(f.read())
        encoders.encode_base64(块)
        块.add_header("Content-Disposition", "attachment",
                      filename=("utf-8", "", os.path.basename(p)))
        根.attach(块)
        if not 静默:
            print(f"  + {os.path.basename(p)}  {人读(os.path.getsize(p))}")

    主机, 端口 = 服务器(发件)
    try:
        if 端口 == 465:
            with smtplib.SMTP_SSL(主机, 端口, context=ssl.create_default_context(), timeout=90) as s:
                s.login(发件, 码)
                s.sendmail(发件, [收], 根.as_string())
        else:
            with smtplib.SMTP(主机, 端口, timeout=90) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(发件, 码)
                s.sendmail(发件, [收], 根.as_string())
        if not 静默:
            print(f"\n✅ 已寄出 → {收}    主题：{主题}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("✗ 授权码不对（注意不是登录密码，要去 mail.qq.com → 设置 → 账户 → 开启 SMTP 服务后拿的那个 16 位码）")
    except Exception as e:
        print(f"✗ 发信失败：{type(e).__name__}: {e}")
    return False


def 寄一批(主题: str, 正文: str, 附件: list[str], 收件: str = ""):
    """附件太大自动拆成多封。"""
    可以, 超了 = 挑附件(附件)
    组, 现, 现尺 = [], [], 0
    for p in 可以:
        尺 = os.path.getsize(p) * 1.37      # base64 膨胀
        if 现 and 现尺 + 尺 > 上限:
            组.append(现); 现, 现尺 = [], 0
        现.append(p); 现尺 += 尺
    if 现:
        组.append(现)
    if not 组:
        组 = [[]]
    for i, g in enumerate(组, 1):
        t = 主题 if len(组) == 1 else f"{主题}（{i}/{len(组)}）"
        发(t, 正文, g, 收件=收件)
        if i < len(组):
            time.sleep(2)
    if 超了:
        print("\n⚠ 这几个压完还是太大，没寄：")
        for p in 超了:
            print(f"    {p}  {人读(os.path.getsize(p))}")
        print("    → 在家连同一个 WiFi 时用 http://192.168.31.36:8777 看")
    return not 超了


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="把产出寄到邮箱")
    ap.add_argument("--设", nargs=2, metavar=("邮箱", "授权码"), help="写入配置")
    ap.add_argument("--收", default="", help="收件邮箱，不给就发给自己")
    ap.add_argument("--主题", default="不烧心 · 产出")
    ap.add_argument("--正文", default="")
    ap.add_argument("--md", default="", help="把一个 markdown 文件当正文（纯文本）")
    ap.add_argument("--附件", nargs="*", default=[])
    ap.add_argument("--大附件", nargs="*", default=[], help="超大会自动压手机版 / 拆封")
    ap.add_argument("--测", action="store_true")
    a = ap.parse_args()

    if a.设:
        存配置(a.设[0], a.设[1], a.收)
        sys.exit(0)

    正 = a.正文
    if a.md and os.path.isfile(a.md):
        with open(a.md, encoding="utf-8") as f:
            正 = f.read()
    if not 正 and not a.md:
        正 = "（无正文）"

    if a.测:
        c = 读配置()
        print("配置：", 配置路)
        print("  发件：", c.get("发件邮箱") or "（没配）")
        print("  授权码：", ("已设 " + "*" * 8) if c.get("授权码") else "（没配）")
        print("  收件：", c.get("收件邮箱") or "（没配）")
        ok = 发("不烧心流水线 · 测试", f"这是一封测试信。\n本机时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("结果：", "✅ 通了" if ok else "✗ 没通")
        sys.exit(0 if ok else 1)

    if a.大附件:
        寄一批(a.主题, 正, a.大附件, a.收)
    else:
        发(a.主题, 正, a.附件, 收件=a.收)
