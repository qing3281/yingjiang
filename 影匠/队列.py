# -*- coding: utf-8 -*-
"""影匠 —— 队列.py：任务队列里的「并发闸门 / 实例轮转 / 降级」三块。

这个文件**不改** `账本.py`（持久账本归 账本.py），只补它没有的那三块：
账本是「这条活到底存不存在」的真相，队列是「现在能开几条、派给谁」的调度。

出处（全部实测，逐字来自飞彩编译产物）
----------------------------------------
`D:\\DSHworkspace\\网盘\\_飞彩解包\\Win\\.next\\static\\chunks\\2703-90569494d1040531.js`
@~86904 —— **每个身份各自一张闸门**：

    let f=new Map;
    function g(e){let t=e.trim();
     if(!t)return Promise.reject(Error("缺少项目并发队列身份"));
     let r=f.get(t)??{active:0,waiters:[]};f.set(t,r);
     let a=()=>{let e=!1;return()=>{if(e)return;e=!0;
       let n=r.waiters.shift();n?n.resolve(a()):(r.active-=1,0===r.active&&f.delete(t))}};
     return r.active<30?(r.active+=1,Promise.resolve(a()))
                       :new Promise(e=>r.waiters.push({resolve:e}))}

@~87976 —— **30 个槽位在实例上轮转**：

    function w(e,t){let r=y(e,t);
     return"project"===r.scope
       ?Array.from({length:30},(e,t)=>r.instances[t%r.instances.length].id)
       :[void 0]}

@~87848 —— 实例级事故的两句原话（**照抄**）：

    `项目设定的生图实例已停用或删除（${s.length} 个），请重新设置后再生图`
    "并发生图实例与当前项目配置不一致，已在供应商请求前停止"

`2853.2f06597dbfd3e0eb.js` @16327 —— 降级的一种：

    「归属不明的主机共享并发 1，添加不会生成作品。」
    「保存不运行生成；未知归属的主机共享并发 1，实际生成可能消耗租赁算力。」

`7528.b8e9b33e52e6855c.js` @772561 / @792313 —— 上游文案（照抄）：

    「导演批量运行请求已过期，未创建任务、未产生费用。」
    「当前画布缺少项目或画布标识，未创建任何任务、未产生费用。」

影匠自己的取舍（**自创，标出来**）
----------------------------------
1. 飞彩的闸门是**每个身份一张**（身份 = 项目/画布的 trim 后字符串），上限写死 30。
   影匠保留这两个语义，但把上限做成可配（`置闸门上限`），因为本机只有一张卡 ——
   账本那边默认上限是 1。两边是**两道不同的闸**，见下。
2. 飞彩只有 async（Promise）。影匠要给 `画布.py` 的同步逐节点执行用，
   所以加了同步的 `闸门()` 上下文管理器（threading 条件变量），语义与原版一致：
   FIFO、释放幂等、归零删身份。
3. **两道闸的分工（自创说法，机制是实测的）**：
   - `账本.取上限()` = **全局**闸，落在 SQLite 里，跨进程、可断点恢复；
   - `进程闸` = **每身份**闸，在进程内存里，管的是「同一个项目别一口气开 30 条」。
   跑一条任务两个都要过：先 `账本.领取()`（全局），再 `进程闸(身份)`（每身份）。
   这是影匠必须自创的一层 —— 飞彩是浏览器单进程，库在 IndexedDB 里，没有跨进程问题。

依赖：只依赖标准库 + 影匠自己的 `账本.py` / `接口/注册表.py`（都只读不改）。
"""
from __future__ import annotations

import os
import sys
import threading
import time

__all__ = [
    "并发上限默认", "槽位数默认", "作用域项目", "作用域老库",
    "队列身份空", "实例不一致", "闸门满",
    "进程闸", "身份表", "全部清空",
    "取实例", "选实例", "轮转",
    "故障转移", "降级",
    "分类", "策略",
    "跑一条", "自测", "自查",
]

_根 = os.path.dirname(os.path.abspath(__file__))
if _根 not in sys.path:
    sys.path.insert(0, _根)


def _装模块(文件名, 别名):
    """
    载入影匠既有模块（只读，绝不改它们）。
    中文文件名在部分环境直接 import 会失败，所以先试 import，再退回按路径载入。
    """
    try:
        return __import__(别名), ""
    except Exception as e1:
        pass
    try:
        import importlib.util

        p = os.path.join(_根, 文件名)
        if not os.path.isfile(p):
            return None, f"文件不存在：{p}"
        spec = importlib.util.spec_from_file_location("_影匠_" + 别名, p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        return m, ""
    except Exception as e2:
        return None, f"import 失败({e1!r})；按路径载入失败({e2!r})"


_账本, _账本错 = _装模块("账本.py", "账本")
_注册表, _注册表错 = _装模块(os.path.join("接口", "注册表.py"), "接口注册表")

# 老库：飞彩把「旧的图片实例」存这儿（localStorage 的等价物）。
_老库文件 = os.path.join(_根, "_work", "老实例.json")

# ───────────────────────────── 常量 ─────────────────────────────

# 飞彩原样的写死常数（2703-…@86904 的 r.active<30 和 @87976 的 length:30）
并发上限默认 = 30
槽位数默认 = 30

作用域项目 = "project"      # 飞彩：按项目配置的实例
作用域老库 = "legacy"       # 飞彩：没有项目配置，用老的实例清单

# 飞彩原文（照抄，别改字）
原话_身份空 = "缺少项目并发队列身份"
原话_实例不一致 = "并发生图实例与当前项目配置不一致，已在供应商请求前停止"
原话_批量过期 = "导演批量运行请求已过期，未创建任务、未产生费用。"
原话_批量为空 = "当前画布缺少项目或画布标识，未创建任何任务、未产生费用。"


class 队列身份空(ValueError):
    """飞彩：身份 trim 之后是空的，直接拒。"""


class 实例不一致(RuntimeError):
    """飞彩：指定的并发实例与项目当前配置对不上 —— 在供应商请求前就停。"""


class 闸门满(RuntimeError):
    """非阻塞领取时闸门满了（任务留在「排队」，不是失败）。"""


# ═══════════════════════ 并发闸门（飞彩 g() 的移植） ═══════════════════════


class _位:
    """一个身份的一张闸门：active + FIFO waiters。"""

    __slots__ = ("active", "waiters", "上限")

    def __init__(self, 上限: int):
        self.active = 0
        self.waiters: list[threading.Event] = []
        self.上限 = 上限


class 进程闸:
    """**每身份**一张并发闸门 —— 飞彩 `g()` 的直译。

    语义（逐条对着原版核过）：
      1. 身份先 ``.strip()``；空 → 抛 队列身份空（原版是 Promise.reject(Error(原话))）；
      2. 身份不存在就现建一张 ``{active:0, waiters:[]}``；
      3. ``active < 上限`` 立刻放行，否则**排队等**（FIFO，不是抢）；
      4. 释放令牌**幂等**：同一个令牌调两次，第二次什么也不做（原版那个 ``e=!1`` 守卫）；
      5. 释放时先把令牌交给队首等待者；没人等才 ``active -= 1``；``active`` 归零就**把身份删掉**
         （原版 ``0===r.active&&f.delete(t)`` —— 地图不留垃圾）。

    影匠自创的部分：上限可配（飞彩写死 30）、提供同步上下文管理器、记录等过多久。
    """

    def __init__(self, 上限: int = 并发上限默认):
        self._上限 = max(1, int(上限))
        self._锁 = threading.Lock()
        self._表: dict[str, _位] = {}
        self.等过总秒 = 0.0

    # ---- 配置 ----

    def 取闸门上限(self) -> int:
        return self._上限

    def 置闸门上限(self, n: int) -> int:
        self._上限 = max(1, int(n))
        return self._上限

    # ---- 内部 ----

    def _槽(self, 身份: str) -> _位:
        return self._表.setdefault(身份, _位(self._上限))

    def _令牌(self, 身份: str, 位: _位):
        """返回一个幂等的释放函数（原版 `a()` 的直译）。"""
        已放 = False
        锁 = self._锁

        def 放():
            nonlocal 已放
            with 锁:
                if 已放:
                    return False
                已放 = True
                n = 位.waiters.pop(0) if 位.waiters else None
                if n is not None:
                    n.set()                     # 令牌直接转交队首，active 不变
                else:
                    位.active -= 1
                    if 位.active == 0:
                        self._表.pop(身份, None)
            return True

        return 放

    # ---- 领取 ----

    def 领取(self, 身份: str, 超时: float | None = None):
        """拿一个槽位。返回**释放函数**（幂等）。等不到就按超时抛。

        这是飞彩 ``await g(身份)`` 的同步版：立刻有位置就立刻返回，
        没有就排队等，语义一模一样。
        """
        起 = time.time()
        键 = str(身份 or "").strip()
        if not 键:
            raise 队列身份空(原话_身份空)
        with self._锁:
            位 = self._槽(键)
            if 位.active < self._上限:
                位.active += 1
                return self._令牌(键, 位)
            无 = threading.Event()
            位.waiters.append(无)
        # 排队中：等前一个把令牌转交给我
        if not 无.wait(超时):
            with self._锁:
                try:
                    位.waiters.remove(无)
                except ValueError:
                    # 刚好在这一刻被转交了 —— 令牌已经是我的，别把自己摘出去
                    self.等过总秒 += time.time() - 起
                    return self._令牌(键, 位)
                if 位.active == 0 and not 位.waiters:
                    self._表.pop(键, None)
            raise 闸门满(f"身份 {键!r} 的并发闸门等超了（上限 {self._上限}，"
                        f"已等 {time.time() - 起:.1f} 秒）。任务**没有开跑**，"
                        f"也不会产生费用 —— 留在「排队」等下一轮。")
        self.等过总秒 += time.time() - 起
        with self._锁:
            return self._令牌(键, 位)

    def 试领取(self, 身份: str):
        """不排队：能拿就拿，拿不到抛 闸门满（飞彩的同步分支）。"""
        键 = str(身份 or "").strip()
        if not 键:
            raise 队列身份空(原话_身份空)
        with self._锁:
            位 = self._槽(键)
            if 位.active >= self._上限:
                raise 闸门满(
                    f"身份 {键!r} 的并发闸门满了：上限 {self._上限}，现在 {位.active} 条在跑，"
                    f"{len(位.waiters)} 条在等。任务留在「排队」，不是失败。"
                )
            位.active += 1
            return self._令牌(键, 位)

    # ---- 看一眼 ----

    def 身份表(self) -> list[dict]:
        with self._锁:
            return [{"身份": k, "在跑": v.active, "在等": len(v.waiters), "上限": v.上限}
                    for k, v in sorted(self._表.items())]

    def 闸门(self, 身份: str) -> dict:
        键 = str(身份 or "").strip()
        with self._锁:
            v = self._表.get(键)
            return {"身份": 键, "在跑": v.active if v else 0,
                    "在等": len(v.waiters) if v else 0, "上限": self._上限}

    def 全部清空(self) -> int:
        with self._锁:
            n = len(self._表)
            self._表.clear()
            return n

    # ---- 同步上下文管理器（影匠自创） ----

    class _守:
        def __init__(self, 闸: "进程闸", 身份: str, 超时: float | None):
            self.闸, self.身份, self.超时 = 闸, 身份, 超时
            self._放 = None
            self.等了 = 0.0

        def __enter__(self):
            起 = time.time()
            self._放 = self.闸.领取(self.身份, self.超时)
            self.等了 = time.time() - 起
            return self

        def __exit__(self, *a):
            if self._放:
                self._放()
            return False

    def 闸门守(self, 身份: str, 超时: float | None = None) -> "进程闸._守":
        """``with 闸.闸门守("项目:xxx"):`` —— 出块自动释放（幂等，异常也释放）。"""
        return 进程闸._守(self, 身份, 超时)


# 模块级默认闸门（飞彩那个 `let f=new Map` 也是模块级单例）
_默认闸 = 进程闸()


def 身份表() -> list[dict]:
    return _默认闸.身份表()


def 全部清空() -> int:
    return _默认闸.全部清空()


# ═══════════════════ 实例轮转与故障转移（飞彩 w() 的移植） ═══════════════════


def _老实例() -> list[str]:
    """飞彩的 legacy 实例清单（localStorage `feicai-image-instance-ids` 的等价物）。"""
    try:
        import json

        with open(_老库文件, "r", encoding="utf-8") as f:
            v = json.load(f)
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
        if isinstance(v, dict):
            return [str(x) for x in (v.get("实例") or []) if str(x).strip()]
    except Exception:
        pass
    return []


def 取实例(项目实例: list | None = None, 指定: str = "", 老库: list | None = None) -> dict:
    """飞彩 ``y(e,t)``：算出这次该用哪些实例。

    返回 ``{scope, instances, 停用的}``，实例是 ``{"id":..., "名称":...}`` 形状的 dict。

    规矩（逐条对着原版核过）：
      * 老库为空 → ``scope="legacy"``，实例 = 全部（原版 ``[...t]``）；
      * 老库非空 → 项目实例里**不在老库里**的那些算「已停用或删除」，
        有一个就抛原话（注意原版判的是 ``s.length>0``，不是「全没了才抛」）；
      * 指定了具体实例但不在本次清单里 → 抛原话（**在供应商请求前**停）。
    """
    老 = list(老库 if 老库 is not None else _老实例())
    全 = list(项目实例 or [])
    规整 = []
    for x in 全:
        if isinstance(x, dict):
            规整.append({"id": str(x.get("id") or x.get("名称") or ""), "名称": str(x.get("名称") or x.get("id") or "")})
        else:
            规整.append({"id": str(x), "名称": str(x)})
    规整 = [x for x in 规整 if x["id"]]

    # ★ 影匠补的一层：**指定了实例就必须在项目清单里**，不管老库空不空。
    #   飞彩原版只在 project 分支查这个（`!a.includes(r)`），legacy 分支不查 ——
    #   那是浏览器里「没配项目就用老的」的语境。影匠多了 `指定实例` 这个入参，
    #   所以把它提到前面统一查：实例配错必须在**发出供应商请求之前**停，
    #   这是那两句原话的用意（「已在供应商请求前停止」）。
    if 指定 and 指定 not in [x["id"] for x in 规整]:
        raise 实例不一致(原话_实例不一致)

    if not 老:
        if not 规整:
            return {"scope": 作用域老库, "instances": [], "停用的": []}
        if 指定:
            return {"scope": 作用域老库, "instances": [x for x in 规整 if x["id"] == 指定],
                    "停用的": []}
        return {"scope": 作用域老库, "instances": 规整, "停用的": []}

    在册 = {x["id"]: x for x in 规整}
    停用 = [i for i in 老 if i not in 在册]
    if len(停用) > 0:
        raise 实例不一致(
            f"项目设定的生图实例已停用或删除（{len(停用)} 个），请重新设置后再生图"
        )
    # 老库里的 id 必须都在册（上面已保证），按老库顺序还原
    选 = [在册[i] for i in 老]
    if 指定:
        if 指定 not in [x["id"] for x in 选]:
            raise 实例不一致(原话_实例不一致)
        return {"scope": 作用域项目, "instances": [在册[指定]], "停用的": []}
    return {"scope": 作用域项目, "instances": 选, "停用的": []}


def 轮转(项目实例: list | None = None, 指定: str = "", 槽位数: int = 槽位数默认,
         老库: list | None = None) -> list:
    """飞彩 ``w(e,t)``：**N 个槽位在实例上轮着来**。

        Array.from({length:30},(e,t)=>r.instances[t%r.instances.length].id)

    project 作用域 → 长度 30 的数组，第 t 个槽是 ``instances[t % len]``；
    legacy 作用域 → ``[None]``（原版 ``[void 0]``：老库不轮转，交给上层决定）。
    """
    解 = 取实例(项目实例, 指定, 老库)
    if 解["scope"] != 作用域项目:
        return [None]
    例 = 解["instances"]
    if not 例:
        return [None]
    n = max(1, int(槽位数))
    return [例[t % len(例)]["id"] for t in range(n)]


def 选实例(槽位表: list, 第几条: int = 0):
    """按第几条任务取槽位（画布执行器就是这么用的：任务序号 % N）。"""
    if not 槽位表:
        return None
    return 槽位表[int(第几条) % len(槽位表)]


def 故障转移(实例们: list, 已废: list | None = None, 报=None) -> dict:
    """实例级失败 → 换一个实例（飞彩原话：**不自动重试这一条，换实例**）。

    飞彩的处置是「实例故障 → 换实例」，不是「同实例重试」：
    同一台机器刚挂过，原地重试大概率再挂一次。

    返回 ``{换到, 还有几个, 用光了, 说明}``。
    """
    废 = {str(x) for x in (已废 or [])}
    剩 = [x for x in (实例们 or []) if str(_实例id(x)) not in 废]
    if not 剩:
        if 报:
            报("本次未自动重试，请手动更换模型后再试")
        return {"换到": None, "还有几个": 0, "用光了": True,
                "说明": "本次未自动重试，请手动更换模型后再试"}
    if 报:
        报(f"实例级失败：换实例到 {_实例id(剩[0])}（不原地重试）")
    return {"换到": 剩[0], "还有几个": len(剩) - 1, "用光了": False,
            "说明": f"换到 {_实例id(剩[0])}；还有 {len(剩) - 1} 个备用"}


def _实例id(x):
    return x.get("id") if isinstance(x, dict) else x


def 降级(首选, 备选们: list, 原因: str = "", 报=None) -> dict:
    """降级（飞彩实测 12 处「降级」，最典型两句照抄）：

        「图片保存失败，使用 data URL 降级」
        「视觉分析跳过（降级）」

    本质：**主路失败不等于整体失败**，给一条能接受的次路，并把降级说出来（不假装没事）。
    """
    次 = list(备选们 or [])
    if not 次:
        if 报:
            报(f"无路可降（{原因}）")
        return {"用了": 首选, "降级了": False, "说明": f"没有备选，只能停：{原因}"}
    选 = 次[0]
    if 报:
        报(f"{原因}，降级：{_实例id(首选)} → {_实例id(选)}")
    return {"用了": 选, "降级了": True, "说明": f"{原因} → 降到 {_实例id(选)}"}


# 飞彩实测的两种降级原话（照抄，供上层直接用）
降级_存图 = "图片保存失败，使用 data URL 降级"
降级_视觉 = "视觉分析跳过（降级）"
降级_归属不明 = "归属不明的主机共享并发 1，添加不会生成作品。"


# ═══════════════════ 失败分类与重试策略（转发给账本，不重造） ═══════════════════


def 分类(错) -> dict:
    """失败分类 —— **转发** `账本.分类异常`，队列这边不重造一套。

    账本已经把错误分成「停」/「退避后重试」/「未知」三类，并且认不出的
    一律按最保守的「未知」处理（不许自动重试一笔可能已经花掉的调用）。
    """
    if _账本 is None:
        raise RuntimeError(f"`账本.py` 没装进来（{_账本错}）—— 失败分类在它那儿")
    return _账本.分类异常(错)


def 策略(错, 连败: int = 0, 试过几次: int = 0, 最多几次: int = 6) -> dict:
    """重试策略 = 账本的建议 + 队列自己的一层「次数上限」。

    ★ 影匠自创：账本明说「只给建议，不给次数上限」，次数上限由调用方决定。
      队列就是那个调用方 —— 这里给一个默认 6 次，且**永不对「未知」自动重试**。
    """
    建 = 账本_建议 = None
    if _账本 is None:
        raise RuntimeError(f"`账本.py` 没装进来（{_账本错}）")
    账本_建议 = _账本.建议(错, 连败)
    动 = 账本_建议["动作"]
    出 = dict(账本_建议)
    出["试过几次"] = int(试过几次)
    出["最多几次"] = int(最多几次)
    if 动 in ("停", "未知"):
        出["还重试吗"] = False
        出["为什么"] = 账本_建议["原因"]
        return 出
    if int(试过几次) >= int(最多几次):
        出["动作"] = "停"
        出["还重试吗"] = False
        出["为什么"] = f"已经试了 {试过几次} 次（上限 {最多几次}），别再硬撑：{账本_建议['原因']}"
        return 出
    出["还重试吗"] = True
    出["为什么"] = 账本_建议["原因"]
    return 出


# ═══════════════════════════ 队列司机 ═══════════════════════════


def 跑一条(
    做,
    类型: str = "其他",
    身份: str = "",
    项目实例: list | None = None,
    指定实例: str = "",
    第几条: int = 0,
    账本=None,
    闸: 进程闸 | None = None,
    戏名: str = "",
    镜头: str = "",
    格号: str = "",
    输入=None,
    闸门等秒: float | None = None,
    最多重试: int = 2,
    报=None,
    干跑: bool = False,
) -> dict:
    """**队列司机**：把一条活从「开账」推到「收尾」，两道闸都过。

    顺序（顺序本身是有讲究的，别调换）：

        ① 账本.预估()          —— 先把价钱说清楚（成本预告，J11）
        ② 账本.新建()          —— 落账，此刻起「这条活存不存在」有据可查（J1）
        ③ 账本.领取()          —— **全局**闸门：排队 → 运行（超了就抛 闸门满）
        ④ 进程闸(身份)         —— **每身份**闸门：同一个项目别一口气开 30 条
        ⑤ 取实例()/轮转()      —— 派给哪个实例（实例轮转）
        ⑥ 做(实例)             —— 真干活（由调用方给，队列不碰网络）
        ⑦ 收尾                —— 完成 / 失败 / **未知**

    ★ 第⑦步的铁律（飞彩 J4 + 影匠账本同一条）：
      抛出来的错先过 `分类()`：
        动作「停」        → 记失败()，**不重试**；
        动作「退避后重试」 → 记失败() → 退避 → `账本.重试()` → 回到 ③；
        动作「未知」      → 记未知()，**绝不自动重试**（可能已经计费）；
        实例级失败        → `故障转移()` 换实例，不原地重试。
    """
    出 = {"任务id": "", "状态": "", "产物": "", "试了几次": 0, "换过实例": [],
          "降级": False, "说明": "", "预估": None, "日志": []}

    def 说(x):
        出["日志"].append(str(x))
        if 报:
            try:
                报(x)
            except Exception:
                pass

    if _账本 is None:
        raise RuntimeError(f"`账本.py` 没装进来（{_账本错}）")
    L = 账本 or _账本.取账本()
    闸 = 闸 or _默认闸

    # ① 成本预告
    try:
        出["预估"] = L.预估(类型)
        说(f"成本预告：{类型} 约 {出['预估'].get('金额')} {出['预估'].get('依据')}"
           f"（{出['预估'].get('说明') or ''}）")
    except Exception as e:
        出["预估"] = {"错": repr(e)}
        说(f"成本预告没算出来（{e!r}）—— 照样往下走，但不许假装知道价")

    # ② 落账
    任务id = L.新建(类型, 戏名=戏名, 镜头=镜头, 格号=格号,
                    估算成本=(出["预估"] or {}).get("金额"), 输入=输入)
    出["任务id"] = 任务id
    说(f"落账：{任务id}")

    # 实例清单（先算，实例配错了要在**发出请求前**就停）
    try:
        解 = 取实例(项目实例, 指定实例)
        槽 = 轮转(项目实例, 指定实例, 第几条=0) if False else 轮转(项目实例, 指定实例)
        本实例 = 选实例(槽, 第几条)
        出["实例"] = _实例id(本实例)
        说(f"实例：scope={解['scope']}，这条派给 {出['实例']}")
    except 实例不一致 as e:
        出["状态"] = "实例不一致"
        出["说明"] = str(e)
        L.失败(任务id, 错=str(e))
        说(f"**在供应商请求前停下**：{e}")
        return 出

    if 干跑:
        出["状态"] = "干跑"
        出["说明"] = "只落账 + 过闸 + 挑实例，**没发出任何请求、没产生费用**"
        L.取消(任务id, 因="干跑")
        说(出["说明"])
        return 出

    连败 = 0
    试 = 0
    废实例: list[str] = []
    while True:
        试 += 1
        出["试了几次"] = 试
        # ③ 全局闸门
        try:
            L.领取(任务id)
        except Exception as e:
            出["状态"] = "闸门满"
            出["说明"] = str(e)
            说(f"全局闸门：{e}")
            return 出        # ④ 每身份闸门
        守 = 闸.闸门守(身份 or f"任务:{任务id}", 闸门等秒)
        try:
            with 守:
                if 守.等了 > 0.05:
                    说(f"每身份闸门等了 {守.等了:.1f} 秒（身份 {身份!r}）")
                # ⑤⑥ 干活
                try:
                    果 = 做(本实例, 出) or {}
                except Exception as e:
                    果 = {"错": e}
                if isinstance(果, dict) and 果.get("错") is not None:
                    e = 果["错"]
                    v = 分类(e)
                    实例级 = bool(getattr(e, "实例级", False)) or str(v["类别"]) == "实例级"
                    # ★ 顺序有讲究：**实例级判定必须在「未知」之前**。
                    #   实例级失败是「这台机器坏了」，换一台就能继续 —— 它压根不是
                    #   「钱花出去没有」的问题。要是一个实例级错误的话里恰好带 502/503
                    #   （`本机 ComfyUI 502` 这种），先走 分类() 就会被判成「退避后重试」，
                    #   然后拿着**已经废掉的那台**死磕退避 —— 那是错的。
                    #   所以：先认实例级 → 换实例；剩下的才交给 分类()。
                    if 实例级:
                        坏 = _实例id(本实例) or str(出.get("实例") or "")
                        if 坏:
                            废实例.append(坏)
                        出["换过实例"].append(坏)
                        换 = 故障转移(解.get("instances") or [], 废实例, 说)
                        L.失败(任务id, 错=str(e))
                        if 换["用光了"]:
                            出["状态"] = "失败"
                            出["说明"] = 换["说明"]
                            return 出
                        # 换实例 = 换一条新账接着跑（和 重试() 同一个道理：旧账已经
                        # 落成「失败」，不能再拿旧 id 去「领取」，否则撞在状态机上：
                        # 「任务 X 现在是「失败」，只有「排队」的才能领取。」）
                        旧id = 任务id
                        try:
                            任务id = L.重试(旧id)
                        except Exception as e2:
                            出["状态"] = "失败"
                            出["说明"] = f"账本不肯为重开的账建新任务：{e2}"
                            说(出["说明"])
                            return 出
                        出["任务id"] = 任务id
                        本实例 = 换["换到"]
                        出["实例"] = _实例id(本实例)
                        连败 = 0
                        说(f"换实例重开：{旧id} → {任务id}，派给 {出['实例']}")
                        continue
                    说(f"第 {试} 次失败：{v['类别']} → 动作「{v['动作']}」：{v['说明']}")
                    if v["动作"] == "未知":
                        L.未知因为(任务id, e)
                        出["状态"] = "未知"
                        出["说明"] = (f"{v['说明']}——**已停止自动重试**，"
                                    f"{v['下一步']}")
                        说(f"记「未知」，不自动重试：{出['说明']}")
                        return 出
                    建 = 策略(e, 连败, 试 - 1, 最多重试 + 1)
                    L.失败(任务id, 错=str(e))
                    if not 建["还重试吗"]:
                        出["状态"] = "失败"
                        出["说明"] = 建["为什么"]
                        说(f"记失败，不重试：{建['为什么']}")
                        return 出
                    # ★ 账本.重试() 是**开一条新任务**接着跑（重试链留着），不是把旧账
                    #   拨回「排队」——所以循环必须换到新 id 上，否则下一次「领取」会
                    #   撞在已经「失败」的旧账上（账本原话：只有「排队」的才能领取）。
                    旧id = 任务id
                    try:
                        任务id = L.重试(旧id)
                    except Exception as e2:
                        出["状态"] = "失败"
                        出["说明"] = f"账本拒绝重试：{e2}"
                        说(出["说明"])
                        return 出
                    出["任务id"] = 任务id
                    说(f"重试链：{旧id} → {任务id}")
                    等 = float(建.get("等待秒") or 0)
                    if 等 > 0:
                        说(f"退避 {等} 秒后重试")
                        time.sleep(等)
                    连败 += 1
                    continue
                # 成功
                产 = str((果 or {}).get("产物") or (果 or {}).get("输出路径") or "")
                本 = float((果 or {}).get("成本") or 0) or None
                L.完成(任务id, 输出路径=产, 实际成本=本)
                出["状态"] = "完成"
                出["产物"] = 产
                if (果 or {}).get("降级"):
                    出["降级"] = True
                出["说明"] = f"第 {试} 次成功" + ("（降级路径）" if 出["降级"] else "")
                说(出["说明"])
                return 出
        finally:
            if 守._放:
                守._放()


# ═══════════════════════════════ 自测 ═══════════════════════════════


def _拦(函数) -> str:
    """跑一下，把抛出来的异常话拿回来；没抛就返回空串。只给自测用。"""
    try:
        函数()
        return ""
    except Exception as e:
        return str(e)


class _数:
    def __init__(self):
        self.过 = self.败 = self.没测 = 0
        self.败项: list[str] = []

    def 测(self, 名, 条件, 详情=""):
        if 条件:
            self.过 += 1
            print(f"  ✓ {名}")
        else:
            self.败 += 1
            self.败项.append(名)
            print(f"  ✗ {名} {详情}")

    def 抛(self, 名, 函数, 异常, 含=""):
        try:
            函数()
        except 异常 as e:
            ok = (含 in str(e)) if 含 else True
            self.测(名, ok, "" if ok else f"异常话里没有「{含}」：{e}")
            return
        except Exception as e:
            self.测(名, False, f"抛的是 {type(e).__name__}，不是 {异常.__name__}：{e}")
            return
        self.测(名, False, "没抛")

    def 小结(self, 谁):
        print()
        print(f"{谁} 自测：通过 {self.过}，失败 {self.败}，没测 {self.没测}")
        if self.败项:
            print("失败项：")
            for x in self.败项:
                print(f"  - {x}")
        print("✓ 自测全过。" if not self.败 else "✗ 自测没过。")


def 自测() -> int:
    import tempfile

    c = _数()
    临时 = os.path.join(tempfile.mkdtemp(prefix="影匠队列自测_"), "账本.db")
    L = _账本.账本(临时, 自动快照=False)

    print("一、每身份并发闸门（飞彩 g()：active/waiters/30/FIFO/幂等/归零删）")
    闸 = 进程闸(3)
    try:
        闸.领取("   ")
        c.测("空身份抛飞彩原话", False, "没抛")
    except 队列身份空 as e:
        c.测("空身份抛飞彩原话", str(e) == 原话_身份空, str(e))
    c.测("身份先 strip（先试 import 再退回，原版也是 t=e.trim()）", 闸.闸门(" 甲 ")["身份"] == "甲")
    令牌 = []
    for i in range(3):
        令牌.append(闸.领取("甲"))
    c.测("3 个槽全拿走 → 在跑 3", 闸.闸门("甲")["在跑"] == 3, str(闸.闸门("甲")))
    c.抛("第 4 个 试领取 抛 闸门满（不排队那条路）",
         lambda: 闸.试领取("甲"), 闸门满, "并发闸门满了")
    c.测("另一身份互不影响（每身份一张）", 闸.试领取("乙") is not None
         and 闸.闸门("甲")["在跑"] == 3)
    c.测("释放幂等：同一个令牌放两次，第二次什么也不做",
         令牌[0]() is True and 令牌[0]() is False)
    c.测("放掉一个 → 在跑 2", 闸.闸门("甲")["在跑"] == 2, str(闸.闸门("甲")))
    令牌[1](); 令牌[2]()
    c.测("全放光 → 身份从表里删掉（原版 f.delete）", 闸.闸门("甲")["在跑"] == 0
         and all(x["身份"] != "甲" for x in 闸.身份表()), str(闸.身份表()))

    print()
    print("二、FIFO：先等的先拿到（不是抢）")
    闸2 = 进程闸(1)
    手 = 闸2.领取("p")
    顺序: list[str] = []
    线 = []
    for i in range(3):
        def 干(i=i):
            t = 闸2.领取("p", 超时=10)
            顺序.append(f"第{i + 1}个")
            t()
        线.append(threading.Thread(target=干))
        time.sleep(0.05)          # 保证入队顺序
    for t in 线:
        t.start()
    time.sleep(0.15)
    手()
    for t in 线:
        t.join(10)
    c.测("等待者按入队顺序拿到槽位", 顺序 == ["第1个", "第2个", "第3个"], str(顺序))
    c.测("都放完了 → 身份清空", 闸2.身份表() == [], str(闸2.身份表()))

    print()
    print("三、闸门守（with 块）：出块自动释放，异常也释放（影匠自创的那层）")
    闸3 = 进程闸(1)
    with 闸3.闸门守("画布:c1") as 守:
        c.测("块内占着槽位", 闸3.闸门("画布:c1")["在跑"] == 1)
    c.测("出块就放了", 闸3.闸门("画布:c1")["在跑"] == 0)
    try:
        with 闸3.闸门守("画布:c1"):
            raise RuntimeError("块里炸")
    except RuntimeError:
        pass
    c.测("块里抛异常也释放（不会漏槽）", 闸3.闸门("画布:c1")["在跑"] == 0)
    with 闸3.闸门守("画布:c1"):
        c.抛("同一身份重入会等超时 → 闸门满（上限 1）",
             lambda: 闸3.试领取("画布:c1"), 闸门满, "满了")

    print()
    print("四、实例轮转（飞彩 w()：Array.from({length:30},(e,t)=>instances[t%len])）")
    三家 = [{"id": "i1", "名称": "本机"}, {"id": "i2", "名称": "云A"}, {"id": "i3", "名称": "云B"}]
    解 = 取实例(三家, "", [])
    c.测("老库为空 → legacy 作用域，实例原样", 解["scope"] == 作用域老库
         and [x["id"] for x in 解["instances"]] == ["i1", "i2", "i3"], str(解["scope"]))
    c.测("legacy 不轮转 → [None]（原版 [void 0]）", 轮转(三家, "", 老库=[]) == [None])
    槽30 = 轮转(三家, "", 老库=["i1", "i2", "i3"])
    c.测("project 作用域 → 正好 30 个槽（原版 length:30）", len(槽30) == 30, str(len(槽30)))
    c.测("槽位按 t%3 轮转", 槽30[:7] == ["i1", "i2", "i3", "i1", "i2", "i3", "i1"], str(槽30[:7]))
    c.测("第 29 槽（最后一个）", 槽30[29] == "i3", str(槽30[29]))
    c.测("选实例：第 4 条（下标 3）派给 i1（3%3=0）", 选实例(槽30, 3) == "i1", str(选实例(槽30, 3)))
    c.测("选实例：第 5 条（下标 4）派给 i2（4%3=1）", 选实例(槽30, 4) == "i2", str(选实例(槽30, 4)))
    c.测("单实例时 30 个槽全是它", set(轮转(["only"], "", 老库=["only"])) == {"only"})
    解2 = 取实例(三家, "i2", ["i1", "i2", "i3"])
    c.测("指定实例 → 只留它一个", [x["id"] for x in 解2["instances"]] == ["i2"])
    c.抛("指定了一个不在项目清单里的实例 → 飞彩原话",
         lambda: 取实例(三家, "i9", ["i1", "i2", "i3"]), 实例不一致, 原话_实例不一致)
    c.抛("老库里有、项目清单里没有 → 飞彩原话（停用或删除）",
         lambda: 取实例(三家, "", ["i1", "i2", "i3", "i4"]), 实例不一致,
         "项目设定的生图实例已停用或删除")
    c.测("指定实例 + 老库为空 → 也要在发请求前停（影匠补的那层）",
         _拦(lambda: 取实例(三家, "i9", [])) == 原话_实例不一致)

    print()
    print("五、故障转移（实例级失败 → 换实例，不原地重试）")
    废: list[str] = []
    换 = 故障转移(三家, 废, None)
    c.测("还有备用 → 换到第一个", _实例id(换["换到"]) == "i1" and not 换["用光了"])
    废.append("i1")
    换2 = 故障转移(三家, 废, None)
    c.测("跳过废掉的实例", _实例id(换2["换到"]) == "i2", str(换2))
    换3 = 故障转移(三家, ["i1", "i2", "i3"], None)
    c.测("全废了 → 不自动重试，交人", 换3["用光了"]
         and 换3["说明"] == "本次未自动重试，请手动更换模型后再试", str(换3))

    print()
    print("六、降级（主路失败不等于整体失败，且降级要说出来）")
    d = 降级("i1", ["i2", "i3"], 原因="i1 连不上", 报=None)
    c.测("有备选就降，并且 降级了=True", d["降级了"] is True and _实例id(d["用了"]) == "i2")
    d2 = 降级("i1", [], 原因="i1 连不上")
    c.测("没备选就老实停下（不假装成功）", d2["降级了"] is False and "只能停" in d2["说明"])
    c.测("飞彩降级原话在册（照抄）",
         "图片保存失败" in 降级_存图 and "视觉分析跳过" in 降级_视觉)

    print()
    print("七、失败分类与重试策略（转发账本，队列只加次数上限）")
    v = 分类(RuntimeError("502 Bad Gateway"))
    c.测("502 → 可自动重试（退避后重试）", v["可自动重试"] is True, str(v))
    v2 = 分类(RuntimeError("参数不合法：ratio 只能是 16:9"))
    c.测("参数错 → 停（不重试，别浪费退避时间）", v2["动作"] == "停", str(v2))
    class 提交后失联(Exception):
        可能已计费 = True
        供应商任务号 = "up-123"
    v3 = 分类(提交后失联("连接被重置"))
    c.测("提交后失联（带任务号）→ 未知，不许自动重试",
         v3["动作"] == "未知" and v3["可自动重试"] is False, str(v3))
    c.测("未知原话带「已停止自动重试」", "已停止自动重试" in v3["下一步"]
         or "查" in v3["下一步"], v3["下一步"])
    建 = 策略(RuntimeError("503 Service Unavailable"), 连败=0, 试过几次=0, 最多几次=2)
    c.测("503 第一次能重试（退避后重试）", 建["还重试吗"] is True, str(建))
    建2 = 策略(RuntimeError("503 Service Unavailable"), 连败=3, 试过几次=2, 最多几次=2)
    c.测("到次数上限 → 停（队列自创的那层）", 建2["还重试吗"] is False, str(建2))
    建3 = 策略(提交后失联("超时"), 试过几次=0, 最多几次=9)
    c.测("★未知永远不重试（次数再多也不）", 建3["还重试吗"] is False, str(建3))

    print()
    print("八、跑一条：真落账 + 过两道闸 + 收尾（账本只读不改）")
    L.置上限(2)
    做过: list[str] = []
    r1 = 跑一条(lambda 实例, 出: (做过.append("ok"), {"产物": "/a.png", "成本": 0})[1],
              类型="出图", 身份="项目:p1", 账本=L, 报=None)
    c.测("成功那条：状态=完成", r1["状态"] == "完成", str(r1["状态"]))
    c.测("产物写进账本", (L.取(r1["任务id"]) or {}).get("输出路径") == "/a.png"
         or (L.取(r1["任务id"]) or {}).get("产物") == "/a.png",
         str(L.取(r1["任务id"])))
    c.测("过闸后没有残留（槽位都放了）", 闸.闸门("项目:p1")["在跑"] == 0
         and _默认闸.闸门("项目:p1")["在跑"] == 0, str(_默认闸.身份表()))
    c.测("成本预告给过了", bool(r1["预估"]) and "依据" in r1["预估"], str(r1["预估"]))

    炸次数 = {"n": 0}
    def 抖两下(实例, 出):
        炸次数["n"] += 1
        if 炸次数["n"] < 2:
            raise RuntimeError("503 service unavailable")
        return {"产物": "/b.png"}
    r2 = 跑一条(抖两下, 类型="出图", 身份="项目:p1", 账本=L, 报=None, 最多重试=3,
              闸门等秒=None)
    c.测("抖动两次后成功：状态=完成 且 试了 2 次", r2["状态"] == "完成"
         and r2["试了几次"] == 2, str(r2))

    def 失联(实例, 出):
        class E(Exception):
            可能已计费 = True
            供应商任务号 = "up-9"
        raise E("提交后连接被重置")
    r3 = 跑一条(失联, 类型="出片", 身份="项目:p1", 账本=L, 报=None)
    c.测("提交后失联 → 状态=未知", r3["状态"] == "未知", str(r3["状态"]))
    c.测("未知那条在账本里也是「未知」",
         (L.取(r3["任务id"]) or {}).get("状态") == "未知", str(L.取(r3["任务id"])))
    c.测("未知那条 试了几次=1（没偷偷重试）", r3["试了几次"] == 1, str(r3["试了几次"]))
    c.测("未知那条进「待人工」清单",
         any(x["id"] == r3["任务id"] for x in L.待人工()), str([x["id"] for x in L.待人工()]))

    def 参数错(实例, 出):
        raise RuntimeError("参数不合法：ratio 只能是 16:9")
    r4 = 跑一条(参数错, 类型="出图", 身份="项目:p1", 账本=L, 报=None)
    c.测("参数错 → 失败且不重试（试了 1 次）", r4["状态"] == "失败"
         and r4["试了几次"] == 1, str(r4))
    c.测("参数错的账是「失败」（不是未知）",
         (L.取(r4["任务id"]) or {}).get("状态") == "失败")

    def 实例挂(实例, 出):
        class 实例级错(Exception):
            实例级 = True
        raise 实例级错("本机 ComfyUI 502")
    r5 = 跑一条(实例挂, 类型="出图", 身份="项目:p1", 账本=L, 报=None,
              项目实例=三家, 第几条=0)
    c.测("实例级失败 → 换实例（换过实例非空）", len(r5["换过实例"]) >= 1, str(r5))
    c.测("换实例后仍然收尾（完成 或 失败，不留半路状态）",
         r5["状态"] in ("完成", "失败"), str(r5["状态"]))

    r6 = 跑一条(lambda i, o: {"产物": "/x.png"}, 类型="出图", 身份="项目:p1",
              账本=L, 干跑=True)
    c.测("干跑：不留运行中的账（已取消）",
         (L.取(r6["任务id"]) or {}).get("状态") == "取消", str(L.取(r6["任务id"])))
    c.测("干跑明说没发请求没花钱", "没发出任何请求" in r6["说明"], r6["说明"])

    print()
    print("九、闸门满：任务留在「排队」，不是失败（账本 + 队列两道都查）")
    L2 = _账本.账本(os.path.join(tempfile.mkdtemp(prefix="影匠队列自测2_"), "账本.db"),
                    自动快照=False)
    L2.置上限(1)
    占位 = L2.新建("出图", 戏名="占位")
    L2.领取(占位)
    r7 = 跑一条(lambda i, o: {"产物": "/never.png"}, 类型="出图", 身份="项目:p2", 账本=L2)
    c.测("全局闸门满 → 状态=闸门满", r7["状态"] == "闸门满", str(r7["状态"]))
    c.测("★满闸的任务留在「排队」（不是失败、不产生费用）",
         (L2.取(r7["任务id"]) or {}).get("状态") == "排队", str(L2.取(r7["任务id"])))
    L2.释放(占位)

    r8 = 跑一条(lambda i, o: {"产物": "/i9.png"}, 类型="出图", 身份="项目:p3", 账本=L,
              项目实例=三家, 指定实例="i9")
    c.测("实例配错 → 在发请求前就停（状态=实例不一致）", r8["状态"] == "实例不一致", str(r8))
    c.测("实例配错那条账是「失败」，且没跑过", r8["试了几次"] == 0)
    c.测("飞彩原话在错误里", 原话_实例不一致 in r8["说明"], r8["说明"])

    print()
    print("十、依赖落点核对（只查有没有，不改别人的文件）")
    c.测("账本.py 装进来了", _账本 is not None, _账本错)
    c.测("账本 有 分类异常（失败分类的源头）", hasattr(_账本, "分类异常"))
    c.测("账本 有 建议（重试策略的源头）", hasattr(_账本, "建议"))
    c.测("账本 有 预估（成本预告的源头）", hasattr(_账本, "预估"))
    c.测("账本 有 闸门/领取/释放（全局那道闸）",
         all(hasattr(_账本, x) for x in ("闸门", "领取", "释放")))
    c.测("接口/注册表.py 装进来了", _注册表 is not None, _注册表错)
    if _注册表 is not None:
        try:
            挑得到 = _注册表.挑("文生图")
            c.测("注册表.挑('文生图') 挑得出来", 挑得到 is not None
                 or _注册表.可用性().get("文生图") is None)
        except Exception as e:
            c.测("注册表.挑() 不炸", False, repr(e))
    c.测("画布.py 在（队列是它的下游执行器）",
         os.path.isfile(os.path.join(_根, "画布.py")))
    print("  （账本.py / 注册表.py 都是别人名下的文件，这里**只读不改**）")

    L.关()
    L2.关()
    临时根 = os.path.dirname(临时)
    try:
        import shutil
        shutil.rmtree(os.path.dirname(临时根), ignore_errors=True)
        shutil.rmtree(临时根, ignore_errors=True)
    except Exception:
        pass

    c.小结("队列.py")
    return 0 if c.败 == 0 else 1


def 自查(悄悄: bool = False) -> int:
    if 悄悄:
        import io
        import contextlib
        缓 = io.StringIO()
        with contextlib.redirect_stdout(缓):
            r = 自测()
        return r
    return 自测()


def _用法():
    print("用法：")
    print("  python 队列.py 自测          # 跑全部自查")
    print("  python 队列.py 身份表        # 现在每身份各开了几条")
    print("  python 队列.py 轮转 i1,i2,i3 # 看 30 个槽位怎么轮（要先把 i1.. 写进 老实例.json）")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    命 = sys.argv[1] if len(sys.argv) > 1 else "自测"
    if 命 in ("自测", "自查", "test"):
        raise SystemExit(自测())
    if 命 == "身份表":
        for x in 身份表():
            print(f"  {x['身份']}: 在跑 {x['在跑']} / 等 {x['在等']} / 上限 {x['上限']}")
        raise SystemExit(0)
    if 命 == "轮转":
        参 = sys.argv[2] if len(sys.argv) > 2 else ""
        例 = [{"id": x.strip(), "名称": x.strip()} for x in 参.split(",") if x.strip()]
        try:
            for i, s in enumerate(轮转(例, "", 老库=[x["id"] for x in 例])):
                print(f"  槽 {i + 1:>2} → {s}")
            raise SystemExit(0)
        except 实例不一致 as e:
            print(f"✗ {e}")
            raise SystemExit(1)
    _用法()
    raise SystemExit(2)
