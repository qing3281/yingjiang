# -*- coding: utf-8 -*-
"""
影匠 · 音色库
=============
把一堆散装参考音频，编成能查、能选、能直接喂给 TTS 的声音库。

用法：
    python 音色库.py                 # 编目 + 生成 音色库.json / 音色库.html
    python 音色库.py --查 磁性御姐    # 命令行查
    python 音色库.py --查 女声 --类 智声整理音色 --限 20
    python 音色库.py --角色          # 看「角色 → 音色」映射表，并验证音色还在不在库里
    python 音色库.py --查角色 凌霜    # 一个角色绑了什么音色（含备选与理由）
    python 音色库.py --验映射        # 只验映射表（音色库是活的目录，路径会变）

角色 → 音色（G5）：
    音色挂在【角色】上，不挂在【台词】上 —— 照抄飞彩的 character.voiceId。
    映射表在 音色\角色映射.json。剧本里只写角色名，音色由这张表决定。

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


def _人名(文件名: str, 相对: str = "") -> str:
    """
    取音色的**显示名字**。

    ★ 这里是踩过坑的：早先的写法是「按第一个 `-` 切开取左边，不超过 12 字就用」，
    结果 `女-常规-清冷无情-2-1.wav` → `女`、`男-常规-清冷无情-3-1.wav` → `男`，
    **两条同名，而且名字完全丢掉了「清冷无情」这个唯一有用的信息**。
    中文音色文件名里的 `-` 是**结构分隔符**，不是「名字-描述」的分界，不能按它切。

    现在的规则（保守，只在明显无意义时才改写）：
      1. 基础 = 文件名去扩展名、去括号内容
      2. `人物——叶修` 这种「占位符——真名」→ 取 `叶修`
      3. 基础有意义就直接用（哪怕长，长名字也比重名强）
      4. `01.wav` 这种纯序号 → 借用父文件夹名（`没有想要的人物角色，教你如何自制所需人物角色音色` → `自制所需人物角色音色`）
    """
    s = Path(文件名).stem
    s = re.sub(r"[（(].*?[)）]", "", s).strip()

    # ② 占位符——真名
    if "——" in s:
        左右 = [x.strip() for x in s.split("——", 1)]
        if 左右[0] in ("人物", "音色", "角色", "voice", "Voice") and 左右[1]:
            return 左右[1]

    # ③ 基础有意义（含中文/字母，不是纯数字序号）→ 直接用
    有料 = re.sub(r"[\s\-_—–.·\d]+", "", s)
    if 有料:
        return s

    # ④ 纯序号 → 借父文件夹名
    if 相对:
        层 = [x for x in str(相对).replace("\\", "/").split("/") if x]
        if len(层) >= 2:
            父 = re.sub(r"[（(].*?[)）]", "", 层[-2]).strip()
            父 = re.sub(r"^没有想要的人物角色，教你如何", "", 父)
            if 父:
                return 父

    return s or Path(文件名).stem


def _去重名(音频: list[dict]) -> int:
    """
    保证 `名字` 唯一 —— 重名会让「按名字点音色」变得不可能。

    实测踩到的三种重名，**一次比一次难发现**：

    1. `没有想要的人物角色，教你如何自制所需人物角色音色\\` 下每个子文件夹里都有一堆 `01.wav`，
       规则 ④ 会把它们都叫成父文件夹名 → 给重名的补「（子文件夹）」。**这一层修掉了 96 条。**
    2. **补了「（子文件夹）」还是重**：
       - `英语人物音色/其他/男声/1.wav … 18.wav` → **18 条**都叫 `男声`，
         因为它们的父目录**就是同一个** `男声\\`，补上去等于没补（原写法 `若 != 名字` 时跳过）。
       - `王也.MP3` 与 `王也.WAV`、`男-…柔和 (2).wav` 与 `男-…柔和.wav`、`云小馨.wav` 与 `云小馨（影视模式）.wav`
         → 括号内容按规则 ① 被剥掉了，**不同文件撞成同名**。
       **这一层剩下 10 个名字 / 36 条。**
    3. 兜底：真正同名又无法拆分的，挂上 `指纹` 前 4 位（相对路径的 md5，库内唯一且稳定）。
       `例如 男声·9b3f` —— 至少选出来的是同一条、不会漂。

    **不变量：`统计.仍有重名` 必须是 `False`。** 它一旦变成 `True`，
    「按名字点音色」就又不可靠了 —— 这是一条能自检的断言，别只当统计数字看。

    返回消歧了几条。
    """
    from collections import Counter  # noqa: PLC0415

    改 = 0
    # 第 1、2 层：按重名组逐组补上下文
    for _轮 in (1, 2):
        计 = Counter(a["名字"] for a in 音频)
        重名 = {k for k, v in 计.items() if v > 1}
        if not 重名:
            break
        for a in 音频:
            旧 = a["名字"]
            if 旧 not in 重名:
                continue
            层 = [x for x in str(a.get("相对", "")).replace("\\", "/").split("/") if x]
            若 = str(Path(层[-2]).stem).strip() if len(层) >= 2 else ""
            if 若 and 若 not in 旧:                      # ← 关键：父目录名已包含在名字里就不要再补
                a.setdefault("名字_原", 旧)
                a["名字"] = f"{旧}（{若}）"
                改 += 1

    # 第 3 层：还重的挂指纹（保证绝对唯一）
    计 = Counter(a["名字"] for a in 音频)
    for a in 音频:
        if 计[a["名字"]] > 1:
            a.setdefault("名字_原", a["名字"])
            a["名字"] = f"{a['名字']}·{str(a.get('指纹', ''))[:4]}"
            改 += 1
    return 改


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
        a["名字"] = _人名(a["文件名"], a["相对"])
        a["指纹"] = hashlib.md5(a["相对"].encode("utf-8")).hexdigest()[:10]
    消歧 = _去重名(音频)
    重名 = len({a["名字"] for a in 音频}) != len(音频)

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
        "名字消歧": 消歧,
        "仍有重名": 重名,
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

    # ★ 分级匹配，**兜底那级必须排在真命中后面**。
    #   踩过的坑：早先写成 `if 低 in 干草 or all(c in 干草)` 单一条件，
    #   于是「女-常规-清冷无情-2-1」把「男-常规-清冷无情-3-1」也捞进来
    #   （6 个字都出现过），再按时长降序 → 7.84 秒的男声排到 4.77 秒的女声前面。
    #   查女声返回男声，是「结果看起来合理但其实错了」的典型，比报错更危险。
    甲, 乙, 丙, 丁 = [], [], [], []
    for a in 库["音频"]:
        if 类 and a["大类"] != 类:
            continue
        名 = (a["名字"] or "").lower()
        文 = (a["文件名"] or "").lower()
        相 = (a["相对"] or "").lower()
        标 = "".join("".join(a[k]) for k in ("性别", "年龄", "气质", "用途", "语言")).lower()
        if 名 == 低:
            甲.append(a)                      # 名字完全等于
        elif 低 in 名 or 低 in 文:
            乙.append(a)                      # 名字 / 文件名包含
        elif 低 in 相 or 低 in 标:
            丙.append(a)                      # 路径 / 标签包含
        elif 字 and all(c in (名 + 文 + 相 + 标) for c in 字):
            丁.append(a)                      # 每字都出现（最弱，置底）
    命中 = 甲 + 乙 + 丙 + 丁
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


# ── 角色 → 音色（G5）──────────────────────────────────────────────────────
# 为什么音色挂在【角色】上、不挂在【台词】上：
#   飞彩就是这么做的（character.voiceId，见 知识\配音.md §一）。挂在台词上的坏处是
#   同一个角色十句台词要在十个地方写音色，改一次要改十处，且必然有一处漏掉。
映射路 = 输出 / "角色映射.json"

# 旁白识别清单 —— 与飞彩的两套清单合并（它一套含「旁白」一套不含，是历史遗留）。
# 影匠只留一套，避免「同一句话在两个地方判定不同」。
旁白词 = {"旁白", "旁", "旁述", "narrator", "n", "画外音", "内心独白"}


def 归一(名: str) -> str:
    """角色名 / 音色名 / 相对路径 的统一归一化。

    两层：
      1. 角色名 —— 照抄飞彩 `ew()`：去首尾空格 + 转小写。
         飞彩原文：`characters.find(e => ew(e.name) === r || e.aliases?.some(e => ew(e) === r))`
      2. ★ 路径分隔符 —— 音色库.json 里 `相对` 存的是 **正斜杠**（`男女——情绪分类/女-…wav`），
         而人手写映射表时习惯用 **反斜杠**。不归一就会「明明同一个文件却判不存在」——
         这正是那个坑的第二次发作（第一次是「文件存在≠文件对」）。
    """
    s = (名 or "").strip().lower().replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    return s


def 是旁白(名: str) -> bool:
    return 归一(名) in 旁白词


def 载映射(建: bool = False) -> dict:
    """读 音色\\角色映射.json。不存在时返回空骨架（建=True 则顺手落盘一份）。"""
    if 映射路.exists():
        try:
            return json.loads(映射路.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ 角色映射.json 读不了（{e}），当空表用。")
    空 = {"说明": "角色 → 音色。照抄飞彩：音色挂在角色上。", "版本": 1, "角色": {}, "未定角色": {}}
    if 建:
        输出.mkdir(parents=True, exist_ok=True)
        映射路.write_text(json.dumps(空, ensure_ascii=False, indent=2), encoding="utf-8")
    return 空


def 找角色(名: str, 映射: dict | None = None) -> dict | None:
    """按角色名找映射条目。三级：角色名精确 → 归一化精确 → 比别名。

    ★ 为什么必须归一层：剧本里写「凌霜」、分镜里写「凌霜 」，音色表里写「凌霜」——
        不归一就是三个角色。飞彩专门写了个 `ew()` 干这件事，说明它也踩过。
    """
    映射 = 映射 if 映射 is not None else 载映射()
    角色表 = 映射.get("角色") or {}
    低 = 归一(名)
    if not 低:
        return None
    for 键, v in 角色表.items():
        if 键 == 名 or 归一(键) == 低:
            return v
    for v in 角色表.values():
        for a in (v.get("别名") or []):
            if 归一(a) == 低:
                return v
    return None


def 解析音色(名字或角色: str, 映射: dict | None = None) -> tuple[str, dict | None]:
    """把一个词解析成音色。

    先当【角色名】查映射表，命中就把该角色的音色顶上来；否则原样当【音色名/路径】用。
    ★ 顺序不能反：角色名和音色名可能撞（比如某角色就叫「御姐」），
      而映射表是**人明确指定过的**，比模糊匹配可信。
    返回 (要用的音色词, 命中的角色条目或 None)。
    """
    v = 找角色(名字或角色, 映射)
    if v and (v.get("音色") or "").strip():
        return v["音色"].strip(), v
    return 名字或角色, v


def 检查映射(映射: dict | None = None) -> dict:
    """检查映射表里每个音色是否还在音色库里 —— 库是活的，路径会变。

    返回 {"对": [...], "错": [(角色, 音色词, 原因)], "空": [...]}
    """
    映射 = 映射 if 映射 is not None else 载映射()
    库路 = 输出 / "音色库.json"
    库 = json.loads(库路.read_text(encoding="utf-8")) if 库路.exists() else {"音频": []}
    相对集 = {归一(a["相对"]) for a in 库["音频"]}
    名集 = {归一(a["名字"]) for a in 库["音频"]}
    对, 错, 空 = [], [], []
    for 键, v in (映射.get("角色") or {}).items():
        音 = (v.get("音色") or "").strip()
        if not 音:
            空.append((键, "音色是空的"))
            continue
        if 归一(音) in 相对集:
            对.append((键, 音, "按路径命中"))
        elif 归一(音) in 名集:
            对.append((键, 音, "按名字命中（建议改成路径，名字可能重名）"))
        else:
            错.append((键, 音, "音色库里没有这条"))
    return {"对": 对, "错": 错, "空": 空}


def 标角色(表: list[dict], 映射: dict | None = None, 详: bool = True) -> dict:
    """给台词表批量标上角色对应的音色（原地改表里的「音色」键）。

    台词表的「角色」键可以是角色名、别名、或直接是音色名。
    命中映射 → 用映射里的音色；没命中 → 原样保留（留给 配音.py 的模糊匹配），并记进「没命中」。
    """
    映射 = 映射 if 映射 is not None else 载映射()
    命中, 没命中, 旁白 = 0, [], 0
    for 句 in 表:
        角 = (句.get("角色") or "").strip()
        if not 角:
            continue
        if 是旁白(角):
            旁白 += 1
        v = 找角色(角, 映射)
        if v and (v.get("音色") or "").strip():
            老 = 句.get("音色")
            句["音色"] = v["音色"].strip()
            句["角色命中"] = "旁白" if 是旁白(角) else "映射"
            if 老 and 归一(老) != 归一(句["音色"]) and 详:
                print(f"    ⚠ 第{句.get('序号','?')}句 角色「{角}」的音色被映射改写了：{老} → {句['音色']}")
            命中 += 1
        else:
            句["角色命中"] = "没命中"
            没命中.append((句.get("序号", "?"), 角, 句.get("音色", "")))
    return {"命中": 命中, "没命中": 没命中, "旁白": 旁白, "总句": len(表)}


def 角色命令(参: str = "", 限: int = 40) -> None:
    """`角色` 子命令：看映射表 + 验音色是否还在库里。"""
    映射 = 载映射(建=False)
    角色表 = 映射.get("角色") or {}
    print(f"\n  角色映射表： {映射路}    （{len(角色表)} 个角色）")
    print("  " + "─" * 78)
    if not 角色表:
        print("  （空的。照 音色\\角色映射.json 的格式往里加。）\n")
        return
    检 = 检查映射(映射)
    for 键, v in 角色表.items():
        音 = (v.get("音色") or "").strip()
        位 = [x for x in 检["对"] if x[0] == 键]
        标 = ("✓ " + 位[0][2]) if 位 else "✗ 音色库里没有这条！"
        print(f"  {键:<12} → {音[:52]:<54} {标}")
        for b in (v.get("备选") or [])[:2]:
            print(f"  {'':<12}   备选 · {b[:60]}")
    print("  " + "─" * 78)
    print(f"  ✓ 对 {len(检['对'])}   ✗ 错 {len(检['错'])}   空 {len(检['空'])}")
    for 键, 音, 因 in 检["错"]:
        print(f"     ✗ {键} → {音[:50]}  （{因}）")
    for 键, 因 in 检["空"]:
        print(f"     · {键} → （{因}）")
    print(f"\n  查角色： python 音色库.py --查角色 凌霜")
    print(f"  验一遍： python 音色库.py --验映射\n")


def 查角色(名: str) -> None:
    """查一个角色绑了什么音色（含备选与理由）。"""
    映射 = 载映射()
    v = 找角色(名, 映射)
    if not v:
        print(f"\n  「{名}」不在角色映射表里。")
        角色命令()
        return
    print(f"\n  角色： {v.get('角色') or 名}")
    if v.get("别名"):
        print(f"  别名： {'、'.join(v['别名'])}")
    音 = (v.get("音色") or "").strip()
    print(f"  音色： {音}")
    库路 = 输出 / "音色库.json"
    if 库路.exists():
        库 = json.loads(库路.read_text(encoding="utf-8"))
        for a in 库["音频"]:
            if 归一(a["相对"]) == 归一(音) or 归一(a["名字"]) == 归一(音):
                print(f"         {a['名字']}   {a['秒']}s / {a['采样率']} Hz / {a['声道']} 声道 / {a['MB']} MB")
                print(f"         {a['路径']}")
                break
    if v.get("选它的理由"):
        print(f"  理由： {v['选它的理由']}")
    if v.get("备选"):
        print(f"  备选（{len(v['备选'])} 个）：")
        for b in v["备选"]:
            print(f"         {b}")
    print()


def main() -> None:
    p = argparse.ArgumentParser(description="影匠 · 音色库编目")
    p.add_argument("--查", metavar="词", help="搜索音色，不填则重新编目")
    p.add_argument("--类", help="限定大类")
    p.add_argument("--限", type=int, default=25, help="最多显示多少条")
    p.add_argument("--角色", action="store_true", help="看「角色 → 音色」映射表并验证")
    p.add_argument("--查角色", metavar="名", help="查一个角色绑了什么音色")
    p.add_argument("--验映射", action="store_true", help="检查映射表里的音色是否都还在库里")
    o = p.parse_args()

    if o.角色:
        角色命令()
        return
    if o.查角色:
        查角色(o.查角色)
        return
    if o.验映射:
        检 = 检查映射()
        print(f"\n  角色映射自检： ✓ 对 {len(检['对'])}   ✗ 错 {len(检['错'])}   空 {len(检['空'])}")
        for 键, 音, 因 in 检["错"]:
            print(f"     ✗ {键} → {音}  （{因}）")
        print()
        sys.exit(1 if (检["错"] or 检["空"]) else 0)

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
