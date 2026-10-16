"""稳当的并行下载器 —— 每段自己循环续传，谁短了补谁，全齐了才拼装。

前两版死在两处，这版针对性修掉：
  1. curl 报 `(18) end of response with 268435456 bytes missing` —— 服务器在
     256 MB 边界掐连接。所以每次只请求一段，掐断了就从断点再要，直到这段够了。
  2. 上一版拿 `-C -` 续传却又把临时文件 os.remove 掉，而 curl 还握着它
     （WinError 32），线程当场死 → 拼出 14 GB 的半个文件。
     这版不再用 -C -，改成「自己记偏移 + 显式 Range」，续传逻辑全在我手里。

拼装前逐段核对字节数，一段不够就绝不拼 —— 宁可报错也不能交半个模型。
"""
import os
import shutil
import subprocess
import sys
import time

CURL = r"C:\WINDOWS\system32\curl.exe"


def 大小(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return 0


def _拉一段(网址, 段文件, 起, 止, 第几, 份数, 每试秒=300):
    """把 [起, 止] 这段字节拉全。返回 True/False。"""
    应长 = 止 - 起 + 1
    试 = 0
    while True:
        试 += 1
        if 试 > 400:
            print(f"    [{第几}] 400 次还没拉全，放弃", flush=True)
            return False
        已 = 大小(段文件)
        if 已 >= 应长:
            return True
        这次起 = 起 + 已
        临时 = 段文件 + ".tmp"
        if os.path.exists(临时):
            try:
                os.remove(临时)
            except OSError:
                time.sleep(1)
                continue
        子 = subprocess.run(
            [CURL, "-sL", "--fail", "--connect-timeout", "20",
             "--max-time", str(每试秒), "--speed-time", "30", "--speed-limit", "10240",
             "-r", f"{这次起}-{止}", "-o", 临时, 网址],
            capture_output=True)
        # --speed-limit 10KB/s 持续 30 秒就判死，避免僵在那一动不动
        新 = 大小(临时)
        if 新 > 0:
            with open(段文件, "ab") as f, open(临时, "rb") as g:
                shutil.copyfileobj(g, f, 4 * 1024 * 1024)
        try:
            os.remove(临时)
        except OSError:
            pass
        现 = 大小(段文件)
        if 现 == 已 and 子.returncode != 0:
            # 一点没动：多半是源端抽风，等一下重来
            time.sleep(2)
        if 现 >= 应长:
            return True
        if 试 % 5 == 0:
            print(f"    [{第几}] {现 / 1048576:.0f} / {应长 / 1048576:.0f} MB"
                  f"  第 {试} 次", flush=True)


def 主(网址, 目标, 份数=8):
    总 = None
    # 先问 Content-Length（走 HEAD 拿不到就退回 GET 一个字节看 Content-Range）
    r = subprocess.run([CURL, "-sL", "-I", "--connect-timeout", "20", 网址],
                       capture_output=True, text=True)
    for 行 in (r.stdout or "").splitlines():
        if 行.lower().startswith("content-length:"):
            总 = int(行.split(":")[1].strip())
    if not 总:
        r2 = subprocess.run([CURL, "-sL", "-r", "0-0", "-D", "-", "-o", os.devnull,
                             "--connect-timeout", "20", 网址],
                            capture_output=True, text=True)
        for 行 in (r2.stdout or "").splitlines():
            if 行.lower().startswith("content-range:"):
                总 = int(行.split("/")[-1].strip())
    if not 总:
        print("✗ 问不出文件总长，没法分段")
        return 2

    段目录 = 目标 + ".parts"
    os.makedirs(段目录, exist_ok=True)
    print(f"  总长 {总 / 1073741824:.3f} GB，切 {份数} 段", flush=True)

    每 = 总 // 份数
    任务 = []
    for i in range(份数):
        起 = i * 每
        止 = (总 - 1) if i == 份数 - 1 else (起 + 每 - 1)
        任务.append((i, 起, 止, os.path.join(段目录, f"{i:02d}.seg")))

    # 已经拉全的段直接跳过（断点续传）
    齐 = sum(1 for _, 起, 止, 段 in 任务 if 大小(段) >= 止 - 起 + 1)
    print(f"  已齐 {齐}/{份数} 段", flush=True)

    import threading
    结果 = {}

    def 干(i, 起, 止, 段):
        结果[i] = _拉一段(网址, 段, 起, 止, i, 份数)

    线 = [threading.Thread(target=干, args=t, daemon=True) for t in 任务]
    for t in 线:
        t.start()

    上轮 = 0
    while any(t.is_alive() for t in 线):
        time.sleep(15)
        现 = sum(大小(段) for _, _, _, 段 in 任务)
        print(f"  {现 / 1073741824:.2f} / {总 / 1073741824:.2f} GB"
              f"  ({现 / 总 * 100:.1f}%)  {(现 - 上轮) / 15 / 1048576:.1f} MB/s",
              flush=True)
        上轮 = 现
    for t in 线:
        t.join()

    短 = [(i, 大小(段), 止 - 起 + 1) for i, 起, 止, 段 in 任务
          if 大小(段) < 止 - 起 + 1]
    if 短:
        print("✗ 这些段没拉全，不拼装：")
        for i, 有, 应 in 短:
            print(f"    {i:02d}.seg  {有} / {应}  B")
        return 3

    print("  全部段齐了，拼装…", flush=True)
    临时目标 = 目标 + ".拼装中"
    with open(临时目标, "wb") as o:
        for _, _, _, 段 in 任务:
            with open(段, "rb") as g:
                shutil.copyfileobj(g, o, 8 * 1024 * 1024)
    拼 = 大小(临时目标)
    if 拼 != 总:
        print(f"✗ 拼出来 {拼} B，应该是 {总} B —— 不替换目标文件")
        return 1
    os.replace(临时目标, 目标)
    shutil.rmtree(段目录, ignore_errors=True)
    print(f"✓ {目标}\n  {拼} B ({拼 / 1073741824:.3f} GB)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(主(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8))
