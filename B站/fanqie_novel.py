# -*- coding: utf-8 -*-
"""
fanqie_novel.py —— 番茄小说网(fanqienovel.com)正文抓取 + PUA 动态字体解密

════════ 实测结论（2026-10-12，Windows + curl_cffi 0.16.3）════════
1) 页面是服务端渲染(SSR)，无 cookie / 无登录 / 无签名参数：
   - 首页            https://fanqienovel.com/            200，直接给出 23 个 /page/<bookId>
   - 详情页(含目录)   https://fanqienovel.com/page/<bookId>     SSR 直出全部 /reader/<itemId>
   - 阅读页(含正文)   https://fanqienovel.com/reader/<itemId>   正文在
                     window.__INITIAL_STATE__.reader.chapterData.content（<p>…</p> 片段）
2) 正文约 50% 的汉字被替换为 Unicode 私用区(PUA) U+E3E8~U+E55B 的码位，
   对应站点下发的动态字体：
       font-family: DNMrHsV173Pd4pgy
       https://lf3-awef.bytetos.com/obj/awesome-font/c/dc027189e0ba4cd-{400,500,700}.{woff2,woff,otf}
3) 该字体**全站（跨书、跨章节）共用同一份固定子集**：字体名恒为 DNMrHsV173Pd4pgy，
   文件 hash 恒为 dc027189e0ba4cd（实测 3 本不同的书 md5 完全相同）。
   cmap 只有 362 个 PUA 码位，区间 U+E3E8~U+E55B 内有 10 个空档：
       E3F6 E3FE E3FF E419 E45B E4B6 E4D4 E4D8 E51A E51F
   字体本身是 SourceHanSansSC-Normal 的 PUA 子集，**不含任何明文字形**，
   因此无法用字体自身反解，必须靠外部建立的码位->汉字映射表。
4) 反爬：
   - ⚠ curl_cffi 的 impersonate="chrome131" 被**针对性拦截**：/reader/ 一律返回
     6371 字节、<title>验证码中间页</title> 的中间页。chrome124 / chrome136 /
     safari17_0 / edge101 / firefox133 / safari15_5 全部正常。
   - /page/ 与 / 即使在被拦截时也能正常访问。
   - 首页内联脚本含 window.TTGCaptcha.init({aid:2503,...})（字节验证码 SDK）
     与 nonce="<32hex>-argus"（字节 Argus 风控签名占位）。
   - robots.txt 为 "User-Agent: * / Allow: /"（全站放行）。
   - 实测以 ~1.2s 间隔抓 20+ 次未触发验证码；高频抓取后 /reader/ 会被拦，
     换未被拦的 TLS 指纹即可恢复。

════════ 法律提示 ════════
番茄小说的正文是**版权作品**。本模块只应被用于：
  (a) 技术验证 / 互操作性研究；
  (b) 阅读自己有权访问的内容；
  (c) 提取「题材、结构、节奏」等不受版权保护的思想层面要素用于原创改写。
**不要**把抓取到的正文直接用于二次创作发布（照搬原文/照搬人物名与独创性设定），
也不要批量下载。详见 情报/剧本来源调研.md。
"""

import html as _html
import re
import time

# ─────────────────────────────────────────────────────────────
# 权威映射表：362 项，由字形图（情报/_font_probe/权威字形表_1~4.png）
# 逐格对照得出，并用 6 章真实语料（约 6000 字）验证过语义通顺。
# 空档(不在 cmap 内)：E3F6 E3FE E3FF E419 E45B E4B6 E4D4 E4D8 E51A E51F
# ─────────────────────────────────────────────────────────────
_TABLE = """
E3E8=在 E3E9=主 E3EA=特 E3EB=家 E3EC=军 E3ED=然 E3EE=表 E3EF=场 E3F0=4 E3F1=要 E3F2=只
E3F3=v E3F4=和 E3F5=6 E3F7=别 E3F8=还 E3F9=g E3FA=现 E3FB=儿 E3FC=岁 E3FD=此 E400=象
E401=月 E402=3 E403=出 E404=战 E405=工 E406=相 E407=O E408=男 E409=直 E40A=失 E40B=世
E40C=F E40D=都 E40E=平 E40F=文 E410=什 E411=V E412=O E413=将 E414=真 E415=T E416=那
E417=当 E418=会 E41A=立 E41B=些 E41C=u E41D=是 E41E=十 E41F=张 E420=学 E421=气 E422=大
E423=爱 E424=两 E425=命 E426=全 E427=后 E428=东 E429=性 E42A=通 E42B=被 E42C=1 E42D=它
E42E=乐 E42F=接 E430=而 E431=感 E432=车 E433=山 E434=公 E435=了 E436=常 E437=以 E438=何
E439=可 E43A=话 E43B=先 E43C=p E43D=i E43E=叫 E43F=轻 E440=M E441=土 E442=w E443=着
E444=变 E445=尔 E446=快 E447=l E448=个 E449=说 E44A=少 E44B=色 E44C=里 E44D=安 E44E=花
E44F=远 E450=7 E451=难 E452=师 E453=放 E454=t E455=报 E456=认 E457=面 E458=道 E459=S
E45A=克 E45C=地 E45D=度 E45E=I E45F=好 E460=机 E461=U E462=民 E463=写 E464=把 E465=万
E466=同 E467=水 E468=新 E469=没 E46A=书 E46B=电 E46C=吃 E46D=像 E46E=斯 E46F=5 E470=为
E471=y E472=白 E473=几 E474=日 E475=教 E476=看 E477=但 E478=第 E479=加 E47A=候 E47B=作
E47C=上 E47D=拉 E47E=住 E47F=有 E480=法 E481=r E482=事 E483=应 E484=位 E485=利 E486=你
E487=声 E488=身 E489=国 E48A=问 E48B=马 E48C=女 E48D=他 E48E=Y E48F=比 E490=父 E491=x
E492=A E493=H E494=N E495=S E496=x E497=边 E498=美 E499=对 E49A=所 E49B=金 E49C=活
E49D=回 E49E=意 E49F=到 E4A0=z E4A1=从 E4A2=j E4A3=知 E4A4=又 E4A5=内 E4A6=因 E4A7=点
E4A8=Q E4A9=三 E4AA=定 E4AB=8 E4AC=R E4AD=b E4AE=正 E4AF=或 E4B0=夫 E4B1=向 E4B2=德
E4B3=听 E4B4=更 E4B5=得 E4B7=告 E4B8=并 E4B9=本 E4BA=q E4BB=过 E4BC=记 E4BD=L E4BE=让
E4BF=打 E4C0=f E4C1=人 E4C2=就 E4C3=者 E4C4=去 E4C5=原 E4C6=满 E4C7=体 E4C8=做 E4C9=经
E4CA=K E4CB=走 E4CC=如 E4CD=孩 E4CE=C E4CF=G E4D0=给 E4D1=使 E4D2=物 E4D3=最 E4D5=笑
E4D6=部 E4D7=员 E4D9=等 E4DA=受 E4DB=k E4DC=行 E4DD=一 E4DE=条 E4DF=果 E4E0=动 E4E1=光
E4E2=门 E4E3=头 E4E4=见 E4E5=往 E4E6=自 E4E7=解 E4E8=成 E4E9=处 E4EA=天 E4EB=能 E4EC=于
E4ED=名 E4EE=其 E4EF=发 E4F0=总 E4F1=母 E4F2=的 E4F3=死 E4F4=手 E4F5=入 E4F6=路 E4F7=进
E4F8=心 E4F9=来 E4FA=h E4FB=时 E4FC=力 E4FD=多 E4FE=开 E4FF=已 E500=许 E501=d E502=至
E503=由 E504=很 E505=界 E506=n E507=小 E508=与 E509=Z E50A=想 E50B=代 E50C=么 E50D=分
E50E=生 E50F=口 E510=再 E511=妈 E512=望 E513=次 E514=西 E515=风 E516=种 E517=带 E518=J
E519=实 E51B=情 E51C=才 E51D=这 E51E=E E520=神 E521=格 E522=长 E523=觉 E524=间
E525=年 E526=眼 E527=无 E528=不 E529=亲 E52A=关 E52B=结 E52C=0 E52D=友 E52E=信 E52F=下
E530=却 E531=重 E532=己 E533=老 E534=2 E535=音 E536=字 E537=m E538=呢 E539=明 E53A=之
E53B=前 E53C=高 E53D=P E53E=B E53F=目 E540=太 E541=e E542=9 E543=起 E544=棱 E545=她
E546=也 E547=W E548=用 E549=方 E54A=子 E54B=英 E54C=每 E54D=理 E54E=便 E54F=四 E550=数
E551=期 E552=中 E553=C E554=外 E555=样 E556=a E557=海 E558=们 E559=任 E55A=们 E55B=任
""".split()

PUA2CHAR = {}
for _tok in _TABLE:
    _cp, _ch = _tok.split("=", 1)
    PUA2CHAR[int(_cp, 16)] = _ch

# 一致性自检：码位必须落在 cmap 区间内、且跳过 10 个空档
_GAPS = {0xE3F6, 0xE3FE, 0xE3FF, 0xE419, 0xE45B, 0xE4B6, 0xE4D4, 0xE4D8, 0xE51A, 0xE51F}
_EXPECT = [c for c in range(0xE3E8, 0xE55C) if c not in _GAPS]
assert len(_EXPECT) == 362, len(_EXPECT)
assert sorted(PUA2CHAR) == _EXPECT, (
    "映射表码位与字体 cmap 不一致：缺失 %s，多余 %s"
    % ([hex(c) for c in set(_EXPECT) - set(PUA2CHAR)],
       [hex(c) for c in set(PUA2CHAR) - set(_EXPECT)])
)


def decrypt(text):
    """把含 PUA 混淆字符的正文还原为明文。"""
    return "".join(PUA2CHAR.get(ord(c), c) for c in text)


def clean_chapter_text(html_text):
    """从阅读页 HTML 抽出本章正文（已去标签、已反转义，但尚未解密）。"""
    paras = re.findall(r"<p>(.*?)</p>", html_text, re.S)
    return _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))


def make_session(impersonate="chrome124"):
    """返回可用的 curl_cffi session。

    ⚠ 不要用 "chrome131"：实测该 TLS 指纹被番茄针对性拦截，
      /reader/ 一律只返回 6371 字节的『验证码中间页』。
    """
    from curl_cffi import requests as creq
    return creq.Session(impersonate=impersonate)


_HEADERS = {"Accept-Language": "zh-CN,zh;q=0.9", "Accept": "text/html,application/xhtml+xml"}


def _get(sess, url, minlen=800, tries=3, delay=1.3):
    last = ""
    for i in range(tries):
        try:
            r = sess.get(url, headers=_HEADERS, timeout=25)
            if r.status_code == 200 and len(r.text) >= minlen:
                return r.text
            last = "HTTP %s len=%d" % (r.status_code, len(r.text))
        except Exception as e:                                       # noqa: BLE001
            last = type(e).__name__
        time.sleep(delay * (i + 1))
    raise RuntimeError("%s -> %s" % (url, last))


def list_chapters(book_id, sess=None):
    """从详情页拿章节 id 列表（详情页 SSR 直出，无需解密）。"""
    sess = sess or make_session()
    page = _get(sess, "https://fanqienovel.com/page/%s" % book_id, minlen=3000)
    out, seen = [], set()
    for m in re.finditer(r'''["'/]reader/(\d{15,25})''', page):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def fetch_chapter(chapter_id, sess=None):
    """抓一章并解密，返回 (明文, 元信息)。"""
    sess = sess or make_session()
    page = _get(sess, "https://fanqienovel.com/reader/%s" % chapter_id, minlen=3000)
    t = re.search(r"<title>(.*?)</title>", page, re.S)
    raw = clean_chapter_text(page)
    info = {
        "chapter_id": chapter_id,
        "title": t.group(1).strip() if t else "",
        "raw_len": len(raw),
        "pua_ratio": sum(1 for c in raw if "\ue000" <= c <= "\uf8ff") / max(1, len(raw)),
    }
    return decrypt(raw), info


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("映射表项数: %d（应为 362）" % len(PUA2CHAR))
    s = make_session()
    chs = list_chapters("7137359676424850443", s)
    print("《娇养玫瑰》目录章节数: %d" % len(chs))
    time.sleep(1.0)
    txt, info = fetch_chapter(chs[1], s)
    print("第 2 章: %s" % info["title"])
    print("  原文 %d 字，PUA 占比 %.1f%%" % (info["raw_len"], info["pua_ratio"] * 100))
    print("  " + txt[:240].replace("\n", " "))
