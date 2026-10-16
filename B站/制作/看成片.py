# -*- coding: utf-8 -*-
"""把成片目录用 HTTP 挂出来，手机/平板在同一个 WiFi 下就能直接看。

用法：
    python 看成片.py                  # 默认挂 D:\\DSHworkspace\\B站\\成片，端口 8777
    python 看成片.py --根 <目录> --端口 9000
    python 看成片.py --停              # 把在跑的关掉

手机浏览器打开：http://<电脑局域网IP>:8777
"""
import argparse
import html
import http.server
import os
import socket
import socketserver
import subprocess
import sys
import urllib.parse

默认根 = r"D:\DSHworkspace\B站\成片"
默认端口 = 8777
端口文件 = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".看成片端口")

视频后缀 = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
图片后缀 = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp"}
音频后缀 = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
文本后缀 = {".html", ".htm", ".md", ".txt", ".json", ".srt", ".vtt"}


def 局域网IP() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def 大小(n: int) -> str:
    for 单位 in ("B", "KB", "MB", "GB"):
        if n < 1024 or 单位 == "GB":
            return f"{n:.0f} {单位}" if 单位 == "B" else f"{n/1:.1f} {单位}" if False else f"{n:.1f} {单位}"
        n /= 1024.0
    return f"{n:.1f} GB"


def 人读(n: int) -> str:
    v = float(n)
    for 单位 in ("B", "KB", "MB", "GB"):
        if v < 1024 or 单位 == "GB":
            return f"{v:.0f} {单位}" if 单位 == "B" else f"{v:.1f} {单位}"
        v /= 1024.0
    return f"{v:.1f} GB"


样式 = """
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 :root{color-scheme:dark}
 body{background:#14141a;color:#e8e8ee;font:15px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;padding:16px}
 a{color:#7fd4ff;text-decoration:none} a:hover{text-decoration:underline}
 h1{font-size:19px;margin:4px 0 14px;color:#ffd166}
 .p{color:#8b8b98;font-size:13px;margin:-8px 0 16px;word-break:break-all}
 table{width:100%;border-collapse:collapse}
 td{padding:9px 6px;border-bottom:1px solid #26262e;vertical-align:middle}
 td.s{text-align:right;color:#8b8b98;white-space:nowrap;font-size:13px;padding-left:10px}
 .i{display:inline-block;width:22px;text-align:center;margin-right:6px}
 video,img{max-width:100%;border-radius:10px;display:block;margin:10px 0}
 pre{background:#1c1c24;padding:12px;border-radius:10px;overflow:auto;font-size:13px}
 .back{display:inline-block;margin-bottom:10px;color:#8b8b98}
</style>
"""


class 处理(http.server.SimpleHTTPRequestHandler):
    根 = 默认根

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=处理.根, **kw)

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    # ---------- 目录页 ----------
    def 列目录(self, 相对: str):
        实路 = os.path.join(处理.根, 相对)
        条目 = []
        try:
            名表 = sorted(os.listdir(实路), key=lambda s: (os.path.isfile(os.path.join(实路, s)), s.lower()))
        except OSError as e:
            self.send_error(404, str(e))
            return
        for 名 in 名表:
            if 名.startswith("."):
                continue
            子 = os.path.join(实路, 名)
            是目录 = os.path.isdir(子)
            后缀 = os.path.splitext(名)[1].lower()
            图标 = "📁" if 是目录 else (
                "🎬" if 后缀 in 视频后缀 else "🖼" if 后缀 in 图片后缀 else
                "🎵" if 后缀 in 音频后缀 else "📄" if 后缀 in 文本后缀 else "📦")
            链接 = urllib.parse.quote(名) + ("/" if 是目录 else "")
            条 = os.path.getsize(子) if not 是目录 else 0
            条目.append(
                f'<tr><td><span class="i">{图标}</span><a href="{链接}">{html.escape(名)}</a></td>'
                f'<td class="s">{人读(条) if not 是目录 else ""}</td></tr>')
        上级 = ""
        if 相对:
            上级 = '<a class="back" href="../">← 上一级</a>'
        行 = "\n".join(条目) or '<tr><td class="s">（空）</td></tr>'
        h = (f'<!doctype html><meta charset="utf-8"><title>看成片</title>{样式}'
             f'{上级}<h1>📂 /{html.escape(相对)}</h1>'
             f'<div class="p">{html.escape(处理.根)}</div>'
             f'<table>{行}</table>')
        b = h.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    # ---------- 文件页（视频/图片内嵌播放） ----------
    def 看文件(self, 相对: str):
        实路 = os.path.join(处理.根, 相对)
        后缀 = os.path.splitext(实路)[1].lower()
        链接 = urllib.parse.quote(os.path.basename(相对))
        上级 = '<a class="back" href="./">← 回到目录</a>'
        if 后缀 in 视频后缀:
            体 = f'<video src="{链接}" controls autoplay playsinline></video>'
        elif 后缀 in 图片后缀:
            体 = f'<img src="{链接}">'
        elif 后缀 in 音频后缀:
            体 = f'<audio src="{链接}" controls autoplay></audio>'
        elif 后缀 == ".html":
            self.send_response(302)
            self.send_header("Location", 链接)
            self.end_headers()
            return
        elif 后缀 == ".md":
            文字 = open(实路, encoding="utf-8", errors="replace").read()
            import re
            文字 = re.sub(r"&", "&amp;", 文字)
            文字 = re.sub(r"<", "&lt;", 文字)
            体 = f'<pre>{文字}</pre>'
        elif 后缀 in 文本后缀:
            文字 = open(实路, encoding="utf-8", errors="replace").read()[:200000]
            体 = f'<pre>{html.escape(文字)}</pre>'
        else:
            self.send_response(302)
            self.send_header("Location", 链接)
            self.end_headers()
            return
        大小文 = 人读(os.path.getsize(实路))
        h = (f'<!doctype html><meta charset="utf-8"><title>{html.escape(os.path.basename(相对))}</title>{样式}'
             f'{上级}<h1>{html.escape(os.path.basename(相对))}</h1>'
             f'<div class="p">{大小文} · <a href="{链接}" download>下载原文件</a></div>{体}')
        b = h.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        路 = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if 路.startswith("/__file/"):
            相对 = 路[len("/__file/"):]
        elif 路.endswith("/") or 路 == "":
            self.列目录(路.strip("/"))
            return
        else:
            相对 = 路.lstrip("/")
        实路 = os.path.join(处理.根, 相对.replace("/", os.sep))
        if not os.path.abspath(实路).startswith(os.path.abspath(处理.根)):
            self.send_error(403)
            return
        if not os.path.exists(实路):
            self.send_error(404)
            return
        if os.path.isdir(实路):
            self.列目录(相对.strip("/"))
            return
        # 视频/图片/音频走自己实现的 Range 分支，其它走后处理页
        if self.是媒体(实路):
            return self.发文件()
        self.看文件(相对)

    def do_HEAD(self):
        return self.发文件(head=True)

    # ---------- ★ Range 支持：手机拖进度条 / 边下边播全靠它 ----------
    # 标准库的 send_head 不支持 Range，整段 85 MB 一次性推过去手机要等很久、
    # 还拖不动进度条。这里自己实现 206 Partial Content。
    def 发文件(self, head: bool = False):
        路 = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        实路 = os.path.join(处理.根, 路.lstrip("/").replace("/", os.sep))
        if not os.path.abspath(实路).startswith(os.path.abspath(处理.根)):
            self.send_error(403)
            return
        if not os.path.isfile(实路):
            self.send_error(404)
            return
        try:
            总 = os.path.getsize(实路)
            f = open(实路, "rb")
        except OSError:
            self.send_error(404)
            return
        with f:
            类型 = self.guess_type(实路)
            起点, 终点 = 0, 总 - 1
            是部分 = False
            头 = self.headers.get("Range")
            if 头 and 头.startswith("bytes="):
                try:
                    段 = 头[6:].split(",")[0].strip()
                    起文, _, 止文 = 段.partition("-")
                    if 起文:
                        起点 = int(起文)
                        if 止文:
                            终点 = min(int(止文), 总 - 1)
                    else:
                        起点 = max(0, 总 - int(止文))
                    是部分 = 0 <= 起点 <= 终点 < 总
                except ValueError:
                    是部分 = False
            if 头 and not 是部分:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{总}")
                self.end_headers()
                return
            长度 = 终点 - 起点 + 1
            self.send_response(206 if 是部分 else 200)
            self.send_header("Content-Type", 类型)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(长度))
            if 是部分:
                self.send_header("Content-Range", f"bytes {起点}-{终点}/{总}")
            self.send_header("Cache-Control", "public, max-age=600")
            self.end_headers()
            if head:
                return
            f.seek(起点)
            剩 = 长度
            块 = 256 * 1024
            try:
                while 剩 > 0:
                    读 = f.read(min(块, 剩))
                    if not 读:
                        break
                    self.wfile.write(读)
                    剩 -= len(读)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def 是媒体(self, 路: str) -> bool:
        后缀 = os.path.splitext(路)[1].lower()
        return 后缀 in 视频后缀 or 后缀 in 图片后缀 or 后缀 in 音频后缀


class 服务器(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def 停() -> int:
    if not os.path.isfile(端口文件):
        print("没找到端口文件，可能没在跑")
        return 1
    端口 = open(端口文件).read().strip()
    出 = subprocess.run(["powershell", "-NoProfile", "-Command",
                         f"Get-NetTCPConnection -State Listen -LocalPort {端口} -ErrorAction SilentlyContinue | "
                         f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"],
                        capture_output=True, text=True)
    os.remove(端口文件)
    print(f"已请求停掉端口 {端口}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="把成片目录挂成网页，手机同 WiFi 直接看")
    ap.add_argument("--根", default=默认根)
    ap.add_argument("--端口", type=int, default=默认端口)
    ap.add_argument("--停", action="store_true")
    a = ap.parse_args()

    if a.停:
        return 停()

    根 = os.path.abspath(a.根)
    if not os.path.isdir(根):
        print(f"✗ 目录不存在：{根}")
        return 1
    处理.根 = 根

    try:
        服 = 服务器(("0.0.0.0", a.端口), 处理)
    except OSError as e:
        print(f"✗ 端口 {a.端口} 起不来：{e}")
        return 1

    ip = 局域网IP()
    open(端口文件, "w").write(str(a.端口))
    print(f"""
✅ 成片服务已开
   目录  {根}
   本机  http://127.0.0.1:{a.端口}
   手机  http://{ip}:{a.端口}      ← 手机连同一个 WiFi，浏览器打开这个
   停止  Ctrl+C 或 python 看成片.py --停
""")
    try:
        服.serve_forever()
    except KeyboardInterrupt:
        print("\n已停")
    finally:
        if os.path.isfile(端口文件):
            os.remove(端口文件)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
