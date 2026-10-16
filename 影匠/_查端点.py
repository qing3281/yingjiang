# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\DSHworkspace\影匠")
import 引擎  # noqa: E402

for 名 in ("本机", "远端"):
    点 = 引擎.换端点(名)
    在 = 引擎.在线()
    print(f"  {名}　在线={在.get('在线')}　{在.get('端点')}　"
          f"{在.get('版本')}　{在.get('显卡','')}　空闲 {在.get('显存空闲GB')} GB")
