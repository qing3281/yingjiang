# -*- coding: utf-8 -*-
"""抓 GLM娘（智谱小狐娘）/ 千问娘 / 九位AI娘化 的 B 站封面当参考图。"""
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

图 = {
    "230_GLM智谱小狐娘_手指舞.jpg": "https://i2.hdslb.com/bfs/archive/9c4cf2cba8405d287603cb81b5658c08bdebe3cf.jpg",
    "231_GLM小狐娘_zcode.jpg": "https://i0.hdslb.com/bfs/archive/71d6c6e3e4551a78705bc77f03a8de82dde0aa6b.jpg",
    "232_大肥鱼和小狐娘.jpg": "https://i1.hdslb.com/bfs/archive/8747a64db234838f3b09a487b2a8a316c2f082bf.jpg",
    "233_琵琶曲_智谱娘VS大肥鱼.jpg": "https://i1.hdslb.com/bfs/archive/76ec925efc4a441f8f3faa87af7de6ad8407ecb7.jpg",
    "240_千问拟人同人手书.jpg": "https://i1.hdslb.com/bfs/archive/8259896ba92b8a4ddda672dee4e1dadfa78e3859.jpg",
    "241_美丽的千问娘.jpg": "https://i0.hdslb.com/bfs/archive/97d19e0a670a678d7289ed1e4ad362ef9528372c.jpg",
    "250_九位AI娘化_借了九张脸.jpg": "https://i2.hdslb.com/bfs/archive/58cf71e902b5d622f02a203568324d2d1f4b0389.jpg",
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
