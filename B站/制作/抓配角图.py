# -*- coding: utf-8 -*-
"""抓豆包娘 / Claude娘 / Kimi娘 / 各AI娘盘点 的 B 站封面，当参考图用。"""
import os
import ssl
import urllib.request

from PIL import Image

ssl._create_default_https_context = ssl._create_unverified_context

出 = r"D:\DSHworkspace\B站\情报\AI娘参考图\配角"
os.makedirs(出, exist_ok=True)

头 = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"),
    "Referer": "https://www.bilibili.com/",
}

# 各AI娘形象盘点 478997 播放，是最全的一张
图 = {
    "200_各AI娘形象盘点_BV14phK66Ejw.jpg": "https://i1.hdslb.com/bfs/archive/f7e799042ae662463faf9fe9101e13b0f7217da0.jpg",
    "201_自制Claude娘梗图_BV1Ntpe6aEzr.jpg": "https://i1.hdslb.com/bfs/archive/7cfcb81f895cbc9cd5770eb6336b4b1c26d9bca8.jpg",
    "202_Claude娘人是猫_BV1jn4y1Z7hu.jpg": "https://i2.hdslb.com/bfs/archive/8083c710ba7af7f11873e64e107d6791510ec595.jpg",
    "203_ClaudePV_Astra_BV1MFpG63E26.jpg": "https://i2.hdslb.com/bfs/archive/5b7f78d1dd363dd09464ce8afdb1eab6c4d2ea4c.jpg",
    "204_三大AI娘互殴_BV1R2pp6UEpk.jpg": "https://i2.hdslb.com/bfs/archive/07e909a5021a43fa34eb9c42ca589778223cf3a3.jpg",
    "210_豆包换装3_BV1U8jc6bEAV.jpg": "https://i1.hdslb.com/bfs/archive/ee65cc733cee3fb8d847275dcc250ef5724c42e6.jpg",
    "211_豆包被调成啥样了_BV1SJXNBbERC.jpg": "https://i0.hdslb.com/bfs/archive/bcd1a28a061af91653aff29e64acdceb936cb730.jpg",
    "212_豆包还是太逊了_BV1zwPFzdEh2.jpg": "https://i2.hdslb.com/bfs/archive/32cb103cf1968d2d3071a65b76c9127aad645f5a.jpg",
    "213_豆包恶搞图_BV1yBp76SESs.jpg": "https://i0.hdslb.com/bfs/archive/8ecd8ddce6674b94aaa1ae1900b8b597323ba27d.jpg",
    "220_Kimi娘_BV1mXHy6cEb7.jpg": "https://i1.hdslb.com/bfs/archive/298533b674cb45c83bacabab08dd70a645f0b58f.jpg",
    "221_Kimi娘鼠标指针17形态_BV1nWeu67ERy.jpg": "https://i1.hdslb.com/bfs/archive/02d4df806e7a98bb3dd067d14e2106ee3a51469b.jpg",
    "222_Kimi自己画娘化形象_BV1DBaB6kET5.jpg": "https://i1.hdslb.com/bfs/archive/bc2e149bcac7fe97cc37ccb6e202c048a67100dc.jpg",
}

for n, u in 图.items():
    try:
        req = urllib.request.Request(u, headers=头)
        d = urllib.request.urlopen(req, timeout=60).read()
        p = os.path.join(出, n)
        with open(p, "wb") as f:
            f.write(d)
        im = Image.open(p)
        print(f"✓ {n}  {im.size}  {len(d)/1024:.0f} KB")
    except Exception as e:
        print(f"✗ {n}  {e}")
