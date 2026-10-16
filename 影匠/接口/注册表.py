# -*- coding: utf-8 -*-
"""影匠 —— 接口/注册表：把适配器汇总注册，对外只露查询。

业务代码不该 import 任何一家供应商，只 import 这个文件：

    注册表.按能力找("图生视频")   -> 谁干得了这个活
    注册表.报价("wan22_i2v")      -> 干一次多少钱
    注册表.可用性()               -> 现在谁真的能用（ComfyUI 起来没、云端 key 配没配）
    注册表.自查()                 -> 这一层自己有没有毛病

用法（命令行）：

    python 注册表.py           # 列一下家底
    python 注册表.py 自查       # 全面体检，全过 = 退出码 0
    python 注册表.py 可用

作者：影匠 · 接口层。纯原创实现。
"""
from __future__ import annotations

import os
import sys

这里 = os.path.dirname(os.path.abspath(__file__))
if 这里 not in sys.path:
    sys.path.insert(0, 这里)


def _装(文件名, 别名):
    """载入同目录模块。中文模块名先试 import，失败退回按路径载入。"""
    路 = os.path.join(这里, 文件名)
    if not os.path.isfile(路):
        return None, f"文件不存在：{路}"
    名 = os.path.splitext(文件名)[0]
    try:
        return __import__(名), ""
    except Exception as e1:
        pass
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_影匠_" + 别名, 路)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        return m, ""
    except Exception as e2:
        return None, f"import 失败({e1!r})；按路径载入失败({e2!r})"


契约, _契约错 = _装("契约.py", "契约")
if 契约 is None:
    raise ImportError(f"注册表离不开 契约.py：{_契约错}")

# 供应商清单：一个文件一家。加供应商 = 往这里加一行。
供应商文件 = ("本地ComfyUI.py", "火山方舟.py")

_装进来的: dict = {}
_装失败的: dict = {}


def 装载(重新: bool = False) -> dict:
    """把 供应商文件 里列的适配器都装进来、注册进契约。返回 {名字: 适配器}。"""
    if _装进来的 and not 重新:
        return dict(_装进来的)
    _装进来的.clear()
    _装失败的.clear()
    for 文件 in 供应商文件:
        m, 错 = _装(文件, os.path.splitext(文件)[0])
        if m is None:
            _装失败的[文件] = 错
            continue
        元 = getattr(m, "元数据", None)
        if not callable(元):
            _装失败的[文件] = "没有 元数据() 函数，不像个适配器"
            continue
        try:
            名 = 契约.注册(m, 覆盖=True)
        except Exception as e:
            装不了 = f"过不了契约的注册检查：{e}"
            _装失败的[文件] = 装不了
            continue
        _装进来的[名] = m
    return dict(_装进来的)


def 装载失败() -> dict:
    装载()
    return dict(_装失败的)


# ───────────────────────────── 查询 ─────────────────────────────


def 列适配器() -> list[dict]:
    """一家一行，够打印用。"""
    装载()
    出 = []
    for 名, a in _装进来的.items():
        元 = a.元数据()
        出.append({
            "名称": 名,
            "能力": list(元.get("能力") or []),
            "模型": list(元.get("模型") or []),
            "是否本地": bool(元.get("是否本地")),
            "需要联网": bool(元.get("需要联网")),
            "异步能力": list(元.get("异步能力") or []),
            "备注": 元.get("备注", ""),
        })
    return 出


def 按能力找(能力: str) -> list:
    """谁声明支持这个能力。返回适配器对象列表（不是名字）。"""
    装载()
    return 契约.找能力(能力)


def 按能力找名(能力: str) -> list[str]:
    return [a.元数据()["名称"] for a in 按能力找(能力)]


def 挑(能力: str, 要本地: bool | None = None):
    """按能力挑一个适配器。要本地=True 就只挑本地的。

    挑的顺序：**本机优先**（不花钱、不怕断网），本机不行才上云。
    """
    装载()
    候选 = 按能力找(能力)
    if 要本地 is not None:
        候选 = [a for a in 候选 if bool(a.元数据().get("是否本地")) == 要本地]
    if not 候选:
        return None
    候选.sort(key=lambda a: 0 if a.元数据().get("是否本地") else 1)
    return 候选[0]


def 报价(模型id: str, 参数: dict | None = None) -> list[dict]:
    """问价：这个模型id 跑一次多少钱。

    参数里认得的：
        张数 / 次数   乘上去
        时长秒        当费率单位是「秒」时乘上去
    本地适配器单价 0 —— 它给的是 0，不是「不知道」。
    """
    装载()
    参数 = dict(参数 or {})
    出 = []
    for 名, a in _装进来的.items():
        费 = a.元数据().get("费率") or {}
        for 模型, 条 in 费.items():
            if 模型 != 模型id and 模型id.lower() not in str(模型).lower():
                continue
            单位 = 条.get("单位") or "次"
            系数 = 参数.get("张数") or 参数.get("次数") or 参数.get("段数") or 1
            if 单位 == "秒" and 参数.get("时长秒"):
                系数 = 参数["时长秒"]
            elif 参数.get("时长秒") and 条.get("按秒"):
                系数 = 参数["时长秒"]
            单价 = 条.get("单价")
            预估 = None if 单价 is None else round(float(单价) * float(系数), 4)
            出.append({
                "适配器": 名,
                "模型id": 模型,
                "单价": 单价,
                "单位": 单位,
                "币种": 条.get("币种") or "CNY",
                "系数": 系数,
                "预估": 预估,
                "说明": 条.get("说明", ""),
                "是本地": bool(a.元数据().get("是否本地")),
                "能不能确定": 单价 is not None,
            })
    return 出


def 可用性(含云端: bool = True) -> dict:
    """现在到底谁能用。会真的去探（ComfyUI 发一次请求，云端只看环境变量）。"""
    装载()
    出 = {}
    for 名, a in _装进来的.items():
        元 = a.元数据()
        if not 含云端 and not 元.get("是否本地"):
            continue
        条 = {
            "是否本地": bool(元.get("是否本地")),
            "需要联网": bool(元.get("需要联网")),
            "就绪": False, "缺": [], "提示": "",
        }
        钩 = getattr(a, "凭证检查", None)
        if callable(钩):
            try:
                r = 钩() or {}
                条["就绪"] = bool(r.get("就绪"))
                条["缺"] = list(r.get("缺") or [])
                条["提示"] = str(r.get("提示") or "")
            except Exception as e:
                条["提示"] = f"凭证检查() 自己炸了：{e!r}"
        else:
            条["就绪"] = True
            条["提示"] = "（这家没实现 凭证检查()，没法探，当它可用）"
        出[名] = 条
    for 文件, 错 in _装失败的.items():
        出[f"（装载失败）{文件}"] = {
            "是否本地": None, "需要联网": None,
            "就绪": False, "缺": [文件], "提示": 错,
        }
    return 出


def 未验证项() -> dict:
    """哪家自己承认「有东西没验证过」。别让上层误以为全都测过了。"""
    装载()
    出 = {}
    for 名, a in _装进来的.items():
        v = a.元数据().get("未验证")
        if v:
            出[名] = list(v)
    return 出


# ───────────────────────────── 自查 ─────────────────────────────


class 体检:
    def __init__(self):
        self.条们 = []

    def 查(self, 名: str, 过: bool, 说明: str = ""):
        self.条们.append({"项": 名, "过": bool(过), "说明": 说明})
        return bool(过)

    def 全过(self) -> bool:
        return all(b["过"] for b in self.条们)


def 自查(打印: bool = False) -> tuple[bool, str]:
    """全面体检：契约自己 + 每家适配器的形状、元数据、路径规矩、状态映射。

    只查**静态能查的**（不发网络、不发真请求）——所以它随时能跑，也不花钱。
    真跑不在这里，在 作品\\接口自测\\自测.py。
    """
    t = 体检()

    # ── 契约自己 ──
    t.查("契约.状态全集 是五态", 契约.状态全集 == ("排队", "运行", "完成", "失败", "未知"),
          str(契约.状态全集))
    样本 = [
        ("queued", 契约.排队), ("running", 契约.运行), ("succeeded", 契约.完成),
        ("failed", 契约.失败), ("cancelled", 契约.失败),
        # 这几条是「未知」立场的试金石：必须判未知，判失败就是 bug
        ("timeout", 契约.未知), ("expired", 契约.未知), ("task not found", 契约.未知),
        ("502", 契约.未知), ("", 契约.未知), ("莫名其妙的东西", 契约.未知),
    ]
    坏 = [f"{a!r}→{契约.归一(a)}（想要 {b}）" for a, b in 样本 if 契约.归一(a) != b]
    t.查("契约.归一 把「可能已送达但说不清」判成未知而不是失败", not 坏, "；".join(坏))
    t.查("契约.是终态(未知) == False（未知要人去查，不算收工）", not 契约.是终态(契约.未知))

    该拒 = ["D:\\x\\a.png", "C:/x/a.png", "\\\\服务器\\共享\\a.png", "//服务器/a.png",
            "a.png", "/a/../b.png", "/作品/", "https://x/a.png", "file:///D:/a.png",
            "/作品/a:b.png"]
    坏 = [v for v in 该拒 if not 契约.检查路径值(v)]
    t.查("契约.检查路径值 拦得住绝对路径/UNC/URL/..", not 坏, "漏放：" + "、".join(map(repr, 坏)))
    该放 = ["/作品/接口自测/a.png", "/素材/角色/沈砚/正面.png", "/a/b/c.mp4"]
    坏 = [v for v in 该放 if 契约.检查路径值(v)]
    t.查("契约.检查路径值 放得过正常相对路径", not 坏,
          "误杀：" + "；".join(f"{v}→{契约.检查路径值(v)}" for v in 坏))
    t.查("契约.扫描绝对路径 抓得住藏在嵌套里的盘符",
           bool(契约.扫描绝对路径({"a": {"b": ["D:\\悄悄\\夹带.png"]}})))
    坏 = 契约.校验提交体({"端点": "http://x/y", "方法": "POST", "体": {}})
    t.查("契约.校验提交体 不许端点是完整网址", bool(坏), "；".join(坏))
    坏 = 契约.校验提交体({"端点": "/x", "方法": "POST", "体": {"p": "D:\\x.png"}})
    t.查("契约.校验提交体 抓得住体里的本机绝对路径", bool(坏), "；".join(坏))
    t.查("契约.校验提交体 放得过正常提交体",
          not 契约.校验提交体({"端点": "/prompt", "方法": "POST", "体": {"a": 1}}))

    # ── 各家 ──
    装进来的 = 装载()
    t.查("至少装进来一家适配器", bool(装进来的), f"装进来 {len(装进来的)} 家")
    for 文件, 错 in _装失败的.items():
        t.查(f"适配器 {文件} 装得进来", False, 错)

    for 名, a in 装进来的.items():
        前 = f"[{名}]"
        t.查(f"{前} 契约要求的函数齐全", not 契约.缺什么函数(a),
              "；".join(契约.缺什么函数(a)))
        元 = {}
        try:
            元 = a.元数据()
        except Exception as e:
            t.查(f"{前} 元数据() 调得动", False, repr(e))
            continue
        t.查(f"{前} 元数据() 合格", not 契约.校验元数据(元),
              "；".join(契约.校验元数据(元)))
        t.查(f"{前} 名称跟注册名一致", 元.get("名称") == 名, f"{元.get('名称')!r} vs {名!r}")
        t.查(f"{前} 声明了能力", bool(元.get("能力")), str(元.get("能力")))
        t.查(f"{前} 声明了费率（哪怕是 0 或 None）", bool(元.get("费率")),
              "费率表空的话，报价() 永远查不到它")
        for 能 in (元.get("能力") or []):
            if not 契约.是异步(a, 能):
                continue
            t.查(f"{前} 异步能力「{能}」有 parseResult", callable(getattr(a, "parseResult", None)))
            try:
                点 = a.轮询端点("假号")
                t.查(f"{前} 异步能力「{能}」的 轮询端点() 给得出东西",
                      bool(点) and all("端点" in x for x in 点), str(点)[:120])
            except Exception as e:
                t.查(f"{前} 异步能力「{能}」的 轮询端点() 不炸", False, repr(e))
        # 凭证检查：没 key / 服务器没起来都不许崩
        try:
            r = a.凭证检查() if callable(getattr(a, "凭证检查", None)) else {"就绪": True, "提示": ""}
            t.查(f"{前} 凭证检查() 不崩（没配好也要给人话）",
                  isinstance(r, dict) and "提示" in r and bool(str(r["提示"]).strip()),
                  str(r.get("提示"))[:120])
        except Exception as e:
            t.查(f"{前} 凭证检查() 不崩", False, repr(e))
        # 校验() 必须返回列表、必须不抛
        try:
            空 = a.校验({"能力": "这个能力不存在"})
            t.查(f"{前} 校验(怪请求) 返回列表且不抛", isinstance(空, list) and bool(空), str(空)[:120])
        except Exception as e:
            t.查(f"{前} 校验(怪请求) 不抛", False, repr(e))
        try:
            怪 = a.校验(None)
            t.查(f"{前} 校验(None) 不抛", isinstance(怪, list), str(怪)[:120])
        except Exception as e:
            t.查(f"{前} 校验(None) 不抛", False, repr(e))

    # ── 报价 / 挑 ──
    t.查("按能力找得到「文生图」", bool(按能力找("文生图")), str(按能力找名("文生图")))
    t.查("按能力找得到「图生视频」", bool(按能力找("图生视频")), str(按能力找名("图生视频")))
    t.查("挑() 优先挑本地的", (挑("文生图") or {}) and
          挑("文生图").元数据().get("是否本地") is True,
          "本机自跑不要钱也不怕断网，理应优先")

    for 名, a in 装进来的.items():
        for m in (a.元数据().get("模型") or []):
            报 = 报价(m)
            t.查(f"[{名}] 模型 {m} 报得出价", bool([x for x in 报 if x["适配器"] == 名]),
                  "费率表里有这个 id 才对得上")

    # ── 不可用也不许崩 ──
    try:
        可用 = 可用性()
        t.查("可用性() 跑得动（哪怕全不可用）", isinstance(可用, dict) and bool(可用),
              "；".join(f"{k}={'就绪' if v['就绪'] else '不可用'}" for k, v in 可用.items()))
    except Exception as e:
        t.查("可用性() 跑得动（哪怕全不可用）", False, repr(e))

    过 = t.全过()
    行 = ["影匠 · 模型接入层自查", "=" * 60]
    好 = sum(1 for b in t.条们 if b["过"])
    行.append(f"共 {len(t.条们)} 项，过 {好} 项，不过 {len(t.条们) - 好} 项")
    行.append("")
    for b in t.条们:
        行.append(f"  [{'✓' if b['过'] else '✗'}] {b['项']}")
        if not b["过"] and b["说明"]:
            行.append(f"        ↳ {b['说明']}")
    行.append("")
    行.append(f"结论：{'全部通过' if 过 else '有项目没过，看上面 ✗'}")
    报 = "\n".join(行)
    if 打印:
        print(报)
    return 过, 报


# ───────────────────────────── 命令行 ─────────────────────────────


def _列家底() -> str:
    行 = ["影匠 · 模型接入层", "=" * 60]
    for 条 in 列适配器():
        地 = "本机" if 条["是否本地"] else "云端"
        行.append(f"\n【{条['名称']}】{地}｜联网：{'要' if 条['需要联网'] else '不要'}")
        行.append(f"  能力：{'、'.join(条['能力'])}")
        行.append(f"  模型id：{'、'.join(条['模型']) or '（无）'}")
        行.append(f"  异步：{'、'.join(条['异步能力']) or '（全是同步）'}")
        if 条["备注"]:
            行.append(f"  备注：{条['备注']}")
    for 文件, 错 in 装载失败().items():
        行.append(f"\n【装载失败】{文件}\n  {错}")
    return "\n".join(行)


def _列可用() -> str:
    行 = ["影匠 · 现在谁能用", "=" * 60]
    for 名, 条 in 可用性().items():
        行.append(f"\n[{'✓' if 条['就绪'] else '✗'}] {名}"
                  f"（{'本机' if 条['是否本地'] else '云端'}）")
        行.append("  " + str(条["提示"]).replace("\n", "\n  "))
        if 条["缺"]:
            行.append(f"  缺：{'、'.join(map(str, 条['缺']))}")
    return "\n".join(行)


if __name__ == "__main__":
    命 = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if 命 in ("自查", "check", "selfcheck"):
        过, _ = 自查(打印=True)
        sys.exit(0 if 过 else 1)
    elif 命 in ("可用", "avail"):
        print(_列可用())
        sys.exit(0)
    elif 命 in ("报价", "price"):
        for 条 in 列适配器():
            for m in 条["模型"]:
                for q in 报价(m):
                    print(f"{q['适配器']}｜{q['模型id']}｜单价 {q['单价']} {q['币种']}/{q['单位']}"
                          f"｜预估 {q['预估']}｜{q['说明']}")
        sys.exit(0)
    else:
        print(_列家底())
        print()
        print("用法：python 注册表.py [自查|可用|报价]")
        sys.exit(0)
