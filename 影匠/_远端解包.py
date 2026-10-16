# -*- coding: utf-8 -*-
import os
import tarfile
import time

目标 = r"E:\影匠AI\ComfyUI\custom_nodes"
包 = r"C:\Users\Seele\_节点包_21个.tar"

os.makedirs(目标, exist_ok=True)
前 = set(os.listdir(目标))

t0 = time.time()
with tarfile.open(包) as t:
    t.extractall(目标)
后 = set(os.listdir(目标))
新 = sorted(后 - 前)

print("  解开用时 %.1f 秒" % (time.time() - t0))
print("  新增 %d 个：%s" % (len(新), 新))
print("  现在 custom_nodes 共 %d 个目录" % len([d for d in os.listdir(目标)
                                             if os.path.isdir(os.path.join(目标, d))]))

# 复验：最要紧的那个包的 __init__.py 在不在
关键 = os.path.join(目标, "comfyui-minimax-h3-audio-T8", "__init__.py")
print("  关键包 __init__.py：%s" % ("在" if os.path.exists(关键) else "★ 不在"))
