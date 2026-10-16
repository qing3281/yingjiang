# -*- coding: utf-8 -*-
"""
影匠 · 多连接分片下载
======================
为什么需要它：单连接从 hf-mirror 拉 19 GB 只有 3 MB/s（预计 1 小时 48 分），
但同一台机器上多开几条连接能各自跑到 3 MB/s 以上 —— 瓶颈不在带宽在单流。

做法：HEAD 问出总长 → 切成 N 段 → 每段一条 curl 并发拉 → 全下完按序拼起来。
每段内部支持「断了接着拉」：记住已落盘字节，对剩下的字节再发一个 Range 请求，
用追加的方式写到同一个分片文件上，不做整段重来。

只用标准库（subprocess + threading + os）。
"""
import os
import re
import shutil
import subprocess
import threading
import time

CURL = r"C:\WINDOWS\system32\curl.exe"


def 问大小(u, 超时=90):
    """要总长。三级探测，谁先答用谁。

    ⚠ 为什么不能只发 HEAD：ModelScope 的 CDN 对 HEAD 不返回 Content-Length
    （实测），于是整个下载器退回单连接，19 GB 要跑 2.4 小时而不是 9 分钟。
    有些 CDN 只在 GET 时用 Content-Range 告诉你总长，所以必须补第二、三级。
    """
    def _顺(命令):
        try:
            r = subprocess.run(命令, capture_output=True, text=True, timeout=超时 + 30)
        except subprocess.TimeoutExpired:
            return 0
        文本 = (r.stdout or "") + "\n" + (r.stderr or "")
        for 行 in 文本.splitlines():
            if 行.lower().startswith("content-range:"):
                m = re.search(r"/\s*(\d+)", 行)
                if m:
                    return int(m.group(1))
        最大 = 0
        for 行 in 文本.splitlines():
            if 行.lower().startswith("content-length:"):
                try:
                    最大 = max(最大, int(行.split(":", 1)[1].strip()))
                except ValueError:
                    pass
        return 最大

    for 命令 in (
        # ① 常规 HEAD
        [CURL, "-sIL", "--connect-timeout", "30", "--max-time", str(超时), u],
        # ② 取 1 字节，从响应头里读 Content-Range: bytes 0-0/总长
        [CURL, "-sL", "--connect-timeout", "30", "--max-time", str(超时),
         "-r", "0-0", "-o", os.devnull, "-D", "-", u],
        # ③ 同上但走 stdout（有的实现 -D - 会被 --silent 吞掉）
        [CURL, "-sL", "--connect-timeout", "30", "--max-time", str(超时),
         "-r", "0-0", "-o", os.devnull, "-w", "\nX-CR: %{size_download}\n", u],
    ):
        n = _顺(命令)
        if n:
            return n
    return 0


def 人类(n):
    for 单位, 除 in (("GB", 1073741824), ("MB", 1048576), ("KB", 1024)):
        if n >= 除:
            return f"{n/除:.2f} {单位}"
    return f"{n} B"


class 进度:
    """线程安全的进度板。

    ⚠ 早先的写法是「每轮循环开头把当前字节数记进来」，结果是：一条 curl 正在
    传几个 GB 的中间过程里，记录值一直停在 0，面板永远显示 0%（实测骗了自己
    一分钟）。现在改成每次报进度都直接问磁盘要文件大小 —— curl 往哪写、写到
    哪，这里读到的就是哪，不会撒谎。
    """

    def __init__(self, 总, 分片们=None):
        self.总 = 总
        self.分片们 = list(分片们 or [])
        self.各 = {}
        self.锁 = threading.Lock()
        self.起 = time.time()

    def 设(self, i, n):
        with self.锁:
            self.各[i] = n

    def 读(self):
        if self.分片们:
            下 = 0
            for p in self.分片们:
                # ⚠ 必须把 .seg 临时块也算进来。curl 跑着的整段时间里，字节都
                # 还在 .seg 里没落到正式分片上 —— 只数分片的话，一条正在传输的
                # 连接看起来永远停在 0（实测：16 路全速跑了 1 分钟，面板一直写
                # 「0 B / 19.09 GB  0.00 MB/s」）。这是同一类「进度撒谎」bug 的
                # 第二次发作，第一次是「每轮清零」。
                for q in (p, p + ".seg"):
                    try:
                        下 += os.path.getsize(q)
                    except OSError:
                        pass
            return 下
        with self.锁:
            return sum(self.各.values())

    def 行(self):
        下 = self.读()
        秒 = max(time.time() - self.起, 0.001)
        if self.总:
            百 = 下 / self.总 * 100
            剩 = (self.总 - 下) / (下 / 秒) if 下 else 0
            return (f"  {人类(下)} / {人类(self.总)}  {百:5.1f}%  "
                    f"{下/1048576/秒:5.2f} MB/s  已用 {秒/60:.1f} 分  还剩约 {剩/60:.1f} 分")
        return f"  {人类(下)}  {下/1048576/秒:.2f} MB/s  已用 {秒/60:.1f} 分"


def _拉一段(u, 分片, 起, 止, 进, i, 每段最多轮=60, 静默=False):
    """把 [起, 止] 这段字节拉到 分片 文件。断了就接着拉，不整段重来。"""
    要 = 止 - 起 + 1
    for 轮 in range(1, 每段最多轮 + 1):
        现 = os.path.getsize(分片) if os.path.exists(分片) else 0
        进.设(i, 现)
        if 现 >= 要:
            return True
        if 现 > 要:      # 多了（不该发生），截断
            with open(分片, "r+b") as f:
                f.truncate(要)
            进.设(i, 要)
            return True

        剩起 = 起 + 现
        # ⚠ 一轮别要太多。ModelScope 的 CDN 对超大 Range 会中途掐断
        # （实测 curl: (18) end of response with 1227594008 bytes missing，
        # 每段 1.19 GB 全部要不满）。改成每轮最多 256 MB，取完立刻再要下一段 ——
        # 总耗时几乎不变，但每一轮都能确实落盘，不会一断丢掉一个 GB。
        剩止 = min(止, 剩起 + 268435456 - 1)
        临时 = 分片 + ".seg"

        try:
            r = subprocess.run(
                [CURL, "-L", "--fail", "--no-progress-meter",
                 "--retry", "5", "--retry-delay", "3", "--retry-all-errors",
                 "--connect-timeout", "30", "--max-time", "0",
                 "--speed-limit", "8192", "--speed-time", "60",
                 "-r", f"{剩起}-{剩止}",
                 "-o", 临时, u],
                timeout=None)
            码 = r.returncode
        except Exception as e:
            if not 静默:
                print(f"    [段{i}] 异常 {type(e).__name__}: {e}", flush=True)
            码 = -1

        # 把拿到的接到分片上
        if os.path.exists(临时):
            得 = os.path.getsize(临时)
            if 得:
                with open(分片, "ab") as fo, open(临时, "rb") as fi:
                    shutil.copyfileobj(fi, fo, 8 * 1024 * 1024)
                os.remove(临时)
            else:
                os.remove(临时)

        新 = os.path.getsize(分片) if os.path.exists(分片) else 0
        进.设(i, 新)
        if 新 >= 要:
            return True
        if 新 <= 现 and 轮 >= 6:
            if not 静默:
                print(f"    [段{i}] 连续 6 轮无进展（退出码 {码}），放弃", flush=True)
            return False
        time.sleep(2)
    return False


def 拉(u, 目标, 份数=8, 预期=0, 静默=False):
    """并发分片下载。成功返回 True，文件落在 目标。"""
    os.makedirs(os.path.dirname(os.path.abspath(目标)), exist_ok=True)
    if not 预期:
        预期 = 问大小(u)
    if not 预期:
        if not 静默:
            print("    问不到大小，退回单连接 curl", flush=True)
        return _单连接(u, 目标)

    份数 = max(1, min(份数, 32))
    块 = 预期 // 份数
    分片目录 = 目标 + ".parts"
    os.makedirs(分片目录, exist_ok=True)

    区间 = []
    for i in range(份数):
        起 = i * 块
        止 = 预期 - 1 if i == 份数 - 1 else (i + 1) * 块 - 1
        区间.append((i, 起, 止))

    分片们 = [os.path.join(分片目录, f"{i:02d}") for i, _, _ in 区间]
    进 = 进度(预期, 分片们)

    if not 静默:
        print(f"    {份数} 路并发，每段约 {人类(块)}，总 {人类(预期)}", flush=True)

    # ── 看门线程：每 20 秒报一次总进度 ──
    停 = threading.Event()

    def 报进度():
        while not 停.wait(20):
            if not 静默:
                print(进.行(), flush=True)

    t = threading.Thread(target=报进度, daemon=True)
    t.start()

    # ── 并发拉 ──
    结果 = {}

    def 干(i, 起, 止):
        分片 = os.path.join(分片目录, f"{i:02d}")
        结果[i] = _拉一段(u, 分片, 起, 止, 进, i, 静默=静默)

    线 = [threading.Thread(target=干, args=(i, 起, 止), daemon=True) for i, 起, 止 in 区间]
    for x in 线:
        x.start()
    for x in 线:
        x.join()
    停.set()

    if not 静默:
        print(进.行(), flush=True)

    坏的 = [i for i, 好 in 结果.items() if not 好]
    if 坏的:
        if not 静默:
            print(f"    ✗ 段 {坏的} 没下完，先不拼", flush=True)
        return False

    # ── 拼 ──
    临时 = 目标 + ".拼装中"
    with open(临时, "wb") as fo:
        for i, 起, 止 in 区间:
            分片 = os.path.join(分片目录, f"{i:02d}")
            with open(分片, "rb") as fi:
                shutil.copyfileobj(fi, fo, 16 * 1024 * 1024)
    大小 = os.path.getsize(临时)
    if 大小 != 预期:
        if not 静默:
            print(f"    ✗ 拼出来 {人类(大小)}，应该是 {人类(预期)} —— 不替换目标文件", flush=True)
        os.remove(临时)
        return False

    os.replace(临时, 目标)
    shutil.rmtree(分片目录, ignore_errors=True)
    if not 静默:
        print(f"    ✓ 拼装完成 {人类(大小)}", flush=True)
    return True


def _单连接(u, 目标):
    """问不到大小时的退路。"""
    for 轮 in range(1, 200):
        r = subprocess.run(
            [CURL, "-L", "--fail", "--no-progress-meter",
             "--retry", "10", "--retry-delay", "5", "--retry-all-errors",
             "--connect-timeout", "30",
             "--speed-limit", "8192", "--speed-time", "60",
             "-C", "-", "-o", 目标, u], timeout=None)
        if r.returncode == 0:
            return True
        if 轮 >= 5 and not os.path.exists(目标):
            return False
        time.sleep(3)
    return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法：python _并行下.py <url> <目标文件> [份数]")
        sys.exit(1)
    u = sys.argv[1]
    目标 = sys.argv[2]
    份 = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    sys.exit(0 if 拉(u, 目标, 份) else 1)
