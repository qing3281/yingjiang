import cv2, os, numpy as np
目 = r"D:\DSHworkspace\影匠\作品\楚子航"
def 读图(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
def 取帧(p, 第几):
    c = cv2.VideoCapture(p); i=0; keep=None; ok,fr=c.read()
    while ok:
        if i==第几: keep=fr.copy(); break
        i+=1; ok,fr=c.read()
    c.release(); return keep
H=240
def 缩(im):
    h,w = im.shape[:2]; return cv2.resize(im,(int(w*H/h),H))
def 拼(路们, 签们):
    图=[]; 
    for p,s in zip(路们,签们):
        im = 读图(p) if p.lower().endswith('.png') else 取帧(p, 0)
        if im is None: continue
        im = 缩(im); cv2.putText(im,s,(6,20),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),1,cv2.LINE_AA)
        图.append(im)
    宽 = sum(i.shape[1] for i in 图)
    布 = np.zeros((H,宽,3),np.uint8); x=0
    for i in 图: 布[:,x:x+i.shape[1]]=i; x+=i.shape[1]
    return 布
排=[]
排.append(拼([os.path.join(目,n) for n in ["01_格32.png","02_中32_1.png","02_中32_2.png","02_中32_3.png"]],
             ["01_g32 36.9","zhong1 56.1","zhong2 52.7","zhong3 44.3"]))
for 版 in ["子镜","子镜_v2"]:
    路=[]; 签=[]
    for k in range(1,5):
        p=os.path.join(目,版,f"格32_{k}.mp4")
        路.append(p); 签.append(f"{版} s{k} f0")
        路.append(p); 签.append(f"{版} s{k} f55")
    排.append(拼(路,签))
宽 = max(r.shape[1] for r in 排)
布 = np.zeros((H*len(排), 宽, 3), np.uint8)
for i,r in enumerate(排): 布[i*H:i*H+H, :r.shape[1]] = r
出 = r"D:\DSHworkspace\_看格32.jpg"
cv2.imencode('.jpg', 布, [int(cv2.IMWRITE_JPEG_QUALITY),88])[1].tofile(出)
print("写好了", 出, 布.shape)
