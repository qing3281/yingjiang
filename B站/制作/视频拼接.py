# -*- coding: utf-8 -*-
"""
视频拼接 —— 把「Wan 出的视频段」和「静帧运镜」混编成一条成片

为什么需要它：图集运镜.py 只认图片。Wan 出的是 mp4，
而一条片子里通常只有几个关键镜头值得花 4 分钟跑 I2V，
其余镜头用静帧运镜（2.8 秒/张）性价比更高。这个脚本让两者能接在一起。

清单格式：
{
  "画布": "1920x1080",
  "转场秒": 0.5,
  "片段": [
    {"类型": "视频", "文件": "D:/.../a.mp4"},
    {"类型": "图",   "文件": "D:/.../b.png", "秒": 4.0, "运镜": "推近"},
    {"类型": "视频", "文件": "D:/.../c.mp4", "裁到秒": 5.0}
  ]
}

用法：
  python 视频拼接.py --清单 清单.json --out 成片.mp4
  python 视频拼接.py --清单 清单.json --out 成片.mp4 --转场 0.8 --bgm 音乐.mp3

实现要点：
  · 全部走 PyAV，不需要 ffmpeg 可执行文件（本机 ffmpeg 不在 PATH）
  · 流式解码 + 环形缓冲做交叉溶解，不把整片读进内存
    （12 段 1080p 全读进内存约 9 GB，会爆）
  · 图片复用图集运镜.py 的「模糊底 + 完整前景居中」适配，
    避免方图被裁掉头顶
"""
import argparse
import json
import math
import os
import sys

import av
import numpy as np
from PIL import Image, ImageFilter

# ------------------------------------------------------------------ 图像工具
def 适配(im, W, H, 模式="blur"):
    """把任意比例的图塞进 W×H 画布"""
    比图 = im.width / im.height
    比布 = W / H
    if abs(比图 - 比布) < 0.02:
        return im.resize((W, H), Image.LANCZOS)

    if 模式 == "pad":
        底 = Image.new("RGB", (W, H), (0, 0, 0))
        缩 = min(W / im.width, H / im.height)
        新 = im.resize((max(1, int(im.width * 缩)), max(1, int(im.height * 缩))), Image.LANCZOS)
        底.paste(新, ((W - 新.width) // 2, (H - 新.height) // 2))
        return 底

    if 模式 == "crop":
        缩 = max(W / im.width, H / im.height)
        新 = im.resize((max(1, int(im.width * 缩)), max(1, int(im.height * 缩))), Image.LANCZOS)
        return 新.crop(((新.width - W) // 2, (新.height - H) // 2,
                        (新.width - W) // 2 + W, (新.height - H) // 2 + H))

    # blur 底
    if im.width / im.height > W / H:
        缩 = W / im.width
    else:
        缩 = H / im.height
    小 = im.resize((max(8, int(im.width * 缩 / 6))), Image.LANCZOS) if False else \
        im.resize((max(8, int(im.width * 缩 / 6)), max(8, int(im.height * 缩 / 6))), Image.LANCZOS)
    底 = 小.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    底 = Image.fromarray((np.asarray(底, dtype=np.float32) * 0.55).astype(np.uint8))
    缩2 = min(W / im.width, H / im.height)
    新 = im.resize((max(1, int(im.width * 缩2)), max(1, int(im.height * 缩2))), Image.LANCZOS)
    底.paste(新, ((W - 新.width) // 2, (H - 新.height) // 2))
    return 底


def 缓动(t):
    """smoothstep：两端慢中间快，比线性像真实运镜"""
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------ 字幕
字体候选 = [
    r"C:\Windows\Fonts\msyhbd.ttc",     # 微软雅黑 粗体
    r"C:\Windows\Fonts\msyh.ttc",       # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",     # 黑体
    r"C:\Windows\Fonts\arialbd.ttf",
]


def 找字体():
    for p in 字体候选:
        if os.path.exists(p):
            return p
    return None


def 做字幕(文, W, H):
    """把一行字渲成一张和画布同宽的 RGBA 图（黑描边 + 底部居中）。

    短剧没字幕等于没法看——MiniMax 出的是英文对白，观众要的是中文。
    """
    from PIL import ImageDraw, ImageFont
    路 = 找字体()
    if not 路 or not 文:
        return None
    字号 = max(18, int(H * 0.052))
    try:
        字 = ImageFont.truetype(路, 字号)
    except Exception:
        return None
    量 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    # 长句折行
    每行上限 = int(W * 0.86)
    行 = []
    当前 = ""
    for ch in 文:
        试 = 当前 + ch
        if 量.textlength(试, font=字) > 每行上限 and 当前:
            行.append(当前); 当前 = ch
        else:
            当前 = 试
    if 当前:
        行.append(当前)

    行高 = int(字号 * 1.32)
    层 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    绘 = ImageDraw.Draw(层)
    底 = H - int(H * 0.075) - 行高 * len(行)
    for k, 一 in enumerate(行):
        宽 = 量.textlength(一, font=字)
        x = (W - 宽) / 2
        y = 底 + k * 行高
        绘.text((x, y), 一, font=字, fill=(255, 255, 255, 255),
                stroke_width=max(2, 字号 // 12), stroke_fill=(0, 0, 0, 235))
    return 层



运镜表 = {
    "推近":   lambda t: (1.00, 1.18, 0.5, 0.5),
    "拉远":   lambda t: (1.18, 1.00, 0.5, 0.5),
    "左到右": lambda t: (1.10, 1.10, 0.5 - 0.09 * t, 0.5),
    "右到左": lambda t: (1.10, 1.10, 0.5 + 0.09 * t, 0.5),
    "上到下": lambda t: (1.10, 1.10, 0.5, 0.5 - 0.09 * t),
    "下到上": lambda t: (1.10, 1.10, 0.5, 0.5 + 0.09 * t),
    "静止":   lambda t: (1.00, 1.00, 0.5, 0.5),
}


def 图取帧(im, i, 总帧, 运镜):
    """从一张图裁出第 i 帧（Ken Burns）"""
    p = 缓动(i / max(1, 总帧 - 1))
    z0, z1, cx0, cy0 = 运镜表.get(运镜, 运镜表["推近"])(p)
    z = z0 + (z1 - z0) * p
    W, H = im.size
    # 基准底图已按画布比例放过；这里只在画布内二次裁切
    return z, cx0, cy0


# ------------------------------------------------------------------ 编码器
class 编码:
    def __init__(self, out, W, H, fps, 采样率=48000, 有声=False,
                 bgm=None, bgm音量=0.20):
        self.W, self.H, self.fps = W, H, fps
        self.采样率 = 采样率
        self.bgm路 = bgm
        self.bgm音量 = bgm音量
        self.音块 = []          # 有 BGM 时要先攒齐再混，不能边算边写
        self.总样本 = 0         # 片长对应的样本数，收尾时补齐用
        self.容器 = av.open(out, mode="w")
        self.流 = self.容器.add_stream("libx264", rate=fps)
        self.流.width, self.流.height = W, H
        self.流.pix_fmt = "yuv420p"
        self.流.options = {"crf": "18", "preset": "medium", "gop": str(fps * 2)}
        self.n = 0
        self.音流 = None
        self.音n = 0
        if 有声:
            self.音流 = self.容器.add_stream("aac", rate=采样率)
            try:
                self.音流.layout = "stereo"
            except Exception:
                pass
            try:
                self.音流.bit_rate = 192000
            except Exception:
                pass

    def 写(self, arr, 字幕=None):
        """arr: uint8 ndarray (H,W,3) 或 float 混合结果；字幕: RGBA 图层或 None"""
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        if 字幕 is not None:
            a = np.asarray(arr, dtype=np.float32)
            s = np.asarray(字幕, dtype=np.float32)
            al = (s[..., 3:4] / 255.0)
            rgb = s[..., :3]
            arr = np.clip(rgb * al + a * (1.0 - al), 0, 255).astype(np.uint8)
        f = av.VideoFrame.from_ndarray(np.ascontiguousarray(arr), format="rgb24")
        f.pts = self.n
        self.n += 1
        for pkt in self.流.encode(f):
            self.容器.mux(pkt)

    def 写音(self, arr):
        """arr: float32 ndarray，形状 (样本, 2) 或 (样本,)"""
        if self.音流 is None or arr is None or len(arr) == 0:
            return
        a = np.asarray(arr, dtype=np.float32)
        if a.ndim == 1:
            a = np.stack([a, a], axis=1)
        if self.bgm路:
            self.音块.append(a)
            return
        self._真写音(a)

    def _真写音(self, a):
        f = av.AudioFrame.from_ndarray(
            np.ascontiguousarray(a.T), format="fltp", layout="stereo")
        f.sample_rate = self.采样率
        f.pts = self.音n
        self.音n += a.shape[0]
        for pkt in self.音流.encode(f):
            self.容器.mux(pkt)

    def 混BGM(self):
        """把主音轨垫在循环播放的 BGM 上，两端各 1.2 秒淡入淡出"""
        if not self.bgm路 or not os.path.exists(self.bgm路):
            return None
        主 = (np.concatenate(self.音块, axis=0) if self.音块
              else np.zeros((0, 2), dtype=np.float32))
        乐 = 取音(self.bgm路, self.采样率)
        if 乐 is None or not len(乐):
            return None
        n = max(len(主), self.总样本, int(self.音n))
        if n <= 0:
            return None
        if len(主) < n:
            主 = 调长(主, n)
        遍 = int(np.ceil(n / len(乐)))
        乐 = np.tile(乐, (遍, 1))[:n]
        淡 = int(1.2 * self.采样率)
        if n > 2 * 淡 > 0:
            包 = np.ones(n, dtype=np.float32)
            包[:淡] = np.linspace(0, 1, 淡)
            包[-淡:] = np.linspace(1, 0, 淡)
            乐 = 乐 * 包[:, None]
        混 = 主 + 乐 * self.bgm音量
        # 限幅，别削顶
        峰 = float(np.abs(混).max())
        if 峰 > 0.99:
            混 = 混 * (0.99 / 峰)
        return 混

    def 收(self):
        for pkt in self.流.encode():
            self.容器.mux(pkt)
        if self.音流 is not None:
            if self.bgm路:
                混 = self.混BGM()
                if 混 is not None and len(混):
                    每 = 4096
                    for s in range(0, len(混), 每):
                        self._真写音(混[s:s + 每])
                else:
                    for a in self.音块:
                        self._真写音(a)
            for pkt in self.音流.encode():
                self.容器.mux(pkt)
        self.容器.close()


# ------------------------------------------------------------------ 取片段帧
def 图段帧(路径, 秒, fps, W, H, 运镜, 适配模式):
    im = Image.open(路径).convert("RGB")
    im = 适配(im, W, H, 适配模式)
    总 = max(1, int(round(秒 * fps)))
    p = 缓动
    for i in range(总):
        t = p(i / max(1, 总 - 1))
        z0, z1, cx0, cy0 = 运镜表.get(运镜, 运镜表["推近"])(t)
        z = z0 + (z1 - z0) * t
        cw, ch = int(W / z), int(H / z)
        cx = int(cx0 * W - cw / 2)
        cy = int(cy0 * H - ch / 2)
        cx = max(0, min(W - cw, cx)); cy = max(0, min(H - ch, cy))
        yield np.asarray(im.crop((cx, cy, cx + cw, cy + ch)).resize((W, H), Image.BILINEAR))


def 视频段帧(路径, fps, W, H, 适配模式, 裁到秒=None):
    c = av.open(路径)
    s = c.streams.video[0]
    源fps = float(s.average_rate) if s.average_rate else fps
    上限 = int(裁到秒 * fps) if 裁到秒 else None
    出 = 0
    # 抽帧对齐到目标 fps：源 16fps → 目标 16 或 24，用时间戳判断该不该出帧
    下一个 = 0.0
    for f in c.decode(s):
        t = float(f.pts * f.time_base) if f.pts is not None else 出 / 源fps
        while 下一个 <= t + 1e-6:
            if 上限 is not None and 出 >= 上限:
                c.close(); return
            im = f.to_image()
            if (im.width, im.height) != (W, H):
                im = 适配(im, W, H, 适配模式)
            yield np.asarray(im)
            出 += 1
            下一个 += 1.0 / fps
    c.close()


def 取音(路径, 采样率=48000):
    """解码一个媒体的音轨 → float32 ndarray (样本, 2)；没有音轨返回 None。

    MiniMax-H3 出的 mp4 自带人声/音效，之前这里直接丢掉，等于白生成。
    """
    try:
        c = av.open(路径)
    except Exception:
        return None
    if not c.streams.audio:
        c.close()
        return None
    s = c.streams.audio[0]
    重采 = av.AudioResampler(format="fltp", layout="stereo", rate=采样率)
    块 = []
    try:
        for fr in c.decode(s):
            for pf in 重采.resample(fr):
                块.append(np.asarray(pf.to_ndarray(), dtype=np.float32).T)
        for pf in 重采.resample(None):
            块.append(np.asarray(pf.to_ndarray(), dtype=np.float32).T)
    except Exception:
        pass
    c.close()
    if not 块:
        return None
    return np.concatenate(块, axis=0)


def 调长(arr, 样本数, 声道=2):
    """把音轨裁/补到恰好 样本数 长（补的部分是静音）"""
    if arr is None:
        return np.zeros((样本数, 声道), dtype=np.float32)
    if len(arr) >= 样本数:
        return arr[:样本数]
    return np.concatenate(
        [arr, np.zeros((样本数 - len(arr), arr.shape[1]), dtype=np.float32)], axis=0)


def 源有音(片段):
    """清单里任一段带音轨，才开音轨输出"""
    for 段 in 片段:
        路 = 段.get("文件")
        if 段.get("类型", "图") == "视频" and 路 and os.path.exists(路):
            try:
                c = av.open(路)
                有 = bool(c.streams.audio)
                c.close()
                if 有:
                    return True
            except Exception:
                pass
    return False


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--清单", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=None, help="默认取清单里的 fps，否则 24")
    ap.add_argument("--转场", type=float, default=None)
    ap.add_argument("--bgm", default=None)
    ap.add_argument("--bgm音量", type=float, default=0.20,
                    help="BGM 相对人声的音量，默认 0.20")
    ap.add_argument("--无声", action="store_true",
                    help="即使片段带音轨也强制输出无声（默认带音轨就保留）")
    ap.add_argument("--适配", choices=["blur", "crop", "pad"], default="blur")
    args = ap.parse_args()

    with open(args.清单, encoding="utf-8") as f:
        清单 = json.load(f)
    W, H = (int(x) for x in 清单.get("画布", "1920x1080").lower().split("x"))
    fps = args.fps or int(清单.get("fps", 24))
    转场秒 = args.转场 if args.转场 is not None else float(清单.get("转场秒", 0.5))
    转场帧 = max(0, int(round(转场秒 * fps)))
    片段 = 清单["片段"]
    if not 片段:
        sys.exit("❌ 清单里没有片段")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    采样率 = 48000
    bgm路 = args.bgm if (args.bgm and os.path.exists(args.bgm)) else None
    if args.bgm and not bgm路:
        print(f"   ⚠ BGM 不存在，忽略：{args.bgm}")
    开音 = ((not args.无声) and 源有音(片段)) or bool(bgm路)
    print(f"画布 {W}x{H} @{fps}fps   转场 {转场秒}s   共 {len(片段)} 段"
          + ("   🔊 含音轨" if 开音 else "   🔇 无音轨")
          + (f"   ♫ BGM 音量 {args.bgm音量:.2f}" if bgm路 else ""))

    编 = 编码(args.out, W, H, fps, 采样率, 开音, bgm路, args.bgm音量)
    挂起 = None            # 上一段末尾的 转场帧 张（float32）
    挂起音 = None
    挂起字幕 = None
    总帧 = 0
    每帧样 = lambda n: n * 采样率 // fps

    import itertools

    for i, 段 in enumerate(片段, 1):
        类 = 段.get("类型", "图")
        路 = 段["文件"]
        if not os.path.exists(路):
            print(f"  [{i}] ⚠ 缺文件，跳过：{路}")
            continue
        if 类 == "视频":
            源 = 视频段帧(路, fps, W, H, args.适配, 段.get("裁到秒"))
            标 = f"视频 {os.path.basename(路)}"
        else:
            源 = 图段帧(路, float(段.get("秒", 4.0)), fps, W, H,
                        段.get("运镜", "推近"), args.适配)
            标 = f"图 {os.path.basename(路)} {段.get('运镜', '推近')}"

        当前字幕 = 做字幕(段["字幕"], W, H) if 段.get("字幕") else None
        if 当前字幕 is not None:
            标 += "  💬"

        本音 = None
        if 开音:
            本音 = 取音(路, 采样率) if 类 == "视频" else None
            标 += ("  🔊" if 本音 is not None else "  ·（静音补）")
        音位 = [0]

        def 帧音(n):
            """按帧数取等长的一段音；源不够就补静音。

            每帧对应的样本数是整除的（48000/24=2000、48000/16=3000），
            所以画面帧和声音样本能严格对齐，不会随时间漂移。
            """
            s = 每帧样(n)
            if 本音 is None:
                return np.zeros((s, 2), dtype=np.float32)
            c = 本音[音位[0]:音位[0] + s]
            音位[0] += s
            return 调长(c, s)

        # 最后一段不再留尾巴（留了也没人接）
        留数 = 0 if i >= len(片段) else 转场帧

        # ---- 溶入：本段开头 k 帧 与 上一段尾巴 交叉 ----
        k = min(转场帧, len(挂起)) if (挂起 and 转场帧 > 0) else 0
        开头 = list(itertools.islice(源, k)) if k else []
        k = min(k, len(开头))
        if k > 0:
            for j in range(k):
                a = j / max(1, k - 1)
                编.写(挂起[j].astype(np.float32) * (1 - a)
                      + 开头[j].astype(np.float32) * a, 当前字幕)
                总帧 += 1
            if 开音:
                k样 = 每帧样(k)
                if k样 > 0:
                    aa = np.linspace(0.0, 1.0, k样, dtype=np.float32)[:, None]
                    新音 = 帧音(k)
                    编.写音(挂起音[:k样] * (1 - aa) + 新音[:k样] * aa)
            挂起 = None; 挂起音 = None; 挂起字幕 = None

        # ---- 主体：流式写出去，只在内存里留最后 留数 帧 ----
        # （之前是把整段解成 float32 列表：1080p 的 15 秒段要 8.3 GB，必崩）
        尾帧, 尾音, n段 = [], [], 0
        for 帧 in itertools.chain(开头[k:], 源):
            n段 += 1
            尾帧.append(帧)
            if 开音:
                尾音.append(帧音(1))
            if len(尾帧) > 留数:
                编.写(尾帧.pop(0).astype(np.float32), 当前字幕); 总帧 += 1
                if 开音:
                    编.写音(尾音.pop(0))

        if n段 == 0:
            print(f"  [{i}] ⚠ 这段没解出帧，跳过")
            continue

        if 留数 > 0 and 尾帧:
            挂起 = 尾帧
            挂起字幕 = 当前字幕
            挂起音 = (np.concatenate(尾音, axis=0) if 尾音
                      else np.zeros((每帧样(len(尾帧)), 2), dtype=np.float32))
        else:
            挂起 = None; 挂起音 = None; 挂起字幕 = None

        print(f"  [{i}/{len(片段)}] {标}  → 累计 {总帧} 帧")

    if 挂起:
        for a in 挂起:
            编.写(a.astype(np.float32), 挂起字幕); 总帧 += 1
    if 开音 and 挂起音 is not None and len(挂起音):
        编.写音(挂起音)
    编.总样本 = 每帧样(总帧)
    编.收()

    时长 = 总帧 / fps
    print(f"\n✅ {args.out}")
    print(f"   {总帧} 帧  {时长:.2f} 秒  {os.path.getsize(args.out)/1024/1024:.1f} MB")
    if bgm路:
        print(f"   ♫ BGM 已混入：{os.path.basename(bgm路)}")


if __name__ == "__main__":
    main()
