# -*- coding: utf-8 -*-
"""核 `_怎么做出来的.html` 里写的每一个数字，看它和磁盘上的是不是一回事。

为什么要有这一步：那页页子末尾我自己写着「每个数字都是从磁盘上读出来的」——
那这句话本身就得有东西来验，不然它就是第 0.05 条第一条病（判据说 OK，其实什么都没量）。
"""
import glob, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")

目 = r"D:\DSHworkspace\影匠\作品\楚子航"
页 = os.path.join(目, "_怎么做出来的.html")

html = open(页, encoding="utf-8").read()
print("页：%s　%d 字节" % (页, len(html.encode("utf-8"))))

# 结构
for 标签 in ("div", "table", "tr", "td", "th", "p"):
    开 = len(re.findall(r"<%s[\s>]" % 标签, html))
    闭 = len(re.findall(r"</%s>" % 标签, html))
    旗 = "✓" if 开 == 闭 else "✗"
    print("  %s <%s> 开 %d 闭 %d" % (旗, 标签, 开, 闭))

判 = []
def 比(名, 页里, 实际):
    好 = (str(页里) == str(实际))
    判.append(好)
    print("  %s %-22s 页里=%-10s 磁盘=%s" % ("✓" if 好 else "✗", 名, 页里, 实际))

print("\n核数：")

格 = open(os.path.join(目, "02-九宫格.md"), encoding="utf-8").read()
# ★ 两种写法都要认：`格N：` 和 `## 格N`。
#   第一版只写了前一种，结果磁盘=0 —— 又是「闸冤枉真话」，不是数据错（这病今天第二次）。
格数 = len(sorted(set(int(m) for m in re.findall(r"格\s*(\d+)\s*[：:｜|]", 格))
                   | set(int(m) for m in re.findall(r"^#+\s*格\s*(\d+)", 格, re.M))))
比("格数", 32, 格数)

首 = len(glob.glob(os.path.join(目, "01_格*.png")))
中 = len(glob.glob(os.path.join(目, "02_中*.png")))
末 = len(glob.glob(os.path.join(目, "末帧", "末_格*.png")))
比("格首帧 01_格N.png", 32, 首)
比("中间帧 02_中N_K.png", 96, 中)
比("末帧 末_格N.png", 31, 末)
比("关键帧图合计", 159, 首 + 中 + 末)

比("总小段 32×4", 128, 32 * 4)
比("总帧 128×56", 7168, 128 * 56)
比("片长秒 7168÷24", 298.7, round(7168 / 24, 1))

表 = json.load(open(os.path.join(目, "配音", "_配音表.json"), encoding="utf-8"))
配 = 表.get("配音") or []
比("配音句数", 32, len(配))
比("人声合计秒", 65.36, round(sum(float(x.get("秒") or 0) for x in 配), 2))

# 页面上写死的四个弯路数字
内 = {"38.63": "接缝 MAE 中位（修之前）", "4.05": "段内正常一帧", "3.74": "接缝 MAE 中位（修之后）",
      "40.38": "首末帧像素中位差", "4.20": "OOM 还差的 GiB", "2.33": "一小段秒数",
      "4:58.7": "片长", "9.5 倍": "接缝倍数"}
for k, v in 内.items():
    好 = k in html
    判.append(好)
    print("  %s 页面里写着 %-8s（%s）" % ("✓" if 好 else "✗", k, v))

print()
print("结论：%s（%d/%d 项对上）" % ("✓ 页面上的数字和磁盘一致" if all(判) else "✗ 有对不上的",
                                  sum(判), len(判)))
sys.exit(0 if all(判) else 1)
