# -*- coding: utf-8 -*-
"""抓 B 站「大肥鱼 / DeepSeek 鲸鱼娘」最新 Q 版同人图的封面，当参考图用。"""
import os
import ssl
import urllib.request

from PIL import Image

ssl._create_default_https_context = ssl._create_unverified_context

出 = r"D:\DSHworkspace\B站\情报\AI娘参考图\新Q版"
os.makedirs(出, exist_ok=True)

头 = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"),
    "Referer": "https://www.bilibili.com/",
}

图 = {
    "100_大肥鱼表情包1700张合集.jpg": "https://i2.hdslb.com/bfs/archive/778bf48f1cb0b2cc457d4cc7cec98c267fe013b1.jpg",
    "101_蓝色大肥鱼动图200张.jpg": "https://i2.hdslb.com/bfs/archive/8f7598b60bfe2f9ddcd531c7005dd7812781547c.jpg",
    "102_新一批蓝色大肥鱼表情包.jpg": "https://i2.hdslb.com/bfs/archive/3b48507f398d5a4a10b932e98be9fbe36e03317d.jpg",
    "103_全动态Live2D大肥鱼桌宠.jpg": "https://i2.hdslb.com/bfs/archive/8cf5b394ec458e2ef3c546188eb4e6ca8314fb05.jpg",
    "104_免费Live2d模型大肥鱼.jpg": "https://i2.hdslb.com/bfs/archive/589bc554d6d240baeaf93057ee96553770762e4c.jpg",
    "105_梗知识蓝色大肥鱼.jpg": "https://i2.hdslb.com/bfs/archive/24503b568a8d77e4c1395fc404bf4b3456cfbb3f.jpg",
    "106_啥子大肥鲸吃完就睡.jpg": "https://i2.hdslb.com/bfs/archive/24b78dab30c95110eca47c07e1e271e5a5e2a678.jpg",
    "107_Harness大肥鱼桌宠插件.jpg": "https://i2.hdslb.com/bfs/archive/ef63434269dd3b7383d9d22bcd8ae2bb22881f2f.jpg",
    "108_不会叫凶一点的大肥鱼.jpg": "https://i2.hdslb.com/bfs/archive/fb92325b78af2579641aebf6f30256962abed747.jpg",
    "109_我觉得Deepseek好可爱.jpg": "https://i2.hdslb.com/bfs/archive/3014994ea21c8f1614cacf867967e7fec81d4f08.jpg",
    "110_鲸鱼娘火出圈蓝胖鱼.png": "https://i2.hdslb.com/bfs/legacy/176c22523f3f0a7c98a01eb44abc9e6131b74fce.png",
    "111_小鲸鱼Q版动态指针.jpg": "https://i2.hdslb.com/bfs/archive/",
}

for n, u in 图.items():
    if not u.endswith((".jpg", ".png")):
        continue
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
