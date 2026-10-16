# -*- coding: utf-8 -*-
r"""
审片 —— 把一支成片的所有待判材料汇成一页 HTML，并管审批状态

  python 审片.py D:\DSHworkspace\B站\成片\它记得          # 生成 审核.html 并打开
  python 审片.py <成片目录> --不打开                       # 只生成
  python 审片.py <成片目录> --通过 -备注 "画质OK，可以投"    # 你点头后签字
  python 审片.py <成片目录> --打回 -备注 "第3镜太暗"        # 打回重做
  python 审片.py <成片目录> --状态                         # 只看当前审批状态

审批是**落盘**的：只有 _审批.json 里 state=通过，投稿.py 才会调上传脚本。
光在命令行敲 yes 不算数——那样一忙就容易手滑把半成品发出去。
"""
import argparse
import datetime as dt
import html
import json
import os
import subprocess
import sys

try:
    import av
except ImportError:
    av = None

try:
    from PIL import Image
except ImportError:
    Image = None

本目录 = os.path.dirname(os.path.abspath(__file__))
审批文件名 = "_审批.json"
待审文件名 = "_待审.json"


# ---------------------------------------------------------------- 素材收集

def 找成片(目录):
    """优先用 _待审.json 里记的，否则挑体积最大的 mp4（排除留档的 _5B/_14B）"""
    m = os.path.join(目录, 待审文件名)
    if os.path.isfile(m):
        try:
            with open(m, encoding="utf-8") as f:
                v = json.load(f).get("成片")
            if v and os.path.isfile(v):
                return v
        except Exception:
            pass
    cand = []
    for f in os.listdir(目录):
        if not f.lower().endswith(".mp4"):
            continue
        p = os.path.join(目录, f)
        # 留档版（xxx_5B.mp4 / xxx_14B.mp4）不算正片
        if os.path.splitext(f)[0].endswith(("_5B", "_14B", "_5b", "_14b")):
            continue
        cand.append((os.path.getsize(p), p))
    return max(cand)[1] if cand else None


def 找封面(目录):
    d = os.path.join(目录, "封面")
    if not os.path.isdir(d):
        return None
    for f in sorted(os.listdir(d)):
        if "带字" in f and f.lower().endswith((".png", ".jpg", ".jpeg")):
            return os.path.join(d, f)
    for f in sorted(os.listdir(d)):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            return os.path.join(d, f)
    return None


def 视频信息(p):
    """用 PyAV 读真实参数；读不到就退化成「只知道大小」"""
    out = {"大小MB": os.path.getsize(p) / 1024 / 1024}
    if av is None:
        return out
    try:
        with av.open(p) as c:
            s = c.streams.video[0]
            out["宽"] = s.codec_context.width
            out["高"] = s.codec_context.height
            out["帧数"] = int(s.frames) if s.frames else None
            out["时长秒"] = float(c.duration / av.time_base) if c.duration else None
            out["fps"] = float(s.average_rate) if s.average_rate else None
            out["编码"] = s.codec_context.name
    except Exception as e:
        out["读取失败"] = str(e)
    return out


def 抽分镜(视频, 目录, 张数=12):
    """均匀抽 N 帧拼一张分镜图，用于一眼看完整片节奏"""
    if av is None or Image is None:
        return None
    try:
        with av.open(视频) as c:
            帧表 = [f for f in c.decode(c.streams.video[0])]
        if not 帧表:
            return None
        n = min(张数, len(帧表))
        选 = [帧表[int(i * (len(帧表) - 1) / max(n - 1, 1))] for i in range(n)]
        列 = 4 if n > 6 else 3
        行 = (n + 列 - 1) // 列
        缩 = 320
        第一 = 选[0].to_image()
        比 = 第一.height / 第一.width
        h = int(缩 * 比)
        板 = Image.new("RGB", (缩 * 列, h * 行), (14, 14, 16))
        for i, f in enumerate(选):
            板.paste(f.to_image().resize((缩, h), Image.LANCZOS), ((i % 列) * 缩, (i // 列) * h))
        路径 = os.path.join(目录, "_分镜.jpg")
        板.save(路径, quality=88)
        return 路径
    except Exception:
        return None


def 读投稿信息(目录):
    for 名 in ("投稿信息.json",):
        p = os.path.join(目录, 名)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f), p
            except Exception:
                pass
    # 退回 _待审.json 里嵌的
    m = os.path.join(目录, 待审文件名)
    if os.path.isfile(m):
        try:
            with open(m, encoding="utf-8") as f:
                j = json.load(f)
            if j.get("投稿"):
                return j["投稿"], m
        except Exception:
            pass
    return None, None


# ---------------------------------------------------------------- 审批状态

def 读审批(目录):
    p = os.path.join(目录, 审批文件名)
    if not os.path.isfile(p):
        return {"state": "待审", "时间": None, "备注": ""}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"state": "待审", "时间": None, "备注": "(审批文件损坏)"}


def 写审批(目录, state, 备注=""):
    p = os.path.join(目录, 审批文件名)
    j = {"state": state,
         "时间": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "备注": 备注}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, indent=2)
    return p


# ---------------------------------------------------------------- 出页面

def 生成页面(目录, 视频, 封面, 信息, 分镜, 技术, 审批):
    名 = os.path.basename(目录.rstrip("\\/"))
    e = html.escape

    def rel(p):
        return e(os.path.relpath(p, 目录).replace("\\", "/")) if p else None

    块 = []
    块.append(f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>审片 · {e(名)}</title><style>
*{{box-sizing:border-box}}
body{{margin:0;background:#0d0e11;color:#e6e8ec;
 font:15px/1.7 "Microsoft YaHei","Segoe UI",system-ui,sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:36px 28px 80px}}
h1{{font-size:30px;margin:0 0 6px;letter-spacing:.5px}}
.sub{{color:#8b93a1;font-size:14px;margin-bottom:26px}}
.badge{{display:inline-block;padding:3px 12px;border-radius:20px;font-size:13px;
 font-weight:600;vertical-align:middle;margin-left:10px}}
.b-待审{{background:#3a2f12;color:#f0c04a;border:1px solid #6b5520}}
.b-通过{{background:#12301c;color:#57d98a;border:1px solid #24623a}}
.b-打回{{background:#351519;color:#f0736f;border:1px solid #6b2a2c}}
.card{{background:#14161b;border:1px solid #23262e;border-radius:12px;
 padding:20px 22px;margin-bottom:18px}}
.card h2{{font-size:16px;margin:0 0 14px;color:#9aa3b2;font-weight:600;
 letter-spacing:.4px;text-transform:uppercase}}
video{{width:100%;border-radius:8px;background:#000;display:block}}
img.cover{{width:100%;max-width:640px;border-radius:8px;display:block}}
.kv{{display:grid;grid-template-columns:110px 1fr;gap:6px 16px;font-size:14px}}
.kv .k{{color:#7c8492}} .kv .v{{color:#dde1e8;word-break:break-all}}
.tags span{{display:inline-block;background:#1d2029;border:1px solid #2c313c;
 border-radius:6px;padding:3px 10px;margin:0 6px 6px 0;font-size:13px;color:#a9b2c0}}
.desc{{white-space:pre-wrap;background:#0f1115;border-left:3px solid #2c313c;
 padding:12px 16px;border-radius:6px;color:#c6ccd6;font-size:14px}}
.judge{{background:#14161b;border:1px solid #2a2f3a;border-radius:12px;padding:20px 22px}}
code{{background:#1d2029;padding:2px 7px;border-radius:5px;font-size:13px;
 color:#8fd0ff;font-family:Consolas,monospace}}
.hint{{color:#7c8492;font-size:13px;margin-top:10px}}
</style></head><body><div class="wrap">""")

    状态 = 审批.get("state", "待审")
    块.append(f'<h1>审片 · {e(名)}<span class="badge b-{e(状态)}">{e(状态)}</span></h1>')
    时间行 = f" · 签于 {e(审批.get('时间') or '')}" if 审批.get("时间") else ""
    备注行 = f" · 备注：{e(审批.get('备注') or '')}" if 审批.get("备注") else ""
    块.append(f'<div class="sub">落盘于 {e(目录)}{时间行}{备注行}</div>')

    # 视频
    块.append('<div class="card"><h2>成片</h2>')
    if 视频:
        块.append(f'<video src="{rel(视频)}" controls preload="metadata" '
                  f'poster="{rel(封面) if 封面 else ""}"></video>')
    else:
        块.append('<div class="hint">没找到 mp4</div>')
    块.append("</div>")

    # 技术参数
    块.append('<div class="card"><h2>技术参数</h2><div class="kv">')
    if 技术.get("宽"):
        块.append(f'<div class="k">分辨率</div><div class="v">{技术["宽"]} × {技术["高"]}</div>')
    if 技术.get("时长秒"):
        块.append(f'<div class="k">时长</div><div class="v">{技术["时长秒"]:.2f} 秒</div>')
    if 技术.get("帧数"):
        块.append(f'<div class="k">帧数</div><div class="v">{技术["帧数"]} 帧</div>')
    if 技术.get("fps"):
        块.append(f'<div class="k">帧率</div><div class="v">{技术["fps"]:.2f} fps</div>')
    if 技术.get("编码"):
        块.append(f'<div class="k">编码</div><div class="v">{e(技术["编码"])}</div>')
    块.append(f'<div class="k">体积</div><div class="v">{技术["大小MB"]:.1f} MB</div>')
    块.append(f'<div class="k">文件</div><div class="v">{rel(视频) or "-"}</div>')
    块.append("</div></div>")

    # 投稿文案
    块.append('<div class="card"><h2>投稿文案</h2>')
    if 信息:
        标 = 信息.get("标题", "")
        块.append('<div class="kv">')
        块.append(f'<div class="k">标题</div><div class="v">{e(标)} '
                  f'<span style="color:#7c8492">（{len(标)} 字）</span></div>')
        块.append(f'<div class="k">分区</div><div class="v">{e(str(信息.get("分区","-")))}</div>')
        if 信息.get("活动"):
            块.append(f'<div class="k">活动</div><div class="v">{e(信息["活动"])}</div>')
        块.append(f'<div class="k">AI声明</div><div class="v">'
                  f'{"是" if 信息.get("AI生成声明") else "否"}</div>')
        if 信息.get("定时发布时间"):
            块.append(f'<div class="k">定时</div><div class="v">{e(str(信息["定时发布时间"]))}</div>')
        块.append("</div>")
        标s = 信息.get("标签") or []
        if 标s:
            块.append('<div style="margin-top:14px" class="tags">' +
                      "".join(f"<span>{e(t)}</span>" for t in 标s) + "</div>")
        if 信息.get("简介"):
            块.append(f'<div class="desc" style="margin-top:14px">{e(信息["简介"])}</div>')
    else:
        块.append('<div class="hint">没找到 投稿信息.json</div>')
    块.append("</div>")

    # 封面
    if 封面:
        块.append(f'<div class="card"><h2>封面</h2>'
                  f'<img class="cover" src="{rel(封面)}"></div>')

    # 分镜
    if 分镜:
        块.append(f'<div class="card"><h2>分镜（等间隔抽 12 帧）</h2>'
                  f'<img class="cover" style="max-width:100%" src="{rel(分镜)}"></div>')

    # 判断区
    块.append(f"""<div class="judge"><h2 style="font-size:16px;margin:0 0 12px;color:#9aa3b2">
怎么表态</h2>
<p style="margin:0 0 10px">看完在命令行签字，或者直接跟我说。通过后投稿脚本才走得下去。</p>
<p style="margin:0 0 8px"><code>python 审片.py "{e(目录)}" --通过 -备注 "可以投"</code></p>
<p style="margin:0"><code>python 审片.py "{e(目录)}" --打回 -备注 "哪里不行"</code></p>
<div class="hint">当前状态：<b>{e(状态)}</b>{
 "——已放行，可以投稿" if 状态 == "通过" else
 "——投稿.py 会拒绝上传" if 状态 == "打回" else
 "——还没签字，投稿.py 会拒绝上传"}</div>
</div>""")
    块.append("</div></body></html>")

    p = os.path.join(目录, "审核.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write("".join(块))
    return p


# ---------------------------------------------------------------- main

def 打开页面(p):
    """用显式找到的浏览器打开。

    本机 .html 没有默认关联程序，os.startfile() 会弹出「选择应用以打开」对话框卡住，
    所以这里自己找 Edge / Chrome，找不到再退回系统默认。
    """
    候选 = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for exe in 候选:
        if os.path.isfile(exe):
            subprocess.Popen([exe, p], close_fds=True)
            return exe
    try:
        os.startfile(p)
        return "(系统默认)"
    except Exception as e:
        return f"(打开失败：{e})"


def main():
    ap = argparse.ArgumentParser(description="成片审核：汇总材料 + 管审批状态")
    ap.add_argument("目录", help="成片目录")
    ap.add_argument("--通过", action="store_true", help="签字放行")
    ap.add_argument("--打回", action="store_true", help="打回重做")
    ap.add_argument("--状态", action="store_true", help="只看审批状态")
    ap.add_argument("--备注", default="", help="备注（打回时写清哪里不行）")
    ap.add_argument("--不打开", action="store_true", help="生成后不自动打开浏览器")
    a = ap.parse_args()

    目录 = os.path.abspath(a.目录)
    if not os.path.isdir(目录):
        sys.exit(f"❌ 不是目录：{目录}")

    if a.状态:
        s = 读审批(目录)
        print(f"{os.path.basename(目录)}: {s.get('state')}  "
              f"{s.get('时间') or ''}  {s.get('备注') or ''}".strip())
        return

    if a.通过 and a.打回:
        sys.exit("❌ --通过 和 --打回 只能给一个")

    if a.通过 or a.打回:
        # 打回必须写清原因，否则下次不知道该改什么
        if a.打回 and not a.备注.strip():
            sys.exit("❌ 打回请用 -备注 写清哪里不行")
        p = 写审批(目录, "通过" if a.通过 else "打回", a.备注)
        s = 读审批(目录)
        print(f"{'✅ 已放行' if a.通过 else '↩ 已打回'}  {p}")
        print(f"   状态 {s['state']}   {s['时间']}   {s['备注']}")
        if a.通过:
            print(f"\n现在可以投稿了：")
            print(f'   python "{os.path.join(本目录,'投稿.py')}" '
                  f'"{os.path.join(目录,'投稿信息.json')}"')
        return

    # 默认动作：生成页面
    视频 = 找成片(目录)
    封面 = 找封面(目录)
    信息, 信息路径 = 读投稿信息(目录)
    技术 = 视频信息(视频) if 视频 else {"大小MB": 0}
    分镜 = 抽分镜(视频, 目录) if 视频 else None
    审批 = 读审批(目录)
    p = 生成页面(目录, 视频, 封面, 信息, 分镜, 技术, 审批)

    print(f"成片  {视频 or '(没找到)'}")
    print(f"封面  {封面 or '(没找到)'}")
    print(f"文案  {信息路径 or '(没找到)'}")
    if 技术.get("宽"):
        print(f"规格  {技术['宽']}x{技术['高']}  {技术.get('时长秒',0):.2f}s  "
              f"{技术.get('帧数','?')} 帧  {技术['大小MB']:.1f} MB")
    print(f"审批  {审批.get('state')}  {审批.get('备注') or ''}")
    print(f"\n✅ 审核页 → {p}")

    if not a.不打开:
        print(f"   用 {打开页面(p)} 打开")


if __name__ == "__main__":
    main()
