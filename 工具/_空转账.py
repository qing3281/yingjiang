# -*- coding: utf-8 -*-
"""空转账 —— 把「思考里刷废话」变成一个能看到的数字。

为什么要这个：
  用户已经说过三次（10-14 02:19 / 10-15 01:20 / 10-15 01:50），
  我每次都「知道了」，每次照旧。**承诺不管用，因为承诺不产生数字。**
  「我加的条件」那一行之所以管用，是因为它每轮都要打出来、能被当场看见。
  这个脚本就是给空转做同一件事：**让它每轮开工时出现在眼前。**

什么叫「空转」——机器可判的判据（不靠感觉）：
  推理正文按句切开，一句话如果
    ① 长度 <= 12 个字
    ② 去掉标点后，每个词都在「催促词表」里
  就算一次空转。催促词表是那些**只表示「快开始吧」、不携带任何信息**的词。

用法：
  python _空转账.py            # 最近 5 场
  python _空转账.py --今        # 只看今天
  python _空转账.py --细        # 列出空转最多的原文片段
"""
import os, sys, re, json, glob, collections
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
SESS = r"D:\DSH\home\sessions\--D-DSHworkspace--"
北京 = timezone(timedelta(hours=8))

# 只表示「快开始吧」的词 —— 不带任何信息量
催促 = {
    'emit', 'go', 'write', 'writing', 'ok', 'okay', 'enough', 'now', 'hmm', 'wait',
    'actually', 'let', 'me', 'here', 'nope', 'yes', 'good', 'right', 'so', 'and',
    'but', 'first', 'next', 'then', 'done', 'alright', 'fine', 'sure', 'just',
    'now.', 'go.', 'emit.', 'write.', 'ok.', 'okay.', 'enough.', 'hmm.', 'wait.',
    '嗯', '好', '行', '开始', '写', '做', '走', '来', '继续', '那么', '现在',
}
去标点 = re.compile(r"[.。，,！!？?：:；;、…~～\-—\s]+")


def 是空转(句):
    干 = 去标点.sub(' ', 句).strip().lower()
    if not 干 or len(干) > 14:
        return False
    词 = 干.split()
    if not 词:
        return False
    return all(w in 催促 for w in 词)


def 切句(文):
    return [s for s in re.split(r'[\n。！？!?；;]+', 文) if s.strip()]


def 读一场(路径):
    """返回 [(时刻, 推理字数, 空转次数, [空转片段...]), ...]"""
    import zstandard as zstd
    d = zstd.ZstdDecompressor()
    out = []
    try:
        with open(路径, 'rb') as f:
            文 = d.stream_reader(f).read().decode('utf-8', 'replace')
    except Exception as e:
        return out, str(e)
    for 行 in 文.splitlines():
        if not 行.strip():
            continue
        try:
            j = json.loads(行)
        except Exception:
            continue
        if j.get('type') != 'assistant/message':
            continue
        dat = j.get('data') or {}
        msg = dat.get('message') or {}
        for c in (msg.get('content') or []):
            if not isinstance(c, dict) or c.get('type') != 'reasoning':
                continue
            t = c.get('text') or ''
            句s = 切句(t)
            坏 = [s.strip() for s in 句s if 是空转(s)]
            if not t:
                continue
            out.append((j.get('time'), len(t), len(坏), 坏))
    return out, None


def 主():
    参 = sys.argv[1:]
    只要今 = '--今' in 参
    要细 = '--细' in 参
    n = 5
    for a in 参:
        if a.isdigit():
            n = int(a)

    import zstandard  # noqa: F401  确认装了
    场s = sorted(glob.glob(os.path.join(SESS, '*', 'session.v4.jsonl.zstd')),
                 key=os.path.getmtime, reverse=True)
    if 只要今:
        今 = datetime.now(北京).date()
        场s = [p for p in 场s if datetime.fromtimestamp(os.path.getmtime(p), 北京).date() == 今]
    场s = 场s[:n]

    print("=" * 88)
    print("空转账　（推理里只表示「快开始吧」的废话）")
    print("=" * 88)
    总字 = 总坏 = 0
    最坏 = []
    for p in 场s:
        条, 错 = 读一场(p)
        if 错:
            print(f"  [读不了] {os.path.basename(os.path.dirname(p))}  {错}")
            continue
        字 = sum(x[1] for x in 条)
        坏 = sum(x[2] for x in 条)
        总字 += 字
        总坏 += 坏
        占比 = (坏 / max(1, len(条))) * 100
        名 = os.path.basename(os.path.dirname(p))[:44]
        t = datetime.fromtimestamp(os.path.getmtime(p), 北京).strftime('%m-%d %H:%M')
        print(f"  {t}  {名:<46} 推理 {len(条):>4} 段 {字:>7,} 字   空转 {坏:>5} 次  每段 {坏/max(1,len(条)):.1f}")
        for 时, l, k, 片段 in 条:
            if k:
                最坏.append((k, 名, t, 片段))

    print()
    print(f"  合计：推理 {总字:,} 字，空转 {总坏:,} 次")
    if 最坏:
        最坏.sort(reverse=True, key=lambda x: x[0])
        print()
        print("  ── 最严重的几段 ──")
        for k, 名, t, 片段 in 最坏[:8]:
            print(f"    {k:>3} 次  {t}  {名}   例：{' / '.join(片段[:6])}")
    print()
    print("  目标：**每段 0.5 次以下**。现在是上面的数。")
    print("  下次开工时这个数字会出现在 _开工.py 的第一段。")


if __name__ == '__main__':
    主()
