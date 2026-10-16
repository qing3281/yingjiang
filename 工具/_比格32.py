import cv2, os, numpy as np
目 = r"D:\DSHworkspace\影匠\作品\楚子航"
def 读图(p):
    # cv2.imread 在中文路径下返回 None（和 imwrite 一样静默失败）
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
def 亮度(p):
    c = cv2.VideoCapture(p); 均=[]; ok,fr = c.read()
    while ok:
        均.append(float(fr.mean())); ok,fr = c.read()
    c.release(); return 均
def 报(名, 路):
    if not os.path.exists(路): print(f"  {名}: 缺"); return
    均 = 亮度(路)
    print(f"  {名}: 首 {均[0]:6.2f} → 末 {均[-1]:6.2f}   最亮 {max(均):6.2f}   最暗 {min(均):6.2f}   均 {np.mean(均):5.2f}   帧 {len(均)}")
print("关键帧亮度：")
for n in ["01_格32.png","02_中32_1.png","02_中32_2.png","02_中32_3.png"]:
    p=os.path.join(目,n)
    im=读图(p)
    print(f"  {n:18s} {im.mean():6.2f}" if im is not None else f"  {n:18s} 读不到")
print("对照 格30 的关键帧：")
for n in ["01_格30.png","02_中30_1.png","02_中30_2.png","02_中30_3.png","末帧\\末_格30.png"]:
    p=os.path.join(目,n); im=读图(p)
    print(f"  {n:18s} {im.mean():6.2f}" if im is not None else f"  {n:18s} 读不到")
print("\n主线版（现在在 子镜\\ 里的）：")
for k in range(1,5): 报(f"格32_{k}", os.path.join(目,"子镜",f"格32_{k}.mp4"))
print("\n子镜_v2 版（种子偏移 5557）：")
for k in range(1,5): 报(f"格32_{k}", os.path.join(目,"子镜_v2",f"格32_{k}.mp4"))
