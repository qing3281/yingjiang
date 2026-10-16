# -*- coding: utf-8 -*-
"""多角色配音 v2：从 `03-台词.md` 读台词表 → 合成 → 混音 → 写字幕 → 烧进画面。

和 `_配长片.py` 的区别（那个是《雪线》的单角色硬编码版）：

1. **台词表从文件读**，不写死在脚本里。剧组的台词一改就得改代码，那是错的。
2. **每个说话人各自一支音色**。走 `配音.角色定音色(名)`（角色 → 音色的映射表），
   没有映射的角色按名字当音色词模糊匹配，再不行退回旁白音色 —— 但**会报出来**，
   不会静默用错人的声音。
3. **字幕时间用「实测音频时长」**，不用「字数 ÷ 4.5」估。估的那个是假的：
   实际语速随文本、情感、音色变，估出来的时间轴会跟声音错位，
   而错位在静音播放时看不出来（字幕停在那儿，声音早说完了）。
4. **一条命令带烧字幕**（`--烧字幕`）。

台词表格式（`作品\\<戏>\\03-台词.md`），每行一句，用 `|` 或 `·` 分隔都认：

    格1 | 旁白 | 光绪二十六年，京城落了一场大雪。
    格7 | 沈砚 | 你回来做什么。
    格8 | 裴照 | 磨刀。 | Angry

    第三格（可选）是情感；不写就是 Neutral。

也认 markdown 表格行（`| 格1 | 旁白 | 台词 |`），会自动跳过表头分隔行。

用法：
    python _配片.py 刀鞘                    # 合成 + 混音 + 写字幕
    python _配片.py 刀鞘 --只合成            # 只为调试台词
    python _配片.py 刀鞘 --烧字幕            # 混完顺手烧进画面
    python _配片.py 刀鞘 --每段秒 4.56 --转场吃 0.5
"""
import argparse
import os
import re
import subprocess
import sys

根 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 根)

import 配音  # noqa: E402

FFMPEG = os.path.join(根, "_bin", "ffmpeg.exe")
旁白音色 = "磁性御姐音，影视解说气场全开"


def 时(t):
    h, m, s = int(t // 3600), int((t % 3600) // 60), t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def 探秒(路):
    """音频/视频的真实时长。不依赖 ffprobe —— `_bin\\` 下只有 ffmpeg.exe。"""
    try:
        r = subprocess.run([FFMPEG, "-i", 路, "-hide_banner"],
                           capture_output=True, text=True, errors="replace")
        m = re.search(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d{1,3})", r.stderr or "")
        if m:
            h, mi, s, ms = m.groups()
            return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def 片有声音轨(路, 报道=None):
    """片子自带的音轨在不在、是不是真有声音。

    H3 是原生有声模型，每格都带一条 AAC。但**「有这条流」不等于「里面有声」** ——
    所以这里既看流，也真解码量几次有效值：有效值低于 0.002 就当没有，
    免得把一条全静音的轨道拼进去、还以为留住了环境音。
    """
    try:
        r = subprocess.run([FFMPEG, "-i", 路, "-hide_banner"],
                           capture_output=True, text=True, errors="replace")
        有流 = bool(re.search(r"Stream #\d+:\d+.*: Audio:", r.stderr or ""))
    except Exception:  # noqa: BLE001
        有流 = False
    if not 有流:
        if 报道:
            报道("  片子没有音轨 → 只用棕噪打底")
        return False
    # 真量一次。★ 只量开头 3 秒是不够的：片头卡是 2 秒黑场静音，
    #   整片开头一量就是 0.0000，会把一条满载雨声的音轨判成「静音」。
    #   所以在 10% / 40% / 70% / 95% 四处各量 2 秒，取最大。
    总 = 探秒(路)
    值 = 0.0
    for 比 in (0.10, 0.40, 0.70, 0.95):
        起 = max(0.0, 总 * 比)
        try:
            r = subprocess.run([FFMPEG, "-ss", f"{起:.2f}", "-t", "2", "-i", 路,
                                "-af", "volumedetect", "-f", "null", os.devnull],
                               capture_output=True, text=True, errors="replace")
            m = re.search(r"mean_volume:\s*(-?[\d.]+)", r.stderr or "")
            if m:
                值 = max(值, 10 ** (float(m.group(1)) / 20))
        except Exception:  # noqa: BLE001
            pass
    if 值 < 0.002:
        if 报道:
            报道(f"  片子音轨是静的（有效值 {值:.4f}）→ 只用棕噪打底")
        return False
    if 报道:
        报道(f"  ✓ 留用片子自带的音轨（有效值 {值:.4f}），说话时侧链把它压下去")
    return True


def 净说话人(谁):
    """把台词表里的说话人变成查音色映射用的键。

    「沈砚（少年）」这种人名带括号的写法，**括号里的字才是这个声音的身份** ——
    格26 那一句是十年前的沈砚，用成年声「同一个人隔了十年」就不成立了。
    所以先拼「括号内 + 括号外」（→「少年沈砚」）当首选键，拼不出来再退回括号外的名字。
    直接拿「沈砚」去查会命中成年沈砚的音色，而且**不报错** —— 这种错最难发现。
    """
    m = re.match(r"^(.*?)[（(](.*?)[)）]\s*$", 谁.strip())
    if m and m.group(1).strip() and m.group(2).strip():
        return [m.group(2).strip() + m.group(1).strip(), m.group(1).strip()]
    return [谁.strip()]


def 读角色名(文):
    """从 03-台词.md 里把声明的角色名读出来。

    文件里有一行 **角色名（只有这六个）**：陈老根 · 系统 · 阿棠 · 周执 · 内门执事 · 旁白。
    这一行就是这份台词表自己声明的**合法说话人全集**，拿它当闸门，
    比在代码里再抄一份名单可靠 —— 名单改了台词表就跟着变。
    """
    for 行 in 文.splitlines():
        if "角色名" in 行 and "·" in 行:
            m = re.search(r"[：:]\s*(.+)$", 行.strip())
            if m:
                名 = [x.strip().strip("* 　") for x in m.group(1).split("·")]
                名 = [x for x in 名 if x]
                if len(名) >= 2:
                    return set(名)
    return set()


def 读台词(md路, 报):
    """从 03-台词.md 抠出 (格号, 说话人, 文本, 情感)。

    ★ 只认**声明过的说话人**。
    台词表末尾还有一张「空格说明」表：

        | 格 | 上一句 | 说明 |
        | 2 | 3 | 让观众先看清这张脸和这双手，上一句旁白还在空气里 |

    它的第 2 列是**上一句的句号**（数字），第 3 列是给人看的备注。
    没有说话人闸门的话，这张表会被当成台词读进来 ——
    句子是「让观众先看清这张脸和这双手」，说话人是「3」。
    查不到映射就退回旁白音，于是**旁白会把这句备注念出来**，
    而且插在格 2 的画面里。79 句里混着 6 句这样的，
    日志只写「⚠ 查映射失败(('3',))→退回旁白音」，夹在几十行里看不见。
    """
    文 = open(md路, encoding="utf-8").read()
    允许 = 读角色名(文)
    if 允许:
        允许 |= {"旁白", "旁白君", "解说"}
    表 = []
    for 行 in 文.splitlines():
        行 = 行.strip()
        if not 行 or 行.startswith("#"):
            continue
        # 跳过 markdown 表格的分隔行 |---|---|
        if re.fullmatch(r"\|[\s:|-]+\|", 行):
            continue
        行 = 行.strip("|").strip()
        段 = [x.strip() for x in re.split(r"\s*[|·]\s*", 行)]
        if len(段) < 3:
            continue
        m = re.match(r"格?\s*(\d+)", 段[0])
        if not m:
            continue
        # 「说话人 | 台词」或者带表头的「格号 | 说话人 | 台词」
        if 段[1] in ("说话人", "谁", "角色"):
            continue
        if 允许 and 段[1] not in 允许:
            continue          # ← 说话人不在这份表自己声明的名单里，不是台词
        表.append({"格": int(m.group(1)), "谁": 段[1], "查": 净说话人(段[1]),
                   "文本": 段[2], "情感": 段[3] if len(段) > 3 else "Neutral"})
    return 表


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("戏")
    ap.add_argument("--只合成", action="store_true")
    ap.add_argument("--无底噪", action="store_true")
    ap.add_argument("--无原声", action="store_true",
                    help="丢掉片子自带的音轨（H3 出的雨声/脚步声/环境音），只用棕噪打底")
    ap.add_argument("--原声量", type=float, default=0.7,
                    help="片子自带音轨的倍数，默认 0.7；压过人声由侧链自动完成")
    ap.add_argument("--人声量", type=float, default=2.6,
                    help="台词相对原声的增益（默认 2.6 ≈ +8.3 dB）。"
                         "实测：不加这句台词只比 H3 环境声高 2.9 dB，听着像念白埋在雨里")
    ap.add_argument("--每段秒", type=float, default=4.4583,
                    help="H3 每格 107 帧 / 24fps = 4.4583 秒（旧 wan2.2 是 4.56，不要混用）")
    ap.add_argument("--转场吃", type=float, default=0.5)
    ap.add_argument("--片", default="")
    ap.add_argument("--烧字幕", action="store_true")
    ap.add_argument("--字号", type=int, default=24)
    参 = ap.parse_args()

    def 报(s):
        print(s, flush=True)

    步长 = 参.每段秒 - 参.转场吃
    戏目录 = os.path.join(根, "作品", 参.戏)
    出目录 = os.path.join(戏目录, "配音")
    os.makedirs(出目录, exist_ok=True)

    md路 = os.path.join(戏目录, "03-台词.md")
    if not os.path.exists(md路):
        报(f"✗ 找不到 {md路}")
        return 1
    表 = 读台词(md路, 报)
    if not 表:
        报(f"✗ {md路} 里一句台词都没读到")
        return 1
    报(f"台词 {len(表)} 句　时间轴 每段 {参.每段秒}s − 转场 {参.转场吃}s = 步长 {步长}s")

    # ── 每个说话人一支音色，全部先解析出来，有找不到的当场报 ──
    人 = []
    for t in 表:
        if t["谁"] not in 人:
            人.append(t["谁"])
    音色 = {}
    报("")
    for n in 人:
        键们 = next(t["查"] for t in 表 if t["谁"] == n)
        # ★ 旁白也要先查映射表。
        # 老版这里直接给死值就 continue 了，于是《觉醒》里挑好的那把
        # 「磁性男中音」永远轮不上 —— 全片第一句和最后一句（题眼）
        # 会用硬编码的磁性御姐说出来，日志还写着「旁白固定」，看着挺正常。
        音色[n] = None
        for k in 键们:
            try:
                色, 源 = 配音.角色定音色(k)
            except Exception:  # noqa: BLE001
                continue
            # ★ 空「源」= 没命中任何映射，只是把输入原样吐回来。
            # 拿它当成功会把「阿七（画外）」这种查表键（→「画外阿七」）
            # 直接送进合成，再被模糊匹配到一支**谁也不知道是什么**的音色，
            # 而且全程不报错。这一条必须挡在这里。
            if not 源:
                continue
            音色[n] = (色, 源 if k == n else f"{源}·{k}")
            break
        if not 音色[n]:
            音色[n] = (旁白音色, f"⚠ 查映射失败({键们})→退回旁白音")
        报(f"  {n:<10} {音色[n][1]:<14} {音色[n][0]}")

    # ── 合成 ──
    # ★ 同一个格里常常有好几句（格5 周泰两句、格9 赵崇武两句…）。
    # 只按「(格号−1)×步长 + 偏」算起点的话，同格几句会**全叠在同一个时刻**，
    # 四个人的声音同时从喇叭里出来。必须让同格的下一句接在上一句真正说完之后。
    # 用实测时长而不是估长：估短了会压字，估长了会拖到下一格。
    报("\n══ 合成 ══")
    段们 = []
    格末 = {}          # 格号 → 本格上一句的结束时间
    越界 = []
    for i, t in enumerate(表, 1):
        基 = round((t["格"] - 1) * 步长 + t.get("偏", 0.7), 3)
        起 = round(max(基, 格末.get(t["格"], 0.0)), 3)
        存 = os.path.join(出目录, f"{i:02d}_{re.sub(r'[（）()]', '_', t['谁']).strip('_')}.wav")
        报(f"  [{i}] 格{t['格']} @{起}s [{t['谁']}] 「{t['文本']}」")
        if os.path.exists(存) and 参.只合成:
            报(f"      复用 {os.path.basename(存)}")
        else:
            try:
                r = 配音.合成(t["文本"], 音色=音色[t["谁"]][0], 情感=t["情感"],
                              存到=存, 报=lambda s: None)
            except Exception as e:  # noqa: BLE001
                报(f"      ✗ {type(e).__name__}: {e}")
                continue
            if not r or not os.path.exists(存):
                报("      ✗ 合成没出文件")
                continue
            报(f"      ✓ {os.path.getsize(存)/1024:.0f} KB  "
               f"{r.get('ComfyUI耗时', r.get('耗时', '?'))} 秒")
        真 = 探秒(存)
        if 真 <= 0:
            报("      ⚠ 量不出时长，这一句的字幕会不准")
        格末[t["格"]] = 起 + (真 if 真 > 0 else len(t["文本"]) / 4.5 + 0.5) + 0.18
        下格起 = t["格"] * 步长
        if 格末[t["格"]] > 下格起:
            越界.append(f"格{t['格']} 说到 {格末[t['格']]:.2f}s，已经进了下一格（下一格 {下格起:.2f}s 起）")
        段们.append({"路": 存, "起": 起, "文本": t["文本"],
                     "格": t["格"], "谁": t["谁"], "秒": 真})

    if 越界:
        报(f"\n  ⚠ {len(越界)} 处台词说过了格子的边界：")
        for x in 越界:
            报(f"      {x}")
        报("      （台词长过 4.06 秒的格子是正常的，但要知道它压到了下一格的画面上）")

    if not 段们:
        报("✗ 一句都没成")
        return 1

    # ── 字幕：用实测时长，不用估 ──
    srt = []
    for i, s in enumerate(段们, 1):
        落 = s["秒"] if s["秒"] > 0 else len(s["文本"]) / 4.5 + 0.5
        srt.append(f"{i}\n{时(s['起'])} --> {时(s['起'] + 落)}\n{s['文本']}\n")
    srt路 = os.path.join(出目录, "_台词.srt")
    open(srt路, "w", encoding="utf-8").write("\n".join(srt))
    总话 = sum(s["秒"] for s in 段们 if s["秒"] > 0)
    报(f"\n  字幕：{srt路}　{len(srt)} 条　台词总时长 {总话:.1f} 秒")

    if 参.只合成:
        return 0

    # ── 找片子 ──
    片名 = 参.片
    if not 片名:
        片夹 = os.path.join(戏目录, "片")
        候选 = [f for f in os.listdir(片夹)
                if f.endswith(".mp4") and "有声" not in f and "字幕" not in f] \
               if os.path.isdir(片夹) else []
        if not 候选:
            报("✗ 片\\ 下没有成片，先跑 --拼")
            return 1
        片名 = sorted(候选, key=lambda f: -os.path.getsize(
            os.path.join(片夹, f)))[0]
        报(f"  自动选中成片：{片名}")
    片 = os.path.join(戏目录, "片", 片名)
    if not os.path.exists(片):
        报(f"✗ 找不到 {片}")
        return 1

    干, 尾 = os.path.splitext(片名)
    出 = os.path.join(戏目录, "片", f"{干}_有声{尾}")

    报("\n══ 混音 ══")
    输入 = [FFMPEG, "-y", "-i", 片]
    链, idx = [], 1
    for i, s in enumerate(段们):
        输入 += ["-i", s["路"]]
        毫 = int(s["起"] * 1000)
        # 后缀写 .wav 其实内容是 FLAC —— ffmpeg 按魔数认，不用管后缀
        链.append(f"[{idx}:a]adelay={毫}|{毫},volume=1.0[v{i}]")
        idx += 1
    滤 = ";".join(链)
    滤 += (f";{''.join(f'[v{i}]' for i in range(len(段们)))}"
           f"amix=inputs={len(段们)}:duration=longest:normalize=0[人声0];"
           # ★ 人声必须**提上来**，不能和原声并排站在 1.0。
           #   2026-10-14 实测：全片台词窗平均 -26.8 dB，留白窗（只有 H3 环境声）-29.7 dB
           #   —— 台词只比环境高 2.9 dB，等于被环境音埋掉。
           #   原因是 `[0:a]`（H3 原生环境声）和每句人声都按 volume=1.0 进 amix，
           #   谁录得响谁就赢；而 H3 的环境声本来就录得不轻。
           f"[人声0]volume={参.人声量}[人声]")

    总 = 探秒(片)

    # ★ H3 是原生有声模型：每一格自带雨声、脚步、衣料摩擦、环境底噪。
    #   2026-10-14 之前这里只 map 了人声和棕噪，把 `[0:a]` 整条丢了 ——
    #   等于把 H3 一半的本事扔掉，再拿合成噪声去顶替真实的环境音。
    #   现在：原声留着当环境床，人声用**侧链压缩**把原声压下去（说话时自动让路，
    #   不说话时环境音回来），棕噪只剩很轻的一层垫底。
    有原声 = (not 参.无原声) and 片有声音轨(片, 报道=报)
    if 有原声:
        # ⚠ 三条流都必须先**铺满整片**再进 amix。踩过的坑：人声是有限长的
        #   （最后一句台词说完就没了），而 `sidechaincompress` 是「谁短跟谁」，
        #   于是 `[原声压]` 被截到「最后一句台词结束」那一刻，
        #   `amix=duration=first` 又以它为基准 → 整条音轨在那里被砍断。
        #   实测：23.0 秒说完最后一句，23.5 秒处两套链都是 -91 dB（数字静音）。
        #   所以人声先 asplit 再用 apad=whole_dur 补到全片长，两条分支都要补。
        滤 += (f";[0:a]aresample=48000,volume={参.原声量}[原声];"
               "[人声]asplit=2[人声出0][人声键0];"
               f"[人声出0]apad=whole_dur={总:.3f}[人声出];"
               f"[人声键0]apad=whole_dur={总:.3f}[人声键];"
               "[原声][人声键]sidechaincompress="
               "threshold=0.04:ratio=12:attack=15:release=450:makeup=1[原声压]")
        if not 参.无底噪:
            滤 += (f";anoisesrc=color=brown:amplitude=0.35:duration={总 + 5:.1f}[噪];"
                   "[噪]highpass=f=180,lowpass=f=1400,volume=0.030[风]")
            滤 += (";[原声压][人声出][风]"
                   "amix=inputs=3:duration=first:normalize=0[混]")
        else:
            滤 += ";[原声压][人声出]amix=inputs=2:duration=first:normalize=0[混]"
        末 = "[混]"
    elif not 参.无底噪:
        # 环境底噪：棕噪过带通压得很低，长度跟着片子走
        滤 += (f";anoisesrc=color=brown:amplitude=0.35:duration={总 + 5:.1f}[噪];"
               "[噪]highpass=f=180,lowpass=f=1400,volume=0.055[风]")
        滤 += ";[风][人声]amix=inputs=2:duration=first:normalize=0[混]"
        末 = "[混]"
    else:
        末 = "[人声]"
    滤 += f";{末}alimiter=limit=0.95,apad[aout]"

    # ⚠ 不能加 -shortest：它把**画面**裁到音频长度（踩过，23.56 秒的片子被砍成 18.65）
    cmd = 输入 + ["-filter_complex", 滤, "-map", "0:v", "-map", "[aout]",
                  "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                  "-t", f"{总}", 出]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(出):
        报(f"  ✗ 混音失败：{(r.stderr or '')[-700:]}")
        return 1

    新秒 = 探秒(出)
    报(f"\n✓ 有声成片：{出}")
    报(f"  {新秒:.2f} 秒  {os.path.getsize(出)/1048576:.2f} MB")
    if abs(新秒 - 总) > 0.5:
        报(f"  ⚠ 混完时长差了 {abs(新秒-总):.2f} 秒（原 {总:.2f}）—— 查一下")

    if 参.烧字幕:
        报("\n══ 烧字幕 ══")
        烧 = os.path.join(根, "_烧字幕.py")
        rc = subprocess.run([sys.executable, "-X", "utf8", 烧, 出, "--srt", srt路,
                             "--字号", str(参.字号)],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
        print((rc.stdout or "").strip())
        if rc.returncode != 0:
            print((rc.stderr or "")[-500:])
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
