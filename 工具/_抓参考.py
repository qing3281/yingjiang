import os, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
目 = r"D:\DSHworkspace\影匠\作品\楚子航\_网络参考"
os.makedirs(目, exist_ok=True)
件 = {
  "楚子航_百科01.jpg": "https://bkimg.cdn.bcebos.com/smart/b21bb051f8198618367afc2287bb39738bd4b31c4844-bkimg-process,v_1,rw_971,rh_504,maxl_971?x-bce-process=image/format,f_auto",
  "楚子航_百科02.jpg": "https://bkimg.cdn.bcebos.com/smart/a50f4bfbfbedab64034fdcf3c060b8c379310a55b0f0-bkimg-process,v_1,rw_940,rh_504,maxl_940?x-bce-process=image/format,f_auto",
  "夏弥_百科01.jpg":   "https://bkimg.cdn.bcebos.com/smart/023b5bb5c9ea15ce36d3259bf95c2df33a87e9501456-bkimg-process,v_1,rw_640,rh_360,maxl_640,pad_1?x-bce-process=image/format,f_auto",
  "夏弥_百科02.jpg":   "https://bkimg.cdn.bcebos.com/smart/0eb30f2442a7d933b9a9bf3ea74bd11373f0017d-bkimg-process,v_1,rw_1,rh_1,maxl_216,pad_1,color_ffffff",
}
请求头 = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Referer": "https://baike.baidu.com/"}
for 名, 址 in 件.items():
    路 = os.path.join(目, 名)
    try:
        r = urllib.request.Request(址, headers=请求头)
        with urllib.request.urlopen(r, timeout=30) as f:
            b = f.read()
        open(路, "wb").write(b)
        print("  ✓ %s  %d B" % (名, len(b)))
    except Exception as e:
        print("  ✗ %s  %s: %s" % (名, type(e).__name__, e))
print("  →", 目)
