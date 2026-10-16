import urllib.request, urllib.parse, os, sys, cv2, numpy as np
sys.stdout.reconfigure(encoding="utf-8")
远端 = "http://100.127.224.106:8188"
fn = "H3___1016_1147_r0005_cosine_bridge.mp4"
sub = "minimax_h3_t8_long_video/chuzihang_20261016_114710/assembled"
q = urllib.parse.urlencode({"filename": fn, "subfolder": sub, "type": "output"})
出目 = r"D:\DSHworkspace\_连片试"
os.makedirs(出目, exist_ok=True)
出 = os.path.join(出目, "试_20秒.mp4")
urllib.request.urlretrieve(远端 + "/view?" + q, 出)
print("下载", 出, os.path.getsize(出), "字节")
c = cv2.VideoCapture(出)
n = int(c.get(cv2.CAP_PROP_FRAME_COUNT)); fps = c.get(cv2.CAP_PROP_FPS)
w = int(c.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
print("帧数 %d  帧率 %.3f  尺寸 %dx%d  时长 %.2f 秒" % (n, fps, w, h, n/fps if fps else 0))
# 抽 12 张均匀铺开
位 = [int(i*(n-1)/11) for i in range(12)]
图 = []
for i in 位:
    c.set(cv2.CAP_PROP_POS_FRAMES, i); ok, fr = c.read()
    if not ok: continue
    fr = cv2.resize(fr, (int(fr.shape[1]*300/fr.shape[0]), 300))
    cv2.putText(fr, "f%d"%i, (6,22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2, cv2.LINE_AA)
    图.append(fr)
c.release()
# 每行 6 张
行 = [图[:6], 图[6:12]]
高 = sum(max(x.shape[0] for x in r) for r in 行)
宽 = max(sum(x.shape[1] for x in r) for r in 行)
布 = np.zeros((高, 宽, 3), np.uint8); y = 0
for r in 行:
    x = 0
    for im in r: 布[y:y+im.shape[0], x:x+im.shape[1]] = im; x += im.shape[1]
    y += max(i.shape[0] for i in r)
p = os.path.join(出目, "试_20秒_抽帧.jpg")
cv2.imencode(".jpg", 布, [int(cv2.IMWRITE_JPEG_QUALITY), 88])[1].tofile(p)
print("抽帧图", p, 布.shape)
