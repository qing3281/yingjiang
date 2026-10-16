# -*- coding: utf-8 -*-
"""
探针 23 —— 用「字频异常」自动揪出错误映射（不靠肉眼）

原理：把解码后的正文按字频排序，与标准现代汉语常用字频表对比。
某字在本该低频的位置却高频出现（例：一部武侠里『约』『格』『任』『每』满天飞），
就是映射错的字。再把这些可疑码位的原始上下文打出来即可定罪。
"""
import html as _html
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\DSHworkspace\B站")
from fanqie_font import PUA2CHAR, decrypt

from curl_cffi import requests as creq

# 现代汉语高频字 Top 120（用于找「不该这么高频却高频」的异常）
COMMON = set("的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和"
             "要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起"
             "发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所"
             "同日手又行意动方期它头经长儿回位分爱老因很给名法间斯知世什两次"
             "使身者被高已亲其进此话常与活正感见明问力理尔点文几定本公特做外"
             "孩相西果走将月十实向声车全信重三机工物气每并别真打太新比才便夫"
             "再书部水像眼等体却加电主界门利海受听表德少克代员许稜先口由死安"
             "写性马光白或住难望教命花结乐色更拉东神记处让母父应直字场平报友"
             "关放至张认接告入笑内英军候民岁往何度山觉路带万男边风解叫任金快"
             "原吃妈变通师立象数四失满战远格士音轻目条呢病始达深完今提求清王"
             "化空业思切怎非找片罗钱紶吗语元喜曾离飞科言干流欢约各即指合反题"
             "必该论交终林请医晚制球决窢传画保读运及则房早院量苦火布品近坐产"
             "答星精视五连司巴奇管类未朋且婚台夜青北队久乎越观落尽形影红爸百"
             "令周吧识步希亚术留市半热送兴造谈容极随演收首根讲整式取照办强石"
             "古华諣拿计您装似足双妻尼转诉米称丽客南领节衣站黑刻统断福城故历"
             "惊脸选包紧争另建维绝树系伤示愿持千史谁准联妇纪基买志静阿诗独复"
             "痛消社算义竟确酒需单治卡幸兰念举仅钟怕共毛句息功官待究跟穿室易"
             "游程号居考突皮哪费倒价图具刚脑永歌响商礼细专黄块脚味灵改据般破"
             "引食仍存众注笔甚某沉血备习校默务土微娘须试怀料调广蜖苏显赛查密"
             "议底列富梦错座参八除跑亮假印设线温虽掉京初养香停际致阳纸李纳验"
             "助激够严证帝饭忘趣支春集丈木研班普导顿睡展跳获艺六波察群皇段急"
             "庭创区奥器谢弟店否害草排背止组州朝封睛板角况曲馆育忙质河续哥呼"
             "若推境遇雨标姐充围案伦护冷警贝著雪索剧啊船险烟依斗值帮汉慢佛肯"
             "闻唱沙局伯族低玩资屋击速顾泪洲团圣旁堂兵七露园牛哭旅街劳型烈姑"
             "陈莫鱼异抱宝权鲁简态级票怪寻杀律胜份汽右洋范床舞秘午登楼贵吸责"
             "例追较职属渐左录丝牙党继托赶章智冲叶胡吉卖坚喝肉遗救修松临藏担"
             "戏善卫药悲敢靠伊村戴词森耳差短祖云规窗散迷油旧适乡架恩投弹铁博"
             "雷府压超负勒杂醒洗采毫嘴毕九冰既状乱景席珍童顶派素脱农疑练野按"
             "犯拍征坏骨余承置臂彩灯巨琴免环姆暗换技翻束增忍餐洛塞缺忆判欧层"
             "付阵玛批岛项狗休懂武革良恶恋委拥娜妙探呀营退摇弄桌熟诺宣银势奖"
             "宫忽套康供优课鸟喊降夏困刘罪亡鞋健模败伴守挥鲜财孤枪禁恐伙杰迹"
             "妹藸遍盖副坦牌江顺秋萨菜划授归浪听凡预奶雄升碃编典袋莱含盛济蒙"
             "棋端腿招释介烧误")

s = creq.Session(impersonate="chrome131")
H = {"Accept-Language": "zh-CN,zh;q=0.9"}


def get(u, tries=4):
    last = ""
    for i in range(tries):
        try:
            r = s.get(u, headers=H, timeout=25)
            if r.status_code == 200 and len(r.text) > 5000:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = type(e).__name__
        import time as _t; _t.sleep(1.2 * (i + 1))
    raise RuntimeError(f"{u} -> {last}")


# 用 5 本不同类型（都市/宫斗/穿清）做统计
BOOKS = ["7137359676424850443", "7096667097870109733", "6823667291557727235",
         "7674861059122924569", "7091150316644600867"]
raw_all, dec_all = [], []
for BK in BOOKS:
    try:
        page = get(f"https://fanqienovel.com/page/{BK}")
    except Exception as e:
        print(f"[{BK}] 跳过 {e}"); continue
    cids, seen = [], set()
    for m in re.finditer(r'["\'/]reader/(\d{15,25})', page):
        if m.group(1) not in seen:
            seen.add(m.group(1)); cids.append(m.group(1))
    for cid in cids[1:6]:
        try:
            t = get(f"https://fanqienovel.com/reader/{cid}")
        except Exception:
            continue
        paras = re.findall(r"<p>(.*?)</p>", t, re.S)
        raw = _html.unescape(re.sub(r"<[^>]+>", "", "".join(paras)))
        if len(raw) < 500:
            continue
        raw_all.append(raw)
        dec_all.append(decrypt(raw))
        import time as _t; _t.sleep(0.6)

raw = "\n".join(raw_all)
dec = "\n".join(dec_all)
print(f"统计语料：原始 {len(raw)} 字（覆盖 {len(BOOKS)} 本不同类型的小说）\n")

# 1) 覆盖率
pua_total = sum(1 for ch in raw if "\ue000" <= ch <= "\uf8ff")
uniq = set(ch for ch in raw if "\ue000" <= ch <= "\uf8ff")
unmapped = uniq - set(chr(c) for c in PUA2CHAR)
print(f"PUA 字符总数 {pua_total}；不同码位 {len(uniq)}；未映射码位 {len(unmapped)}")

# 2) 解码后仍残留的 PUA
left = Counter(ch for ch in dec if "\ue000" <= ch <= "\uf8ff")
print(f"解码后残留未映射字符 {sum(left.values())} 个 / ({sum(left.values())/max(pua_total,1)*100:.2f}%)")
for ch, n in left.most_common(20):
    print(f"    U+{ord(ch):04X} x{n}")
print()

# 3) 字频异常：本字在解码文本中的占比 vs 是否为常用字
cnt = Counter(ch for ch in dec if "\u4e00" <= ch <= "\u9fff")
total_cjk = sum(cnt.values())
print("== 字频异常榜（解码后占比 > 0.35% 却不在常用字表里，或占比畸高）==")
rows = []
for ch, n in cnt.most_common(80):
    share = n / total_cjk * 100
    suspect = (share > 0.35 and ch not in COMMON)
    rows.append((ch, n, share, suspect))
for ch, n, share, sus in rows[:60]:
    flag = "  <<< 可疑" if sus else ""
    print(f"   {ch}  {n:6d}  {share:5.2f}%{flag}")

print()
print("== 用 PUA 码位反查：每个映射字在解码文本里的占比（只列占比 > 0.3% 的）==")
by_char = Counter()
for ch in dec:
    by_char[ch] += 1
rev = {}
for cp, c in PUA2CHAR.items():
    rev.setdefault(c, []).append(cp)
for ch, n in by_char.most_common(70):
    share = n / total_cjk * 100
    if share > 0.3:
        cps = ",".join(f"{c:04X}" for c in rev.get(ch, []))
        tag = "★映射字" if ch in rev else "（非映射，原文自带）"
        print(f"   {ch} {n:6d} {share:5.2f}%  {tag} {cps}")
