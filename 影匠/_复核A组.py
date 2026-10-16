# -*- coding: utf-8 -*-
r"""复核网盘 A 组：**只看 inode，不看目录大小**。

为什么必须这么查（2026-10-14 的教训）：
  我之前凭「目录有多大」写了一份删除清单，写着 `ComfyUI-aki\models` 是 9.60 GB 的 SD1.5 老模型。
  今天复核发现**那个目录实际是 76.55 GB** —— 里面装的是 H3 的文本编码器和 VAE，
  而且**已经硬链到 `D:\\Comfy-Desktop\\ComfyUI-Shared\\models` 在用的那份**。
  按目录大小算「删了能省 76.55 GB」是错的；按 `st_nlink` 算才对。

判据：一个文件删掉能释放多少字节 =
  `0`          如果 `st_nlink > 1`（还有别的路径指着同一个 inode）
  `st_size`    如果 `st_nlink == 1`（这是最后一个链接）
"""
import os
import sys
from collections import defaultdict

根 = r"D:\DSHworkspace\素材\网盘"
在用 = r"D:\Comfy-Desktop\ComfyUI-Shared\models"

# A 组候选：打算删的东西
候选 = [
    ("aki 旧版本（四个旧版压缩包）", os.path.join(根, r"下载\ComfyUI-aki\旧版本")),
    ("aki v3.2 7z", os.path.join(根, r"下载\ComfyUI-aki\ComfyUI-aki-v3.2.7z")),
    ("aki models", os.path.join(根, r"下载\ComfyUI-aki\models")),
    ("九月整合包 7z（内容已解压取出）",
     os.path.join(根, r"下载\3.九月整合包（minimax+qwen2.1+自由姿势)\Comfyui-WF-整合包-不含模型-2026.9.28.7z")),
]

# 全盘 inode 索引（只索引「在用」那棵树，用来判断 nlink>1 的另一个链接是不是在用的那份）
def 建索引(树):
    索 = defaultdict(list)
    for 底, _, 文s in os.walk(树):
        for 文 in 文s:
            p = os.path.join(底, 文)
            try:
                st = os.stat(p)
            except OSError:
                continue
            索[(st.st_dev, st.st_ino)].append(p)
    return 索

print("=" * 78)
print("  复核网盘 A 组（按 inode 算，不按目录大小算）")
print("=" * 78)

print(f"\n  索引在用的那份：{在用}")
在用索 = 建索引(在用)
print(f"  共 {sum(len(v) for v in 在用索.values())} 个文件，{len(在用索)} 个 inode")

总名义 = 0
总真省 = 0
明细 = []

for 名, 路 in 候选:
    if not os.path.exists(路):
        print(f"\n  ── {名}：✗ 不在 {路}")
        continue

    文s = []
    if os.path.isfile(路):
        文s = [路]
    else:
        for 底, _, fs in os.walk(路):
            for f in fs:
                文s.append(os.path.join(底, f))

    名义 = 0
    真省 = 0
    共享 = []
    for p in 文s:
        try:
            st = os.stat(p)
        except OSError:
            continue
        名义 += st.st_size
        if st.st_nlink > 1:
            # 还有别的链接 —— 看看是不是在用的那份
            他 = [q for q in 在用索.get((st.st_dev, st.st_ino), []) if os.path.abspath(q) != os.path.abspath(p)]
            if 他:
                共享.append((p, 他[0], st.st_size))
                # 若「在用」那份也在同一棵树内被删，才真省；这里保守算 0
                真省 += 0
            else:
                # nlink>1 但另一个链接不在「在用」树里 —— 说明还有第三处，同样按 0 算
                共享.append((p, "（别的路径，未定位）", st.st_size))
        else:
            真省 += st.st_size

    总名义 += 名义
    总真省 += 真省
    明细.append((名, 路, len(文s), 名义, 真省, 共享))

    print(f"\n  ── {名}")
    print(f"     路径　{路}")
    print(f"     文件 {len(文s)} 个　名义 {名义 / 2**30:.2f} GB　**真能省 {真省 / 2**30:.2f} GB**")
    if 共享:
        共享.sort(key=lambda t: -t[2])
        print(f"     其中 {len(共享)} 个文件是硬链（删了不省空间），最大的几个：")
        for p, q, sz in 共享[:6]:
            短 = os.path.basename(p)
            print(f"       {sz / 2**30:7.2f} GB  {短}")
            print(f"                  ↳ 同一 inode：{q}")

print("\n" + "=" * 78)
print(f"  A 组合计：名义 {总名义 / 2**30:.2f} GB　→　**真能省 {总真省 / 2**30:.2f} GB**")
print("=" * 78)

print("""
  说明：上面「真能省」只算了 st_nlink == 1 的文件。
  硬链文件（st_nlink > 1）即使删掉这个路径，只要「在用」那份还在，**一个字节都不会释放** ——
  这正是为什么不能按目录大小估。
""")
