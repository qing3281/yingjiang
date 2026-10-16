# -*- coding: utf-8 -*-
"""
图集运镜 —— 把 N 张静图合成一条带推拉摇移的成片（形态A）

不需要视频模型，今天就能跑。这是"AI绘画/AI生成"题材的主力形态。

用法：
  python 图集运镜.py --images "out/*.png" --out 成片.mp4
  python 图集运镜.py --images "out/*.png" --out 成片.mp4 --size 1080x1920 --per 4 --bgm bgm.mp3

运镜设计（每张图自动分配，循环使用）：
  0 缓慢推近      1 缓慢拉远      2 左→右平移      3 右→左平移
  4 推近+上摇     5 拉远+下摇     6 左上→右下      7 右下→左上
"""
import argparse
import glob
import os
import sys
from fractions import Fraction

import av
import numpy as np
from PIL import Image, ImageFilter

# ---------------------------------------------------------------- 运镜轨迹
# 每个轨迹返回 (t) -> (缩放系数, 中心x比例, 中心y比例)
#   t: 0.0 ~ 1.0 表示这张图的播放进度
#   缩放系数 1.0 = 刚好铺满画面；>1.0 表示画面被裁掉了多少
#   中心 x/y 为 0~1，0.5 表示居中
def _lerp(a, b, t):
    return a + (b - a) * t


轨迹 = {
    # 名称: (起始缩放, 结束缩放, 起心x, 起心y, 终心x, 终心y)
    "推近":     (1.00, 1.16, 0.50, 0.50, 0.50, 0.50),
    "拉远":     (1.16, 1.00, 0.50, 0.50, 0.50, 0.50),
    "左到右":   (1.14, 1.14, 0.38, 0.50, 0.62, 0.50),
    "右到左":   (1.14, 1.14, 0.62, 0.50, 0.38, 0.50),
    "推近上摇": (1.02, 1.16, 0.50, 0.60, 0.50, 0.40),
    "拉远下摇": (1.16, 1.02, 0.50, 0.40, 0.50, 0.60),
    "左上右下": (1.16, 1.16, 0.40, 0.40, 0.60, 0.60),
    "右下左上": (1.16, 1.16, 0.60, 0.60, 0.40, 0.40),
}
顺序 = ["推近", "左到右", "拉远", "推近上摇", "右到左", "拉远下摇", "左上右下", "右下左上"]


def 缓动(t):
    """平滑起步/收尾（smoothstep），避免匀速的机械感"""
    return t * t * (3.0 - 2.0 * t)


class 素材:
    def __init__(self, path, 目标宽, 目标高, 最高缩放, 适配="blur"):
        im = Image.open(path).convert("RGB")
        self.路径 = path
        比 = 目标宽 / 目标高
        图比 = im.width / im.height

        def 铺满(x):
            """等比放大到刚好盖住目标框，再多裁掉溢出的部分"""
            if x.width / x.height > 比:
                新W = int(round(x.height * 比))
                左 = (x.width - 新W) // 2
                return x.crop((左, 0, 左 + 新W, x.height))
            新H = int(round(x.width / 比))
            上 = (x.height - 新H) // 2
            return x.crop((0, 上, x.width, 上 + 新H))

        def 装下(x):
            """等比缩放直到整张图都在目标框内（可能留边）"""
            if x.width / x.height > 比:
                新H = int(round(x.width / 比))
                return x.resize((x.width, 新H), Image.LANCZOS)
            新W = int(round(x.height * 比))
            return x.resize((新W, x.height), Image.LANCZOS)

        if abs(图比 - 比) < 0.02:
            成品 = im if abs(图比 - 比) < 0.001 else 铺满(im)
        elif 适配 == "crop":
            成品 = 铺满(im)
        elif 适配 == "pad":
            成品 = 装下(im)
        else:  # blur：模糊底 + 完整前景，这是最稳妥的适配
            底 = 铺满(im).resize((目标宽, 目标高), Image.LANCZOS)
            底 = 底.filter(ImageFilter.GaussianBlur(目标高 / 22))
            底 = Image.fromarray(
                (np.asarray(底, dtype=np.float32) * 0.55).astype(np.uint8)
            )
            前 = 装下(im)
            if 前.width > 目标宽:
                前 = 前.resize((目标宽, int(round(前.height * 目标宽 / 前.width))), Image.LANCZOS)
            底.paste(前, ((目标宽 - 前.width) // 2, (目标高 - 前.height) // 2))
            成品 = 底

        # 统一缩放到"最大缩放"对应的分辨率：后续每帧只需小幅重采样，
        # 同时保证源图永远够大到能裁出任意缩放/任意中心的画面
        工作W = int(round(目标宽 * 最高缩放))
        工作H = int(round(目标高 * 最高缩放))
        if 成品.size != (工作W, 工作H):
            采样 = Image.LANCZOS if 成品.width > 工作W else Image.BICUBIC
            成品 = 成品.resize((工作W, 工作H), 采样)
        self.图 = 成品
        self.目标宽 = 目标宽
        self.目标高 = 目标高

    def 取帧(self, 缩放, cx, cy):
        """按 缩放/中心 取出一帧目标尺寸的画面"""
        w = self.目标宽 / 缩放
        h = self.目标高 / 缩放
        # 源图不够大时退回最大可用范围
        if w > self.图.width:
            w = float(self.图.width)
        if h > self.图.height:
            h = float(self.图.height)
        x0 = cx * self.图.width - w / 2
        y0 = cy * self.图.height - h / 2
        # 越界回夹（留出浮点余量，PIL 的 box 不许超界）
        x0 = max(0.0, min(self.图.width - w, x0))
        y0 = max(0.0, min(self.图.height - h, y0))
        return self.图.resize(
            (self.目标宽, self.目标高), Image.BICUBIC,
            box=(x0, y0, x0 + w, y0 + h),
        )


def 生成画面帧(素材s, 每张秒, 帧率, 转场秒, 轨迹序列):
    """生成器：逐帧吐出 (PIL.Image, 时间戳秒)"""
    n = len(素材s)
    每张帧数 = int(round(每张秒 * 帧率))
    转场帧数 = int(round(转场秒 * 帧率))
    重叠 = 转场帧数 if n > 1 else 0

    def 某张的帧(i, k):
        """第 i 张的第 k 帧（k 从 0 开始，共 每张帧数 帧）"""
        t = 缓动(k / max(1, 每张帧数 - 1))
        s0, s1, x0, y0, x1, y1 = 轨迹[轨迹序列[i % len(轨迹序列)]]
        缩 = _lerp(s0, s1, t)
        return 素材s[i].取帧(缩, _lerp(x0, x1, t), _lerp(y0, y1, t))

    # 第 i 张从 帧偏移[i] 开始
    偏移 = [i * (每张帧数 - 重叠) for i in range(n)]
    总帧数 = 偏移[-1] + 每张帧数

    for f in range(总帧数):
        # 找出覆盖当前帧的所有素材
        覆盖 = [i for i in range(n) if 偏移[i] <= f < 偏移[i] + 每张帧数]
        if not 覆盖:
            continue
        if len(覆盖) == 1:
            i = 覆盖[0]
            yield 某张的帧(i, f - 偏移[i]), f / 帧率
        else:
            # 跨两张 → 交叉溶解
            a, b = 覆盖[0], 覆盖[1]
            ka = f - 偏移[a]
            kb = f - 偏移[b]
            混 = (ka - (每张帧数 - 重叠) + 1) / 转场帧数   # 0→1
            混 = max(0.0, min(1.0, 混))
            混 = 缓动(混)
            fa = 某张的帧(a, ka)
            fb = 某张的帧(b, kb)
            yield Image.blend(fa, fb, 混), f / 帧率


def 加音频(container, 视频流, bgm路径, 总时长, 帧率):
    """把 BGM 混进去（短了循环、长了裁断，两端各 1.5 秒淡入淡出）"""
    if not bgm路径 or not os.path.exists(bgm路径):
        return None
    采样率 = 44100
    try:
        输入 = av.open(bgm路径)
        音频流 = 输入.streams.audio[0]
        重采样 = av.AudioResampler(format="s16", layout="stereo", rate=采样率)
        片段 = []
        for frame in 输入.decode(音频流):
            for rf in 重采样.resample(frame):
                片段.append(rf.to_ndarray())
        for rf in 重采样.resample(None):
            片段.append(rf.to_ndarray())
        输入.close()
        if not 片段:
            return None
        音频 = np.concatenate([a.reshape(2, -1) for a in 片段], axis=1)  # (2, N)
    except Exception as e:
        print(f"  ⚠ BGM 读取失败，跳过：{e}")
        return None

    需要 = int(round(总时长 * 采样率))
    if 音频.shape[1] < 需要:
        重复 = int(np.ceil(需要 / 音频.shape[1]))
        音频 = np.tile(音频, (1, 重复))
    音频 = 音频[:, :需要].astype(np.float32)

    # 淡入淡出
    淡 = int(round(1.5 * 采样率))
    if 淡 * 2 < 需要:
        包络 = np.ones(需要, dtype=np.float32)
        包络[:淡] = np.linspace(0, 1, 淡)
        包络[-淡:] = np.linspace(1, 0, 淡)
        音频 *= 包络

    # 整体压低到 -14 dB 左右，留出人声/音效空间
    音频 *= 0.20
    数据 = np.clip(音频, -32768, 32767).astype(np.int16)

    输出流 = container.add_stream("aac", rate=采样率)
    输出流.layout = "stereo"
    输出流.bit_rate = 192_000

    每帧 = 1024
    偏移 = 0
    while 偏移 < 数据.shape[1]:
        块 = 数据[:, 偏移:偏移 + 每帧]
        偏移 += 每帧
        if 块.shape[1] == 0:
            break
        if 块.shape[1] < 每帧:  # 补齐最后一帧
            块 = np.pad(块, ((0, 0), (0, 每帧 - 块.shape[1])))
        f = av.AudioFrame.from_ndarray(np.ascontiguousarray(块), format="s16", layout="stereo")
        f.sample_rate = 采样率
        f.pts = None
        for pkt in 输出流.encode(f):
            container.mux(pkt)
    for pkt in 输出流.encode():
        container.mux(pkt)
    return 输出流


def main():
    ap = argparse.ArgumentParser(description="图集运镜：静图 → 成片")
    ap.add_argument("--images", required=True, help="图片路径，支持通配符或用 ; 分隔多个")
    ap.add_argument("--out", required=True, help="输出 mp4 路径")
    ap.add_argument("--size", default="1920x1080", help="输出分辨率，如 1920x1080 或 1080x1920")
    ap.add_argument("--per", type=float, default=4.0, help="每张图秒数（默认 4）")
    ap.add_argument("--xfade", type=float, default=0.7, help="转场秒数（默认 0.7）")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--bgm", default=None, help="背景音乐文件")
    ap.add_argument("--crf", type=int, default=18, help="画质，越小越好（默认 18）")
    ap.add_argument("--fade-out", type=float, default=0.0, help="片尾黑场秒数（0=不加）")
    ap.add_argument("--fit", default="blur", choices=["blur", "crop", "pad"],
                    help="图片比例与画布不符时：blur=模糊底+完整图（默认，不切内容）"
                         " / crop=裁掉溢出（会切头） / pad=黑边")
    args = ap.parse_args()

    目标宽, 目标高 = (int(x) for x in args.size.lower().split("x"))

    # 收集图片
    路径表 = []
    for 段 in args.images.split(";"):
        段 = 段.strip()
        if not 段:
            continue
        命中 = sorted(glob.glob(段))
        if 命中:
            路径表.extend(命中)
        elif os.path.isfile(段):
            路径表.append(段)
    路径表 = [p for p in 路径表 if p.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
    if not 路径表:
        print("❌ 没找到任何图片")
        sys.exit(1)

    最高缩放 = max(max(v[0], v[1]) for v in 轨迹.values())
    print(f"图集运镜   {len(路径表)} 张图 → {目标宽}x{目标高} @{args.fps}fps")
    print(f"每张 {args.per}s，转场 {args.xfade}s")
    素材s = [素材(p, 目标宽, 目标高, 最高缩放, args.fit) for p in 路径表]
    for p in 路径表:
        print(f"   · {os.path.basename(p)}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    if os.path.exists(args.out):
        os.remove(args.out)

    n = len(素材s)
    每张帧数 = int(round(args.per * args.fps))
    重叠 = int(round(args.xfade * args.fps)) if n > 1 else 0
    总帧数 = (n - 1) * (每张帧数 - 重叠) + 每张帧数
    总时长 = 总帧数 / args.fps
    print(f"总长 {总时长:.1f}s（{总帧数} 帧）\n")

    container = av.open(args.out, mode="w")
    视频流 = container.add_stream("libx264", rate=args.fps)
    视频流.width = 目标宽
    视频流.height = 目标高
    视频流.pix_fmt = "yuv420p"
    视频流.options = {"preset": "medium", "crf": str(args.crf), "profile": "high", "level": "4.2"}
    视频流.bit_rate = 0

    # 音频要先加，保证流顺序是 视频/音频
    音轨 = None

    帧号 = 0
    for img, ts in 生成画面帧(素材s, args.per, args.fps, args.xfade, 顺序):
        if args.fade_out > 0:
            剩余 = 总时长 - ts
            if 剩余 < args.fade_out:
                系数 = max(0.0, 剩余 / args.fade_out)
                img = Image.fromarray((np.asarray(img, dtype=np.float32) * 系数).astype(np.uint8))
        f = av.VideoFrame.from_image(img)
        f.pts = 帧号
        f.time_base = Fraction(1, args.fps)
        for pkt in 视频流.encode(f):
            container.mux(pkt)
        帧号 += 1
        if 帧号 % (args.fps * 5) == 0:
            print(f"  ... {帧号}/{总帧数} 帧  ({帧号/总帧数*100:.0f}%)")
    for pkt in 视频流.encode():
        container.mux(pkt)
    print(f"  视频轨完成 {帧号} 帧")

    if args.bgm:
        print(f"  混入 BGM: {os.path.basename(args.bgm)}")
        音轨 = 加音频(container, 视频流, args.bgm, 总时长, args.fps)
    container.close()

    大小 = os.path.getsize(args.out) / 1024 / 1024
    print(f"\n✅ {args.out}")
    print(f"   {目标宽}x{目标高}  {总时长:.1f}s  {大小:.1f} MB")
    检 = av.open(args.out)
    检视 = 检.streams.video[0]
    时长 = float(检视.duration * 检视.time_base) if 检视.duration else 总时长
    有音 = "有" if len(检.streams.audio) > 0 else "无"
    检.close()
    print(f"   校验: {检视.codec_context.name} {检视.width}x{检视.height} {时长:.1f}s  音频:{有音}")


if __name__ == "__main__":
    main()
