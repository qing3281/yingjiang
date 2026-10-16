import os, shutil, sys
目 = r"D:\DSHworkspace\影匠\作品\楚子航"
新 = os.path.join(目, "子镜_v2")
旧 = os.path.join(目, "子镜")
备 = os.path.join(目, "子镜_格32旧版_备份")
os.makedirs(备, exist_ok=True)
搬 = 0
for k in range(1, 5):
    名 = f"格32_{k}.mp4"
    新路 = os.path.join(新, 名); 旧路 = os.path.join(旧, 名); 备路 = os.path.join(备, 名)
    assert os.path.exists(新路), f"新版缺 {名}"
    assert os.path.exists(旧路), f"旧版缺 {名}"
    shutil.copy2(旧路, 备路)          # 先备份（带文件名，规矩）
    shutil.copy2(新路, 旧路)          # 再覆盖
    搬 += 1
# 数个数（规矩 5）
新数 = len([f for f in os.listdir(旧) if f.endswith(".mp4")])
备数 = len([f for f in os.listdir(备) if f.endswith(".mp4")])
print(f"换了 {搬} 段；子镜\\ 现有 {新数} 个 mp4；备份目录 {备数} 个")
print("备份目录：", 备)
for k in range(1,5):
    p = os.path.join(旧, f"格32_{k}.mp4")
    print(f"  {os.path.basename(p):12s} {os.path.getsize(p):>10,} 字节  {os.path.getmtime(p):.0f}")
