# -*- coding: utf-8 -*-
"""
影匠 · 音色库
=============
把一堆散装参考音频，编成能查、能选、能直接喂给 TTS 的声音库。

用法：
    python 音色库.py                 # 编目 + 生成 音色库.json / 音色库.html
    python 音色库.py --查 磁性御姐    # 命令行查
    python 音色库.py --查 女声 --类 智声整理音色 --限 20

设计原则：
  1. 不猜。文件名里没写的属性就不填，宁可留空也不编。
  2. 原文件一个字节都不动。目录结构原样保留，只读。
  3. 中文友好。路径、文件名、标签全走 UTF-8，Windows 长路径用长路径前缀兜底。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

根 = Path(__file__).resolve().parent
原声 = 根 / "音色" / "原声"
输出 = 根 / "音色"

音频后缀 = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma"}

# ── 属性词典 ──────────────────────────────────────────────────────────
# 每条： 标签 → 触发词（按顺序匹配，先命中先算）
性别词 = [
    ("女", ["女声", "女生", "女士", "御姐", "少女", "萝莉", "女童", "女孩", "女性", "女"]),
    ("男", ["男声", "男生", "男士", "大叔", "少年", "青叔", "男童", "男孩", "男性", "男"]),
]
年龄词 = [
    ("孩童", ["孩童", "儿童", "幼童", "宝宝", "小孩"]),
    ("少年", ["少年", "青年", "少女", "青叔", "学生"]),
    ("中年", ["中年", "大叔", "熟男", "少妇", "熟女"]),
    ("老年", ["老年", "长者", "老人", "苍老", "爷爷", "奶奶"]),
]
气质词 = [
    ("磁性", ["磁性", "低磁", "磁"]),
    ("温柔", ["温柔", "温暖", "暖心", "软"]),
    ("高冷", ["高冷", "清冷", "冷艳", "冷淡"]),
    ("慵懒", ["慵懒", "懒"]),
    ("阳光", ["阳光", "清脆", "活泼", "开朗"]),
    ("浑厚", ["浑厚", "醇厚", "厚重", "烟嗓", "沙哑", "洪亮"]),
    ("甜美", ["甜美", "甜", "萌", "嗲"]),
    ("优雅", ["优雅", "成熟", "知性", "端庄"]),
    ("故事感", ["故事感", "叙事"]),
]
用途词 = [
    ("旁白", ["旁白", "解说", "解说词"]),
    ("有声书", ["有声书", "说书", "朗读", "小说"]),
    ("纪录片", ["纪录片", "记录片"]),
    ("广告", ["广告", "宣传", "带货", "口播"]),
    ("影视配音", ["影视", "配音", "角色扮演", "译制"]),
    ("游戏", ["游戏", "二次元", "动漫"]),
    ("教学", ["教学", "课程", "讲课"]),
]
语言词 = [
    ("英语", ["英语", "english", "美式", "英式", "澳洲", "加拿大", "爱尔兰", "菲律宾", "印度"]),
    ("日语", ["日语", "日本"]),
    ("方言", ["方言", "粤语", "东北", "四川", "河南", "上海", "闽南", "山东", "湖南"]),
]
情绪词 = ("多情感", "多情绪", "情感")


def _读时长(路径: Path) -> dict:
    """读音频头，拿到时长/采样率/声道。拿不到就返回空，绝不瞎编。"""
    信息 = {"秒": None, "采样率": None, "声道": None}
    try:
        import soundfile as sf
        with sf.SoundFile(str(路径)) as f:
            信息["秒"] = round(len(f) / f.samplerate, 2) if f.samplerate else None
            信息["采样率"] = int(f.samplerate)
            信息["声道"] = int(f.channels)
            if 信息["秒"] and 信息["秒"] > 0:
                return 信息
    except Exception:
        pass
    try:
        from mutagen import File as MFile
        m = MFile(str(路径))
        if m is not None and m.info is not None:
            信息["秒"] = round(float(m.info.length), 2)
            信息["采样率"] = int(getattr(m.info, "sample_rate", 0)) or None
            信息["声道"] = int(getattr(m.info, "channels", 0)) or None
    except Exception:
        pass
    return 信息


def _打标(文本: str) -> dict:
    """从文件名/路径里抽属性。抽不到就是空列表。"""
    低 = 文本.lower()
    出 = {"性别": [], "年龄": [], "气质": [], "用途": [], "语言": []}
    for 标签, 词表 in (("性别", 性别词), ("年龄", 年龄词), ("气质", 气质词),
                       ("用途", 用途词), ("语言", 语言词)):
        for 值, 触发 in 词表:
            if any(t.lower() in 低 for t in 触发):
                出[标签].append(值)
    return 出


def _人名(文件名: str) -> str:
    """从「名字-描述」里取名字部分。"""
    s = Path(文件名).stem
    s = re.sub(r"[（(].*?[)）]", "", s)
    for 分 in ("-", "—", "_", "–"):
        if 分 in s:
            左 = s.split(分, 1)[0].strip()
            if 0 < len(左) <= 12:
                return 左
    return s.strip()[:24]


def 扫描() -> list[dict]:
    if not 原声.exists():
        sys.exit(f"✗ 找不到 {原声}，先把音色包解到那儿。")
    音频 = []
    前缀 = "\\\\?\\" + str(原声.resolve())
    for 根目录, _, 文件们 in os.walk(前缀):
        for 名 in 文件们:
            if Path(名).suffix.lower() not in 音频后缀:
                continue
            全 = Path(根目录) / 名
            显示 = Path(str(全).replace("\\\\?\\", "", 1))
            try:
                相对 = 显示.relative_to(原声.resolve())
            except ValueError:
                相对 = 显示.name
            层 = 相对.parts
            st = 全.stat()
            音频.append({
                "路径": str(显示),
                "相对": str(相对).replace("\\", "/"),
                "文件名": 名,
                "大类": 层[0] if len(层) >= 2 else "未分类",
                "子类": 层[1] if len(层) >= 3 else "",
                "字节": st.st_size,
                "MB": round(st.st_size / 1048576, 2),
                "格式": Path(名).suffix.lower().lstrip("."),
                **_读时长(全),
            })
    return 音频


def 编目() -> dict:
    音频 = 扫描()
    for a in 音频:
        标 = _打标(a["相对"])
        a.update(标)
        a["名字"] = _人名(a["文件名"])
        a["指纹"] = hashlib.md5(a["相对"].encode("utf-8")).hexdigest()[:10]

    总秒 = sum(a["秒"] or 0 for a in 音频)
    总MB = sum(a["MB"] for a in 音频)
    有长 = [a for a in 音频 if a["秒"]]

    # 去重：同字节数 + 同时长 → 疑似重复
    桶 = defaultdict(list)
    for a in 音频:
        桶[(a["字节"], a["秒"])].append(a)
    重复组 = {k: v for k, v in 桶.items() if len(v) > 1}

    统计 = {
        "总数": len(音频),
        "总MB": round(总MB, 1),
        "总时长_分": round(总秒 / 60, 1),
        "能读到时长": len(有长),
        "平均时长_秒": round(总秒 / len(有长), 1) if 有长 else None,
        "最长_秒": max((a["秒"] for a in 有长), default=None),
        "最短_秒": min((a["秒"] for a in 有长), default=None),
        "采到属性": {
            维度: dict(Counter(值 for a in 音频 for 值 in a[维度]).most_common())
            for 维度 in ("性别", "年龄", "气质", "用途", "语言")
        },
        "按大类": dict(Counter(a["大类"] for a in 音频).most_common()),
        "按格式": dict(Counter(a["格式"] for a in 音频).most_common()),
        "疑似重复组": len(重复组),
    }
    return {
        "版本": 1,
        "生成时间": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "根目录": str(原声),
        "统计": 统计,
        "音频": sorted(音频, key=lambda a: (a["大类"], a["子类"], a["文件名"])),
    }


# ── 网页 ──────────────────────────────────────────────────────────────
网页模板 = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>影匠 · 音色库</title>
<style>
:root{--纸:#fbf9f6;--墨:#1c1b1a;--灰:#8a8580;--线:#e5e0d8;--金:#b8873a;--卡:#fff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--纸);color:var(--墨);font:15px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;padding:28px 32px 80px}
header{max-width:1500px;margin:0 auto 22px}
h1{font-size:30px;letter-spacing:.5px;font-weight:700}
h1 small{font-size:14px;color:var(--灰);font-weight:400;margin-left:12px;letter-spacing:0}
.数{display:flex;gap:26px;flex-wrap:wrap;margin:16px 0 6px}
.数 div{background:var(--卡);border:1px solid var(--线);border-radius:10px;padding:10px 18px;min-width:104px}
.数 b{display:block;font-size:22px;color:var(--金);line-height:1.25}
.数 span{font-size:12px;color:var(--灰)}
.控{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:18px 0 12px;padding:14px 16px;background:var(--卡);border:1px solid var(--线);border-radius:12px}
input[type=search],select{font:inherit;padding:8px 12px;border:1px solid var(--线);border-radius:8px;background:#fff;outline:none}
input[type=search]{flex:1;min-width:220px}
input[type=search]:focus,select:focus{border-color:var(--金)}
.签{display:flex;gap:6px;flex-wrap:wrap}
.签 button{font:inherit;font-size:13px;padding:5px 12px;border:1px solid var(--线);border-radius:20px;background:#fff;cursor:pointer;color:var(--灰)}
.签 button[data-on="1"]{background:var(--金);border-color:var(--金);color:#fff}
table{width:100%;border-collapse:collapse;max-width:1500px;margin:0 auto;background:var(--卡);border:1px solid var(--线);border-radius:12px;overflow:hidden}
th{text-align:left;font-size:12px;font-weight:600;color:var(--灰);padding:10px 12px;border-bottom:1px solid var(--线);background:#f6f3ee;position:sticky;top:0;cursor:pointer;user-select:none;white-space:nowrap}
th:hover{color:var(--金)}
td{padding:8px 12px;border-bottom:1px solid #f2eee8;vertical-align:middle}
tr:hover td{background:#fdfbf7}
.名{font-weight:600;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.路{font-size:11px;color:var(--灰);max-width:330px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:rtl;text-align:left}
.标{display:inline-block;font-size:11px;padding:1px 7px;border-radius:10px;background:#f0ece4;color:#6b6459;margin:1px 3px 1px 0;white-space:nowrap}
.标.女{background:#fbe9f0;color:#a8426d}.标.男{background:#e6eefb;color:#37619e}
.标.老年,.标.中年{background:#f3ecdd;color:#8a6a2c}
.标.孩童,.标.少年{background:#e8f5e9;color:#3d7a45}
.标.英语,.标.日语,.标.方言{background:#eee9fb;color:#6146a8}
audio{height:30px;width:220px;vertical-align:middle}
.空{text-align:center;color:var(--灰);padding:60px 0}
.尾{max-width:1500px;margin:16px auto 0;font-size:12px;color:var(--灰);display:flex;justify-content:space-between}
</style></head><body>
<header>
<h1>影匠 · 音色库<small>__根__</small></h1>
<div class="数">
  <div><b>__总数__</b><span>条音色</span></div>
  <div><b>__总MB__</b><span>MB 素材</span></div>
  <div><b>__总时长__</b><span>分钟总时长</span></div>
  <div><b>__均长__</b><span>秒 / 条</span></div>
  <div><b>__大类数__</b><span>个大类</span></div>
</div>
<div class="控">
  <input type="search" id="搜" placeholder="搜名字 / 描述 / 路径…（例：御姐、旁白、英语、少年）">
  <select id="类"><option value="">全部大类</option>__类选项__</select>
  <select id="性"><option value="">不限性别</option><option>女</option><option>男</option></select>
  <select id="龄"><option value="">不限年龄</option><option>孩童</option><option>少年</option><option>中年</option><option>老年</option></select>
  <select id="质"><option value="">不限气质</option>__质选项__</select>
  <select id="序">
    <option value="默认">默认顺序</option><option value="长">时长 ↓</option><option value="短">时长 ↑</option>
    <option value="大">体积 ↓</option><option value="名">名字</option>
  </select>
</div>
<div class="签" id="快"></div>
</header>
<table><thead><tr>
  <th data-k="名">名字</th><th data-k="大类">大类</th><th data-k="秒">时长</th>
  <th data-k="MB">体积</th><th data-k="格式">格式</th><th>标签</th><th>试听</th><th>路径</th>
</tr></thead><tbody id="身"></tbody></table>
<div class="尾"><span id="计"></span><span>__时间__ 生成 · 影匠</span></div>
<script>
const 数 = __数据__;
const 身 = document.getElementById('身'), 计 = document.getElementById('计');
const 搜 = document.getElementById('搜'), 类 = document.getElementById('类'), 性 = document.getElementById('性'),
      龄 = document.getElementById('龄'), 质 = document.getElementById('质'), 序 = document.getElementById('序');
let 排 = {k:'默认', d:1};
function 标(a){
  const o=[];
  a.性别.forEach(v=>o.push(['性别',v])); a.年龄.forEach(v=>o.push(['年龄',v]));
  a.气质.forEach(v=>o.push(['气质',v])); a.用途.forEach(v=>o.push(['用途',v]));
  a.语言.forEach(v=>o.push(['语言',v]));
  return o.map(([k,v])=>`<span class="标 ${v}">${v}</span>`).join('');
}
function 画(){
  const q = 搜.value.trim().toLowerCase();
  let 集 = 数.filter(a=>{
    if (类.value && a.大类 !== 类.value) return false;
    if (性.value && !a.性别.includes(性.value)) return false;
    if (龄.value && !a.年龄.includes(龄.value)) return false;
    if (质.value && !a.气质.includes(质.value)) return false;
    if (q){ const h=(a.名字+' '+a.文件名+' '+a.相对+' '+a.性别.join('')+a.年龄.join('')+a.气质.join('')+a.用途.join('')+a.语言.join('')).toLowerCase(); if(!h.includes(q) && ![...q].every(c=>c===' '||h.includes(c))) return false; }
    return true;
  });
  const s = 序.value;
  if (s==='长') 集.sort((x,y)=>(y.秒||0)-(x.秒||0));
  else if (s==='短') 集.sort((x,y)=>(x.秒||1e9)-(y.秒||1e9));
  else if (s==='大') 集.sort((x,y)=>y.MB-x.MB);
  else if (s==='名') 集.sort((x,y)=>x.名字.localeCompare(y.名字,'zh'));
  else if (排.k!=='默认') 集.sort((x,y)=>{const p=排.k; const A=x[p]??0,B=y[p]??0; return (typeof A==='string'? String(A).localeCompare(String(B),'zh') : A-B)*排.d;});
  计.textContent = `显示 ${集.length} / ${数.length} 条`;
  if(!集.length){ 身.innerHTML='<tr><td colspan="8" class="空">没有匹配的音色 —— 换个词试试</td></tr>'; return; }
  const 片 = 集.slice(0, 600).map(a=>`<tr>
    <td class="名" title="${a.文件名.replace(/"/g,'&quot;')}">${a.名字}</td>
    <td style="font-size:12px;color:#8a8580">${a.大类}${a.子类?' / '+a.子类:''}</td>
    <td>${a.秒!=null?a.秒+'s':'—'}</td><td>${a.MB}M</td><td>${a.格式}</td>
    <td>${标(a)}</td>
    <td><audio controls preload="none" src="原声/${encodeURI(a.相对)}"></audio></td>
    <td class="路" title="${a.相对}">${a.相对}</td></tr>`).join('');
  身.innerHTML = 片 + (集.length>600?`<tr><td colspan="8" class="空">…还有 ${集.length-600} 条，缩小范围再看</td></tr>`:'');
}
[搜,类,性,龄,质,序].forEach(e=>e.addEventListener('input',画));
document.querySelectorAll('th[data-k]').forEach(th=>th.addEventListener('click',()=>{
  const k=th.dataset.k; 排 = (排.k===k)? {k, d:-排.d} : {k, d:-1}; 序.value='默认'; 画();
}));
const 快 = {女:['女声御姐','磁性','温柔','旁白解说','有声书'], 男:['大叔','磁性','旁白解说','纪录片','少年']};
document.getElementById('快').innerHTML = Object.entries(快).flatMap(([g,ws])=>ws.map(w=>`<button data-w="${w}">${w}</button>`)).join('');
document.querySelectorAll('#快 button').forEach(b=>b.addEventListener('click',()=>{
  const w=b.dataset.w; 搜.value = 搜.value===w? '' : w; 画();
}));
画();
</script></body></html>"""


def 出网页(库: dict) -> Path:
    音 = 库["音频"]
    精简 = [{k: a[k] for k in ("名字", "文件名", "相对", "大类", "子类", "秒", "MB", "格式",
                               "性别", "年龄", "气质", "用途", "语言")} for a in 音]
    类计 = Counter(a["大类"] for a in 音)
    质计 = Counter(v for a in 音 for v in a["气质"])
    页 = (网页模板
          .replace("__数据__", json.dumps(精简, ensure_ascii=False))
          .replace("__根__", 库["根目录"])
          .replace("__总数__", str(库["统计"]["总数"]))
          .replace("__总MB__", str(库["统计"]["总MB"]))
          .replace("__总时长__", str(库["统计"]["总时长_分"]))
          .replace("__均长__", str(库["统计"]["平均时长_秒"] or "—"))
          .replace("__大类数__", str(len(类计)))
          .replace("__类选项__", "".join(f'<option>{k}</option>' for k, _ in 类计.most_common()))
          .replace("__质选项__", "".join(f'<option>{k}</option>' for k, _ in 质计.most_common()))
          .replace("__时间__", 库["生成时间"]))
    路 = 输出 / "音色库.html"
    路.write_text(页, encoding="utf-8")
    return 路


def 查(词: str, 类: str | None, 限: int) -> None:
    库 = json.loads((输出 / "音色库.json").read_text(encoding="utf-8"))
    低 = 词.lower()
    字 = [c for c in 低 if not c.isspace()]
    命中 = []
    for a in 库["音频"]:
        if 类 and a["大类"] != 类:
            continue
        干草 = (a["名字"] + a["文件名"] + a["相对"] + "".join(
            "".join(a[k]) for k in ("性别", "年龄", "气质", "用途", "语言"))).lower()
        # 先试整串，不中再退化成「每个字都出现过」——这样「老人」能命中「老年人」
        if 低 in 干草 or (字 and all(c in 干草 for c in 字)):
            命中.append(a)
    命中.sort(key=lambda a: -(a["秒"] or 0))
    print(f"\n  「{词}」命中 {len(命中)} 条" + (f"（大类={类}）" if 类 else ""))
    print("  " + "─" * 78)
    for a in 命中[:限]:
        t = f"{a['秒']}s" if a["秒"] is not None else "—"
        标 = "/".join(a["性别"] + a["年龄"] + a["气质"] + a["用途"] + a["语言"]) or "无标签"
        print(f"  {a['名字'][:14]:<16}{t:>8}  {a['MB']:>6}M  {a['大类'][:8]:<10}{标[:34]}")
        print(f"       {a['相对']}")
    if len(命中) > 限:
        print(f"  …还有 {len(命中)-限} 条")
    print()


def main() -> None:
    p = argparse.ArgumentParser(description="影匠 · 音色库编目")
    p.add_argument("--查", metavar="词", help="搜索音色，不填则重新编目")
    p.add_argument("--类", help="限定大类")
    p.add_argument("--限", type=int, default=25, help="最多显示多少条")
    o = p.parse_args()

    if o.查:
        查(o.查, o.类, o.限)
        return

    输出.mkdir(parents=True, exist_ok=True)
    库 = 编目()
    (输出 / "音色库.json").write_text(json.dumps(库, ensure_ascii=False, indent=1), encoding="utf-8")
    页 = 出网页(库)
    s = 库["统计"]
    print(f"\n  ✓ 音色库编好了")
    print(f"    {s['总数']} 条 · {s['总MB']} MB · {s['总时长_分']} 分钟 · 平均 {s['平均时长_秒']} 秒")
    print(f"    能读到时长 {s['能读到时长']}/{s['总数']}，疑似重复 {s['疑似重复组']} 组")
    print(f"\n    大类：")
    for k, v in list(s["按大类"].items())[:12]:
        print(f"      {v:>5}  {k}")
    print(f"\n    采到的标签（性别/年龄/气质）：")
    for 维 in ("性别", "年龄", "气质"):
        top = list(s["采到属性"][维].items())[:8]
        print(f"      {维}： " + "  ".join(f"{k}×{v}" for k, v in top))
    print(f"\n    目录： {输出 / '音色库.json'}")
    print(f"           {页}")
    print(f"\n    查一条试试：  python 音色库.py --查 磁性御姐\n")


if __name__ == "__main__":
    main()
